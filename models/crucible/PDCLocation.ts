import mongoose, { Schema, Document } from 'mongoose';
import { createModel, DATABASE_NAMES } from '../../config/databases';

// Interface for PDC Location document
export interface IPDCLocation extends Document {
  _id: string;
  Location_Name: string;
  Provider_ID: string;
  Tax_ID: string;
  Is_Dormant: boolean;
  Metadata?: {
    hire_date?: string;
    submission_date?: string;
    effective_date?: string;
    row_id?: number;
  };
  Percentage: string;
  State: string;
}

// Schema definition
const PDCLocationSchema = new Schema<IPDCLocation>({
  _id: { type: String, required: true },
  Location_Name: { type: String, required: true },
  Provider_ID: { type: String, required: true, ref: 'PDCProvider' },
  Tax_ID: { type: String, required: true },
  Is_Dormant: { type: Boolean, default: false },
  Metadata: {
    hire_date: { type: String },
    submission_date: { type: String },
    effective_date: { type: String },
    row_id: { type: Number }
  },
  Percentage: { type: String },
  State: { type: String, required: true }
}, {
  collection: 'PDC_locations',
  timestamps: false
});

// Add indexes for better query performance
PDCLocationSchema.index({ Provider_ID: 1 });
PDCLocationSchema.index({ State: 1 });
PDCLocationSchema.index({ Is_Dormant: 1 });

// Create and export the model using the crucible database
const PDCLocation = createModel<IPDCLocation>(
  DATABASE_NAMES.CRUCIBLE,
  'PDCLocation',
  PDCLocationSchema
);

export default PDCLocation;