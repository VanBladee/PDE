Mission: maintain Fee Strategy Pivot & Credentialing APIs per /openapi/admin-cockpit.yaml.
Read /agents/prompts/system.txt as your system prompt. Only modify code in /src and /scripts.
Use Mongo cross-DB $lookup (same Atlas cluster), $convert(onError:0) for money, TZ=America/Denver.
Indexes via scripts/create-indexes.ts. Passing tests + OpenAPI conformance = done.
