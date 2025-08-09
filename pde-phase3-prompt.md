# Claude Code Prompt - Phase 3: Build Transformation & Metrics Layer

Build the transformation layer that creates the exact metrics Mark needs: write-offs WITH patient volume context.

## Context from Previous Phases
- Extractors built and working
- Data available: credentialing, claims, fee schedules
- Need: Calculate carrier metrics that show write-offs AND patient counts

## Step 1: Create Carrier Metrics Calculator

Create `src/transformers/CarrierMetricsCalculator.ts`:
```typescript
interface ClaimWithPayment {
  claim_id: string;
  location_id: string;
  patient_id: string;
  carrier_code?: string;
  procedures: Array<{
    code: string;
    fee_billed: number;
    write_off: number;
    write_off_percent: number;
  }>;
  totals: {
    billed: number;
    paid: number;
    write_off: number;
  };
}

interface CarrierMetrics {
  carrier_code: string;
  carrier_name: string;
  location_id: string;
  period: string;
  
  // The metrics Mark specifically asked for
  patient_count: number;           // "841 patients"
  revenue_per_patient: number;     // "$492.28 per patient"
  avg_write_off_percent: number;   // "67% write-offs"
  
  // Supporting metrics
  total_claims: number;
  total_billed: number;
  total_paid: number;
  total_write_off: number;
  
  // For drill-down capability
  by_procedure: Record<string, {
    count: number;
    total_write_off: number;
    avg_write_off_percent: number;
  }>;
  
  calculated_at: Date;
}

export class CarrierMetricsCalculator {
  
  calculateMetrics(claims: ClaimWithPayment[], period: string = '2024_Q4'): CarrierMetrics[] {
    console.log('📊 Calculating carrier metrics with patient volume...');
    
    // Group claims by carrier and location
    const groupedData = this.groupClaimsByCarrierLocation(claims);
    const metrics: CarrierMetrics[] = [];
    
    for (const [key, claimGroup] of groupedData.entries()) {
      const [carrier_code, location_id] = key.split('::');
      
      // Get unique patients (THIS IS CRITICAL FOR MARK'S DECISION MAKING)
      const uniquePatients = new Set(claimGroup.map(c => c.patient_id));
      const patientCount = uniquePatients.size;
      
      // Calculate totals
      const totalBilled = claimGroup.reduce((sum, c) => sum + c.totals.billed, 0);
      const totalPaid = claimGroup.reduce((sum, c) => sum + c.totals.paid, 0);
      const totalWriteOff = claimGroup.reduce((sum, c) => sum + c.totals.write_off, 0);
      
      // Calculate procedure-level metrics for drill-down
      const procedureMetrics = this.calculateProcedureMetrics(claimGroup);
      
      // Build the metric object
      const metric: CarrierMetrics = {
        carrier_code,
        carrier_name: this.getCarrierName(carrier_code),
        location_id,
        period,
        
        // THE KEY METRICS FOR DECISION MAKING
        patient_count: patientCount,
        revenue_per_patient: patientCount > 0 ? totalPaid / patientCount : 0,
        avg_write_off_percent: totalBilled > 0 ? (totalWriteOff / totalBilled) * 100 : 0,
        
        // Supporting data
        total_claims: claimGroup.length,
        total_billed: totalBilled,
        total_paid: totalPaid,
        total_write_off: totalWriteOff,
        
        // Drill-down capability
        by_procedure: procedureMetrics,
        
        calculated_at: new Date()
      };
      
      metrics.push(metric);
      
      // Log key insights (like Mark's Delta example)
      if (metric.avg_write_off_percent > 50 && metric.patient_count > 500) {
        console.log(`💡 Insight: ${carrier_code} has high write-offs (${metric.avg_write_off_percent.toFixed(1)}%) but brings ${metric.patient_count} patients at $${metric.revenue_per_patient.toFixed(2)}/patient`);
      }
    }
    
    console.log(`✅ Calculated metrics for ${metrics.length} carrier-location combinations`);
    return metrics;
  }
  
  private groupClaimsByCarrierLocation(claims: ClaimWithPayment[]): Map<string, ClaimWithPayment[]> {
    const grouped = new Map<string, ClaimWithPayment[]>();
    
    for (const claim of claims) {
      // Skip claims without carrier info
      if (!claim.carrier_code) continue;
      
      const key = `${claim.carrier_code}::${claim.location_id || 'ALL'}`;
      
      if (!grouped.has(key)) {
        grouped.set(key, []);
      }
      grouped.get(key)!.push(claim);
    }
    
    return grouped;
  }
  
  private calculateProcedureMetrics(claims: ClaimWithPayment[]) {
    const procedureMap = new Map<string, {
      count: number;
      total_write_off: number;
      total_billed: number;
    }>();
    
    for (const claim of claims) {
      for (const proc of claim.procedures) {
        if (!procedureMap.has(proc.code)) {
          procedureMap.set(proc.code, {
            count: 0,
            total_write_off: 0,
            total_billed: 0
          });
        }
        
        const stats = procedureMap.get(proc.code)!;
        stats.count++;
        stats.total_write_off += proc.write_off;
        stats.total_billed += proc.fee_billed;
      }
    }
    
    // Convert to final format
    const result: Record<string, any> = {};
    for (const [code, stats] of procedureMap.entries()) {
      result[code] = {
        count: stats.count,
        total_write_off: stats.total_write_off,
        avg_write_off_percent: stats.total_billed > 0 
          ? (stats.total_write_off / stats.total_billed) * 100 
          : 0
      };
    }
    
    return result;
  }
  
  private getCarrierName(code: string): string {
    const carrierNames: Record<string, string> = {
      'DELTA': 'Delta Dental',
      'BCBS': 'Blue Cross Blue Shield',
      'CIGNA': 'Cigna',
      'AETNA': 'Aetna',
      'UHC': 'United Healthcare',
      'METLIFE': 'MetLife',
      // Add more mappings as needed
    };
    return carrierNames[code] || code;
  }
}
```

