import { Schema, Document, Types } from 'mongoose';
import { createModel, DATABASE_NAMES } from '../../config/databases';

// Interface for fee change
interface IFeeChange {
  fee_sched_num: number;
  code_num: number;
  procedure_code: string;
  old_amount: number;
  new_amount: number;
  change_pct: number;
  detected_date: Date;
}

// Interface for PDC Fee History document
export interface IPDCFeeHistory extends Document {
  location_id: string;
  practice_name: string;
  fee_schedules: any[]; // Snapshot of fee schedules at this point in time
  collected_at: Date;
  changes_detected: IFeeChange[];
}

// Schema definition
const feeChangeSchema = new Schema<IFeeChange>({
  fee_sched_num: {
    type: Number,
    required: true,
  },
  code_num: Number,
  procedure_code: {
    type: String,
    required: true,
    index: true,
  },
  old_amount: {
    type: Number,
    required: true,
  },
  new_amount: {
    type: Number,
    required: true,
  },
  change_pct: Number,
  detected_date: {
    type: Date,
    required: true,
  },
});

const pdcFeeHistorySchema = new Schema<IPDCFeeHistory>({
  location_id: {
    type: String,
    required: true,
    index: true,
  },
  practice_name: {
    type: String,
    required: true,
  },
  fee_schedules: {
    type: Schema.Types.Mixed,
    required: true,
  },
  collected_at: {
    type: Date,
    required: true,
    index: true,
  },
  changes_detected: [feeChangeSchema],
}, {
  timestamps: false,
  collection: 'PDC_fee_history',
});

// Indexes
pdcFeeHistorySchema.index({ location_id: 1, collected_at: -1 });
pdcFeeHistorySchema.index({ 'changes_detected.procedure_code': 1 });
pdcFeeHistorySchema.index({ 'changes_detected.change_pct': -1 });

// Instance methods
pdcFeeHistorySchema.methods.getSignificantChanges = function(minChangePct: number = 5) {
  return this.changes_detected
    .filter((change: IFeeChange) => Math.abs(change.change_pct) >= minChangePct)
    .sort((a: IFeeChange, b: IFeeChange) => Math.abs(b.change_pct) - Math.abs(a.change_pct));
};

// Static methods
pdcFeeHistorySchema.statics.getFeeHistory = function(locationId: string, procedureCode: string, limit: number = 10) {
  return this.aggregate([
    {
      $match: {
        location_id: locationId,
        $or: [
          { 'changes_detected.procedure_code': procedureCode },
          { 'fee_schedules.fees.ProcedureCode': procedureCode }
        ]
      }
    },
    { $sort: { collected_at: -1 } },
    { $limit: limit },
    {
      $project: {
        collected_at: 1,
        fee_data: {
          $map: {
            input: '$fee_schedules',
            as: 'schedule',
            in: {
              schedule_num: '$$schedule.FeeSchedNum',
              description: '$$schedule.Description',
              fee: {
                $arrayElemAt: [
                  {
                    $filter: {
                      input: '$$schedule.fees',
                      as: 'fee',
                      cond: { $eq: ['$$fee.ProcedureCode', procedureCode] }
                    }
                  },
                  0
                ]
              }
            }
          }
        },
        changes: {
          $filter: {
            input: '$changes_detected',
            as: 'change',
            cond: { $eq: ['$$change.procedure_code', procedureCode] }
          }
        }
      }
    }
  ]);
};

pdcFeeHistorySchema.statics.getTrendAnalysis = function(locationId: string, procedureCodes: string[], dateRange?: { start: Date; end: Date }) {
  const matchStage: any = { location_id: locationId };
  if (dateRange) {
    matchStage.collected_at = { $gte: dateRange.start, $lte: dateRange.end };
  }
  
  return this.aggregate([
    { $match: matchStage },
    { $unwind: '$fee_schedules' },
    { $unwind: '$fee_schedules.fees' },
    {
      $match: {
        'fee_schedules.fees.ProcedureCode': { $in: procedureCodes }
      }
    },
    {
      $group: {
        _id: {
          date: { $dateToString: { format: '%Y-%m', date: '$collected_at' } },
          procedure: '$fee_schedules.fees.ProcedureCode',
          schedule: '$fee_schedules.Description'
        },
        avgFee: { $avg: '$fee_schedules.fees.Amount' },
        minFee: { $min: '$fee_schedules.fees.Amount' },
        maxFee: { $max: '$fee_schedules.fees.Amount' }
      }
    },
    {
      $sort: {
        '_id.procedure': 1,
        '_id.schedule': 1,
        '_id.date': 1
      }
    }
  ]);
};

// Create and export the model
const PDCFeeHistory = createModel<IPDCFeeHistory>(
  DATABASE_NAMES.CRUCIBLE,
  'PDCFeeHistory',
  pdcFeeHistorySchema
);

export default PDCFeeHistory;