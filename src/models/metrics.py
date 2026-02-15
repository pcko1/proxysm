import uuid
from datetime import datetime

from sqlalchemy import BigInteger, CheckConstraint, DateTime, Float, Integer, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from src.models.base import Base


class MetricsRollup(Base):
    __tablename__ = "metrics_rollup"
    __table_args__ = (
        UniqueConstraint(
            "entity_type", "entity_id", "period_start", "period_granularity",
            name="uq_metrics_rollup_entity_period",
        ),
        CheckConstraint(
            "entity_type IN ('proxy', 'pool', 'project', 'provider')",
            name="ck_metrics_entity_type",
        ),
        CheckConstraint(
            "period_granularity IN ('5min', '1hour', '1day')",
            name="ck_metrics_granularity",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    entity_type: Mapped[str] = mapped_column(String(10), nullable=False)
    entity_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    period_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    period_granularity: Mapped[str] = mapped_column(String(10), nullable=False)
    total_requests: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    successful_requests: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    failed_requests: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    bytes_sent: Mapped[int] = mapped_column(BigInteger, default=0, server_default="0")
    bytes_received: Mapped[int] = mapped_column(BigInteger, default=0, server_default="0")
    avg_response_time_ms: Mapped[float | None] = mapped_column(Float, nullable=True)
    p95_response_time_ms: Mapped[float | None] = mapped_column(Float, nullable=True)

    def __repr__(self) -> str:
        return f"<MetricsRollup {self.entity_type}:{self.entity_id} {self.period_granularity}>"
