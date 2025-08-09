# Claude Code Prompt - Phase 2: Build Unified Extraction Layer

Now that the project structure is set up, create TypeScript wrappers for the Python extractors and build a unified extraction interface.

## Context from Phase 1
- Python extractors copied to src/extractors/
- PythonBridge utility created
- MongoDB connections configured

## Step 1: Create Smartsheet Extractor Wrapper

Create `src/extractors/SmartsheetExtractor.ts`:
```typescript
import { PythonBridge } from '../utils/python-bridge';
import path from 'path';

interface CredentialingRecord {
  provider_id: string;
  carrier_code: string;
  location_id: string;
  status: 'ACTIVE' | 'PENDING' | 'INACTIVE';
  effective_date: Date;
  smartsheet_row_id: number;
}

export class SmartsheetExtractor {
  private scriptPath: string;

  constructor() {
    this.scriptPath = path.join(__dirname, 'smartsheet/smartsheet_extractor.py');
  }

  async extractCredentialing(): Promise<CredentialingRecord[]> {
    console.log('📋 Extracting credentialing from Smartsheet...');
    
    const result = await PythonBridge.execute(this.scriptPath, [
      '--mode', 'credentialing',
      '--output', 'json'
    ]);

    console.log(`✅ Extracted ${result.length} credentialing records`);
    return result;
  }

  async extractProviders(): Promise<any[]> {
    console.log('👥 Extracting providers from Smartsheet...');
    
    const result = await PythonBridge.execute(this.scriptPath, [
      '--mode', 'providers',
      '--output', 'json'
    ]);

    console.log(`✅ Extracted ${result.length} providers`);
    return result;
  }
}
```

## Step 2: Create OpenDental Extractor Wrapper

Create `src/extractors/OpenDentalExtractor.ts`:
```typescript
import { PythonBridge } from '../utils/python-bridge';
import mongoose from 'mongoose';
import path from 'path';

interface Payment {
  checkNumber: string;
  carrierName: string;
  checkAmount: number;
  dateIssued: Date;
}

interface Procedure {
  code: string;
  fee_billed: number;
  fee_allowed: number;
  amount_paid: number;
  write_off: number;
  write_off_percent: number;
}

interface UnifiedClaim {
  claim_id: string;
  location_id: string;
  provider_id: string;
  patient_id: string;
  service_date: Date;
  payment?: Payment;
  procedures: Procedure[];
  totals: {
    billed: number;
    allowed: number;
    paid: number;
    write_off: number;
  };
}

export class OpenDentalExtractor {
  private claimsScript: string;
  private activityDb: any;

  constructor() {
    this.claimsScript = path.join(__dirname, 'opendental/claims_extractor.py');
  }

  async connectToActivityDB() {
    const activityConn = await mongoose.createConnection(
      `${process.env.MONGO_URI}/${process.env.ACTIVITY_DB}`
    );
    this.activityDb = activityConn;
  }

  async extractClaimsWithPayments(): Promise<UnifiedClaim[]> {
    console.log('🦷 Extracting claims from OpenDental...');
    
    // Get Jobs collection for payment data
    const Jobs = this.activityDb.collection('Jobs');
    const ProcessedClaims = this.activityDb.collection('ProcessedClaims');

    // Extract payments from Jobs
    const jobs = await Jobs.find({
      'payment.checkNumber': { $exists: true }
    }).toArray();

    // Create payment lookup
    const paymentLookup = new Map();
    for (const job of jobs) {
      if (job.events?.claim_doc_ids) {
        for (const claimId of job.events.claim_doc_ids) {
          paymentLookup.set(claimId.toString(), job.payment);
        }
      }
    }

    // Process claims with procedures
    const claims = await ProcessedClaims.find({}).toArray();
    const unifiedClaims: UnifiedClaim[] = [];

    for (const claim of claims) {
      const payment = paymentLookup.get(claim._id.toString());
      
      // Transform procedures
      const procedures = (claim.procedures || []).map((proc: any) => {
        const feeBilled = parseFloat(proc.feeBilled || 0);
        const writeOff = parseFloat(proc.writeOff || '0');
        
        return {
          code: proc.procCode,
          fee_billed: feeBilled,
          fee_allowed: parseFloat(proc.allowedAmount || 0),
          amount_paid: parseFloat(proc.insAmountPaid || 0),
          write_off: writeOff,
          write_off_percent: feeBilled > 0 ? (writeOff / feeBilled) * 100 : 0
        };
      });

      unifiedClaims.push({
        claim_id: claim._id.toString(),
        location_id: claim.locationId,
        provider_id: claim.providerId,
        patient_id: claim.patientId,
        service_date: claim.date_sent,
        payment: payment ? {
          checkNumber: payment.checkNumber,
          carrierName: payment.carrierName,
          checkAmount: payment.checkAmt,
          dateIssued: payment.dateIssued
        } : undefined,
        procedures,
        totals: {
          billed: procedures.reduce((sum, p) => sum + p.fee_billed, 0),
          allowed: procedures.reduce((sum, p) => sum + p.fee_allowed, 0),
          paid: procedures.reduce((sum, p) => sum + p.amount_paid, 0),
          write_off: procedures.reduce((sum, p) => sum + p.write_off, 0)
        }
      });
    }

    console.log(`✅ Extracted ${unifiedClaims.length} unified claims`);
    return unifiedClaims;
  }
}
```

## Step 3: Create Fee Schedule Extractor

