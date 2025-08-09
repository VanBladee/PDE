import { MongoClient } from "mongodb";
import { MongoMemoryServer } from "mongodb-memory-server";

describe("DB Boundaries", () => {
  let mongod: MongoMemoryServer;
  let client: MongoClient;

  beforeAll(async () => {
    mongod = await MongoMemoryServer.create({
      binary: { version: "7.0.14" }
    });
    client = new MongoClient(mongod.getUri());
    await client.connect();
  });

  afterAll(async () => {
    await client.close();
    await mongod.stop();
  });

  it("enforces database boundaries for collections", async () => {
    // Verify activity database only contains allowed collections
    const activity = client.db("activity");
    await activity.collection("processedclaims").insertOne({ test: "claim1" });
    await activity.collection("jobs").insertOne({ test: "job1" });
    
    const activityColls = (await activity.listCollections({}, { nameOnly: true }).toArray()).map(c => c.name);
    expect(activityColls).toContain("processedclaims");
    expect(activityColls).toContain("jobs");
    expect(activityColls).not.toContain("PDC_fee_schedules");
    expect(activityColls).not.toContain("locations");

    // Verify registry database contains locations
    const registry = client.db("registry");
    await registry.collection("locations").insertOne({ test: "location1" });
    
    const registryColls = (await registry.listCollections({}, { nameOnly: true }).toArray()).map(c => c.name);
    expect(registryColls).toContain("locations");
    expect(registryColls).not.toContain("PDC_fee_schedules");

    // Verify crucible database contains PDC collections
    const crucible = client.db("crucible");
    await crucible.collection("PDC_fee_schedules").insertOne({ test: "schedule1" });
    await crucible.collection("PDC_provider_status").insertOne({ test: "provider1" });
    
    const crucibleColls = (await crucible.listCollections({}, { nameOnly: true }).toArray()).map(c => c.name);
    expect(crucibleColls).toContain("PDC_fee_schedules");
    expect(crucibleColls).toContain("PDC_provider_status");
    expect(crucibleColls).not.toContain("processedclaims");
    expect(crucibleColls).not.toContain("jobs");
  });
});