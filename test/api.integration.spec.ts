import request from 'supertest';
import express from 'express';
import { MongoClient } from 'mongodb';
import { MongoMemoryServer } from 'mongodb-memory-server';
import routes from '../src/routes';
import { errorHandler } from '../src/middleware/error-handler';
import { UnifiedClaimsService } from '../src/services/unified-claims.service';

describe('API Integration Tests', () => {
  let mongod: MongoMemoryServer;
  let client: MongoClient;
  let app: express.Application;

  beforeAll(async () => {
    // Start in-memory MongoDB
    mongod = await MongoMemoryServer.create();
    
    // Connect client for seeding data
    client = new MongoClient(mongod.getUri());
    await client.connect();

    // Create Express app for testing
    app = express();
    app.use(express.json());
    app.use(express.urlencoded({ extended: true }));
    
    // Mock MongoDB client in app locals
    app.locals.mongoClient = client;
    
    // Health check
    app.get('/health', (_req, res) => {
      res.json({ status: 'ok', timestamp: new Date().toISOString() });
    });
    
    // Routes
    app.use('/', routes);
    
    // Error handler
    app.use(errorHandler);
  });

  afterAll(async () => {
    // Close connections
    await client.close();
    await mongod.stop();
  });

  describe('Authentication', () => {
    it('should reject requests without authentication', async () => {
      const response = await request(app)
        .get('/api/fee-strategy/pivot')
        .expect(401);

      expect(response.body).toEqual({
        error: 'Unauthorized. Provide x-api-key header or Bearer token.'
      });
    });

    it.skip('should accept requests with API key', async () => {
      // Skip: Cross-DB lookups not supported in test environment
      const response = await request(app)
        .get('/api/fee-strategy/pivot')
        .set('x-api-key', 'test-api-key')
        .expect(200);

      expect(response.body).toHaveProperty('rows');
      expect(response.body).toHaveProperty('summary');
    });

    it.skip('should accept requests with Bearer token', async () => {
      // Skip: Cross-DB lookups not supported in test environment
      // Create a simple JWT for testing (header.payload.signature)
      const header = Buffer.from(JSON.stringify({ alg: 'HS256', typ: 'JWT' })).toString('base64');
      const payload = Buffer.from(JSON.stringify({ sub: 'test-user', exp: Date.now() + 3600000 })).toString('base64');
      const token = `${header}.${payload}.fake-signature`;

      const response = await request(app)
        .get('/api/fee-strategy/pivot')
        .set('Authorization', `Bearer ${token}`)
        .expect(200);

      expect(response.body).toHaveProperty('rows');
      expect(response.body).toHaveProperty('summary');
    });

    it('should not require auth for health check', async () => {
      const response = await request(app)
        .get('/health')
        .expect(200);

      expect(response.body).toHaveProperty('status', 'ok');
      expect(response.body).toHaveProperty('timestamp');
    });
  });

  describe('Fee Strategy Endpoints', () => {
    beforeEach(async () => {
      // Seed test data
      const activity = client.db('activity');
      const registry = client.db('registry');
      const crucible = client.db('crucible');

      await activity.collection('processedclaims').deleteMany({});
      await activity.collection('jobs').deleteMany({});
      await registry.collection('locations').deleteMany({});
      await crucible.collection('PDC_fee_schedules').deleteMany({});
    });

    it.skip('should return empty results when no data exists', async () => {
      // Skip: Cross-DB lookups not supported in test environment
      const response = await request(app)
        .get('/api/fee-strategy/pivot')
        .set('x-api-key', 'test-key')
        .expect(200);

      expect(response.body.rows).toEqual([]);
      expect(response.body.summary.totalRows).toBe(0);
    });

    it.skip('should handle all query parameters correctly', async () => {
      // Skip: Cross-DB lookups not supported in test environment
      const response = await request(app)
        .get('/api/fee-strategy/pivot')
        .set('x-api-key', 'test-key')
        .query({
          start: '2024-01-01',
          end: '2024-12-31',
          'locations[]': ['PROVO', 'VEGAS'],
          'carriers[]': 'DELTA',
          procedures: 'D0120,D0140',
          minCount: '1',
          page: '1',
          limit: '100'
        })
        .expect(200);

      expect(response.body).toHaveProperty('rows');
      expect(response.body).toHaveProperty('summary');
    });

    it.skip('should return CSV with correct content type', async () => {
      // Skip: Cross-DB lookups not supported in test environment
      const response = await request(app)
        .get('/api/fee-strategy/pivot.csv')
        .set('x-api-key', 'test-key')
        .expect(200);

      expect(response.headers['content-type']).toContain('text/csv');
      expect(response.headers['content-disposition']).toContain('attachment');
      expect(response.headers['content-disposition']).toContain('fee-strategy-pivot.csv');
    });

    it('should redirect legacy endpoint', async () => {
      const response = await request(app)
        .get('/fee-strategy/pivot-data')
        .set('x-api-key', 'test-key')
        .query({ locations: 'PROVO' })
        .expect(302);

      expect(response.headers.location).toContain('/api/fee-strategy/pivot');
      expect(response.headers.location).toContain('locations=PROVO');
    });
  });

  describe('Credentialing Endpoints', () => {
    it.skip('should return credentialing status data', async () => {
      // Skip: Cross-DB lookups not supported in test environment
      const response = await request(app)
        .get('/api/credentialing/status')
        .set('x-api-key', 'test-key')
        .expect(200);

      expect(response.body).toHaveProperty('rows');
      expect(response.body).toHaveProperty('summary');
      expect(response.body.summary).toHaveProperty('totalRows');
      expect(response.body.summary).toHaveProperty('lastUpdated');
    });

    it.skip('should accept query parameters for credentialing status', async () => {
      // Skip: Cross-DB lookups not supported in test environment
      const response = await request(app)
        .get('/api/credentialing/status')
        .set('x-api-key', 'test-key')
        .query({
          locations: 'PROVO,VEGAS',
          status: 'ACTIVE',
          issuesOnly: 'true'
        })
        .expect(200);

      expect(response.body).toHaveProperty('rows');
      expect(response.body).toHaveProperty('summary');
    });

    it.skip('should return CSV for credentialing export', async () => {
      // Skip: Cross-DB lookups not supported in test environment
      const response = await request(app)
        .get('/api/credentialing/export.csv')
        .set('x-api-key', 'test-key')
        .expect(200);

      expect(response.headers['content-type']).toContain('text/csv');
      expect(response.headers['content-disposition']).toContain('attachment');
      expect(response.headers['content-disposition']).toContain('credentialing-status.csv');
    });
  });

  describe('Error Handling', () => {
    it('should return 404 for unknown routes', async () => {
      await request(app)
        .get('/api/unknown-endpoint')
        .set('x-api-key', 'test-key')
        .expect(404);
    });

    it('should handle malformed JSON', async () => {
      await request(app)
        .post('/api/fee-strategy/pivot')
        .set('x-api-key', 'test-key')
        .set('Content-Type', 'application/json')
        .send('{ invalid json')
        .expect(400);
    });
  });
});