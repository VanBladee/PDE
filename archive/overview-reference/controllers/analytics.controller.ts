import { Request, Response } from 'express';
import { Types } from 'mongoose';
import Analytics from '../models/activity/Analytics';
import Location from '../models/registry/Location';
import ClaimsOutbound from '../models/od_live/ClaimsOutbound';
import Job from '../models/activity/Job';
import { ClaimsLifecycleData } from '../types/analytics';
import { differenceInCalendarDays, parse, subWeeks } from 'date-fns';
import { CredentialingService } from '../services/credentialing.service';
import { getDatabase, DATABASE_NAMES } from '../config/databases';

/**
 * Utility function to normalize carrier names for better matching
 * Handles common variations in carrier naming
 */
const normalizeCarrierName = (carrierName: string): string => {
  if (!carrierName) return '';
  
  return carrierName
    .toLowerCase()
    .replace(/\s+/g, ' ')           // Normalize whitespace
    .replace(/\./g, '')             // Remove periods
    .replace(/\binc\b/g, '')        // Remove "inc"
    .replace(/\bllc\b/g, '')        // Remove "llc"
    .replace(/\bcorp\b/g, '')       // Remove "corp"
    .replace(/\bcompany\b/g, '')    // Remove "company"
    .replace(/\binsurance\b/g, '')  // Remove "insurance"
    .replace(/\bof\s+[a-z]+$/g, '') // Remove "of State" suffixes
    .trim();
};

/**
 * Find the best matching carrier from registry for a given claims carrier name
 */
const findBestCarrierMatch = (claimsCarrierName: string, registryCarriers: any[]): string => {
  if (!claimsCarrierName || !registryCarriers.length) return claimsCarrierName;
  
  const normalizedClaims = normalizeCarrierName(claimsCarrierName);
  
  // Try exact match first
  const exactMatch = registryCarriers.find(carrier => 
    normalizeCarrierName(carrier.name) === normalizedClaims
  );
  
  if (exactMatch) return exactMatch.name;
  
  // Try partial match - claims name contains registry name or vice versa
  const partialMatch = registryCarriers.find(carrier => {
    const normalizedRegistry = normalizeCarrierName(carrier.name);
    return normalizedClaims.includes(normalizedRegistry) || 
           normalizedRegistry.includes(normalizedClaims);
  });
  
  if (partialMatch) return partialMatch.name;
  
  // No match found, return original
  return claimsCarrierName;
};

/**
 * Get total claims processed across all locations in the organization
 */
export const getTotalClaimsProcessed = async (req: Request, res: Response) => {
  try {
    const { org } = req.user!; // Organization ID from auth middleware
    
    // Parse query parameters
    const { date_from, date_to } = req.query;
    
    // Build query for analytics data
    const analyticsQuery: any = {};
    
    // Add date filters if provided
    if (date_from || date_to) {
      analyticsQuery.createdAt = {};
      if (date_from) analyticsQuery.createdAt.$gte = new Date(date_from as string);
      if (date_to) analyticsQuery.createdAt.$lte = new Date(date_to as string);
    }
    
    // Get all analytics data for the organization
    const analyticsData = await Analytics.find(analyticsQuery);
    
    // Calculate total finalized claims
    const totalClaims = analyticsData.reduce((total, analytics) => {
      return total + (analytics.usage.finalized_claims || 0);
    }, 0);
    
    res.status(200).json({
      success: true,
      message: 'Total claims processed data fetched successfully',
      data: {
        totalClaims,
        locationCount: analyticsData.length,
      },
      filters: {
        date_from,
        date_to,
      },
    });
  } catch (error) {
    console.error('Error fetching total claims processed:', error);
    res.status(500).json({
      success: false,
      message: 'Failed to fetch total claims processed',
      error: error instanceof Error ? error.message : 'Unknown error',
    });
  }
};

/**
 * Get claims processed for a specific location
 */
export const getLocationClaimsProcessed = async (req: Request, res: Response) => {
  try {
    const { org } = req.user!; // Organization ID from auth middleware
    const { locationId } = req.params; // Location ID from URL parameter
    
    // Parse query parameters
    const { date_from, date_to } = req.query;
    
    // Validate locationId format
    if (!Types.ObjectId.isValid(locationId)) {
      return res.status(400).json({
        success: false,
        message: 'Invalid location ID format',
      });
    }
    
    // Build query for analytics data
    const analyticsQuery: any = {
      locationId: new Types.ObjectId(locationId),
    };
    
    // Add date filters if provided
    if (date_from || date_to) {
      analyticsQuery.createdAt = {};
      if (date_from) analyticsQuery.createdAt.$gte = new Date(date_from as string);
      if (date_to) analyticsQuery.createdAt.$lte = new Date(date_to as string);
    }
    
    // Get analytics data for the specific location
    const analyticsData = await Analytics.findOne(analyticsQuery);
    
    // Get location details to verify it belongs to the user's organization
    const location = await Location.findOne({
      _id: new Types.ObjectId(locationId),
      org: new Types.ObjectId(org),
    });
    
    if (!location) {
      return res.status(404).json({
        success: false,
        message: 'Location not found or access denied',
      });
    }
    
    // Extract finalized claims count
    const finalizedClaims = analyticsData?.usage?.finalized_claims || 0;
    const processedClaims = analyticsData?.usage?.processed_claims || 0;
    
    res.status(200).json({
      success: true,
      message: 'Location claims processed data fetched successfully',
      data: {
        locationId,
        locationName: location.practice_name,
        finalizedClaims,
        processedClaims,
        hasAnalyticsData: !!analyticsData,
      },
      filters: {
        date_from,
        date_to,
      },
    });
  } catch (error) {
    console.error('Error fetching location claims processed:', error);
    res.status(500).json({
      success: false,
      message: 'Failed to fetch location claims processed',
      error: error instanceof Error ? error.message : 'Unknown error',
    });
  }
};

/**
 * Get top users leaderboard data
 */
export const getTopUsersLeaderboard = async (req: Request, res: Response) => {
  try {
    const { org } = req.user!; // Organization ID from auth middleware
    
    // Import User model
    const User = (await import('../models/registry/User')).default;
    
    // Query users from the same organization
    const allUsers = await User.find({ org: new Types.ObjectId(org) }).lean();
    
    // Sort users by submitCounter in descending order, treating undefined/null as 0
    const sortedUsers = allUsers.sort((a, b) => {
      const aCount = a.submitCounter || 0;
      const bCount = b.submitCounter || 0;
      return bCount - aCount;
    });
    
    // Get top 5 users
    const topUsers = sortedUsers.slice(0, 6);
    
    // Build leaderboard data
    const leaderboardData = topUsers.map((user) => {
      return {
        name: `${user.firstName} ${user.lastName}`,
        claims: user.submitCounter || 0,
        userId: user._id,
      };
    });
    
    res.status(200).json({
      success: true,
      message: 'Top users leaderboard data fetched successfully',
      data: leaderboardData,
    });
  } catch (error) {
    console.error('Error fetching top users leaderboard:', error);
    res.status(500).json({
      success: false,
      message: 'Failed to fetch top users leaderboard',
      error: error instanceof Error ? error.message : 'Unknown error',
    });
  }
};

/**
 * Get manual writeoffs analytics data
 */
export const getManualWriteoffs = async (req: Request, res: Response) => {
  try {
    const { org } = req.user!; // Organization ID from auth middleware
    
    // Parse query parameters
    const { date_from, date_to, location_id } = req.query;
    
    // TODO: Implement manual writeoffs analytics logic
    // This will analyze and return data about manual writeoffs
    
    res.status(200).json({
      success: true,
      message: 'Manual writeoffs analytics data fetched successfully',
      data: {
        placeholder: 'Manual writeoffs analytics functionality to be implemented',
        organization: org,
        filters: {
          date_from,
          date_to,
          location_id,
        },
      },
    });
  } catch (error) {
    console.error('Error fetching manual writeoffs analytics:', error);
    res.status(500).json({
      success: false,
      message: 'Failed to fetch manual writeoffs analytics',
      error: error instanceof Error ? error.message : 'Unknown error',
    });
  }
};

