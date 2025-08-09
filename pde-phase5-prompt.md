# Claude Code Prompt - Phase 5: Build REST API for Admin Cockpit

Create the REST API layer that serves data to the Admin Cockpit dashboard, maintaining exact compatibility with existing frontend expectations.

## Context from Previous Phases
- Database populated with: carrier_metrics, credentialing_matrix, unified_claims, fee_schedules
- Admin Cockpit expects specific endpoints and response formats
- Must maintain backward compatibility

## Step 1: Create API Controllers

Create `src/api/controllers/CredentialingController.ts`:
```typescript
import { Request, Response } from 'express';
import { CredentialingMatrix } from '../../models/CredentialingMatrix';
import { CarrierMetrics } from '../../models/CarrierMetrics';

export class CredentialingController {
  
  /**
   * Get credentialing matrix for dashboard display
   * Expected by: Admin Cockpit Credentialing Page
   */
  async getMatrix(req: Request, res: Response) {
    try {
      const { provider_id, carrier_code, location_id, status } = req.query;
      
      // Build query
      const query: any = {};
      if (provider_id) query.provider_id = provider_id;
      if (carrier_code) query.carrier_code = carrier_code;
      if (location_id) query.location_id = location_id;
      if (status) query.status = status;
      
      const matrix = await CredentialingMatrix.find(query)
        .sort({ provider_name: 1, carrier_code: 1 })
        .lean();
      
      // Group by provider for dashboard display
      const groupedMatrix = this.groupByProvider(matrix);
      
      res.json({
        success: true,
        data: groupedMatrix,
        total: matrix.length,
        timestamp: new Date()
      });
    } catch (error) {
      console.error('Error fetching credentialing matrix:', error);
      res.status(500).json({
        success: false,
        error: 'Failed to fetch credentialing matrix'
      });
    }
  }
  
  /**
   * Get credentialing gaps analysis
   */
  async getGaps(req: Request, res: Response) {
    try {
      const priorityCarriers = ['DELTA', 'BCBS', 'CIGNA', 'AETNA', 'UHC'];
      
      // Find all providers
      const allProviders = await CredentialingMatrix.distinct('provider_id');
      const allLocations = await CredentialingMatrix.distinct('location_id');
      
      const gaps = [];
      
      for (const provider of allProviders) {
        for (const carrier of priorityCarriers) {
          for (const location of allLocations) {
            const exists = await CredentialingMatrix.findOne({
              provider_id: provider,
              carrier_code: carrier,
              location_id: location,
              status: 'ACTIVE'
            });
            
            if (!exists) {
              gaps.push({
                provider_id: provider,
                carrier_code: carrier,
                location_id: location,
                impact: 'HIGH', // Calculate based on patient volume
                estimated_loss: 0 // Calculate from carrier metrics
              });
            }
          }
        }
      }
      
      // Enhance gaps with financial impact
      for (const gap of gaps) {
        const metrics = await CarrierMetrics.findOne({
          carrier_code: gap.carrier_code,
          location_id: gap.location_id
        });
        
        if (metrics) {
          gap.estimated_loss = metrics.revenue_per_patient * 10; // Estimate 10 patients/month
        }
      }
      
      res.json({
        success: true,
        data: gaps.sort((a, b) => b.estimated_loss - a.estimated_loss),
        summary: {
          total_gaps: gaps.length,
          high_impact: gaps.filter(g => g.estimated_loss > 1000).length,
          total_estimated_loss: gaps.reduce((sum, g) => sum + g.estimated_loss, 0)
        }
      });
    } catch (error) {
      console.error('Error analyzing credentialing gaps:', error);
      res.status(500).json({
        success: false,
        error: 'Failed to analyze credentialing gaps'
      });
    }
  }
  
  private groupByProvider(matrix: any[]) {
    const grouped: Record<string, any> = {};
    
    for (const record of matrix) {
      if (!grouped[record.provider_id]) {
        grouped[record.provider_id] = {
          provider_id: record.provider_id,
          provider_name: record.provider_name,
          carriers: {}
        };
      }
      
      if (!grouped[record.provider_id].carriers[record.carrier_code]) {
        grouped[record.provider_id].carriers[record.carrier_code] = {
          locations: []
        };
      }
      
      grouped[record.provider_id].carriers[record.carrier_code].locations.push({
        location_id: record.location_id,
        status: record.status,
        effective_date: record.effective_date
      });
    }
    
    return Object.values(grouped);
  }
}
```

