import { Schema, Document, Types } from 'mongoose';
import { createModel, DATABASE_NAMES } from '../../config/databases';

// Interface for Carrier document
export interface ICarrier extends Document {
  id: Types.ObjectId;
  name: string;
  code: string;
  type: 'airline' | 'shipping' | 'freight' | 'other';
  active: boolean;
  metadata: Record<string, any>;
}

// Schema definition
const carrierSchema = new Schema<ICarrier>({
  name: {
    type: String,
    required: true,
    trim: true,
  },
  code: {
    type: String,
    required: true,
    unique: true,
    uppercase: true,
  },
  type: {
    type: String,
    enum: ['airline', 'shipping', 'freight', 'other'],
    required: true,
  },
  active: {
    type: Boolean,
    default: true,
  },
  metadata: {
    type: Schema.Types.Mixed,
    default: {},
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

// Create and export the model using the od_live database with lazy loading
const Carrier = createModel<ICarrier>(
  DATABASE_NAMES.OD_LIVE,
  'Carrier',
  carrierSchema
);

export default Carrier; 