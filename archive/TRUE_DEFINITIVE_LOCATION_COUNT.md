# THE ACTUAL TRUTH: 44 Unique Physical Locations

Based on the raw Smartsheet data provided directly by the user, the **definitive count is 44 unique physical locations**.

## Location Breakdown by State

### Utah: 29 locations (not 25!)
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
11. **MTN. VIEW (84-3191484)** ← MISSING FROM EXTRACTION
12. **N. LOGAN (82-2724174)** ← MISSING FROM EXTRACTION
13. **N. OGDEN (92-3874166)** ← MISSING FROM EXTRACTION
14. OGDEN (99-4219526)
15. PARK CITY (82-2761852)
16. PROVIDENCE (84-4291469)
17. PROVO (86-3448732)
18. REDWOOD (88-3906576)
19. SANDY (82-2797501)
20. SOUTH JORDAN (83-3594222)
21. SOUTH OGDEN (83-3988478)
22. SOUTH PROVO (92-3856564)
23. **ST. GEORGE (83-2566764)** ← MISSING FROM EXTRACTION
24. STANSBURY (84-3183846)
25. SUGARHOUSE (82-3069069)
26. THANKSGIVING POINT (86-1918074)
27. TOOELE (87-3100597)
28. WEST JORDAN (82-2723988)
29. ZION (88-3346129)

### Nevada: 4 locations (correct)
1. SPRING VALLEY (33-5013104)
2. SUMMERHILLS (39-2894525)
3. SUMMERLIN (88-0512322)
4. SUNRISE (33-1262407)

### Colorado: 6 locations (not 5!)
1. BROADMOOR (93-4498028)
2. **CITADEL CROSSING (93-4517487)** ← MISSING FROM EXTRACTION
3. LEHMAN (83-0658299)
4. PREMIER (82-5376977)
5. RESEARCH PKWY (99-2576458)
6. SPRINGS (85-4006063)

### Arizona: 5 locations (correct)
1. CHANDLER (99-1613326)
2. CHINO (99-2747023)
3. HORIZON (99-2717502)
4. PRESCOTT VALLEY (99-2764915)
5. SCOTTSDALE WEST (33-3944099)

## Why the Extraction Missed 5 Locations

The v2 extraction script is missing these 5 locations:
1. **MTN. VIEW (84-3191484)** - A completely new location not in any archive
2. **N. LOGAN (82-2724174)** - Was in archive but not extracted
3. **N. OGDEN (92-3874166)** - Was in archive but not extracted
4. **ST. GEORGE (83-2566764)** - Was in archive but not extracted
5. **CITADEL CROSSING (93-4517487)** - Was in archive but not extracted

## Key Insights from Raw Data

### 1. Provider Distribution
- **Most providers work at multiple locations**: Shaun Heward works at 24 locations!
- Luis Franco: 19 locations
- Robert Swenson: 18 locations
- Vanessa Bikhazi: 13 locations
- Daniel Burstein: 12 locations

### 2. Active vs Dormant
- Total Provider Instances: 303
- Active Providers: 241 (79.5%)
- Dormant Providers: 62 (20.5%)
- Note: This is different from extraction which showed more dormant providers

### 3. The Mystery of "53"
Even with the true count of 44, we still don't reach 53. The possibilities:
- 53 was a projected/planned number
- 53 included test locations or duplicates
- 53 was simply an error that got propagated

## Conclusion

**The definitive, actual count is 44 unique physical locations**, based on direct inspection of the raw Smartsheet data. The extraction process has bugs that cause it to miss 5 locations. This explains part of the discrepancy, but even the true count of 44 doesn't match the mythical "53" in the metadata.