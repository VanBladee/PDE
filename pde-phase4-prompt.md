# Claude Code Prompt - Phase 4: Build MongoDB Database Layer

Create the MongoDB integration layer that stores transformed data in collections optimized for the Admin Cockpit dashboard.

## Context from Previous Phases
- Extraction complete: credentialing, claims, fees
- Transformation complete: metrics, matrix, analysis
- Need: Store in MongoDB for dashboard consumption

## Step 1: Create MongoDB Models

Create `src/models/CarrierMetrics.ts`:
```typescript
import mongoose, { Schema, Document } from 'mongoose';

export interface ICarrierMetrics extends Document {
  carrier_code: string;
  carrier_name: string;
  location_id: string;
  period: string;
  
  // Core metrics for decision making
  patient_count: number;
  revenue_per_patient: number;
  avg_write_off_percent: number;
  
  // Supporting data
  total_claims: number;
  total_billed: number;
  total_paid: number;
  total_write_off: number;
  
  // Drill-down data
  by_procedure: Record<string, {
    count: number;
    total_write_off: number;
    avg_write_off_percent: number;
  }>;
  
  calculated_at: Date;
}

const CarrierMetricsSchema = new Schema({
  carrier_code: { type: String, required: true, index: true },
  carrier_name: { type: String, required: true },
  location_id: { type: String, required: true, index: true },
  period: { type: String, required: true, index: true },
  
  patient_count: { type: Number, required: true },
  revenue_per_patient: { type: Number, required: true },
  avg_write_off_percent: { type: Number, required: true },
  
  total_claims: { type: Number, required: true },
  total_billed: { type: Number, required: true },
  total_paid: { type: Number, required: true },
  total_write_off: { type: Number, required: true },
  
  by_procedure: { type: Schema.Types.Mixed },
  
  calculated_at: { type: Date, default: Date.now }
});

// Compound index for efficient queries
CarrierMetricsSchema.index({ carrier_code: 1, location_id: 1, period: 1 }, { unique: true });

export const CarrierMetrics = mongoose.model<ICarrierMetrics>('CarrierMetrics', CarrierMetricsSchema);
```

Create `src/models/CredentialingMatrix.ts`:
```typescript
import mongoose, { Schema, Document } from 'mongoose';

export interface ICredentialingMatrix extends Document {
  provider_id: string;
  provider_name: string;
  carrier_code: string;
  location_id: string;
  status: 'ACTIVE' | 'PENDING' | 'INACTIVE' | 'EXPIRED';
  effective_date: Date;
  expiration_date?: Date;
  smartsheet_row_id?: number;
  last_updated: Date;
}

const CredentialingMatrixSchema = new Schema({
  provider_id: { type: String, required: true, index: true },
  provider_name: { type: String, required: true },
  carrier_code: { type: String, required: true, index: true },
  location_id: { type: String, required: true, index: true },
  status: { 
    type: String, 
    required: true,
    enum: ['ACTIVE', 'PENDING', 'INACTIVE', 'EXPIRED']
  },
  effective_date: { type: Date, required: true },
  expiration_date: { type: Date },
  smartsheet_row_id: { type: Number },
  last_updated: { type: Date, default: Date.now }
});

// Indexes for dashboard queries
CredentialingMatrixSchema.index({ provider_id: 1, carrier_code: 1, location_id: 1 }, { unique: true });
CredentialingMatrixSchema.index({ status: 1, expiration_date: 1 }); // For finding expiring credentials

export const CredentialingMatrix = mongoose.model<ICredentialingMatrix>('CredentialingMatrix', CredentialingMatrixSchema);
```

