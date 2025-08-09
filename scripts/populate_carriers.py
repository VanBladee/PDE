#!/usr/bin/env python3
"""
Populate carriersRegistry collection with carriers from JSON data
"""

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from pymongo import MongoClient, UpdateOne
from bson import ObjectId
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def populate_carriers_registry():
    """Populate carriersRegistry collection with carriers from JSON files"""
    
    # Connect to MongoDB
    mongo_uri = os.getenv('MONGO_URI', 'mongodb://localhost:27017/')
    client = MongoClient(mongo_uri)
    db = client['crucible']
    carriers_registry = db['carriersRegistry']
    
    # Get all carriers from JSON files
    carriers = set()
    sync_output = Path('sync-output')
    
    for json_file in sync_output.glob('*_providers.json'):
        try:
            with open(json_file, 'r') as f:
                data = json.load(f)
                for provider in data:
                    for carrier_status in provider.get('carrier_statuses', []):
                        carriers.add(carrier_status['carrier'])
        except Exception as e:
            print(f"Error reading {json_file}: {e}")
    
    print(f"Found {len(carriers)} unique carriers in JSON files")
    
    # Create carrier mapping (similar to sync script)
    carrier_mapping = {
        # Common carriers
        'Aetna': 'AETNA001',
        'Ameritas': 'AMERITAS001',
        'Anthem': 'ANTHEM001',
        'BCBS': 'BCBS001',
        'BCBS Anthem': 'BCBS_ANTHEM001',
        'BCBS AZ (Dominion)': 'BCBS_AZ001',
        'Blue Cross': 'BCBS001',
        'Blue Shield': 'BCBS001',
        'Regence BCBS': 'BCBS_REG001',
        'Careington': 'CARE001',
        'Cigna': 'CIGNA001',
        'Connection Dental (GEHA)': 'GEHA001',
        'GEHA (Connection)': 'GEHA001',
        'Delta Dental': 'DELTA001',
        'Dental Select': 'DENSEL001',
        'Dental Select Silver': 'DENSEL_S001',
        'Dental Select Gold': 'DENSEL_G001',
        'Dental Select Platinum': 'DENSEL_P001',
        'DentaQuest': 'DENTAQ001',
        'Dentaquest (HMO)': 'DENTAQ_HMO001',
        'Dentist Direct': 'DENTDIR001',
        'Renaissance (Dentist Direct)': 'DENTDIR001',
        'DHA': 'DHA001',
        'DHA/Sun Life': 'DHA_SUN001',
        'DMBA (recred)': 'DMBA001',
        'Diversified': 'DIV001',
        'EMI Advantage': 'EMI_ADV001',
        'EMI Premier': 'EMI_PREM001',
        'EMI Value': 'EMI_VAL001',
        'Guardian': 'GUARD001',
        'Guardian (Zelis)': 'GUARD_ZELIS001',
        'Humana': 'HUMANA001',
        'MCNA Medicaid': 'MCNA_MED001',
        'Medicaid': 'MEDICAID001',
        'MetLife': 'METLIFE001',
        'PEHP': 'PEHP001',
        'Premier Access Medicaid': 'PREM_ACC_MED001',
        'Premiere Access': 'PREM_ACC001',
        'Principal': 'PRINCIPAL001',
        'Principal (Zelis)': 'PRINCIPAL_ZELIS001',
        'Samera Health': 'SAMERA001',
        'SelectHealth Advantage': 'SEL_ADV001',
        'SelectHealth Classic': 'SEL_CLASSIC001',
        'SelectHealth Fundamental': 'SEL_FUND001',
        'SelectHealth Prime': 'SEL_PRIME001',
        'TDA': 'TDA001',
        'UHC': 'UHC001',
        'Unicare (Anthem) 100/200/300': 'UNICARE_100001',
        'Unicare (Anthem) PPO': 'UNICARE_PPO001',
        'Unicare 100/200/300': 'UNICARE_100001',
        'Unicare PPO': 'UNICARE_PPO001',
        'United Concordia': 'UNITED_CONC001',
        'United Concordia (Zelis)': 'UNITED_CONC_ZELIS001',
        'United HealthCare': 'UNITED_HC001',
    }
    
    # Generate bulk operations
    bulk_ops = []
    for carrier_name in sorted(carriers):
        # Get or generate carrier ID
        carrier_id = carrier_mapping.get(carrier_name)
        if not carrier_id:
            # Generate new carrier ID
            import re
            carrier_id = re.sub(r'[^A-Z0-9]', '', carrier_name.upper())[:8] + '001'
            carrier_mapping[carrier_name] = carrier_id
            print(f"Generated new carrier ID: {carrier_name} → {carrier_id}")
        
        bulk_ops.append(
            UpdateOne(
                {'carrierId': carrier_id},
                {
                    '$set': {
                        'carrierId': carrier_id,
                        'name': carrier_name,  # Use 'name' to match dashboard expectations
                        'carrierName': carrier_name,  # Keep both for compatibility
                        'npi': '',  # To be filled later
                        'status': 'active',
                        'lastUpdated': datetime.now(timezone.utc)
                    },
                    '$setOnInsert': {
                        '_id': ObjectId(),
                        'metadata': {
                            'region': 'US',
                            'planTypes': ['dental'],
                            'lastContractUpdate': datetime.now(timezone.utc)
                        }
                    }
                },
                upsert=True
            )
        )
    
    # Execute bulk operations
    if bulk_ops:
        result = carriers_registry.bulk_write(bulk_ops)
        print(f"Carriers registry populated: {result.upserted_count} inserted, {result.modified_count} updated")
        
        # Verify
        total_carriers = carriers_registry.count_documents({})
        print(f"Total carriers in registry: {total_carriers}")
        
        # Show first few carriers
        print("\nFirst 10 carriers in registry:")
        for carrier in carriers_registry.find().limit(10):
            print(f"- {carrier.get('name', 'Unknown')} (ID: {carrier.get('carrierId', 'Unknown')})")
    else:
        print("No carriers to insert")

if __name__ == '__main__':
    populate_carriers_registry() 