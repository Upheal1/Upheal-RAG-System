# Docker Services Reference

> Local Supabase development stack — container inventory, ports, and resource usage.

---

## Container Overview

| Container | Image | Version | Status | Size |
|-----------|-------|---------|--------|------|
| `supabase_db_Upheal-RAG-System` | `public.ecr.aws/supabase/postgres` | `17.6.1.106` | ✅ Healthy | 1.68 GB |
| `supabase_auth_Upheal-RAG-System` | `public.ecr.aws/supabase/gotrue` | `v2.188.1` | ✅ Healthy | 80.2 MB |
| `supabase_rest_Upheal-RAG-System` | `public.ecr.aws/supabase/postgrest` | `v14.10` | ✅ Healthy | 27.4 MB |
| `supabase_realtime_Upheal-RAG-System` | `public.ecr.aws/supabase/realtime` | `v2.86.3` | ✅ Healthy | 629 MB |
| `supabase_storage_Upheal-RAG-System` | `public.ecr.aws/supabase/storage-api` | `v1.54.1` | ✅ Healthy | 1.35 GB |
| `supabase_edge_runtime_Upheal-RAG-System` | `public.ecr.aws/supabase/edge-runtime` | `v1.73.13` | ✅ Healthy | 1.12 GB |
| `supabase_studio_Upheal-RAG-System` | `public.ecr.aws/supabase/studio` | `2026.04.28-sha-89d08a2` | ✅ Healthy | 1.54 GB |
| `supabase_pg_meta_Upheal-RAG-System` | `public.ecr.aws/supabase/postgres-meta` | `v0.96.4` | ✅ Healthy | 505 MB |
| `supabase_kong_Upheal-RAG-System` | `public.ecr.aws/supabase/kong` | `2.8.1` | ✅ Healthy | 203 MB |
| `supabase_inbucket_Upheal-RAG-System` | `public.ecr.aws/supabase/mailpit` | `v1.22.3` | ✅ Healthy | 43.5 MB |
| `supabase_analytics_Upheal-RAG-System` | `public.ecr.aws/supabase/logflare` | `1.39.1` | ✅ Healthy | 905 MB |
| `supabase_vector_Upheal-RAG-System` | `public.ecr.aws/supabase/vector` | `0.53.0-alpine` | 🔄 Restarting | 209 MB |

**Total image footprint:** ~7.26 GB

---

## Service Details

### Database (`supabase_db`)

| Property | Value |
|----------|-------|
| **Image** | `public.ecr.aws/supabase/postgres:17.6.1.106` |
| **Container** | `supabase_db_Upheal-RAG-System` |
| **Host Port** | `54322` |
| **Container Port** | `5432` |
| **Connection URL** | `postgresql://postgres:postgres@127.0.0.1:54322/postgres` |
| **Purpose** | Main PostgreSQL database for the project |

> **Note:** A second Postgres container `sleepy_hermann` (`17.6.1.111`) runs on port `54320` — this is the shadow database used by `supabase db diff` / `db pull`.

---

### Auth (`supabase_auth`)

| Property | Value |
|----------|-------|
| **Image** | `public.ecr.aws/supabase/gotrue:v2.188.1` |
| **Container** | `supabase_auth_Upheal-RAG-System` |
| **Container Port** | `9999` |
| **Purpose** | GoTrue authentication server (JWT, OAuth, MFA) |

---

### REST API (`supabase_rest`)

| Property | Value |
|----------|-------|
| **Image** | `public.ecr.aws/supabase/postgrest:v14.10` |
| **Container** | `supabase_rest_Upheal-RAG-System` |
| **Container Port** | `3000` |
| **Purpose** | PostgREST auto-generated REST API from Postgres schema |
| **Exposed via** | Kong gateway at `http://localhost:54321/rest/v1` |

---

### Realtime (`supabase_realtime`)

| Property | Value |
|----------|-------|
| **Image** | `public.ecr.aws/supabase/realtime:v2.86.3` |
| **Container** | `supabase_realtime_Upheal-RAG-System` |
| **Container Port** | `4000` |
| **Purpose** | WebSocket server for live Postgres changes |

---

### Storage (`supabase_storage`)

| Property | Value |
|----------|-------|
| **Image** | `public.ecr.aws/supabase/storage-api:v1.54.1` |
| **Container** | `supabase_storage_Upheal-RAG-System` |
| **Container Port** | `5000` |
| **Purpose** | S3-compatible object storage API |

---

### Edge Functions (`supabase_edge_runtime`)

| Property | Value |
|----------|-------|
| **Image** | `public.ecr.aws/supabase/edge-runtime:v1.73.13` |
| **Container** | `supabase_edge_runtime_Upheal-RAG-System` |
| **Container Port** | `8081` |
| **Purpose** | Deno runtime for serverless edge functions |
| **Exposed via** | Kong gateway at `http://localhost:54321/functions/v1` |

---

### Studio (`supabase_studio`)

