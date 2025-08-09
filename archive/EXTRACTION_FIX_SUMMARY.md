# Extraction Script Fix Summary

## Problem
The extraction script was only capturing 39 out of 44 dental office locations from the Smartsheet data.

## Missing Locations (5)
1. **MTN. VIEW (84-3191484)** - Utah
2. **N. LOGAN (82-2724174)** - Utah  
3. **N. OGDEN (92-3874166)** - Utah
4. **ST. GEORGE (83-2566764)** - Utah
5. **CITADEL CROSSING (93-4517487)** - Colorado

## Root Causes

### 1. Regex Pattern Too Restrictive
The original regex `^([A-Z][A-Z\s]+?)(?:\s+(\d{2}-\d{7}))?$` required at least 2 uppercase letters and didn't allow periods.

**Fixed:** Updated to `^([A-Z][A-Za-z\s.\-]+?)(?:\s+(\d{2}-\d{7}))?$` to allow:
- Periods in location names (N. LOGAN, MTN. VIEW, ST. GEORGE)
- Mixed case (Citadel Crossing)
- Hyphens in names

### 2. Non-Location Entry Filtering
The script was capturing non-location entries like "Credentialing Key", "Filler Space", etc.

**Fixed:** Added filtering logic to skip these entries while preserving real locations.

### 3. Location Tracking Logic
When "Ci" appeared before "Citadel Crossing", the tracking got confused because "Ci" was treated as a location.

**Fixed:** Special handling for edge cases and improved state management.

### 4. Zero-Provider Locations
PARK CITY was being found but not saved because the logic only saved locations when moving to the next one.

**Fixed:** Initialize location stats immediately when found to ensure all locations are captured.

## Results
✅ **All 44 locations now captured successfully**
- Nevada: 4 locations ✓
- Utah: 29 locations ✓  
- Arizona: 5 locations ✓
- Colorado: 6 locations ✓

## Files Modified
- `/src/sync-credentialing-data-v2.py` - Enhanced regex, improved filtering, fixed location tracking
- `/validate_extraction.py` - Added case-insensitive validation

## Verification
Run `python validate_extraction.py` to confirm all 44 locations are captured.