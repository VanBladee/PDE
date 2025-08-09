# Claude Code Prompt - Phase 6: Pipeline Automation & Monitoring

Set up automated scheduling, monitoring, and alerting for the PDE pipeline to ensure data stays fresh without manual intervention.

## Context from Previous Phases
- Complete ETL pipeline built and working
- API serving Admin Cockpit
- Need: Automatic daily/hourly updates

## Step 1: Create Pipeline Scheduler

Create `src/scheduler/PipelineScheduler.ts`:
```typescript
import cron from 'node-cron';
import { CompletePipeline } from '../pipeline/CompletePipeline';
import { DatabaseManager } from '../database/DatabaseManager';
import { EmailNotifier } from '../utils/EmailNotifier';
import { SlackNotifier } from '../utils/SlackNotifier';

interface ScheduleConfig {
  credentialing: string;  // Cron expression
  claims: string;
  metrics: string;
  fullPipeline: string;
}

export class PipelineScheduler {
  private pipeline: CompletePipeline;
  private emailNotifier: EmailNotifier;
  private slackNotifier: SlackNotifier;
  private jobs: Map<string, cron.ScheduledTask>;
  
  constructor() {
    this.pipeline = new CompletePipeline();
    this.emailNotifier = new EmailNotifier();
    this.slackNotifier = new SlackNotifier();
    this.jobs = new Map();
  }
  
  /**
   * Initialize all scheduled jobs
   */
  initializeSchedules(config: ScheduleConfig = this.getDefaultConfig()) {
    console.log('⏰ Initializing pipeline schedules...\n');
    
    // Daily credentialing sync (6 AM)
    this.scheduleJob('credentialing', config.credentialing, async () => {
      console.log('Running scheduled credentialing sync...');
      await this.runCredentialingSync();
    });
    
    // Hourly claims sync (every hour)
    this.scheduleJob('claims', config.claims, async () => {
      console.log('Running scheduled claims sync...');
      await this.runClaimsSync();
    });
    
    // Metrics recalculation (every 4 hours)
    this.scheduleJob('metrics', config.metrics, async () => {
      console.log('Running scheduled metrics calculation...');
      await this.runMetricsCalculation();
    });
    
    // Full pipeline (daily at 2 AM)
    this.scheduleJob('fullPipeline', config.fullPipeline, async () => {
      console.log('Running scheduled full pipeline...');
      await this.runFullPipeline();
    });
    
    console.log('✅ All schedules initialized:');
    console.log(`  • Credentialing: ${config.credentialing}`);
    console.log(`  • Claims: ${config.claims}`);
    console.log(`  • Metrics: ${config.metrics}`);
    console.log(`  • Full Pipeline: ${config.fullPipeline}\n`);
  }
  
  private getDefaultConfig(): ScheduleConfig {
    return {
      credentialing: '0 6 * * *',      // Daily at 6 AM
      claims: '0 * * * *',             // Every hour
      metrics: '0 */4 * * *',          // Every 4 hours
      fullPipeline: '0 2 * * *'        // Daily at 2 AM
    };
  }
  
  private scheduleJob(name: string, cronExpression: string, task: () => Promise<void>) {
    const job = cron.schedule(cronExpression, async () => {
      const startTime = Date.now();
      try {
        await task();
        const duration = (Date.now() - startTime) / 1000;
        
        await this.notifySuccess(name, duration);
      } catch (error) {
        await this.notifyError(name, error);
      }
    });
    
    this.jobs.set(name, job);
    job.start();
  }
  
  async runCredentialingSync() {
    const db = DatabaseManager.getInstance();
    await db.connect();
    
    try {
      // Only sync credentialing data
      const extractor = new (await import('../extractors/SmartsheetExtractor')).SmartsheetExtractor();
      const loader = new (await import('../loaders/MongoLoader')).MongoLoader();
      
      const credentialing = await extractor.extractCredentialing();
      await loader.loadCredentialingMatrix(credentialing, false);
      
      console.log(`✅ Synced ${credentialing.length} credentialing records`);
    } finally {
      await db.disconnect();
    }
  }
  
  async runClaimsSync() {
    const db = DatabaseManager.getInstance();
    await db.connect();
    
    try {
      // Sync only recent claims (last 24 hours)
      const extractor = new (await import('../extractors/OpenDentalExtractor')).OpenDentalExtractor();
      const loader = new (await import('../loaders/MongoLoader')).MongoLoader();
      
      await extractor.connectToActivityDB();
      const claims = await extractor.extractClaimsWithPayments();
      
      // Filter to recent claims only
      const recentClaims = claims.filter(c => {
        const claimDate = new Date(c.service_date);
        const dayAgo = new Date(Date.now() - 24 * 60 * 60 * 1000);
        return claimDate > dayAgo;
      });
      
      if (recentClaims.length > 0) {
        await loader.loadUnifiedClaims(recentClaims);
        console.log(`✅ Synced ${recentClaims.length} recent claims`);
      } else {
        console.log('No new claims to sync');
      }
    } finally {
      await db.disconnect();
    }
  }
  
  async runMetricsCalculation() {
    const db = DatabaseManager.getInstance();
    await db.connect();
    
    try {
      const calculator = new (await import('../transformers/CarrierMetricsCalculator')).CarrierMetricsCalculator();
      const loader = new (await import('../loaders/MongoLoader')).MongoLoader();
      
      // Get claims from database
      const UnifiedClaim = (await import('../models/UnifiedClaim')).UnifiedClaim;
      const claims = await UnifiedClaim.find({
        service_date: { $gte: new Date(Date.now() - 90 * 24 * 60 * 60 * 1000) }
      }).lean();
      
      // Recalculate metrics
      const metrics = calculator.calculateMetrics(claims);
      await loader.loadCarrierMetrics(metrics, true);
      
      console.log(`✅ Recalculated ${metrics.length} carrier metrics`);
    } finally {
      await db.disconnect();
    }
  }
  
  async runFullPipeline() {
    await this.pipeline.run({ clearExisting: true });
  }
  
  private async notifySuccess(jobName: string, duration: number) {
    const message = `✅ PDE Job "${jobName}" completed successfully in ${duration.toFixed(2)}s`;
    console.log(message);
    
    if (process.env.ENABLE_NOTIFICATIONS === 'true') {
      await this.slackNotifier.send(message, 'good');
    }
  }
  
  private async notifyError(jobName: string, error: any) {
    const message = `❌ PDE Job "${jobName}" failed: ${error.message}`;
    console.error(message);
    
    if (process.env.ENABLE_NOTIFICATIONS === 'true') {
      await this.slackNotifier.send(message, 'danger');
      await this.emailNotifier.sendAlert('PDE Pipeline Error', message);
    }
  }
  
  stopAll() {
    for (const [name, job] of this.jobs) {
      job.stop();
      console.log(`Stopped job: ${name}`);
    }
  }
}
```

