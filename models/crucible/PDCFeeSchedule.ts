import { Schema, Document, Types } from 'mongoose';
import { createModel, DATABASE_NAMES } from '../../config/databases';

// Interface for PDC Fee Schedule document
export interface IPDCFeeSchedule extends Document {
  location_id: string;
  practice_name: string;
  address: string;
  fee_schedules: {
    FeeSchedNum: number;
    Description: string;
    FeeSchedType: string;
    IsGlobal: boolean;
    fees: {
      FeeNum: number;
      Amount: number;
      FeeSched: number;
      CodeNum: number;
      ProcedureCode: string;  // CDT code
      Description: string;     // Procedure description
      ClinicNum: number;
      ProvNum: number;
    }[];
    fee_count: number;
  }[];
  summary: {
    total_fee_schedules: number;
    total_fees: number;
    total_providers: number;
    unique_procedures: number;
    collection_time_seconds: number;
  };
  collected_at: Date;
}

// Schema definition
const pdcFeeScheduleSchema = new Schema<IPDCFeeSchedule>({
  location_id: {
    type: String,
    required: true,
    index: true,
  },
  practice_name: {
    type: String,
    required: true,
  },
  address: {
    type: String,
    required: true,
  },
  fee_schedules: [{
    FeeSchedNum: {
      type: Number,
      required: true,
    },
    Description: {
      type: String,
      required: true,
    },
    FeeSchedType: String,
    IsGlobal: Boolean,
    fees: [{
      FeeNum: Number,
      Amount: {
        type: Number,
        required: true,
      },
      FeeSched: Number,
      CodeNum: Number,
      ProcedureCode: {
        type: String,
        required: true,
        index: true,
      },
      Description: String,
      ClinicNum: Number,
      ProvNum: Number,
    }],
    fee_count: Number,
  }],
  summary: {
    total_fee_schedules: Number,
    total_fees: Number,
    total_providers: Number,
    unique_procedures: Number,
    collection_time_seconds: Number,
  },
  collected_at: {
    type: Date,
    required: true,
    index: true,
  },
}, {
  timestamps: false,
  collection: 'PDC_fee_schedules',
});

// Compound indexes for efficient queries
pdcFeeScheduleSchema.index({ location_id: 1, collected_at: -1 });
pdcFeeScheduleSchema.index({ 'fee_schedules.fees.ProcedureCode': 1 });
pdcFeeScheduleSchema.index({ 'fee_schedules.FeeSchedNum': 1 });

// Instance methods
pdcFeeScheduleSchema.methods.getFeeForProcedure = function(procedureCode: string, feeSchedNum?: number) {
  for (const schedule of this.fee_schedules) {
    if (feeSchedNum && schedule.FeeSchedNum !== feeSchedNum) continue;
    
    const fee = schedule.fees.find((f: any) => f.ProcedureCode === procedureCode);
    if (fee) {
      return {
        amount: fee.Amount,
        scheduleDescription: schedule.Description,
        scheduleNum: schedule.FeeSchedNum,
      };
    }
  }
  return null;
};

// Static methods
pdcFeeScheduleSchema.statics.getLatestForLocation = function(locationId: string) {
  return this.findOne({ location_id: locationId })
    .sort({ collected_at: -1 })
    .exec();
};

pdcFeeScheduleSchema.statics.compareCarrierFees = function(procedureCode: string, locationId?: string) {
  const matchStage: any = { 'fee_schedules.fees.ProcedureCode': procedureCode };
  if (locationId) matchStage.location_id = locationId;
  
  return this.aggregate([
    { $match: matchStage },
    { $unwind: '$fee_schedules' },
    { $unwind: '$fee_schedules.fees' },
    { $match: { 'fee_schedules.fees.ProcedureCode': procedureCode } },
    {
      $group: {
        _id: '$fee_schedules.Description',
        avgFee: { $avg: '$fee_schedules.fees.Amount' },
        minFee: { $min: '$fee_schedules.fees.Amount' },
        maxFee: { $max: '$fee_schedules.fees.Amount' },
        count: { $sum: 1 },
      }
    },
    { $sort: { avgFee: -1 } }
  ]);
};

// Create and export the model
const PDCFeeSchedule = createModel<IPDCFeeSchedule>(
  DATABASE_NAMES.CRUCIBLE,
  'PDCFeeSchedule',
  pdcFeeScheduleSchema
);

export default PDCFeeSchedule;