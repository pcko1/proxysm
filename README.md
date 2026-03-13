<div align="center">

<img src="assets/proxysm-logo-small.png" alt="Proxysm Logo" width="200"/>

<h1>Proxysm: your proxy prism</h1>

<a href="https://www.python.org"><img src="https://img.shields.io/badge/python-3.11%2B-3776AB?logo=python&logoColor=white" alt="Python 3.11+"/></a>
<a href="https://www.docker.com"><img src="https://img.shields.io/badge/Docker-2496ED?logo=docker&logoColor=white" alt="Docker"/></a>
<a href="https://github.com/pcko1/proxysm/actions/workflows/tests.yml"><img src="https://github.com/pcko1/proxysm/actions/workflows/tests.yml/badge.svg" alt="Tests"/></a>
<a href="#license"><img src="https://img.shields.io/badge/license-MIT-green" alt="License"/></a>
<br>
<a href="https://fastapi.tiangolo.com"><img src="https://img.shields.io/badge/FastAPI-009688?logo=fastapi&logoColor=white" alt="FastAPI"/></a>
<a href="https://www.postgresql.org"><img src="https://img.shields.io/badge/PostgreSQL-4169E1?logo=postgresql&logoColor=white" alt="PostgreSQL"/></a>
<a href="https://redis.io"><img src="https://img.shields.io/badge/Redis-DC382D?logo=redis&logoColor=white" alt="Redis"/></a>
<a href="https://grafana.com"><img src="https://img.shields.io/badge/Grafana-F46800?logo=grafana&logoColor=white" alt="Grafana"/></a>

<br>

<i>Proxy + Prism: one request in, multiple providers out.<br>
Like a prism splits light, Proxysm splits your traffic across upstream proxy providers.</i>

<br>

Self-hosted proxy management platform with intelligent rotation, health monitoring, and real-time analytics.<br>
A single endpoint that handles rotation, failover, and observability across all your proxies.

<br>

<img src="assets/proxysm-showcase.gif" alt="Proxysm UI Showcase" width="100%"/>

</div>

## Agentic Setup (🌟 Recommended)

> [!TIP]
> Copy the prompt below into any AI coding agent (Claude Code, Cursor, Copilot, etc.) and it will clone, configure, and walk you through the entire project step by step.

