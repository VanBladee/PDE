import { Schema, Document, Types } from 'mongoose';
import { createModel, DATABASE_NAMES } from '../../config/databases';

// Interface for Carriers Registry document (real user data)
export interface ICarriersRegistry extends Document {
  id: Types.ObjectId;
  carrierId: string;
  carrierName: string;
  status: 'active' | 'inactive';
  npi?: string;
  metadata?: {
    region?: string;
    planTypes?: string[];
    lastContractUpdate?: Date;
  };
  lastUpdated: Date;
}

// Schema for the real carriers registry in crucible database
const carriersRegistrySchema = new Schema<ICarriersRegistry>({
  carrierId: {
    type: String,
    required: true,
    trim: true,
    index: true,
  },
  carrierName: {
    type: String,
    required: true,
    trim: true,
    index: true,
  },
  status: {
    type: String,
    enum: ['active', 'inactive'],
    required: true,
    default: 'active',
    index: true,
  },
  npi: {
    type: String,
    trim: true,
  },
  metadata: {
    region: String,
    planTypes: [String],
    lastContractUpdate: Date,
  },
  lastUpdated: {
    type: Date,
    default: Date.now,
  },
}, {
  timestamps: true,
  toJSON: {
    transform: function(doc: any, ret: any) {
      ret.id = ret._id;
      delete ret._id;
      delete ret.__v;
      return ret;
    }
  }
});

// Create and export the model using the crucible database
const CarriersRegistry = createModel<ICarriersRegistry>(
  DATABASE_NAMES.CRUCIBLE,
  'carriersRegistry',
  carriersRegistrySchema
);

export default CarriersRegistry;