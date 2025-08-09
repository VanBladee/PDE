// src/controllers/sessions.controller.ts
import { Request, Response } from 'express';
import { getCache } from '../utils/cache';

/**
 * @desc    Check the online status of multiple users
 * @route   POST /api/v1/sessions/status
 * @access  Private
 */
export const getUsersOnlineStatus = async (req: Request, res: Response) => {
  try {
    const { userIds } = req.body;

    if (!Array.isArray(userIds)) {
      return res.status(400).json({ success: false, error: 'userIds must be an array' });
    }

    const statusMap: Record<string, boolean> = {};

    // Check the cache for each user's session
    for (const userId of userIds) {
      // A common convention is to store a session key like 'session:<userId>'
      // Or to check for a user data cache key that has a short expiry.
      // We will check for the user data cache key as a proxy for being "online".
      const cacheKey = `user:${userId}`;
      const userData = await getCache(cacheKey);
      statusMap[userId] = userData !== null;
    }

    res.status(200).json({
      success: true,
      data: statusMap,
    });

  } catch (error) {
    console.error('Error fetching user online status:', error);
    res.status(500).json({ success: false, error: 'Server Error' });
  }
};