/**
 * Get VCR fee discrepancies analytics data
 */
export const getVcrFeeDiscrepancies = async (req: Request, res: Response) => {
  try {
    const { org } = req.user!; // Organization ID from auth middleware
    
    // Parse query parameters
    const { date_from, date_to, location_id } = req.query;
    
    // TODO: Implement VCR fee discrepancies analytics logic
    // This will analyze and return data about VCR fee discrepancies
    
    res.status(200).json({
      success: true,
      message: 'VCR fee discrepancies analytics data fetched successfully',
      data: {
        placeholder: 'VCR fee discrepancies analytics functionality to be implemented',
        organization: org,
        filters: {
          date_from,
          date_to,
          location_id,
        },
      },
    });
  } catch (error) {
    console.error('Error fetching VCR fee discrepancies analytics:', error);
    res.status(500).json({
      success: false,
      message: 'Failed to fetch VCR fee discrepancies analytics',
      error: error instanceof Error ? error.message : 'Unknown error',
    });
  }
};

/**
 * Get network processing analysis data
 */
export const getNetworkProcessingAnalysis = async (req: Request, res: Response) => {
  try {
    const { org } = req.user!; // Organization ID from auth middleware
    
    // Parse query parameters
    const { date_from, date_to, location_id } = req.query;
    
    // Get all locations for the organization
    const locationsQuery: any = { org: new Types.ObjectId(org) };
    if (location_id) {
      locationsQuery._id = new Types.ObjectId(location_id as string);
    }
    
    const locations = await Location.find(locationsQuery).lean();
    
    if (!locations || locations.length === 0) {
      return res.status(404).json({
        success: false,
        message: 'No locations found for this organization',
      });
    }
    
    // Build query for processed claims
    const processedClaimsQuery: any = {};
    
    // Add date filters if provided
    if (date_from || date_to) {
      processedClaimsQuery.created_at = {};
      if (date_from) processedClaimsQuery.created_at.$gte = date_from as string;
      if (date_to) processedClaimsQuery.created_at.$lte = date_to as string;
    }
    
    // Add location filter if provided
    if (location_id) {
      processedClaimsQuery.locationId = new Types.ObjectId(location_id as string);
    } else {
      // If no specific location, get all locations for the organization
      const locationIds = locations.map(loc => loc._id);
      processedClaimsQuery.locationId = { $in: locationIds };
    }
    
    // Import ProcessedClaim model
    const ProcessedClaim = (await import('../models/activity/ProcessedClaim')).default;
    
    // Get all processed claims for the filtered locations
    const processedClaims = await ProcessedClaim.find(processedClaimsQuery).lean();
    
    // Analyze network status from processed claims
    let inNetworkCount = 0;
    let outOfNetworkCount = 0;
    let totalClaims = 0;
    
    processedClaims.forEach((processedClaim) => {
      totalClaims++;
      
      // Check if the processed claim has isOON property
      if (processedClaim.isOON !== undefined) {
        if (processedClaim.isOON === true) {
          outOfNetworkCount++;
        } else {
          inNetworkCount++;
        }
      }
    });
    
    // Calculate percentages
    const inNetworkPercentage = totalClaims > 0 ? (inNetworkCount / totalClaims) * 100 : 0;
    const outOfNetworkPercentage = totalClaims > 0 ? (outOfNetworkCount / totalClaims) * 100 : 0;
    
    // Prepare chart data
    const chartData = [
      { name: 'In Network', value: Math.round(inNetworkPercentage * 100) / 100 },
      { name: 'Out of Network', value: Math.round(outOfNetworkPercentage * 100) / 100 },
    ];
    
    res.status(200).json({
      success: true,
      message: 'Network processing analysis data fetched successfully',
      data: {
        totalClaims,
        inNetworkCount,
        outOfNetworkCount,
        inNetworkPercentage: Math.round(inNetworkPercentage * 100) / 100,
        outOfNetworkPercentage: Math.round(outOfNetworkPercentage * 100) / 100,
        chartData,
      },
      filters: {
        date_from,
        date_to,
        location_id,
      },
    });
  } catch (error) {
    console.error('Error fetching network processing analysis:', error);
    res.status(500).json({
      success: false,
      message: 'Failed to fetch network processing analysis',
      error: error instanceof Error ? error.message : 'Unknown error',
    });
  }
};

/**
 * Get EOB upload status analytics data
 */
export const getEobUploadStatus = async (req: Request, res: Response) => {
  try {
    const { org } = req.user!; // Organization ID from auth middleware
    
    // Parse query parameters
    const { date_from, date_to, location_id, status } = req.query;
    
    // TODO: Implement EOB upload status analytics logic
    // This will analyze and return EOB upload status data and metrics
    
    res.status(200).json({
      success: true,
      message: 'EOB upload status analytics data fetched successfully',
      data: {
        placeholder: 'EOB upload status analytics functionality to be implemented',
        organization: org,
        filters: {
          date_from,
          date_to,
          location_id,
          status,
        },
      },
    });
  } catch (error) {
    console.error('Error fetching EOB upload status analytics:', error);
    res.status(500).json({
      success: false,
      message: 'Failed to fetch EOB upload status analytics',
      error: error instanceof Error ? error.message : 'Unknown error',
    });
  }
};

/**
 * Get common denials analytics data
 */
export const getCommonDenials = async (req: Request, res: Response) => {
  try {
    const { org } = req.user!; // Organization ID from auth middleware
    
    // Parse query parameters
    const { date_from, date_to, location_id, denial_code } = req.query;
    
    // TODO: Implement common denials analytics logic
    // This will analyze and return data about common denials and patterns
    
    res.status(200).json({
      success: true,
      message: 'Common denials analytics data fetched successfully',
      data: {
        placeholder: 'Common denials analytics functionality to be implemented',
        organization: org,
        filters: {
          date_from,
          date_to,
          location_id,
          denial_code,
        },
      },
    });
  } catch (error) {
    console.error('Error fetching common denials analytics:', error);
    res.status(500).json({
      success: false,
      message: 'Failed to fetch common denials analytics',
      error: error instanceof Error ? error.message : 'Unknown error',
    });
  }
};

/**
 * Get UCR fee analysis data
 * Analyzes claims_outbound collection for UCR vs Fee Billed discrepancies
 */
