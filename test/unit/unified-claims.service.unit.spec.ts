import { UnifiedClaimsService } from "../../src/services/unified-claims.service";

const aggResult = [{
  carrier: "Delta Dental",
  locationId: "loc123",
  locationCode: "PROVO",
  locationName: "Provo Clinic",
  procedure: "D0120",
  month: "2024-02",
  metrics: { 
    billed: 150, 
    allowed: 95, 
    paid: 76, 
    writeOff: 55, 
    writeOffPct: 36.67, 
    feeScheduled: 80, 
    scheduleVariance: 46.67, 
    claimCount: 1 
  },
  hasIssues: false
}];

function makeSvc() {
  const fakeDb: any = {
    collection: () => ({
      aggregate: jest.fn().mockReturnValue({ 
        toArray: () => Promise.resolve(aggResult) 
      })
    }),
  };
  const fakeClient: any = { db: () => fakeDb };
  return new UnifiedClaimsService(fakeClient);
}

// Helper to check if stage is an unwind (handles both formats)
function isUnwindStage(stage: any, path: string): boolean {
  if (typeof stage.$unwind === 'string') {
    return stage.$unwind === path;
  }
  if (typeof stage.$unwind === 'object' && stage.$unwind.path) {
    return stage.$unwind.path === path;
  }
  return false;
}

