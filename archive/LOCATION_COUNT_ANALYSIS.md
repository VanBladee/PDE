# Location Count Analysis - Finding the Truth

## Data Sources Comparison

### 1. Archive Comprehensive Data (`archive/data/comprehensive_provider_network_data.json`)
- **Metadata claims**: 53 total locations
- **Actual count**: 41 locations
  - Utah: 26 locations
  - Colorado: 6 locations  
  - Arizona: 5 locations
  - Nevada: 4 locations
- **Discrepancy**: Metadata says 53 but only 41 locations exist in the file

### 2. Extracted Data (`sync-output/*.json`)
- **Total unique locations**: 33
  - Utah: 24 locations
  - Colorado: 5 locations
  - Arizona: 3 locations
  - Nevada: 1 location (extraction issue - only SUMMERLIN)
- **Note**: Extraction is incomplete for Nevada and Arizona

### 3. MongoDB Data (`crucible` database)
- **Current state**: Only 14 locations
  - Utah: 10 locations
  - Nevada: 4 locations
  - Arizona: 0 locations (missing!)
  - Colorado: 0 locations (missing!)
- **Collections**:
  - `locations`: 30 documents (summary data)
  - `provider_locations`: 87 documents (provider-location assignments)
  - `providers`: 36 documents
  - `provider_carrier_statuses`: 2,727 documents

## The Truth About Location Count

Based on the analysis:

1. **The 53 location claim is incorrect** - The metadata in the comprehensive file claims 53 but only contains 41
2. **The actual unique locations across all sources**: ~41 locations
3. **MongoDB is severely incomplete** - Missing Arizona and Colorado entirely

## Actual Location Breakdown

### Utah (26 locations)
1. BOUNTIFUL (84-4192377)
2. CACHE VALLEY (82-2724259)
3. DAYBREAK (84-2598507)
4. EAST OGDEN (33-2135430)
5. FAIRFIELD (88-3343395)
6. HEBER (92-2313079)
7. LEHI (82-3054474)
8. MAGNA (93-4461968)
9. MIDVALE (92-1442336)
10. MILLCREEK (92-1386801)
11. N. LOGAN (82-2724174)
12. N. OGDEN (92-3874166)
13. OGDEN (99-4219526)
14. PARK CITY (82-2761852)
15. PROVIDENCE (84-4291469)
16. PROVO (86-3448732)
17. SANDY (82-2797501)
18. SOUTH JORDAN (83-3594222)
19. SOUTH OGDEN (83-3988478)
20. SOUTH PROVO (92-3856564)
21. SUGARHOUSE (82-3069069)
22. ST. GEORGE (83-2566764)
23. STANSBURY (84-3183846)
24. TOOELE (87-3100597)
25. WEST JORDAN (82-2723988)
26. ZION (88-3346129)

### Colorado (6 locations)
1. BROADMOOR (93-4498028)
2. CITADEL CROSSING (93-4517487)
3. LEHMAN (83-0658299)
4. PREMIER (82-5376977)
5. RESEARCH PKWY (99-2576458)
6. SPRINGS (85-4006063)

### Arizona (5 locations)
1. CHANDLER (99-1613326)
2. CHINO (99-2747023)
3. HORIZON (99-2717502)
4. PRESCOTT VALLEY (99-2764915)
5. SCOTTSDALE WEST (33-3944099)

### Nevada (4 locations)
1. FLAMINGO RD (33-4895660)
2. SPRING VALLEY (33-5013104)
3. SUMMERLIN (88-0512322)
4. SUNRISE (33-1262407)

## Additional Locations from Extraction (Not in Archive)
The extraction found some locations not in the comprehensive file:
- Utah: REDWOOD, THANKSGIVING POINT, etc.
- Nevada: SUMMERHILLS (might be a variant of SUMMERLIN)

## Conclusion

**The actual number of unique physical locations is approximately 41-45**, not 53 or 229. The confusion arises from:
1. Incorrect metadata (claims 53 but has 41)
2. Provider-location assignments being counted as locations
3. Incomplete data migration to MongoDB
4. Extraction issues missing some locations