export const getUCRFeeAnalysis = async (req: Request, res: Response) => {
  try {
    const { org } = req.user!; // Organization ID from auth middleware
    
    // Parse query parameters
    const { location_id } = req.query;
    
    // Get all locations for the organization
    const locationsQuery: any = { org: new Types.ObjectId(org) };
    if (location_id) {
      locationsQuery._id = new Types.ObjectId(location_id as string);
    }
    
    const locations = await Location.find(locationsQuery).lean();
    
    if (!locations || locations.length === 0) {
      return res.status(404).json({
        success: false,
        message: 'No locations found for this organization',
      });
    }
    
    // Analyze UCR discrepancies for each location
    const locationAnalysis = await Promise.all(
      locations.map(async (location) => {
        // Find all claims_outbound documents for this location using locationId
        const claimsOutboundDocs = await ClaimsOutbound.find({
          locationId: location._id
        }).lean();
        
        if (!claimsOutboundDocs || claimsOutboundDocs.length === 0) {
          console.log(`No claims_outbound documents found for location: ${location.practice_name} (${location._id})`);
          return {
            locationId: location._id.toString(),
            locationName: location.practice_name,
            totalProcedures: 0,
            matchesUCR: 0,
            mismatchesUCR: 0,
            matchPercentage: 0,
            mismatchPercentage: 0,
            hasData: false,
          };
        }
        
        // Analyze procedures for UCR discrepancies
        let totalProcedures = 0;
        let matchesUCR = 0;
        let mismatchesUCR = 0;
        
        // Each document is now an individual claim
        claimsOutboundDocs.forEach((claimDoc: any) => {
          if (claimDoc && claimDoc.procedures && Array.isArray(claimDoc.procedures)) {
            claimDoc.procedures.forEach((procedure: any) => {
              totalProcedures++;
              
              // Handle potential snake_case vs camelCase field names from different sources
              const feeBilled = procedure.feeBilled ?? procedure.fee_billed;
              const ucrAmount = procedure.ucr_amount; // Already matches schema example
              
              // Primary method: Check matchesUCR boolean field
              if (procedure.matchesUCR === true) {
                matchesUCR++;
              } else if (procedure.matchesUCR === false) {
                mismatchesUCR++;
              } 
              // Fallback method: Compare ucr_amount with feeBilled
              else if (ucrAmount != null && feeBilled != null) {
                if (Math.abs(Number(feeBilled) - Number(ucrAmount)) < 0.01) {
                  matchesUCR++;
                } else {
                  mismatchesUCR++;
                }
              } else {
                // If no UCR data is available, we can't analyze it.
                // You might want to log this for debugging.
              }
            });
          }
        });
        
        const matchPercentage = totalProcedures > 0 ? (matchesUCR / totalProcedures) * 100 : 0;
        const mismatchPercentage = totalProcedures > 0 ? (mismatchesUCR / totalProcedures) * 100 : 0;
        
        return {
          locationId: location._id.toString(),
          locationName: location.practice_name,
          totalProcedures,
          matchesUCR,
          mismatchesUCR,
          matchPercentage: Math.round(matchPercentage * 100) / 100,
          mismatchPercentage: Math.round(mismatchPercentage * 100) / 100,
          hasData: totalProcedures > 0,
        };
      })
    );
    
    // Calculate aggregate statistics across all locations
    const aggregateStats = locationAnalysis.reduce((acc, location) => {
      if (location.hasData) {
        acc.totalProcedures += location.totalProcedures;
        acc.matchesUCR += location.matchesUCR;
        acc.mismatchesUCR += location.mismatchesUCR;
      }
      return acc;
    }, { totalProcedures: 0, matchesUCR: 0, mismatchesUCR: 0 });
    
    const aggregateMatchPercentage = aggregateStats.totalProcedures > 0 
      ? Math.round((aggregateStats.matchesUCR / aggregateStats.totalProcedures) * 10000) / 100
      : 0;
    const aggregateMismatchPercentage = aggregateStats.totalProcedures > 0 
      ? Math.round((aggregateStats.mismatchesUCR / aggregateStats.totalProcedures) * 10000) / 100
      : 0;
    
    // Prepare chart data
    const chartData = [
      { name: 'UCR Matches Fee', value: aggregateMatchPercentage },
      { name: 'UCR < Fee Billed', value: aggregateMismatchPercentage * 0.6 },
      { name: 'UCR > Fee Billed', value: aggregateMismatchPercentage * 0.4 },
    ];
    
    res.status(200).json({
      success: true,
      message: 'UCR fee analysis data fetched successfully',
      data: {
        aggregate: {
          totalProcedures: aggregateStats.totalProcedures,
          matchesUCR: aggregateStats.matchesUCR,
          mismatchesUCR: aggregateStats.mismatchesUCR,
          matchPercentage: aggregateMatchPercentage,
          mismatchPercentage: aggregateMismatchPercentage,
        },
        locations: locationAnalysis,
        chartData,
      },
      filters: {
        location_id,
      },
    });
  } catch (error) {
    console.error('Error fetching UCR fee analysis:', error);
    res.status(500).json({
      success: false,
      message: 'Failed to fetch UCR fee analysis',
      error: error instanceof Error ? error.message : 'Unknown error',
    });
  }
};

/**
 * Get denial breakdown analytics data
 * Analyzes processed_claims collection for denied vs approved claims by location and carrier
 */
export const getDenialBreakdown = async (req: Request, res: Response) => {
  try {
    const { org } = req.user!; // Organization ID from auth middleware
    
    // Parse query parameters
    const { date_from, date_to, location_id, view_by } = req.query;
    
    // Get all locations for the organization
    const locationsQuery: any = { org: new Types.ObjectId(org) };
    if (location_id) {
      locationsQuery._id = new Types.ObjectId(location_id as string);
    }
    
    const locations = await Location.find(locationsQuery).lean();
    
    if (!locations || locations.length === 0) {
      return res.status(404).json({
        success: false,
        message: 'No locations found for this organization',
      });
    }
    
    // Build query for processed claims
    const processedClaimsQuery: any = {};
    
    // Add date filters if provided
    if (date_from || date_to) {
      processedClaimsQuery.created_at = {};
      if (date_from) processedClaimsQuery.created_at.$gte = date_from as string;
      if (date_to) processedClaimsQuery.created_at.$lte = date_to as string;
    }
    
    // Add location filter if provided
    if (location_id) {
      processedClaimsQuery.locationId = new Types.ObjectId(location_id as string);
    } else {
      // If no specific location, get all locations for the organization
      const locationIds = locations.map(loc => loc._id);
      processedClaimsQuery.locationId = { $in: locationIds };
    }
    
    // Import ProcessedClaim model
    const ProcessedClaim = (await import('../models/activity/ProcessedClaim')).default;
    
    // Get all processed claims for the filtered locations
    const processedClaims = await ProcessedClaim.find(processedClaimsQuery).lean();
    
    // Get all claim IDs to fetch associated jobs
    const claimIds = processedClaims.map(claim => claim._id);
    
    // Fetch jobs that contain these claims to get carrier information
    const jobs = await Job.find({
      'events.claim_doc_ids': { $in: claimIds }
    }).lean();
    
    // Create a map of claim ID to carrier name from jobs
    const claimToCarrierMap = new Map<string, string>();
    jobs.forEach(job => {
      const carrierName = job.payment?.carrierName;
      if (carrierName && job.events?.claim_doc_ids) {
        job.events.claim_doc_ids.forEach((claimId: any) => {
          claimToCarrierMap.set(claimId.toString(), carrierName);
        });
      }
    });
    
    // Analyze denial data
    let totalClaims = 0;
    let deniedClaims = 0;
    let approvedClaims = 0;
    const carrierDenials: { [key: string]: { denied: number; total: number; carrierName: string } } = {};
    const locationDenials: { [key: string]: { denied: number; total: number; locationName: string } } = {};
    
    processedClaims.forEach((processedClaim) => {
      totalClaims++;
      
      // Get location info
      const locationId = processedClaim.locationId.toString();
      const location = locations.find(loc => loc._id.toString() === locationId);
      const locationName = location?.practice_name || 'Unknown Location';
      
      // Get carrier name from the job mapping, fallback to processedClaim data or matched_claims
      let carrierName = claimToCarrierMap.get(processedClaim._id.toString()) || 
                       processedClaim.carrier_name || 
                       processedClaim.matched_claims?.[0]?.carrier_name || 
                       'Unknown Carrier';
      
      // Check if claim is denied
      if (processedClaim.isDenied === true) {
        deniedClaims++;
        
        // Track by carrier
        if (!carrierDenials[carrierName]) {
          carrierDenials[carrierName] = { denied: 0, total: 0, carrierName };
        }
        carrierDenials[carrierName].denied++;
        carrierDenials[carrierName].total++;
        
        // Track by location
        if (!locationDenials[locationId]) {
          locationDenials[locationId] = { denied: 0, total: 0, locationName };
        }
        locationDenials[locationId].denied++;
        locationDenials[locationId].total++;
      } else {
        approvedClaims++;
        
        // Track by carrier
        if (!carrierDenials[carrierName]) {
          carrierDenials[carrierName] = { denied: 0, total: 0, carrierName };
        }
        carrierDenials[carrierName].total++;
        
        // Track by location
        if (!locationDenials[locationId]) {
          locationDenials[locationId] = { denied: 0, total: 0, locationName };
        }
        locationDenials[locationId].total++;
      }
    });
    
    // Calculate percentages
    const deniedPercentage = totalClaims > 0 ? (deniedClaims / totalClaims) * 100 : 0;
    const approvedPercentage = totalClaims > 0 ? (approvedClaims / totalClaims) * 100 : 0;
    
    // Prepare chart data
    const chartData = [
      { name: 'Approved', value: Math.round(approvedPercentage * 100) / 100 },
      { name: 'Denied', value: Math.round(deniedPercentage * 100) / 100 },
    ];
    
    // Prepare breakdown data based on view_by parameter
    let breakdownData: any[] = [];
    
    if (view_by === 'carrier') {
      // Sort carriers by denial percentage (highest first)
      breakdownData = Object.values(carrierDenials)
        .map(carrier => ({
          name: carrier.carrierName,
          denied: carrier.denied,
          total: carrier.total,
          deniedPercentage: carrier.total > 0 ? Math.round((carrier.denied / carrier.total) * 10000) / 100 : 0,
        }))
        .sort((a, b) => b.deniedPercentage - a.deniedPercentage)
        .slice(0, 10); // Top 10 carriers by denial rate
    } else {
      // Default to location breakdown
      breakdownData = Object.values(locationDenials)
        .map(location => ({
          name: location.locationName,
          denied: location.denied,
          total: location.total,
          deniedPercentage: location.total > 0 ? Math.round((location.denied / location.total) * 10000) / 100 : 0,
        }))
        .sort((a, b) => b.deniedPercentage - a.deniedPercentage);
    }
    
    res.status(200).json({
      success: true,
      message: 'Denial breakdown data fetched successfully',
      data: {
        totalClaims,
        deniedClaims,
        approvedClaims,
        deniedPercentage: Math.round(deniedPercentage * 100) / 100,
        approvedPercentage: Math.round(approvedPercentage * 100) / 100,
        chartData,
        breakdownData,
        viewBy: view_by || 'location',
      },
      filters: {
        date_from,
        date_to,
        location_id,
        view_by,
      },
    });
  } catch (error) {
    console.error('Error fetching denial breakdown:', error);
    res.status(500).json({
      success: false,
      message: 'Failed to fetch denial breakdown',
      error: error instanceof Error ? error.message : 'Unknown error',
    });
  }
};