## Step 2: Create Credentialing Matrix Transformer

Create `src/transformers/CredentialingMatrixBuilder.ts`:
```typescript
interface CredentialingRecord {
  provider_id: string;
  carrier_code: string;
  location_id: string;
  status: string;
  effective_date: Date;
}

interface Provider {
  provider_id: string;
  name: string;
  npi: string;
  locations: string[];
}

interface CredentialingMatrix {
  provider_id: string;
  provider_name: string;
  total_locations: number;
  total_carriers: number;
  credentialing_coverage: number; // Percentage of possible assignments completed
  
  // Matrix view data
  by_carrier: Record<string, {
    credentialed_locations: string[];
    missing_locations: string[];
    coverage_percent: number;
  }>;
  
  // Gaps identification
  gaps: Array<{
    carrier_code: string;
    location_id: string;
    impact: 'HIGH' | 'MEDIUM' | 'LOW';
    reason: string;
  }>;
}

export class CredentialingMatrixBuilder {
  
  buildMatrix(
    credentialing: CredentialingRecord[],
    providers: Provider[],
    locations: string[],
    priorityCarriers: string[] = ['DELTA', 'BCBS', 'CIGNA', 'AETNA', 'UHC']
  ): CredentialingMatrix[] {
    console.log('🔐 Building credentialing matrix...');
    
    const matrices: CredentialingMatrix[] = [];
    
    for (const provider of providers) {
      // Get all credentialing for this provider
      const providerCreds = credentialing.filter(c => c.provider_id === provider.provider_id);
      
      // Build carrier analysis
      const byCarrier: Record<string, any> = {};
      const gaps: any[] = [];
      
      for (const carrier of priorityCarriers) {
        const carrierCreds = providerCreds.filter(c => c.carrier_code === carrier);
        const credentialedLocations = carrierCreds.map(c => c.location_id);
        const missingLocations = provider.locations.filter(loc => !credentialedLocations.includes(loc));
        
        byCarrier[carrier] = {
          credentialed_locations: credentialedLocations,
          missing_locations: missingLocations,
          coverage_percent: (credentialedLocations.length / provider.locations.length) * 100
        };
        
        // Identify high-impact gaps
        if (missingLocations.length > 0 && priorityCarriers.includes(carrier)) {
          gaps.push({
            carrier_code: carrier,
            location_id: missingLocations[0], // Report first gap
            impact: missingLocations.length > 3 ? 'HIGH' : 'MEDIUM',
            reason: `Provider not credentialed with ${carrier} at ${missingLocations.length} locations`
          });
        }
      }
      
      // Calculate overall coverage
      const totalPossibleAssignments = provider.locations.length * priorityCarriers.length;
      const actualAssignments = providerCreds.filter(c => 
        priorityCarriers.includes(c.carrier_code)
      ).length;
      
      matrices.push({
        provider_id: provider.provider_id,
        provider_name: provider.name,
        total_locations: provider.locations.length,
        total_carriers: new Set(providerCreds.map(c => c.carrier_code)).size,
        credentialing_coverage: (actualAssignments / totalPossibleAssignments) * 100,
        by_carrier: byCarrier,
        gaps: gaps
      });
      
      // Log critical gaps
      if (gaps.filter(g => g.impact === 'HIGH').length > 0) {
        console.log(`⚠️  Provider ${provider.name} has ${gaps.filter(g => g.impact === 'HIGH').length} high-impact credentialing gaps`);
      }
    }
    
    console.log(`✅ Built credentialing matrix for ${matrices.length} providers`);
    
    // Summary statistics
    const avgCoverage = matrices.reduce((sum, m) => sum + m.credentialing_coverage, 0) / matrices.length;
    console.log(`📊 Average credentialing coverage: ${avgCoverage.toFixed(1)}%`);
    
    return matrices;
  }
}
```

