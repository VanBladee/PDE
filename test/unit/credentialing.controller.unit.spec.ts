import request from 'supertest';
import express from 'express';
import { CredentialingController } from '../../src/controllers/credentialing.controller';
import { CredentialingService } from '../../src/services/credentialing.service';

// Mock the service
jest.mock('../../src/services/credentialing.service');

describe('CredentialingController', () => {
  let app: express.Application;
  let mockService: jest.Mocked<CredentialingService>;
  let controller: CredentialingController;
  let consoleErrorSpy: jest.SpyInstance;

  const mockCredentialingData: any = {
    rows: [
      {
        provider_npi: "1234567890",
        provider_name: "Dr. Smith",
        tin: "12-3456789",
        location_id: "PROVO",
        carrier: "DELTA",
        plan: "PPO",
        status: "ACTIVE",
        effective_date: "2023-01-01",
        term_date: "2025-12-31",
        last_verified_at: "2024-12-01T00:00:00Z",
        verification_source: "Portal",
        source_url: "https://provider.delta.com",
        notes: "Verified via portal",
        is_manual_override: false,
        override_by: null,
        override_at: null,
        alerts: []
      },
      {
        provider_npi: "0987654321",
        provider_name: "Dr. Jones, \"MD\"",
        tin: "98-7654321",
        location_id: "VEGAS",
        carrier: "AETNA",
        plan: null,
        status: "OON",
        effective_date: "2023-06-01",
        term_date: null,
        last_verified_at: "2023-06-01T00:00:00Z",
        verification_source: "Manual",
        source_url: null,
        notes: "Out of network, needs review",
        is_manual_override: true,
        override_by: "admin@example.com",
        override_at: "2023-06-01T00:00:00Z",
        alerts: ["NETWORK_MISMATCH", "STALE_DATA"]
      }
    ],
    summary: {
      totalRows: 2,
      dateRange: { start: undefined, end: undefined },
      lastUpdated: new Date()
    }
  };

  beforeAll(() => {
    // Mock console.error to silence expected errors
    consoleErrorSpy = jest.spyOn(console, 'error').mockImplementation(() => {});
  });

  afterAll(() => {
    // Restore console.error
    consoleErrorSpy.mockRestore();
  });

  beforeEach(() => {
    // Reset mocks
    jest.clearAllMocks();

    // Create mock service
    mockService = {
      getCredentialingStatus: jest.fn().mockResolvedValue(mockCredentialingData),
      buildCredentialingPipeline: jest.fn()
    } as any;

    // Create controller with mock service
    controller = new CredentialingController(mockService);

    // Setup Express app for testing
    app = express();
    app.use(express.json());
    app.use(express.urlencoded({ extended: true }));

    // Setup routes
    app.get('/api/credentialing/status', (req, res) => controller.getStatus(req, res));
    app.get('/api/credentialing/export.csv', (req, res) => controller.exportCsv(req, res));
  });

  describe('GET /api/credentialing/status', () => {
    it('should return credentialing data with default filters', async () => {
      const response = await request(app)
        .get('/api/credentialing/status')
        .expect(200);

      expect(response.body.rows).toEqual(mockCredentialingData.rows);
      expect(response.body.summary.totalRows).toBe(2);
      expect(response.body.summary.lastUpdated).toBeDefined();
      expect(mockService.getCredentialingStatus).toHaveBeenCalledWith({
        start: undefined,
        end: undefined,
        locations: undefined,
        carriers: undefined,
        status: undefined,
        issuesOnly: false
      });
    });

    it('should handle array parameters with brackets notation', async () => {
      await request(app)
        .get('/api/credentialing/status')
        .query({
          'locations[]': ['PROVO', 'VEGAS'],
          'carriers[]': 'DELTA',
          start: '2024-01-01',
          end: '2024-12-31'
        })
        .expect(200);

      expect(mockService.getCredentialingStatus).toHaveBeenCalledWith({
        start: '2024-01-01',
        end: '2024-12-31',
        locations: ['PROVO', 'VEGAS'],
        carriers: ['DELTA'],
        status: undefined,
        issuesOnly: false
      });
    });

    it('should handle comma-separated parameters', async () => {
      await request(app)
        .get('/api/credentialing/status')
        .query({
          locations: 'PROVO,VEGAS',
          carriers: 'DELTA,AETNA',
          status: 'ACTIVE',
          issuesOnly: 'true'
        })
        .expect(200);

      expect(mockService.getCredentialingStatus).toHaveBeenCalledWith({
        start: undefined,
        end: undefined,
        locations: ['PROVO', 'VEGAS'],
        carriers: ['DELTA', 'AETNA'],
        status: 'ACTIVE',
        issuesOnly: true
      });
    });

    it('should handle status filter', async () => {
      await request(app)
        .get('/api/credentialing/status')
        .query({
          status: 'OON'
        })
        .expect(200);

      expect(mockService.getCredentialingStatus).toHaveBeenCalledWith({
        start: undefined,
        end: undefined,
        locations: undefined,
        carriers: undefined,
        status: 'OON',
        issuesOnly: false
      });
    });

    it('should handle issuesOnly filter', async () => {
      await request(app)
        .get('/api/credentialing/status')
        .query({
          issuesOnly: true
        })
        .expect(200);

      expect(mockService.getCredentialingStatus).toHaveBeenCalledWith({
        start: undefined,
        end: undefined,
        locations: undefined,
        carriers: undefined,
        status: undefined,
        issuesOnly: true
      });
    });

    it('should handle service errors', async () => {
      mockService.getCredentialingStatus.mockRejectedValue(new Error('Database error'));

      const response = await request(app)
        .get('/api/credentialing/status')
        .expect(500);

      expect(response.body).toEqual({ error: 'Database error' });
    });
  });

  describe('GET /api/credentialing/export.csv', () => {
    it('should return CSV with proper headers', async () => {
      const response = await request(app)
        .get('/api/credentialing/export.csv')
        .expect(200);

      expect(response.headers['content-type']).toBe('text/csv; charset=utf-8');
      expect(response.headers['content-disposition']).toBe('attachment; filename="credentialing-status.csv"');
      
      const lines = response.text.split('\n');
      expect(lines[0]).toBe('provider_npi,provider_name,tin,location_id,carrier,plan,status,effective_date,term_date,last_verified_at,verification_source,source_url,notes,is_manual_override,override_by,override_at,alerts');
      expect(lines).toHaveLength(3); // header + 2 data rows
    });

    it('should properly format CSV data rows', async () => {
      const response = await request(app)
        .get('/api/credentialing/export.csv')
        .expect(200);

      const lines = response.text.split('\n');
      
      // First data row (no alerts)
      expect(lines[1]).toBe('1234567890,Dr. Smith,12-3456789,PROVO,DELTA,PPO,ACTIVE,2023-01-01,2025-12-31,2024-12-01T00:00:00Z,Portal,https://provider.delta.com,Verified via portal,false,,,');
      
      // Second data row (with alerts and special characters)
      expect(lines[2]).toBe('0987654321,"Dr. Jones, ""MD""",98-7654321,VEGAS,AETNA,,OON,2023-06-01,,2023-06-01T00:00:00Z,Manual,,"Out of network, needs review",true,admin@example.com,2023-06-01T00:00:00Z,NETWORK_MISMATCH;STALE_DATA');
    });

    it('should handle empty results', async () => {
      mockService.getCredentialingStatus.mockResolvedValue({ 
        rows: [], 
        summary: {
          totalRows: 0,
          dateRange: { start: undefined, end: undefined },
          lastUpdated: new Date()
        }
      });

      const response = await request(app)
        .get('/api/credentialing/export.csv')
        .expect(200);

      expect(response.headers['content-type']).toBe('text/csv; charset=utf-8');
      expect(response.text).toBe('No data available');
    });

    it('should escape CSV fields with special characters', async () => {
      mockService.getCredentialingStatus.mockResolvedValue({
        rows: [{
          ...mockCredentialingData.rows[0],
          provider_name: 'Dr. "Quote", Comma',
          notes: 'Line 1\nLine 2'
        }],
        summary: mockCredentialingData.summary
      });

      const response = await request(app)
        .get('/api/credentialing/export.csv')
        .expect(200);

      // Verify the entire response contains the escaped fields
      expect(response.text).toContain('"Dr. ""Quote"", Comma"');
      expect(response.text).toContain('"Line 1');
      expect(response.text).toContain('Line 2"');
    });

    it('should apply filters to CSV export', async () => {
      await request(app)
        .get('/api/credentialing/export.csv')
        .query({
          locations: 'PROVO',
          status: 'ACTIVE',
          issuesOnly: 'true'
        })
        .expect(200);

      expect(mockService.getCredentialingStatus).toHaveBeenCalledWith({
        start: undefined,
        end: undefined,
        locations: ['PROVO'],
        carriers: undefined,
        status: 'ACTIVE',
        issuesOnly: true
      });
    });

    it('should handle null values properly in CSV', async () => {
      mockService.getCredentialingStatus.mockResolvedValue({
        rows: [{
          provider_npi: "1111111111",
          provider_name: "Dr. Null",
          tin: "11-1111111",
          location_id: "TEST",
          carrier: "TEST",
          plan: null,
          status: "ACTIVE",
          effective_date: null,
          term_date: null,
          last_verified_at: null,
          verification_source: null,
          source_url: null,
          notes: null,
          is_manual_override: false,
          override_by: null,
          override_at: null,
          alerts: []
        }],
        summary: mockCredentialingData.summary
      });

      const response = await request(app)
        .get('/api/credentialing/export.csv')
        .expect(200);

      const lines = response.text.split('\n');
      // Verify null values are represented as empty strings
      expect(lines[1]).toBe('1111111111,Dr. Null,11-1111111,TEST,TEST,,ACTIVE,,,,,,,false,,,');
    });

    it('should join multiple alerts with semicolon', async () => {
      mockService.getCredentialingStatus.mockResolvedValue({
        rows: [{
          ...mockCredentialingData.rows[0],
          alerts: ['NETWORK_MISMATCH', 'EXPIRING_SOON', 'STALE_DATA', 'PENDING_EFFECTIVE']
        }],
        summary: mockCredentialingData.summary
      });

      const response = await request(app)
        .get('/api/credentialing/export.csv')
        .expect(200);

      const lines = response.text.split('\n');
      expect(lines[1]).toContain('NETWORK_MISMATCH;EXPIRING_SOON;STALE_DATA;PENDING_EFFECTIVE');
    });
  });

  describe('Parameter normalization', () => {
    it('should handle mixed array and comma-separated params', async () => {
      await request(app)
        .get('/api/credentialing/status')
        .query({
          locations: 'PROVO',
          'carriers[]': ['DELTA', 'AETNA']
        })
        .expect(200);

      expect(mockService.getCredentialingStatus).toHaveBeenCalledWith({
        start: undefined,
        end: undefined,
        locations: ['PROVO'],
        carriers: ['DELTA', 'AETNA'],
        status: undefined,
        issuesOnly: false
      });
    });

    it('should handle single values as arrays', async () => {
      await request(app)
        .get('/api/credentialing/status')
        .query({
          locations: 'PROVO',
          carriers: 'DELTA'
        })
        .expect(200);

      expect(mockService.getCredentialingStatus).toHaveBeenCalledWith({
        start: undefined,
        end: undefined,
        locations: ['PROVO'],
        carriers: ['DELTA'],
        status: undefined,
        issuesOnly: false
      });
    });
  });
});