Create `src/models/UnifiedClaim.ts`:
```typescript
import mongoose, { Schema, Document } from 'mongoose';

export interface IUnifiedClaim extends Document {
  claim_id: string;
  location_id: string;
  provider_id: string;
  patient_id: string;
  service_date: Date;
  
  // Payment info from Jobs
  carrier_code: string;
  carrier_name: string;
  check_number?: string;
  check_amount?: number;
  check_date?: Date;
  
  // Procedure details
  procedures: Array<{
    code: string;
    fee_billed: number;
    fee_allowed: number;
    amount_paid: number;
    patient_portion: number;
    write_off: number;
    write_off_percent: number;
  }>;
  
  // Totals
  totals: {
    billed: number;
    allowed: number;
    paid: number;
    write_off: number;
  };
  
  created_at: Date;
}

const UnifiedClaimSchema = new Schema({
  claim_id: { type: String, required: true, unique: true },
  location_id: { type: String, required: true, index: true },
  provider_id: { type: String, required: true, index: true },
  patient_id: { type: String, required: true, index: true },
  service_date: { type: Date, required: true, index: true },
  
  carrier_code: { type: String, index: true },
  carrier_name: { type: String },
  check_number: { type: String, index: true },
  check_amount: { type: Number },
  check_date: { type: Date },
  
  procedures: [{
    code: { type: String, required: true },
    fee_billed: { type: Number, required: true },
    fee_allowed: { type: Number, required: true },
    amount_paid: { type: Number, required: true },
    patient_portion: { type: Number, default: 0 },
    write_off: { type: Number, required: true },
    write_off_percent: { type: Number, required: true }
  }],
  
  totals: {
    billed: { type: Number, required: true },
    allowed: { type: Number, required: true },
    paid: { type: Number, required: true },
    write_off: { type: Number, required: true }
  },
  
  created_at: { type: Date, default: Date.now }
});

// Indexes for analytics queries
UnifiedClaimSchema.index({ carrier_code: 1, service_date: -1 });
UnifiedClaimSchema.index({ 'procedures.code': 1 });

export const UnifiedClaim = mongoose.model<IUnifiedClaim>('UnifiedClaim', UnifiedClaimSchema);
```

Create `src/models/FeeSchedule.ts`:
```typescript
import mongoose, { Schema, Document } from 'mongoose';

export interface IFeeSchedule extends Document {
  carrier_code: string;
  schedule_name: string;
  location_ids: string[];
  effective_date: Date;
  expiration_date?: Date;
  fees: Record<string, number>; // procedure_code -> fee amount
  source: 'CONTRACT' | 'VERIFIED_CLAIMS' | 'MANUAL_ENTRY';
  last_updated: Date;
}

const FeeScheduleSchema = new Schema({
  carrier_code: { type: String, required: true, index: true },
  schedule_name: { type: String, required: true },
  location_ids: [{ type: String }],
  effective_date: { type: Date, required: true },
  expiration_date: { type: Date },
  fees: { type: Schema.Types.Mixed, required: true },
  source: { 
    type: String, 
    required: true,
    enum: ['CONTRACT', 'VERIFIED_CLAIMS', 'MANUAL_ENTRY']
  },
  last_updated: { type: Date, default: Date.now }
});

// Index for finding active schedules
FeeScheduleSchema.index({ carrier_code: 1, effective_date: -1 });

export const FeeSchedule = mongoose.model<IFeeSchedule>('FeeSchedule', FeeScheduleSchema);
```

## Step 2: Create Database Connection Manager

Create `src/database/DatabaseManager.ts`:
```typescript
import mongoose from 'mongoose';
import dotenv from 'dotenv';

dotenv.config();

export class DatabaseManager {
  private static instance: DatabaseManager;
  private mainConnection: mongoose.Connection | null = null;
  private activityConnection: mongoose.Connection | null = null;
  
  private constructor() {}
  
  static getInstance(): DatabaseManager {
    if (!DatabaseManager.instance) {
      DatabaseManager.instance = new DatabaseManager();
    }
    return DatabaseManager.instance;
  }
  
  async connect(): Promise<void> {
    try {
      // Main platinum_unified database
      const mainUri = `${process.env.MONGO_URI}/${process.env.DB_NAME}`;
      this.mainConnection = await mongoose.createConnection(mainUri).asPromise();
      console.log('✅ Connected to platinum_unified database');
      
      // Activity database (for source data)
      const activityUri = `${process.env.MONGO_URI}/${process.env.ACTIVITY_DB}`;
      this.activityConnection = await mongoose.createConnection(activityUri).asPromise();
      console.log('✅ Connected to activity database');
      
    } catch (error) {
      console.error('❌ Database connection failed:', error);
      throw error;
    }
  }
  
  getMainConnection(): mongoose.Connection {
    if (!this.mainConnection) {
      throw new Error('Main database not connected');
    }
    return this.mainConnection;
  }
  
  getActivityConnection(): mongoose.Connection {
    if (!this.activityConnection) {
      throw new Error('Activity database not connected');
    }
    return this.activityConnection;
  }
  
  async disconnect(): Promise<void> {
    if (this.mainConnection) await this.mainConnection.close();
    if (this.activityConnection) await this.activityConnection.close();
    console.log('📴 Database connections closed');
  }
}
```

## Step 3: Create MongoDB Loader