## Step 3: Create Fee Analysis Transformer

Create `src/transformers/FeeAnalyzer.ts`:
```typescript
interface FeeSchedule {
  carrier_code: string;
  fees: Record<string, number>;
}

interface ClaimProcedure {
  code: string;
  fee_billed: number;
  fee_allowed: number;
  write_off: number;
}

interface FeeAnalysis {
  carrier_code: string;
  procedure_code: string;
  
  // Contract vs Reality
  contracted_rate: number;
  actual_allowed: number;
  variance: number;
  variance_percent: number;
  
  // Volume context
  procedure_count: number;
  total_loss: number; // For negotiation evidence
  
  // Recommendations
  action: 'NEGOTIATE' | 'ACCEPT' | 'DROP' | 'MONITOR';
  reason: string;
}

export class FeeAnalyzer {
  
  analyzeFeePerformance(
    feeSchedules: FeeSchedule[],
    claims: any[],
    minVolumeThreshold: number = 10
  ): FeeAnalysis[] {
    console.log('💰 Analyzing fee schedule performance...');
    
    const analyses: FeeAnalysis[] = [];
    
    // Build actual payment data from claims
    const actualPayments = this.aggregateActualPayments(claims);
    
    for (const schedule of feeSchedules) {
      for (const [procCode, contractedRate] of Object.entries(schedule.fees)) {
        const actualData = actualPayments.get(`${schedule.carrier_code}::${procCode}`);
        
        if (!actualData || actualData.count < minVolumeThreshold) {
          continue; // Skip low-volume procedures
        }
        
        const avgActualAllowed = actualData.totalAllowed / actualData.count;
        const variance = contractedRate - avgActualAllowed;
        const variancePercent = (variance / contractedRate) * 100;
        const totalLoss = variance * actualData.count;
        
        // Determine action based on variance and volume
        let action: FeeAnalysis['action'] = 'MONITOR';
        let reason = '';
        
        if (variancePercent > 20 && actualData.count > 100) {
          action = 'NEGOTIATE';
          reason = `Losing $${totalLoss.toFixed(0)} annually on ${actualData.count} procedures`;
        } else if (variancePercent > 30 && actualData.count > 50) {
          action = 'DROP';
          reason = `Excessive write-offs (${variancePercent.toFixed(1)}%) not justified by volume`;
        } else if (variancePercent < 5) {
          action = 'ACCEPT';
          reason = 'Reimbursement meeting expectations';
        }
        
        analyses.push({
          carrier_code: schedule.carrier_code,
          procedure_code: procCode,
          contracted_rate: contractedRate,
          actual_allowed: avgActualAllowed,
          variance: variance,
          variance_percent: variancePercent,
          procedure_count: actualData.count,
          total_loss: totalLoss,
          action,
          reason
        });
        
        // Log significant losses (like the $56,700 on D0120 Mark mentioned)
        if (totalLoss > 10000) {
          console.log(`💸 Major loss identified: ${schedule.carrier_code} - ${procCode}: $${totalLoss.toFixed(0)} loss on ${actualData.count} procedures`);
        }
      }
    }
    
    console.log(`✅ Analyzed ${analyses.length} carrier-procedure combinations`);
    
    // Summary of negotiation opportunities
    const negotiateItems = analyses.filter(a => a.action === 'NEGOTIATE');
    const totalNegotiationOpportunity = negotiateItems.reduce((sum, item) => sum + item.total_loss, 0);
    console.log(`💡 Negotiation opportunity: $${totalNegotiationOpportunity.toFixed(0)} across ${negotiateItems.length} procedure codes`);
    
    return analyses;
  }
  
  private aggregateActualPayments(claims: any[]): Map<string, {count: number; totalAllowed: number}> {
    const aggregated = new Map<string, {count: number; totalAllowed: number}>();
    
    for (const claim of claims) {
      if (!claim.carrier_code) continue;
      
      for (const proc of claim.procedures) {
        const key = `${claim.carrier_code}::${proc.code}`;
        
        if (!aggregated.has(key)) {
          aggregated.set(key, { count: 0, totalAllowed: 0 });
        }
        
        const stats = aggregated.get(key)!;
        stats.count++;
        stats.totalAllowed += proc.fee_allowed;
      }
    }
    
    return aggregated;
  }
}
```

