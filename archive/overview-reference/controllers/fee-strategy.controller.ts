import { Request, Response } from 'express';
import { 
  PDCProvider, 
  PDCLocation, 
  PDCProviderStatus, 
  CarriersRegistry,
  PDCFeeSchedule,
  PDCProviderFeeMapping,
  PDCFeeValidation,
  PDCFeeHistory
} from '../models/crucible';
import ClaimsOutbound from '../models/od_live/ClaimsOutbound';
import InsuranceCarrier from '../models/od_live/InsuranceCarrier';
import { Parser } from 'json2csv';
import { getDatabase, DATABASE_NAMES } from '../config/databases';

// Simplified pivot data function - get basic claims with fee data
export const getPivotData = async (req: Request, res: Response) => {
  try {
    const { startDate, endDate, locations, carriers, limit = 1000 } = req.query;
    
    // Build match conditions
    const matchConditions: any = {
      service_date: {
        $gte: new Date((startDate as string) || '2024-01-01'),
        $lte: new Date((endDate as string) || new Date())
      }
    };
    
    if (locations) {
      matchConditions.location_id = { $in: (locations as string).split(',') };
    }
    
    if (carriers) {
      matchConditions.carrier_id = { $in: (carriers as string).split(',') };
    }
    
    // For now, return mock data to get the app working
    // TODO: Implement real data fetching after fixing model structure
    const pivotData = [
      {
        claimId: '1',
        serviceDate: new Date(),
        locationId: 'loc1',
        locationName: 'Main Office',
        locationState: 'CA',
        carrierId: 'car1',
        carrierName: 'Blue Shield',
        patientId: 'pat1',
        procedureCode: 'D0120',
        feeBilled: 100,
        feeScheduled: 90,
        variance: 10,
        variancePercentage: 11.11
      },
      {
        claimId: '2',
        serviceDate: new Date(),
        locationId: 'loc1',
        locationName: 'Main Office',
        locationState: 'CA',
        carrierId: 'car2',
        carrierName: 'Delta Dental',
        patientId: 'pat2',
        procedureCode: 'D0150',
        feeBilled: 150,
        feeScheduled: 140,
        variance: 10,
        variancePercentage: 7.14
      }
    ];
    
    res.json({
      success: true,
      data: pivotData,
      metadata: {
        totalRecords: pivotData.length,
        dateRange: { startDate, endDate },
        filters: { locations, carriers }
      }
    });
    
  } catch (error) {
    console.error('Error in getPivotData:', error);
    res.status(500).json({ 
      success: false, 
      error: 'Failed to fetch pivot data',
      message: error instanceof Error ? error.message : 'Unknown error'
    });
  }
};

// Get fee schedules with comparison data
export const getFeeSchedules = async (req: Request, res: Response) => {
  try {
    const { locationId, carrierId, procedureCode } = req.query;

    const matchConditions: any = {};
    if (locationId) matchConditions.location_id = String(locationId);

    const feeSchedules = await PDCFeeSchedule.find(matchConditions)
      .sort({ collected_at: -1 })
      .limit(1);

    if (!feeSchedules.length) {
      return res.json({
        success: true,
        data: [],
        message: 'No fee schedules found'
      });
    }

    // If specific procedure code requested, filter fees
    let scheduleData = feeSchedules[0].toObject();
    if (procedureCode) {
      scheduleData.fee_schedules = scheduleData.fee_schedules.map((schedule: any) => ({
        ...schedule,
        fees: schedule.fees.filter((fee: any) => fee.ProcedureCode === procedureCode)
      }));
    }

    // If carrier filter requested, filter schedules by description
    if (carrierId) {
      scheduleData.fee_schedules = scheduleData.fee_schedules.filter((schedule: any) =>
        schedule.Description.toLowerCase().includes(String(carrierId).toLowerCase())
      );
    }

    res.json({
      success: true,
      data: scheduleData,
      collectedAt: scheduleData.collected_at
    });
  } catch (error) {
    console.error('Error fetching fee schedules:', error);
    res.status(500).json({
      success: false,
      error: 'Failed to fetch fee schedules'
    });
  }
};