export const getClaimsLifeCycleReport = async (req: Request, res: Response) => {
  try {
    const { org } = req.user!;

    const locations = await Location.find({ org: new Types.ObjectId(org) }).lean();
    const locationIds = locations.map(loc => loc._id);

    const ProcessedClaim = (await import('../models/activity/ProcessedClaim')).default;
    const Job = (await import('../models/activity/Job')).default;

    const processedClaims = await ProcessedClaim.find({
      locationId: { $in: locationIds }
    }).lean();

    // Fetch all jobs with payments for the organization's locations
    const jobsWithPayments = await Job.find({
      locationId: { $in: locationIds },
      'payment.dateIssued': { $exists: true },
      status: 'completed'
    }).lean();

    // Create a map of claim ID to payment date from jobs
    const claimPaymentMap = new Map<string, string>();
    
    jobsWithPayments.forEach(job => {
      const paymentDate = job.payment?.dateIssued;
      if (paymentDate) {
        // Check both possible locations for claim IDs
        const claimIds = job.events?.claim_doc_ids || job.patients?.flatMap((p: any) => p.claims) || [];
        claimIds.forEach((claimId: any) => {
          claimPaymentMap.set(claimId.toString(), paymentDate);
        });
      }
    });

    console.log(`\n📊 Claims Lifecycle Report Generation`);
    console.log(`📍 Organization: ${org}`);
    console.log(`📍 Locations found: ${locations.length}`);
    console.log(`📍 Processed claims found: ${processedClaims.length}`);
    console.log(`📍 Jobs with payments found: ${jobsWithPayments.length}`);
    console.log(`📍 Claims with payment dates: ${claimPaymentMap.size}`);

    const responseData: {
      dateOfService: string;
      date_sent: string;
      date_received: string;
      date_issued: string | null;
    }[] = [];

    let totalClaimsAnalyzed = 0;
    let claimsWithMissingData = 0;
    let claimsMissingDateSent = 0;
    let claimsMissingDateReceived = 0;
    let claimsMissingDOS = 0;
    let claimsMissingDateIssued = 0;

    processedClaims.forEach((doc: any) => {
      totalClaimsAnalyzed++;
      
      const date_sent = doc.date_sent;
      const date_received = doc.date_received;
      const procedures = doc.procedures;
      const dateOfService = procedures?.[0]?.dateOfService;
      // Get payment date from the jobs collection mapping
      const paymentDateIssued = claimPaymentMap.get(doc._id.toString()) || null;

      // Track missing data separately
      const missingDateSent = !date_sent;
      const missingDateReceived = !date_received;
      const missingDOS = !dateOfService;
      const missingDateIssued = !paymentDateIssued;

      if (missingDateSent) claimsMissingDateSent++;
      if (missingDateReceived) claimsMissingDateReceived++;
      if (missingDOS) claimsMissingDOS++;
      if (missingDateIssued) claimsMissingDateIssued++;

      // Debug logging for first few claims
      if (totalClaimsAnalyzed <= 3) {
        console.log(`\n🔍 Sample Claim #${totalClaimsAnalyzed}:`);
        console.log(`  - Date of Service: ${dateOfService || 'MISSING'}`);
        console.log(`  - Date Sent to Payer: ${date_sent || 'MISSING'}`);
        console.log(`  - Date Payment Issued: ${paymentDateIssued || 'MISSING'}`);
        console.log(`  - Date Payment Received: ${date_received || 'MISSING'}`);
      }

      const responseObjectUnit: {
        dateOfService: string;
        date_sent: string;
        date_received: string;
        date_issued: string | null;
      } = {
        date_sent: date_sent || '',
        date_received: date_received || '',
        dateOfService: dateOfService || '',
        date_issued: paymentDateIssued,
      };

      if (date_sent && date_received && dateOfService) {
        responseData.push(responseObjectUnit);
      } else {
        claimsWithMissingData++;
      }
    });

    const dataCompleteness = (responseData.length / totalClaimsAnalyzed) * 100;

    console.log(`\n📈 Data Quality Summary:`);
    console.log(`  - Total claims analyzed: ${totalClaimsAnalyzed}`);
    console.log(`  - Claims with complete data: ${responseData.length} (${dataCompleteness.toFixed(1)}%)`);
    console.log(`  - Claims missing date_sent: ${claimsMissingDateSent} (${((claimsMissingDateSent/totalClaimsAnalyzed)*100).toFixed(1)}%)`);
    console.log(`  - Claims missing date_received: ${claimsMissingDateReceived} (${((claimsMissingDateReceived/totalClaimsAnalyzed)*100).toFixed(1)}%)`);
    console.log(`  - Claims missing date_issued: ${claimsMissingDateIssued} (${((claimsMissingDateIssued/totalClaimsAnalyzed)*100).toFixed(1)}%)`);
    console.log(`  - Claims missing DOS: ${claimsMissingDOS} (${((claimsMissingDOS/totalClaimsAnalyzed)*100).toFixed(1)}%)`);

    // 🔢 Calculate average processing times
    let totalSendTime = 0;
    let totalReceiveTime = 0;
    let totalRevenueCycleTime = 0;
    let totalCashPostingTime = 0;
    let count = 0;
    let cashPostingCount = 0;
    let invalidDates = 0;

    responseData.forEach(({ dateOfService, date_sent, date_received, date_issued }, index) => {
      try {
        // Parse dates with their correct formats
        // Handle both MM-dd-yyyy and yyyy-MM-dd formats for dateOfService
        let parsedDOS;
        if (dateOfService.includes('-') && dateOfService.split('-')[0].length === 4) {
          parsedDOS = parse(dateOfService, 'yyyy-MM-dd', new Date());
        } else {
          parsedDOS = parse(dateOfService, 'MM-dd-yyyy', new Date());
        }
        const parsedSent = parse(date_sent, 'yyyy-MM-dd', new Date());
        const parsedReceived = parse(date_received, 'yyyy-MM-dd', new Date());

        // Validate core dates
        if (isNaN(parsedDOS.getTime()) || isNaN(parsedSent.getTime()) || isNaN(parsedReceived.getTime())) {
          invalidDates++;
          if (invalidDates <= 3) {
            console.log(`\n❌ Invalid date format in claim ${index + 1}:`);
            console.log(`  - DOS: ${dateOfService} -> ${parsedDOS}`);
            console.log(`  - Sent: ${date_sent} -> ${parsedSent}`);
            console.log(`  - Received: ${date_received} -> ${parsedReceived}`);
          }
          return;
        }

        const daysToSend = differenceInCalendarDays(parsedSent, parsedDOS);
        const daysToReceive = differenceInCalendarDays(parsedReceived, parsedSent);
        const totalRevenueCycleDays = differenceInCalendarDays(parsedReceived, parsedDOS);

        // Calculate cash posting time if date_issued is available
        let cashPostingDays = 0;
        if (date_issued) {
          // Try multiple date formats for payment issued date
          let parsedIssued;
          if (date_issued.includes('/')) {
            // Handle MM/dd/yyyy format from Jobs collection
            parsedIssued = parse(date_issued, 'MM/dd/yyyy', new Date());
          } else if (date_issued.includes('-') && date_issued.split('-')[0].length === 4) {
            parsedIssued = parse(date_issued, 'yyyy-MM-dd', new Date());
          } else {
            parsedIssued = parse(date_issued, 'MM-dd-yyyy', new Date());
          }
          
          if (!isNaN(parsedIssued.getTime())) {
            cashPostingDays = differenceInCalendarDays(parsedReceived, parsedIssued);
            if (cashPostingDays >= 0) {
              totalCashPostingTime += cashPostingDays;
              cashPostingCount++;
            }
          }
        }

        // Log sample calculations
        if (count < 3) {
          console.log(`\n✅ Sample calculation ${count + 1}:`);
          console.log(`  - DOS: ${dateOfService}`);
          console.log(`  - Sent to Payer: ${date_sent} (${daysToSend} days after service)`);
          console.log(`  - Payment Received: ${date_received} (${daysToReceive} days after sent)`);
          console.log(`  - Total Revenue Cycle: ${totalRevenueCycleDays} days`);
          if (date_issued && cashPostingDays >= 0) {
            console.log(`  - Cash Posting Time: ${cashPostingDays} days (from issued to received)`);
          }
        }

        // Only include positive values in calculations
        if (daysToSend >= 0 && daysToReceive >= 0 && totalRevenueCycleDays >= 0) {
          totalSendTime += daysToSend;
          totalReceiveTime += daysToReceive;
          totalRevenueCycleTime += totalRevenueCycleDays;
          count++;
        } else {
          console.log(`\n⚠️  Negative time difference detected (claim ${index + 1}):`);
          console.log(`  - Days to Send: ${daysToSend}`);
          console.log(`  - Days to Receive: ${daysToReceive}`);
          console.log(`  - Total Revenue Cycle: ${totalRevenueCycleDays}`);
        }
      } catch (error) {
        console.error(`Error parsing dates for claim ${index + 1}:`, error);
      }
    });

    const averageTimeToSend = count > 0 ? totalSendTime / count : 0;
    const averageTimeToReceive = count > 0 ? totalReceiveTime / count : 0;
    const averageTotalRevenueCycle = count > 0 ? totalRevenueCycleTime / count : 0;
    const averageCashPostingTime = cashPostingCount > 0 ? totalCashPostingTime / cashPostingCount : 0;

    console.log(`\n📊 Calculation Summary:`);
    console.log(`  - Valid calculations: ${count} out of ${responseData.length} complete records`);
    console.log(`  - Cash posting calculations: ${cashPostingCount} claims with payment issued date`);
    console.log(`  - Invalid date formats: ${invalidDates}`);
    
    console.log(`\n📈 Final Averages:`);
    console.log(`  - Average Claim Turnaround: ${averageTimeToSend.toFixed(2)} days`);
    console.log(`  - Average Payer Response Time: ${averageTimeToReceive.toFixed(2)} days`);
    console.log(`  - Average Total Revenue Cycle: ${averageTotalRevenueCycle.toFixed(2)} days`);
    console.log(`  - Average Cash Posting Time: ${averageCashPostingTime.toFixed(2)} days (${cashPostingCount} claims with data)`);
    
    // Add data quality warning
    if (dataCompleteness < 50) {
      console.log(`\n⚠️  DATA QUALITY WARNING:`);
      console.log(`  Only ${dataCompleteness.toFixed(1)}% of claims have complete date information.`);
      console.log(`  Averages are based on ${count} claims out of ${totalClaimsAnalyzed} total claims.`);
    }

    res.status(200).json({
      success: true,
      data: {
        averageTimeToSend: parseFloat(averageTimeToSend.toFixed(2)),
        averageTimeToReceive: parseFloat(averageTimeToReceive.toFixed(2)),
        averageTotalTime: parseFloat(averageTotalRevenueCycle.toFixed(2)), // Total Revenue Cycle
        averageCashPostingTime: parseFloat(averageCashPostingTime.toFixed(2)),
        totalClaims: responseData.length,
        dataQuality: {
          totalClaimsAnalyzed,
          claimsWithCompleteData: responseData.length,
          dataCompleteness: parseFloat(dataCompleteness.toFixed(1)),
          missingDateSent: claimsMissingDateSent,
          missingDateReceived: claimsMissingDateReceived,
          missingDOS: claimsMissingDOS,
          missingDateIssued: claimsMissingDateIssued,
          claimsWithCashPostingData: cashPostingCount
        }
      }
    });
  } catch (error) {
    console.error('Error fetching claims lifecycle report:', error);
    res.status(500).json({
      success: false,
      message: 'Failed to fetch claims lifecycle report',
      error: error instanceof Error ? error.message : 'Unknown error',
    });
  }
};

