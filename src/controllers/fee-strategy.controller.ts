import { Request, Response } from 'express';
import { UnifiedClaimsService } from '../services/unified-claims.service';
import { createHash } from 'crypto';

interface CacheEntry {
  data: any;
  expires: number;
}

export class FeeStrategyController {
  private cache = new Map<string, CacheEntry>();
  private CACHE_TTL = 10 * 60 * 1000; // 10 minutes

  constructor(private unifiedClaimsService: UnifiedClaimsService) {}

  // Helper to normalize array params (supports locations[], carriers[] etc)
  private normalizeArrayParam(req: Request, paramName: string): string[] | undefined {
    // Check for array brackets notation first (locations[])
    const bracketParam = req.query[`${paramName}[]`];
    if (bracketParam) {
      return Array.isArray(bracketParam) ? bracketParam as string[] : [bracketParam as string];
    }

    // Check regular param
    const param = req.query[paramName];
    if (!param) return undefined;

    // If already array, return it
    if (Array.isArray(param)) {
      return param as string[];
    }

    // If string, check if comma-separated
    const strParam = param as string;
    return strParam.includes(',') ? strParam.split(',') : [strParam];
  }

  // Generate cache key from filters
  private getCacheKey(filters: any): string {
    return createHash('md5').update(JSON.stringify(filters)).digest('hex');
  }

  async getPivot(req: Request, res: Response) {
    try {
      const filters = {
        start: req.query.start as string | undefined,
        end: req.query.end as string | undefined,
        locations: this.normalizeArrayParam(req, 'locations'),
        carriers: this.normalizeArrayParam(req, 'carriers'),
        procedures: this.normalizeArrayParam(req, 'procedures'),
        minCount: Number(req.query.minCount ?? 0),
        page: Number(req.query.page ?? 1),
        limit: Number(req.query.limit ?? 20000)
      };

      // Check cache
      const cacheKey = this.getCacheKey(filters);
      const cached = this.cache.get(cacheKey);
      if (cached && cached.expires > Date.now()) {
        res.setHeader('X-Cache', 'HIT');
        res.json(cached.data);
        return;
      }

      const results = await this.unifiedClaimsService.getFeeStrategyPivot(filters);
      
      // Cache the results
      this.cache.set(cacheKey, {
        data: results,
        expires: Date.now() + this.CACHE_TTL
      });

      // Clean expired entries periodically
      if (this.cache.size > 100) {
        for (const [key, entry] of this.cache) {
          if (entry.expires <= Date.now()) {
            this.cache.delete(key);
          }
        }
      }

      res.setHeader('X-Cache', 'MISS');
      res.json(results);
    } catch (e) { 
      console.error('Fee strategy pivot error:', e);
      res.status(500).json({ error: (e as Error).message }); 
    }
  }

  async getPivotCsv(req: Request, res: Response) {
    try {
      const filters = {
        start: req.query.start as string | undefined,
        end: req.query.end as string | undefined,
        locations: this.normalizeArrayParam(req, 'locations'),
        carriers: this.normalizeArrayParam(req, 'carriers'),
        procedures: this.normalizeArrayParam(req, 'procedures'),
        minCount: Number(req.query.minCount ?? 0)
      };
      
      const { rows } = await this.unifiedClaimsService.getFeeStrategyPivot(filters);
      
      if (!rows?.length) {
        res.setHeader("Content-Type", "text/csv");
        res.send("No data available");
        return;
      }
      
      const headers = ["carrier","locationId","locationCode","locationName","procedure","month","billed","allowed","paid","writeOff","writeOffPct","feeScheduled","scheduleVariance","claimCount","hasIssues"];
      const csv = [headers.join(","), ...rows.map(r => {
        // Escape fields that might contain commas
        const escapeField = (field: any) => {
          const str = String(field ?? '');
          return str.includes(',') || str.includes('"') || str.includes('\n') 
            ? `"${str.replace(/"/g, '""')}"`
            : str;
        };
        
        return [
          escapeField(r.carrier),
          escapeField(r.locationId),
          escapeField(r.locationCode),
          escapeField(r.locationName),
          escapeField(r.procedure),
          escapeField(r.month),
          r.metrics.billed,
          r.metrics.allowed,
          r.metrics.paid,
          r.metrics.writeOff,
          r.metrics.writeOffPct,
          r.metrics.feeScheduled ?? '',
          r.metrics.scheduleVariance ?? '',
          r.metrics.claimCount,
          r.hasIssues
        ].join(",");
      })].join("\n");
      
      res.setHeader("Content-Type","text/csv");
      res.setHeader("Content-Disposition",'attachment; filename="fee-strategy-pivot.csv"');
      res.send(csv);
    } catch (e) {
      console.error('Fee strategy CSV error:', e);
      res.status(500).json({ error: (e as Error).message });
    }
  }

  // Legacy route handler - redirect to new endpoint
  async pivotDataLegacy(req: Request, res: Response) {
    // Build query string from original params
    const queryString = Object.entries(req.query)
      .map(([key, value]) => {
        if (Array.isArray(value)) {
          return value.map(v => `${key}=${encodeURIComponent(String(v))}`).join('&');
        }
        return `${key}=${encodeURIComponent(String(value))}`;
      })
      .join('&');
    
    res.redirect(302, `/api/fee-strategy/pivot${queryString ? '?' + queryString : ''}`);
  }
}