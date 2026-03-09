# Proxysm

**Proxy + Prism** — one request in, multiple providers out.

Self-hosted proxy management platform with intelligent rotation, health monitoring, and real-time analytics. Proxysm sits between your applications and upstream proxy providers, splitting traffic across them like a prism splits light — giving you a single endpoint that handles rotation, failover, and observability across all your proxies.

## Features

- **Proxy Rotation** — Round-robin, random, weighted random, and least-connections strategies
- **Health Monitoring** — Adaptive 3-state health model (healthy / degraded / dead) with automatic failover
- **HTTP & SOCKS5** — Dual-protocol proxy servers with transparent upstream forwarding
- **Project Isolation** — Separate API keys, rate limits, and bandwidth quotas per project
- **Pool Management** — Group proxies into pools with per-pool rotation strategies
- **Real-time Dashboard** — Built-in web UI with live stats, charts, and proxy management
- **Prometheus Metrics** — Optional `/metrics` endpoint with 28 metric families
- **Grafana Dashboard** — Pre-built 35-panel dashboard, auto-provisioned via Docker
- **Alerting** — Configurable webhook alerts for error rates, pool health, and bandwidth
- **Bulk Import** — Import proxy lists from URLs or raw text in any common format

## Quick Start

```bash
git clone https://github.com/pcko1/proxysm.git
cd proxysm
cp .env.example .env
docker compose up -d
```

Open `http://localhost:8080` to access the dashboard.

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
| Prometheus | `http://localhost:9090` | — |
| Grafana | `http://localhost:3000` | `admin` / value of `GRAFANA_PASSWORD` |

The Grafana dashboard is auto-provisioned with 35 panels across 6 sections:

- **Overview** — Request rate, active connections, error rate, latency, bandwidth, proxy health
- **Proxy Traffic** — Requests by project/protocol, status codes, error types, latency percentiles, top domains
- **Bandwidth** — Sent/received over time, bandwidth by project
- **Health Checks** — Success/failure rate, check latency, status transitions
- **Pools & Rotation** — Pool sizes, healthy proxies, rotations by strategy, pool exhaustions
- **Management API** — API request rate by endpoint, API latency, in-flight requests

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

- **Runtime** — Python 3.12, FastAPI, uvicorn, uvloop
- **Database** — PostgreSQL 16 with time-partitioned tables
- **Cache** — Redis 7 for rotation state, health cache, and bandwidth counters
- **Proxy** — asyncio TCP servers for HTTP and SOCKS5 protocols
- **Monitoring** — prometheus-client, Grafana with auto-provisioned dashboards
- **Scheduling** — APScheduler for health checks, metrics rollup, and partition management

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

All rights reserved.
