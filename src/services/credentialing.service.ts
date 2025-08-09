import { Db, MongoClient } from 'mongodb';

export interface CredentialingFilters {
  start?: string;
  end?: string;
  locations?: string[];
  carriers?: string[];
  status?: 'ACTIVE' | 'PENDING' | 'TERMINATED' | 'OON' | 'UNKNOWN';
  issuesOnly?: boolean;
}

export type CredentialingAlert = 'NETWORK_MISMATCH' | 'EXPIRING_SOON' | 'STALE_DATA' | 'PENDING_EFFECTIVE';

export interface CredentialingRow {
  provider_npi: string;
  provider_name: string;
  tin: string;
  location_id: string;
  carrier: string;
  plan?: string | null;
  status: 'ACTIVE' | 'PENDING' | 'TERMINATED' | 'OON' | 'UNKNOWN';
  effective_date?: string | null;
  term_date?: string | null;
  last_verified_at?: string | null;
  verification_source?: string | null;
  source_url?: string | null;
  notes?: string | null;
  is_manual_override: boolean;
  override_by?: string | null;
  override_at?: string | null;
  alerts: CredentialingAlert[];
}

export interface CredentialingResponse {
  rows: CredentialingRow[];
  summary: {
    totalRows: number;
    dateRange: { start?: string; end?: string };
    lastUpdated: Date;
  };
}

export class CredentialingService {
  private db: Db;

  constructor(mongoClient: MongoClient) {
    this.db = mongoClient.db('crucible');
  }

