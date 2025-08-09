// scripts/db-health.ts
import { MongoClient } from "mongodb";

type Check = { name: string; ok: boolean; details?: unknown };

function hasAllKeys(indexKey: Record<string, number>, keys: string[]) {
  return keys.every((k) => Object.prototype.hasOwnProperty.call(indexKey, k));
}

async function run() {
  const uri = process.env.MONGO_URI;
  const timeout = parseInt(process.env.MONGO_TIMEOUT_MS ?? "8000", 10);
  const asJson = process.argv.includes("--json");

  const out: { ok: boolean; checks: Check[]; server?: unknown; startedAt: string; finishedAt?: string } = {
    ok: false,
    checks: [],
    startedAt: new Date().toISOString(),
  };

  if (!uri) {
    out.checks.push({ name: "env:MONGO_URI", ok: false, details: "MONGO_URI is required" });
    print(out, asJson);
    process.exit(1);
  }

  const client = new MongoClient(uri, { serverSelectionTimeoutMS: timeout });
  try {
    await client.connect();
    out.checks.push({ name: "connect", ok: true });

    // Server info (best-effort)
    try {
      const info = await client.db("admin").admin().serverInfo();
      out.server = { version: info.version, gitVersion: info.gitVersion };
    } catch (e) {
      out.checks.push({ name: "serverInfo", ok: false, details: String(e) });
    }

    // --- Existence checks
    await exists(client, out, "activity", "processedclaims");
    await exists(client, out, "activity", "jobs");
    await exists(client, out, "crucible", "PDC_fee_schedules");
    await exists(client, out, "registry", "locations");

    // --- Sample doc sanity
    const pcSample = await client
      .db("activity")
      .collection("processedclaims")
      .findOne({}, { projection: { job_id: 1, locationId: 1, "data.patients.claims.procedures.procCode": 1 } });
    out.checks.push({
      name: "sample: activity.processedclaims",
      ok: !!pcSample,
      details: pcSample ? { hasJobId: !!(pcSample as any).job_id, hasLocationId: !!(pcSample as any).locationId } : "none",
    });

    // --- Index checks (best-effort; ignore permission errors)
    await hasIndex(client, out, "activity", "processedclaims", [
      "data.payment.dateIssued",
      "locationId",
      "data.patients.claims.procedures.procCode",
    ]);
    await hasIndex(client, out, "activity", "processedclaims", ["job_id"]);
    await hasIndex(client, out, "activity", "jobs", ["payment.dateIssued", "locationId", "payment.carrierName"]);
    await hasIndex(client, out, "crucible", "PDC_fee_schedules", ["location_id", "fee_schedules.Description", "collected_at"]);
    await hasIndex(client, out, "registry", "locations", ["code"]);

    // --- Negative check: PDC collections should NOT be in activity
    const wrong = await client.db("activity")
      .listCollections({ name: "PDC_fee_schedules" }, { nameOnly: true }).toArray();
    out.checks.push({ name: "activity.PDC_fee_schedules should NOT exist", ok: wrong.length === 0 });

    // --- Cross-DB $lookup smoke test
    const cross = await client
      .db("activity")
      .collection("processedclaims")
      .aggregate(
        [
          { $limit: 1 },
          { $lookup: { from: "jobs", localField: "job_id", foreignField: "_id", as: "job" } },
          { $lookup: { from: { db: "registry", coll: "locations" }, localField: "locationId", foreignField: "_id", as: "loc" } },
          {
            $lookup: {
              from: { db: "crucible", coll: "PDC_fee_schedules" },
              let: { loc: { $arrayElemAt: ["$loc.code", 0] } },
              pipeline: [{ $match: { $expr: { $eq: ["$location_id", "$$loc"] } } }, { $limit: 1 }],
              as: "sched",
            },
          },
          { $project: { jobSize: { $size: "$job" }, locSize: { $size: "$loc" }, schedSize: { $size: "$sched" } } },
        ],
        { allowDiskUse: true }
      )
      .toArray()
      .catch((e) => {
        out.checks.push({ name: "cross-db $lookup pipeline", ok: false, details: String(e) });
        return [];
      });

    if (cross?.[0]) {
      out.checks.push({ name: "cross-db $lookup works", ok: true, details: cross[0] });
    } else {
      out.checks.push({
        name: "cross-db $lookup works",
        ok: false,
        details: "no processedclaims sample or pipeline returned 0",
      });
    }

    out.ok = out.checks.every((c) => c.ok);
  } catch (e) {
    out.checks.push({ name: "connect", ok: false, details: String(e) });
    out.ok = false;
  } finally {
    out.finishedAt = new Date().toISOString();
    await client.close().catch(() => undefined);
  }

  print(out, asJson);
  process.exit(out.ok ? 0 : 1);
}

async function exists(client: MongoClient, out: { checks: Check[] }, dbName: string, coll: string) {
  const arr = await client.db(dbName).listCollections({ name: coll }, { nameOnly: true }).toArray();
  out.checks.push({ name: `exists: ${dbName}.${coll}`, ok: arr.length > 0 });
}

async function hasIndex(
  client: MongoClient,
  out: { checks: Check[] },
  db: string,
  coll: string,
  keys: string[]
) {
  try {
    const idx = await client.db(db).collection(coll).listIndexes().toArray();
    const found = idx.some((i) => hasAllKeys(i.key as Record<string, number>, keys));
    out.checks.push({ name: `indexes: ${db}.${coll} ⊇ [${keys.join(", ")}]`, ok: found });
  } catch (e) {
    out.checks.push({ name: `indexes: ${db}.${coll}`, ok: false, details: `listIndexes failed: ${String(e)}` });
  }
}

function print(out: any, asJson: boolean) {
  if (asJson) {
    console.log(JSON.stringify(out, null, 2));
    return;
  }
  console.log(`Mongo health: ${out.ok ? "OK" : "FAIL"}`);
  for (const c of out.checks) {
    console.log(`${c.ok ? "✓" : "✗"} ${c.name}${c.details ? " — " + JSON.stringify(c.details) : ""}`);
  }
  if (out.server) console.log("server:", JSON.stringify(out.server));
}

run().catch((e) => {
  console.error(e);
  process.exit(1);
});