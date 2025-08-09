import { Request, Response } from 'express';
import { Types } from 'mongoose';
import { createModel, DATABASE_NAMES } from '../config/databases';
import { Schema, Document } from 'mongoose';

// Interface for AuditLog document
export interface IAuditLog extends Document {
  event: string;
  timestamp: Date;
  meta: {
    url: string;
    user_agent: string;
    log_id?: string;
  };
  browser_info: any;
  session_id: string;
  user_email: string;
  log_id?: string;
  data: any;
  createdAt: Date;
  updatedAt: Date;
}

// Mongoose schema for AuditLogs
const auditLogSchema = new Schema<IAuditLog>({
  event: {
    type: String,
    required: true,
  },
  timestamp: {
    type: Date,
    required: true,
    default: Date.now,
  },
  meta: {
    url: {
      type: String,
      required: true,
    },
    user_agent: {
      type: String,
      required: true,
    },
    log_id: {
      type: String,
    },
  },
  browser_info: {
    type: Schema.Types.Mixed,
  },
  session_id: {
    type: String,
    required: true,
  },
  user_email: {
    type: String,
    required: true,
  },
  log_id: {
    type: String,
  },
  data: {
    type: Schema.Types.Mixed,
  },
}, {
  timestamps: true,
  collection: 'audit_logs', // Explicitly specify the collection name
  toJSON: {
    transform: function(doc: any, ret: any) {
      ret.id = ret._id;
      delete ret._id;
      delete ret.__v;
      return ret;
    }
  }
});

// Create index on session_id for efficient querying
auditLogSchema.index({ session_id: 1 });
auditLogSchema.index({ user_email: 1 });
auditLogSchema.index({ timestamp: -1 });
auditLogSchema.index({ event: 1 });

// Create and export the AuditLog model using the activity database
const AuditLog = createModel<IAuditLog>(
  DATABASE_NAMES.ACTIVITY,
  'AuditLog',
  auditLogSchema
);

/**
 * Get all audit logs with pagination and filtering
 */
export const getAuditLogs = async (req: Request, res: Response) => {
  try {
    const { org } = req.user!; // Organization ID from auth middleware

    // Parse pagination parameters
    const page = parseInt(req.query.page as string) || 1;
    const limit = parseInt(req.query.limit as string) || 10;
    const skip = (page - 1) * limit;

    // Parse filters
    const { date_from, date_to, event, user_email, session_id, log_id } = req.query;

    // Build query filter
    const filter: any = {};

    // Add date filters if provided
    if (date_from || date_to) {
      filter.timestamp = {};
      if (date_from) filter.timestamp.$gte = new Date(date_from as string);
      if (date_to) filter.timestamp.$lte = new Date(date_to as string);
    }

    // Add event filter if provided
    if (event) {
      filter.event = { $regex: event, $options: 'i' };
    }

    // Add user_email filter if provided
    if (user_email) {
      filter.user_email = { $regex: user_email, $options: 'i' };
    }

    // Add session_id filter if provided
    if (session_id) {
      filter.session_id = session_id as string;
    }

    // Add log_id filter if provided
    if (log_id) {
      filter['meta.log_id'] = log_id as string;
    }

    // Execute queries in parallel for efficiency
    const [auditLogs, totalCount] = await Promise.all([
      AuditLog.find(filter)
        .sort({ timestamp: -1 }) // Sort by newest first
        .skip(skip)
        .limit(limit)
        .lean(),
      AuditLog.countDocuments(filter),
    ]);

    // Calculate pagination metadata
    const totalPages = Math.ceil(totalCount / limit);
    const hasNextPage = page < totalPages;
    const hasPrevPage = page > 1;

    const result = {
      auditLogs,
      pagination: {
        currentPage: page,
        totalPages,
        totalCount,
        limit,
        hasNextPage,
        hasPrevPage,
      },
    };

    res.status(200).json({
      success: true,
      message: 'Audit logs fetched successfully',
      data: result,
      filters: {
        date_from,
        date_to,
        event,
        user_email,
        session_id,
        log_id,
      },
    });
  } catch (error) {
    console.error('Error fetching audit logs:', error);
    res.status(500).json({
      success: false,
      message: 'Failed to fetch audit logs',
      error: error instanceof Error ? error.message : 'Unknown error',
    });
  }
};


export default AuditLog;