```
You are setting up Proxysm, a self-hosted proxy management platform built with Python 3.12, FastAPI, PostgreSQL 16, Redis 7, and Docker. Repository: https://github.com/pcko1/proxysm.git. Ports: 8080 (Web UI + REST API + Prometheus metrics), 9080 (HTTP/HTTPS proxy), 9081 (SOCKS5 proxy). Follow these steps in order. Step 1 - Clone and Configure: Run "git clone https://github.com/pcko1/proxysm.git && cd proxysm". Copy .env.example to .env. Open .env and show me the key variables that need customizing: PM_ADMIN_PASSWORD (admin dashboard and API password, default: changeme), PM_SECRET_KEY (secret key for token signing, default: change-me), DB_PASSWORD (PostgreSQL password, default: changeme). Set temporary values so we can get the stack running. Do NOT start containers yet — ask me to confirm the .env values first. Step 2 - Start the Stack: Verify Docker and Docker Compose are installed (docker --version, docker compose version). Run "docker compose up -d" to start the core services (app, PostgreSQL, Redis). Wait for all 3 containers to be healthy using "docker compose ps". Run database migrations: "docker compose exec app alembic upgrade head". If any container is unhealthy, run "docker compose logs <service>" to diagnose. Common issues: port 8080/9080/9081 already in use (stop conflicting services), database not ready (wait and retry — the app container depends on db health). Confirm the dashboard loads at http://localhost:8080. Step 3 - Guided Tour: Walk me through each UI page one by one. Dashboard (http://localhost:8080/dashboard) — explain what each stat card means: total proxies, healthy/degraded/dead counts, request throughput, error rates, bandwidth usage, latency percentiles, and the interactive charts. Proxies (http://localhost:8080/proxies) — how to add proxies individually (IP:port with optional auth) and how to bulk import from a URL or pasted text, supporting HTTP, HTTPS, and SOCKS5 protocols. Pools (http://localhost:8080/pools) — explain what pools are, when to use them, and the available rotation strategies (round_robin, random, weighted_random, least_connections). Pools group proxies together and are assigned to projects. Projects (http://localhost:8080/projects) — explain how each project gets a unique slug + API key, has isolated rate limits, bandwidth quotas, and assigned pools, and that the slug:key pair is used as proxy authentication. API Docs (http://localhost:8080/api-docs) — the full interactive REST API reference powered by ReDoc, covering all endpoints: /api/v1/ips (list/create proxies), /api/v1/ips/bulk (bulk import), /api/v1/pools (list/create pools), /api/v1/pools/{id}/ips (add/remove proxies in pool), /api/v1/projects (list/create projects), /api/v1/projects/{id}/pools (assign/unassign pools), /api/v1/projects/{id}/rotate-key (rotate API key), /api/v1/stats/overview (dashboard statistics), /api/v1/alerts (alert rules), /api/v1/health (health check, no auth). All management endpoints require admin auth via "Authorization: Bearer <admin_password_sha256>". Settings (http://localhost:8080/settings) — configure webhook alerts (error_rate_above, pool_below_min_healthy, bandwidth_exceeded, all_proxies_dead), view system info, check Prometheus toggle status. Step 4 - End-to-End Test: Perform a complete test flow. (a) Add at least one proxy — go to Proxies page, click Add Proxy, enter a proxy address (e.g. http://user:pass@1.2.3.4:8080). If I don't have a proxy to test with, explain that I need at least one upstream proxy and help me find options or set up a local test proxy. (b) Create a pool — go to Pools page, click Create Pool, name it (e.g. "default"), pick round_robin strategy, assign the proxy to this pool. (c) Create a project — go to Projects page, click Create Project, name it (e.g. "test"), assign the pool, note the generated project slug and API key. (d) Test HTTP proxy on port 9080: curl -x http://PROJECT_SLUG:API_KEY@localhost:9080 https://httpbin.org/ip (replace PROJECT_SLUG and API_KEY with actual values). (e) Test SOCKS5 proxy on port 9081: curl --proxy socks5://PROJECT_SLUG:API_KEY@localhost:9081 https://httpbin.org/ip. (f) Go back to the Dashboard and verify the requests appear in the stats. Step 5 - Enable Monitoring (Optional): If I want Prometheus + Grafana, set PROMETHEUS_ENABLED=true and GRAFANA_PASSWORD=<a password> in .env. Run "docker compose --profile monitoring up -d". This adds Prometheus at http://localhost:9090 and Grafana at http://localhost:3000 (login: admin / GRAFANA_PASSWORD value). Grafana has a pre-built dashboard with 35 panels auto-provisioned across 6 sections: Overview (request rate, active connections, error rate, latency, bandwidth, proxy health), Proxy Traffic (requests by project/protocol, status codes, error types, latency percentiles, top domains), Bandwidth (sent/received over time, bandwidth by project), Health Checks (success/failure rate, check latency, status transitions), Pools & Rotation (pool sizes, healthy proxies, rotations by strategy, pool exhaustions), Management API (API request rate by endpoint, API latency, in-flight requests). Confirm the dashboard loads with panels. For external Prometheus setups, scrape proxysm-host:8080 and import grafana/dashboards/proxysm-overview.json. Step 6 - Architecture Briefing: After everything is running, summarize: Rotation strategies — round_robin (sequential through healthy proxies), random (random selection from healthy), weighted_random (random with configurable weights per proxy), least_connections (routes to proxy with fewest active connections). Health model — adaptive 3-state model: unknown->healthy (1 success), unknown->degraded (1 failure), healthy->degraded (2 failures or latency spike), degraded->healthy (3 successes), degraded->dead (5 failures), dead->degraded (1 success on recheck). Check intervals adapt per status: healthy at base interval, degraded every 15s, dead with exponential backoff up to 10 minutes. Project isolation — each project has its own API key, rate limits, bandwidth quotas, and pool assignments, authenticated via standard proxy auth (slug:key). Key source files in src/: main.py (FastAPI app setup and startup), proxy/http_proxy.py (HTTP/HTTPS proxy server), proxy/socks5_proxy.py (SOCKS5 proxy server), health/checker.py (adaptive health monitoring), web/routes.py (dashboard page routes), api/ directory (REST API endpoints), prometheus.py (metrics instrumentation). CRITICAL FINAL STEP - Password Security and Completion: After setup is complete, you MUST make it absolutely clear that I need to change ALL passwords and secrets in .env to my own secure values. Do NOT let me keep the defaults or any values you generated during setup. This is a hard blocker before the setup is considered done. Then show a ready-to-use curl example for the proxy rotation endpoint using the actual PROJECT_SLUG and API_KEY from the project created in Step 4, like: curl -x http://PROJECT_SLUG:API_KEY@localhost:9080 https://httpbin.org/ip. End with the message: "Change your passwords in .env now. Do not use defaults or AI-generated values in production. This includes PM_ADMIN_PASSWORD, PM_SECRET_KEY, DB_PASSWORD, and GRAFANA_PASSWORD." followed by "✅ Setup complete!" Rules: Ask me before running any destructive commands. If something fails, show me the logs and explain what went wrong before retrying. Keep explanations concise — I want to understand the system, not read a textbook. Replace PROJECT_SLUG and API_KEY with actual values from the project I create. If I have questions about any feature, read the relevant source file before answering.
```

> [!CAUTION]
> Never use default or AI-generated passwords in production. After setup, change all secrets in `.env` (`PM_ADMIN_PASSWORD`, `PM_SECRET_KEY`, `DB_PASSWORD`, `GRAFANA_PASSWORD`) to your own secure values.

## Quick Start (Manual)

If you prefer to set things up yourself instead of using the agentic setup above:

```bash
git clone https://github.com/pcko1/proxysm.git
cd proxysm
cp .env.example .env
docker compose up -d
docker compose exec app alembic upgrade head
```

Open `http://localhost:8080` to access the dashboard.

| Port | Purpose |
|------|---------|
| `8080` | Web UI, REST API, Prometheus metrics |
| `9080` | HTTP/HTTPS proxy |
| `9081` | SOCKS5 proxy |

## Usage

```bash
# HTTP/HTTPS
curl -x http://PROJECT_SLUG:API_KEY@localhost:9080 https://httpbin.org/ip

# SOCKS5
curl --proxy socks5://PROJECT_SLUG:API_KEY@localhost:9081 https://httpbin.org/ip
```

## Features

- **Proxy Rotation** - Round-robin, random, weighted random, and least-connections strategies
- **Health Monitoring** - Adaptive 3-state health model (healthy / degraded / dead) with automatic failover
- **HTTP & SOCKS5** - Dual-protocol proxy servers with transparent upstream forwarding
- **Project Isolation** - Separate API keys, rate limits, and bandwidth quotas per project
- **Pool Management** - Group proxies into pools with per-pool rotation strategies
- **Real-time Dashboard** - Built-in web UI with live stats, charts, and proxy management
- **Observability** - Prometheus metrics, pre-built Grafana dashboard, configurable webhook alerts

## License

This project is licensed under the [MIT License](LICENSE).
