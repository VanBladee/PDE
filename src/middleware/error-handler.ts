import { Request, Response, NextFunction } from 'express';

interface ApiError extends Error {
  statusCode?: number;
  details?: any;
}

/**
 * Global error handler middleware
 * Formats errors according to OpenAPI spec Error schema
 */
export function errorHandler(
  err: ApiError,
  req: Request,
  res: Response,
  _next: NextFunction
) {
  // Log error for debugging
  console.error('Error:', {
    path: req.path,
    method: req.method,
    error: err.message,
    stack: err.stack,
    details: err.details
  });

  // Determine status code
  const statusCode = err.statusCode || 500;

  // Format error response per OpenAPI spec
  const errorResponse = {
    error: err.message || 'Internal server error'
  };

  // Send response
  res.status(statusCode).json(errorResponse);
}

/**
 * Create a standardized API error
 */
export function createApiError(message: string, statusCode: number, details?: any): ApiError {
  const error = new Error(message) as ApiError;
  error.statusCode = statusCode;
  error.details = details;
  return error;
}