import { Schema, Document, Types } from 'mongoose';
import { createModel, DATABASE_NAMES } from '../../config/databases';

// Interface for Insurance Carrier document
export interface IInsuranceCarrier extends Document {
  id: Types.ObjectId;
  name: string;
  code?: string;
  type: 'dental' | 'medical' | 'vision' | 'hybrid';
  active: boolean;
  networkStatus: 'in_network' | 'out_of_network' | 'unknown';
  metadata: {
    // Standard fee schedules
    feeSchedule?: Record<string, number>; // CDT code -> fee mapping
    contractTerms?: {
      effectiveDate?: Date;
      expirationDate?: Date;
      autoRenewal?: boolean;
      terminationNotice?: number; // days
    };
    // Payment processing info
    paymentInfo?: {
      averagePaymentTime?: number; // days
      paymentMethod?: 'check' | 'eft' | 'ach' | 'electronic';
      denialRate?: number; // percentage
    };
    // Contact and administrative info
    contact?: {
      providerServices?: string;
      claimsAddress?: string;
      phone?: string;
      website?: string;
    };
    // Performance metrics
    performance?: {
      claimVolume?: number;
      totalRevenue?: number;
      averageClaimAmount?: number;
      lastUpdated?: Date;
    };
  };
  // Audit fields
  createdBy?: Types.ObjectId;
  updatedBy?: Types.ObjectId;
}

// Schema definition for Insurance Carriers
const insuranceCarrierSchema = new Schema<IInsuranceCarrier>({
  name: {
    type: String,
    required: true,
    trim: true,
    index: true, // For fast carrier name lookups
  },
  code: {
    type: String,
    trim: true,
    uppercase: true,
    sparse: true, // Allows multiple null values but unique non-null values
  },
  type: {
    type: String,
    enum: ['dental', 'medical', 'vision', 'hybrid'],
    required: true,
    default: 'dental',
  },
  active: {
    type: Boolean,
    default: true,
    index: true, // For filtering active carriers
  },
  networkStatus: {
    type: String,
    enum: ['in_network', 'out_of_network', 'unknown'],
    default: 'unknown',
    index: true, // For network filtering
  },
  metadata: {
    // Fee schedules - CDT code to fee mapping
    feeSchedule: {
      type: Schema.Types.Mixed,
      default: {},
    },
    // Contract terms
    contractTerms: {
      effectiveDate: Date,
      expirationDate: Date,
      autoRenewal: { type: Boolean, default: false },
      terminationNotice: { type: Number, default: 30 }, // days
    },
    // Payment processing information
    paymentInfo: {
      averagePaymentTime: Number, // days
      paymentMethod: {
        type: String,
        enum: ['check', 'eft', 'ach', 'electronic'],
      },
      denialRate: Number, // percentage
    },
    // Contact information
    contact: {
      providerServices: String,
      claimsAddress: String,
      phone: String,
      website: String,
    },
    // Performance metrics (calculated periodically)
    performance: {
      claimVolume: { type: Number, default: 0 },
      totalRevenue: { type: Number, default: 0 },
      averageClaimAmount: { type: Number, default: 0 },
      lastUpdated: Date,
    },
  },
  // Audit fields
  createdBy: {
    type: Schema.Types.ObjectId,
    ref: 'User',
  },
  updatedBy: {
    type: Schema.Types.ObjectId,
    ref: 'User',
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

// Indexes for performance
insuranceCarrierSchema.index({ name: 1, active: 1 });
insuranceCarrierSchema.index({ type: 1, networkStatus: 1 });
insuranceCarrierSchema.index({ 'metadata.performance.claimVolume': -1 });

// Create and export the model using the od_live database
const InsuranceCarrier = createModel<IInsuranceCarrier>(
  DATABASE_NAMES.OD_LIVE,
  'InsuranceCarrier',
  insuranceCarrierSchema
);

export default InsuranceCarrier;