import { Request, Response } from 'express';
import Location from '../models/registry/Location';
import { Types } from 'mongoose';
import {
  getOrSetCache,
  clearCache,
  clearCacheByPrefix,
} from '../utils/cache';

/**
 * Get all locations for the user's organization with pagination
 */
export const getLocations = async (req: Request, res: Response) => {
  try {
    const { org } = req.user!; // Organization ID from auth middleware
    
    // Parse pagination parameters
    const page = parseInt(req.query.page as string) || 1;
    const limit = parseInt(req.query.limit as string) || 10;
    const skip = (page - 1) * limit;
    
    // Parse search and filter parameters
    const search = req.query.search as string;
    const region = req.query.region as string;
    const is_dso = req.query.is_dso === 'true' ? true : req.query.is_dso === 'false' ? false : undefined;
    const userId = req.query.userId as string;

    // Create cache key based on all filter parameters
    const cacheKey = `locations:${org}:page:${page}:limit:${limit}:search:${search || 'none'}:region:${region || 'all'}:dso:${is_dso !== undefined ? is_dso : 'all'}:userId:${userId || 'none'}`;
    
    const result = await getOrSetCache(
      cacheKey,
      async () => {
        // Build query filter
        const filter: any = {
          org: new Types.ObjectId(org), // Filter by user's organization
        };
        
        if (userId) {
          filter.users = { $in: [new Types.ObjectId(userId)] };
        }
        // Add search functionality
        if (search) {
          filter.$or = [
            { practice_name: { $regex: search, $options: 'i' } },
            { address: { $regex: search, $options: 'i' } },
            { phoneNumber: { $regex: search, $options: 'i' } },
          ];
        }
        
        // Add region filter
        if (region && region !== 'all') {
          filter.region = { $regex: region, $options: 'i' };
        }
        
        // Add DSO filter
        if (is_dso !== undefined) {
          filter.is_dso = is_dso;
        }
        
        // Execute queries in parallel for efficiency
        const [locations, totalCount] = await Promise.all([
          Location.find(filter)
            .select('-__v') // Exclude version field
            .sort({ practice_name: 1 }) // Sort alphabetically by practice name
            .skip(skip)
            .limit(limit)
            .lean(), // Use lean() for better performance on read-only queries
          Location.countDocuments(filter),
        ]);
        
        // Calculate pagination metadata
        const totalPages = Math.ceil(totalCount / limit);
        const hasNextPage = page < totalPages;
        const hasPrevPage = page > 1;
        
        return {
          locations,
          pagination: {
            currentPage: page,
            totalPages,
            totalCount,
            limit,
            hasNextPage,
            hasPrevPage,
          },
        };
      },
      'MEDIUM' // Cache for 10 minutes
    );
    
    res.status(200).json({
      success: true,
      data: result,
    });
  } catch (error) {
    console.error('Error fetching locations:', error);
    res.status(500).json({
      success: false,
      message: 'Failed to fetch locations',
      error: error instanceof Error ? error.message : 'Unknown error',
    });
  }
};

/**
 * Create a new location for the organization
 */
export const createLocation = async (req: Request, res: Response) => {
  try {
    const { org, id } = req.user!; // Organization ID and user ID from auth middleware
    const { 
      practice_name, 
      phoneNumber, 
      address, 
      taxId, 
      pms_db, 
      is_dso, 
      region,
      users 
    } = req.body;
    
    // Check if location with same practice name already exists in the organization
    const existingLocation = await Location.findOne({ 
      practice_name: practice_name?.trim() || '',
      org: new Types.ObjectId(org)
    });
    
    if (existingLocation) {
      return res.status(400).json({
        success: false,
        message: 'Location with this practice name already exists in your organization',
      });
    }
    
    // Create new location with organization ID and auto-set dso_admin to current user
    const newLocation = new Location({
      practice_name: practice_name?.trim() || '',
      phoneNumber: phoneNumber?.trim() || '',
      address: address?.trim() || '',
      taxId: taxId?.trim() || '',
      pms_db: pms_db?.trim() || 'OD_LIVE',
      is_dso: is_dso || false,
      dso_admin: id, // Auto-set to current user's ID
      users: users ? users.map((userId: string) => new Types.ObjectId(userId)) : [], // Convert string IDs to ObjectIds
      region: region?.trim() || '',
      org: new Types.ObjectId(org),
    });
    
    // Save location
    await newLocation.save();
    
    // Clear location caches for this organization
    await clearLocationCaches(org);
    
    // Return location without version field
    const locationResponse = await Location.findById(newLocation._id)
      .select('-__v')
      .lean();
    
    res.status(201).json({
      success: true,
      message: 'Location created successfully',
      data: locationResponse,
    });
  } catch (error) {
    console.error('Error creating location:', error);
    res.status(500).json({
      success: false,
      message: 'Failed to create location',
      error: error instanceof Error ? error.message : 'Unknown error',
    });
  }
};

