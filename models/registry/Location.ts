import { Schema, model, Document, Types } from 'mongoose';

// Interface to represent a Location document
export interface ILocation extends Document {
  id: Types.ObjectId;
  practice_name: string;
  phoneNumber: string;
  address: string;
  taxId: string;
  pms_db: string;
  is_dso: boolean;
  dso_admin: string;
  users: Types.ObjectId[];
  region: string;
  org: Types.ObjectId;
}

// Mongoose schema for Location
const locationSchema = new Schema<ILocation>({
  practice_name: {
    type: String,
    required: true,
    trim: true,
  },
  phoneNumber: {
    type: String,
    required: true,
    trim: true,
  },
  address: {
    type: String,
    required: true,
    trim: true,
  },
  taxId: {
    type: String,
    required: true,
    trim: true,
  },
  pms_db: {
    type: String,
    required: true,
    trim: true,
  },
  is_dso: {
    type: Boolean,
    required: true,
    default: false,
  },
  dso_admin: {
    type: String,
    required: true,
    trim: true,
  },
  users: {
    type: [Schema.Types.ObjectId],
    required: true,
    default: [],
    ref: 'User', // Reference to User model
  },
  region: {
    type: String,
    required: false,
    trim: true,
    default: '',
  },
  org: {
    type: Schema.Types.ObjectId,
    required: true,
    ref: 'Organization', // Reference to Organization model
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

// Create and export the Location model
const Location = model<ILocation>('Location', locationSchema);

export default Location;