  buildCredentialingPipeline(filters?: CredentialingFilters): any[] {
    const pipeline: any[] = [];

    // Start with PDC_provider_status collection
    const matchConditions: any = {};
    
    // Apply filters
    if (filters?.locations?.length) {
      matchConditions.location_id = { $in: filters.locations };
    }
    
    if (filters?.carriers?.length) {
      matchConditions.carrier = { $in: filters.carriers };
    }
    
    if (filters?.status) {
      matchConditions.status = filters.status;
    }

    if (Object.keys(matchConditions).length > 0) {
      pipeline.push({ $match: matchConditions });
    }

    // Join with registry.locations for location name
    pipeline.push({
      $lookup: {
        from: { db: "registry", coll: "locations" },
        let: { locId: "$location_id" },
        pipeline: [
          { $match: { $expr: { $eq: ["$code", "$$locId"] } } }
        ],
        as: "location"
      }
    });

    // Unwind location (optional, as location might not exist)
    pipeline.push({
      $set: {
        location_name: { $ifNull: [{ $first: "$location.name" }, "$location_id"] }
      }
    });

    // Calculate dates for alert computation
    const today = new Date();
    const thirtyDaysFromNow = new Date(today.getTime() + 30 * 24 * 60 * 60 * 1000);
    const thirtyDaysAgo = new Date(today.getTime() - 30 * 24 * 60 * 60 * 1000);
    const ninetyDaysAgo = new Date(today.getTime() - 90 * 24 * 60 * 60 * 1000);

    // Add fields for alert calculation
    pipeline.push({
      $addFields: {
        // Convert string dates to Date objects for comparison
        effective_date_obj: {
          $cond: [
            { $eq: ["$effective_date", null] },
            null,
            { $dateFromString: { dateString: "$effective_date", onError: null } }
          ]
        },
        term_date_obj: {
          $cond: [
            { $eq: ["$term_date", null] },
            null,
            { $dateFromString: { dateString: "$term_date", onError: null } }
          ]
        },
        last_verified_obj: {
          $cond: [
            { $eq: ["$last_verified_at", null] },
            null,
            { $dateFromString: { dateString: "$last_verified_at", onError: null } }
          ]
        }
      }
    });

    // For NETWORK_MISMATCH, we need to check for paid claims in last 90 days
    // This requires a lookup to activity.processedclaims
    pipeline.push({
      $lookup: {
        from: { db: "activity", coll: "processedclaims" },
        let: { 
          providerNpi: "$provider_npi",
          locationId: "$location_id",
          carrier: "$carrier"
        },
        pipeline: [
          { 
            $match: { 
              $expr: {
                $and: [
                  { $gte: ["$data.patients.claims.date_received", ninetyDaysAgo] },
                  { $gt: ["$data.patients.claims.procedures.insAmountPaid", 0] }
                ]
              }
            }
          },
          { $unwind: "$data.patients" },
          { $unwind: "$data.patients.claims" },
          { $unwind: "$data.patients.claims.procedures" },
          {
            $match: {
              $expr: {
                $and: [
                  { $eq: ["$data.patients.claims.provider_npi", "$$providerNpi"] },
                  { $gt: ["$data.patients.claims.procedures.insAmountPaid", 0] }
                ]
              }
            }
          },
          { $limit: 1 },
          { $project: { _id: 1 } }
        ],
        as: "recentPaidClaims"
      }
    });

    // Calculate alerts
    pipeline.push({
      $addFields: {
        alerts: {
          $filter: {
            input: [
              // NETWORK_MISMATCH: status is OON but has paid claims in last 90 days
              {
                $cond: [
                  {
                    $and: [
                      { $eq: ["$status", "OON"] },
                      { $gt: [{ $size: "$recentPaidClaims" }, 0] }
                    ]
                  },
                  "NETWORK_MISMATCH",
                  null
                ]
              },
              // EXPIRING_SOON: term_date is within 30 days
              {
                $cond: [
                  {
                    $and: [
                      { $ne: ["$term_date_obj", null] },
                      { $gte: ["$term_date_obj", today] },
                      { $lte: ["$term_date_obj", thirtyDaysFromNow] }
                    ]
                  },
                  "EXPIRING_SOON",
                  null
                ]
              },
              // STALE_DATA: last_verified_at is older than 30 days
              {
                $cond: [
                  {
                    $and: [
                      { $ne: ["$last_verified_obj", null] },
                      { $lt: ["$last_verified_obj", thirtyDaysAgo] }
                    ]
                  },
                  "STALE_DATA",
                  null
                ]
              },
              // PENDING_EFFECTIVE: status is PENDING and effective_date is in the future
              {
                $cond: [
                  {
                    $and: [
                      { $eq: ["$status", "PENDING"] },
                      { $ne: ["$effective_date_obj", null] },
                      { $gt: ["$effective_date_obj", today] }
                    ]
                  },
                  "PENDING_EFFECTIVE",
                  null
                ]
              }
            ],
            cond: { $ne: ["$$this", null] }
          }
        }
      }
    });

    // Filter for issuesOnly if specified
    if (filters?.issuesOnly) {
      pipeline.push({
        $match: {
          $expr: { $gt: [{ $size: "$alerts" }, 0] }
        }
      });
    }

    // Apply date range filter on last_verified_at if specified
    if (filters?.start || filters?.end) {
      const dateMatch: any = {};
      if (filters.start) {
        dateMatch.$gte = new Date(filters.start);
      }
      if (filters.end) {
        dateMatch.$lte = new Date(filters.end);
      }
      pipeline.push({
        $match: {
          last_verified_obj: dateMatch
        }
      });
    }

    // Project final output
    pipeline.push({
      $project: {
        _id: 0,
        provider_npi: 1,
        provider_name: 1,
        tin: 1,
        location_id: 1,
        carrier: 1,
        plan: { $ifNull: ["$plan", null] },
        status: 1,
        effective_date: { $ifNull: ["$effective_date", null] },
        term_date: { $ifNull: ["$term_date", null] },
        last_verified_at: { $ifNull: ["$last_verified_at", null] },
        verification_source: { $ifNull: ["$verification_source", null] },
        source_url: { $ifNull: ["$source_url", null] },
        notes: { $ifNull: ["$notes", null] },
        is_manual_override: { $ifNull: ["$is_manual_override", false] },
        override_by: { $ifNull: ["$override_by", null] },
        override_at: { $ifNull: ["$override_at", null] },
        alerts: 1
      }
    });

    // Sort by provider_name and location
    pipeline.push({
      $sort: { provider_name: 1, location_id: 1, carrier: 1 }
    });

    return pipeline;
  }

  async getCredentialingStatus(filters?: CredentialingFilters): Promise<CredentialingResponse> {
    const pipeline = this.buildCredentialingPipeline(filters);
    
    const rows = await this.db.collection('PDC_provider_status')
      .aggregate<CredentialingRow>(pipeline, { allowDiskUse: true })
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