Create `src/loaders/MongoLoader.ts`:
```typescript
import { DatabaseManager } from '../database/DatabaseManager';
import { CarrierMetrics } from '../models/CarrierMetrics';
import { CredentialingMatrix } from '../models/CredentialingMatrix';
import { UnifiedClaim } from '../models/UnifiedClaim';
import { FeeSchedule } from '../models/FeeSchedule';

export class MongoLoader {
  private db: DatabaseManager;
  
  constructor() {
    this.db = DatabaseManager.getInstance();
  }
  
  async loadCarrierMetrics(metrics: any[], clearExisting: boolean = false): Promise<void> {
    console.log('💾 Loading carrier metrics to MongoDB...');
    
    if (clearExisting) {
      await CarrierMetrics.deleteMany({});
      console.log('  Cleared existing metrics');
    }
    
    // Bulk upsert for efficiency
    const bulkOps = metrics.map(metric => ({
      updateOne: {
        filter: {
          carrier_code: metric.carrier_code,
          location_id: metric.location_id,
          period: metric.period
        },
        update: { $set: metric },
        upsert: true
      }
    }));
    
    const result = await CarrierMetrics.bulkWrite(bulkOps);
    console.log(`  ✅ Loaded ${result.upsertedCount} new, updated ${result.modifiedCount} existing metrics`);
  }
  
  async loadCredentialingMatrix(records: any[], clearExisting: boolean = false): Promise<void> {
    console.log('💾 Loading credentialing matrix to MongoDB...');
    
    if (clearExisting) {
      await CredentialingMatrix.deleteMany({});
      console.log('  Cleared existing credentialing');
    }
    
    const bulkOps = records.map(record => ({
      updateOne: {
        filter: {
          provider_id: record.provider_id,
          carrier_code: record.carrier_code,
          location_id: record.location_id
        },
        update: { $set: record },
        upsert: true
      }
    }));
    
    const result = await CredentialingMatrix.bulkWrite(bulkOps);
    console.log(`  ✅ Loaded ${result.upsertedCount} new, updated ${result.modifiedCount} existing records`);
  }
  
  async loadUnifiedClaims(claims: any[], batchSize: number = 1000): Promise<void> {
    console.log('💾 Loading unified claims to MongoDB...');
    
    let totalInserted = 0;
    
    // Process in batches for large datasets
    for (let i = 0; i < claims.length; i += batchSize) {
      const batch = claims.slice(i, i + batchSize);
      
      const bulkOps = batch.map(claim => ({
        updateOne: {
          filter: { claim_id: claim.claim_id },
          update: { $set: claim },
          upsert: true
        }
      }));
      
      const result = await UnifiedClaim.bulkWrite(bulkOps);
      totalInserted += result.upsertedCount;
      
      if ((i + batchSize) % 5000 === 0) {
        console.log(`  Progress: ${i + batchSize} / ${claims.length} claims`);
      }
    }
    
    console.log(`  ✅ Loaded ${totalInserted} claims`);
  }
  
  async loadFeeSchedules(schedules: any[]): Promise<void> {
    console.log('💾 Loading fee schedules to MongoDB...');
    
    const bulkOps = schedules.map(schedule => ({
      updateOne: {
        filter: {
          carrier_code: schedule.carrier_code,
          schedule_name: schedule.schedule_name
        },
        update: { $set: schedule },
        upsert: true
      }
    }));
    
    const result = await FeeSchedule.bulkWrite(bulkOps);
    console.log(`  ✅ Loaded ${result.upsertedCount} new, updated ${result.modifiedCount} existing schedules`);
  }
  
  async createIndexes(): Promise<void> {
    console.log('📑 Creating database indexes...');
    
    // Ensure all indexes are created
    await CarrierMetrics.createIndexes();
    await CredentialingMatrix.createIndexes();
    await UnifiedClaim.createIndexes();
    await FeeSchedule.createIndexes();
    
    console.log('  ✅ All indexes created');
  }
  
  async getStatistics(): Promise<any> {
    const stats = {
      carrier_metrics: await CarrierMetrics.countDocuments(),
      credentialing_matrix: await CredentialingMatrix.countDocuments(),
      unified_claims: await UnifiedClaim.countDocuments(),
      fee_schedules: await FeeSchedule.countDocuments()
    };
    
    return stats;
  }
}
```

## Step 4: Create Complete Pipeline Orchestrator

