# Proxy Manager -- Design Document

**Date:** 2026-02-14
**Status:** Draft
**Authors:** Brainstorm team (UX Designer, Technical Architect, Devil's Advocate, Product Manager)

---

## 1. Overview

A self-hosted, open-source proxy management platform for teams and individuals who purchase proxies from multiple providers and need intelligent rotation, per-project isolation, and real-time observability -- without vendor lock-in.

### Why Now

- Scrapoxy (the leading open-source proxy manager, 11+ years) was recently discontinued -- massive vacuum
- 43% of scraping professionals use 2-3+ proxy providers with no unified management tool
- No open-source tool combines BYOP support, multi-project isolation, target-aware blacklisting, and observability

### Build Philosophy

The tool is built in **3 phases**, each fully functional. Phase 1 is barely usable but works end-to-end. Each subsequent phase layers on top without rewriting what came before.

---

## 2. Tech Stack (All Phases)

| Layer | Technology | Rationale |
|-------|------------|-----------|
| Framework | FastAPI + Uvicorn (uvloop) | Auto OpenAPI docs, Pydantic validation, async-native |
| Database | PostgreSQL 16 + asyncpg | Relational integrity for M:N, table partitioning later |
| ORM | SQLAlchemy 2.0 async + Alembic | Mature migrations, complex queries, raw SQL escape hatch |
| Cache/State | Redis 7 | Atomic rotation via Lua scripts, sub-ms latency |
| Serialization | orjson | 3-10x faster JSON than stdlib |
| Logging | structlog | Structured JSON logging |
| Docker | 3-container compose | app + postgres + redis |

### System Architecture

```
  Clients ──────────────> ┌──────────────────────────────────────┐
  (scrapers,              │           Docker Compose              │
   browsers,              │                                       │
   scripts)               │  ┌──────────────────────────────┐    │
        ┌──── :8080 ────> │  │        FastAPI App            │    │
        │  (API + UI)     │  │  REST API + Web Dashboard     │    │
        │                 │  │                                │    │
        ├──── :9000 ────> │  │  Forward Proxy (HTTP/HTTPS)   │    │
        │                 │  │                                │    │
        ├──── :9001 ────> │  │  Forward Proxy (SOCKS5)       │    │
        │                 │  │                                │    │
        │                 │  │  Background: Health Checker    │    │
        │                 │  └──────────┬──────────┬─────────┘    │
        │                 │             │          │               │
        │                 │  ┌──────────▼──┐ ┌────▼───────────┐  │
        │                 │  │ PostgreSQL  │ │     Redis       │  │
        │                 │  │ (entities)  │ │ (rotation state │  │
        │                 │  │             │ │  health cache)  │  │
        │                 │  └─────────────┘ └────────────────┘  │
        │                 └──────────────────────────────────────┘
        │
        └── Upstream proxies (providers) ──> Target sites
```

### Docker Deployment (All Phases)

```yaml
services:
  app:
    image: proxymanager:latest
    build: .
    depends_on:
      db: { condition: service_healthy }
      redis: { condition: service_healthy }
    environment:
      - DATABASE_URL=postgresql+asyncpg://proxymanager:${DB_PASSWORD}@db:5432/proxymanager
      - REDIS_URL=redis://redis:6379/0
      - PM_SECRET_KEY=${SECRET_KEY}
      - PM_ADMIN_PASSWORD=${ADMIN_PASSWORD}
    ports:
      - "8080:8080"
      - "9000:9000"
      - "9001:9001"
    restart: unless-stopped

  db:
    image: postgres:16-alpine
    volumes: [pgdata:/var/lib/postgresql/data]
    environment:
      - POSTGRES_DB=proxymanager
      - POSTGRES_USER=proxymanager
      - POSTGRES_PASSWORD=${DB_PASSWORD}
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U proxymanager"]
      interval: 10s
    restart: unless-stopped

  redis:
    image: redis:7-alpine
    command: redis-server --appendonly yes --maxmemory 256mb --maxmemory-policy allkeys-lru
    volumes: [redisdata:/data]
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 10s
    restart: unless-stopped

volumes:
  pgdata:
  redisdata:
```

---

# PHASE 1: Barely Usable

> **Goal:** Import proxies, organize into pools/projects, get rotating proxies through a forward proxy or API. No analytics, no blacklisting, no charts. Just the core loop working end-to-end.

## P1 -- Database Schema

Only the essential entities. No metrics tables, no blacklist table, no partitioning.

```sql
CREATE TABLE providers (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(255) UNIQUE NOT NULL,
    notes TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE proxies (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    provider_id UUID NOT NULL REFERENCES providers(id) ON DELETE RESTRICT,
    host VARCHAR(255) NOT NULL,
    port INTEGER NOT NULL CHECK (port > 0 AND port < 65536),
    protocol VARCHAR(10) NOT NULL CHECK (protocol IN ('http', 'https', 'socks5')),
    username VARCHAR(255),
    password_encrypted TEXT,
    is_active BOOLEAN DEFAULT true,
    last_health_check TIMESTAMPTZ,
    last_health_status VARCHAR(20) DEFAULT 'unknown'
        CHECK (last_health_status IN ('healthy', 'dead', 'unknown')),
    avg_latency_ms FLOAT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE (host, port, protocol)
);

CREATE INDEX idx_proxies_provider ON proxies(provider_id);
CREATE INDEX idx_proxies_active_health ON proxies(is_active, last_health_status);

CREATE TABLE pools (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(255) UNIQUE NOT NULL,
    rotation_strategy VARCHAR(30) DEFAULT 'round_robin'
        CHECK (rotation_strategy IN ('round_robin', 'random')),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE projects (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(255) UNIQUE NOT NULL,
    slug VARCHAR(255) UNIQUE NOT NULL,
    api_key_hash VARCHAR(128) NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE pool_proxies (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    pool_id UUID NOT NULL REFERENCES pools(id) ON DELETE CASCADE,
    proxy_id UUID NOT NULL REFERENCES proxies(id) ON DELETE CASCADE,
    added_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE (pool_id, proxy_id)
);

CREATE INDEX idx_pool_proxies_proxy ON pool_proxies(proxy_id);

CREATE TABLE project_pools (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    pool_id UUID NOT NULL REFERENCES pools(id) ON DELETE CASCADE,
    priority INTEGER DEFAULT 0,
    assigned_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE (project_id, pool_id)
);
```

## P1 -- API Endpoints

Minimal CRUD + rotation. No stats, no blacklist, no monitoring endpoints.

### Authentication
- **Management API**: Bearer token (`PM_ADMIN_PASSWORD` hashed)
- **Forward proxy + Rotator API**: Project API key via proxy auth or `X-API-Key` header

### Proxies
| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/v1/ips` | List proxies (paginated, filterable by pool, status, protocol) |
| `POST` | `/api/v1/ips` | Add single proxy |
| `POST` | `/api/v1/ips/bulk` | Bulk import (auto-detect format) |
| `GET` | `/api/v1/ips/{id}` | Get proxy detail |
| `PATCH` | `/api/v1/ips/{id}` | Update proxy |
| `DELETE` | `/api/v1/ips/{id}` | Remove proxy |
| `POST` | `/api/v1/ips/{id}/check` | Trigger immediate health check |

### Pools
| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/v1/pools` | List pools |
| `POST` | `/api/v1/pools` | Create pool |
| `GET` | `/api/v1/pools/{id}` | Pool detail with member count |
| `PATCH` | `/api/v1/pools/{id}` | Update pool |
| `DELETE` | `/api/v1/pools/{id}` | Delete pool |
| `POST` | `/api/v1/pools/{id}/ips` | Add proxies to pool |
| `DELETE` | `/api/v1/pools/{id}/ips` | Remove proxies from pool |

### Projects
| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/v1/projects` | List projects |
| `POST` | `/api/v1/projects` | Create project (generates API key) |
| `GET` | `/api/v1/projects/{id}` | Project detail |
| `PATCH` | `/api/v1/projects/{id}` | Update project |
| `DELETE` | `/api/v1/projects/{id}` | Delete project |
| `POST` | `/api/v1/projects/{id}/pools` | Assign pools |
| `DELETE` | `/api/v1/projects/{id}/pools/{poolId}` | Unassign pool |
| `POST` | `/api/v1/projects/{id}/rotate-key` | Regenerate API key |

### Providers
| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/v1/providers` | List providers |
| `POST` | `/api/v1/providers` | Create provider |
| `GET` | `/api/v1/providers/{id}` | Provider detail |
| `PATCH` | `/api/v1/providers/{id}` | Update provider |
| `DELETE` | `/api/v1/providers/{id}` | Delete provider |

### Rotation
| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/v1/rotate/{project_slug}` | Get next healthy proxy (API mode) |
| *(port 9000)* | HTTP/HTTPS forward proxy | Transparent rotation |
| *(port 9001)* | SOCKS5 forward proxy | Transparent rotation |

### System
| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/v1/health` | System health check |

### Import Formats (auto-detected)

| Format | Example |
|--------|---------|
| `ip:port` | `1.2.3.4:8080` |
| `ip:port:user:pass` | `1.2.3.4:8080:admin:secret` |
| `protocol://ip:port` | `socks5://1.2.3.4:1080` |
| `protocol://user:pass@ip:port` | `http://u:p@1.2.3.4:8080` |
| CSV with headers | `ip,port,protocol,username,password` |
| JSON array | `[{"host":"1.2.3.4","port":8080}]` |

## P1 -- Rotation Engine

Minimal: round-robin and random only. Redis-backed for atomic concurrent access.

### Redis Structures (Phase 1)

```
pool:{pool_id}:proxies = LIST [proxy_id_1, proxy_id_2, ...]
proxy:{proxy_id}:health = "healthy" | "dead" | "unknown"  (with TTL)
proxy:{proxy_id}:info = HASH {host, port, protocol, username, password}
```

### Rotation Logic (Lua Script)

```
Input: pool_id, strategy
Output: proxy connection info OR error

1. Get candidate based on strategy:
   - round_robin: LMOVE pool:{pool_id}:proxies RIGHT LEFT
   - random: random index into list
2. For each candidate (up to pool size):
   a. Check proxy:{candidate}:health != "dead"
   b. If healthy/unknown, return proxy:{candidate}:info
   c. If dead, try next
3. If none found, return POOL_EXHAUSTED error
```

No blacklist checks in Phase 1. No weighted selection. Just "give me the next working proxy."

## P1 -- Forward Proxy

### HTTP/HTTPS (port 9000)
- HTTP `CONNECT` for HTTPS tunneling
- Direct proxying for plain HTTP
- Proxy auth maps `user:pass` to project -> project's pools -> rotation
- On each request: authenticate -> select proxy -> forward -> respond

### SOCKS5 (port 9001)
- RFC 1928 SOCKS5 with username/password auth (RFC 1929)
- Auth maps to project, then rotation selects upstream proxy
- Establish SOCKS5 tunnel through selected upstream -> relay bytes

## P1 -- Health Checking

Simple alive/dead model. No degraded state yet.

- Background task via APScheduler, runs every 60 seconds
- `asyncio.Semaphore(200)` limits concurrent checks
- HTTP/HTTPS: `GET` through proxy to a test endpoint (e.g., `httpbin.org/ip`)
- SOCKS5: TCP connection through proxy to test endpoint via `python-socks`
- Result: update `proxy:{id}:health` in Redis + `last_health_check`/`last_health_status` in PostgreSQL
- New proxies get immediate health check on import

```
unknown ──(check succeeds)──> healthy
unknown ──(check fails)─────> dead
healthy ──(3 consecutive failures)──> dead
dead ────(1 success)─────────> healthy
```

## P1 -- Minimal Web UI

Four pages. Functional, not pretty. Server-rendered HTML (Jinja2 templates) or lightweight SPA (your choice).

| Page | What It Shows |
|------|---------------|
| **Proxies** | Table: host, port, protocol, provider, status (healthy/dead/unknown), last checked. Bulk import button (paste or file upload). |
| **Pools** | List of pools with proxy count and health summary (X healthy / Y total). Create pool, add/remove proxies. |
| **Projects** | List of projects with assigned pools. Create project (shows generated API key once). Assign/unassign pools. |
| **Providers** | Simple list of provider names. CRUD. |

No charts. No real-time updates. No overview dashboard. Just CRUD tables that let you manage entities and see proxy health at a glance.

## P1 -- What You Can Do After Phase 1

```bash
# 1. Deploy
docker compose up -d

# 2. Create a provider
curl -X POST localhost:8080/api/v1/providers \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -d '{"name": "my-provider"}'

# 3. Import proxies
curl -X POST localhost:8080/api/v1/ips/bulk \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -d '{"provider_id": "...", "proxies": "1.2.3.4:8080\n5.6.7.8:3128:user:pass"}'

# 4. Create pool + assign proxies
curl -X POST localhost:8080/api/v1/pools -d '{"name": "datacenter-us"}'
curl -X POST localhost:8080/api/v1/pools/{pool_id}/ips -d '{"proxy_ids": [...]}'

# 5. Create project + assign pool
curl -X POST localhost:8080/api/v1/projects -d '{"name": "scraper-v1"}'
# → returns {"api_key": "pm_live_abc123..."}
curl -X POST localhost:8080/api/v1/projects/{id}/pools -d '{"pool_id": "..."}'

# 6. Use it -- forward proxy mode
curl -x http://scraper-v1:pm_live_abc123@localhost:9000 https://httpbin.org/ip

# 7. Or use it -- API rotation mode
curl localhost:8080/api/v1/rotate/scraper-v1 -H "X-API-Key: pm_live_abc123"
# → {"host": "1.2.3.4", "port": 8080, "protocol": "http"}
```

That's it. Import, organize, rotate, proxy. Everything else comes in Phase 2.

---

# PHASE 2: Production-Ready

> **Goal:** Make the tool reliable and observable. Auto-blacklisting prevents bad proxies from being used. Metrics tell you what's happening. Pool exclusivity prevents cross-contamination. The dashboard becomes actually useful.

## P2 -- Schema Additions

New tables added via Alembic migrations. Existing tables get new columns.

### Altered Tables

```sql
-- proxies: add geo + degraded status
ALTER TABLE proxies
    ALTER COLUMN last_health_status SET DATA TYPE VARCHAR(20),
    ADD CHECK (last_health_status IN ('healthy', 'degraded', 'dead', 'unknown')),
    ADD COLUMN country_code CHAR(2),
    ADD COLUMN city VARCHAR(255),
    ADD COLUMN asn VARCHAR(50);

CREATE INDEX idx_proxies_country ON proxies(country_code);

-- pools: add exclusivity + advanced config
ALTER TABLE pools
    ADD COLUMN is_exclusive BOOLEAN DEFAULT false,
    ADD COLUMN sticky_session_ttl INTEGER DEFAULT 0,
    ADD COLUMN health_check_interval INTEGER DEFAULT 60,
    ADD COLUMN blacklist_threshold FLOAT DEFAULT 0.20,
    ADD COLUMN blacklist_window_seconds INTEGER DEFAULT 300,
    ADD COLUMN blacklist_cooldown_seconds INTEGER DEFAULT 1800,
    ADD COLUMN min_healthy_proxies INTEGER DEFAULT 1,
    ALTER COLUMN rotation_strategy SET DATA TYPE VARCHAR(30),
    ADD CHECK (rotation_strategy IN (
        'round_robin', 'random', 'weighted_random', 'least_connections'
    ));

-- pool_proxies: add weight for weighted rotation
ALTER TABLE pool_proxies ADD COLUMN weight INTEGER DEFAULT 1 CHECK (weight > 0);

-- projects: add quotas
ALTER TABLE projects
    ADD COLUMN rate_limit_rpm INTEGER DEFAULT 0,
    ADD COLUMN bandwidth_quota_bytes BIGINT DEFAULT 0;

-- providers: add API integration fields
ALTER TABLE providers
    ADD COLUMN api_endpoint TEXT,
    ADD COLUMN api_key_encrypted TEXT;
```

### New Tables

```sql
-- Per-project proxy blacklist
CREATE TABLE project_proxy_blacklist (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    proxy_id UUID NOT NULL REFERENCES proxies(id) ON DELETE CASCADE,
    target_domain VARCHAR(255),  -- NULL = blacklisted for all targets
    reason TEXT,
    auto_generated BOOLEAN DEFAULT true,
    blacklisted_at TIMESTAMPTZ DEFAULT NOW(),
    expires_at TIMESTAMPTZ,      -- NULL = permanent (until manual removal)
    UNIQUE (project_id, proxy_id, target_domain)
);

CREATE INDEX idx_blacklist_expires ON project_proxy_blacklist(expires_at)
    WHERE expires_at IS NOT NULL;
CREATE INDEX idx_blacklist_project ON project_proxy_blacklist(project_id);

-- Request log (time-partitioned -- CRITICAL)
CREATE TABLE request_log (
    id BIGSERIAL,
    project_id UUID NOT NULL,
    pool_id UUID NOT NULL,
    proxy_id UUID NOT NULL,
    status_code SMALLINT,
    response_time_ms INTEGER,
    bytes_sent INTEGER DEFAULT 0,
    bytes_received INTEGER DEFAULT 0,
    target_domain VARCHAR(255),
    error_type VARCHAR(50),
    created_at TIMESTAMPTZ DEFAULT NOW()
) PARTITION BY RANGE (created_at);

-- Partitions managed by background task (daily)

CREATE INDEX idx_request_log_project ON request_log(project_id, created_at);
CREATE INDEX idx_request_log_proxy ON request_log(proxy_id, created_at);

-- Health check log (time-partitioned)
CREATE TABLE health_check_log (
    id BIGSERIAL,
    proxy_id UUID NOT NULL,
    status VARCHAR(30) NOT NULL,
    latency_ms INTEGER,
    external_ip VARCHAR(45),
    checked_at TIMESTAMPTZ DEFAULT NOW()
) PARTITION BY RANGE (checked_at);

-- Aggregated metrics (rolled up by background task)
CREATE TABLE metrics_rollup (
    id BIGSERIAL PRIMARY KEY,
    entity_type VARCHAR(10) NOT NULL
        CHECK (entity_type IN ('proxy', 'pool', 'project', 'provider')),
    entity_id UUID NOT NULL,
    period_start TIMESTAMPTZ NOT NULL,
    period_granularity VARCHAR(10) NOT NULL
        CHECK (period_granularity IN ('5min', '1hour', '1day')),
    total_requests INTEGER DEFAULT 0,
    successful_requests INTEGER DEFAULT 0,
    failed_requests INTEGER DEFAULT 0,
    bytes_sent BIGINT DEFAULT 0,
    bytes_received BIGINT DEFAULT 0,
    avg_response_time_ms FLOAT,
    p95_response_time_ms FLOAT,
    UNIQUE (entity_type, entity_id, period_start, period_granularity)
);

-- Webhook/alert configuration
CREATE TABLE alert_rules (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(255) NOT NULL,
    condition_type VARCHAR(50) NOT NULL,
    condition_config JSONB NOT NULL,
    action_type VARCHAR(50) NOT NULL,
    action_config JSONB NOT NULL,
    is_enabled BOOLEAN DEFAULT true,
    last_triggered_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW()
);
```

### Metrics Retention Policy

| Granularity | Retention |
|-------------|-----------|
| Raw request_log | 7 days |
| 5-minute rollups | 7 days |
| 1-hour rollups | 90 days |
| 1-day rollups | Forever |

Background task drops old partitions and purges expired rollups daily.

## P2 -- Additional Redis Structures

```
# Weighted set (for weighted rotation)
pool:{pool_id}:weighted = ZSET {proxy_id_1: weight_1, ...}

# Connection counts (for least-connections)
pool:{pool_id}:connections = ZSET {proxy_id_1: count_1, ...}

# Per-project blacklist
blacklist:{project_id} = SET(proxy_id_1, proxy_id_2, ...)

# Sticky sessions
sticky:{pool_id}:{session_key} = proxy_id  (with TTL)

# Rate limiting
ratelimit:{project_id}:{window} = count

# Bandwidth counters (flushed to PG periodically)
bw:{entity_type}:{entity_id}:sent = bytes
bw:{entity_type}:{entity_id}:recv = bytes
```

## P2 -- Enhanced Rotation Lua Script

```
Input: pool_id, project_id, strategy, session_key (optional)
Output: proxy connection info OR error

1. If session_key, check sticky:{pool_id}:{session_key}
   -> If exists, healthy, and not blacklisted, return it
2. Rate limit check: INCR ratelimit:{project_id}:{window}
   -> If exceeds project RPM, return RATE_LIMITED
3. Select candidate per strategy:
   - round_robin: LMOVE RIGHT LEFT
   - random: random index
   - weighted_random: ZRANGEBYSCORE with random offset
   - least_connections: ZRANGEBYSCORE LIMIT 0 1
4. For each candidate (up to pool size):
   a. Check proxy:{candidate}:health != "dead"
   b. Check NOT SISMEMBER blacklist:{project_id} candidate
   c. If passes, return proxy:{candidate}:info
   d. If fails, try next
5. No candidate found -> POOL_EXHAUSTED error
```

## P2 -- Enhanced Health Checking

Three-state model with jittered scheduling:

```
unknown ──(check succeeds)──> healthy
unknown ──(check fails)─────> degraded

healthy ──(2 consecutive failures OR latency > 3x avg)──> degraded
degraded ──(5 consecutive failures)──> dead
dead ────(1 success on periodic recheck)──> degraded
degraded ──(3 consecutive successes)──> healthy
```

- **Jittering**: Random offset per proxy prevents thundering herd
- **Concurrency**: `asyncio.Semaphore(500)`
- **Adaptive intervals**: Healthy=60s, Degraded=15s, Dead=120s (backoff to 10min)
- **Geo-detection**: Health check response reveals external IP -> MaxMind GeoLite2 lookup -> store country/city/ASN

## P2 -- Auto-Blacklisting & Recovery

### Blacklist Evaluator (Background Task)

Runs every 30 seconds:
1. For each project, query recent request_log entries (within `blacklist_window_seconds`)
2. Group by proxy_id, calculate error rate
3. If error_rate > `blacklist_threshold`, insert into `project_proxy_blacklist` with `expires_at = NOW() + blacklist_cooldown_seconds`
4. Push proxy_id into Redis `blacklist:{project_id}` set

### Cooldown Recovery (Background Task)

Runs every 60 seconds:
1. Query blacklist entries where `expires_at <= NOW()`
2. Remove from `project_proxy_blacklist` table
3. Remove from Redis `blacklist:{project_id}` set
4. Proxy re-enters rotation. If it fails again, it gets re-blacklisted.

### Pool Exhaustion

If all proxies are blacklisted for a project, the rotator returns:
```json
{"error": "POOL_EXHAUSTED", "message": "All proxies blacklisted for this project. Earliest recovery: 2026-02-14T17:30:00Z"}
```

## P2 -- Bandwidth Tracking

**Per-request**: Middleware counts `Content-Length` / chunked bytes. Fire-and-forget `INCRBY` to Redis bandwidth counters.

**Periodic flush**: Every 30s, background task reads+resets Redis counters, writes deltas to `metrics_rollup` in PostgreSQL.

**Overhead**: ~0.1ms additional latency per request (pipelined Redis INCRBY).

## P2 -- Additional API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/v1/projects/{id}/blacklist` | Get blacklisted proxies |
| `POST` | `/api/v1/projects/{id}/blacklist` | Manually blacklist proxy |
| `DELETE` | `/api/v1/projects/{id}/blacklist/{proxyId}` | Remove from blacklist |
| `GET` | `/api/v1/ips/{id}/stats` | Proxy performance stats |
| `GET` | `/api/v1/pools/{id}/stats` | Pool performance stats |
| `GET` | `/api/v1/projects/{id}/stats` | Project stats (requests, bandwidth, error rate) |
| `GET` | `/api/v1/providers/{id}/stats` | Provider performance comparison |
| `GET` | `/api/v1/stats/overview` | Global dashboard data |
| `GET` | `/api/v1/stats/timeseries` | Time-series metrics (filterable) |
| `GET` | `/api/v1/alerts` | List alert rules |
| `POST` | `/api/v1/alerts` | Create alert rule |
| `PATCH` | `/api/v1/alerts/{id}` | Update alert rule |
| `DELETE` | `/api/v1/alerts/{id}` | Delete alert rule |
| `WS` | `/ws/events` | Real-time event stream |

## P2 -- Dashboard Upgrade

| Page | What It Shows |
|------|---------------|
| **Overview** | Health ring (healthy/degraded/dead %), request volume sparkline (24h), bandwidth gauge, top 5 failing IPs, pool utilization bars |
| **Proxies** | Enhanced table: + country flag, latency, success rate, last error. Filterable by status, protocol, country, provider |
| **Pools** | + Health score bar, exclusivity badge, rotation strategy display, blacklisted count per project |
| **Projects** | + Error rate indicator, bandwidth used vs quota, blacklist count, request volume chart |
| **Providers** | + Success rate comparison, avg latency, proxy count |
| **Blacklist Manager** (new) | Per-project blacklisted IPs with reason, auto/manual flag, expiry time, bulk un-blacklist |
| **Monitoring** (new) | Live request log (filterable), historical time-series charts, alert rule configuration |
| **Settings** (new) | API key display, webhook URLs, retention policy, global defaults |

Real-time updates via WebSocket for request log and health status changes.

## P2 -- Webhook Alerts

Configurable rules with conditions and actions:

**Conditions**: `error_rate_above`, `pool_below_min_healthy`, `bandwidth_exceeded`, `all_proxies_dead`

**Actions**: Webhook POST (JSON payload), auto-blacklist

```json
{
  "event": "alert.triggered",
  "alert_name": "High error rate on scraper-v2",
  "severity": "critical",
  "condition": {"type": "error_rate_above", "threshold": 0.20, "actual": 0.35},
  "context": {"project": "scraper-v2", "pool": "datacenter-us"},
  "dashboard_url": "http://proxymanager:8080/projects/..."
}
```

---

# PHASE 3: Full-Featured

> **Goal:** Intelligence, automation, and integrations. The tool becomes a competitive proxy management platform.

## P3 -- Features

### IP Reputation Scoring
- Composite 0-100 score per proxy: success rate (40%), latency consistency (20%), uptime (20%), blacklist frequency (10%), age (10%)
- Displayed as colored badge in UI
- Used as weight input for `weighted_random` rotation (high-reputation proxies get more traffic)

### Retry with Automatic Fallback
- Forward proxy retries failed request through next proxy (configurable: 0-3 retries)
- Transparent to client -- they see a successful response or the final error
- Configurable per project: `retry_count`, `retry_on_status_codes` (e.g., [403, 429, 503])

### Proxy Chaining (Multi-Hop)
- Pool config: `chain_through_pool_id` -- requests first go through a proxy from pool A, then through a proxy from pool B
- Use case: residential proxy -> datacenter proxy -> target (for added anonymity)
- Supported via `aiohttp-socks` chaining

### Provider API Auto-Sync
- Configure provider API endpoint + credentials
- Background task periodically polls provider API for current IP list
- Auto-adds new IPs, marks removed IPs as inactive
- Configurable sync interval (e.g., every 6 hours)

### Multi-User RBAC
- Roles: Admin (full), Manager (manage pools/projects, no system config), Viewer (read-only)
- API keys scoped to projects
- User management UI

### Prometheus Metrics Export
- `GET /metrics` endpoint in Prometheus exposition format
- Metrics: active_proxies, request_rate, error_rate, rotation_latency_histogram, health_check_duration, pool_utilization, redis_connection_pool, pg_connection_pool

### Cost Analytics
- Optional cost fields on providers: `cost_per_gb`, `cost_per_ip_per_day`
- Dashboard: cost per project, cost per successful request, cost comparison across providers
- Monthly cost reports

### Python SDK
```python
from proxymanager import ProxyManagerClient

pm = ProxyManagerClient("http://localhost:8080", api_key="...")
pool = pm.pools.create(name="dc-us", strategy="weighted_random")
pm.ips.bulk_import("proxies.txt", pool_id=pool.id)
project = pm.projects.create(name="scraper-v2", pools=[pool.id])
proxy = pm.rotator.next(project="scraper-v2")
```

### Pool Templates / Presets
- "General Scraping": round-robin, 60s health check, 20% blacklist threshold
- "High-Security Target": LRU, 15s health check, 10% threshold, sticky sessions
- "High-Volume API": weighted, 120s health check, 30% threshold

### Request Replay / Debug Mode
- Per-project "debug mode" captures full request/response headers on failures
- UI shows exact error for failed requests
- "Replay" button sends same request through a different proxy

## P3 -- Schema Additions

```sql
-- User accounts for RBAC
CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email VARCHAR(255) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    role VARCHAR(20) NOT NULL CHECK (role IN ('admin', 'manager', 'viewer')),
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Provider cost tracking
ALTER TABLE providers
    ADD COLUMN cost_per_gb NUMERIC(10,4),
    ADD COLUMN cost_per_ip_per_day NUMERIC(10,4),
    ADD COLUMN sync_interval_seconds INTEGER DEFAULT 0,
    ADD COLUMN last_synced_at TIMESTAMPTZ;

-- Pool chaining
ALTER TABLE pools
    ADD COLUMN chain_through_pool_id UUID REFERENCES pools(id);

-- Project retry config
ALTER TABLE projects
    ADD COLUMN retry_count INTEGER DEFAULT 0,
    ADD COLUMN retry_on_status_codes JSONB DEFAULT '[]';

-- Proxy reputation
ALTER TABLE proxies
    ADD COLUMN reputation_score FLOAT DEFAULT 50.0;
```

---

## Risks & Mitigations

| Risk | Mitigation |
|------|------------|
| Rotator used as open proxy | API key auth on every request (Phase 1); bind to localhost by default |
| Metrics storage growth | Time-partitioned tables + retention policy (Phase 2) |
| All proxies blacklisted | Auto-cooldown with TTL + re-test (Phase 2); `POOL_EXHAUSTED` error |
| Health check thundering herd | Jittered scheduling + semaphore (Phase 2) |
| Redis failure | Fallback to in-memory round-robin (degraded mode) |
| PostgreSQL failure | Continue serving from Redis cache; queue writes |
| Proxy credentials exposed | Encrypted at rest; write-only in API; masked in logs |
| Multiple workers sharing state | Redis leader election -- one worker runs background scheduler |
| Exclusive pool IP conflict | Application-level validation on pool assignment (Phase 2) |

---

## Explicitly Out of Scope (All Phases)

- Multi-tenant SaaS mode
- Built-in web scraping capabilities
- Proxy purchasing/provisioning
- Captcha solving integration
- Header/fingerprint rotation (separate concern)
- Plugin/extension system

---

## Success Metrics

| KPI | Target | Phase |
|-----|--------|-------|
| Time to first proxied request | < 3 minutes | P1 |
| Rotator p99 latency | < 5ms | P1 |
| Health check coverage | 100% within interval | P1 |
| Proxy selection accuracy | > 99% healthy + not blacklisted | P2 |
| Dashboard load time | < 1s | P2 |
| System uptime | > 99.9% | P2 |
