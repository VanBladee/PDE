// scripts/bootstrap-dev-data.ts
import { MongoClient, ObjectId } from 'mongodb';
import { createHash } from 'crypto';
import dotenv from 'dotenv';

dotenv.config();

const seedFlag = { __seed: true }; // marker for cleanup/idempotency

function stableObjectId(seed: string): ObjectId {
  const hex = createHash('sha1').update(seed).digest('hex').slice(0, 24);
  return new ObjectId(hex);
}

function daysAgo(n: number) {
  const d = new Date();
  d.setDate(d.getDate() - n);
  return d;
}

async function bootstrapDevData() {
  const appEnv = process.env.APP_ENV || process.env.NODE_ENV || 'dev';
  if (!['dev', 'stage', 'development', 'staging'].includes(appEnv)) {
    console.log(`Skipping bootstrap: APP_ENV="${appEnv}" is not dev/stage`);
    return;
  }

  const uri = process.env.MONGO_URI || 'mongodb://localhost:27017';
  const client = new MongoClient(uri);

  try {
    await client.connect();
    console.log('Connected to MongoDB for dev data bootstrap');

    const registry = client.db('registry');
    const activity = client.db('activity');
    const crucible = client.db('crucible');

    // 1) Locations (string _id for simplicity; pipeline compares _id equality)
    const locations = [
      { _id: 'PROVO', code: 'PROVO', name: 'Provo Office', state: 'UT', active: true },
      { _id: 'VEGAS', code: 'VEGAS', name: 'Las Vegas Office', state: 'NV', active: true },
    ];

    for (const loc of locations) {
      const { _id, ...locFields } = loc;
      await registry.collection('locations').updateOne(
        { code: loc.code },
        { $set: { ...locFields, ...seedFlag }, $setOnInsert: { _id } },
        { upsert: true }
      );
    }
    console.log('✓ Upserted locations:', locations.map(l => l.code).join(', '));

    // 2) Jobs — ensure two recent jobs (last 15 days) to enable NETWORK_MISMATCH and pivot in 90d windows
    const jobs = [
      {
        checkNumber: 'DLT-2024-001',
        locationId: 'PROVO',
        payment: { carrierName: 'DELTA', dateIssued: daysAgo(120).toISOString().slice(0,10), checkAmt: 2450, checkNumber: 'DLT-2024-001' },
        status: 'processed',
        createdAt: daysAgo(120),
      },
      {
        checkNumber: 'DLT-2024-002',
        locationId: 'VEGAS',
        payment: { carrierName: 'DELTA', dateIssued: daysAgo(90).toISOString().slice(0,10), checkAmt: 1850, checkNumber: 'DLT-2024-002' },
        status: 'processed',
        createdAt: daysAgo(90),
      },
      {
        checkNumber: 'AET-RECENT-001',
        locationId: 'PROVO',
        payment: { carrierName: 'AETNA', dateIssued: daysAgo(10).toISOString().slice(0,10), checkAmt: 3200, checkNumber: 'AET-RECENT-001' },
        status: 'processed',
        createdAt: daysAgo(10),
      },
      {
        checkNumber: 'AET-RECENT-002',
        locationId: 'VEGAS',
        payment: { carrierName: 'AETNA', dateIssued: daysAgo(15).toISOString().slice(0,10), checkAmt: 2100, checkNumber: 'AET-RECENT-002' },
        status: 'processed',
        createdAt: daysAgo(15),
      },
    ];

    for (const job of jobs) {
      await activity.collection('jobs').updateOne(
        { 'payment.checkNumber': job.checkNumber },
        {
          $set: { locationId: job.locationId, payment: job.payment, status: job.status, createdAt: job.createdAt, ...seedFlag },
          $setOnInsert: { _id: stableObjectId(`job:${job.checkNumber}`) },
        },
        { upsert: true }
      );
    }
    console.log('✓ Upserted jobs:', jobs.map(j => j.checkNumber).join(', '));

    // 3) Claims — 8 claims across those jobs, 3–5 procedures each (numbers, not strings)
    const procedures = [
      { code: 'D0120', name: 'Periodic oral evaluation' },
      { code: 'D0140', name: 'Limited oral evaluation' },
      { code: 'D0150', name: 'Comprehensive oral evaluation' },
      { code: 'D1110', name: 'Prophylaxis - adult' },
      { code: 'D2391', name: 'Composite - one surface, posterior' },
    ];

    const claimDistribution: Array<{ checkNumber: string; count: number }> = [
      { checkNumber: 'DLT-2024-001', count: 2 },
      { checkNumber: 'DLT-2024-002', count: 2 },
      { checkNumber: 'AET-RECENT-001', count: 2 },
      { checkNumber: 'AET-RECENT-002', count: 2 },
    ];

    const claimDocs: any[] = [];
    let claimCounter = 0;

    for (const dist of claimDistribution) {
      const job = jobs.find(j => j.checkNumber === dist.checkNumber)!;
      for (let i = 0; i < dist.count; i++) {
        claimCounter++;
        const claimNumber = `CLM-${dist.checkNumber}-${i + 1}`;

        const procCount = 3 + Math.floor(Math.random() * 3); // 3..5
        const claimProcedures = Array.from({ length: procCount }).map((_, idx) => {
          const proc = procedures[idx % procedures.length]!;
          const base = 120 + idx * 40;
          const feeBilled = Math.round((base + Math.random() * 50) * 100) / 100;
          const allowedAmount = Math.round((feeBilled * 0.8) * 100) / 100;
          const insAmountPaid = Math.round((allowedAmount * 0.8) * 100) / 100;
          const writeOff = Math.round((feeBilled - allowedAmount) * 100) / 100;
          return {
            procCode: proc.code,
            procName: proc.name,
            feeBilled,
            allowedAmount,
            insAmountPaid,
            writeOff,
            deductible: 0,
          };
        });

        claimDocs.push({
          claimNumber,
          job_id: stableObjectId(`job:${dist.checkNumber}`),
          locationId: job.locationId, // string matches registry.locations _id
          data: {
            payment: { dateIssued: job.payment.dateIssued }, // helps index
            patients: [{
              patientId: `PAT${String(claimCounter).padStart(3, '0')}`,
              claims: [{
                claimId: claimNumber,
                date_received: new Date(job.payment.dateIssued),
                procedures: claimProcedures,
              }],
            }],
          },
          createdAt: new Date(),
          ...seedFlag,
        });
      }
    }

    for (const c of claimDocs) {
      await activity.collection('processedclaims').updateOne(
        { claimNumber: c.claimNumber },                     // stable business key
        { $set: c, $setOnInsert: { _id: stableObjectId(`claim:${c.claimNumber}`) } },
        { upsert: true }
      );
    }
    const totalProcs = claimDocs.reduce((n, d) => n + (d.data?.patients?.[0]?.claims?.[0]?.procedures?.length || 0), 0);
    console.log(`✓ Upserted ${claimDocs.length} claims with ${totalProcs} procedures`);

    // 4) Fee schedules — one doc per (location, schedule) with fee_schedules as an ARRAY
    // Descriptions align with extraction logic (carrier precedence & UCR).
    type FeeSchedSpec = { loc: string; desc: string; seedKey: string; base: number };
    const schedSpecs: FeeSchedSpec[] = [
      { loc: 'PROVO', desc: 'DELTA DENTAL PPO', seedKey: 'PROVO:DELTA', base: 95 },
      { loc: 'PROVO', desc: 'AETNA DENTAL PPO', seedKey: 'PROVO:AETNA', base: 92 },
      { loc: 'PROVO', desc: 'UCR FEE SCHEDULE', seedKey: 'PROVO:UCR',   base: 140 },
      { loc: 'VEGAS', desc: 'DELTA DENTAL PPO', seedKey: 'VEGAS:DELTA', base: 97 },
      { loc: 'VEGAS', desc: 'AETNA DENTAL PPO', seedKey: 'VEGAS:AETNA', base: 90 },
      { loc: 'VEGAS', desc: 'UCR FEE SCHEDULE', seedKey: 'VEGAS:UCR',   base: 150 },
    ];

    for (const spec of schedSpecs) {
      const fees = procedures.map((p, i) => ({
        ProcedureCode: p.code,
        Amount: Math.round((spec.base + i * 12 + Math.random() * 8) * 100) / 100,
      }));

      await crucible.collection('PDC_fee_schedules').updateOne(
        { location_id: spec.loc, 'fee_schedules.Description': spec.desc },
        {
          $set: {
            location_id: spec.loc,
            fee_schedules: [ { Description: spec.desc, fees } ], // ARRAY shape
            collected_at: daysAgo(20),
            ...seedFlag,
          },
          $setOnInsert: { _id: stableObjectId(`pdcfs:${spec.seedKey}`) },
        },
        { upsert: true }
      );
    }
    console.log(`✓ Upserted ${schedSpecs.length} fee schedules`);

    // 5) Provider credentialing statuses — cover all alerts
    // ALERTS:
    // - NETWORK_MISMATCH: OON but has paid claims in last 90d
    // - EXPIRING_SOON: term_date within 30 days
    // - STALE_DATA: last_verified_at older than 30 days
    // - PENDING_EFFECTIVE: effective_date in the future
    const providerStatuses = [
      // Active (no alert)
      {
        provider_npi: '1111111111',
        provider_name: 'Dr. Smith',
        tin: '11-1111111',
        location_id: 'PROVO',
        carrier: 'DELTA',
        plan: 'PPO',
        status: 'ACTIVE',
        effective_date: daysAgo(200),
        last_verified_at: daysAgo(3),
        verification_source: 'Portal',
        notes: 'Good standing',
      },
      // OON + paid in last 90d -> NETWORK_MISMATCH (AETNA recent claims exist above)
      {
        provider_npi: '2222222222',
        provider_name: 'Dr. Jones',
        tin: '22-2222222',
        location_id: 'VEGAS',
        carrier: 'AETNA',
        plan: 'PPO',
        status: 'OON',
        effective_date: daysAgo(400),
        last_verified_at: daysAgo(5),
        verification_source: 'Portal',
        notes: 'Expected mismatch test',
      },
      // Term date within 30 days -> EXPIRING_SOON
      {
        provider_npi: '3333333333',
        provider_name: 'Dr. Soon',
        tin: '33-3333333',
        location_id: 'PROVO',
        carrier: 'DELTA',
        plan: 'PPO',
        status: 'ACTIVE',
        effective_date: daysAgo(365),
        term_date: daysAgo(-20), // in 20 days
        last_verified_at: daysAgo(1),
        verification_source: 'Portal',
      },
      // Stale data -> STALE_DATA
      {
        provider_npi: '4444444444',
        provider_name: 'Dr. Stale',
        tin: '44-4444444',
        location_id: 'VEGAS',
        carrier: 'AETNA',
        plan: 'PPO',
        status: 'ACTIVE',
        effective_date: daysAgo(200),
        last_verified_at: daysAgo(45),
        verification_source: 'Portal',
      },
      // Pending effective in future -> PENDING_EFFECTIVE
      {
        provider_npi: '5555555555',
        provider_name: 'Dr. Pending',
        tin: '55-5555555',
        location_id: 'PROVO',
        carrier: 'DELTA',
        plan: 'PPO',
        status: 'PENDING',
        effective_date: daysAgo(-10), // in 10 days
        last_verified_at: daysAgo(2),
        verification_source: 'Portal',
      },
      // Terminated -> TERMINATED (no special alert unless combined)
      {
        provider_npi: '6666666666',
        provider_name: 'Dr. Term',
        tin: '66-6666666',
        location_id: 'VEGAS',
        carrier: 'DELTA',
        plan: 'PPO',
        status: 'TERMINATED',
        effective_date: daysAgo(500),
        term_date: daysAgo(60),
        last_verified_at: daysAgo(3),
        verification_source: 'Portal',
      },
    ];

    for (const ps of providerStatuses) {
      await crucible.collection('PDC_provider_status').updateOne(
        { provider_npi: ps.provider_npi, location_id: ps.location_id, carrier: ps.carrier },
        {
          $set: { ...ps, ...seedFlag },
          $setOnInsert: { _id: stableObjectId(`pdcps:${ps.provider_npi}:${ps.location_id}:${ps.carrier}`) },
        },
        { upsert: true }
      );
    }
    console.log(`✓ Upserted ${providerStatuses.length} provider statuses`);

    console.log('\n📊 Bootstrap Summary:');
    console.log(`  - Locations: ${locations.length}`);
    console.log(`  - Jobs: ${jobs.length}`);
    console.log(`  - Claims: ${claimDocs.length}`);
    console.log(`  - Fee Schedules: ${schedSpecs.length}`);
    console.log(`  - Provider Status: ${providerStatuses.length}`);
    console.log('\n✨ Bootstrap completed successfully!');
  } catch (err) {
    console.error('Error bootstrapping dev data:', err);
    process.exitCode = 1;
  } finally {
    await client.close();
  }
}

bootstrapDevData();
