#!/usr/bin/env python3
"""
Analyze provider-location-carrier relationships and validate extraction data
"""

import json
from collections import defaultdict
from pathlib import Path
import re

def analyze_provider_data():
    """Analyze the extracted provider data to understand the structure"""
    
    states = ['nevada', 'utah', 'arizona', 'colorado']
    analysis = {}
    
    for state in states:
        json_file = Path('sync-output') / f'{state}_providers.json'
        with open(json_file, 'r') as f:
            providers = json.load(f)
        
        # Track unique providers and their locations
        provider_locations = defaultdict(list)
        location_providers = defaultdict(list)
        all_locations = set()
        
        for p in providers:
            name = p['provider_name']
            location = p.get('location', 'Unknown')
            location_id = p.get('location_id', '')
            
            # Create location-specific entry
            location_key = f"{location} {location_id}" if location_id else location
            provider_locations[name].append({
                'location': location,
                'location_id': location_id,
                'location_full': location_key,
                'carrier_statuses': p.get('carrier_statuses', []),
                'percentage': p.get('percentage', '')
            })
            
            location_providers[location_key].append(name)
            all_locations.add(location_key)
        
        analysis[state] = {
            'total_instances': len(providers),
            'unique_providers': len(provider_locations),
            'unique_locations': len(all_locations),
            'providers_by_location': dict(location_providers),
            'locations_by_provider': {k: len(v) for k, v in provider_locations.items()},
            'multi_location_providers': {k: v for k, v in provider_locations.items() if len(v) > 1}
        }
        
        # Print analysis
        print(f"\n{'='*60}")
        print(f"{state.upper()} ANALYSIS")
        print(f"{'='*60}")
        print(f"Total provider instances: {analysis[state]['total_instances']}")
        print(f"Unique providers: {analysis[state]['unique_providers']}")
        print(f"Unique locations: {analysis[state]['unique_locations']}")
        
        print(f"\nLocations:")
        for loc in sorted(all_locations):
            count = len(location_providers[loc])
            print(f"  {loc}: {count} providers")
        
        print(f"\nProviders at multiple locations: {len(analysis[state]['multi_location_providers'])}")
        for name, locations in list(analysis[state]['multi_location_providers'].items())[:5]:
            print(f"  {name}:")
            for loc in locations[:3]:  # Show first 3 locations
                print(f"    - {loc['location']} ({loc['percentage']})")
    
    return analysis

def check_carrier_consistency(state_data):
    """Check if carrier statuses are consistent across locations for same provider"""
    
    inconsistencies = []
    
    for state, providers in state_data.items():
        json_file = Path('sync-output') / f'{state}_providers.json'
        with open(json_file, 'r') as f:
            provider_list = json.load(f)
        
        # Group by provider name
        provider_instances = defaultdict(list)
        for p in provider_list:
            provider_instances[p['provider_name']].append(p)
        
        # Check each provider with multiple locations
        for name, instances in provider_instances.items():
            if len(instances) > 1:
                # Compare carrier statuses across locations
                carrier_status_by_location = {}
                
                for inst in instances:
                    location = f"{inst.get('location', 'Unknown')} {inst.get('location_id', '')}"
                    carrier_statuses = {cs['carrier']: cs['status_code'] 
                                      for cs in inst.get('carrier_statuses', [])}
                    carrier_status_by_location[location] = carrier_statuses
                
                # Find differences
                all_carriers = set()
                for statuses in carrier_status_by_location.values():
                    all_carriers.update(statuses.keys())
                
                for carrier in all_carriers:
                    statuses_at_locations = {
                        loc: statuses.get(carrier, 'missing')
                        for loc, statuses in carrier_status_by_location.items()
                    }
                    
                    # Check if statuses differ
                    unique_statuses = set(statuses_at_locations.values())
                    if len(unique_statuses) > 1:
                        inconsistencies.append({
                            'state': state,
                            'provider': name,
                            'carrier': carrier,
                            'locations': statuses_at_locations
                        })
    
    return inconsistencies

def main():
    print("PROVIDER-LOCATION-CARRIER ANALYSIS")
    print("="*80)
    
    # Run main analysis
    analysis = analyze_provider_data()
    
    print("\n\nCARRIER STATUS CONSISTENCY CHECK")
    print("="*80)
    
    # Check for carrier status differences across locations
    inconsistencies = check_carrier_consistency({state: None for state in ['nevada', 'utah', 'arizona', 'colorado']})
    
    if inconsistencies:
        print(f"\nFound {len(inconsistencies)} carrier status differences across locations:")
        for i, inc in enumerate(inconsistencies[:10]):  # Show first 10
            print(f"\n{i+1}. {inc['provider']} - {inc['carrier']} ({inc['state']})")
            for loc, status in inc['locations'].items():
                print(f"   {loc}: {status}")
    else:
        print("\nNo carrier status inconsistencies found across locations.")
    
    # Compare with user's manual counts
    print("\n\nCOMPARISON WITH MANUAL COUNTS")
    print("="*80)
    manual_counts = {
        'nevada': 10,
        'utah': 66,
        'arizona': 11,
        'colorado': 16
    }
    
    for state, manual in manual_counts.items():
        extracted = analysis[state]['unique_providers']
        print(f"{state.upper()}:")
        print(f"  Manual count: {manual}")
        print(f"  Extracted count: {extracted}")
        print(f"  Difference: {extracted - manual}")
        if extracted != manual:
            print(f"  ⚠️  MISMATCH - Extraction may be incomplete!")

if __name__ == "__main__":
    main()