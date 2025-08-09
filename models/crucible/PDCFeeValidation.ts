import { Schema, Document, Types } from 'mongoose';
import { createModel, DATABASE_NAMES } from '../../config/databases';

// Interface for validation anomaly
interface IValidationAnomaly {
  procedure_code: string;
  procedure_desc: string;
  scheduled_fee: number;
  avg_billed: number;
  variance_amount: number;
  variance_pct: number;
  claim_count: number;
  confidence_score: number;
}

// Interface for schedule validation
interface IScheduleValidation {
  fee_sched_num: number;
  description: string;
  total_fees: number;
  fees_validated: number;
  anomalies: IValidationAnomaly[];
  confidence_scores: {
    high: number;    // 90%+ confidence
    medium: number;  // 70-89% confidence
    low: number;     // <70% confidence
  };
  summary_stats: {
    avg_variance_pct: number;
    max_variance_pct: number;
    total_variance_amount: number;
  };
}

// Interface for PDC Fee Validation document
export interface IPDCFeeValidation extends Document {
  location_id: string;
  practice_name: string;
  validation_date: Date;
  claims_analyzed: number;
  lookback_days: number;
  schedule_validations: IScheduleValidation[];
  overall_stats: {
    total_schedules: number;
    total_fees: number;
    total_validated: number;
    validation_rate: number;
    total_anomalies: number;
    avg_confidence: number;
  };
}

// Schema definition
const validationAnomalySchema = new Schema<IValidationAnomaly>({
  procedure_code: {
    type: String,
    required: true,
  },
  procedure_desc: String,
  scheduled_fee: {
    type: Number,
    required: true,
  },
  avg_billed: {
    type: Number,
    required: true,
  },
  variance_amount: Number,
  variance_pct: Number,
  claim_count: Number,
  confidence_score: Number,
});

const scheduleValidationSchema = new Schema<IScheduleValidation>({
  fee_sched_num: {
    type: Number,
    required: true,
  },
  description: String,
  total_fees: Number,
  fees_validated: Number,
  anomalies: [validationAnomalySchema],
  confidence_scores: {
    high: Number,
    medium: Number,
    low: Number,
  },
  summary_stats: {
    avg_variance_pct: Number,
    max_variance_pct: Number,
    total_variance_amount: Number,
  },
});

const pdcFeeValidationSchema = new Schema<IPDCFeeValidation>({
  location_id: {
    type: String,
    required: true,
    index: true,
  },
  practice_name: {
    type: String,
    required: true,
  },
  validation_date: {
    type: Date,
    required: true,
    index: true,
  },
  claims_analyzed: Number,
  lookback_days: Number,
  schedule_validations: [scheduleValidationSchema],
  overall_stats: {
    total_schedules: Number,
    total_fees: Number,
    total_validated: Number,
    validation_rate: Number,
    total_anomalies: Number,
    avg_confidence: Number,
  },
}, {
  timestamps: false,
  collection: 'PDC_fee_validation',
});

// Indexes
pdcFeeValidationSchema.index({ location_id: 1, validation_date: -1 });
pdcFeeValidationSchema.index({ 'schedule_validations.anomalies.variance_pct': -1 });

// Instance methods
pdcFeeValidationSchema.methods.getAnomalies = function(thresholdPct: number = 10) {
  const anomalies: any[] = [];
  
  this.schedule_validations.forEach((validation: IScheduleValidation) => {
    validation.anomalies.forEach((anomaly: IValidationAnomaly) => {
      if (Math.abs(anomaly.variance_pct) >= thresholdPct) {
        anomalies.push({
          ...anomaly,
          fee_schedule: validation.description,
          fee_sched_num: validation.fee_sched_num,
          location: this.practice_name,
        });
      }
    });
  });
  
  return anomalies.sort((a, b) => Math.abs(b.variance_pct) - Math.abs(a.variance_pct));
};

// Static methods
pdcFeeValidationSchema.statics.getLatestValidation = function(locationId: string) {
  return this.findOne({ location_id: locationId })
    .sort({ validation_date: -1 })
    .exec();
};

pdcFeeValidationSchema.statics.getHighVarianceProcedures = function(minVariancePct: number = 15) {
  return this.aggregate([
    { $unwind: '$schedule_validations' },
    { $unwind: '$schedule_validations.anomalies' },
    {
      $match: {
        $or: [
          { 'schedule_validations.anomalies.variance_pct': { $gte: minVariancePct } },
          { 'schedule_validations.anomalies.variance_pct': { $lte: -minVariancePct } }
        ]
      }
    },
    {
      $group: {
        _id: '$schedule_validations.anomalies.procedure_code',
        procedure_desc: { $first: '$schedule_validations.anomalies.procedure_desc' },
        avg_variance_pct: { $avg: '$schedule_validations.anomalies.variance_pct' },
        max_variance_pct: { $max: '$schedule_validations.anomalies.variance_pct' },
        location_count: { $addToSet: '$location_id' },
        total_occurrences: { $sum: 1 }
      }
    },
    {
      $project: {
        procedure_code: '$_id',
        procedure_desc: 1,
        avg_variance_pct: { $round: ['$avg_variance_pct', 2] },
        max_variance_pct: { $round: ['$max_variance_pct', 2] },
        affected_locations: { $size: '$location_count' },
        total_occurrences: 1
      }
    },
    { $sort: { avg_variance_pct: -1 } }
  ]);
};

// Create and export the model
const PDCFeeValidation = createModel<IPDCFeeValidation>(
  DATABASE_NAMES.CRUCIBLE,
  'PDCFeeValidation',
  pdcFeeValidationSchema
);

export default PDCFeeValidation;