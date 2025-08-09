# Comprehensive Guide to the Credentialing System

## Overview

This guide explains how the credentialing system works across two interconnected projects:
1. **carrier-network-scraper** - Extracts data from Smartsheet and populates MongoDB
2. **Admin-Cockpit** - Displays the data in a UI for management

## Data Flow Architecture

```
Smartsheet URLs (4 states) 
    ↓
[carrier-network-scraper]
    ├── Playwright Browser Automation
    ├── JavaScript Response Interception
    ├── Data Extraction & Validation
    └── Provider Matching & Deduplication
    ↓
MongoDB (crucible database)
    ├── PDC_providers (Provider master records)
    ├── PDC_locations (Provider-location pairs)
    └── PDC_providerStatus (Carrier status by provider-location)
    ↓
[Admin-Cockpit UI]
    └── Credentialing Dashboard
```

## Understanding the Data Model

### Key Insight: Provider-Location-Carrier Relationships

The system tracks a **many-to-many-to-many relationship**:
- **Providers** work at multiple **Locations**
- Each **Provider-Location** pair has multiple **Carrier Statuses**
- Carrier statuses can vary by location for the same provider

### The Truth About Location Counts

After thorough investigation across all data sources:

**Actual Physical Locations**: **39 unique locations** across 4 states (as of August 8, 2025)
- Nevada: 4 locations
- Utah: 25 locations
- Arizona: 5 locations
- Colorado: 5 locations

**Current MongoDB State**:
- Only **14 locations** loaded (incomplete migration)
- **87 provider-location assignments** (multiple providers per location)
- Missing Arizona and Colorado entirely

**Why the Confusion?**
1. **Bad metadata**: Archive file claims 53 but only contains 41
2. **Incomplete extraction**: V1 only found 33 locations
3. **Provider assignments mistaken for locations**: 87 assignments ≠ 87 locations
4. **Incomplete MongoDB migration**: Only 14 of 41 locations loaded

**The "53" is incorrect** - it's a documentation error. Fresh extraction on August 8, 2025 shows exactly 39 locations.

### MongoDB Collections Structure

#### 1. PDC_providers (Master Provider Registry)
```javascript
{
  _id: ObjectId("..."),
  Provider_Name: "John Smith DDS",
  NPI: "1234567890",        // Optional
  Credentials: ["DDS"],     // Optional
  Primary_State: "utah"
}
```

#### 2. PDC_locations (Provider-Location Assignments)
```javascript
{
  _id: ObjectId("..."),
  Provider_ID: ObjectId("..."),  // Links to PDC_providers
  Provider_Name: "John Smith DDS",
  Location_Name: "TOOELE",
  Tax_ID: "87-3100597",
  State: "utah",
  Is_Dormant: false,
  Percentage: "100%"
}
```

#### 3. PDC_providerStatus (Carrier Status by Location)
```javascript
{
  _id: ObjectId("..."),
  Provider_ID: ObjectId("..."),
  Location_ID: ObjectId("..."),  // Links to PDC_locations
  Carrier_Name: "Aetna",
  Status: "x",  // x=in-network, n=out-of-network, f=honor-fees
  Last_Updated: ISODate("2024-08-05")
}
```

## Legacy Collections (Being Phased Out)

The system also has legacy collections from earlier implementations:
- `crucible.providerNetwork` - Matched providers (old schema)
- `crucible.smartsheetProviders` - Unmatched providers (old schema)
- `crucible.carriersRegistry` - Carrier definitions

## Data Extraction Process

### 1. Smartsheet Structure
Each Smartsheet contains:
- **Location Headers**: "BOUNTIFUL 84-4192377" (Name + Tax ID)
- **Provider Rows**: Name, percentage, hire date, carrier statuses
- **Dormant Section**: Providers marked as inactive

### 2. Extraction Logic
```python
# From sync-credentialing-data.py
for location in smartsheet:
    for provider in location.providers:
        # Create/update provider record
        # Create provider-location assignment
        # Record carrier statuses for this location
```

### 3. Key Challenges
- **Same provider, different locations**: Must track separately
- **Same provider, different statuses**: Status varies by location
- **Deduplication**: Fuzzy matching to identify same provider

## Displaying in the UI

### Accurate Representation Guidelines

1. **Location Count Display**
   ```javascript
   // Wrong
   "Total Locations: 229"
   
   // Correct
   "Physical Locations: 34"
   "Provider Assignments: 229"
   ```

2. **Provider View**
   - Show provider once with expandable locations
   - Display carrier status per location
   - Indicate if status varies by location

3. **Location View**
   - Group providers by physical location (Tax ID)
   - Show all providers at that location
   - Display aggregate statistics

### Example UI Structure
```
Provider: John Smith DDS
├── TOOELE (87-3100597)
│   ├── Aetna: ✓ (in-network)
│   └── BCBS: ✗ (out-of-network)
└── PROVO (86-3448732)
    ├── Aetna: ✓ (in-network)
    └── BCBS: ✓ (in-network)  ← Different status!
```

## Common Queries

### 1. Get Unique Physical Locations
```javascript
db.PDC_locations.aggregate([
  { $group: { 
    _id: "$Tax_ID",
    location_name: { $first: "$Location_Name" },
    state: { $first: "$State" },
    provider_count: { $sum: 1 }
  }}
])
```

### 2. Find Providers with Multiple Locations
```javascript
db.PDC_locations.aggregate([
  { $group: {
    _id: "$Provider_ID",
    locations: { $addToSet: "$Location_Name" },
    count: { $sum: 1 }
  }},
  { $match: { count: { $gt: 1 } } }
])
```

### 3. Find Status Variations by Location
```javascript
// Providers whose carrier status varies by location
db.PDC_providerStatus.aggregate([
  { $group: {
    _id: { 
      provider: "$Provider_ID",
      carrier: "$Carrier_Name"
    },
    statuses: { $addToSet: "$Status" }
  }},
  { $match: { "statuses.1": { $exists: true } } }
])
```

## Best Practices for the Credentialing Page

1. **Always distinguish between**:
   - Physical locations (unique Tax IDs)
   - Provider-location assignments
   - Total provider count (unique providers)

2. **Handle multi-location providers**:
   - Don't duplicate provider entries
   - Show location-specific statuses
   - Highlight status variations

3. **Performance considerations**:
   - Use aggregation pipelines for counts
   - Index on Tax_ID for location grouping
   - Cache unique location counts

4. **Data integrity**:
   - Validate Tax ID format (XX-XXXXXXX)
   - Ensure provider-location uniqueness
   - Track last update timestamps

## Summary

The credentialing system is designed to handle complex healthcare provider network relationships where:
- Providers work at multiple locations
- Carrier network status varies by location
- Data must be extracted, deduplicated, and displayed accurately

Understanding these relationships is crucial for:
- Accurate data representation in the UI
- Proper aggregation and counting
- Meaningful reporting and analytics