// Get fee comparisons across carriers
export const getFeeComparisons = async (req: Request, res: Response) => {
  try {
    const { procedureCode, locationId } = req.query;

    if (!procedureCode) {
      return res.status(400).json({
        success: false,
        error: 'Procedure code is required'
      });
    }

    // Get fee schedules for comparison - simplified query
    const comparisons = await PDCFeeSchedule.aggregate([
      {
        $match: {
          ...(locationId && { location_id: String(locationId) }),
          'fee_schedules.fees.Code': String(procedureCode)
        }
      },
      { $unwind: '$fee_schedules' },
      { $unwind: '$fee_schedules.fees' },
      {
        $match: {
          'fee_schedules.fees.Code': String(procedureCode)
        }
      },
      {
        $group: {
          _id: '$carrier_id',
          avgFee: { $avg: '$fee_schedules.fees.Fee' },
          count: { $sum: 1 }
        }
      }
    ]);

    // Get actual claims data for comparison
    const claimsAggregation = await ClaimsOutbound.aggregate([
      {
        $match: {
          procedures: { $exists: true },
          ...(locationId && { locationId })
        }
      },
      { $unwind: '$procedures' },
      {
        $match: {
          'procedures.procCode': String(procedureCode)
        }
      },
      {
        $group: {
          _id: '$carrier_name',
          avgBilled: { $avg: '$procedures.fee_billed' },
          avgAllowed: { $avg: { $ifNull: ['$procedures.fee_allowed', '$procedures.fee_billed'] } },
          avgWriteOff: { $avg: { $toDouble: { $ifNull: ['$procedures.write_off', '0'] } } },
          claimCount: { $sum: 1 }
        }
      },
      { $sort: { avgBilled: -1 } }
    ]);

    // Combine scheduled and actual data
    const combinedData = comparisons.map((scheduled: any) => {
      const actualData = claimsAggregation.find(
        (claim: any) => claim._id?.toLowerCase().includes(scheduled._id.toLowerCase())
      );

      return {
        carrier: scheduled._id,
        scheduledFee: scheduled.avgFee,
        actualAvgBilled: actualData?.avgBilled || null,
        actualAvgAllowed: actualData?.avgAllowed || null,
        actualAvgWriteOff: actualData?.avgWriteOff || null,
        claimCount: actualData?.claimCount || 0,
        variance: actualData ? (actualData.avgBilled - scheduled.avgFee) : null,
        variancePercentage: actualData && scheduled.avgFee > 0
          ? ((actualData.avgBilled - scheduled.avgFee) / scheduled.avgFee) * 100
          : null
      };
    });

    res.json({
      success: true,
      procedureCode: String(procedureCode),
      data: combinedData
    });
  } catch (error) {
    console.error('Error fetching fee comparisons:', error);
    res.status(500).json({
      success: false,
      error: 'Failed to fetch fee comparisons'
    });
  }
};

// Get fee validation data
export const getFeeValidations = async (req: Request, res: Response) => {
  try {
    const { locationId, minVariance = 10 } = req.query;

    // For now, return empty validation data
    // TODO: Implement actual validation logic later
    res.json({
      success: true,
      data: {
        message: 'Fee validation feature coming soon',
        locationId,
        minVariance
      }
    });
  } catch (error) {
    console.error('Error fetching fee validations:', error);
    res.status(500).json({
      success: false,
      error: 'Failed to fetch fee validations'
    });
  }
};

// Get providers with fee mappings
export const getProviders = async (req: Request, res: Response) => {
  try {
    const { locationId, withFeeSchedule } = req.query;

    // Get providers
    const providerQuery: any = {};
    if (locationId) {
      // First get location to get provider IDs
      const location = await PDCLocation.findById(locationId);
      if (location && location.Provider_ID) {
        providerQuery._id = location.Provider_ID;
      }
    }

    const providers = await PDCProvider.find(providerQuery).sort({ Provider_Name: 1 });

    if (withFeeSchedule === 'true') {
      // Get fee mappings for these providers
      const providerNums = providers.map(p => p._id);
      const mappings = await PDCProviderFeeMapping.find({
        provider_num: { $in: providerNums }
      });

      const mappingMap = new Map(
        mappings.map(m => [m.provider_num.toString(), m])
      );

      const providersWithMappings = providers.map(provider => ({
        id: provider._id,
        name: provider.Provider_Name,
        npi: mappingMap.get(provider._id.toString())?.npi,
        feeScheduleNum: mappingMap.get(provider._id.toString())?.fee_sched_num,
        hasFeeSchedule: mappingMap.has(provider._id.toString())
      }));

      return res.json({
        success: true,
        data: providersWithMappings,
        count: providersWithMappings.length
      });
    }

    const formattedProviders = providers.map(provider => ({
      id: provider._id,
      name: provider.Provider_Name
    }));

    res.json({
      success: true,
      data: formattedProviders,
      count: formattedProviders.length
    });
  } catch (error) {
    console.error('Error fetching providers:', error);
    res.status(500).json({
      success: false,
      error: 'Failed to fetch providers'
    });
  }
};

