import { Schema, Document, Types } from 'mongoose';
import { createModel, DATABASE_NAMES } from '../../config/databases';

// Interface for AuditLog document
export interface IAuditLog extends Document {
  id: Types.ObjectId;
  userId: Types.ObjectId;
  action: string;
  resource: string;
  resourceId?: string;
  changes?: Record<string, any>;
  metadata?: Record<string, any>;
  ipAddress?: string;
  userAgent?: string;
  createdAt: Date;
}

// Schema definition
const auditLogSchema = new Schema<IAuditLog>({
  userId: {
    type: Schema.Types.ObjectId,
    required: true,
    index: true,
  },
  action: {
    type: String,
    required: true,
    index: true,
  },
  resource: {
    type: String,
    required: true,
    index: true,
  },
  resourceId: {
    type: String,
    index: true,
  },
  changes: {
    type: Schema.Types.Mixed,
  },
  metadata: {
    type: Schema.Types.Mixed,
  },
  ipAddress: String,
  userAgent: String,
}, {
  timestamps: { createdAt: true, updatedAt: false }, // Only need createdAt for audit logs
  toJSON: {
    transform: function(doc: any, ret: any) {
      ret.id = ret._id;
      delete ret._id;
      delete ret.__v;
      return ret;
    }
  }
});

// Add compound index for efficient querying
auditLogSchema.index({ userId: 1, createdAt: -1 });
auditLogSchema.index({ resource: 1, resourceId: 1, createdAt: -1 });

// Create and export the model using the activity database with lazy loading
const AuditLog = createModel<IAuditLog>(
  DATABASE_NAMES.ACTIVITY,
  'AuditLog',
  auditLogSchema
);

export default AuditLog; 