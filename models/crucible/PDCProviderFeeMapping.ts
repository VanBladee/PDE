import { Schema, Document, Types } from 'mongoose';
import { createModel, DATABASE_NAMES } from '../../config/databases';

// Interface for PDC Provider Fee Mapping document
export interface IPDCProviderFeeMapping extends Document {
  location_id: string;
  practice_name: string;
  provider_num: number;
  provider_name: string;
  provider_abbr: string;
  npi: string;
  fee_sched_num: number;
  is_hidden: boolean;
  collected_at: Date;
}

// Schema definition
const pdcProviderFeeMappingSchema = new Schema<IPDCProviderFeeMapping>({
  location_id: {
    type: String,
    required: true,
    index: true,
  },
  practice_name: {
    type: String,
    required: true,
  },
  provider_num: {
    type: Number,
    required: true,
    index: true,
  },
  provider_name: {
    type: String,
    required: true,
  },
  provider_abbr: {
    type: String,
    required: true,
  },
  npi: {
    type: String,
    index: true,
  },
  fee_sched_num: {
    type: Number,
    required: true,
    index: true,
  },
  is_hidden: {
    type: Boolean,
    default: false,
  },
  collected_at: {
    type: Date,
    required: true,
  },
}, {
  timestamps: false,
  collection: 'PDC_provider_fee_mappings',
});

// Compound indexes for efficient queries
pdcProviderFeeMappingSchema.index({ provider_num: 1, fee_sched_num: 1 });
pdcProviderFeeMappingSchema.index({ location_id: 1, provider_num: 1 });
pdcProviderFeeMappingSchema.index({ npi: 1, collected_at: -1 });

// Static methods
pdcProviderFeeMappingSchema.statics.getProviderFeeSchedule = function(providerNum: number) {
  return this.findOne({ provider_num: providerNum, is_hidden: false })
    .sort({ collected_at: -1 })
    .exec();
};

pdcProviderFeeMappingSchema.statics.getProvidersByFeeSchedule = function(feeSchedNum: number) {
  return this.find({ fee_sched_num: feeSchedNum, is_hidden: false })
    .sort({ provider_name: 1 })
    .exec();
};

pdcProviderFeeMappingSchema.statics.getLocationProviderMappings = function(locationId: string) {
  return this.aggregate([
    {
      $match: {
        location_id: locationId,
        is_hidden: false
      }
    },
    {
      $group: {
        _id: '$fee_sched_num',
        providers: {
          $push: {
            provider_num: '$provider_num',
            provider_name: '$provider_name',
            provider_abbr: '$provider_abbr',
            npi: '$npi'
          }
        },
        count: { $sum: 1 }
      }
    },
    {
      $sort: { count: -1 }
    }
  ]);
};

// Create and export the model
const PDCProviderFeeMapping = createModel<IPDCProviderFeeMapping>(
  DATABASE_NAMES.CRUCIBLE,
  'PDCProviderFeeMapping',
  pdcProviderFeeMappingSchema
);

export default PDCProviderFeeMapping;