// Get PDC locations
export const getLocations = async (req: Request, res: Response) => {
  try {
    const { state, includeDormant = false } = req.query;

    const query: any = {};
    if (state) query.State = state;
    if (includeDormant !== 'true') query.Is_Dormant = false;

    const locations = await PDCLocation.find(query).sort({ Location_Name: 1 });

    const formattedLocations = locations.map(location => ({
      id: location._id,
      name: location.Location_Name,
      state: location.State,
      taxId: location.Tax_ID,
      isDormant: location.Is_Dormant,
      percentage: location.Percentage
    }));

    res.json({
      success: true,
      data: formattedLocations,
      count: formattedLocations.length
    });
  } catch (error) {
    console.error('Error fetching locations:', error);
    res.status(500).json({
      success: false,
      error: 'Failed to fetch locations'
    });
  }
};

// Get carriers from claims and registry
export const getCarriers = async (req: Request, res: Response) => {
  try {
    // Get unique carriers from claims
    const claimCarriers = await ClaimsOutbound.distinct('carrier_name', {
      carrier_name: { $exists: true, $ne: null }
    });

    // Get carriers from registry
    const registryCarriers = await CarriersRegistry.find({}).sort({ carrierName: 1 });

    // Create a map for registry data
    const registryMap = new Map(
      registryCarriers.map(c => [c.carrierName.toLowerCase(), c])
    );

    // Combine and format carrier data
    const allCarriers = new Set(claimCarriers);
    const formattedCarriers = Array.from(allCarriers)
      .sort()
      .map(carrierName => {
        const registryData = registryMap.get((carrierName as string).toLowerCase());
        return {
          id: (carrierName as string).toLowerCase().replace(/\s+/g, '_'),
          name: carrierName as string,
          carrierId: registryData?.carrierId || (carrierName as string).substring(0, 3).toUpperCase(),
          hasClaimsData: true,
          hasFeeSchedule: false, // TODO: Check PDC_fee_schedules instead
          claimCount: 0 // Will be populated if needed
        };
      });

    // Add carriers from registry that aren't in claims
    registryCarriers.forEach(regCarrier => {
      if (!allCarriers.has(regCarrier.carrierName)) {
        formattedCarriers.push({
          id: regCarrier.carrierId,
          name: regCarrier.carrierName,
          carrierId: regCarrier.carrierId,
          hasClaimsData: false,
          hasFeeSchedule: false, // TODO: Check PDC_fee_schedules instead
          claimCount: 0
        });
      }
    });

    res.json({
      success: true,
      data: formattedCarriers,
      count: formattedCarriers.length
    });
  } catch (error) {
    console.error('Error fetching carriers:', error);
    res.status(500).json({
      success: false,
      error: 'Failed to fetch carriers'
    });
  }
};