Create `src/api/controllers/FeeStrategyController.ts`:
```typescript
import { Request, Response } from 'express';
import { CarrierMetrics } from '../../models/CarrierMetrics';
import { UnifiedClaim } from '../../models/UnifiedClaim';
import { FeeSchedule } from '../../models/FeeSchedule';

export class FeeStrategyController {
  
  /**
   * Get pivot table data for Fee Strategy page
   * This is the CRITICAL endpoint for Mark's decision making
   */
  async getPivotData(req: Request, res: Response) {
    try {
      const { 
        carrier_code, 
        location_id, 
        period = '2024_Q4',
        min_patient_count = 0 
      } = req.query;
      
      // Build query
      const query: any = { period };
      if (carrier_code) query.carrier_code = carrier_code;
      if (location_id) query.location_id = location_id;
      if (min_patient_count) {
        query.patient_count = { $gte: parseInt(min_patient_count as string) };
      }
      
      const metrics = await CarrierMetrics.find(query)
        .sort({ patient_count: -1 })
        .lean();
      
      // Format for pivot table
      const pivotData = metrics.map(m => ({
        carrier: m.carrier_name,
        carrier_code: m.carrier_code,
        location: m.location_id,
        
        // THE KEY COLUMNS MARK NEEDS
        write_off_percent: m.avg_write_off_percent.toFixed(1) + '%',
        patient_count: m.patient_count,
        revenue_per_patient: '$' + m.revenue_per_patient.toFixed(2),
        
        // Supporting data
        total_revenue: '$' + m.total_paid.toLocaleString(),
        total_write_off: '$' + m.total_write_off.toLocaleString(),
        
        // Decision helper
        recommendation: this.getRecommendation(m),
        
        // For drill-down
        _id: m._id,
        has_procedure_details: Object.keys(m.by_procedure || {}).length > 0
      }));
      
      res.json({
        success: true,
        data: pivotData,
        summary: {
          total_carriers: new Set(metrics.map(m => m.carrier_code)).size,
          total_locations: new Set(metrics.map(m => m.location_id)).size,
          avg_write_off: (metrics.reduce((sum, m) => sum + m.avg_write_off_percent, 0) / metrics.length).toFixed(1),
          total_patients: metrics.reduce((sum, m) => sum + m.patient_count, 0)
        },
        filters_applied: { carrier_code, location_id, period }
      });
    } catch (error) {
      console.error('Error fetching pivot data:', error);
      res.status(500).json({
        success: false,
        error: 'Failed to fetch pivot data'
      });
    }
  }
  
  /**
   * Drill down into specific carrier-location combination
   */
  async drillDown(req: Request, res: Response) {
    try {
      const { carrier_code, location_id, procedure_code } = req.query;
      
      if (procedure_code) {
        // Deepest level - show individual claims for this procedure
        const claims = await UnifiedClaim.find({
          carrier_code,
          location_id,
          'procedures.code': procedure_code
        })
        .limit(100)
        .sort({ service_date: -1 })
        .lean();
        
        const procedureDetails = claims.map(claim => {
          const proc = claim.procedures.find(p => p.code === procedure_code);
          return {
            claim_id: claim.claim_id,
            service_date: claim.service_date,
            patient_id: claim.patient_id,
            fee_billed: proc?.fee_billed,
            fee_allowed: proc?.fee_allowed,
            amount_paid: proc?.amount_paid,
            write_off: proc?.write_off,
            write_off_percent: proc?.write_off_percent?.toFixed(1) + '%'
          };
        });
        
        res.json({
          success: true,
          level: 'procedure_claims',
          data: procedureDetails
        });
        
      } else if (carrier_code && location_id) {
        // Mid level - show procedure breakdown
        const metrics = await CarrierMetrics.findOne({
          carrier_code,
          location_id
        }).lean();
        
        if (!metrics || !metrics.by_procedure) {
          return res.json({
            success: true,
            level: 'procedures',
            data: []
          });
        }
        
        const procedureBreakdown = Object.entries(metrics.by_procedure).map(([code, stats]: [string, any]) => ({
          procedure_code: code,
          procedure_count: stats.count,
          total_write_off: '$' + stats.total_write_off.toLocaleString(),
          avg_write_off_percent: stats.avg_write_off_percent.toFixed(1) + '%',
          
          // For negotiation evidence
          annual_loss: '$' + (stats.total_write_off * 4).toLocaleString(), // Quarterly * 4
          negotiation_priority: stats.total_write_off > 10000 ? 'HIGH' : 'NORMAL'
        }));
        
        res.json({
          success: true,
          level: 'procedures',
          data: procedureBreakdown.sort((a, b) => {
            const aLoss = parseFloat(a.total_write_off.replace(/[$,]/g, ''));
            const bLoss = parseFloat(b.total_write_off.replace(/[$,]/g, ''));
            return bLoss - aLoss;
          })
        });
        
      } else {
        // Top level - show all locations for carrier
        const metrics = await CarrierMetrics.find({ carrier_code }).lean();
        
        res.json({
          success: true,
          level: 'locations',
          data: metrics.map(m => ({
            location_id: m.location_id,
            patient_count: m.patient_count,
            revenue_per_patient: '$' + m.revenue_per_patient.toFixed(2),
            avg_write_off_percent: m.avg_write_off_percent.toFixed(1) + '%'
          }))
        });
      }
    } catch (error) {
      console.error('Error in drill-down:', error);
      res.status(500).json({
        success: false,
        error: 'Failed to drill down'
      });
    }
  }
  
  /**
   * Get fee comparison analysis
   */
  async compareFees(req: Request, res: Response) {
    try {
      const { carrier1, carrier2, procedure_codes } = req.body;
      
      const [schedule1, schedule2] = await Promise.all([
        FeeSchedule.findOne({ carrier_code: carrier1 }),
        FeeSchedule.findOne({ carrier_code: carrier2 })
      ]);
      
      const comparison = [];
      const codes = procedure_codes || Object.keys(schedule1?.fees || {});
      
      for (const code of codes) {
        const fee1 = schedule1?.fees[code] || 0;
        const fee2 = schedule2?.fees[code] || 0;
        const difference = fee1 - fee2;
        const percentDiff = fee2 > 0 ? (difference / fee2) * 100 : 0;
        
        comparison.push({
          procedure_code: code,
          [carrier1]: '$' + fee1.toFixed(2),
          [carrier2]: '$' + fee2.toFixed(2),
          difference: '$' + difference.toFixed(2),
          percent_difference: percentDiff.toFixed(1) + '%',
          favors: difference > 0 ? carrier1 : carrier2
        });
      }
      
      res.json({
        success: true,
        data: comparison.sort((a, b) => {
          const aDiff = parseFloat(a.difference.replace(/[$,]/g, ''));
          const bDiff = parseFloat(b.difference.replace(/[$,]/g, ''));
          return Math.abs(bDiff) - Math.abs(aDiff);
        })
      });
    } catch (error) {
      console.error('Error comparing fees:', error);
      res.status(500).json({
        success: false,
        error: 'Failed to compare fees'
      });
    }
  }
  
  private getRecommendation(metrics: any): string {
    // Business logic matching Mark's criteria
    if (metrics.avg_write_off_percent > 60 && metrics.patient_count < 100) {
      return 'EVALUATE - High write-offs, low volume';
    } else if (metrics.avg_write_off_percent > 50 && metrics.patient_count > 500) {
      return 'KEEP - High volume justifies write-offs';
    } else if (metrics.revenue_per_patient < 200) {
      return 'NEGOTIATE - Low revenue per patient';
    } else if (metrics.avg_write_off_percent < 30 && metrics.patient_count > 200) {
      return 'EXCELLENT - Good rates and volume';
    }
    return 'MONITOR';
  }
}
```