/**
 * Get a single location by ID (must belong to user's organization)
 */
export const getLocationById = async (req: Request, res: Response) => {
  try {
    const { id } = req.params;
    const { org } = req.user!; // Organization ID from auth middleware
    
    // Validate ObjectId format
    if (!Types.ObjectId.isValid(id)) {
      return res.status(400).json({
        success: false,
        message: 'Invalid location ID format',
      });
    }
    
    // Create cache key for individual location
    const cacheKey = `location:${id}:org:${org}`;
    
    const location = await getOrSetCache(
      cacheKey,
      async () => {
        // Find location by ID and organization (security check)
        const loc = await Location.findOne({
          _id: new Types.ObjectId(id),
          org: new Types.ObjectId(org),
        })
          .select('-__v') // Exclude version field
          .lean(); // Use lean() for better performance
        
        if (!loc) {
          throw new Error('Location not found');
        }
        
        return loc;
      },
      'LONG' // Cache individual locations for 1 hour
    );
    
    res.status(200).json({
      success: true,
      data: location,
    });
  } catch (error) {
    if (error instanceof Error && error.message === 'Location not found') {
      return res.status(404).json({
        success: false,
        message: 'Location not found or access denied',
      });
    }
    
    console.error('Error fetching location:', error);
    res.status(500).json({
      success: false,
      message: 'Failed to fetch location',
      error: error instanceof Error ? error.message : 'Unknown error',
    });
  }
};

/**
 * Get a single location by name (must belong to user's organization)
 */
export const getLocationByName = async (req: Request, res: Response) => {
  try {
    const { name } = req.params;
    const { org } = req.user!; // Organization ID from auth middleware
    
    // Decode the URL-encoded name
    const decodedName = decodeURIComponent(name);
    
    console.log('Looking for location with name:', decodedName);
    
    // Create cache key for location by name
    const cacheKey = `location:name:${name}:org:${org}`;
    
    const location = await getOrSetCache(
      cacheKey,
      async () => {
        // Escape special regex characters in the decoded name
        const escapedName = decodedName.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
        
        // Find location by name and organization (case-insensitive)
        const loc = await Location.findOne({
          practice_name: { $regex: new RegExp(`^${escapedName}$`, 'i') },
          org: new Types.ObjectId(org),
        })
          .select('-__v') // Exclude version field
          .lean(); // Use lean() for better performance
        
        if (!loc) {
          throw new Error('Location not found');
        }
        
        return loc;
      },
      'LONG' // Cache individual locations for 1 hour
    );
    
    res.status(200).json({
      success: true,
      data: location,
    });
  } catch (error) {
    if (error instanceof Error && error.message === 'Location not found') {
      return res.status(404).json({
        success: false,
        message: 'Location not found or access denied',
      });
    }
    
    console.error('Error fetching location by name:', error);
    res.status(500).json({
      success: false,
      message: 'Failed to fetch location',
      error: error instanceof Error ? error.message : 'Unknown error',
    });
  }
};

/**
 * Get location statistics for the user's organization
 */
export const getLocationStats = async (req: Request, res: Response) => {
  try {
    const { org } = req.user!; // Organization ID from auth middleware
    
    // Create cache key for organization stats
    const cacheKey = `location-stats:${org}`;
    
    const result = await getOrSetCache(
      cacheKey,
      async () => {
        // Use aggregation pipeline for efficient statistics
        const stats = await Location.aggregate([
          {
            $match: {
              org: new Types.ObjectId(org),
            },
          },
          {
            $group: {
              _id: null,
              totalLocations: { $sum: 1 },
              dsoLocations: {
                $sum: { $cond: [{ $eq: ['$is_dso', true] }, 1, 0] },
              },
              regularLocations: {
                $sum: { $cond: [{ $eq: ['$is_dso', false] }, 1, 0] },
              },
              regions: { $addToSet: '$region' },
            },
          },
          {
            $project: {
              _id: 0,
              totalLocations: 1,
              dsoLocations: 1,
              regularLocations: 1,
              uniqueRegions: { $size: '$regions' },
            },
          },
        ]);
        
        return stats[0] || {
          totalLocations: 0,
          dsoLocations: 0,
          regularLocations: 0,
          uniqueRegions: 0,
        };
      },
      'LONG' // Cache stats for 1 hour since they don't change frequently
    );
    
    res.status(200).json({
      success: true,
      data: result,
    });
  } catch (error) {
    console.error('Error fetching location statistics:', error);
    res.status(500).json({
      success: false,
      message: 'Failed to fetch location statistics',
      error: error instanceof Error ? error.message : 'Unknown error',
    });
  }
};

