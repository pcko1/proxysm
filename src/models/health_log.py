import uuid
from datetime import datetime

from sqlalchemy import DateTime, Integer, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from src.models.base import Base


class HealthCheckLog(Base):
    """Time-partitioned health check log."""
    __tablename__ = "health_check_log"
    __table_args__ = {"postgresql_partition_by": "RANGE (checked_at)"}

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    proxy_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False)
    latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    external_ip: Mapped[str | None] = mapped_column(String(45), nullable=True)
    checked_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, primary_key=True
    )

    def __repr__(self) -> str:
        return f"<HealthCheckLog proxy={self.proxy_id} status={self.status}>"