Create `src/api/controllers/DashboardController.ts`:
```typescript
import { Request, Response } from 'express';
import { CarrierMetrics } from '../../models/CarrierMetrics';
import { CredentialingMatrix } from '../../models/CredentialingMatrix';
import { UnifiedClaim } from '../../models/UnifiedClaim';

export class DashboardController {
  
  /**
   * Get summary statistics for main dashboard
   */
  async getSummary(req: Request, res: Response) {
    try {
      const [
        totalClaims,
        totalProviders,
        activeCredentials,
        carrierMetrics
      ] = await Promise.all([
        UnifiedClaim.countDocuments(),
        CredentialingMatrix.distinct('provider_id'),
        CredentialingMatrix.countDocuments({ status: 'ACTIVE' }),
        CarrierMetrics.find().lean()
      ]);
      
      // Calculate key metrics
      const totalWriteOff = carrierMetrics.reduce((sum, m) => sum + m.total_write_off, 0);
      const totalRevenue = carrierMetrics.reduce((sum, m) => sum + m.total_paid, 0);
      const avgWriteOffPercent = carrierMetrics.reduce((sum, m) => sum + m.avg_write_off_percent, 0) / carrierMetrics.length;
      
      res.json({
        success: true,
        data: {
          claims: {
            total: totalClaims,
            processed_today: 0, // Would calculate from timestamps
            pending: 0
          },
          providers: {
            total: totalProviders.length,
            fully_credentialed: 0, // Would calculate
            with_gaps: 0
          },
          credentialing: {
            active: activeCredentials,
            expiring_soon: 0, // Would calculate
            pending: 0
          },
          financial: {
            total_revenue: totalRevenue,
            total_write_off: totalWriteOff,
            avg_write_off_percent: avgWriteOffPercent,
            top_carriers_by_volume: this.getTopCarriers(carrierMetrics)
          }
        },
        generated_at: new Date()
      });
    } catch (error) {
      console.error('Error fetching dashboard summary:', error);
      res.status(500).json({
        success: false,
        error: 'Failed to fetch dashboard summary'
      });
    }
  }
  
  private getTopCarriers(metrics: any[]) {
    const carrierTotals = new Map();
    
    for (const m of metrics) {
      if (!carrierTotals.has(m.carrier_code)) {
        carrierTotals.set(m.carrier_code, {
          carrier: m.carrier_name,
          patient_count: 0,
          total_revenue: 0
        });
      }
      
      const totals = carrierTotals.get(m.carrier_code);
      totals.patient_count += m.patient_count;
      totals.total_revenue += m.total_paid;
    }
    
    return Array.from(carrierTotals.values())
      .sort((a, b) => b.patient_count - a.patient_count)
      .slice(0, 5);
  }
}
```

