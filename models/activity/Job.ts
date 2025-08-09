import { Schema, model, Document, Types } from 'mongoose';
import { createModel, DATABASE_NAMES } from '../../config/databases';

// Interface for patient claim reference
export interface IPatientClaim {
  firstName: string;
  lastName: string;
  subscriberFirstName: string;
  subscriberLastName: string;
  claims: Types.ObjectId[];
}

// Interface for payment details
export interface IJobPayment {
  checkAmt: number;
  checkNumber: string;
  dateIssued: string;
  bankBranch: string;
  payType: string;
  carrierName: string;
}

// Interface for timeline
export interface ITimeline {
  started_at: string;
  updated_at: string;
  processed_at?: string;
}

// Interface for job errors (renamed to avoid conflict with Document.errors)
export interface IJobErrors {
  processing_errors: any[];
  error_code: string | null;
  error_message: string | null;
  error_phase: string | null;
  has_critical_errors: boolean;
}

// Interface for file details
export interface IJobFile {
  document_id: string;
  sftp_path: string;
  filename: string;
  original_file: string;
}

// Interface for field edit summary
export interface IFieldEditSummary {
  total_edits: number;
  edited_fields: Record<string, any>;
  edited_claims: string[];
  last_edit_timestamp: string | null;
  editors: string[];
}

// Interface for events
export interface IEvents {
  claim_doc_ids: Types.ObjectId[];
  eob_attached: boolean;
  payment_success: boolean;
  has_field_edits: boolean;
  field_edit_summary: IFieldEditSummary;
  field_edits: any[];
  denied_claims: number;
}

// Interface to represent a Job document
export interface IJob extends Document {
  _id: Types.ObjectId;
  locationId: Types.ObjectId;
  documentType: string;
  status: string;
  phase: string;
  timeline: ITimeline;
  job_errors: IJobErrors; // Renamed to avoid conflict
  files: IJobFile[];
  user_id: Types.ObjectId;
  user_email: string;
  chain_id: string;
  patients: IPatientClaim[];
  payment?: IJobPayment;
  events: IEvents;
  log_id: string;
}

// Mongoose schema for Job
const jobSchema = new Schema({
  locationId: {
    type: Schema.Types.ObjectId,
    required: true,
    ref: 'Location',
    index: true,
  },
  documentType: {
    type: String,
    required: true,
  },
  status: {
    type: String,
    required: true,
    index: true,
  },
  phase: {
    type: String,
    required: true,
  },
  timeline: {
    started_at: { type: String, required: true },
    updated_at: { type: String, required: true },
    processed_at: { type: String },
  },
  job_errors: {
    processing_errors: { type: [Schema.Types.Mixed], default: [] },
    error_code: { type: String, default: null },
    error_message: { type: String, default: null },
    error_phase: { type: String, default: null },
    has_critical_errors: { type: Boolean, default: false },
  },
  files: [{
    document_id: { type: String, required: true },
    sftp_path: { type: String, required: true },
    filename: { type: String, required: true },
    original_file: { type: String, required: true },
  }],
  user_id: {
    type: Schema.Types.ObjectId,
    required: true,
    index: true,
  },
  user_email: {
    type: String,
    required: true,
    index: true,
  },
  chain_id: {
    type: String,
    required: true,
  },
  patients: [{
    firstName: { type: String, required: true },
    lastName: { type: String, required: true },
    subscriberFirstName: { type: String, required: true },
    subscriberLastName: { type: String, required: true },
    claims: [{ type: Schema.Types.ObjectId, ref: 'ProcessedClaim' }],
  }],
  payment: {
    checkAmt: { type: Number },
    checkNumber: { type: String },
    dateIssued: { type: String },
    bankBranch: { type: String },
    payType: { type: String },
    carrierName: { type: String },
  },
  events: {
    claim_doc_ids: [{ type: Schema.Types.ObjectId, ref: 'ProcessedClaim' }],
    eob_attached: { type: Boolean, default: false },
    payment_success: { type: Boolean, default: false },
    has_field_edits: { type: Boolean, default: false },
    field_edit_summary: {
      total_edits: { type: Number, default: 0 },
      edited_fields: { type: Schema.Types.Mixed, default: {} },
      edited_claims: { type: [String], default: [] },
      last_edit_timestamp: { type: String, default: null },
      editors: { type: [String], default: [] },
    },
    field_edits: { type: [Schema.Types.Mixed], default: [] },
    denied_claims: { type: Number, default: 0 },
  },
  log_id: {
    type: String,
    required: true,
  },
}, {
  timestamps: true,
  collection: 'jobs', // Explicitly set collection name
});

// Create and export the Job model using the activity database
const Job = createModel<IJob>(DATABASE_NAMES.ACTIVITY, 'Job', jobSchema);

export default Job;