/**
 * Get average check amounts per clinic per week
 */
export const getAverageCheckAmounts = async (req: Request, res: Response) => {
  try {
    const { org } = req.user!; // Organization ID from auth middleware
    
    // Get all locations for the organization
    const locations = await Location.find({ 
      org: new Types.ObjectId(org)
    }).lean();
    
    const locationIds = locations.map(loc => loc._id);
    
    // Calculate date range for the past 4 weeks
    const endDate = new Date();
    const startDate = subWeeks(endDate, 4);
    
    // Aggregate check amounts by location and week
    const checkAmountsByWeek = await Job.aggregate([
      {
        $match: {
          locationId: { $in: locationIds },
          'payment.checkAmt': { $exists: true, $gt: 0 },
          'timeline.started_at': {
            $gte: startDate.toISOString(),
            $lte: endDate.toISOString()
          },
          phase: { $in: ['finalized', 'processed'] },
          'events.eob_attached': true
        }
      },
      {
        $addFields: {
          weekStart: {
            $dateFromString: {
              dateString: '$timeline.started_at',
              onError: null
            }
          }
        }
      },
      {
        $match: {
          weekStart: { $ne: null }
        }
      },
      {
        $group: {
          _id: {
            locationId: '$locationId',
            week: { $week: '$weekStart' },
            year: { $year: '$weekStart' }
          },
          totalCheckAmount: { $sum: '$payment.checkAmt' },
          count: { $sum: 1 }
        }
      },
      {
        $group: {
          _id: '$_id.locationId',
          weeklyAmounts: {
            $push: {
              week: '$_id.week',
              year: '$_id.year',
              total: '$totalCheckAmount',
              count: '$count'
            }
          },
          totalAmount: { $sum: '$totalCheckAmount' },
          totalWeeks: { $sum: 1 }
        }
      },
      {
        $project: {
          locationId: '$_id',
          averagePerWeek: { 
            $cond: [
              { $gt: ['$totalWeeks', 0] },
              { $divide: ['$totalAmount', '$totalWeeks'] },
              0
            ]
          },
          totalAmount: 1,
          totalWeeks: 1,
          weeklyAmounts: 1
        }
      }
    ]);
    
    // Map location names to the results
    const locationMap = new Map(locations.map(loc => [loc._id.toString(), loc.practice_name]));
    
    const results = checkAmountsByWeek.map(item => ({
      locationId: item.locationId,
      locationName: locationMap.get(item.locationId.toString()) || 'Unknown',
      averagePerWeek: Math.round(item.averagePerWeek * 100) / 100,
      totalAmount: item.totalAmount,
      weeksOfData: item.totalWeeks
    }));
    
    // Calculate overall average across all clinics
    const overallAverage = results.length > 0
      ? results.reduce((sum, loc) => sum + loc.averagePerWeek, 0) / results.length
      : 0;
    
    res.json({
      success: true,
      data: {
        averagePerClinicPerWeek: Math.round(overallAverage * 100) / 100,
        clinicBreakdown: results,
        dateRange: {
          from: startDate.toISOString(),
          to: endDate.toISOString()
        }
      }
    });
  } catch (error) {
    console.error('Error in getAverageCheckAmounts:', error);
    res.status(500).json({
      success: false,
      message: 'Failed to fetch average check amounts',
      error: error instanceof Error ? error.message : 'Unknown error',
    });
  }
};