## Step 2: Create Monitoring System

Create `src/monitoring/HealthMonitor.ts`:
```typescript
import { DatabaseManager } from '../database/DatabaseManager';
import { CarrierMetrics } from '../models/CarrierMetrics';
import { CredentialingMatrix } from '../models/CredentialingMatrix';
import { UnifiedClaim } from '../models/UnifiedClaim';

interface HealthStatus {
  status: 'healthy' | 'degraded' | 'unhealthy';
  checks: {
    database: boolean;
    dataFreshness: boolean;
    apiResponsive: boolean;
    diskSpace: boolean;
  };
  metrics: {
    lastClaimDate: Date | null;
    lastCredentialingUpdate: Date | null;
    claimCount24h: number;
    errorRate: number;
  };
  issues: string[];
}

export class HealthMonitor {
  private db: DatabaseManager;
  
  constructor() {
    this.db = DatabaseManager.getInstance();
  }
  
  async checkHealth(): Promise<HealthStatus> {
    const issues: string[] = [];
    const checks = {
      database: false,
      dataFreshness: false,
      apiResponsive: false,
      diskSpace: true // Assume OK unless checked
    };
    
    // Check database connection
    try {
      await this.db.connect();
      checks.database = true;
    } catch (error) {
      issues.push('Database connection failed');
    }
    
    // Check data freshness
    const metrics = await this.getMetrics();
    
    if (metrics.lastClaimDate) {
      const hoursSinceLastClaim = (Date.now() - metrics.lastClaimDate.getTime()) / (1000 * 60 * 60);
      if (hoursSinceLastClaim > 24) {
        issues.push(`No new claims in ${hoursSinceLastClaim.toFixed(1)} hours`);
      } else {
        checks.dataFreshness = true;
      }
    }
    
    // Check API (would ping actual endpoint)
    checks.apiResponsive = true; // Placeholder
    
    // Determine overall status
    let status: HealthStatus['status'] = 'healthy';
    if (issues.length > 2 || !checks.database) {
      status = 'unhealthy';
    } else if (issues.length > 0) {
      status = 'degraded';
    }
    
    return {
      status,
      checks,
      metrics,
      issues
    };
  }
  
  private async getMetrics() {
    try {
      const [lastClaim, lastCred, recentClaims] = await Promise.all([
        UnifiedClaim.findOne().sort({ created_at: -1 }).select('created_at'),
        CredentialingMatrix.findOne().sort({ last_updated: -1 }).select('last_updated'),
        UnifiedClaim.countDocuments({
          created_at: { $gte: new Date(Date.now() - 24 * 60 * 60 * 1000) }
        })
      ]);
      
      return {
        lastClaimDate: lastClaim?.created_at || null,
        lastCredentialingUpdate: lastCred?.last_updated || null,
        claimCount24h: recentClaims,
        errorRate: 0 // Would calculate from error logs
      };
    } catch (error) {
      return {
        lastClaimDate: null,
        lastCredentialingUpdate: null,
        claimCount24h: 0,
        errorRate: 0
      };
    }
  }
  
  async startMonitoring(intervalMinutes: number = 5) {
    console.log(`🔍 Starting health monitoring (every ${intervalMinutes} minutes)...`);
    
    setInterval(async () => {
      const health = await this.checkHealth();
      
      if (health.status === 'unhealthy') {
        console.error('⚠️  SYSTEM UNHEALTHY:', health.issues);
        // Send alerts
      } else if (health.status === 'degraded') {
        console.warn('⚠️  System degraded:', health.issues);
      }
      
      // Log metrics
      console.log(`Health Check: ${health.status.toUpperCase()}`);
      console.log(`  Claims (24h): ${health.metrics.claimCount24h}`);
      console.log(`  Last claim: ${health.metrics.lastClaimDate?.toISOString() || 'N/A'}`);
    }, intervalMinutes * 60 * 1000);
  }
}
```

