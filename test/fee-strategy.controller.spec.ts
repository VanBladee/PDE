import request from 'supertest';
import express from 'express';
import { FeeStrategyController } from '../src/controllers/fee-strategy.controller';
import { UnifiedClaimsService } from '../src/services/unified-claims.service';

// Mock the service
jest.mock('../src/services/unified-claims.service');

describe('FeeStrategyController', () => {
  let app: express.Application;
  let mockService: jest.Mocked<UnifiedClaimsService>;
  let controller: FeeStrategyController;

  const mockPivotData: any = {
    rows: [
      {
        carrier: 'DELTA',
        locationId: '123',
        locationCode: 'PROVO',
        locationName: 'Provo Clinic',
        procedure: 'D0120',
        month: '2024-01',
        metrics: {
          billed: 150,
          allowed: 95,
          paid: 76,
          writeOff: 55,
          writeOffPct: 0.3667,
          feeScheduled: 80,
          scheduleVariance: 0.1875,
          claimCount: 1
        },
        hasIssues: false
      }
    ],
    summary: {
      totalRows: 1,
      dateRange: { start: '2024-01-01', end: '2024-01-31' },
      lastUpdated: new Date().toISOString()
    }
  };

  beforeEach(() => {
    // Reset mocks
    jest.clearAllMocks();

    // Create mock service
    mockService = {
      getFeeStrategyPivot: jest.fn().mockResolvedValue(mockPivotData)
    } as any;

    // Create controller with mock service
    controller = new FeeStrategyController(mockService);

    // Setup Express app for testing
    app = express();
    app.use(express.json());
    app.use(express.urlencoded({ extended: true }));

    // Setup routes
    app.get('/api/fee-strategy/pivot', (req, res) => controller.getPivot(req, res));
    app.get('/api/fee-strategy/pivot.csv', (req, res) => controller.getPivotCsv(req, res));
    app.get('/fee-strategy/pivot-data', (req, res) => controller.pivotDataLegacy(req, res));
  });

  describe('GET /api/fee-strategy/pivot', () => {
    it('should return pivot data with default filters', async () => {
      const response = await request(app)
        .get('/api/fee-strategy/pivot')
        .expect(200);

      expect(response.body).toEqual(mockPivotData);
      expect(mockService.getFeeStrategyPivot).toHaveBeenCalledWith({
        start: undefined,
        end: undefined,
        locations: undefined,
        carriers: undefined,
        procedures: undefined,
        minCount: 0,
        page: 1,
        limit: 20000
      });
    });

    it('should handle array parameters with brackets notation', async () => {
      await request(app)
        .get('/api/fee-strategy/pivot')
        .query({
          'locations[]': ['PROVO', 'VEGAS'],
          'carriers[]': 'DELTA',
          start: '2024-01-01',
          end: '2024-01-31'
        })
        .expect(200);

      expect(mockService.getFeeStrategyPivot).toHaveBeenCalledWith({
        start: '2024-01-01',
        end: '2024-01-31',
        locations: ['PROVO', 'VEGAS'],
        carriers: ['DELTA'],
        procedures: undefined,
        minCount: 0,
        page: 1,
        limit: 20000
      });
    });

    it('should handle comma-separated parameters', async () => {
      await request(app)
        .get('/api/fee-strategy/pivot')
        .query({
          locations: 'PROVO,VEGAS',
          procedures: 'D0120,D0140',
          minCount: '5',
          page: '2',
          limit: '100'
        })
        .expect(200);

      expect(mockService.getFeeStrategyPivot).toHaveBeenCalledWith({
        start: undefined,
        end: undefined,
        locations: ['PROVO', 'VEGAS'],
        carriers: undefined,
        procedures: ['D0120', 'D0140'],
        minCount: 5,
        page: 2,
        limit: 100
      });
    });

    it('should use cached results on second request', async () => {
      // First request
      await request(app)
        .get('/api/fee-strategy/pivot')
        .query({ locations: 'PROVO' })
        .expect(200);

      expect(mockService.getFeeStrategyPivot).toHaveBeenCalledTimes(1);

      // Second request with same params should use cache
      await request(app)
        .get('/api/fee-strategy/pivot')
        .query({ locations: 'PROVO' })
        .expect(200);

      // Service should still only be called once
      expect(mockService.getFeeStrategyPivot).toHaveBeenCalledTimes(1);
    });

    it('should handle service errors', async () => {
      mockService.getFeeStrategyPivot.mockRejectedValue(new Error('Database error'));

      const response = await request(app)
        .get('/api/fee-strategy/pivot')
        .expect(500);

      expect(response.body).toEqual({ error: 'Database error' });
    });
  });

  describe('GET /api/fee-strategy/pivot.csv', () => {
    it('should return CSV with proper headers', async () => {
      const response = await request(app)
        .get('/api/fee-strategy/pivot.csv')
        .expect(200);

      expect(response.headers['content-type']).toBe('text/csv; charset=utf-8');
      expect(response.headers['content-disposition']).toBe('attachment; filename="fee-strategy-pivot.csv"');
      
      const lines = response.text.split('\n');
      expect(lines[0]).toBe('carrier,locationId,locationCode,locationName,procedure,month,billed,allowed,paid,writeOff,writeOffPct,feeScheduled,scheduleVariance,claimCount,hasIssues');
      expect(lines[1]).toBe('DELTA,123,PROVO,Provo Clinic,D0120,2024-01,150,95,76,55,0.3667,80,0.1875,1,false');
    });

    it('should handle empty results', async () => {
      mockService.getFeeStrategyPivot.mockResolvedValue({ 
        rows: [], 
        summary: {
          totalRows: 0,
          dateRange: { start: undefined, end: undefined },
          lastUpdated: new Date()
        }
      });

      const response = await request(app)
        .get('/api/fee-strategy/pivot.csv')
        .expect(200);

      expect(response.headers['content-type']).toBe('text/csv; charset=utf-8');
      expect(response.text).toBe('No data available');
    });

    it('should escape CSV fields with special characters', async () => {
      mockService.getFeeStrategyPivot.mockResolvedValue({
        rows: [{
          ...mockPivotData.rows[0],
          locationName: 'Clinic, "Special"'
        }],
        summary: mockPivotData.summary
      });

      const response = await request(app)
        .get('/api/fee-strategy/pivot.csv')
        .expect(200);

      const lines = response.text.split('\n');
      expect(lines[1]).toContain('"Clinic, ""Special"""');
    });

    it('should not include pagination params for CSV', async () => {
      await request(app)
        .get('/api/fee-strategy/pivot.csv')
        .query({ page: '2', limit: '100' })
        .expect(200);

      expect(mockService.getFeeStrategyPivot).toHaveBeenCalledWith({
        start: undefined,
        end: undefined,
        locations: undefined,
        carriers: undefined,
        procedures: undefined,
        minCount: 0
        // Note: page and limit are NOT passed for CSV
      });
    });
  });

  describe('GET /fee-strategy/pivot-data (legacy)', () => {
    it('should redirect to new endpoint with all query params', async () => {
      const response = await request(app)
        .get('/fee-strategy/pivot-data')
        .query({
          'locations[]': ['PROVO', 'VEGAS'],
          start: '2024-01-01',
          minCount: '5'
        })
        .expect(302);

      // Query params are normalized without brackets in the redirect
      expect(response.headers.location).toBe('/api/fee-strategy/pivot?locations=PROVO&locations=VEGAS&start=2024-01-01&minCount=5');
    });

    it('should handle empty query params', async () => {
      const response = await request(app)
        .get('/fee-strategy/pivot-data')
        .expect(302);

      expect(response.headers.location).toBe('/api/fee-strategy/pivot');
    });
  });

  describe('Parameter normalization', () => {
    it('should handle mixed array and comma-separated params', async () => {
      await request(app)
        .get('/api/fee-strategy/pivot')
        .query({
          locations: 'PROVO',
          'carriers[]': ['DELTA', 'AETNA'],
          procedures: 'D0120,D0140,D1110'
        })
        .expect(200);

      expect(mockService.getFeeStrategyPivot).toHaveBeenCalledWith({
        start: undefined,
        end: undefined,
        locations: ['PROVO'],
        carriers: ['DELTA', 'AETNA'],
        procedures: ['D0120', 'D0140', 'D1110'],
        minCount: 0,
        page: 1,
        limit: 20000
      });
    });

    it('should handle single values as arrays', async () => {
      await request(app)
        .get('/api/fee-strategy/pivot')
        .query({
          locations: 'PROVO',
          carriers: 'DELTA',
          procedures: 'D0120'
        })
        .expect(200);

      expect(mockService.getFeeStrategyPivot).toHaveBeenCalledWith({
        start: undefined,
        end: undefined,
        locations: ['PROVO'],
        carriers: ['DELTA'],
        procedures: ['D0120'],
        minCount: 0,
        page: 1,
        limit: 20000
      });
    });
  });

  describe('Cache behavior', () => {
    it('should cache results for 10 minutes', async () => {
      const now = Date.now();
      jest.spyOn(Date, 'now').mockReturnValue(now);

      // First request
      await request(app).get('/api/fee-strategy/pivot').expect(200);
      expect(mockService.getFeeStrategyPivot).toHaveBeenCalledTimes(1);

      // Request 5 minutes later - should use cache
      jest.spyOn(Date, 'now').mockReturnValue(now + 5 * 60 * 1000);
      await request(app).get('/api/fee-strategy/pivot').expect(200);
      expect(mockService.getFeeStrategyPivot).toHaveBeenCalledTimes(1);

      // Request 11 minutes later - cache expired
      jest.spyOn(Date, 'now').mockReturnValue(now + 11 * 60 * 1000);
      await request(app).get('/api/fee-strategy/pivot').expect(200);
      expect(mockService.getFeeStrategyPivot).toHaveBeenCalledTimes(2);
    });

    it('should use different cache keys for different params', async () => {
      await request(app)
        .get('/api/fee-strategy/pivot')
        .query({ locations: 'PROVO' })
        .expect(200);

      await request(app)
        .get('/api/fee-strategy/pivot')
        .query({ locations: 'VEGAS' })
        .expect(200);

      expect(mockService.getFeeStrategyPivot).toHaveBeenCalledTimes(2);
    });
  });
});