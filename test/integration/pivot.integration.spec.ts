import { MongoClient, ObjectId } from "mongodb";
import { GenericContainer, StartedTestContainer } from "testcontainers";
import { UnifiedClaimsService } from "../../src/services/unified-claims.service";

// Note: These integration tests require MongoDB 7.0+ with cross-DB $lookup support
// In CI environments without this feature, these tests will be skipped
const describeIntegration = process.env.SKIP_CROSSDB_TESTS ? describe.skip : describe;

describeIntegration("UnifiedClaimsService (integration)", () => {
  let container: StartedTestContainer | null = null;
  let client: MongoClient;

  beforeAll(async () => {
    // Use real MongoDB if available (e.g., in CI), otherwise use testcontainers
    const mongoUri = process.env.MONGO_URI || process.env.MONGODB_URI;
    
    if (mongoUri) {
      console.log("Using real MongoDB instance");
      client = new MongoClient(mongoUri);
    } else {
      console.log("Starting MongoDB container");
      container = await new GenericContainer("mongo:7.0")
        .withExposedPorts(27017)
        .start();
      
      const uri = `mongodb://localhost:${container.getMappedPort(27017)}`;
      client = new MongoClient(uri);
    }
    
    await client.connect();

    // Seed test data across all databases
    const activity = client.db("activity");
    const registry = client.db("registry");
    const crucible = client.db("crucible");

    const locationId = new ObjectId();
    await registry.collection("locations").insertOne({ 
      _id: locationId, 
      code: "PROVO", 
      name: "Provo Clinic" 
    });

    const jobId = new ObjectId();
    await activity.collection("jobs").insertOne({
      _id: jobId, 
      locationId,
      payment: { 
        carrierName: "DELTA", 
        dateIssued: "2024-02-01", 
        checkAmt: 76.0 
      }
    });

    await activity.collection("processedclaims").insertOne({
      _id: new ObjectId(), 
      job_id: jobId, 
      locationId,
      data: {
        payment: { dateIssued: "2024-02-01" },
        patients: [{
          claims: [{
            date_received: new Date("2024-02-01"),
            procedures: [{
              procCode: "D0120", 
              feeBilled: "150", 
              allowedAmount: "95", 
              insAmountPaid: "76", 
              writeOff: "55"
            }]
          }]
        }]
      }
    });

    await crucible.collection("PDC_fee_schedules").insertOne({
      location_id: "PROVO",
      fee_schedules: [
        { 
          Description: "DELTA DENTAL PPO", 
          fees: [{ ProcedureCode: "D0120", Amount: "80" }] 
        },
        { 
          Description: "UCR FEE SCHEDULE",  
          fees: [{ ProcedureCode: "D0120", Amount: "100" }] 
        }
      ],
      collected_at: new Date("2024-02-01")
    });
  }, 60000); // 60 second timeout for container startup

  afterAll(async () => {
    await client.close();
    if (container) {
      await container.stop();
    }
  });

  it("computes pivot with cross-DB lookups and returns correct feeScheduled and metrics", async () => {
    const svc = new UnifiedClaimsService(client);
    const { rows, summary } = await svc.getFeeStrategyPivot({ 
      start: "2024-02-01", 
      end: "2024-02-29", 
      locations: ["PROVO"] 
    });
    
    expect(rows).toHaveLength(1);
    
    const row = rows[0];
    expect(row).toMatchObject({
      carrier: "DELTA",
      locationId: expect.any(String),
      locationCode: "PROVO",
      locationName: "Provo Clinic",
      procedure: "D0120",
      month: "2024-02",
      metrics: {
        billed: 150,
        allowed: 95,
        paid: 76,
        writeOff: 55,
        writeOffPct: expect.closeTo(36.67, 2),
        feeScheduled: 80, // Should use DELTA-specific fee schedule
        scheduleVariance: expect.closeTo(46.67, 2),
        claimCount: 1
      },
      hasIssues: false
    });
    
    expect(summary).toMatchObject({
      totalRows: 1,
      dateRange: {
        start: "2024-02-01",
        end: "2024-02-29"
      },
      lastUpdated: expect.any(Date)
    });
  });

  it("aggregates multiple claims correctly", async () => {
    // Add another claim for same month/location/procedure
    const activity = client.db("activity");
    const jobId = (await activity.collection("jobs").findOne({}))!._id;
    const locationId = (await client.db("registry").collection("locations").findOne({}))!._id;
    
    await activity.collection("processedclaims").insertOne({
      _id: new ObjectId(),
      job_id: jobId,
      locationId,
      data: {
        payment: { dateIssued: "2024-02-15" },
        patients: [{
          claims: [{
            date_received: new Date("2024-02-15"),
            procedures: [{
              procCode: "D0120",
              feeBilled: "150",
              allowedAmount: "95",
              insAmountPaid: "76",
              writeOff: "55"
            }]
          }]
        }]
      }
    });

    const svc = new UnifiedClaimsService(client);
    const { rows } = await svc.getFeeStrategyPivot({
      start: "2024-02-01",
      end: "2024-02-29"
    });

    expect(rows).toHaveLength(1);
    expect(rows[0].metrics.claimCount).toBe(2);
    expect(rows[0].metrics.billed).toBe(300); // 150 + 150
    expect(rows[0].metrics.allowed).toBe(190); // 95 + 95
    expect(rows[0].metrics.paid).toBe(152); // 76 + 76
    expect(rows[0].metrics.writeOff).toBe(110); // 55 + 55
  });

  it("respects database boundaries", async () => {
    // Create PDC collection in wrong database (activity)
    const activity = client.db("activity");
    await activity.collection("PDC_fee_schedules").insertOne({
      location_id: "PROVO",
      fee_schedules: [{
        Description: "WRONG DB SCHEDULE",
        fees: [{ ProcedureCode: "D0120", Amount: "999" }]
      }],
      collected_at: new Date()
    });

    const svc = new UnifiedClaimsService(client);
    const { rows } = await svc.getFeeStrategyPivot({
      locations: ["PROVO"]
    });

    // Should still use crucible DB fee schedule (80), not activity DB (999)
    expect(rows[0].metrics.feeScheduled).toBe(80);
  });

  it("handles missing fee schedules", async () => {
    // Add claim for location without fee schedule
    const registry = client.db("registry");
    const activity = client.db("activity");
    
    const vegasId = new ObjectId();
    await registry.collection("locations").insertOne({
      _id: vegasId,
      code: "VEGAS",
      name: "Vegas Clinic"
    });

    const jobId = (await activity.collection("jobs").findOne({}))!._id;
    
    await activity.collection("processedclaims").insertOne({
      _id: new ObjectId(),
      job_id: jobId,
      locationId: vegasId,
      data: {
        patients: [{
          claims: [{
            date_received: new Date("2024-02-01"),
            procedures: [{
              procCode: "D0140",
              feeBilled: "120",
              allowedAmount: "100",
              insAmountPaid: "80",
              writeOff: "20"
            }]
          }]
        }]
      }
    });

    const svc = new UnifiedClaimsService(client);
    const { rows } = await svc.getFeeStrategyPivot({
      locations: ["VEGAS"]
    });

    expect(rows).toHaveLength(1);
    expect(rows[0].metrics.feeScheduled).toBeNull();
    expect(rows[0].metrics.scheduleVariance).toBeNull();
  });

  it("applies filters correctly", async () => {
    // Add claims for different months
    const activity = client.db("activity");
    const jobId = (await activity.collection("jobs").findOne({}))!._id;
    const locationId = (await client.db("registry").collection("locations").findOne({}))!._id;
    
    await activity.collection("processedclaims").insertOne({
      _id: new ObjectId(),
      job_id: jobId,
      locationId,
      data: {
        patients: [{
          claims: [{
            date_received: new Date("2024-03-15"),
            procedures: [{
              procCode: "D0140",
              feeBilled: "200",
              allowedAmount: "150",
              insAmountPaid: "120",
              writeOff: "50"
            }]
          }]
        }]
      }
    });

    const svc = new UnifiedClaimsService(client);
    
    // Filter by date range
    const febResult = await svc.getFeeStrategyPivot({
      start: "2024-02-01",
      end: "2024-02-29"
    });
    
    const marchResult = await svc.getFeeStrategyPivot({
      start: "2024-03-01",
      end: "2024-03-31"
    });
    
    // February should have D0120 claims
    expect(febResult.rows.every(r => r.month === "2024-02")).toBe(true);
    expect(febResult.rows.some(r => r.procedure === "D0120")).toBe(true);
    
    // March should have D0140 claim
    expect(marchResult.rows).toHaveLength(1);
    expect(marchResult.rows[0].month).toBe("2024-03");
    expect(marchResult.rows[0].procedure).toBe("D0140");
  });
});