## Step 3: Create Notification Utilities

Create `src/utils/SlackNotifier.ts`:
```typescript
export class SlackNotifier {
  private webhookUrl: string;
  
  constructor() {
    this.webhookUrl = process.env.SLACK_WEBHOOK_URL || '';
  }
  
  async send(message: string, color: 'good' | 'warning' | 'danger' = 'good') {
    if (!this.webhookUrl) {
      console.log('Slack webhook not configured');
      return;
    }
    
    try {
      const response = await fetch(this.webhookUrl, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          attachments: [{
            color,
            title: 'PDE Pipeline',
            text: message,
            footer: 'Platinum Data Engine',
            ts: Math.floor(Date.now() / 1000)
          }]
        })
      });
      
      if (!response.ok) {
        console.error('Failed to send Slack notification');
      }
    } catch (error) {
      console.error('Slack notification error:', error);
    }
  }
}
```

Create `src/utils/EmailNotifier.ts`:
```typescript
export class EmailNotifier {
  async sendAlert(subject: string, body: string) {
    // Placeholder - would integrate with email service
    console.log(`📧 Email Alert: ${subject}`);
    console.log(`   ${body}`);
  }
  
  async sendReport(reportData: any) {
    // Send daily report
    console.log('📊 Sending daily report...');
  }
}
```

## Step 4: Create Automated Service Runner

Create `src/automated-service.ts`:
```typescript
import { APIServer } from './api/server';
import { PipelineScheduler } from './scheduler/PipelineScheduler';
import { HealthMonitor } from './monitoring/HealthMonitor';
import dotenv from 'dotenv';

dotenv.config();

class AutomatedPDEService {
  private apiServer: APIServer;
  private scheduler: PipelineScheduler;
  private monitor: HealthMonitor;
  
  constructor() {
    this.apiServer = new APIServer();
    this.scheduler = new PipelineScheduler();
    this.monitor = new HealthMonitor();
  }
  
  async start() {
    console.log(`
