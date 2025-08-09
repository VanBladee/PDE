import { Schema, Document, Types } from 'mongoose';
import { createModel, DATABASE_NAMES } from '../../config/databases';

// Interface for Analytics document
export interface IAnalytics extends Document {
  id: Types.ObjectId;
  locationId: Types.ObjectId;
  claim_stats: {
    oon_claims: string;
    denied_claims: string;
  };
  usage: {
    finalized_claims: number;
    processed_claims: number;
  };
  createdAt: Date;
  updatedAt: Date;
}

// Mongoose schema for Analytics
const analyticsSchema = new Schema<IAnalytics>({
  locationId: {
    type: Schema.Types.ObjectId,
    required: true,
    ref: 'Location', // Reference to Location model in registry database
  },
  claim_stats: {
    oon_claims: {
      type: String,
      default: '',
    },
    denied_claims: {
      type: String,
      default: '',
    },
  },
  usage: {
    finalized_claims: {
      type: Number,
      required: true,
      default: 0,
    },
    processed_claims: {
      type: Number,
      required: true,
      default: 0,
    },
  },
}, {
  timestamps: true, // Automatically add createdAt and updatedAt fields
  // Transform _id to id when converting to JSON
  toJSON: {
    transform: function(doc: any, ret: any) {
      ret.id = ret._id;
      delete ret._id;
      delete ret.__v;
      return ret;
    }
  }
});

// Create and export the Analytics model using the activity database
const Analytics = createModel<IAnalytics>(
  DATABASE_NAMES.ACTIVITY,
  'Analytics',
  analyticsSchema
);

export default Analytics; 