Create `src/pipeline/CompletePipeline.ts`:
```typescript
import { MasterExtractor } from '../extractors/MasterExtractor';
import { MasterTransformer } from '../transformers/MasterTransformer';
import { MongoLoader } from '../loaders/MongoLoader';
import { DatabaseManager } from '../database/DatabaseManager';

export class CompletePipeline {
  private extractor: MasterExtractor;
  private transformer: MasterTransformer;
  private loader: MongoLoader;
  private db: DatabaseManager;
  
  constructor() {
    this.extractor = new MasterExtractor();
    this.transformer = new MasterTransformer();
    this.loader = new MongoLoader();
    this.db = DatabaseManager.getInstance();
  }
  
  async run(options: {
    clearExisting?: boolean;
    extractOnly?: boolean;
    transformOnly?: boolean;
  } = {}): Promise<void> {
    console.log('🚀 PLATINUM DATA ENGINE - STARTING PIPELINE\n');
    console.log('═'.repeat(50));
    
    const startTime = Date.now();
    
    try {
      // Connect to databases
      await this.db.connect();
      
      // Step 1: Extract
      console.log('\n📥 PHASE 1: EXTRACTION');
      console.log('─'.repeat(50));
      const extractedData = await this.extractor.extractAll();
      
      if (options.extractOnly) {
        console.log('✅ Extraction complete (extract-only mode)');
        return;
      }
      
      // Step 2: Transform
      console.log('\n⚙️  PHASE 2: TRANSFORMATION');
      console.log('─'.repeat(50));
      const transformedData = await this.transformer.transformAll(extractedData);
      
      if (options.transformOnly) {
        console.log('✅ Transformation complete (transform-only mode)');
        return;
      }
      
      // Step 3: Load
      console.log('\n💾 PHASE 3: LOADING TO MONGODB');
      console.log('─'.repeat(50));
      
      await this.loader.loadCarrierMetrics(transformedData.carrierMetrics, options.clearExisting);
      await this.loader.loadCredentialingMatrix(extractedData.credentialing, options.clearExisting);
      await this.loader.loadUnifiedClaims(extractedData.claims, 1000);
      await this.loader.loadFeeSchedules(extractedData.feeSchedules);
      
      // Create indexes
      await this.loader.createIndexes();
      
      // Final statistics
      console.log('\n📊 PIPELINE COMPLETE - FINAL STATISTICS');
      console.log('═'.repeat(50));
      
      const stats = await this.loader.getStatistics();
      console.log('Database Collections:');
      console.log(`  • Carrier Metrics: ${stats.carrier_metrics.toLocaleString()}`);
      console.log(`  • Credentialing Matrix: ${stats.credentialing_matrix.toLocaleString()}`);
      console.log(`  • Unified Claims: ${stats.unified_claims.toLocaleString()}`);
      console.log(`  • Fee Schedules: ${stats.fee_schedules.toLocaleString()}`);
      
      const duration = (Date.now() - startTime) / 1000;
      console.log(`\n⏱️  Total Duration: ${duration.toFixed(2)} seconds`);
      console.log('✅ Pipeline completed successfully!\n');
      
    } catch (error) {
      console.error('\n❌ PIPELINE FAILED:', error);
      throw error;
    } finally {
      await this.db.disconnect();
    }
  }
}
```

## Step 5: Create Main Entry Point

Create `src/index.ts`:
```typescript
import { CompletePipeline } from './pipeline/CompletePipeline';
import dotenv from 'dotenv';

dotenv.config();

async function main() {
  const pipeline = new CompletePipeline();
  
  // Parse command line arguments
  const args = process.argv.slice(2);
  const options = {
    clearExisting: args.includes('--clear'),
    extractOnly: args.includes('--extract-only'),
    transformOnly: args.includes('--transform-only')
  };
  
  try {
    await pipeline.run(options);
    process.exit(0);
  } catch (error) {
    console.error('Fatal error:', error);
    process.exit(1);
  }
}

// Run if called directly
if (require.main === module) {
  main();
}

export { CompletePipeline };
```

## Update package.json Scripts
```json
{
  "scripts": {
    "dev": "nodemon src/index.ts",
    "start": "ts-node src/index.ts",
    "pipeline": "ts-node src/index.ts",
    "pipeline:clear": "ts-node src/index.ts --clear",
    "pipeline:extract": "ts-node src/index.ts --extract-only",
    "build": "tsc",
    "test": "jest"
  }
}
```

## Validation
Run the complete pipeline:
```bash
# Full pipeline with fresh data
npm run pipeline:clear

# Check MongoDB
mongo platinum_unified
> db.carrierMetrics.findOne()
> db.credentialingMatrix.count()
> db.unifiedClaims.count()
```

Expected results:
- ✅ All collections populated
- ✅ Carrier metrics showing patient counts
- ✅ Credentialing matrix with 10,000+ records
- ✅ Claims with write-off calculations
