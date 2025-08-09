# Definitive Location Count - Fresh Extraction August 8, 2025

## Executive Summary

**The actual number of unique physical locations is 39**, based on a fresh extraction from live Smartsheet data performed on August 8, 2025.

## Location Breakdown by State

### Nevada: 4 locations
1. SUMMERLIN (88-0512322)
2. SUNRISE (33-1262407)
3. SPRING VALLEY (33-5013104)
4. SUMMERHILLS (39-2894525)

### Utah: 25 locations
1. PROVO (86-3448732)
2. LEHI (82-3054474)
3. SANDY (82-2797501)
4. WEST JORDAN (82-2723988)
5. PARK CITY (82-2761852)
6. CACHE VALLEY (82-2724259)
7. SOUTH JORDAN (83-3594222)
8. SOUTH OGDEN (83-3988478)
9. DAYBREAK (84-2598507)
10. STANSBURY (84-3183846)
11. PROVIDENCE (84-4291469)
12. THANKSGIVING POINT (86-1918074)
13. TOOELE (87-3100597)
14. SUGARHOUSE (82-3069069)
15. FAIRFIELD (88-3343395)
16. REDWOOD (88-3906576)
17. MIDVALE (92-1442336)
18. HEBER (92-2313079)
19. ZION (88-3346129)
20. MILLCREEK (92-1386801)
21. SOUTH PROVO (92-3856564)
22. BOUNTIFUL (84-4192377)
23. MAGNA (93-4461968)
24. OGDEN (99-4219526)
25. EAST OGDEN (33-2135430)

### Arizona: 5 locations
1. CHANDLER (99-1613326)
2. CHINO (99-2747023)
3. PRESCOTT VALLEY (99-2764915)
4. HORIZON (99-2717502)
5. SCOTTSDALE WEST (33-3944099)

### Colorado: 5 locations
1. PREMIER (82-5376977)
2. LEHMAN (83-0658299)
3. SPRINGS (85-4006063)
4. BROADMOOR (93-4498028)
5. RESEARCH PKWY (99-2576458)

## Key Findings

### 1. The "53" is Definitively Wrong
- No data source contains 53 unique locations
- The metadata claiming 53 appears to be a historical error
- Fresh extraction shows 39 locations
- Archive file has 41 locations
- Even combining all sources doesn't reach 53

### 2. Location Changes Over Time
**Locations Added Since Archive** (3):
- REDWOOD (88-3906576) - Utah
- SUMMERHILLS (39-2894525) - Nevada
- THANKSGIVING POINT (86-1918074) - Utah

**Locations Removed Since Archive** (5):
- CITADEL CROSSING (93-4517487) - Colorado
- FLAMINGO RD (33-4895660) - Nevada
- N. LOGAN (82-2724174) - Utah
- N. OGDEN (92-3874166) - Utah
- ST. GEORGE (83-2566764) - Utah

### 3. Provider Distribution
From the fresh extraction:
- **Total Provider Instances**: 516 (across all locations)
- **Active Providers**: 333 (64.5%)
- **Dormant Providers**: 183 (35.5%)

### 4. Location Size Variation
- **Largest**: TOOELE, Utah with 69 providers
- **Smallest**: CHANDLER, Arizona with 0 providers (location exists but no active providers)

## Data Validation

All 39 locations have:
- ✓ Valid Tax ID format (XX-XXXXXXX)
- ✓ Unique location name + Tax ID combination
- ✓ No duplicates across states
- ✓ Consistent naming conventions

## Recommendations

1. **Update All Documentation**: Replace any reference to "53 locations" with "39 locations"
2. **MongoDB Migration**: Complete loading all 39 locations (currently only has 14)
3. **Regular Monitoring**: Locations change over time - implement tracking
4. **Archive Updates**: Update the comprehensive file to reflect current state

## Conclusion

The definitive count is **39 unique physical locations** as of August 8, 2025. This is based on live data extraction directly from Smartsheet sources. The "53" appears to be a documentation error that has persisted in metadata but is not supported by any actual data.