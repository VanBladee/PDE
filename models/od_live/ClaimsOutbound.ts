import { Schema, Document, Types } from 'mongoose';
import { createModel, DATABASE_NAMES } from '../../config/databases';

// Interface for procedure details in claims_outbound
export interface IClaimsOutboundProcedure {
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

// Interface for claim details in claims_outbound
export interface IClaimsOutboundClaim {
  claimNum: string;
  isOrtho: boolean;
  isSupplemental: boolean;
  isDenied: boolean;
  isOON: boolean;
  procedures: IClaimsOutboundProcedure[];
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

// Interface for patient details in claims_outbound
export interface IClaimsOutboundPatient {
  firstName: string;
  lastName: string;
  subscriberFirstName: string;
  subscriberLastName: string;
  claims: IClaimsOutboundClaim[];
}

// Interface for claims_outbound document - actual structure
export interface IClaimsOutbound extends Document {
  _id: Types.ObjectId;
  locationId: Types.ObjectId;
  practice_name?: string; // Added based on actual schema
  claims_data?: IClaimsOutboundClaim[]; // Direct array of claims (actual structure)
  count?: number; // Added based on actual schema
  lastUpdated?: string; // Added based on actual schema
  patients?: IClaimsOutboundPatient[]; // Alternative field name
  claims?: IClaimsOutboundClaim[]; // Alternative field name
  data?: any; // Generic data field
  updated_at?: string;
  total_claims?: number;
  lastupdated?: string;
  created_at: Date;
  updatedAt: Date;
}

// Mongoose schema for ClaimsOutbound - actual structure
const claimsOutboundSchema = new Schema({
  locationID: {
    type: Schema.Types.ObjectId,
    required: true,
    ref: 'Location',
    index: true,
  },
  practice_name: {
    type: String,
    required: false,
  },
  claims_data: {
    type: [Schema.Types.Mixed], // Direct array of claims (actual structure)
    required: false,
    default: [],
  },
  count: {
    type: Number,
    required: false,
  },
  lastUpdated: {
    type: String,
    required: false,
  },
  patients: {
    type: [Schema.Types.Mixed], // Alternative field for patients data
    required: false,
    default: [],
  },
  claims: {
    type: [Schema.Types.Mixed], // Alternative field for claims data
    required: false,
    default: [],
  },
  data: {
    type: Schema.Types.Mixed, // Generic data field
    required: false,
  },
  updated_at: {
    type: String,
    required: false,
  },
  total_claims: {
    type: Number,
    required: false,
  },
  lastupdated: {
    type: String,
    required: false,
  },
}, {
  timestamps: true, // Automatically add createdAt and updatedAt fields
  collection: 'claims_outbound', // Explicitly set collection name
  strict: false, // Allow fields not defined in schema
  toJSON: {
    transform: function(doc: any, ret: any) {
      ret.id = ret._id;
      delete ret._id;
      delete ret.__v;
      return ret;
    }
  }
});

// Create and export the ClaimsOutbound model using the od_live database
const ClaimsOutbound = createModel<IClaimsOutbound>(
  DATABASE_NAMES.OD_LIVE,
  'ClaimsOutbound',
  claimsOutboundSchema
);

export default ClaimsOutbound; 