# Production System Guide: Enhanced Carrier Network Extraction

## Overview

This guide documents the production-ready carrier network extraction system with continuous improvement capabilities. The system automatically extracts provider data from Smartsheet, validates it, deduplicates providers, and outputs to carrier-specific JSON files with accuracy tracking.

## Key Enhancements

### 1. **Robust Extraction** (`src/core/extraction/`)
- **Retry Logic**: Automatic retry with exponential backoff for network failures
- **Screenshot Capture**: Captures screenshots on failures for debugging
- **Health Checks**: Validates responses before processing
- **Checkpoint System**: Can resume failed extractions

### 2. **Data Validation** (`src/core/extraction/validators.py`)
- **Pydantic Models**: Type-safe data validation
- **Business Rules**: Validates percentages, location formats, carrier statuses
- **Comprehensive Checks**: Ensures data consistency and completeness

### 3. **Smart Deduplication** (`src/core/matching/provider_dedup.py`)
- **Fuzzy Matching**: Uses existing provider_matcher.py for intelligent matching
- **NPI Support**: Uses NPI as primary identifier when available
- **Learning System**: Learns from user feedback on matches
- **Name Normalization**: Handles titles, credentials, and variations

### 4. **Continuous Improvement** (`src/continuous_improvement_service.py`)
- **Scheduled Extractions**: Runs automatically at configured times
- **Accuracy Tracking**: Monitors data quality over time
- **Auto-Improvements**: Applies fixes based on quality metrics
- **Carrier-Specific Output**: Updates files in `/Users/rainceo/OpenDental_Conekt/carrier_credentialing`

### 5. **Monitoring Dashboard** (`src/api/monitoring_api.py`)
- **Real-time Metrics**: View extraction status and quality scores
- **Trend Analysis**: Track improvements over time
- **Manual Triggers**: Trigger extractions on-demand
- **Recommendations**: Get actionable improvement suggestions

## Quick Start

### 1. Install Dependencies
```bash
npm run install:prod
```

### 2. Configure Environment
Ensure your `.env` file contains:
```env
MONGO_URI=mongodb://...
NEVADA_CREDENTIALING=https://...
UTAH_CREDENTIALING=https://...
ARIZONA_CREDENTIALING=https://...
COLORADO_CREDENTIALING=https://...
```

### 3. Run Continuous Service
```bash
npm run continuous
```

This will:
- Run initial extraction for all states
- Schedule daily extractions at 2 AM and 2 PM
- Monitor quality every 6 hours
- Update carrier files in `/Users/rainceo/OpenDental_Conekt/carrier_credentialing`

### 4. Monitor Progress
In a separate terminal:
```bash
npm run monitor
```

Then open http://localhost:8001 to view the monitoring dashboard.

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                   Continuous Improvement Service             │
│  ┌─────────────┐  ┌──────────────┐  ┌──────────────────┐  │
│  │  Scheduler  │  │  Extractor   │  │  Quality Monitor │  │
│  └─────────────┘  └──────────────┘  └──────────────────┘  │
└─────────────────────────────────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────┐
│                      Data Pipeline                           │
│  ┌──────────┐  ┌────────────┐  ┌─────────────┐            │
│  │ Validate │→ │ Deduplicate │→ │   Output    │            │
│  └──────────┘  └────────────┘  └─────────────┘            │
└─────────────────────────────────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────┐
│              Carrier-Specific JSON Files                     │
│  /Users/rainceo/OpenDental_Conekt/carrier_credentialing/   │
│  ├── aetna_carrier_credentialing.json                      │
│  ├── bcbs_regence_carrier_credentialing.json               │
│  ├── cigna_carrier_credentialing.json                      │
│  └── ...                                                    │
└─────────────────────────────────────────────────────────────┘
```

## Data Quality Metrics

The system tracks four key quality metrics:

1. **Completeness** (0-100%): Are all required fields present?
2. **Consistency** (0-100%): How similar is data between extractions?
3. **Validity** (0-100%): Are status codes and formats correct?
4. **Change Rate** (0-100%): Is the data stable or volatile?

Overall quality score = Average of all metrics

## Carrier File Format

Each carrier JSON file contains:

```json
{
  "carrier_name": "Aetna",
  "last_extraction": "2024-08-05T10:30:00Z",
  "total_providers": 150,
  "accuracy_metrics": {
    "overall": 0.92,
    "completeness": 0.95,
    "consistency": 0.88,
    "validity": 0.98,
    "change_rate": 0.87
  },
  "providers": [
    {
      "provider_name": "John Smith DDS",
      "locations": [
        {
          "name": "PROVO 86-3448732",
          "status": "x",
          "is_dormant": false,
          "last_updated": "2024-08-05T10:30:00Z"
        }
      ],
      "status": "x",
      "last_updated": "2024-08-05T10:30:00Z",
      "confidence_score": 95.0,
      "data_sources": ["smartsheet"],
      "validation_notes": []
    }
  ]
}
```

## Configuration

Edit `config/continuous_improvement.json`:

```json
{
  "extraction_schedule": {
    "daily": ["02:00", "14:00"],  // Times to run daily
    "weekly_full": "sunday"        // Day for weekly full extraction
  },
  "quality_thresholds": {
    "min_accuracy": 0.85,         // Minimum acceptable accuracy
    "min_completeness": 0.90,     // Minimum data completeness
    "max_change_rate": 0.15       // Maximum acceptable volatility
  }
}
```

## Monitoring Endpoints

- `GET /` - Web dashboard
- `GET /api/health` - System health metrics
- `GET /api/extraction-status` - Status by state
- `GET /api/carrier-quality` - Quality scores by carrier
- `GET /api/recent-improvements` - Recent system improvements
- `POST /api/trigger-extraction` - Manually trigger extraction

## Troubleshooting

### Common Issues

1. **Low Quality Scores**
   - Check extraction logs in `logs/carrier_sync.log`
   - Review screenshots in `screenshots/` directory
   - Verify Smartsheet URLs are still valid

2. **Missing Providers**
   - Check deduplication threshold in config
   - Review duplicate_map in extraction results
   - Verify location parsing is working correctly

3. **Extraction Failures**
   - Check network connectivity
   - Verify Playwright browser can launch
   - Review error screenshots for clues

### Debug Mode

Run with verbose logging:
```bash
LOG_LEVEL=DEBUG npm run continuous
```

### Manual Extraction

Run extraction for specific state:
```python
from src.continuous_improvement_service import ContinuousImprovementService
service = ContinuousImprovementService()
await service.run_extraction_cycle(['nevada'])
```

## Best Practices

1. **Monitor Quality Trends**: Check dashboard daily for declining quality
2. **Review Improvements**: Validate automated improvements weekly
3. **Update Carrier List**: Add new carriers to config as needed
4. **Backup Data**: Regular backups of carrier JSON files
5. **Test Changes**: Use test mode before deploying extraction changes

## Next Steps

1. **Set up Airflow** for more sophisticated scheduling
2. **Add Redis caching** for improved performance
3. **Implement API authentication** for production security
4. **Create data lake** for historical analysis
5. **Build ML models** for better deduplication

## Support

- Logs: `logs/carrier_sync.log`
- Screenshots: `screenshots/`
- Extraction results: `extraction_results/`
- Accuracy history: `/Users/rainceo/OpenDental_Conekt/carrier_credentialing/.accuracy_history/`

The system is designed to be self-improving. As it runs, it will learn from patterns, improve deduplication, and maintain high data quality automatically.