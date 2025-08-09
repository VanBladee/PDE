import { CredentialingService } from "../../src/services/credentialing.service";

const mockProviderData = [
  {
    provider_npi: "1234567890",
    provider_name: "Dr. Smith",
    tin: "12-3456789",
    location_id: "PROVO",
    carrier: "DELTA",
    plan: "PPO",
    status: "ACTIVE",
    effective_date: "2023-01-01",
    term_date: "2025-12-31",
    last_verified_at: new Date().toISOString(),
    verification_source: "Portal",
    source_url: "https://provider.delta.com",
    notes: "Verified via portal",
    is_manual_override: false,
    override_by: null,
    override_at: null,
    alerts: []
  },
  {
    provider_npi: "0987654321",
    provider_name: "Dr. Jones",
    tin: "98-7654321",
    location_id: "VEGAS",
    carrier: "AETNA",
    plan: null,
    status: "OON",
    effective_date: "2023-06-01",
    term_date: null,
    last_verified_at: "2023-06-01T00:00:00Z",
    verification_source: "Manual",
    source_url: null,
    notes: "Out of network",
    is_manual_override: true,
    override_by: "admin@example.com",
    override_at: "2023-06-01T00:00:00Z",
    alerts: ["NETWORK_MISMATCH", "STALE_DATA"]
  }
];

function makeSvc() {
  const fakeDb: any = {
    collection: () => ({
      aggregate: jest.fn().mockReturnValue({ 
        toArray: () => Promise.resolve(mockProviderData) 
      })
    }),
  };
  const fakeClient: any = { db: () => fakeDb };
  return new CredentialingService(fakeClient);
}

