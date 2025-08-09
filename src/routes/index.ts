import { Router } from 'express';
import { MongoClient } from 'mongodb';
import { FeeStrategyController } from '../controllers/fee-strategy.controller';
import { CredentialingController } from '../controllers/credentialing.controller';
import { UnifiedClaimsService } from '../services/unified-claims.service';
import { CredentialingService } from '../services/credentialing.service';
import { authenticate } from '../middleware/auth';

const router = Router();

// Apply authentication to all routes except health check
router.use(authenticate);

// Initialize services and controllers with MongoDB client
router.use((req, res, next) => {
  const client = req.app.locals.mongoClient as MongoClient;
  if (!client) {
    res.status(500).json({ error: 'Database connection not available' });
    return;
  }

  // Initialize services
  const unifiedClaimsService = new UnifiedClaimsService(client);
  const credentialingService = new CredentialingService(client);
  
  // Initialize controllers
  const feeStrategyController = new FeeStrategyController(unifiedClaimsService);
  const credentialingController = new CredentialingController(credentialingService);

  // Make controllers available to routes
  req.app.locals.feeStrategyController = feeStrategyController;
  req.app.locals.credentialingController = credentialingController;
  
  next();
});

// Fee Strategy routes
router.get('/api/fee-strategy/pivot', (req, res, next) => {
  const controller = req.app.locals.feeStrategyController as FeeStrategyController;
  controller.getPivot(req, res).catch(next);
});

router.get('/api/fee-strategy/pivot.csv', (req, res, next) => {
  const controller = req.app.locals.feeStrategyController as FeeStrategyController;
  controller.getPivotCsv(req, res).catch(next);
});

// Legacy compatibility route
router.get('/fee-strategy/pivot-data', (req, res, next) => {
  const controller = req.app.locals.feeStrategyController as FeeStrategyController;
  controller.pivotDataLegacy(req, res).catch(next);
});

// Credentialing routes
router.get('/api/credentialing/status', (req, res, next) => {
  const controller = req.app.locals.credentialingController as CredentialingController;
  controller.getStatus(req, res).catch(next);
});

router.get('/api/credentialing/export.csv', (req, res, next) => {
  const controller = req.app.locals.credentialingController as CredentialingController;
  controller.exportCsv(req, res).catch(next);
});

export default router;