/**
 * Get fee comparison between two carriers for specific CDT codes
 * Uses ONLY real claims data - queries by provider NPI based on credentialing
 */
export const getFeeComparison = async (req: Request, res: Response) => {
  try {
    const { carrier_a, carrier_b, location_id, provider_npi, sort_by = 'dollar_diff', months_back = '12' } = req.query;
    const { org } = req.user!;
    
    // Calculate date cutoff for data freshness (default: last 12 months)
    const monthsBack = parseInt(months_back as string, 10) || 12;
    const dateCutoff = new Date();
    dateCutoff.setMonth(dateCutoff.getMonth() - monthsBack);
    const dateCutoffStr = dateCutoff.toISOString().split('T')[0];
    
    console.log(`📅 Fee comparison using claims from last ${monthsBack} months (since ${dateCutoffStr})`);
    
    // 10 core CDT codes to display
    const CORE_CDT_CODES = [
      'D0120', // Periodic Exam
      'D1110', // Prophylaxis/Cleaning
      'D1206', // Fluoride
      'D0220', // PA first
      'D0230', // PA additional
      'D0274', // Bitewings
      'D8090', // Orthodontic
      'D2740', // Crown
      'D0140', // Limited Exam
      'D2330', // 1 surface composite
    ];
    
    const CDT_DESCRIPTIONS: Record<string, string> = {
      'D0120': 'Periodic Exam',
      'D1110': 'Prophylaxis/Cleaning',
      'D1206': 'Fluoride',
      'D0220': 'PA first',
      'D0230': 'PA additional',
      'D0274': 'Bitewings',
      'D8090': 'Orthodontic',
      'D2740': 'Crown',
      'D0140': 'Limited Exam',
      'D2330': '1 surface composite'
    };
    
    // Initialize credentialing service to get provider-carrier relationships
    await CredentialingService.initialize();
    
    // Get NPIs for providers credentialed with these carriers
    const npisForCarrierA = CredentialingService.getNPIsForCarrier(carrier_a as string);
    const npisForCarrierB = CredentialingService.getNPIsForCarrier(carrier_b as string);
    
    console.log(`📊 Fee Comparison Pipeline:`);
    console.log(`  - Carrier A (${carrier_a}): ${npisForCarrierA.length} credentialed providers`);
    console.log(`  - Carrier B (${carrier_b}): ${npisForCarrierB.length} credentialed providers`);
    
    // Get user's locations
    const locations = await Location.find({ org: new Types.ObjectId(org) }).lean();
    const locationIds = location_id === 'all' || !location_id 
      ? locations.map(loc => loc._id)
      : [new Types.ObjectId(location_id as string)];
    
    // Build pipeline to query claims - NO FILTERS that would exclude data
    const matchConditions: any = {
      locationID: { $in: locationIds },
      carrier_name: { $in: [carrier_a, carrier_b] },
      procedures: { $exists: true, $ne: [] }
    };
    
    const pipeline = [
      { $match: matchConditions },
      { $unwind: '$procedures' },
      {
        $match: {
          // Use CORRECT field names from schema
          'procedures.procCode': { $in: CORE_CDT_CODES },
          'procedures.feeBilled': { $exists: true, $gt: 0 },
          // Filter by specific provider NPI if provided
          ...(provider_npi ? { 'procedures.provider.npi': provider_npi } : {})
        }
      },
      {
        $group: {
          _id: {
            cdtCode: '$procedures.proc_code',
            carrier: '$carrier_name'
          },
          avgFee: { $avg: '$procedures.feeBilled' },
          minFee: { $min: '$procedures.feeBilled' },
          maxFee: { $max: '$procedures.feeBilled' },
          count: { $sum: 1 },
          providers: { $addToSet: '$procedures.provider.name' },
          latestDate: { $max: '$procedures.dateOfService' },
          oldestDate: { $min: '$procedures.dateOfService' }
        }
      }
    ];
    
    // Remove quality pipeline - we'll just use all available data
    // const qualityPipeline = null;
    
    const ClaimsOutbound = (await import('../models/od_live/ClaimsOutbound')).default;
    
    // Run pipeline
    const feeData = await ClaimsOutbound.aggregate(pipeline);
    const qualityData: any[] = [];
    
    // Extract quality metrics
    const quality = qualityData[0] || {};
    const dataQuality = {
      totalProcedures: quality.totalProcedures?.[0]?.count || 0,
      validFees: quality.validFees?.[0]?.count || 0,
      zeroFees: quality.zeroFees?.[0]?.count || 0,
      missingFees: quality.missingFees?.[0]?.count || 0,
      recentClaims: quality.recentClaims?.[0]?.count || 0,
      dataCompleteness: 0,
      freshness: 0
    };
    
    // Calculate percentages
    if (dataQuality.totalProcedures > 0) {
      dataQuality.dataCompleteness = Math.round((dataQuality.validFees / dataQuality.totalProcedures) * 100);
      dataQuality.freshness = Math.round((dataQuality.recentClaims / dataQuality.totalProcedures) * 100);
    }
    
    console.log(`📊 Data Quality Metrics:`);
    console.log(`  - Total procedures: ${dataQuality.totalProcedures}`);
    console.log(`  - Valid fees: ${dataQuality.validFees} (${dataQuality.dataCompleteness}%)`);  
    console.log(`  - Zero fees: ${dataQuality.zeroFees}`);
    console.log(`  - Missing fees: ${dataQuality.missingFees}`);
    console.log(`  - Recent claims: ${dataQuality.recentClaims} (${dataQuality.freshness}%)`);
    
    // Build comparison data for each CDT code with enhanced metrics
    const comparisons = CORE_CDT_CODES.map(cdtCode => {
      const carrierAData = feeData.find(d => 
        d._id.cdtCode === cdtCode && d._id.carrier === carrier_a
      );
      const carrierBData = feeData.find(d => 
        d._id.cdtCode === cdtCode && d._id.carrier === carrier_b
      );
      
      const feeA = carrierAData?.avgFee || 0;
      const feeB = carrierBData?.avgFee || 0;
      const dollarDiff = feeA - feeB;
      const percentDiff = feeB > 0 ? ((dollarDiff / feeB) * 100) : 0;
      
      // Calculate data confidence based on sample size
      const totalVolume = (carrierAData?.count || 0) + (carrierBData?.count || 0);
      const confidence = totalVolume >= 10 ? 'high' : totalVolume >= 5 ? 'medium' : 'low';
      
      return {
        cdtCode,
        description: CDT_DESCRIPTIONS[cdtCode],
        carrierAFee: Math.round(feeA * 100) / 100,
        carrierBFee: Math.round(feeB * 100) / 100,
        carrierAFeeRange: carrierAData ? {
          min: Math.round(carrierAData.minFee * 100) / 100,
          max: Math.round(carrierAData.maxFee * 100) / 100
        } : null,
        carrierBFeeRange: carrierBData ? {
          min: Math.round(carrierBData.minFee * 100) / 100,
          max: Math.round(carrierBData.maxFee * 100) / 100
        } : null,
        dollarDifference: Math.round(dollarDiff * 100) / 100,
        percentDifference: Math.round(percentDiff * 10) / 10,
        volume: totalVolume,
        carrierAVolume: carrierAData?.count || 0,
        carrierBVolume: carrierBData?.count || 0,
        dataConfidence: confidence,
        dateRange: {
          oldest: [carrierAData?.oldestDate, carrierBData?.oldestDate].filter(Boolean).sort()[0],
          latest: [carrierAData?.latestDate, carrierBData?.latestDate].filter(Boolean).sort().reverse()[0]
        }
      };
    }); // Include ALL CDT codes, even with no data
    
    // Apply sorting
    const sortedComparisons = [...comparisons].sort((a, b) => {
      switch (sort_by) {
        case 'percent_diff':
          return Math.abs(b.percentDifference) - Math.abs(a.percentDifference);
        case 'cdt_code':
          return a.cdtCode.localeCompare(b.cdtCode);
        case 'volume':
          return b.volume - a.volume;
        case 'dollar_diff':
        default:
          return Math.abs(b.dollarDifference) - Math.abs(a.dollarDifference);
      }
    });
    
    // Enhanced summary with data quality indicators
    const summary = {
      totalProcedures: comparisons.length,
      totalProceduresRequested: CORE_CDT_CODES.length,
      carrierAHigher: comparisons.filter(c => c.dollarDifference > 0).length,
      carrierBHigher: comparisons.filter(c => c.dollarDifference < 0).length,
      avgDifference: comparisons.length > 0 
        ? comparisons.reduce((sum, c) => sum + Math.abs(c.dollarDifference), 0) / comparisons.length
        : 0,
      dataQuality: {
        ...dataQuality,
        warnings: [] as string[]
      }
    };
    
    // Add data quality warnings
    if (dataQuality.dataCompleteness < 80) {
      summary.dataQuality.warnings.push(
        `Only ${dataQuality.dataCompleteness}% of procedures have valid fee data`
      );
    }
    if (dataQuality.freshness < 90) {
      summary.dataQuality.warnings.push(
        `Only ${dataQuality.freshness}% of claims are from the last ${monthsBack} months`
      );
    }
    if (comparisons.length < CORE_CDT_CODES.length * 0.5) {
      summary.dataQuality.warnings.push(
        `Insufficient data for ${CORE_CDT_CODES.length - comparisons.length} out of ${CORE_CDT_CODES.length} requested CDT codes`
      );
    }
    
    res.json({
      success: true,
      data: {
        comparisons: sortedComparisons,
        summary,
        carriers: {
          a: carrier_a,
          b: carrier_b
        },
        metadata: {
          dateRange: {
            from: dateCutoffStr,
            to: new Date().toISOString().split('T')[0]
          },
          locationId: location_id || 'all',
          providerNpi: provider_npi || 'all',
          sortBy: sort_by
        }
      }
    });
    
  } catch (error) {
    console.error('Fee comparison error:', error);
    res.status(500).json({
      success: false,
      message: 'Failed to generate fee comparison',
      error: error instanceof Error ? error.message : 'Unknown error'
    });
  }
};

