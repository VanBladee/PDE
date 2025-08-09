import mongoose, { Schema, Document } from 'mongoose';
import { createModel, DATABASE_NAMES } from '../../config/databases';

// Interface for PDC Provider document
export interface IPDCProvider extends Document {
  _id: string;
  Provider_Name: string;
}

// Schema definition
const PDCProviderSchema = new Schema<IPDCProvider>({
  _id: { type: String, required: true },
  Provider_Name: { type: String, required: true }
}, {
  collection: 'PDC_providers',
  timestamps: false
});

// Create and export the model using the crucible database
const PDCProvider = createModel<IPDCProvider>(
  DATABASE_NAMES.CRUCIBLE,
  'PDCProvider',
  PDCProviderSchema
);

export default PDCProvider;