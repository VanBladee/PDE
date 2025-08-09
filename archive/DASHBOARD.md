# Carrier Network Dashboard

A luxurious dark-themed web interface for managing healthcare provider network statuses across multiple insurance carriers.

## Overview

The dashboard provides a centralized interface to:
- View all providers and their carrier network statuses
- Edit carrier statuses in real-time (changes save directly to MongoDB)
- Trigger extraction and sync processes with visual feedback
- Filter providers by state, location, and match status

## Features

### 🎨 Dark Theme Interface
- Deep black background (#0a0a0a) for reduced eye strain
- Cyan accent colors for primary actions
- Color-coded status indicators:
  - ✅ Green = In-Network (x)
  - ❌ Red = Out-of-Network (n)
  - ⚡ Yellow = Honor Fees (f)
  - ⬜ Gray = No status

### 🚀 Process Control
- **EXTRACT Button**: Triggers Smartsheet data extraction
- **SYNC Button**: Syncs extracted data to MongoDB
- Real-time status display showing if processes are running
- Timestamp tracking for last extract/sync operations

### 📊 Provider Management
- Displays providers from both collections:
  - `crucible.providerNetwork` - Matched providers
  - `crucible.smartsheetProviders` - Unmatched providers
- Shows match confidence scores and locations
- Editable dropdown for each carrier status
- Instant save to MongoDB on change

### 🔍 Filtering
- Filter by state (Nevada, Utah, Arizona, Colorado)
- Filter by location (dynamically populated)
- Filter by match status (Matched/Smartsheet Only)
- **Refresh Carriers** button to sync with MongoDB carriersRegistry

## Installation

### Prerequisites
- Python 3.8+ with Flask
- MongoDB connection
- Configured `.env` file with `MONGO_URI`

### Setup
```bash
# Install dependencies
npm run dashboard:install

# Or manually
cd dashboard
pip install -r requirements.txt
```

## Running the Dashboard

### Option 1: NPM Script
```bash
npm run dashboard
```

### Option 2: Startup Script
```bash
cd dashboard
./start.sh
```

### Option 3: Direct Python
```bash
cd dashboard
/opt/anaconda3/bin/python3 app.py
```

Access at: http://localhost:5000

## Architecture

### Technology Stack
- **Backend**: Flask (Python)
- **Frontend**: HTMX + Alpine.js
- **Styling**: Tailwind CSS (via CDN)
- **Database**: MongoDB (pymongo)

### Key Components

#### `app.py`
Main Flask application with routes:
- `/` - Main dashboard page
- `/extract` - Trigger extraction process
- `/sync` - Trigger sync process
- `/status` - Get process status (polled every 5s)
- `/providers` - Get provider table data
- `/update/<id>/<carrier>` - Update carrier status
- `/locations` - Get location list for filters

#### `templates/index.html`
Main dashboard layout with:
- Action buttons and status display
- Filters with Alpine.js state management
- HTMX-powered provider table container

#### `templates/provider_table.html`
Dynamic table component:
- Renders provider rows with editable statuses
- HTMX updates on dropdown change
- Visual feedback for save operations
- Pagination controls

### Data Flow

1. **Page Load**
   - HTMX loads provider table
   - Alpine.js fetches location list
   - Status endpoint polled every 5 seconds

2. **Editing Status**
   - User changes dropdown
   - HTMX sends POST to `/update`
   - MongoDB updated directly
   - Visual feedback (green/red flash)

3. **Extract/Sync**
   - Button triggers subprocess
   - Status updates in real-time
   - Table can be refreshed to see new data

## Carrier Management

### Dynamic Carrier Loading
The dashboard always prioritizes carriers from MongoDB `carriersRegistry`:
1. Loads all carriers from `crucible.carriersRegistry` on page load
2. Caches carrier data for 60 seconds to reduce DB calls
3. Falls back to JSON files only if MongoDB is unavailable
4. Provides "Refresh Carriers" button to force reload

### Carrier Registry Integration
- When MongoDB carriersRegistry is updated, the dashboard automatically reflects changes
- Carrier IDs are used internally for storage consistency
- Carrier names are displayed in the UI for readability
- Updates preserve the carrier-to-ID mapping

## MongoDB Schema

### Collections Used

#### `crucible.providerNetwork`
Matched providers with schema:
```javascript
{
  _id: ObjectId,
  providerName: String,
  state: String,
  metadata: {
    smartsheetLocation: String,
    confidence: Number
  },
  carrierStatuses: {
    carrierId: {
      status: 'in_network|out_of_network|honor_fees',
      lastUpdated: Date
    }
  }
}
```

#### `crucible.smartsheetProviders`
Unmatched providers (same schema)

#### `crucible.carriersRegistry`
Carrier definitions:
```javascript
{
  _id: ObjectId,
  name: String,
  code: String
}
```

## Troubleshooting

### Dashboard shows no carriers
- Check if `crucible.carriersRegistry` has data
- Fallback uses default carrier list
- Check browser console for errors

### MongoDB connection fails
- Verify `MONGO_URI` in `.env`
- Check network connectivity
- Dashboard will show data from JSON files as fallback

### Changes not saving
- Check browser network tab for errors
- Verify MongoDB write permissions
- Check Flask logs for detailed errors

### Process buttons not working
- Ensure Python scripts exist in `src/`
- Check file permissions
- View Flask console for subprocess errors

## Development

### Adding New Features

1. **New Filter**
   - Add to Alpine.js state in `index.html`
   - Include in HTMX request with `hx-include`
   - Handle in `get_providers()` query

2. **New Status Code**
   - Add option to dropdown in `provider_table.html`
   - Add color class in CSS
   - Update status mapping in `update_provider()`

3. **New Process Button**
   - Add button in `index.html`
   - Create route in `app.py`
   - Use `subprocess.Popen()` for async execution

### Debugging
- Enable Flask debug mode (already on)
- Check `logs/carrier_sync.log` for extraction/sync logs
- Use browser DevTools for HTMX requests
- MongoDB Compass to verify data changes

## Security Considerations

- No authentication (add if deploying publicly)
- Direct MongoDB access (consider API layer for production)
- Subprocess execution (validate all inputs)
- CORS not configured (add for remote access)

## Future Enhancements

- WebSocket for real-time extraction progress
- Bulk edit mode for multiple cells
- Export to CSV functionality
- Audit trail for all changes
- User authentication and roles
- Keyboard navigation improvements
- Undo/redo functionality