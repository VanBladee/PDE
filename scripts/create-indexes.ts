// scripts/create-indexes.ts
import { MongoClient } from "mongodb";

export async function run() {
  const uri = process.env.MONGO_URI;
  if (!uri) {
    console.error("MONGO_URI env var is required");
    process.exit(1);
  }

  const client = new MongoClient(uri);
  try {
    await client.connect();

    const activity = client.db("activity");
    const crucible = client.db("crucible");
    const registry = client.db("registry");

    await activity.collection("processedclaims").createIndexes([
      { key: { "data.payment.dateIssued": -1, locationId: 1, "data.patients.claims.procedures.procCode": 1 } },
      { key: { job_id: 1 } },
    ]);

    await activity.collection("jobs").createIndexes([
      { key: { "payment.dateIssued": -1, locationId: 1, "payment.carrierName": 1 } },
    ]);

    await crucible.collection("PDC_fee_schedules").createIndexes([
      { key: { location_id: 1, "fee_schedules.Description": 1, collected_at: -1 } },
    ]);

    await registry.collection("locations").createIndexes([
      { key: { code: 1 }, unique: true },
    ]);

    console.log("Indexes created ✅");
  } finally {
    await client.close();
  }
}

// Auto-run when executed via `node dist/scripts/create-indexes.js`
/* eslint-disable @typescript-eslint/no-explicit-any */
const isCJS = typeof require !== "undefined" && (require as any).main === module;
if (isCJS) {
  run().catch((e) => {
    console.error(e);
    process.exit(1);
  });
}
