import { Request, Response } from 'express';
import { CredentialingService } from '../services/credentialing.service';
import { createHash } from 'crypto';

interface CacheEntry {
  data: any;
  expires: number;
}

export class CredentialingController {
  private cache = new Map<string, CacheEntry>();
  private CACHE_TTL = 10 * 60 * 1000; // 10 minutes

  constructor(private credentialingService: CredentialingService) {}

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

  async getStatus(req: Request, res: Response) {
    try {
      const filters = {
        start: req.query.start as string | undefined,
        end: req.query.end as string | undefined,
        locations: this.normalizeArrayParam(req, 'locations'),
        carriers: this.normalizeArrayParam(req, 'carriers'),
        status: req.query.status as 'ACTIVE' | 'PENDING' | 'TERMINATED' | 'OON' | 'UNKNOWN' | undefined,
        issuesOnly: req.query.issuesOnly === 'true'
      };

      // Check cache
      const cacheKey = this.getCacheKey(filters);
      const cached = this.cache.get(cacheKey);
      if (cached && cached.expires > Date.now()) {
        res.setHeader('X-Cache', 'HIT');
        res.json(cached.data);
        return;
      }

      const results = await this.credentialingService.getCredentialingStatus(filters);
      
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
      console.error('Credentialing status error:', e);
      res.status(500).json({ error: (e as Error).message });
    }
  }

  async exportCsv(req: Request, res: Response) {
    try {
      const filters = {
        start: req.query.start as string | undefined,
        end: req.query.end as string | undefined,
        locations: this.normalizeArrayParam(req, 'locations'),
        carriers: this.normalizeArrayParam(req, 'carriers'),
        status: req.query.status as 'ACTIVE' | 'PENDING' | 'TERMINATED' | 'OON' | 'UNKNOWN' | undefined,
        issuesOnly: req.query.issuesOnly === 'true'
      };

      const { rows } = await this.credentialingService.getCredentialingStatus(filters);

      if (!rows?.length) {
        res.setHeader("Content-Type", "text/csv; charset=utf-8");
        res.send("No data available");
        return;
      }

      // Define CSV headers
      const headers = [
        "provider_npi",
        "provider_name", 
        "tin",
        "location_id",
        "carrier",
        "plan",
        "status",
        "effective_date",
        "term_date",
        "last_verified_at",
        "verification_source",
        "source_url",
        "notes",
        "is_manual_override",
        "override_by",
        "override_at",
        "alerts"
      ];

      // Helper to escape CSV fields
      const escapeField = (field: any) => {
        if (field === null || field === undefined) return '';
        const str = String(field);
        // If field contains comma, quote, or newline, wrap in quotes and escape quotes
        if (str.includes(',') || str.includes('"') || str.includes('\n')) {
          return `"${str.replace(/"/g, '""')}"`;
        }
        return str;
      };

      // Build CSV rows
      const csvRows = [
        headers.join(","),
        ...rows.map(row => {
          return [
            escapeField(row.provider_npi),
            escapeField(row.provider_name),
            escapeField(row.tin),
            escapeField(row.location_id),
            escapeField(row.carrier),
            escapeField(row.plan),
            escapeField(row.status),
            escapeField(row.effective_date),
            escapeField(row.term_date),
            escapeField(row.last_verified_at),
            escapeField(row.verification_source),
            escapeField(row.source_url),
            escapeField(row.notes),
            escapeField(row.is_manual_override),
            escapeField(row.override_by),
            escapeField(row.override_at),
            escapeField(row.alerts.join(';')) // Join alerts with semicolon
          ].join(",");
        })
      ].join("\n");

      // Set response headers
      res.setHeader("Content-Type", "text/csv; charset=utf-8");
      res.setHeader("Content-Disposition", 'attachment; filename="credentialing-status.csv"');
      res.send(csvRows);
    } catch (e) {
      console.error('Credentialing CSV error:', e);
      res.status(500).json({ error: (e as Error).message });
    }
  }
}