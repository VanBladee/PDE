import { Schema, Document, Types } from 'mongoose';
import { createModel, DATABASE_NAMES } from '../../config/databases';

// Interface for Organization document
export interface IOrganization extends Document {
  id: Types.ObjectId;
  name: string;
  type: string;
  status: 'active' | 'inactive' | 'suspended';
  settings: Record<string, any>;
  createdAt: Date;
  updatedAt: Date;
}

// Schema definition
const organizationSchema = new Schema<IOrganization>({
  name: {
    type: String,
    required: true,
    trim: true,
  },
  type: {
    type: String,
    required: true,
  },
  status: {
    type: String,
    enum: ['active', 'inactive', 'suspended'],
    default: 'active',
  },
  settings: {
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

// Create and export the model using the registry database with lazy loading
const Organization = createModel<IOrganization>(
  DATABASE_NAMES.REGISTRY,
  'Organization',
  organizationSchema
);

export default Organization; 