describe("UnifiedClaimsService (unit)", () => {
  it("builds the correct pipeline structure with cross-DB lookups", () => {
    const svc = makeSvc();
    const pipeline = svc.buildPivotPipeline({ 
      start: "2024-02-01", 
      end: "2024-02-29", 
      locations: ["PROVO"] 
    });
    
    // Ensure cross-DB $lookup remains in code (contract check)
    const pipelineStr = JSON.stringify(pipeline);
    expect(pipelineStr).toContain('"db":"crucible"');
    expect(pipelineStr).toContain('"coll":"PDC_fee_schedules"');
    expect(pipelineStr).toContain('"db":"registry"');
    expect(pipelineStr).toContain('"coll":"locations"');
    expect(Array.isArray(pipeline)).toBe(true);
    
    // Check pipeline stages
    expect(pipeline[0]).toHaveProperty('$match');
    expect(pipeline[0].$match).toMatchObject({
      'data.patients': { $exists: true, $ne: [] }
    });
    
    // Check unwinds (tolerant of both formats)
    expect(isUnwindStage(pipeline[1], '$data.patients')).toBe(true);
    expect(isUnwindStage(pipeline[2], '$data.patients.claims')).toBe(true);
    expect(isUnwindStage(pipeline[3], '$data.patients.claims.procedures')).toBe(true);
    
    // Check filter was applied
    const hasFilterMatch = pipeline.some(stage => 
      stage.$match && stage.$match['_id.locationCode']
    );
    expect(hasFilterMatch).toBe(true);
  });

  it("contains cross-DB lookup to registry.locations", () => {
    const svc = makeSvc();
    const pipeline = svc.buildPivotPipeline();
    
    const registryLookup = pipeline.find(stage => 
      stage.$lookup && 
      stage.$lookup.from?.db === "registry" && 
      stage.$lookup.from?.coll === "locations"
    );
    
    expect(registryLookup).toBeDefined();
    expect(registryLookup.$lookup.let).toHaveProperty('locId');
    expect(registryLookup.$lookup.as).toBe('loc');
  });

  it("contains cross-DB lookup to crucible.PDC_fee_schedules", () => {
    const svc = makeSvc();
    const pipeline = svc.buildPivotPipeline();
    
    const crucibleLookup = pipeline.find(stage => 
      stage.$lookup && 
      stage.$lookup.from?.db === "crucible" && 
      stage.$lookup.from?.coll === "PDC_fee_schedules"
    );
    
    expect(crucibleLookup).toBeDefined();
    expect(crucibleLookup.$lookup.let).toHaveProperty('loc');
    expect(crucibleLookup.$lookup.let).toHaveProperty('code');
    expect(crucibleLookup.$lookup.let).toHaveProperty('carrierRaw');
    expect(crucibleLookup.$lookup.as).toBe('sched');
  });

  it("groups by Carrier × Location × Procedure × Month", () => {
    const svc = makeSvc();
    const pipeline = svc.buildPivotPipeline();
    
    const groupStage = pipeline.find(stage => stage.$group);
    
    expect(groupStage).toBeDefined();
    expect(groupStage.$group._id).toEqual({
      carrier: "$carrierName",
      locationId: "$locationId",
      locationCode: "$locationCode",
      locationName: "$locationName",
      procedure: "$data.patients.claims.procedures.procCode",
      month: "$month"
    });
    
    // Check aggregations
    expect(groupStage.$group.billed).toEqual({ $sum: "$feeBilled" });
    expect(groupStage.$group.allowed).toEqual({ $sum: "$allowed" });
    expect(groupStage.$group.paid).toEqual({ $sum: "$paid" });
    expect(groupStage.$group.writeOff).toEqual({ $sum: "$writeOff" });
    expect(groupStage.$group.claimCount).toEqual({ $sum: 1 });
  });

  it("returns {rows, summary} shape per OpenAPI", async () => {
    const svc = makeSvc();
    const result = await svc.getFeeStrategyPivot({ 
      start: "2024-02-01", 
      end: "2024-02-29" 
    });
    
    expect(result).toHaveProperty('rows');
    expect(result).toHaveProperty('summary');
    expect(result.rows).toEqual(aggResult);
    expect(result.summary).toMatchObject({
      totalRows: 1,
      dateRange: {
        start: "2024-02-01",
        end: "2024-02-29"
      },
      lastUpdated: expect.any(Date)
    });
  });

  it("applies all filter types to pipeline", () => {
    const svc = makeSvc();
    const pipeline = svc.buildPivotPipeline({
      start: "2024-01-01",
      end: "2024-12-31",
      locations: ["PROVO", "VEGAS"],
      carriers: ["DELTA", "AETNA"],
      procedures: ["D0120", "D0140"],
      minCount: 5
    });

    // Find the filter match stage (should be second to last)
    const filterStage = pipeline[pipeline.length - 2];
    expect(filterStage.$match).toBeDefined();
    
    const match = filterStage.$match;
    expect(match.dosRecv.$gte).toEqual(new Date("2024-01-01"));
    expect(match.dosRecv.$lte).toEqual(new Date("2024-12-31"));
    expect(match['_id.locationCode'].$in).toEqual(["PROVO", "VEGAS"]);
    expect(match['_id.carrier'].$in).toEqual(["DELTA", "AETNA"]);
    expect(match['_id.procedure'].$in).toEqual(["D0120", "D0140"]);
    expect(match.claimCount.$gte).toBe(5);
  });

  it("builds pipeline without filters", () => {
    const svc = makeSvc();
    const pipeline = svc.buildPivotPipeline();
    
    // Should not have the filter match stage
    const hasFilterMatch = pipeline.some(stage => 
      stage.$match && (stage.$match.dosRecv || stage.$match['_id.locationCode'])
    );
    expect(hasFilterMatch).toBe(false);
  });

  it("verifies fee schedule precedence logic in pipeline", () => {
    const svc = makeSvc();
    const pipeline = svc.buildPivotPipeline();
    
    // Find the fee schedule lookup stage
    const feeScheduleLookup = pipeline.find(stage => 
      stage.$lookup && stage.$lookup.from?.coll === "PDC_fee_schedules"
    );
    
    expect(feeScheduleLookup).toBeDefined();
    const subPipeline = feeScheduleLookup.$lookup.pipeline;
    
    // Check precedence calculation exists
    const precedenceStage = subPipeline.find((stage: any) => 
      stage.$addFields && stage.$addFields._precedence
    );
    expect(precedenceStage).toBeDefined();
    
    // Verify precedence logic: carrier match = 1, global = 3, default = 2
    const precedenceLogic = precedenceStage.$addFields._precedence;
    expect(precedenceLogic.$cond[0]).toBe("$_isCarrierMatch");
    expect(precedenceLogic.$cond[1]).toBe(1);
    expect(precedenceLogic.$cond[2].$cond[0]).toBe("$_isGlobal");
    expect(precedenceLogic.$cond[2].$cond[1]).toBe(3);
    expect(precedenceLogic.$cond[2].$cond[2]).toBe(2);
  });

  it("calculates metrics correctly in pipeline", () => {
    const svc = makeSvc();
    const pipeline = svc.buildPivotPipeline();
    
    // Find the metrics calculation stage
    const metricsStage = pipeline.find(stage => 
      stage.$addFields && stage.$addFields.writeOffPct
    );
    
    expect(metricsStage).toBeDefined();
    expect(metricsStage.$addFields.writeOffPct).toBeDefined();
    expect(metricsStage.$addFields.scheduleVariance).toBeDefined();
    expect(metricsStage.$addFields.hasIssues).toBeDefined();
    
    // Verify writeOffPct calculation
    const writeOffPct = metricsStage.$addFields.writeOffPct;
    expect(writeOffPct.$cond[0]).toEqual({ $gt: ["$billed", 0] });
  });

  it("converts numeric strings properly", () => {
    const svc = makeSvc();
    const pipeline = svc.buildPivotPipeline();
    
    // Find conversion stage
    const conversionStage = pipeline.find(stage => 
      stage.$set && stage.$set.feeBilled
    );
    
    expect(conversionStage).toBeDefined();
    expect(conversionStage.$set.feeBilled.$convert).toBeDefined();
    expect(conversionStage.$set.feeBilled.$convert.to).toBe("double");
    expect(conversionStage.$set.feeBilled.$convert.onError).toBe(0);
  });

  it("handles empty results gracefully", async () => {
    const fakeDb: any = {
      collection: () => ({
        aggregate: jest.fn().mockReturnValue({ 
          toArray: () => Promise.resolve([]) 
        })
      }),
    };
    const fakeClient: any = { db: () => fakeDb };
    const svc = new UnifiedClaimsService(fakeClient);
    
    const result = await svc.getFeeStrategyPivot();
    
    expect(result.rows).toEqual([]);
    expect(result.summary.totalRows).toBe(0);
    expect(result.summary.dateRange.start).toBeUndefined();
    expect(result.summary.dateRange.end).toBeUndefined();
  });

  it("final projection matches expected output format", () => {
    const svc = makeSvc();
    const pipeline = svc.buildPivotPipeline();
    
    // Find final projection stage
    const projectionStage = pipeline[pipeline.length - 1];
    
    expect(projectionStage.$project).toBeDefined();
    expect(projectionStage.$project._id).toBe(0);
    expect(projectionStage.$project.carrier).toBe("$_id.carrier");
    expect(projectionStage.$project.locationCode).toBe("$_id.locationCode");
    expect(projectionStage.$project.procedure).toBe("$_id.procedure");
    expect(projectionStage.$project.month).toBe("$_id.month");
    expect(projectionStage.$project.metrics).toEqual({
      billed: "$billed",
      allowed: "$allowed",
      paid: "$paid",
      writeOff: "$writeOff",
      writeOffPct: "$writeOffPct",
      feeScheduled: "$feeScheduled",
      scheduleVariance: "$scheduleVariance",
      claimCount: "$claimCount"
    });
    expect(projectionStage.$project.hasIssues).toBe(1);
  });
});