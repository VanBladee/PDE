import { Db, MongoClient } from 'mongodb';

interface FeeStrategyFilters {
  start?: string;
  end?: string;
  locations?: string[];
  carriers?: string[];
  procedures?: string[];
  minCount?: number;
}

export class UnifiedClaimsService {
  private db: Db;

  constructor(private mongoClient: MongoClient) {
    void this.mongoClient; // TODO: remove once wired
    this.db = mongoClient.db('activity');
  }

  buildPivotPipeline(filters?: FeeStrategyFilters): any[] {
    const pipeline: any[] = [
      {
        $match: {
          'data.patients': { $exists: true, $ne: [] }
        }
      },
      { $unwind: "$data.patients" },
      { $unwind: "$data.patients.claims" },
      { $unwind: "$data.patients.claims.procedures" },
      
      // Filter out malformed line items
      { $match: {
        // Must have procCode
        'data.patients.claims.procedures.procCode': { $exists: true, $nin: [null, ''] }
      }},
      
      // Convert money fields with coercion
      { $addFields: {
        _tempBilled: { $convert: { input: "$data.patients.claims.procedures.feeBilled", to: "double", onError: 0, onNull: 0 } },
        _tempAllowed: { $convert: { input: "$data.patients.claims.procedures.allowedAmount", to: "double", onError: 0, onNull: 0 } },
        _tempPaid: { $convert: { input: "$data.patients.claims.procedures.insAmountPaid", to: "double", onError: 0, onNull: 0 } },
        _tempWriteOff: { $convert: { input: "$data.patients.claims.procedures.writeOff", to: "double", onError: 0, onNull: 0 } }
      }},
      
      // join Job by job_id (one-to-one)
      { $lookup: {
          from: "jobs",
          localField: "job_id",
          foreignField: "_id",
          as: "job"
      }},
      { $set: { 
          job: { $first: "$job" } 
      }},
      { $set: {
          carrierName: "$job.payment.carrierName" 
      }},
      
      // Drop rows where all money fields are 0 and no carrierName
      { $match: {
        $or: [
          { carrierName: { $exists: true, $nin: [null, ''] } },
          { _tempBilled: { $gt: 0 } },
          { _tempAllowed: { $gt: 0 } },
          { _tempPaid: { $gt: 0 } },
          { _tempWriteOff: { $gt: 0 } }
        ]
      }},
      
      // resolve location code/name (for fee schedule join + UI)
      { $lookup: {
          from: { db: "registry", coll: "locations" },
          let: { locId: "$locationId" },
          pipeline: [
            { $match: { $expr: { $eq: ["$_id", "$$locId"] } } }
          ],
          as: "loc"
      }},
      { $set: {
          loc: { $first: "$loc" }
      }},
      { $set: {
          locationCode: "$loc.code",
          locationName: "$loc.name"
      }},
      
      // Join fee schedules with precedence
      { $lookup: {
        from: { db: "crucible", coll: "PDC_fee_schedules" },
        let: {
          loc: "$locationCode",
          code: "$data.patients.claims.procedures.procCode",
          carrierRaw: "$carrierName"
        },
        pipeline: [
          { $match: { $expr: { $eq: ["$location_id", "$$loc"] } } },
          { $unwind: "$fee_schedules" },
          { $unwind: "$fee_schedules.fees" },
          { $match: { $expr: { $eq: ["$fee_schedules.fees.ProcedureCode", "$$code"] } } },
      
          // Normalize both sides to uppercase strings
          { $addFields: {
              _descU: { $toUpper: "$fee_schedules.Description" },
              _carU:  { $toUpper: { $ifNull: ["$$carrierRaw", ""] } }
          }},
      
          // precedence: exact carrier mention → 1, location default → 2, global/UCR → 3
          { $addFields: {
              _isCarrierMatch: {
                $and: [
                  { $gt: [ { $strLenCP: "$_carU" }, 0 ] },
                  { $regexMatch: { input: "$_descU", regex: "$_carU" } }
                ]
              },
              _isGlobal: { $regexMatch: { input: "$_descU", regex: /UCR|DEFAULT/i } }
          }},
          { $addFields: {
              _precedence: {
                $cond: [
                  "$_isCarrierMatch", 1,
                  { $cond: [ "$_isGlobal", 3, 2 ] }
                ]
              }
          }},
          { $sort: { _precedence: 1, collected_at: -1 } },
          { $limit: 1 },
          { $project: { feeScheduled: "$fee_schedules.fees.Amount" } }
        ],
        as: "sched"
      }},
      { $set: {
        feeScheduled: {
          $convert: { input: { $first: "$sched.feeScheduled" }, to: "double", onError: null, onNull: null }
        }
      }},
      
      // Compute month + metrics (use temp fields we already converted)
      { $set: {
          feeBilled:   "$_tempBilled",
          allowed:     "$_tempAllowed",
          paid:        "$_tempPaid",
          writeOff:    "$_tempWriteOff",
          dosRecv: { $ifNull: [
            "$data.patients.claims.date_received",
            { $toDate: "$job.payment.dateIssued" }
          ]}
      }},
      
      { $set: {
          month: { $dateToString: { date: "$dosRecv", format: "%Y-%m", timezone: "America/Denver" } }
      }},
      
      { $group: {
          _id: { carrier: "$carrierName", locationId: "$locationId", locationCode: "$locationCode", locationName: "$locationName", procedure: "$data.patients.claims.procedures.procCode", month: "$month" },
          billed: { $sum: "$feeBilled" },
          allowed: { $sum: "$allowed" },
          paid: { $sum: "$paid" },
          writeOff: { $sum: "$writeOff" },
          claimCount: { $sum: 1 },
          feeScheduled: { $first: "$feeScheduled" }
      }},
      
      { $addFields: {
          writeOffPct: {
            $cond: [{ $gt: ["$billed", 0] }, { $multiply: [{ $divide: ["$writeOff", "$billed"] }, 100] }, 0]
          },
          scheduleVariance: {
            $cond: [{ $gt: ["$billed", 0] }, { $multiply: [{ $divide: [{ $subtract: ["$billed", { $ifNull: ["$feeScheduled", 0] }] }, "$billed"] }, 100] }, null]
          },
          hasIssues: {
            $gt: [{ $abs: { $subtract: ["$billed", { $add: ["$allowed", "$paid", "$writeOff"] }] } }, 1.0]
          }
      }},
      
      { $project: {
          _id: 0,
          carrier: "$_id.carrier",
          locationId: "$_id.locationId",
          locationCode: "$_id.locationCode",
          locationName: "$_id.locationName",
          procedure: "$_id.procedure",
          month: "$_id.month",
          metrics: { 
            billed: "$billed", 
            allowed: "$allowed", 
            paid: "$paid", 
            writeOff: "$writeOff", 
            writeOffPct: "$writeOffPct", 
            feeScheduled: "$feeScheduled", 
            scheduleVariance: "$scheduleVariance", 
            claimCount: "$claimCount" 
          },
          hasIssues: 1
      }}
    ];

    // Apply filters if provided
    const matchConditions: any = {};
    
    if (filters?.start || filters?.end) {
      matchConditions['dosRecv'] = {};
      if (filters.start) matchConditions['dosRecv']['$gte'] = new Date(filters.start);
      if (filters.end) matchConditions['dosRecv']['$lte'] = new Date(filters.end);
    }
    
    if (filters?.locations?.length) {
      matchConditions['_id.locationCode'] = { $in: filters.locations };
    }
    
    if (filters?.carriers?.length) {
      matchConditions['_id.carrier'] = { $in: filters.carriers };
    }
    
    if (filters?.procedures?.length) {
      matchConditions['_id.procedure'] = { $in: filters.procedures };
    }
    
    if (filters?.minCount) {
      matchConditions['claimCount'] = { $gte: filters.minCount };
    }
    
    if (Object.keys(matchConditions).length > 0) {
      // Insert filter match after grouping but before final projection
      pipeline.splice(-1, 0, { $match: matchConditions });
    }

    return pipeline;
  }

