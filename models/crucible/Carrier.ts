import { Schema, model, Document } from 'mongoose';

export interface ICarrier extends Document {
  _id: string;
  carrierId: string;
  carrierName: string;
  lastUpdated: Date;
  metadata?: {
    region?: string;
    planTypes?: string[];
    lastContractUpdate?: Date;
  };
  npi?: string;
  status: string;
}

const CarrierSchema = new Schema({
  _id: String,
  carrierId: String,
  carrierName: String,
  lastUpdated: Date,
  metadata: {
    region: String,
    planTypes: [String],
    lastContractUpdate: Date
  },
  npi: String,
  status: String
}, { collection: 'carriersRegistry' });

export const Carrier = model<ICarrier>('Carrier', CarrierSchema);