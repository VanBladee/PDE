Mission: maintain Fee Strategy Pivot & Credentialing APIs per /openapi/admin-cockpit.yaml.
Read /agents/prompts/system.txt as your system prompt. Only modify code in /src and /scripts.
Use Mongo cross-DB $lookup (same Atlas cluster), $convert(onError:0) for money, TZ=America/Denver.
Indexes via scripts/create-indexes.ts. Passing tests + OpenAPI conformance = done.

DB boundaries (HARD RULE):
- activity: processedclaims, jobs
- registry: locations
- crucible: PDC_fee_schedules, PDC_provider_status, and any new PDC_* collections
- od_live: OpenDental live stuff
Never create/read PDC_* in activity. Always use cross-DB $lookup: { from: { db: "crucible", coll: "PDC_*" } }

DB boundaries apply in tests too. Seed registry.locations and all PDC_* collections in crucible, never in activity.
Cross-DB $lookup must remain in the service, including in tests. Do not switch to single-DB fallbacks.
If needed, pin mongodb-memory-server to a modern MongoDB binary (≥6.0) so cross-DB $lookup works.
