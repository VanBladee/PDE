import { MongoClient } from 'mongodb';

interface HealthCheckResult {
  database: string;
  collections: string[];
  violations: string[];
  stats: {
    [collection: string]: {
      count: number;
      indexes: number;
    };
  };
}

async function checkDbHealth() {
  const mongoUri = process.env.MONGO_URI;
  if (!mongoUri) {
    console.error('MONGO_URI environment variable is required');
    process.exit(1);
  }

  const client = new MongoClient(mongoUri);
  const results: HealthCheckResult[] = [];
  let hasViolations = false;

  try {
    await client.connect();
    console.log('Connected to MongoDB for health check\n');

    // Check activity database
    console.log('Checking activity database...');
    const activityDb = client.db('activity');
    const activityCollections = await activityDb.listCollections().toArray();
    const activityResult: HealthCheckResult = {
      database: 'activity',
      collections: activityCollections.map(c => c.name),
      violations: [],
      stats: {}
    };

    // Check for PDC_ collections in activity (violation)
    for (const coll of activityCollections) {
      if (coll.name.startsWith('PDC_')) {
        activityResult.violations.push(`Found PDC collection in activity: ${coll.name}`);
        hasViolations = true;
      }
      
      // Get stats
      const collection = activityDb.collection(coll.name);
      const count = await collection.countDocuments();
      const indexes = await collection.listIndexes().toArray();
      activityResult.stats[coll.name] = { count, indexes: indexes.length };
    }
    results.push(activityResult);

    // Check registry database
    console.log('Checking registry database...');
    const registryDb = client.db('registry');
    const registryCollections = await registryDb.listCollections().toArray();
    const registryResult: HealthCheckResult = {
      database: 'registry',
      collections: registryCollections.map(c => c.name),
      violations: [],
      stats: {}
    };

    for (const coll of registryCollections) {
      const collection = registryDb.collection(coll.name);
      const count = await collection.countDocuments();
      const indexes = await collection.listIndexes().toArray();
      registryResult.stats[coll.name] = { count, indexes: indexes.length };
    }
    results.push(registryResult);

    // Check crucible database
    console.log('Checking crucible database...');
    const crucibleDb = client.db('crucible');
    const crucibleCollections = await crucibleDb.listCollections().toArray();
    const crucibleResult: HealthCheckResult = {
      database: 'crucible',
      collections: crucibleCollections.map(c => c.name),
      violations: [],
      stats: {}
    };

    // Check required PDC_ collections exist
    const requiredPDCCollections = ['PDC_fee_schedules', 'PDC_provider_status'];
    for (const required of requiredPDCCollections) {
      if (!crucibleCollections.find(c => c.name === required)) {
        crucibleResult.violations.push(`Missing required collection: ${required}`);
        hasViolations = true;
      }
    }

    for (const coll of crucibleCollections) {
      const collection = crucibleDb.collection(coll.name);
      const count = await collection.countDocuments();
      const indexes = await collection.listIndexes().toArray();
      crucibleResult.stats[coll.name] = { count, indexes: indexes.length };
    }
    results.push(crucibleResult);

    // Print results
    console.log('\n=== DATABASE HEALTH CHECK RESULTS ===\n');
    
    for (const result of results) {
      console.log(`Database: ${result.database}`);
      console.log(`Collections: ${result.collections.join(', ') || '(none)'}`);
      
      if (result.violations.length > 0) {
        console.log(`⚠️  Violations:`);
        result.violations.forEach(v => console.log(`   - ${v}`));
      } else {
        console.log(`✅ No violations`);
      }
      
      console.log(`Stats:`);
      for (const [coll, stats] of Object.entries(result.stats)) {
        console.log(`  ${coll}: ${stats.count} documents, ${stats.indexes} indexes`);
      }
      console.log();
    }

    // Check cross-database lookup capability
    console.log('Testing cross-database lookup capability...');
    try {
      // Try a simple cross-db aggregation
      await crucibleDb.collection('PDC_provider_status').aggregate([
        { $limit: 1 },
        {
          $lookup: {
            from: { db: 'registry', coll: 'locations' },
            pipeline: [{ $limit: 1 }],
            as: 'test'
          }
        }
      ]).toArray();
      console.log('✅ Cross-database lookups supported\n');
    } catch (error: any) {
      console.log('⚠️  Cross-database lookups not supported:', error.message, '\n');
    }

    if (hasViolations) {
      console.log('❌ Health check failed: violations found');
      process.exit(1);
    } else {
      console.log('✅ Health check passed: all databases configured correctly');
    }

  } catch (error) {
    console.error('Error during health check:', error);
    process.exit(1);
  } finally {
    await client.close();
  }
}

// Run if called directly
if (require.main === module) {
  checkDbHealth().catch(console.error);
}

export { checkDbHealth };