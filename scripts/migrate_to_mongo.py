"""
Migrate Carrier Credentialing Data from JSON Files to MongoDB
"""

import json
from pathlib import Path
from pymongo import MongoClient
import logging

def setup_logging():
    """Set up logging for the migration script"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler('logs/mongo_migration.log')
        ]
    )
    Path('logs').mkdir(exist_ok=True)

def connect_to_mongo():
    """Connect to MongoDB and return the database object"""
    client = MongoClient('mongodb://localhost:27017/')
    db = client['PDC_Credentialing']
    return db

def migrate_data():
    """Migrate data from JSON files to MongoDB"""
    logger = logging.getLogger(__name__)
    db = connect_to_mongo()

    # Drop existing collections for a clean migration
    db.Providers.drop()
    db.Locations.drop()
    db.Carrier_Status.drop()
    logger.info("Cleared existing collections.")

    json_dir = Path('/Users/rainceo/OpenDental_Conekt/carrier_credentialing')
    json_files = list(json_dir.glob('*_carrier_credentialing.json'))

    for file_path in json_files:
        with open(file_path, 'r') as f:
            data = json.load(f)
            carrier_name = data['carrier_name']

            for provider_data in data.get('providers', []):
                provider_name = provider_data['provider_name']
                
                # Insert provider and get ID
                provider_doc = db.Providers.find_one_and_update(
                    {'Provider_Name': provider_name},
                    {'$setOnInsert': {'Provider_Name': provider_name}},
                    upsert=True,
                    return_document=True
                )
                provider_id = provider_doc['_id']

                for location_data in provider_data.get('locations', []):
                    # Insert location and get ID
                    location_doc = db.Locations.find_one_and_update(
                        {
                            'Provider_ID': provider_id,
                            'Location_Name': location_data['location_name'],
                            'Tax_ID': location_data['tax_id']
                        },
                        {
                            '$set': {
                                'State': location_data['state'],
                                'Is_Dormant': location_data['is_dormant'],
                                'Percentage': location_data.get('percentage'),
                                'Metadata': location_data.get('metadata', {})
                            }
                        },
                        upsert=True,
                        return_document=True
                    )
                    location_id = location_doc['_id']

                    # Insert carrier status
                    db.Carrier_Status.insert_one({
                        'Provider_ID': provider_id,
                        'Location_ID': location_id,
                        'Carrier_Name': carrier_name,
                        'Status': location_data.get('status', ''),
                        'Last_Updated': location_data['last_updated']
                    })
        logger.info(f"Processed {file_path.name}")

    # Create indexes for faster queries
    db.Locations.create_index('Provider_ID')
    db.Carrier_Status.create_index('Provider_ID')
    db.Carrier_Status.create_index('Location_ID')
    logger.info("Created indexes on collections.")
    logger.info("Data migration to MongoDB completed successfully.")

if __name__ == '__main__':
    setup_logging()
    migrate_data()