describe("CredentialingService (unit)", () => {
  describe("buildCredentialingPipeline", () => {
    it("builds pipeline with cross-DB lookup to registry.locations", () => {
      const svc = makeSvc();
      const pipeline = svc.buildCredentialingPipeline();
      
      const registryLookup = pipeline.find(stage => 
        stage.$lookup && 
        stage.$lookup.from?.db === "registry" && 
        stage.$lookup.from?.coll === "locations"
      );
      
      expect(registryLookup).toBeDefined();
      expect(registryLookup.$lookup.let).toHaveProperty('locId');
      expect(registryLookup.$lookup.as).toBe('location');
    });

    it("contains cross-DB lookup to activity.processedclaims for NETWORK_MISMATCH", () => {
      const svc = makeSvc();
      const pipeline = svc.buildCredentialingPipeline();
      
      const activityLookup = pipeline.find(stage => 
        stage.$lookup && 
        stage.$lookup.from?.db === "activity" && 
        stage.$lookup.from?.coll === "processedclaims"
      );
      
      expect(activityLookup).toBeDefined();
      expect(activityLookup.$lookup.let).toHaveProperty('providerNpi');
      expect(activityLookup.$lookup.let).toHaveProperty('locationId');
      expect(activityLookup.$lookup.let).toHaveProperty('carrier');
      expect(activityLookup.$lookup.as).toBe('recentPaidClaims');
    });

    it("includes alert calculation stage", () => {
      const svc = makeSvc();
      const pipeline = svc.buildCredentialingPipeline();
      
      // Find the stage that adds alerts
      const alertStage = pipeline.find(stage => 
        stage.$addFields && stage.$addFields.alerts
      );
      
      expect(alertStage).toBeDefined();
      const alertsFilter = alertStage.$addFields.alerts.$filter;
      expect(alertsFilter).toBeDefined();
      expect(alertsFilter.input).toHaveLength(4); // 4 alert types
    });

    it("applies location filter", () => {
      const svc = makeSvc();
      const pipeline = svc.buildCredentialingPipeline({
        locations: ["PROVO", "VEGAS"]
      });
      
      const matchStage = pipeline.find(stage => 
        stage.$match && stage.$match.location_id
      );
      
      expect(matchStage).toBeDefined();
      expect(matchStage.$match.location_id).toEqual({ $in: ["PROVO", "VEGAS"] });
    });

    it("applies carrier filter", () => {
      const svc = makeSvc();
      const pipeline = svc.buildCredentialingPipeline({
        carriers: ["DELTA", "AETNA"]
      });
      
      const matchStage = pipeline.find(stage => 
        stage.$match && stage.$match.carrier
      );
      
      expect(matchStage).toBeDefined();
      expect(matchStage.$match.carrier).toEqual({ $in: ["DELTA", "AETNA"] });
    });

    it("applies status filter", () => {
      const svc = makeSvc();
      const pipeline = svc.buildCredentialingPipeline({
        status: "ACTIVE"
      });
      
      const matchStage = pipeline.find(stage => 
        stage.$match && stage.$match.status
      );
      
      expect(matchStage).toBeDefined();
      expect(matchStage.$match.status).toBe("ACTIVE");
    });

    it("applies issuesOnly filter", () => {
      const svc = makeSvc();
      const pipeline = svc.buildCredentialingPipeline({
        issuesOnly: true
      });
      
      const issuesMatchStage = pipeline.find(stage => 
        stage.$match && stage.$match.$expr && 
        stage.$match.$expr.$gt && 
        stage.$match.$expr.$gt[0].$size === "$alerts"
      );
      
      expect(issuesMatchStage).toBeDefined();
    });

    it("applies date range filter", () => {
      const svc = makeSvc();
      const pipeline = svc.buildCredentialingPipeline({
        start: "2024-01-01",
        end: "2024-12-31"
      });
      
      const dateMatchStage = pipeline.find(stage => 
        stage.$match && stage.$match.last_verified_obj
      );
      
      expect(dateMatchStage).toBeDefined();
      expect(dateMatchStage.$match.last_verified_obj.$gte).toEqual(new Date("2024-01-01"));
      expect(dateMatchStage.$match.last_verified_obj.$lte).toEqual(new Date("2024-12-31"));
    });

    it("includes proper sort order", () => {
      const svc = makeSvc();
      const pipeline = svc.buildCredentialingPipeline();
      
      const sortStage = pipeline[pipeline.length - 1];
      expect(sortStage.$sort).toEqual({
        provider_name: 1,
        location_id: 1,
        carrier: 1
      });
    });

    it("projects all required fields", () => {
      const svc = makeSvc();
      const pipeline = svc.buildCredentialingPipeline();
      
      const projectStage = pipeline.find(stage => stage.$project && stage.$project._id === 0);
      
      expect(projectStage).toBeDefined();
      expect(projectStage.$project).toMatchObject({
        _id: 0,
        provider_npi: 1,
        provider_name: 1,
        tin: 1,
        location_id: 1,
        carrier: 1,
        status: 1,
        alerts: 1
      });
    });
  });

  describe("getCredentialingStatus", () => {
    it("returns rows and summary structure", async () => {
      const svc = makeSvc();
      const result = await svc.getCredentialingStatus();
      
      expect(result).toHaveProperty('rows');
      expect(result).toHaveProperty('summary');
      expect(result.summary).toMatchObject({
        totalRows: 2,
        dateRange: { start: undefined, end: undefined },
        lastUpdated: expect.any(Date)
      });
    });

    it("returns rows with proper structure", async () => {
      const svc = makeSvc();
      const result = await svc.getCredentialingStatus();
      
      expect(result.rows).toHaveLength(2);
      expect(result.rows[0]).toMatchObject({
        provider_npi: expect.any(String),
        provider_name: expect.any(String),
        tin: expect.any(String),
        location_id: expect.any(String),
        carrier: expect.any(String),
        status: expect.any(String),
        alerts: expect.any(Array)
      });
    });

    it("includes date range in summary when provided", async () => {
      const svc = makeSvc();
      const result = await svc.getCredentialingStatus({
        start: "2024-01-01",
        end: "2024-12-31"
      });
      
      expect(result.summary.dateRange).toEqual({
        start: "2024-01-01",
        end: "2024-12-31"
      });
    });

    it("handles empty results", async () => {
      const fakeDb: any = {
        collection: () => ({
          aggregate: jest.fn().mockReturnValue({ 
            toArray: () => Promise.resolve([]) 
          })
        }),
      };
      const fakeClient: any = { db: () => fakeDb };
      const svc = new CredentialingService(fakeClient);
      
      const result = await svc.getCredentialingStatus();
      
      expect(result.rows).toEqual([]);
      expect(result.summary.totalRows).toBe(0);
    });
  });

  describe("alert computation logic", () => {
    it("correctly identifies NETWORK_MISMATCH alert condition", () => {
      const svc = makeSvc();
      const pipeline = svc.buildCredentialingPipeline();
      
      const alertStage = pipeline.find(stage => 
        stage.$addFields && stage.$addFields.alerts
      );
      
      const networkMismatchCondition = alertStage.$addFields.alerts.$filter.input[0];
      expect(networkMismatchCondition.$cond[0].$and).toBeDefined();
      expect(networkMismatchCondition.$cond[0].$and[0]).toEqual({ $eq: ["$status", "OON"] });
      expect(networkMismatchCondition.$cond[0].$and[1].$gt[0]).toEqual({ $size: "$recentPaidClaims" });
      expect(networkMismatchCondition.$cond[1]).toBe("NETWORK_MISMATCH");
    });

    it("correctly identifies EXPIRING_SOON alert condition", () => {
      const svc = makeSvc();
      const pipeline = svc.buildCredentialingPipeline();
      
      const alertStage = pipeline.find(stage => 
        stage.$addFields && stage.$addFields.alerts
      );
      
      const expiringSoonCondition = alertStage.$addFields.alerts.$filter.input[1];
      expect(expiringSoonCondition.$cond[0].$and).toBeDefined();
      expect(expiringSoonCondition.$cond[1]).toBe("EXPIRING_SOON");
    });

    it("correctly identifies STALE_DATA alert condition", () => {
      const svc = makeSvc();
      const pipeline = svc.buildCredentialingPipeline();
      
      const alertStage = pipeline.find(stage => 
        stage.$addFields && stage.$addFields.alerts
      );
      
      const staleDataCondition = alertStage.$addFields.alerts.$filter.input[2];
      expect(staleDataCondition.$cond[0].$and).toBeDefined();
      expect(staleDataCondition.$cond[1]).toBe("STALE_DATA");
    });

    it("correctly identifies PENDING_EFFECTIVE alert condition", () => {
      const svc = makeSvc();
      const pipeline = svc.buildCredentialingPipeline();
      
      const alertStage = pipeline.find(stage => 
        stage.$addFields && stage.$addFields.alerts
      );
      
      const pendingEffectiveCondition = alertStage.$addFields.alerts.$filter.input[3];
      expect(pendingEffectiveCondition.$cond[0].$and).toBeDefined();
      expect(pendingEffectiveCondition.$cond[0].$and[0]).toEqual({ $eq: ["$status", "PENDING"] });
      expect(pendingEffectiveCondition.$cond[1]).toBe("PENDING_EFFECTIVE");
    });
  });

  describe("date conversion handling", () => {
    it("adds date conversion fields for comparison", () => {
      const svc = makeSvc();
      const pipeline = svc.buildCredentialingPipeline();
      
      const dateConversionStage = pipeline.find(stage => 
        stage.$addFields && stage.$addFields.effective_date_obj
      );
      
      expect(dateConversionStage).toBeDefined();
      expect(dateConversionStage.$addFields).toHaveProperty('effective_date_obj');
      expect(dateConversionStage.$addFields).toHaveProperty('term_date_obj');
      expect(dateConversionStage.$addFields).toHaveProperty('last_verified_obj');
    });
  });
});