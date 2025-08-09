# Claude Code Prompt - Phase 1: PDE Setup & Consolidation

Create a new Node.js/TypeScript project called "PDE" (Platinum Data Engine) at `/Users/rainceo/Desktop/mac/Projects/PDE` that consolidates data extraction logic from multiple existing projects.

## Step 1: Initialize Project Structure

```bash
cd /Users/rainceo/Desktop/mac/Projects
mkdir PDE && cd PDE

# Create complete directory structure
mkdir -p src/extractors/{smartsheet,opendental,fees}
mkdir -p src/transformers src/loaders src/api src/utils
mkdir -p config models scripts tests archive .claudecode
mkdir -p logs output temp

# Initialize Node.js project with TypeScript
npm init -y
npm install typescript @types/node ts-node nodemon
npm install express mongoose dotenv node-cron
npm install @types/express @types/mongoose --save-dev
```

## Step 2: Copy Existing Working Code

```bash
# SMARTSHEET COMPONENTS (Python)
cp /Users/rainceo/Desktop/mac/Projects/carrier-network-scraper/src/core/extraction/smartsheet_extractor.py src/extractors/smartsheet/
cp -r /Users/rainceo/Desktop/mac/Projects/carrier-network-scraper/config/* config/smartsheet/
cp /Users/rainceo/Desktop/mac/Projects/carrier-network-scraper/insert_to_pdc_status.py scripts/
cp /Users/rainceo/Desktop/mac/Projects/carrier-network-scraper/requirements.txt requirements-python.txt

# OPENDENTAL COMPONENTS (Python)
cp -r /Users/rainceo/Desktop/mac/Projects/main-app/backend/services/integrations/opendental/* src/extractors/opendental/
cp /Users/rainceo/Desktop/mac/Projects/main-app/backend/services/integrations/opendental/claims_od_connector/claimsOpenDental.py src/extractors/opendental/claims_extractor.py
cp /Users/rainceo/Desktop/mac/Projects/main-app/backend/services/integrations/opendental/fee_schedules_od_connector/feeSchedOpenDental.py src/extractors/fees/fee_extractor.py

# OVERVIEW COMPONENTS (TypeScript)
cp /Users/rainceo/Desktop/mac/Projects/overview/Admin-Cockpit-Backend/src/config/databases.ts config/databases.ts
cp -r /Users/rainceo/Desktop/mac/Projects/overview/Admin-Cockpit-Backend/src/models/* models/

# DOCUMENTATION
cp /Users/rainceo/Desktop/mac/Projects/carrier-network-scraper/*.md archive/
cp /Users/rainceo/Desktop/mac/Projects/overview/*.md archive/
```

## Step 3: Create TypeScript Configuration

Create `tsconfig.json`:
```json
{
  "compilerOptions": {
    "target": "ES2020",
    "module": "commonjs",
    "lib": ["ES2020"],
    "outDir": "./dist",
    "rootDir": "./src",
    "strict": true,
    "esModuleInterop": true,
    "skipLibCheck": true,
    "forceConsistentCasingInFileNames": true,
    "resolveJsonModule": true,
    "moduleResolution": "node"
  },
  "include": ["src/**/*"],
  "exclude": ["node_modules", "dist"]
}
```

## Step 4: Create Python-Node Bridge

Since we have Python extractors, create `src/utils/python-bridge.ts`:
```typescript
import { spawn } from 'child_process';
import path from 'path';

export class PythonBridge {
  static async execute(scriptPath: string, args: any[] = []): Promise<any> {
    return new Promise((resolve, reject) => {
      const pythonProcess = spawn('python3', [scriptPath, ...args]);
      let result = '';
      let error = '';

      pythonProcess.stdout.on('data', (data) => {
        result += data.toString();
      });

      pythonProcess.stderr.on('data', (data) => {
        error += data.toString();
      });

      pythonProcess.on('close', (code) => {
        if (code !== 0) {
          reject(new Error(error));
        } else {
          try {
            resolve(JSON.parse(result));
          } catch {
            resolve(result);
          }
        }
      });
    });
  }
}
```

## Step 5: Create Environment Configuration

Create `.env`:
```env
# MongoDB
MONGO_URI=mongodb://localhost:27017
DB_NAME=platinum_unified
ACTIVITY_DB=activity
CRUCIBLE_DB=crucible
OD_LIVE_DB=od_live

# Smartsheet
SMARTSHEET_TOKEN=your_token_here
SMARTSHEET_SHEET_ID=7849506498725508

# OpenDental
OD_API_URL=https://api.opendental.com
OD_API_KEY=your_key_here

# Server
PORT=3001
NODE_ENV=development
```

## Step 6: Create Master Context Document

Create `.claudecode/context.md`:
```markdown
# PDE Context

## Data Flow
1. **Extract**: Smartsheet (credentialing) + OpenDental (claims/payments)
2. **Transform**: Calculate write-offs, join claims with payments, aggregate metrics
3. **Load**: Store in platinum_unified MongoDB database
4. **Serve**: REST API for Admin Cockpit dashboard

## Key Collections
- credentialing_matrix: 10,035 provider/carrier/location records
- unified_claims: Merged Jobs + ProcessedClaims
- carrier_metrics: Pre-calculated for dashboard performance
- fee_schedules: Contracted rates by carrier

## Critical Metrics
- Write-off % WITH patient volume
- Revenue per patient by carrier
- Provider credentialing gaps
```

## Expected Output
- Working project structure with all files copied
- Python-Node bridge for existing extractors
- Environment configuration ready
- All dependencies installed

## Validation
Run these commands to verify:
```bash
npm run dev  # Should start without errors
ls -la src/extractors/smartsheet/  # Should show Python files
ls -la src/extractors/opendental/  # Should show OpenDental integration
```
