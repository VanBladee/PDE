# Provider-Location-Carrier Data Architecture Plan

## Executive Summary

Our analysis reveals critical insights about the provider network data structure:

1. **Providers work at multiple locations** (e.g., Robert Swenson works at 15 locations in Utah)
2. **Carrier statuses vary by location** for the same provider (206+ instances found)
3. **Current extraction is incomplete** (Nevada: 1/10 providers, Arizona: 4/11 providers)

This plan outlines a comprehensive solution to properly capture and store provider-location-carrier relationships in MongoDB for efficient querying and accurate representation of the network.

## Current State Analysis

### Extraction Accuracy Issues

| State    | Manual Count | Extracted | Missing | Notes |
|----------|--------------|-----------|---------|-------|
| Nevada   | 10           | 1         | 9       | Only extracting SUMMERLIN location |
| Utah     | 66           | 77        | -11     | Over-counting due to location duplicates |
| Arizona  | 11           | 4         | 7       | Missing multiple locations |
| Colorado | 16           | 22        | -6      | Over-counting due to location duplicates |

### Key Findings

1. **Multi-Location Providers**: 
   - Utah: 43/77 providers work at multiple locations
   - Colorado: 19/22 providers work at multiple locations
   
2. **Carrier Status Variations**:
   - 206+ instances where provider carrier status differs by location
   - Example: Juan Diaz de Leon has DMBA status 'n' at PROVO but 'f' at SOUTH JORDAN

3. **Location Distribution**:
   - Utah: 24 unique locations
   - Colorado: 5 unique locations
   - Arizona: 3 unique locations
   - Nevada: 1 location (extraction issue)

## Proposed MongoDB Schema

### Collections Structure

#### 1. `providers` Collection (Master Provider Registry)
```javascript
{
  "_id": ObjectId("..."),
  "provider_name": "Robert Swenson",
  "npi": "1234567890", // If available
  "credentials": ["DDS", "DMD"], // If available
  "primary_state": "utah",
  "created_at": ISODate("2024-01-01"),
  "updated_at": ISODate("2024-01-01")
}
```

#### 2. `provider_locations` Collection (Provider-Location Relationships)
```javascript
{
  "_id": ObjectId("..."),
  "provider_id": ObjectId("..."), // Reference to providers collection
  "provider_name": "Robert Swenson", // Denormalized for query performance
  "location": {
    "name": "PROVO",
    "id": "86-3448732",
    "full_name": "PROVO 86-3448732",
    "state": "utah",
    "region": "central", // Optional grouping
    "is_active": true
  },
  "employment_details": {
    "percentage": "100%",
    "hire_date": ISODate("2023-01-01"), // If available
    "status": "active",
    "is_dormant": false
  },
  "metadata": {
    "smartsheet_location": "PROVO",
    "smartsheet_location_id": "86-3448732",
    "extraction_date": ISODate("2024-01-01"),
    "source_url": "https://..."
  }
}
```

#### 3. `provider_carrier_statuses` Collection (Location-Specific Carrier Statuses)
```javascript
{
  "_id": ObjectId("..."),
  "provider_location_id": ObjectId("..."), // Reference to provider_locations
  "provider_id": ObjectId("..."), // Reference to providers
  "provider_name": "Robert Swenson", // Denormalized
  "location_full": "PROVO 86-3448732", // Denormalized
  "state": "utah",
  "carrier_id": ObjectId("..."), // Reference to carriersRegistry
  "carrier_name": "Aetna", // Denormalized
  "status": {
    "code": "x", // x, n, f, p, s, o
    "description": "in_network", // Human readable
    "effective_date": ISODate("2024-01-01"),
    "submission_date": ISODate("2024-01-01")
  },
  "history": [ // Track status changes
    {
      "code": "p",
      "description": "processing",
      "changed_at": ISODate("2023-12-01"),
      "changed_from": null
    }
  ],
  "last_updated": ISODate("2024-01-01"),
  "extraction_date": ISODate("2024-01-01")
}
```

#### 4. `locations` Collection (Master Location Registry)
```javascript
{
  "_id": ObjectId("..."),
  "name": "PROVO",
  "location_id": "86-3448732",
  "full_name": "PROVO 86-3448732",
  "state": "utah",
  "type": "office", // office, clinic, hospital
  "address": { // If available
    "street": "123 Main St",
    "city": "Provo",
    "state": "UT",
    "zip": "84601"
  },
  "active_providers": 7,
  "dormant_providers": 2,
  "total_providers": 9,
  "last_updated": ISODate("2024-01-01")
}
```

### Indexes for Optimal Query Performance