Create `src/extractors/FeeScheduleExtractor.ts`:
```typescript
import { PythonBridge } from '../utils/python-bridge';
import fs from 'fs/promises';
import path from 'path';
import csv from 'csv-parse/sync';

interface FeeSchedule {
  carrier_code: string;
  schedule_name: string;
  location_ids: string[];
  effective_date: Date;
  fees: Record<string, number>;
}

export class FeeScheduleExtractor {
  private pythonScript: string;
  private csvOutputDir: string;

  constructor() {
    this.pythonScript = path.join(__dirname, 'fees/fee_extractor.py');
    this.csvOutputDir = path.join(process.cwd(), 'output');
  }

  async extractFromCSV(): Promise<FeeSchedule[]> {
    console.log('💰 Extracting fee schedules from CSV files...');
    
    // Find latest CSV file
    const files = await fs.readdir(this.csvOutputDir);
    const csvFiles = files.filter(f => f.startsWith('fee_schedules_'));
    
    if (csvFiles.length === 0) {
      console.log('No fee schedule CSV files found, generating...');
      await this.generateFeeScheduleCSV();
    }

    const latestFile = csvFiles.sort().pop();
    const csvPath = path.join(this.csvOutputDir, latestFile!);
    
    // Parse CSV
    const fileContent = await fs.readFile(csvPath, 'utf-8');
    const records = csv.parse(fileContent, {
      columns: true,
      skip_empty_lines: true
    });

    // Group by carrier and location
    const scheduleMap = new Map<string, FeeSchedule>();
    
    for (const record of records) {
      const key = `${record.carrier_code}_${record.schedule_name}`;
      
      if (!scheduleMap.has(key)) {
        scheduleMap.set(key, {
          carrier_code: record.carrier_code,
          schedule_name: record.schedule_name,
          location_ids: [],
          effective_date: new Date(),
          fees: {}
        });
      }
      
      const schedule = scheduleMap.get(key)!;
      if (!schedule.location_ids.includes(record.location_id)) {
        schedule.location_ids.push(record.location_id);
      }
      schedule.fees[record.procedure_code] = parseFloat(record.fee_amount);
    }

    const schedules = Array.from(scheduleMap.values());
    console.log(`✅ Extracted ${schedules.length} fee schedules`);
    return schedules;
  }

  private async generateFeeScheduleCSV(): Promise<void> {
    await PythonBridge.execute(this.pythonScript, ['--output', this.csvOutputDir]);
  }
}
```

## Step 4: Create Master Extractor Orchestrator

Create `src/extractors/MasterExtractor.ts`:
```typescript
import { SmartsheetExtractor } from './SmartsheetExtractor';
import { OpenDentalExtractor } from './OpenDentalExtractor';
import { FeeScheduleExtractor } from './FeeScheduleExtractor';

export class MasterExtractor {
  private smartsheet: SmartsheetExtractor;
  private opendental: OpenDentalExtractor;
  private fees: FeeScheduleExtractor;

  constructor() {
    this.smartsheet = new SmartsheetExtractor();
    this.opendental = new OpenDentalExtractor();
    this.fees = new FeeScheduleExtractor();
  }

  async extractAll() {
    console.log('🚀 Starting complete extraction process...\n');
    
    const startTime = Date.now();
    
    // Run extractions in parallel where possible
    const [credentialing, providers] = await Promise.all([
      this.smartsheet.extractCredentialing(),
      this.smartsheet.extractProviders()
    ]);

    // OpenDental needs its own connection
    await this.opendental.connectToActivityDB();
    const claims = await this.opendental.extractClaimsWithPayments();

    // Fee schedules
    const feeSchedules = await this.fees.extractFromCSV();

    const duration = (Date.now() - startTime) / 1000;
    
    console.log('\n📊 Extraction Summary:');
    console.log(`  • Credentialing Records: ${credentialing.length}`);
    console.log(`  • Providers: ${providers.length}`);
    console.log(`  • Claims: ${claims.length}`);
    console.log(`  • Fee Schedules: ${feeSchedules.length}`);
    console.log(`  • Duration: ${duration.toFixed(2)}s\n`);

    return {
      credentialing,
      providers,
      claims,
      feeSchedules
    };
  }
}
```

## Step 5: Create Test Script

Create `src/test-extraction.ts`:
```typescript
import dotenv from 'dotenv';
import { MasterExtractor } from './extractors/MasterExtractor';

dotenv.config();

async function testExtraction() {
  try {
    const extractor = new MasterExtractor();
    const data = await extractor.extractAll();
    
    // Log sample data
    console.log('Sample Credentialing:', data.credentialing[0]);
    console.log('Sample Claim:', data.claims[0]);
    console.log('Sample Fee Schedule:', data.feeSchedules[0]);
    
    process.exit(0);
  } catch (error) {
    console.error('Extraction failed:', error);
    process.exit(1);
  }
}

testExtraction();
```

## Add Scripts to package.json
```json
{
  "scripts": {
    "dev": "nodemon src/index.ts",
    "test:extract": "ts-node src/test-extraction.ts",
    "build": "tsc",
    "start": "node dist/index.js"
  }
}
```

## Validation
Run extraction test:
```bash
npm run test:extract
```

Should output:
- ✅ Credentialing records from Smartsheet
- ✅ Claims with payment data from OpenDental
- ✅ Fee schedules from CSV
- ✅ Sample data for each type
