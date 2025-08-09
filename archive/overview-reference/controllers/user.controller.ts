import { Request, Response } from 'express';
import User, { IUser } from '../models/registry/User';
import Location from '../models/registry/Location';
import { Types } from 'mongoose';
import { getOrSetCache, clearCache, clearCacheByPrefix } from '../utils/cache';
import bcrypt from 'bcrypt';
// import { sendEmailInvite } from './auth.controller'; // TODO: Implement email invites

/**
 * Get all users for the user's organization with pagination
 */
export const getUsers = async (req: Request, res: Response) => {
  try {
    const { org } = req.user!; // Organization ID from auth middleware
    
    // Parse pagination parameters
    const page = parseInt(req.query.page as string) || 1;
    const limit = parseInt(req.query.limit as string) || 10;
    const skip = (page - 1) * limit;
    
    // Parse search parameter
    const search = req.query.search as string;
    
    // Create cache key based on all filter parameters
    const cacheKey = `users:${org}:page:${page}:limit:${limit}:search:${search || 'none'}`;
    
    const result = await getOrSetCache(
      cacheKey,
      async () => {
        // Build query filter
        const filter: any = {
          org: new Types.ObjectId(org), // Filter by user's organization
        };
        
        // Add search functionality
        if (search) {
          filter.$or = [
            { email: { $regex: search, $options: 'i' } },
            { firstName: { $regex: search, $options: 'i' } },
            { lastName: { $regex: search, $options: 'i' } },
          ];
        }
        
        // Execute queries in parallel for efficiency
        const [users, totalCount] = await Promise.all([
          User.find(filter)
            .select('-password -__v') // Exclude password and version fields
            .sort({ email: 1 }) // Sort alphabetically by email
            .skip(skip)
            .limit(limit)
            .lean(), // Use lean() for better performance on read-only queries
          User.countDocuments(filter),
        ]);
        
        // Calculate pagination metadata
        const totalPages = Math.ceil(totalCount / limit);
        const hasNextPage = page < totalPages;
        const hasPrevPage = page > 1;
        
        return {
          users,
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
      message: 'Users fetched successfully',
      data: result,
    });
  } catch (error) {
    console.error('Error fetching users:', error);
    res.status(500).json({
      success: false,
      message: 'Failed to fetch users',
      error: error instanceof Error ? error.message : 'Unknown error',
    });
  }
};

/**
 * Create a new user for the organization
 */
export const createUser = async (req: Request, res: Response) => {
  try {
    const { org } = req.user!; // Organization ID from auth middleware
    const { email, password, firstName, lastName, type, tier, processCounter, submitCounter, settings, selectedLocations } = req.body;
    
    // Check if user already exists
    const existingUser = await User.findOne({ email: email.toLowerCase() });
    if (existingUser) {
      return res.status(400).json({
        success: false,
        message: 'User with this email already exists',
      });
    }
    
    // Create new user with organization ID
    const newUser = new User({
      email: email.toLowerCase(),
      password,
      firstName,
      lastName: lastName || '',
      type: type || 'standard',
      tier: tier || 0,
      org: new Types.ObjectId(org),
      processCounter: processCounter || 0,
      submitCounter: submitCounter || 0,
      settings: settings || {},
    });
    
    // Get password reset token
    const resetToken = newUser.getPasswordResetToken();

    // Save user (password will be hashed automatically by pre-save hook)
    await newUser.save();
    
    // TODO: Send email invite when sendEmailInvite is implemented
    // try {
    //   await sendEmailInvite(newUser.email, resetToken);
    // } catch (error) {
    //   console.error('Failed to send email invite:', error);
    // }

    // Update selected locations to include the new user
    if (selectedLocations && selectedLocations.length > 0) {
      // const Location = (await import('../models/registry/Location')).default; // This line is no longer needed
      
      // Update each selected location's users array
      await Promise.all(
        selectedLocations.map(async (locationId: string) => {
          await Location.findByIdAndUpdate(
            locationId,
            { $addToSet: { users: newUser._id } },
            { new: true }
          );
        })
      );
    }
    
    // Clear user caches for this organization
    await clearUserCaches(org);
    
    // Return user without password
    const userResponse = await User.findById(newUser._id)
      .select('-password -__v')
      .lean();
    
    res.status(201).json({
      success: true,
      message: 'User created successfully. Invitation email sent.',
      data: userResponse,
    });
  } catch (error) {
    console.error('Error creating user:', error);
    res.status(500).json({
      success: false,
      message: 'Failed to create user',
      error: error instanceof Error ? error.message : 'Unknown error',
    });
  }
};

/**
 * Get a single user by ID (must belong to user's organization)
 */
export const getUserById = async (req: Request, res: Response) => {
  try {
    const { id } = req.params;
    const { org } = req.user!; // Organization ID from auth middleware
    
    // Validate ObjectId format
    if (!Types.ObjectId.isValid(id)) {
      return res.status(400).json({
        success: false,
        message: 'Invalid user ID format',
      });
    }
    
    // Create cache key for individual user
    const cacheKey = `user:${id}:org:${org}`;
    
    const user = await getOrSetCache(
      cacheKey,
      async () => {
        // Find user by ID and organization (security check)
        const foundUser = await User.findOne({
          _id: new Types.ObjectId(id),
          org: new Types.ObjectId(org),
        })
          .select('-password -__v') // Exclude password and version fields
          .lean(); // Use lean() for better performance
        
        if (!foundUser) {
          throw new Error('User not found');
        }
        
        return foundUser;
      },
      'LONG' // Cache individual users for 1 hour
    );
    
    res.status(200).json({
      success: true,
      data: user,
    });
  } catch (error) {
    if (error instanceof Error && error.message === 'User not found') {
      return res.status(404).json({
        success: false,
        message: 'User not found or access denied',
      });
    }
    
    console.error('Error fetching user:', error);
    res.status(500).json({
      success: false,
      message: 'Failed to fetch user',
      error: error instanceof Error ? error.message : 'Unknown error',
    });
  }
};

/**
 * Update user details
 */
export const updateUser = async (req: Request, res: Response) => {
  try {
    const { id } = req.params;
    const { org } = req.user!;
    const updateData = req.body;
    
    // Validate ObjectId format
    if (!Types.ObjectId.isValid(id)) {
      return res.status(400).json({
        success: false,
        message: 'Invalid user ID format',
      });
    }
    
    // Don't allow updating certain fields
    delete updateData.org;
    delete updateData._id;
    delete updateData.password; // Password updates should be handled separately
    
    // Update user
    const updatedUser = await User.findOneAndUpdate(
      {
        _id: new Types.ObjectId(id),
        org: new Types.ObjectId(org),
      },
      updateData,
      {
        new: true,
        runValidators: true,
      }
    ).select('-password -__v');
    
    if (!updatedUser) {
      return res.status(404).json({
        success: false,
        message: 'User not found or access denied',
      });
    }
    
    // Clear caches
    await clearCache(`user:${id}:org:${org}`);
    await clearUserCaches(org);
    
    res.status(200).json({
      success: true,
      message: 'User updated successfully',
      data: updatedUser,
    });
  } catch (error) {
    console.error('Error updating user:', error);
    res.status(500).json({
      success: false,
      message: 'Failed to update user',
      error: error instanceof Error ? error.message : 'Unknown error',
    });
  }
};

/**
 * Update user type
 */
export const updateUserType = async (req: Request, res: Response) => {
  try {
    const { id } = req.params;
    const { org } = req.user!;
    const { type } = req.body;

    // Validate input
    if (!type || typeof type !== 'string') {
      return res.status(400).json({
        success: false,
        message: 'Type is required and must be a string',
      });
    }

    // Validate ObjectId format
    if (!Types.ObjectId.isValid(id)) {
      return res.status(400).json({
        success: false,
        message: 'Invalid user ID format',
      });
    }

    // Update only the type field
    const updatedUser = await User.findOneAndUpdate(
      { _id: new Types.ObjectId(id), org: new Types.ObjectId(org) },
      { type },
      { new: true, runValidators: true }
    ).select('-password -__v');

    if (!updatedUser) {
      return res.status(404).json({
        success: false,
        message: 'User not found or access denied',
      });
    }

    // Clear caches
    await clearCache(`user:${id}:org:${org}`);
    await clearUserCaches(org, id);

    res.status(200).json({
      success: true,
      message: 'User type updated successfully',
      data: updatedUser,
    });
  } catch (error) {
    console.error('Error updating user type:', error);
    res.status(500).json({
      success: false,
      message: 'Failed to update user type',
      error: error instanceof Error ? error.message : 'Unknown error',
    });
  }
};

/**
 * Update user tier
 */
export const updateUserTier = async (req: Request, res: Response) => {
  try {
    const { id } = req.params;
    const { org } = req.user!;
    const { tier } = req.body;

    // Validate input
    if (tier === undefined || typeof tier !== 'number') {
      return res.status(400).json({
        success: false,
        message: 'Tier is required and must be a number',
      });
    }

    // Validate ObjectId format
    if (!Types.ObjectId.isValid(id)) {
      return res.status(400).json({
        success: false,
        message: 'Invalid user ID format',
      });
    }

    // Update only the tier field
    const updatedUser = await User.findOneAndUpdate(
      { _id: new Types.ObjectId(id), org: new Types.ObjectId(org) },
      { tier },
      { new: true, runValidators: true },
    ).select('-password -__v');

    if (!updatedUser) {
      return res.status(404).json({
        success: false,
        message: 'User not found or access denied',
      });
    }

    // Clear caches
    await clearCache(`user:${id}:org:${org}`);
    await clearUserCaches(org, id);

    res.status(200).json({
      success: true,
      message: 'User tier updated successfully',
      data: updatedUser,
    });
  } catch (error) {
    console.error('Error updating user tier:', error);
    res.status(500).json({
      success: false,
      message: 'Failed to update user tier',
      error: error instanceof Error ? error.message : 'Unknown error',
    });
  }
};

/**
 * Delete a user
 */
export const deleteUser = async (req: Request, res: Response) => {
  try {
    const { id } = req.params;
    const { org } = req.user!;

    // Validate ObjectId format
    if (!Types.ObjectId.isValid(id)) {
      return res.status(400).json({
        success: false,
        message: 'Invalid user ID format',
      });
    }

    const userId = new Types.ObjectId(id);

    // Find user to be deleted
    const userToDelete = await User.findOne({
      _id: userId,
      org: new Types.ObjectId(org),
    });

    if (!userToDelete) {
      return res.status(404).json({
        success: false,
        message: 'User not found or access denied',
      });
    }

    // Use a transaction to ensure atomicity
    const session = await User.startSession();
    session.startTransaction();

    try {
      // 1. Delete the user
      await User.deleteOne({ _id: userId }, { session });

      // 2. Remove the user from any locations they were assigned to
      await Location.updateMany(
        { users: userId },
        { $pull: { users: userId } },
        { session }
      );

      // Commit the transaction
      await session.commitTransaction();
      session.endSession();

      // Clear caches after successful deletion
      await clearCache(`user:${id}:org:${org}`);
      await clearUserCaches(org);

      res.status(200).json({
        success: true,
        message: 'User deleted successfully.',
      });
    } catch (transactionError) {
      // If anything fails, abort the transaction
      await session.abortTransaction();
      session.endSession();
      throw transactionError; // Rethrow to be caught by outer catch block
    }
  } catch (error) {
    console.error('Error deleting user:', error);
    res.status(500).json({
      success: false,
      message: 'Failed to delete user',
      error: error instanceof Error ? error.message : 'Unknown error',
    });
  }
};

/**
 * Updates a user's status to ACTIVE or INACTIVE.
 * @param res The Express response object.
 * @param userId The ID of the user to update.
 * @param orgId The organization ID of the user.
 * @param newStatus The new status to set ('ACTIVE' or 'INACTIVE').
 */
const updateUserStatus = async (
  res: Response,
  userId: string,
  orgId: string,
  newStatus: 'ACTIVE' | 'INACTIVE'
) => {
  // Validate ObjectId format
  if (!Types.ObjectId.isValid(userId)) {
    return res.status(400).json({
      success: false,
      message: 'Invalid user ID format',
    });
  }

  try {
    // Find user by ID and organization
    const user = await User.findOne({
      _id: new Types.ObjectId(userId),
      org: new Types.ObjectId(orgId),
    });

    if (!user) {
      return res.status(404).json({
        success: false,
        message: 'User not found or access denied',
      });
    }

    // Do not allow changing status if it's 'PENDING'
    if (user.settings.status === 'PENDING') {
      return res.status(400).json({
        success: false,
        message: 'Cannot change status of a user that is pending approval.',
      });
    }

    // Update the user's status
    user.settings.status = newStatus;
    await user.save();

    // Clear caches
    await clearUserCaches(orgId, userId);

    // Return success response
    res.status(200).json({
      success: true,
      message: `User status updated to ${newStatus}`,
      data: user,
    });
  } catch (error) {
    console.error(`Error updating user status to ${newStatus}:`, error);
    res.status(500).json({
      success: false,
      message: `Failed to update user status to ${newStatus}`,
      error: error instanceof Error ? error.message : 'Unknown error',
    });
  }
};


/**
 * Deactivates a user, setting their status to INACTIVE.
 */
export const deactivateUser = async (req: Request, res: Response) => {
  const { id } = req.params;
  const { org } = req.user!;
  await updateUserStatus(res, id, org, 'INACTIVE');
};

/**
 * Activates a user, setting their status to ACTIVE.
 */
export const activateUser = async (req: Request, res: Response) => {
  const { id } = req.params;
  const { org } = req.user!;
  await updateUserStatus(res, id, org, 'ACTIVE');
};


/**
 * Utility function to clear user-related caches for an organization
 * This should be called when users are created, updated, or deleted
 */
export const clearUserCaches = async (orgId: string, userId?: string) => {
  // Clear organization-specific user caches
  await clearCacheByPrefix(`users:${orgId}:`);
  
  // Clear specific user cache if userId provided
  if (userId) {
    await clearCache(`user:${userId}:org:${orgId}`);
  }
};

/**
 * Update user settings (e.g., darkMode preference)
 */
export const updateUserSettings = async (req: Request, res: Response) => {
  try {
    const userId = req.user!.id;
    const { darkMode } = req.body;
    
    console.log('Updating user settings:', { userId, darkMode });
    
    // Update only the settings fields that were provided
    const updateData: any = {};
    if (darkMode !== undefined) {
      updateData['settings.darkMode'] = darkMode;
    }
    
    console.log('Update data:', updateData);
    
    // Update user settings
    const updatedUser = await User.findByIdAndUpdate(
      userId,
      { $set: updateData },
      {
        new: true,
        runValidators: true,
      }
    ).select('-password -__v');
    
    if (!updatedUser) {
      return res.status(404).json({
        success: false,
        message: 'User not found',
      });
    }
    
    console.log('User settings updated:', updatedUser.settings);
    
    // Clear user cache
    await clearCache(`user:${userId}:org:${req.user!.org}`);
    
    res.status(200).json({
      success: true,
      message: 'Settings updated successfully',
      data: updatedUser,
    });
  } catch (error) {
    console.error('Error updating user settings:', error);
    res.status(500).json({
      success: false,
      message: 'Failed to update settings',
      error: error instanceof Error ? error.message : 'Unknown error',
    });
  }
};