```javascript
// providers collection
db.providers.createIndex({ "provider_name": 1 })
db.providers.createIndex({ "npi": 1 })
db.providers.createIndex({ "primary_state": 1 })

// provider_locations collection
db.provider_locations.createIndex({ "provider_id": 1 })
db.provider_locations.createIndex({ "location.state": 1, "location.name": 1 })
db.provider_locations.createIndex({ "provider_name": 1, "location.state": 1 })
db.provider_locations.createIndex({ "employment_details.is_dormant": 1 })

// provider_carrier_statuses collection
db.provider_carrier_statuses.createIndex({ "provider_id": 1, "location_full": 1 })
db.provider_carrier_statuses.createIndex({ "carrier_id": 1, "status.code": 1 })
db.provider_carrier_statuses.createIndex({ "state": 1, "carrier_name": 1, "status.code": 1 })
db.provider_carrier_statuses.createIndex({ "provider_location_id": 1, "carrier_id": 1 })

// locations collection
db.locations.createIndex({ "state": 1, "name": 1 })
db.locations.createIndex({ "location_id": 1 })
```

## Implementation Plan

### Phase 1: Fix Extraction Logic (Immediate)

1. **Update sync-credentialing-data.py** to properly parse location headers:
   - Recognize patterns like "FLAMINGO RD 33-4895660"
   - Track current location context throughout parsing
   - Don't skip location header rows

2. **Implement location-aware provider extraction**:
   - Maintain state for current location
   - Reset state on "Dormant Providers" delimiter
   - Handle providers appearing after location headers

3. **Validation**: Ensure extraction matches manual counts

### Phase 2: Data Transformation Pipeline

1. **Create transformation script** (`transform_provider_data.py`):
   ```python
   # Pseudo-code structure
   def transform_extraction_to_schema(raw_data):
       providers = extract_unique_providers(raw_data)
       provider_locations = build_provider_location_relationships(raw_data)
       carrier_statuses = extract_location_specific_statuses(raw_data)
       locations = extract_unique_locations(raw_data)
       return providers, provider_locations, carrier_statuses, locations
   ```

2. **Handle data normalization**:
   - Deduplicate provider names
   - Standardize location formats
   - Map carrier names to carrier IDs from carriersRegistry

### Phase 3: MongoDB Migration

1. **Create migration script** (`migrate_to_new_schema.py`):
   - Drop existing collections (backup first)
   - Create new collections with proper structure
   - Insert transformed data
   - Create indexes

2. **Data validation**:
   - Verify all providers are captured
   - Confirm location relationships
   - Validate carrier status variations

### Phase 4: Query Interface Development

1. **Create query utilities** for common use cases:
   ```python
   # Get all locations for a provider
   def get_provider_locations(provider_name)
   
   # Get carrier status for provider at specific location
   def get_provider_carrier_status(provider_name, location, carrier)
   
   # Get all providers at a location
   def get_location_providers(location_name, state)
   
   # Find providers with different statuses across locations
   def find_status_variations(carrier_name)
   ```

2. **Dashboard updates**:
   - Add location selector
   - Show provider's status per location
   - Highlight status variations

## Example Queries

### 1. Find all locations where a provider works
```javascript
db.provider_locations.find({
  "provider_name": "Robert Swenson",
  "employment_details.is_dormant": false
})
```

### 2. Get carrier status for provider at specific location
```javascript
db.provider_carrier_statuses.findOne({
  "provider_name": "Robert Swenson",
  "location_full": "PROVO 86-3448732",
  "carrier_name": "Aetna"
})
```

### 3. Find providers with varying statuses across locations
```javascript
db.provider_carrier_statuses.aggregate([
  {
    $group: {
      _id: {
        provider: "$provider_name",
        carrier: "$carrier_name"
      },
      statuses: { $addToSet: "$status.code" },
      locations: { $push: "$location_full" }
    }
  },
  {
    $match: {
      $expr: { $gt: [{ $size: "$statuses" }, 1] }
    }
  }
])
```

### 4. Get network coverage statistics by location
```javascript
db.provider_carrier_statuses.aggregate([
  {
    $match: { 
      "location_full": "PROVO 86-3448732",
      "carrier_name": "Aetna"
    }
  },
  {
    $group: {
      _id: "$status.code",
      count: { $sum: 1 }
    }
  }
])
```

## Benefits of This Architecture

1. **Accurate Representation**: Captures the reality that providers have different statuses at different locations
2. **Query Performance**: Optimized indexes for common queries
3. **Historical Tracking**: Status change history for compliance/auditing
4. **Scalability**: Can handle providers at 100+ locations
5. **Data Integrity**: Normalized structure prevents inconsistencies
6. **Flexibility**: Easy to add new attributes or relationships

## Success Metrics

1. **Data Completeness**:
   - 100% of providers extracted (matching manual counts)
   - All location relationships captured
   - All carrier status variations preserved

2. **Query Performance**:
   - Sub-100ms response for provider lookups
   - Sub-500ms for aggregation queries
   - Efficient location-based filtering

3. **Data Quality**:
   - No duplicate providers
   - Consistent location naming
   - Accurate status tracking

## Next Steps

1. **Immediate**: Fix extraction logic to capture all Nevada providers
2. **This Week**: Implement new schema and migration scripts
3. **Next Week**: Update dashboard to support location-based queries
4. **Ongoing**: Monitor data quality and query performance

## Conclusion

This architecture properly models the complex reality of provider networks where:
- Providers work at multiple locations
- Carrier participation varies by location
- Status changes need to be tracked over time

By implementing this plan, we'll have a robust, queryable system that accurately represents the provider network landscape.