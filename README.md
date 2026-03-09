<div align="center">

<img src="assets/proxysm-logo-small.png" alt="Proxysm Logo" width="200"/>

<h1>Proxysm: your proxy prism</h1>

<a href="https://www.python.org"><img src="https://img.shields.io/badge/python-3.11%2B-3776AB?logo=python&logoColor=white" alt="Python 3.11+"/></a>
<a href="https://fastapi.tiangolo.com"><img src="https://img.shields.io/badge/FastAPI-009688?logo=fastapi&logoColor=white" alt="FastAPI"/></a>
<a href="https://www.postgresql.org"><img src="https://img.shields.io/badge/PostgreSQL-4169E1?logo=postgresql&logoColor=white" alt="PostgreSQL"/></a>
<a href="https://redis.io"><img src="https://img.shields.io/badge/Redis-DC382D?logo=redis&logoColor=white" alt="Redis"/></a>
<a href="https://www.docker.com"><img src="https://img.shields.io/badge/Docker-2496ED?logo=docker&logoColor=white" alt="Docker"/></a>
<a href="https://grafana.com"><img src="https://img.shields.io/badge/Grafana-F46800?logo=grafana&logoColor=white" alt="Grafana"/></a>
<a href="#license"><img src="https://img.shields.io/badge/license-MIT-green" alt="License"/></a>

<br>

<i>Proxy + Prism: one request in, multiple providers out.<br>
Like a prism splits light, Proxysm splits your traffic across upstream proxy providers.</i>

<br>

Self-hosted proxy management platform with intelligent rotation, health monitoring, and real-time analytics.<br>
A single endpoint that handles rotation, failover, and observability across all your proxies.

</div>

## Features

- **Proxy Rotation** - Round-robin, random, weighted random, and least-connections strategies
- **Health Monitoring** - Adaptive 3-state health model (healthy / degraded / dead) with automatic failover
- **HTTP & SOCKS5** - Dual-protocol proxy servers with transparent upstream forwarding
- **Project Isolation** - Separate API keys, rate limits, and bandwidth quotas per project
- **Pool Management** - Group proxies into pools with per-pool rotation strategies
- **Real-time Dashboard** - Built-in web UI with live stats, charts, and proxy management
- **Prometheus Metrics** - Optional `/metrics` endpoint with 28 metric families
- **Grafana Dashboard** - Pre-built 35-panel dashboard, auto-provisioned via Docker
- **Alerting** - Configurable webhook alerts for error rates, pool health, and bandwidth
- **Bulk Import** - Import proxy lists from URLs or raw text in any common format

## Quick Start

```bash
git clone https://github.com/pcko1/proxysm.git
cd proxysm
cp .env.example .env
docker compose up -d
```

Open `http://localhost:8080` to access the dashboard.

## AI-Assisted Setup