| Property | Value |
|----------|-------|
| **Image** | `public.ecr.aws/supabase/studio:2026.04.28-sha-89d08a2` |
| **Container** | `supabase_studio_Upheal-RAG-System` |
| **Host Port** | `54323` |
| **Container Port** | `3000` |
| **URL** | [http://127.0.0.1:54323](http://127.0.0.1:54323) |
| **Purpose** | Supabase Dashboard GUI for managing database, auth, storage |

---

### Postgres Meta (`supabase_pg_meta`)

| Property | Value |
|----------|-------|
| **Image** | `public.ecr.aws/supabase/postgres-meta:v0.96.4` |
| **Container** | `supabase_pg_meta_Upheal-RAG-System` |
| **Container Port** | `8080` |
| **Purpose** | Schema introspection API used by Studio |
| **Exposed via** | Kong at `/pg/*` |

---

### API Gateway (`supabase_kong`)

| Property | Value |
|----------|-------|
| **Image** | `public.ecr.aws/supabase/kong:2.8.1` |
| **Container** | `supabase_kong_Upheal-RAG-System` |
| **Host Port** | `54321` |
| **Container Port** | `8000` |
| **URL** | [http://127.0.0.1:54321](http://127.0.0.1:54321) |
| **Purpose** | Reverse proxy routing all services through a single endpoint |

**Kong routes:**

| Path | Service |
|------|---------|
| `/rest/v1` | PostgREST |
| `/auth/v1` | GoTrue |
| `/storage/v1` | Storage API |
| `/realtime/v1` | Realtime |
| `/functions/v1` | Edge Runtime |
| `/pg/*` | Postgres Meta |
| `/mcp` | MCP Server |

---

### Email (`supabase_inbucket`)

| Property | Value |
|----------|-------|
| **Image** | `public.ecr.aws/supabase/mailpit:v1.22.3` |
| **Container** | `supabase_inbucket_Upheal-RAG-System` |
| **Host Port** | `54324` |
| **Container Port** | `8025` |
| **URL** | [http://127.0.0.1:54324](http://127.0.0.1:54324) |
| **Purpose** | Email capture for testing (catches all auth emails locally) |

---

### Analytics (`supabase_analytics`)

| Property | Value |
|----------|-------|
| **Image** | `public.ecr.aws/supabase/logflare:1.39.1` |
| **Container** | `supabase_analytics_Upheal-RAG-System` |
| **Host Port** | `54327` |
| **Container Port** | `4000` |
| **Purpose** | Log aggregation and analytics backend |
| **Note** | ⚠️ Analytics on Windows requires Docker daemon exposed on `tcp://localhost:2375` |

---

### Log Collector (`supabase_vector`)

| Property | Value |
|----------|-------|
| **Image** | `public.ecr.aws/supabase/vector:0.53.0-alpine` |
| **Container** | `supabase_vector_Upheal-RAG-System` |
| **Status** | 🔄 Restarting loop (Windows limitation) |
| **Purpose** | Log shipping to analytics backend |
| **Note** | ⚠️ Vector container is in a restart loop on Windows. This is a known issue and does not affect core functionality. |

---

## Port Map

```
┌─────────────────────────────────────────────────────────────┐
│                     Localhost Ports                         │
├──────────┬──────────────────────────────────────────────────┤
│ 54321    │ Kong Gateway (all APIs)                          │
│ 54322    │ Postgres Database                                │
│ 54323    │ Supabase Studio (Dashboard GUI)                  │
│ 54324    │ Mailpit (Email testing)                          │
│ 54327    │ Logflare (Analytics)                             │
└──────────┴──────────────────────────────────────────────────┘
```

---

## Quick Commands

```bash
# Start local Supabase
npx supabase start

# Stop local Supabase
npx supabase stop

# Check container status
docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"

# View logs for a specific service
docker logs -f supabase_db_Upheal-RAG-System
docker logs -f supabase_auth_Upheal-RAG-System

# Restart a single container
docker restart supabase_db_Upheal-RAG-System

# Access Postgres directly
docker exec -it supabase_db_Upheal-RAG-System psql -U postgres -d postgres

# Reset database (destructive)
npx supabase db reset

# Link to cloud project
npx supabase link --project-ref gcxxmjptbyvlabqzcprv

# Push migrations to cloud
npx supabase db push
```

---

## Troubleshooting

### Vector container restarting

**Symptom:** `supabase_vector_Upheal-RAG-System` shows `Restarting (0)`

**Cause:** Windows Docker socket path limitation. Vector cannot access Docker daemon logs.

**Impact:** Log shipping to analytics is broken. Core database/auth/rest services are unaffected.

**Fix:** Not required for local development. To expose Docker daemon on Windows:
1. Docker Desktop → Settings → General → **Expose daemon on tcp://localhost:2375**
2. Restart Supabase: `npx supabase stop && npx supabase start`

---

### Port conflicts

**Symptom:** `supabase start` fails with "port already allocated"

**Fix:** Find and kill the process using the port:

```powershell
# Find PID using port 54322
netstat -ano | findstr :54322

# Kill the process
taskkill /PID <PID> /F
```

---

### Database won't start after migration error

**Symptom:** Migration fails, database is in inconsistent state

**Fix:**
```bash
# Reset local database (wipes all data)
npx supabase db reset

# Or reset linked remote database
npx supabase db reset --linked
```

---

## Image Registry

All Supabase images are pulled from AWS Public ECR:

```
public.ecr.aws/supabase/
```

To update to latest versions:
```bash
npx supabase stop
docker pull public.ecr.aws/supabase/postgres:latest
npx supabase start
```

---

## Resource Usage (Typical)

| Resource | Usage |
|----------|-------|
| **RAM** | ~2.5–4 GB (all containers running) |
| **Disk** | ~7.3 GB (images) + database volume growth |
| **CPU** | Low idle; spikes during ingestion/migrations |

**Free tier disk warning:** With 500 MB database limit, monitor growth via `log_table_sizes` view or Studio.
