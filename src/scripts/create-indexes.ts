import { MongoClient } from 'mongodb';

async function createIndexes() {
  const mongoUri = process.env.MONGO_URI;
  if (!mongoUri) {
    console.error('MONGO_URI environment variable is required');
    process.exit(1);
  }

  const client = new MongoClient(mongoUri);

  try {
    await client.connect();
    console.log('Connected to MongoDB');

    // Activity database indexes
    const activity = client.db('activity');
    
    // processedclaims indexes
    console.log('Creating indexes for activity.processedclaims...');
    await activity.collection('processedclaims').createIndexes([
      { key: { 'data.patients.claims.date_received': -1 } },
      { key: { 'data.patients.claims.provider_npi': 1 } },
      { key: { 'data.locationId': 1 } },
      { key: { 'data.carrier': 1 } },
      { key: { 'data.patients.claims.procedures.code': 1 } },
      { key: { 'data.patients.claims.procedures.insAmountPaid': 1 } }
    ]);

    // jobs indexes
    console.log('Creating indexes for activity.jobs...');
    await activity.collection('jobs').createIndexes([
      { key: { status: 1, lastRun: -1 } },
      { key: { locationId: 1 } }
    ]);

    // Registry database indexes
    const registry = client.db('registry');
    
    // locations indexes
    console.log('Creating indexes for registry.locations...');
    await registry.collection('locations').createIndexes([
      { key: { code: 1 }, unique: true },
      { key: { name: 1 } }
    ]);

    // Crucible database indexes
    const crucible = client.db('crucible');
    
    // PDC_fee_schedules indexes
    console.log('Creating indexes for crucible.PDC_fee_schedules...');
    await crucible.collection('PDC_fee_schedules').createIndexes([
      { key: { locationId: 1, carrier: 1, procedureCode: 1 } },
      { key: { effectiveDate: -1 } }
    ]);

    // PDC_provider_status indexes
    console.log('Creating indexes for crucible.PDC_provider_status...');
    await crucible.collection('PDC_provider_status').createIndexes([
      { key: { provider_npi: 1, location_id: 1, carrier: 1 }, unique: true },
      { key: { status: 1 } },
      { key: { last_verified_at: -1 } },
      { key: { effective_date: 1 } },
      { key: { term_date: 1 } }
    ]);

    console.log('All indexes created successfully');
  } catch (error) {
    console.error('Error creating indexes:', error);
    process.exit(1);
  } finally {
    await client.close();
  }
}

// Run if called directly
if (require.main === module) {
  createIndexes().catch(console.error);
}

export { createIndexes };