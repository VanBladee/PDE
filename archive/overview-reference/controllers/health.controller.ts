import { Request, Response } from 'express';
import mongoose from 'mongoose';
import { getDatabase, DATABASE_NAMES } from '../config/databases';

/**
 * Health check endpoint to verify database connections
 */
export const healthCheck = async (req: Request, res: Response) => {
  try {
    const healthStatus = {
      status: 'healthy',
      timestamp: new Date().toISOString(),
      mongoose: {
        readyState: mongoose.connection.readyState,
        host: mongoose.connection.host,
        port: mongoose.connection.port,
        name: mongoose.connection.name,
      },
      databases: {} as Record<string, any>,
    };

    // Check each database connection
    for (const [key, dbName] of Object.entries(DATABASE_NAMES)) {
      try {
        const db = getDatabase(dbName as any);
        healthStatus.databases[dbName] = {
          status: 'connected',
          readyState: db.readyState,
        };
      } catch (error) {
        healthStatus.databases[dbName] = {
          status: 'error',
          error: error instanceof Error ? error.message : 'Unknown error',
        };
      }
    }

    // Check if any database has errors
    const hasErrors = Object.values(healthStatus.databases).some(
      (db: any) => db.status === 'error'
    );

    if (hasErrors) {
      healthStatus.status = 'degraded';
      return res.status(200).json(healthStatus);
    }

    res.status(200).json(healthStatus);
  } catch (error) {
    console.error('Health check error:', error);
    res.status(500).json({
      status: 'unhealthy',
      timestamp: new Date().toISOString(),
      error: error instanceof Error ? error.message : 'Unknown error',
    });
  }
}; 