## Step 4: Create Master Transformer

Create `src/transformers/MasterTransformer.ts`:
```typescript
import { CarrierMetricsCalculator } from './CarrierMetricsCalculator';
import { CredentialingMatrixBuilder } from './CredentialingMatrixBuilder';
import { FeeAnalyzer } from './FeeAnalyzer';

export class MasterTransformer {
  private metricsCalc: CarrierMetricsCalculator;
  private credMatrix: CredentialingMatrixBuilder;
  private feeAnalyzer: FeeAnalyzer;
  
  constructor() {
    this.metricsCalc = new CarrierMetricsCalculator();
    this.credMatrix = new CredentialingMatrixBuilder();
    this.feeAnalyzer = new FeeAnalyzer();
  }
  
  async transformAll(extractedData: any) {
    console.log('⚙️  Starting transformation pipeline...\n');
    
    const { credentialing, providers, claims, feeSchedules } = extractedData;
    
    // 1. Calculate carrier metrics (Mark's key requirement)
    const carrierMetrics = this.metricsCalc.calculateMetrics(claims);
    
    // 2. Build credentialing matrix
    const locations = ['44', '12', '08', '15', '22']; // Get from config
    const credentialingMatrix = this.credMatrix.buildMatrix(
      credentialing,
      providers,
      locations
    );
    
    // 3. Analyze fee performance
    const feeAnalysis = this.feeAnalyzer.analyzeFeePerformance(
      feeSchedules,
      claims
    );
    
    console.log('\n📊 Transformation Summary:');
    console.log(`  • Carrier Metrics: ${carrierMetrics.length} combinations`);
    console.log(`  • Credentialing Matrices: ${credentialingMatrix.length} providers`);
    console.log(`  • Fee Analyses: ${feeAnalysis.length} opportunities`);
    
    return {
      carrierMetrics,
      credentialingMatrix,
      feeAnalysis,
      raw: extractedData // Keep raw data for reference
    };
  }
}
```

## Step 5: Update Test Script

Update `src/test-transformation.ts`:
```typescript
import dotenv from 'dotenv';
import { MasterExtractor } from './extractors/MasterExtractor';
import { MasterTransformer } from './transformers/MasterTransformer';

dotenv.config();

async function testTransformation() {
  try {
    // Extract
    const extractor = new MasterExtractor();
    const extractedData = await extractor.extractAll();
    
    // Transform
    const transformer = new MasterTransformer();
    const transformedData = await transformer.transformAll(extractedData);
    
    // Show key insights
    console.log('\n🎯 KEY INSIGHTS:\n');
    
    // Find Delta Dental metrics (Mark's example)
    const deltaMetrics = transformedData.carrierMetrics.find(m => m.carrier_code === 'DELTA');
    if (deltaMetrics) {
      console.log(`Delta Dental Analysis:`);
      console.log(`  • Write-offs: ${deltaMetrics.avg_write_off_percent.toFixed(1)}%`);
      console.log(`  • Patients: ${deltaMetrics.patient_count}`);
      console.log(`  • Revenue/Patient: $${deltaMetrics.revenue_per_patient.toFixed(2)}`);
      console.log(`  • Decision: ${deltaMetrics.patient_count > 500 ? 'STAY IN-NETWORK' : 'EVALUATE'}\n`);
    }
    
    // Show credentialing gaps
    const highGaps = transformedData.credentialingMatrix
      .flatMap(m => m.gaps)
      .filter(g => g.impact === 'HIGH');
    console.log(`Credentialing Gaps: ${highGaps.length} high-impact gaps found\n`);
    
    // Show negotiation opportunities
    const negotiations = transformedData.feeAnalysis
      .filter(f => f.action === 'NEGOTIATE')
      .sort((a, b) => b.total_loss - a.total_loss)
      .slice(0, 5);
    
    console.log('Top 5 Fee Negotiation Opportunities:');
    negotiations.forEach(n => {
      console.log(`  • ${n.carrier_code} - ${n.procedure_code}: $${n.total_loss.toFixed(0)} potential recovery`);
    });
    
    process.exit(0);
  } catch (error) {
    console.error('Transformation failed:', error);
    process.exit(1);
  }
}

testTransformation();
```

## Validation
```bash
npm run test:transform
```

Expected output:
- ✅ Carrier metrics with patient counts
- ✅ Delta Dental example matching Mark's requirements
- ✅ Credentialing gap identification
- ✅ Fee negotiation opportunities with dollar amounts