Have an AI agent set up and walk you through the entire project. Copy and paste this into [Claude Code](https://claude.ai/claude-code) or any AI coding assistant:

```
git clone https://github.com/pcko1/proxysm.git && cd proxysm && claude -p "You are setting up Proxysm, a self-hosted proxy management platform (Python/FastAPI, PostgreSQL 16, Redis 7, Docker). Repo: https://github.com/pcko1/proxysm.git — Ports: 8080 (Web UI + API), 9080 (HTTP proxy), 9081 (SOCKS5 proxy). Step 1: Copy .env.example to .env, then show me the key variables (PM_ADMIN_PASSWORD, PM_SECRET_KEY, DB_PASSWORD) and ask me to confirm before continuing. For now set temporary values to get running. Step 2: Ensure Docker and Docker Compose are installed, run docker compose up -d, wait for all 3 containers (app, db, redis) to be healthy via docker compose ps. If any fail, check logs and fix. Confirm http://localhost:8080 loads. Step 3: Walk me through each UI page — Dashboard (stats overview), Proxies (add single or bulk import), Pools (group proxies with rotation strategies), Projects (isolated endpoints with slug+key auth), API Docs (interactive REST reference), Settings (alerts, Prometheus, system info). Step 4: End-to-end test — help me add a proxy, create a pool with round_robin strategy, create a project, assign the pool, then test with: curl -x http://SLUG:KEY@localhost:9080 https://httpbin.org/ip and curl --proxy socks5://SLUG:KEY@localhost:9081 https://httpbin.org/ip — verify stats appear on the dashboard. Step 5 (optional): If I want monitoring, set PROMETHEUS_ENABLED=true in .env, run docker compose --profile monitoring up -d, confirm Grafana at http://localhost:3000 (admin/GRAFANA_PASSWORD) loads the auto-provisioned 35-panel dashboard. Step 6: Give me a brief architecture summary — rotation strategies (round_robin, random, weighted_random, least_connections), health model (3-state: healthy/degraded/dead with adaptive check intervals), project isolation (separate keys, rate limits, bandwidth quotas), and key source files in src/. IMPORTANT: After setup is complete, make it absolutely clear that I MUST change all passwords and secrets in .env to my own secure values. Do NOT let me keep the defaults or any values you generated. This is a hard blocker — the final step is always: Change your passwords in .env now, do not use defaults or AI-generated values in production. Rules: ask before destructive commands, show logs on failure, keep explanations concise."
```

## Architecture

```
┌─────────────┐     ┌──────────────────────────────────────────┐
│  Your App   │────>│  Proxysm                                 │
│             │     │  ┌──────────┐  ┌────────┐  ┌──────────┐  │
│  HTTP/S     │────>│  │ HTTP     │  │Rotation│  │ Upstream │  │───> Target
│  SOCKS5     │────>│  │ SOCKS5   │─>│ Engine │─>│ Proxies  │  │
│             │     │  └──────────┘  └────────┘  └──────────┘  │
└─────────────┘     │  ┌──────────┐  ┌────────┐  ┌──────────┐  │
                    │  │ Web UI   │  │  Stats │  │  Health  │  │
                    │  │ REST API │  │ Engine │  │ Checker  │  │
                    │  └──────────┘  └────────┘  └──────────┘  │
                    └──────────────────────────────────────────┘
                          │                │                │
                    ┌─────┴──────┐   ┌─────┴──────┐   ┌─────┴──────┐
                    │ PostgreSQL │   │   Redis    │   │ Prometheus │
                    └────────────┘   └────────────┘   └────────────┘
```

| Component | Port | Purpose |
|-----------|------|---------|
| Web UI / API | `8080` | Dashboard, REST API, Prometheus metrics |
| HTTP Proxy | `9080` | Forward HTTP/HTTPS requests through upstream proxies |
| SOCKS5 Proxy | `9081` | Forward SOCKS5 connections through upstream proxies |

## Configuration

All configuration is via environment variables. Copy `.env.example` and edit as needed:

```bash
cp .env.example .env
```

| Variable | Default | Description |
|----------|---------|-------------|
| `DATABASE_URL` | `postgresql+asyncpg://...` | PostgreSQL connection string |
| `REDIS_URL` | `redis://redis:6379/0` | Redis connection string |
| `PM_SECRET_KEY` | `change-me` | Secret key for token signing |
| `PM_ADMIN_PASSWORD` | `changeme` | Admin password for API and dashboard |
| `PM_LOG_LEVEL` | `info` | Log level (debug, info, warning, error) |
| `PROMETHEUS_ENABLED` | `false` | Enable `/metrics` endpoint |
| `GRAFANA_PASSWORD` | `proxysm` | Grafana admin password (monitoring profile) |

## Usage

### Connecting Through the Proxy

Proxysm authenticates requests using your project slug and API key via standard proxy authentication.

**HTTP/HTTPS (port 9080):**

```bash
curl -x http://PROJECT_SLUG:API_KEY@localhost:9080 https://httpbin.org/ip
```

**SOCKS5 (port 9081):**

```bash
curl --proxy socks5://PROJECT_SLUG:API_KEY@localhost:9081 https://httpbin.org/ip
```

### REST API

All management endpoints require admin authentication via `Authorization: Bearer <admin_password_sha256>`.

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/v1/ips` | `GET` `POST` | List or create proxies |
| `/api/v1/ips/bulk` | `POST` | Bulk import from URL or text |
| `/api/v1/pools` | `GET` `POST` | List or create pools |
| `/api/v1/pools/{id}/ips` | `POST` `DELETE` | Add/remove proxies in pool |
| `/api/v1/projects` | `GET` `POST` | List or create projects |
| `/api/v1/projects/{id}/pools` | `POST` `DELETE` | Assign/unassign pools |
| `/api/v1/projects/{id}/rotate-key` | `POST` | Rotate API key |
| `/api/v1/stats/overview` | `GET` | Global dashboard statistics |
| `/api/v1/alerts` | `GET` `POST` | List or create alert rules |
| `/api/v1/health` | `GET` | Health check (no auth) |

Full API docs available at `http://localhost:8080/docs` (Swagger UI).

### Rotation Strategies

| Strategy | Description |
|----------|-------------|
| `round_robin` | Sequential rotation through all healthy proxies |
| `random` | Random selection from healthy proxies |
| `weighted_random` | Random selection with configurable weights per proxy |
| `least_connections` | Routes to the proxy with fewest active connections |

### Health Model

Proxysm uses an adaptive 3-state health model with automatic failover:

```
unknown ──success──> healthy
unknown ──failure──> degraded
healthy ──2 failures or latency spike──> degraded
degraded ──3 successes──> healthy
degraded ──5 failures──> dead
dead ──1 success on recheck──> degraded
```

Check intervals adapt per status: healthy proxies check at the base interval, degraded every 15s, and dead proxies use exponential backoff up to 10 minutes.

## Monitoring

### Built-in Dashboard

The web UI at `http://localhost:8080/dashboard` provides real-time stats including request throughput, error rates, latency percentiles, bandwidth, proxy health distribution, and top domains.

### Prometheus + Grafana

Enable the full monitoring stack with a single flag:

```bash
# Set in .env
PROMETHEUS_ENABLED=true

# Start with monitoring profile
docker compose --profile monitoring up -d
```

This adds:

| Service | URL | Credentials |
|---------|-----|-------------|
| Prometheus | `http://localhost:9090` | - |
| Grafana | `http://localhost:3000` | `admin` / value of `GRAFANA_PASSWORD` |

The Grafana dashboard is auto-provisioned with 35 panels across 6 sections:

- **Overview** - Request rate, active connections, error rate, latency, bandwidth, proxy health
- **Proxy Traffic** - Requests by project/protocol, status codes, error types, latency percentiles, top domains
- **Bandwidth** - Sent/received over time, bandwidth by project
- **Health Checks** - Success/failure rate, check latency, status transitions
- **Pools & Rotation** - Pool sizes, healthy proxies, rotations by strategy, pool exhaustions
- **Management API** - API request rate by endpoint, API latency, in-flight requests

### External Prometheus

If you already run Prometheus, point it at Proxysm directly:

```yaml
scrape_configs:
  - job_name: proxysm
    scrape_interval: 15s
    static_configs:
      - targets: ['your-proxysm-host:8080']
```

Import `grafana/dashboards/proxysm-overview.json` into your Grafana instance.

## Alerting

Configure webhook alerts for critical conditions:

| Condition | Description |
|-----------|-------------|
| `error_rate_above` | Error rate exceeds threshold within time window |
| `pool_below_min_healthy` | Pool drops below minimum healthy proxy count |
| `bandwidth_exceeded` | Bandwidth usage exceeds configured limit |
| `all_proxies_dead` | Every proxy in a pool becomes unreachable |

Manage alerts via the Settings page or the `/api/v1/alerts` endpoint.

## Tech Stack

- **Runtime** - Python 3.12, FastAPI, uvicorn, uvloop
- **Database** - PostgreSQL 16 with time-partitioned tables
- **Cache** - Redis 7 for rotation state, health cache, and bandwidth counters
- **Proxy** - asyncio TCP servers for HTTP and SOCKS5 protocols
- **Monitoring** - prometheus-client, Grafana with auto-provisioned dashboards
- **Scheduling** - APScheduler for health checks, metrics rollup, and partition management

## Development

```bash
# Install dependencies
pip install -e ".[dev]"

# Run linter
ruff check src/

# Run type checker
mypy src/

# Run tests
pytest
```

## License

This project is licensed under the [MIT License](LICENSE).