  async getFeeStrategyPivot(filters?: FeeStrategyFilters) {
    const pipeline = this.buildPivotPipeline(filters);
    
    // Track malformed records for debugging
    let droppedMalformed = 0;
    let totalLineItems = 0;
    let coverage = 'not_sampled';
    
    if (process.env.NODE_ENV !== 'production' || Math.random() < 0.01) { // Sample 1% in prod
      // Count total line items before filtering
      const countPipeline = [
        { $match: { 'data.patients': { $exists: true, $ne: [] } } },
        { $unwind: "$data.patients" },
        { $unwind: "$data.patients.claims" },
        { $unwind: "$data.patients.claims.procedures" },
        { $count: "total" }
      ];
      
      const countResult = await this.db.collection('processedclaims')
        .aggregate(countPipeline)
        .toArray();
      
      totalLineItems = countResult[0]?.total || 0;
      
      // Count after malformed filtering
      const filteredPipeline = [
        { $match: { 'data.patients': { $exists: true, $ne: [] } } },
        { $unwind: "$data.patients" },
        { $unwind: "$data.patients.claims" },
        { $unwind: "$data.patients.claims.procedures" },
        { $match: {
          'data.patients.claims.procedures.procCode': { $exists: true, $nin: [null, ''] }
        }},
        { $addFields: {
          _tempBilled: { $convert: { input: "$data.patients.claims.procedures.feeBilled", to: "double", onError: 0, onNull: 0 } },
          _tempAllowed: { $convert: { input: "$data.patients.claims.procedures.allowedAmount", to: "double", onError: 0, onNull: 0 } },
          _tempPaid: { $convert: { input: "$data.patients.claims.procedures.insAmountPaid", to: "double", onError: 0, onNull: 0 } },
          _tempWriteOff: { $convert: { input: "$data.patients.claims.procedures.writeOff", to: "double", onError: 0, onNull: 0 } }
        }},
        { $lookup: {
          from: "jobs",
          localField: "job_id",
          foreignField: "_id",
          as: "job"
        }},
        { $set: { job: { $first: "$job" } }},
        { $set: { carrierName: "$job.payment.carrierName" }},
        { $match: {
          $or: [
            { carrierName: { $exists: true, $nin: [null, ''] } },
            { _tempBilled: { $gt: 0 } },
            { _tempAllowed: { $gt: 0 } },
            { _tempPaid: { $gt: 0 } },
            { _tempWriteOff: { $gt: 0 } }
          ]
        }},
        { $count: "filtered" }
      ];
      
      const filteredResult = await this.db.collection('processedclaims')
        .aggregate(filteredPipeline)
        .toArray();
      
      const filteredCount = filteredResult[0]?.filtered || 0;
      droppedMalformed = totalLineItems - filteredCount;
      coverage = totalLineItems > 0 ? `${((filteredCount / totalLineItems) * 100).toFixed(1)}%` : 'n/a';
      
      console.log(`Data quality: { droppedMalformed: ${droppedMalformed}, processed: ${filteredCount}, coverage: ${coverage} }`);
    }

    // Debug mode to see where docs disappear
    if (process.env.DEBUG_PIVOT === "1") {
      const activity = this.db.collection("processedclaims");
      const diag = await activity.aggregate([
        // 1) just unwind
        { $match: { "data.patients": { $exists: true, $ne: [] } } },
        { $unwind: "$data.patients" },
        { $unwind: "$data.patients.claims" },
        { $unwind: "$data.patients.claims.procedures" },
        { $limit: 5 },
        { $project: {
            _id: 1,
            job_id: 1,
            locationId: 1,
            proc: "$data.patients.claims.procedures.procCode",
            dr: "$data.patients.claims.date_received"
        }}
      ]).toArray();
      // eslint-disable-next-line no-console
      console.log("DEBUG_PIVOT sample after unwind:", JSON.stringify(diag, null, 2));
    }

    const rows = await this.db.collection('processedclaims')
      .aggregate(pipeline, { allowDiskUse: true })
      .toArray();

    return {
      rows,
      summary: {
        totalRows: rows.length,
        dateRange: { start: filters?.start, end: filters?.end },
        lastUpdated: new Date()
      }
    };
  }
}