/**
 * Get available carriers for carrier selection dropdowns
 * Uses the REAL carrier data from crucible.carriersRegistry
 */
export const getAvailableCarriers = async (req: Request, res: Response) => {
  try {
    const { org } = req.user!;
    const { location_id, source = 'hybrid' } = req.query;
    
    // Import the REAL carriers registry model
    const CarriersRegistry = (await import('../models/crucible/CarriersRegistry')).default;
    
    let carrierNames: string[] = [];
    
    if (source === 'registry' || source === 'hybrid') {
      // Method 1: Get carriers from the REAL crucible.carriersRegistry
      const registryCarriers = await CarriersRegistry.find({ 
        status: 'active' 
      })
      .select('carrierName carrierId status')
      .sort({ carrierName: 1 })
      .lean();
      
      const registryNames = registryCarriers.map(carrier => carrier.carrierName);
      carrierNames = [...carrierNames, ...registryNames];
    }
    
    if (source === 'claims' || source === 'hybrid') {
      // Method 2: Get carriers from claims data (includes carriers not in registry)
      // Get locations for filtering claims
      const locationQuery: any = { org: new Types.ObjectId(org) };
      if (location_id && Types.ObjectId.isValid(location_id as string)) {
        locationQuery._id = new Types.ObjectId(location_id as string);
      }
      
      const locations = await Location.find(locationQuery).lean();
      const locationIds = locations.map(loc => loc._id);
      
      // Get unique carrier names from claims data
      const claimsCarriers = await ClaimsOutbound.aggregate([
        { $match: { locationID: { $in: locationIds } } },
        { $unwind: { path: '$claims_data', preserveNullAndEmptyArrays: true } },
        { $unwind: { path: '$patients', preserveNullAndEmptyArrays: true } },
        {
          $project: {
            carrier: {
              $cond: [
                { $ne: ['$claims_data.matched_claim.carrier_name', null] },
                '$claims_data.matched_claim.carrier_name',
                '$patients.claims.matched_claim.carrier_name'
              ]
            }
          }
        },
        { $match: { carrier: { $exists: true, $ne: null } } },
        { $group: { _id: '$carrier' } },
        { $sort: { _id: 1 } }
      ]);
      
      const claimsNames = claimsCarriers.map(c => c._id).filter(Boolean);
      carrierNames = [...carrierNames, ...claimsNames];
    }
    
    // Remove duplicates and sort alphabetically
    const uniqueCarriers = [...new Set(carrierNames)].sort();
    
    console.log(`📊 Carriers found: Registry source: ${source === 'registry' || source === 'hybrid'}, Claims source: ${source === 'claims' || source === 'hybrid'}, Total unique: ${uniqueCarriers.length}`);
    
    res.status(200).json({
      success: true,
      message: 'Available carriers fetched successfully',
      data: { 
        carriers: uniqueCarriers,
        source,
        count: uniqueCarriers.length
      }
    });
  } catch (error) {
    console.error('Error fetching available carriers:', error);
    res.status(500).json({
      success: false,
      message: 'Failed to fetch available carriers',
      error: error instanceof Error ? error.message : 'Unknown error',
    });
  }
};

/**
 * Get detailed carriers from REAL registry with metadata
 */
export const getCarriersFromRegistry = async (req: Request, res: Response) => {
  try {
    const { active_only = 'true', include_metadata = 'false' } = req.query;
    
    // Import the REAL carriers registry model
    const CarriersRegistry = (await import('../models/crucible/CarriersRegistry')).default;
    
    // Build query
    const query: any = {};
    if (active_only === 'true') {
      query.status = 'active';
    }
    
    // Build projection
    const projection = include_metadata === 'true' 
      ? 'carrierName carrierId status metadata lastUpdated' 
      : 'carrierName carrierId status';
    
    const carriers = await CarriersRegistry.find(query)
      .select(projection)
      .sort({ carrierName: 1 })
      .lean();
    
    // Transform data to match expected format
    const transformedCarriers = carriers.map(carrier => ({
      id: carrier._id,
      name: carrier.carrierName,
      code: carrier.carrierId,
      active: carrier.status === 'active',
      metadata: carrier.metadata,
      lastUpdated: carrier.lastUpdated
    }));
    
    res.status(200).json({
      success: true,
      message: 'Carriers from REAL registry fetched successfully',
      data: { 
        carriers: transformedCarriers,
        count: transformedCarriers.length,
        activeOnly: active_only === 'true',
        includeMetadata: include_metadata === 'true',
        source: 'crucible.carriersRegistry'
      }
    });
  } catch (error) {
    console.error('Error fetching carriers from registry:', error);
    res.status(500).json({
      success: false,
      message: 'Failed to fetch carriers from registry',
      error: error instanceof Error ? error.message : 'Unknown error',
    });
  }
};

/**
 * Diagnostic endpoint to compare carriers between registry and claims data
 * Helps identify naming mismatches and mapping opportunities
 */
