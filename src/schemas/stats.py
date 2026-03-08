from datetime import datetime

from pydantic import BaseModel, ConfigDict


class OverviewStats(BaseModel):
    total_proxies: int = 0
    healthy_proxies: int = 0
    degraded_proxies: int = 0
    dead_proxies: int = 0
    unknown_proxies: int = 0
    total_pools: int = 0
    total_projects: int = 0
    total_requests_24h: int = 0
    successful_requests_24h: int = 0
    failed_requests_24h: int = 0
    bytes_sent_24h: int = 0
    bytes_received_24h: int = 0
    avg_response_time_ms: float | None = None

    model_config = ConfigDict(from_attributes=True)


class EntityStats(BaseModel):
    total_requests: int = 0
    successful_requests: int = 0
    failed_requests: int = 0
    error_rate: float = 0.0
    avg_response_time_ms: float | None = None
    p95_response_time_ms: float | None = None
    bytes_sent: int = 0
    bytes_received: int = 0

    model_config = ConfigDict(from_attributes=True)


class TimeseriesPoint(BaseModel):
    period_start: datetime
    total_requests: int = 0
    successful_requests: int = 0
    failed_requests: int = 0
    avg_response_time_ms: float | None = None

    model_config = ConfigDict(from_attributes=True)


class TimeseriesResponse(BaseModel):
    granularity: str
    data: list[TimeseriesPoint]


class StatusCodeBreakdown(BaseModel):
    project_id: str
    project_name: str
    status_2xx: int = 0
    status_3xx: int = 0
    status_4xx: int = 0
    status_5xx: int = 0
    total: int = 0

    model_config = ConfigDict(from_attributes=True)
