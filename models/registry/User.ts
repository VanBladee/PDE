import { Schema, model, Document, Types } from 'mongoose';
import bcrypt from 'bcrypt';
import crypto from 'crypto';
import { createModel, DATABASE_NAMES } from '../../config/databases';

export type UserStatus = 'ACTIVE' | 'INACTIVE' | 'PENDING';

// Interface to represent a User document
export interface IUser extends Document {
  id: Types.ObjectId;
  type: string;
  firstName: string;
  lastName: string;
  email: string;
  password?: string; // Optional because it will be selected false
  tier: number;
  processCounter: number;
  submitCounter: number;
  settings: {
    status: UserStatus;
    darkMode?: boolean;
  };
  org: Types.ObjectId;
  matchPassword(password: string): Promise<boolean>;
  getPasswordResetToken(): string;
  passwordResetToken?: string;
  passwordResetExpires?: Date;
}

// Mongoose schema for User
const userSchema = new Schema<IUser>({
  type: {
    type: String,
    required: true,
    trim: true,
  },
  firstName: {
    type: String,
    required: true,
    trim: true,
  },
  lastName: {
    type: String,
    required: false,
    trim: true,
    default: '',
  },
  email: {
    type: String,
    required: true,
    unique: true,
    trim: true,
    lowercase: true,
  },
  password: {
    type: String,
    required: true,
    select: false, // Do not return password by default
  },
  tier: {
    type: Number,
    default: 0,
  },
  processCounter: {
    type: Number,
    default: 0,
  },
  submitCounter: {
    type: Number,
    default: 0,
  },
  settings: {
    status: {
      type: String,
      enum: ['ACTIVE', 'INACTIVE', 'PENDING'],
      default: 'PENDING',
    },
    darkMode: {
      type: Boolean,
      default: false,
    },
  },
  org: {
    type: Schema.Types.ObjectId,
    required: true,
    ref: 'Organization', // Add reference to Organization model
  },
  passwordResetToken: String,
  passwordResetExpires: Date,
}, {
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

// Hash password before saving
userSchema.pre<IUser>('save', async function (next) {
  // Only hash the password if it has been modified (or is new)
  if (!this.isModified('password')) {
    return next();
  }

  try {
    // Hash password with cost of 12
    const salt = await bcrypt.genSalt(12);
    this.password = await bcrypt.hash(this.password!, salt);
    next();
  } catch (error) {
    next(error as Error);
  }
});

// Method to compare password
userSchema.methods.matchPassword = async function (enteredPassword: string): Promise<boolean> {
  if (!this.password) {
    return false;
  }
  
  // Convert $2y$ (PHP format) to $2b$ (standard format)====== probably because we use python to hash in our web app.
  let hashToCompare = this.password;
  if (this.password.startsWith('$2y$')) {
    hashToCompare = this.password.replace('$2y$', '$2b$');
  }
  
  return await bcrypt.compare(enteredPassword, hashToCompare);
};

// Generate and hash password reset token
userSchema.methods.getPasswordResetToken = function() {
  // Generate token
  const resetToken = crypto.randomBytes(20).toString('hex');

  // Hash token and set to passwordResetToken field
  this.passwordResetToken = crypto
    .createHash('sha256')
    .update(resetToken)
    .digest('hex');

  // Set expire to 24 hours
  this.passwordResetExpires = Date.now() + 24 * 60 * 60 * 1000;

  return resetToken;
}

// Create and export the User model, registering its schema.
const User = createModel<IUser>(DATABASE_NAMES.REGISTRY, 'User', userSchema);

export default User; 