╔══════════════════════════════════════════════════════╗
║                                                      ║
║     PLATINUM DATA ENGINE - AUTOMATED SERVICE        ║
║                                                      ║
║     Starting all components...                      ║
║                                                      ║
╚══════════════════════════════════════════════════════╝
    `);
    
    // Start API server
    await this.apiServer.start();
    
    // Initialize scheduled jobs
    this.scheduler.initializeSchedules();
    
    // Start health monitoring
    await this.monitor.startMonitoring(5);
    
    // Run initial pipeline
    if (process.env.RUN_ON_START === 'true') {
      console.log('Running initial pipeline...');
      await this.scheduler.runFullPipeline();
    }
    
    console.log(`
╔══════════════════════════════════════════════════════╗
║                                                      ║
║     ✅ ALL SYSTEMS OPERATIONAL                      ║
║                                                      ║
║     API: http://localhost:3001                      ║
║     Monitoring: Active                              ║
║     Schedules: Running                              ║
║                                                      ║
╚══════════════════════════════════════════════════════╝
    `);
  }
  
  async stop() {
    console.log('\nShutting down PDE Service...');
    this.scheduler.stopAll();
    await this.apiServer.stop();
    console.log('Shutdown complete');
  }
}

// Start the service
const service = new AutomatedPDEService();

service.start().catch(error => {
  console.error('Failed to start automated service:', error);
  process.exit(1);
});

// Graceful shutdown
process.on('SIGINT', async () => {
  await service.stop();
  process.exit(0);
});

process.on('SIGTERM', async () => {
  await service.stop();
  process.exit(0);
});
```

## Step 5: Create Docker Configuration

Create `Dockerfile`:
```dockerfile
FROM node:18-alpine

WORKDIR /app

# Install Python for bridge scripts
RUN apk add --no-cache python3 py3-pip

# Copy package files
COPY package*.json ./
RUN npm ci --only=production

# Copy application
COPY . .

# Build TypeScript
RUN npm run build

# Expose API port
EXPOSE 3001

# Start automated service
CMD ["node", "dist/automated-service.js"]
```

Create `docker-compose.yml`:
```yaml
version: '3.8'

services:
  pde:
    build: .
    container_name: platinum-data-engine
    environment:
      - NODE_ENV=production
      - MONGO_URI=mongodb://mongo:27017
      - DB_NAME=platinum_unified
      - ACTIVITY_DB=activity
      - PORT=3001
      - RUN_ON_START=true
      - ENABLE_NOTIFICATIONS=true
    ports:
      - "3001:3001"
    depends_on:
      - mongo
    restart: unless-stopped
    volumes:
      - ./logs:/app/logs
      - ./output:/app/output
    
  mongo:
    image: mongo:6
    container_name: pde-mongodb
    volumes:
      - mongo_data:/data/db
    ports:
      - "27017:27017"
    restart: unless-stopped

volumes:
  mongo_data:
```

## Update package.json Scripts
```json
{
  "scripts": {
    "dev": "nodemon src/index.ts",
    "api": "nodemon src/start-api.ts",
    "service": "nodemon src/automated-service.ts",
    "pipeline": "ts-node src/index.ts",
    "build": "tsc",
    "start": "node dist/automated-service.js",
    "docker:build": "docker-compose build",
    "docker:up": "docker-compose up -d",
    "docker:down": "docker-compose down",
    "docker:logs": "docker-compose logs -f pde"
  }
}
```

## Validation

1. **Test Automated Service Locally:**
```bash
npm run service
```

2. **Deploy with Docker:**
```bash
npm run docker:build
npm run docker:up
npm run docker:logs
```

3. **Verify Schedules:**
Check logs for:
- ✅ "All schedules initialized"
- ✅ "Health Check: HEALTHY"
- ✅ Periodic job executions

4. **Test API Still Works:**
```bash
curl http://localhost:3001/api/health
curl http://localhost:3001/api/fee-strategy/pivot
```

## Production Deployment Checklist
- [ ] Set environment variables
- [ ] Configure Slack webhook
- [ ] Set appropriate cron schedules
- [ ] Enable monitoring alerts
- [ ] Configure log rotation
- [ ] Set up backup strategy
- [ ] Document runbooks
