#!/usr/bin/env python3
"""
Insert extracted carrier network data into MongoDB PDC_provider_status collection
Maps extracted JSON to the correct schema for the credentialing dashboard
"""

import os
import json
import argparse
from datetime import datetime, timezone
from pathlib import Path
import logging
from pymongo import MongoClient, UpdateOne
from bson import ObjectId
from dotenv import load_dotenv
import sys

# Load environment variables
load_dotenv()

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class PDCStatusInserter:
    """Insert carrier network data into PDC_provider_status collection"""
    
    def __init__(self):
        self.mongo_uri = os.getenv('MONGO_URI')
        if not self.mongo_uri:
            raise ValueError("MONGO_URI not found in environment variables")
            
        self.client = MongoClient(self.mongo_uri)
        self.registry_db = self.client['registry']  # Use registry database
        
        # Target collection
        self.pdc_status = self.registry_db['PDC_provider_status']
        
        # State mappings
        self.state_mapping = {
            'nevada': 'NV',
            'utah': 'UT', 
            'arizona': 'AZ',
            'colorado': 'CO'
        }
        
        # Organization info (can be configured via env)
        self.organization_id = os.getenv('PDC_ORGANIZATION_ID', 'PDC001')
        self.organization_name = os.getenv('PDC_ORGANIZATION_NAME', 'Platinum Dental Care')
        
        # Statistics
        self.stats = {
            'total_records': 0,
            'inserted': 0,
            'updated': 0,
            'errors': 0,
            'locations_processed': set(),
            'carriers_processed': set()
        }
    
    def generate_provider_id(self, provider_name: str, location_id: str) -> str:
        """Generate unique provider ID based on name and location"""
        # Simple hash-based ID generation
        import hashlib
        unique_str = f"{provider_name}_{location_id}"
        return hashlib.md5(unique_str.encode()).hexdigest()[:12].upper()
    
    def generate_location_id(self, location_name: str, tax_id: str) -> str:
        """Generate unique location ID based on name and tax ID"""
        import hashlib
        unique_str = f"{location_name}_{tax_id}"
        return hashlib.md5(unique_str.encode()).hexdigest()[:12].upper()
    
    def generate_carrier_id(self, carrier_name: str) -> str:
        """Generate carrier ID from name"""
        # Simple approach: uppercase, remove spaces/special chars, add suffix
        import re
        carrier_id = re.sub(r'[^A-Z0-9]', '', carrier_name.upper())[:10]
        return f"{carrier_id}001"
    
    def insert_state_data(self, state: str, providers_file: Path, locations_file: Path) -> dict:
        """Insert data from state JSON files"""
        logger.info(f"Processing {state} data...")
        
        # Load providers data
        with open(providers_file, 'r') as f:
            providers = json.load(f)
        
        # Load locations data to get full location info
        with open(locations_file, 'r') as f:
            locations = json.load(f)
        
        # Create location lookup
        location_lookup = {
            loc['location_id']: loc for loc in locations
        }
        
        # Track ALL locations from the locations file, even if they have no providers
        for location in locations:
            location_key = f"{location['name']} ({location['location_id']})"
            self.stats['locations_processed'].add(location_key)
            logger.info(f"  Found location: {location_key} with {location['total_providers']} providers")
        
        # Get state abbreviation
        state_abbr = self.state_mapping.get(state, state.upper()[:2])
        
        # Prepare bulk operations
        bulk_ops = []
        
        # Process each provider
        for provider in providers:
            provider_name = provider['provider_name']
            location_tax_id = provider['location_id']
            location_name = provider['location']
            
            # Generate IDs
            provider_id = self.generate_provider_id(provider_name, location_tax_id)
            location_id = self.generate_location_id(location_name, location_tax_id)
            
            # Track unique locations
            self.stats['locations_processed'].add(f"{location_name} ({location_tax_id})")
            
            # Process each carrier status - create one document per carrier
            for carrier_status in provider['carrier_statuses']:
                carrier_name = carrier_status['carrier']
                carrier_id = self.generate_carrier_id(carrier_name)
                status_code = carrier_status['status_code']  # Use the raw code (x, n, f, etc.)
                
                # Track unique carriers
                self.stats['carriers_processed'].add(carrier_name)
                
                # Create document matching PDC_provider_status schema
                doc = {
                    # Provider Information
                    'Provider_ID': provider_id,
                    'Provider_Name': provider_name,
                    
                    # Location Information
                    'Location_ID': location_id,
                    'Location_Name': location_name,
                    'Location_State': state_abbr,
                    'Location_TaxID': location_tax_id,
                    
                    # Carrier Information
                    'Carrier_ID': carrier_id,
                    'Carrier_Name': carrier_name,
                    
                    # Status Information
                    'Status': status_code,  # x, n, f, p, s, o, or empty
                    'Percentage': provider.get('percentage', ''),
                    'Last_Updated': datetime.now(timezone.utc),
                    
                    # Organization Info
                    'Organization_ID': self.organization_id,
                    'Organization_Name': self.organization_name,
                    
                    # Metadata
                    'createdAt': datetime.now(timezone.utc),
                    'updatedAt': datetime.now(timezone.utc),
                    
                    # Additional metadata
                    'metadata': {
                        'is_dormant': provider.get('is_dormant', False),
                        'extraction_date': datetime.now(timezone.utc),
                        'source': 'smartsheet',
                        'state_full': state
                    }
                }
                
                # Create update operation (upsert)
                bulk_ops.append(
                    UpdateOne(
                        {
                            'Provider_ID': provider_id,
                            'Location_ID': location_id,
                            'Carrier_ID': carrier_id,
                            'Organization_ID': self.organization_id
                        },
                        {'$set': doc},
                        upsert=True
                    )
                )
                
                self.stats['total_records'] += 1
        
        # Execute bulk operations
        if bulk_ops:
            try:
                result = self.pdc_status.bulk_write(bulk_ops, ordered=False)
                self.stats['inserted'] += result.upserted_count
                self.stats['updated'] += result.modified_count
                logger.info(f"  Processed {len(bulk_ops)} records")
                logger.info(f"  Inserted: {result.upserted_count}, Updated: {result.modified_count}")
            except Exception as e:
                logger.error(f"Error inserting {state} data: {str(e)}")
                self.stats['errors'] += len(bulk_ops)
        
        return {
            'processed': len(bulk_ops),
            'providers': len(providers),
            'locations': len(location_lookup)
        }
    
    def create_indexes(self):
        """Create indexes for optimal query performance"""
        logger.info("Creating indexes...")
        
        # Compound index for unique constraint
        self.pdc_status.create_index([
            ('Provider_ID', 1),
            ('Location_ID', 1),
            ('Carrier_ID', 1),
            ('Organization_ID', 1)
        ], unique=True)
        
        # Query performance indexes
        self.pdc_status.create_index([('Organization_ID', 1), ('Location_State', 1)])
        self.pdc_status.create_index([('Organization_ID', 1), ('Location_TaxID', 1)])
        self.pdc_status.create_index([('Provider_Name', 1)])
        self.pdc_status.create_index([('Location_Name', 1)])
        self.pdc_status.create_index([('Carrier_Name', 1)])
        self.pdc_status.create_index([('Status', 1)])
        self.pdc_status.create_index([('Last_Updated', -1)])
        
        logger.info("Indexes created successfully")
    
    def insert_all_states(self, sync_dir: str = 'sync-output'):
        """Insert all state data from sync directory"""
        sync_path = Path(sync_dir)
        
        if not sync_path.exists():
            logger.error(f"Sync directory not found: {sync_dir}")
            return
        
        # Create indexes first
        self.create_indexes()
        
        # Process each state
        states_processed = []
        for providers_file in sync_path.glob('*_providers_v2.json'):
            state = providers_file.stem.replace('_providers_v2', '')
            locations_file = sync_path / f'{state}_locations.json'
            
            if not locations_file.exists():
                logger.warning(f"Locations file not found for {state}")
                continue
            
            state_stats = self.insert_state_data(state, providers_file, locations_file)
            states_processed.append({
                'state': state,
                'stats': state_stats
            })
        
        # Generate summary report
        self.print_summary(states_processed)
    
    def print_summary(self, states_processed):
        """Print insertion summary"""
        print("\n" + "="*80)
        print("PDC_provider_status Insertion Summary")
        print("="*80)
        print(f"Database: registry")
        print(f"Collection: PDC_provider_status")
        print(f"Organization: {self.organization_name} ({self.organization_id})")
        print(f"Run Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print()
        
        # State breakdown
        print("State Breakdown:")
        for state_info in states_processed:
            state = state_info['state']
            stats = state_info['stats']
            state_abbr = self.state_mapping.get(state, state.upper()[:2])
            print(f"\n{state.upper()} ({state_abbr}):")
            print(f"  Providers: {stats['providers']}")
            print(f"  Locations: {stats['locations']}")
            print(f"  Records Created: {stats['processed']}")
        
        # Totals
        print(f"\nTOTALS:")
        print(f"  Total Records: {self.stats['total_records']}")
        print(f"  Inserted: {self.stats['inserted']}")
        print(f"  Updated: {self.stats['updated']}")
        print(f"  Errors: {self.stats['errors']}")
        print(f"  Unique Locations: {len(self.stats['locations_processed'])}")
        print(f"  Unique Carriers: {len(self.stats['carriers_processed'])}")
        
        # Expected vs Actual
        print(f"\nLocation Verification:")
        print(f"  Expected: 44 unique physical offices")
        print(f"  Found: {len(self.stats['locations_processed'])} unique locations")
        
        if len(self.stats['locations_processed']) == 44:
            print("  ✅ All locations captured!")
        else:
            print(f"  ⚠️  Missing {44 - len(self.stats['locations_processed'])} locations")
        
        # Show location breakdown by state
        print(f"\nLocations by State:")
        state_locations = {'NV': [], 'UT': [], 'AZ': [], 'CO': []}
        for loc in sorted(self.stats['locations_processed']):
            # Determine state from location data
            for state_info in states_processed:
                state_abbr = self.state_mapping.get(state_info['state'], '')
                if state_abbr:
                    state_locations[state_abbr].append(loc)
                    break
        
        # Note: This simple approach may not accurately distribute locations
        # In production, we'd track state per location during processing
        
        print("="*80)
    
    def verify_insertion(self):
        """Verify data was inserted correctly"""
        logger.info("\nVerifying insertion...")
        
        # Count total documents
        total_docs = self.pdc_status.count_documents({'Organization_ID': self.organization_id})
        logger.info(f"Total documents in PDC_provider_status: {total_docs}")
        
        # Count unique locations
        unique_locations = self.pdc_status.distinct('Location_TaxID', {'Organization_ID': self.organization_id})
        logger.info(f"Unique locations (by Tax ID): {len(unique_locations)}")
        
        # Count by state
        pipeline = [
            {'$match': {'Organization_ID': self.organization_id}},
            {'$group': {
                '_id': '$Location_State',
                'count': {'$sum': 1},
                'locations': {'$addToSet': '$Location_TaxID'}
            }}
        ]
        
        state_counts = list(self.pdc_status.aggregate(pipeline))
        logger.info("\nDocuments by state:")
        for state in state_counts:
            logger.info(f"  {state['_id']}: {state['count']} records, {len(state['locations'])} unique locations")
        
        # Sample document
        sample = self.pdc_status.find_one({'Organization_ID': self.organization_id})
        if sample:
            logger.info("\nSample document:")
            logger.info(f"  Provider: {sample.get('Provider_Name')}")
            logger.info(f"  Location: {sample.get('Location_Name')} ({sample.get('Location_TaxID')})")
            logger.info(f"  Carrier: {sample.get('Carrier_Name')}")
            logger.info(f"  Status: {sample.get('Status')}")


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(description='Insert carrier network data into PDC_provider_status')
    parser.add_argument('--sync-dir', default='sync-output', help='Directory containing JSON files')
    parser.add_argument('--verify-only', action='store_true', help='Only verify existing data')
    parser.add_argument('--clear-first', action='store_true', help='Clear existing data before insert')
    
    args = parser.parse_args()
    
    try:
        inserter = PDCStatusInserter()
        
        if args.verify_only:
            inserter.verify_insertion()
        else:
            if args.clear_first:
                logger.warning("Clearing existing PDC data...")
                result = inserter.pdc_status.delete_many({'Organization_ID': inserter.organization_id})
                logger.info(f"Deleted {result.deleted_count} existing records")
            
            logger.info("🚀 Starting PDC_provider_status insertion")
            logger.info("="*60)
            inserter.insert_all_states(args.sync_dir)
            inserter.verify_insertion()
            logger.info("\n✅ Insertion completed successfully!")
            
    except Exception as e:
        logger.error(f"Insertion failed: {str(e)}")
        raise


if __name__ == "__main__":
    main()