export const getCarrierMappingDiagnostics = async (req: Request, res: Response) => {
  try {
    const { org } = req.user!;
    const { location_id } = req.query;
    
    // Import Insurance Carrier model
    const InsuranceCarrier = (await import('../models/od_live/InsuranceCarrier')).default;
    
    // Get all active insurance carriers from registry
    const registryCarriers = await InsuranceCarrier.find({ active: true })
      .select('name code type networkStatus')
      .sort({ name: 1 })
      .lean();
    
    // Get locations for filtering claims
    const locationQuery: any = { org: new Types.ObjectId(org) };
    if (location_id && Types.ObjectId.isValid(location_id as string)) {
      locationQuery._id = new Types.ObjectId(location_id as string);
    }
    
    const locations = await Location.find(locationQuery).lean();
    const locationIds = locations.map(loc => loc._id);
    
    // Get unique carrier names from claims data
    const claimsCarriers = await ClaimsOutbound.aggregate([
      { $match: { locationID: { $in: locationIds } } },
      { $unwind: { path: '$claims_data', preserveNullAndEmptyArrays: true } },
      { $unwind: { path: '$patients', preserveNullAndEmptyArrays: true } },
      {
        $project: {
          carrier: {
            $cond: [
              { $ne: ['$claims_data.matched_claim.carrier_name', null] },
              '$claims_data.matched_claim.carrier_name',
              '$patients.claims.matched_claim.carrier_name'
            ]
          }
        }
      },
      { $match: { carrier: { $exists: true, $ne: null } } },
      { $group: { _id: '$carrier', count: { $sum: 1 } } },
      { $sort: { count: -1 } }
    ]);
    
    const registryNames = registryCarriers.map(c => c.name);
    const claimsNames = claimsCarriers.map(c => c._id);
    
    // Find potential matches and mismatches
    const potentialMatches: any[] = [];
    const unmatchedClaims: any[] = [];
    const unmatchedRegistry: any[] = [];
    
    // Check each claims carrier against registry
    for (const claimCarrier of claimsCarriers) {
      const matchedRegistry = findBestCarrierMatch(claimCarrier._id, registryCarriers);
      
      if (matchedRegistry !== claimCarrier._id) {
        // Found a potential match
        potentialMatches.push({
          claimsName: claimCarrier._id,
          registryName: matchedRegistry,
          claimsCount: claimCarrier.count,
          confidence: 'medium' // Could add more sophisticated scoring
        });
      } else if (!registryNames.includes(claimCarrier._id)) {
        // No match found in registry
        unmatchedClaims.push({
          name: claimCarrier._id,
          count: claimCarrier.count
        });
        }
    }
    
    // Find registry carriers not appearing in claims
    registryCarriers.forEach(regCarrier => {
      if (!claimsNames.includes(regCarrier.name)) {
        unmatchedRegistry.push({
          name: regCarrier.name,
          code: regCarrier.code
        });
      }
    });
    
    const diagnostics = {
      summary: {
        registryCarriers: registryCarriers.length,
        claimsCarriers: claimsCarriers.length,
        potentialMatches: potentialMatches.length,
        unmatchedClaims: unmatchedClaims.length,
        unmatchedRegistry: unmatchedRegistry.length
      },
      potentialMatches,
      unmatchedClaims: unmatchedClaims.slice(0, 20), // Limit for readability
      unmatchedRegistry: unmatchedRegistry.slice(0, 20),
      exactMatches: registryNames.filter(name => claimsNames.includes(name)).length
    };
    
    res.status(200).json({
      success: true,
      message: 'Carrier mapping diagnostics generated successfully',
      data: diagnostics
    });
  } catch (error) {
    console.error('Error generating carrier mapping diagnostics:', error);
    res.status(500).json({
      success: false,
      message: 'Failed to generate carrier mapping diagnostics',
      error: error instanceof Error ? error.message : 'Unknown error',
    });
  }
};

/**
 * Get providers who have actual claims processed for specified carriers
 * Only returns providers with claims data in the system
 */
export const getCredentialedProviders = async (req: Request, res: Response) => {
  try {
    const { carriers, location_id, months_back = '12' } = req.query;
    const { org } = req.user!;
    
    // Parse carriers array from query string
    const carrierList = Array.isArray(carriers) 
      ? carriers as string[] 
      : typeof carriers === 'string' 
        ? carriers.split(',') 
        : [];
    
    // Calculate date cutoff for data freshness
    const monthsBack = parseInt(months_back as string, 10) || 12;
    const dateCutoff = new Date();
    dateCutoff.setMonth(dateCutoff.getMonth() - monthsBack);
    const dateCutoffStr = dateCutoff.toISOString().split('T')[0];
    
    // Get user's locations
    const locations = await Location.find({ org: new Types.ObjectId(org) }).lean();
    const locationIds = location_id === 'all' || !location_id 
      ? locations.map(loc => loc._id)
      : [new Types.ObjectId(location_id as string)];
    
    // Query claims to find providers with actual claims data
    const pipeline: any[] = [
      {
        $match: {
          locationID: { $in: locationIds },
          ...(carrierList.length > 0 ? { carrier_name: { $in: carrierList } } : {}),
          procedures: { $exists: true, $ne: [] }
        }
      },
      { $unwind: '$procedures' },
      {
        $match: {
          'procedures.provider': { $exists: true },
          'procedures.provider.npi': { $exists: true, $ne: null },
          // Use correct field name
          'procedures.feeBilled': { $exists: true, $gt: 0 }
        }
      },
      {
        $group: {
          _id: {
            npi: '$procedures.provider.npi',
            name: '$procedures.provider.name'
          },
          carriers: { $addToSet: '$carrier_name' },
          claimCount: { $sum: 1 }
        }
      },
      {
        $project: {
          _id: 0,
          npi: '$_id.npi',
          name: '$_id.name',
          carriers: 1,
          claimCount: 1
        }
      },
      { $sort: { name: 1 } }
    ];
    
    const ClaimsOutbound = (await import('../models/od_live/ClaimsOutbound')).default;
    const providersWithClaims = await ClaimsOutbound.aggregate(pipeline);
    
    console.log(`👥 Found ${providersWithClaims.length} providers with claims for carriers: ${carrierList.join(', ') || 'all'} (last ${monthsBack} months)`);
    
    // Add data quality warning if few providers found
    const warnings = [];
    if (providersWithClaims.length === 0) {
      warnings.push('No providers found with recent claims data for the selected carriers');
    } else if (providersWithClaims.length < 5) {
      warnings.push(`Only ${providersWithClaims.length} providers found with recent claims data`);
    }
    
    res.json({
      success: true,
      data: {
        providers: providersWithClaims,
        summary: {
          totalProviders: providersWithClaims.length,
          requestedCarriers: carrierList,
          locationId: location_id || 'all',
          dateRange: {
            from: dateCutoffStr,
            to: new Date().toISOString().split('T')[0]
          },
          warnings
        }
      }
    });
  } catch (error) {
    console.error('Error fetching providers with claims:', error);
    res.status(500).json({
      success: false,
      message: 'Failed to fetch providers with claims',
      error: error instanceof Error ? error.message : 'Unknown error'
    });
  }
};

/**
 * Get fee comparison between two carriers
 */





/**
 * @desc    Get denial rate statistics
 * @route   GET /api/v1/analytics/denial-rate
 * @access  Private
 */
export const getDenialRate = async (req: Request, res: Response) => {
  try {
    const thirtyDaysAgo = new Date();
    thirtyDaysAgo.setDate(thirtyDaysAgo.getDate() - 30);

    const odLiveDb = getDatabase(DATABASE_NAMES.OD_LIVE);
    const ClaimsOutboundModel = odLiveDb.model('ClaimsOutbound');

    const denialPipeline = [
      {
        $match: {
          date_sent: { $gte: thirtyDaysAgo },
          status: { $exists: true }
        }
      },
      {
        $group: {
          _id: null, // Group all documents to calculate a single overall rate
          totalClaims: { $sum: 1 },
          deniedClaims: {
            $sum: {
              $cond: [
                {
                  $or: [
                    { $regexMatch: { input: '$status', regex: /DENIED/i } },
                    { $regexMatch: { input: '$status', regex: /REJECTED/i } }
                  ]
                },
                1,
                0
              ]
            }
          }
        }
      }
    ];

    const results = await ClaimsOutboundModel.aggregate(denialPipeline);
    const summary = results[0] || { totalClaims: 0, deniedClaims: 0 };

    const deniedPercentage = summary.totalClaims > 0 
      ? (summary.deniedClaims / summary.totalClaims) * 100 
      : 0;

    res.status(200).json({
      success: true,
      data: {
        totalClaims: summary.totalClaims,
        deniedClaims: summary.deniedClaims,
        deniedPercentage: deniedPercentage,
      }
    });

  } catch (error) {
    console.error('Error fetching denial rate data:', error);
    res.status(500).json({ success: false, error: 'Server Error' });
  }
};


