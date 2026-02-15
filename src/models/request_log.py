import uuid
from datetime import datetime

from sqlalchemy import DateTime, Integer, SmallInteger, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from src.models.base import Base


class RequestLog(Base):
    """Time-partitioned request log. Partitions managed by background task."""
    __tablename__ = "request_log"
    __table_args__ = {"postgresql_partition_by": "RANGE (created_at)"}

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    project_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    pool_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    proxy_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    status_code: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    response_time_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    bytes_sent: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    bytes_received: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    target_domain: Mapped[str | None] = mapped_column(String(255), nullable=True)
    error_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, primary_key=True
    )

    def __repr__(self) -> str:
        return f"<RequestLog project={self.project_id} status={self.status_code}>"