## Step 2: Create API Routes

Create `src/api/routes/index.ts`:
```typescript
import { Router } from 'express';
import { CredentialingController } from '../controllers/CredentialingController';
import { FeeStrategyController } from '../controllers/FeeStrategyController';
import { DashboardController } from '../controllers/DashboardController';

export function createRoutes(): Router {
  const router = Router();
  
  // Controllers
  const credentialing = new CredentialingController();
  const feeStrategy = new FeeStrategyController();
  const dashboard = new DashboardController();
  
  // Dashboard routes
  router.get('/dashboard/summary', dashboard.getSummary.bind(dashboard));
  
  // Credentialing routes
  router.get('/credentialing/matrix', credentialing.getMatrix.bind(credentialing));
  router.get('/credentialing/gaps', credentialing.getGaps.bind(credentialing));
  
  // Fee Strategy routes (CRITICAL FOR MARK)
  router.get('/fee-strategy/pivot', feeStrategy.getPivotData.bind(feeStrategy));
  router.get('/fee-strategy/drill-down', feeStrategy.drillDown.bind(feeStrategy));
  router.post('/fee-strategy/compare', feeStrategy.compareFees.bind(feeStrategy));
  
  // Health check
  router.get('/health', (req, res) => {
    res.json({ 
      status: 'healthy', 
      service: 'PDE API',
      timestamp: new Date()
    });
  });
  
  return router;
}
```

## Step 3: Create Express Server

