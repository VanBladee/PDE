import mongoose, { Schema, Document } from 'mongoose';
import { createModel, DATABASE_NAMES } from '../../config/databases';

// Type for credentialing status
export type CredentialingStatus = 'x' | 'p' | 's' | 'n' | 'f' | 'o' | '';

// Interface for PDC Provider Status document
export interface IPDCProviderStatus extends Document {
  _id: string;
  Provider_ID: string;
  Location_ID: string;
  Carrier_Name: string;
  Status: CredentialingStatus;
  Last_Updated: string;
}

// Schema definition
const PDCProviderStatusSchema = new Schema<IPDCProviderStatus>({
  _id: { type: String, required: true },
  Provider_ID: { type: String, required: true, ref: 'PDCProvider' },
  Location_ID: { type: String, required: true, ref: 'PDCLocation' },
  Carrier_Name: { type: String, required: true },
  Status: { 
    type: String, 
    enum: ['x', 'p', 's', 'n', 'f', 'o', ''],
    default: 'n'
  },
  Last_Updated: { type: String, required: true }
}, {
  collection: 'PDC_provider_status',
  timestamps: false
});

// Add indexes for better query performance
PDCProviderStatusSchema.index({ Provider_ID: 1, Location_ID: 1, Carrier_Name: 1 }, { unique: true });
PDCProviderStatusSchema.index({ Status: 1 });
PDCProviderStatusSchema.index({ Carrier_Name: 1 });
PDCProviderStatusSchema.index({ Last_Updated: -1 });

// Create and export the model using the crucible database
const PDCProviderStatus = createModel<IPDCProviderStatus>(
  DATABASE_NAMES.CRUCIBLE,
  'PDCProviderStatus',
  PDCProviderStatusSchema
);

export default PDCProviderStatus;