// NEW: Get fee strategy analysis from PDC_fee_schedules collection
export const getFeeStrategyAnalysis = async (req: Request, res: Response) => {
  try {
    const { practiceId, scheduleType, procedureCode } = req.query;
    
    const crucibleDb = getDatabase(DATABASE_NAMES.CRUCIBLE);
    const PDCFeeSchedules = crucibleDb.collection('PDC_fee_schedules');
    
    // Build query
    const query: any = {};
    if (practiceId) query.practice_id = practiceId;
    
    // Fetch fee schedules
    const feeSchedules = await PDCFeeSchedules.find(query).toArray();
    
    // Flatten and transform data for visualization
    const analysisData: any[] = [];
    
    feeSchedules.forEach(practice => {
      practice.fee_schedules?.forEach((schedule: any) => {
        // Filter by schedule type if specified
        if (scheduleType && !schedule.schedule_name.toLowerCase().includes((scheduleType as string).toLowerCase())) {
          return;
        }
        
        schedule.fees?.forEach((fee: any) => {
          // Filter by procedure code if specified
          if (procedureCode && fee.ProcedureCode !== procedureCode) return;
          
          const writeOffPercentage = fee.WriteOffPercentage || ((fee.WriteOffAmount / fee.UCR) * 100) || 0;
          
          analysisData.push({
            id: `${practice._id}-${schedule.schedule_number}-${fee.ProcedureCode}`,
            practiceId: practice.practice_id,
            practiceName: practice.practice_name,
            scheduleNumber: schedule.schedule_number,
            scheduleName: schedule.schedule_name,
            scheduleType: schedule.schedule_type || 'PPO',
            procedureCode: fee.ProcedureCode,
            description: fee.Description,
            ucr: fee.UCR || 0,
            scheduleFee: fee.ScheduleFee || fee.AllowableCharge || 0,
            writeOffAmount: fee.WriteOffAmount || (fee.UCR - (fee.ScheduleFee || fee.AllowableCharge || 0)) || 0,
            writeOffPercentage: writeOffPercentage,
            // Mock data for visualization (will be real when claims available)
            patientVolume: Math.floor(Math.random() * 400) + 50,
            claimCount: Math.floor(Math.random() * 300) + 20,
            // Calculate verdict based on write-off percentage
            verdict: writeOffPercentage > 40 ? 'DROP' : 
                    writeOffPercentage > 25 ? 'NEGOTIATE' : 'KEEP',
            profitabilityScore: writeOffPercentage < 10 ? 'high' : 
                               writeOffPercentage < 25 ? 'medium' : 'low'
          });
        });
      });
    });
    
    // Calculate summary statistics
    const summary = {
      totalProcedures: analysisData.length,
      avgWriteOffPercentage: analysisData.reduce((sum, item) => sum + item.writeOffPercentage, 0) / analysisData.length || 0,
      totalPractices: new Set(analysisData.map(item => item.practiceId)).size,
      totalSchedules: new Set(analysisData.map(item => item.scheduleName)).size,
      verdictCounts: {
        keep: analysisData.filter(item => item.verdict === 'KEEP').length,
        negotiate: analysisData.filter(item => item.verdict === 'NEGOTIATE').length,
        drop: analysisData.filter(item => item.verdict === 'DROP').length
      }
    };
    
    res.json({
      success: true,
      data: analysisData,
      summary
    });
  } catch (error) {
    console.error('Error fetching fee strategy analysis:', error);
    res.status(500).json({
      success: false,
      error: 'Failed to fetch fee strategy analysis'
    });
  }
};

// Export pivot data to CSV
export const exportPivotData = async (req: Request, res: Response) => {
  try {
    const { data, filename = 'fee-strategy-export' } = req.body;

    if (!data || !Array.isArray(data)) {
      return res.status(400).json({
        success: false,
        error: 'Invalid data provided for export'
      });
    }

    // Define fields for CSV export
    const fields = [
      { label: 'Carrier', value: 'carrierName' },
      { label: 'Procedure Code', value: 'procedureCode' },
      { label: 'Procedure Description', value: 'procedureDescription' },
      { label: 'Location', value: 'locationName' },
      { label: 'State', value: 'locationState' },
      { label: 'Provider', value: 'providerName' },
      { label: 'Date of Service', value: 'dateOfService' },
      { label: 'Fee Billed', value: 'feeBilled' },
      { label: 'Fee Scheduled', value: 'feeScheduled' },
      { label: 'Fee Allowed', value: 'feeAllowed' },
      { label: 'Write-off Amount', value: 'writeOff' },
      { label: 'Write-off %', value: 'writeOffPercentage' },
      { label: 'Variance', value: 'variance' },
      { label: 'Variance %', value: 'variancePercentage' },
      { label: 'Collection Rate', value: 'collectionRate' },
      { label: 'Is Anomaly', value: 'isAnomaly' },
      { label: 'Confidence Score', value: 'confidence' },
      { label: 'Status', value: 'status' }
    ];

    const parser = new Parser({ fields });
    const csv = parser.parse(data);

    res.setHeader('Content-Type', 'text/csv');
    res.setHeader('Content-Disposition', `attachment; filename="${filename}-${Date.now()}.csv"`);
    res.send(csv);
  } catch (error) {
    console.error('Error exporting pivot data:', error);
    res.status(500).json({
      success: false,
      error: 'Failed to export data'
    });
  }

};