import { Schema, model, Document, Types } from 'mongoose';
import { createModel, DATABASE_NAMES } from '../../config/databases';

// Interface for procedure details
export interface IProcedure {
  procCode: string;
  tooth?: string;
  dateOfService: string;
  isVerified: boolean;
  feeBilled: number;
  allowedAmount: number;
  deductible: number;
  insAmountPaid: number;
  patientPays: number;
  remarks?: string;
  writeOff?: string;
  FeeBilled: number;
  geometry?: {
    BoundingBox: {
      Width: number;
      Height: number;
      Left: number;
      Top: number;
    };
    Polygon: Array<{ X: number; Y: number }>;
  };
  page: number;
  matchesUCR?: boolean;
  ucr_amount?: number;
}

// Interface for claim details
export interface IClaim {
  claimNum: string;
  isOrtho: boolean;
  isSupplemental: boolean;
  isDenied: boolean;
  isOON: boolean;
  procedures: IProcedure[];
  date_sent?: string;      // Date claim was sent to payer
  date_received?: string;  // Date payment was received from payer
  matched_claim?: {
    claim_num: number;
    pat_num: number;
    claim_fee: number;
    date_of_service: string;
    claim_note: string;
    is_secondary: boolean;
    has_secondary_plan: boolean;
    has_pending_secondary: boolean;
    match_score: number | null;
    match_source: string;
    claim_procs: Array<{
      CodeSent: string;
      FeeBilled: number;
      ClaimProcNum: number;
      WriteOff: number;
    }>;
    isOrtho: boolean;
    ortho_details: any;
    is_supplemental: boolean;
    carrier_name: string | null;
  };
}

// Interface for patient details
export interface IPatient {
  firstName: string;
  lastName: string;
  subscriberFirstName: string;
  subscriberLastName: string;
  claims: IClaim[];
}

// Interface for payment details
export interface IPayment {
  checkAmt: number;
  checkNumber: string;
  dateIssued: string;
  bankBranch: string;
  payType: string;
  carrierName: string;
}

// Interface for field edit details
export interface IFieldEdit {
  timestamp: string;
  field: string;
  oldValue: string;
  newValue: string;
  claimNum: string;
  procedureDetails?: {
    userEmail: string;
    logId: string;
  };
}

// Interface for field edit summary
export interface IFieldEditSummary {
  total_edits: number;
  edited_fields: Record<string, any>;
  edited_claims: string[];
  last_edit_timestamp: string | null;
  editors: string[];
}

// Interface for logs
export interface ILogs {
  eob_attached: boolean;
  payment_success: boolean;
  denied_claims: number;
  is_fee_mismatch: boolean;
  has_field_edits: boolean;
  field_edit_summary: IFieldEditSummary;
  field_edits: IFieldEdit[];
}

// Interface for data structure
export interface IData {
  success: boolean;
  patients: IPatient[];
  payment?: IPayment;
  log_id: string;
  scaling_used: string;
  documentType: string;
  used_initial_context: boolean;
  procedures_with_geometry: number;
  geometric_data_processed: boolean;
  matching_combined: boolean;
  patients_matched: number;
  matching_stats: {
    matched: number;
    failed: number;
    skipped: number;
  };
  phase: string;
}

// Interface for file details
export interface IFile {
  document_id: string;
  sftp_path: string;
  filename: string;
  original_file: string;
}

// Interface to represent a ProcessedClaim document
export interface IProcessedClaim extends Document {
  _id: Types.ObjectId;
  job_id: Types.ObjectId;
  locationId: Types.ObjectId;
  data: any; // Using any for complex nested data
  files: any[];
  logs: any;
  created_at: string;
  updated_at: string;
  error_details: any[];
  processing_errors: any[];
  has_errors: boolean;
  error_phase: string | null;
  last_error_timestamp: string | null;
  user_id: string;
  user_email: string;
  log_id: string;
  // TODO: Remove old fields after database schema finalized
  claimNum?: string;
  isOrtho?: boolean;
  isSupplemental?: boolean;
  isDenied?: boolean;
  procedures?: IProcedure[];
  isOON?: boolean;
  matched_claims?: Array<{
    claim_num: number;
    pat_num: number;
    date_of_service: string;
    claim_fee: number;
    claim_note: string;
    is_secondary: boolean;
    has_secondary_plan: boolean;
    has_pending_secondary: boolean;
    match_score: number;
    match_source: string;
    claim_procs: Array<{
      CodeSent: string;
      FeeBilled: number;
      ClaimProcNum: number;
      WriteOff: number;
    }>;
    isOrtho: boolean;
    ortho_details: any;
    is_supplemental: boolean;
    carrier_name: string;
  }>;
  ortho_details?: any;
  carrier_name?: string;
  date_received?: string;
  date_sent?: string;
  is_split_claim?: boolean;
  needs_od_split?: boolean;
  excluded_from_batch?: boolean;
}

// Mongoose schema for ProcessedClaim
const processedClaimSchema = new Schema({
  job_id: {
    type: Types.ObjectId,
    required: true,
    index: true,
  },
  locationId: {
    type: Schema.Types.ObjectId,
    required: true,
    ref: 'Location', // Reference to Location model in registry database
    index: true,
  },
  data: {
    type: Schema.Types.Mixed,
    required: true,
  },
  files: {
    type: [Schema.Types.Mixed],
    required: false,
    default: [],
  },
  logs: {
    type: Schema.Types.Mixed,
    required: false,
    default: {},
  },
  created_at: {
    type: String,
    required: true,
  },
  updated_at: {
    type: String,
    required: true,
  },
  error_details: {
    type: [Schema.Types.Mixed],
    required: false,
    default: [],
  },
  processing_errors: {
    type: [Schema.Types.Mixed],
    required: false,
    default: [],
  },
  has_errors: {
    type: Boolean,
    required: false,
    default: false,
  },
  error_phase: {
    type: String,
    required: false,
    default: null,
  },
  last_error_timestamp: {
    type: String,
    required: false,
    default: null,
  },
  user_id: {
    type: String,
    required: true,
    index: true,
  },
  user_email: {
    type: String,
    required: true,
    index: true,
  },
  log_id: {
    type: String,
    required: true,
  },
  // TODO: Remove old fields after database schema finalized
  claimNum: {
    type: String,
    required: false,
  },
  isOrtho: {
    type: Boolean,
    required: false,
  },
  isSupplemental: {
    type: Boolean,
    required: false,
  },
  isDenied: {
    type: Boolean,
    required: false,
  },
  procedures: {
    type: [Schema.Types.Mixed],
    required: false,
    default: [],
  },
  isOON: {
    type: Boolean,
    required: false,
  },
  matched_claims: {
    type: [Schema.Types.Mixed],
    required: false,
    default: [],
  },
  ortho_details: {
    type: Schema.Types.Mixed,
    required: false,
    default: {},
  },
  carrier_name: {
    type: String,
    required: false,
  },
  date_received: {
    type: String,
    required: false,
  },
  date_sent: {
    type: String,
    required: false,
  },
  is_split_claim: {
    type: Boolean,
    required: false,
    default: false,
  },
  needs_od_split: {
    type: Boolean,
    required: false,
    default: false,
  },
  excluded_from_batch: {
    type: Boolean,
    required: false,
    default: false,
  },
}, {
  timestamps: true,
  collection: 'processed_claims', // Explicitly set collection name
});

// Create and export the ProcessedClaim model using the activity database
const ProcessedClaim = createModel<IProcessedClaim>(DATABASE_NAMES.ACTIVITY, 'ProcessedClaim', processedClaimSchema);

export default ProcessedClaim; 