/**
 * Utility function to clear location-related caches for an organization
 * This should be called when locations are created, updated, or deleted
 */
export const clearLocationCaches = async (orgId: string, locationId?: string) => {
  try {
    // Clear all list-based caches for this organization
    await clearCacheByPrefix(`locations:${orgId}:`);
    
    // Clear stats cache for the organization
    await clearCache(`location-stats:${orgId}`);
    
    // Clear specific location cache if locationId is provided
    if (locationId) {
      await clearCache(`location:${locationId}:org:${orgId}`);
    }
    
    console.log(`Cleared location caches for org: ${orgId}`);
  } catch (error) {
    console.error('Failed to clear location caches:', error);
  }
};

/**
 * Add a user to a location's user array
 */
export const addUserToLocation = async (req: Request, res: Response) => {
  try {
    const { id } = req.params; // Location ID
    const { userId } = req.body; // User ID to add
    const { org } = req.user!; // Organization ID from auth middleware

    if (!Types.ObjectId.isValid(id) || !Types.ObjectId.isValid(userId)) {
      return res.status(400).json({
        success: false,
        message: 'Invalid location or user ID format',
      });
    }

    const location = await Location.findOne({
      _id: new Types.ObjectId(id),
      org: new Types.ObjectId(org),
    });

    if (!location) {
      return res.status(404).json({
        success: false,
        message: 'Location not found or access denied',
      });
    }

    const userObjectId = new Types.ObjectId(userId);
    const userExists = location.users.some(user => user.equals(userObjectId));

    if (userExists) {
      return res.status(409).json({
        success: false,
        message: 'User is already assigned to this location',
      });
    }

    // Use $addToSet to prevent duplicate user entries
    await Location.updateOne(
      { _id: new Types.ObjectId(id) },
      { $addToSet: { users: userObjectId } }
    );

    // Clear caches for this location and organization
    await clearLocationCaches(org, id);

    res.status(200).json({
      success: true,
      message: 'User added to location successfully',
    });
  } catch (error) {
    console.error('Error adding user to location:', error);
    res.status(500).json({
      success: false,
      message: 'Failed to add user to location',
      error: error instanceof Error ? error.message : 'Unknown error',
    });
  }
};

/**
 * Remove a user from a location's user array
 */
export const removeUserFromLocation = async (req: Request, res: Response) => {
  try {
    const { id, userId } = req.params; // Location ID and User ID
    const { org } = req.user!; // Organization ID from auth middleware

    if (!Types.ObjectId.isValid(id) || !Types.ObjectId.isValid(userId)) {
      return res.status(400).json({
        success: false,
        message: 'Invalid location or user ID format',
      });
    }

    const location = await Location.findOne({
      _id: new Types.ObjectId(id),
      org: new Types.ObjectId(org),
    });

    if (!location) {
      return res.status(404).json({
        success: false,
        message: 'Location not found or access denied',
      });
    }
    
    // Use $pull to remove the user from the array
    const result = await Location.updateOne(
      { _id: new Types.ObjectId(id) },
      { $pull: { users: new Types.ObjectId(userId) } }
    );

    if (result.modifiedCount === 0) {
      return res.status(404).json({
        success: false,
        message: 'User was not found in this location\'s assigned users',
      });
    }

    // Clear caches for this location and organization
    await clearLocationCaches(org, id);

    res.status(200).json({
      success: true,
      message: 'User removed from location successfully',
    });
  } catch (error) {
    console.error('Error removing user from location:', error);
    res.status(500).json({
      success: false,
      message: 'Failed to remove user from location',
      error: error instanceof Error ? error.message : 'Unknown error',
    });
  }
};