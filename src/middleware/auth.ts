import { Request, Response, NextFunction } from 'express';

// Extend Express Request to include auth info
declare global {
  namespace Express {
    interface Request {
      auth?: {
        type: 'apiKey' | 'bearer';
        sub?: string; // Subject from JWT
        apiKey?: string;
      };
    }
  }
}

/**
 * Authenticate requests using either API Key or Bearer JWT
 * Per OpenAPI spec: accepts x-api-key header OR Authorization: Bearer token
 */
export function authenticate(req: Request, res: Response, next: NextFunction) {
  // Skip auth for health check
  if (req.path === '/health') {
    return next();
  }

  const apiKey = req.headers['x-api-key'] as string;
  const authHeader = req.headers.authorization;

  // Check API Key
  if (apiKey) {
    // In production, validate against stored API keys
    // For now, check if it exists and is not empty
    if (apiKey.length > 0) {
      req.auth = { type: 'apiKey', apiKey };
      return next();
    }
  }

  // Check Bearer token
  if (authHeader && authHeader.startsWith('Bearer ')) {
    const token = authHeader.substring(7);
    
    try {
      // In production, verify JWT with proper secret/public key
      // For now, basic validation that token exists
      if (token.length > 0) {
        // Decode JWT (in production, use jsonwebtoken library)
        // This is a placeholder - real implementation would verify signature
        const [, payloadBase64] = token.split('.');
        if (payloadBase64) {
          try {
            const payload = JSON.parse(Buffer.from(payloadBase64, 'base64').toString());
            req.auth = { type: 'bearer', sub: payload.sub };
            return next();
          } catch {
            // Invalid JWT format
          }
        }
      }
    } catch (error) {
      // Invalid token
    }
  }

  // No valid auth provided
  res.status(401).json({ error: 'Unauthorized. Provide x-api-key header or Bearer token.' });
}