Create `src/api/server.ts`:
```typescript
import express from 'express';
import cors from 'cors';
import helmet from 'helmet';
import compression from 'compression';
import { createRoutes } from './routes';
import { DatabaseManager } from '../database/DatabaseManager';
import dotenv from 'dotenv';

dotenv.config();

export class APIServer {
  private app: express.Application;
  private db: DatabaseManager;
  private port: number;
  
  constructor(port: number = 3001) {
    this.app = express();
    this.db = DatabaseManager.getInstance();
    this.port = port;
    
    this.setupMiddleware();
    this.setupRoutes();
    this.setupErrorHandling();
  }
  
  private setupMiddleware() {
    // Security
    this.app.use(helmet());
    
    // CORS - configure for Admin Cockpit frontend
    this.app.use(cors({
      origin: process.env.FRONTEND_URL || 'http://localhost:3000',
      credentials: true
    }));
    
    // Body parsing
    this.app.use(express.json({ limit: '10mb' }));
    this.app.use(express.urlencoded({ extended: true }));
    
    // Compression
    this.app.use(compression());
    
    // Request logging
    this.app.use((req, res, next) => {
      console.log(`${new Date().toISOString()} ${req.method} ${req.path}`);
      next();
    });
  }
  
  private setupRoutes() {
    // API routes
    this.app.use('/api', createRoutes());
    
    // Root endpoint
    this.app.get('/', (req, res) => {
      res.json({
        service: 'Platinum Data Engine API',
        version: '1.0.0',
        endpoints: [
          '/api/dashboard/summary',
          '/api/credentialing/matrix',
          '/api/credentialing/gaps',
          '/api/fee-strategy/pivot',
          '/api/fee-strategy/drill-down',
          '/api/fee-strategy/compare'
        ]
      });
    });
  }
  
  private setupErrorHandling() {
    // 404 handler
    this.app.use((req, res) => {
      res.status(404).json({
        success: false,
        error: 'Endpoint not found'
      });
    });
    
    // Global error handler
    this.app.use((err: any, req: express.Request, res: express.Response, next: express.NextFunction) => {
      console.error('Unhandled error:', err);
      res.status(500).json({
        success: false,
        error: process.env.NODE_ENV === 'production' 
          ? 'Internal server error' 
          : err.message
      });
    });
  }
  
  async start() {
    try {
      // Connect to database
      await this.db.connect();
      
      // Start server
      this.app.listen(this.port, () => {
        console.log(`
╔════════════════════════════════════════════╗
║     PLATINUM DATA ENGINE API              ║
║                                            ║
║     Server running on port ${this.port}           ║
║     http://localhost:${this.port}                  ║
║                                            ║
║     Ready to serve Admin Cockpit          ║
╚════════════════════════════════════════════╝
        `);
      });
    } catch (error) {
      console.error('Failed to start server:', error);
      process.exit(1);
    }
  }
  
  async stop() {
    await this.db.disconnect();
    console.log('Server stopped');
  }
}
```

## Step 4: Create API Entry Point

Create `src/start-api.ts`:
```typescript
import { APIServer } from './api/server';

const server = new APIServer(parseInt(process.env.PORT || '3001'));

server.start().catch(error => {
  console.error('Failed to start API server:', error);
  process.exit(1);
});

// Graceful shutdown
process.on('SIGINT', async () => {
  console.log('\nShutting down gracefully...');
  await server.stop();
  process.exit(0);
});
```

## Step 5: Update package.json

Add necessary dependencies and scripts:
```json
{
  "scripts": {
    "dev": "nodemon src/index.ts",
    "api": "nodemon src/start-api.ts",
    "pipeline": "ts-node src/index.ts",
    "pipeline:clear": "ts-node src/index.ts --clear",
    "start": "node dist/start-api.js",
    "build": "tsc",
    "test:api": "curl http://localhost:3001/api/health"
  },
  "dependencies": {
    "express": "^4.18.2",
    "cors": "^2.8.5",
    "helmet": "^7.0.0",
    "compression": "^1.7.4",
    "mongoose": "^7.5.0",
    "dotenv": "^16.3.1",
    "@types/express": "^4.17.17",
    "@types/cors": "^2.8.13",
    "@types/compression": "^1.7.2"
  }
}
```

## Validation

Start the API server:
```bash
npm run api
```

Test endpoints:
```bash
# Health check
curl http://localhost:3001/api/health

# Get pivot data (Mark's critical view)
curl http://localhost:3001/api/fee-strategy/pivot

# Get credentialing matrix
curl http://localhost:3001/api/credentialing/matrix

# Drill down into Delta Dental
curl "http://localhost:3001/api/fee-strategy/drill-down?carrier_code=DELTA&location_id=44"
```

Expected results:
- ✅ API responds on port 3001
- ✅ Pivot endpoint returns carrier metrics with patient counts
- ✅ Credentialing endpoint returns matrix data
- ✅ Drill-down works through all levels
