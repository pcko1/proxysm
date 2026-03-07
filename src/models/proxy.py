from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    Float,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.models.base import Base, TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from src.models.associations import PoolProxy


class Proxy(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "proxies"
    __table_args__ = (
        UniqueConstraint("host", "port", "protocol", name="uq_proxy_host_port_protocol"),
        CheckConstraint("port >= 0 AND port <= 65535", name="ck_proxy_port_range"),
        CheckConstraint(
            "protocol IN ('http', 'https', 'socks5')", name="ck_proxy_protocol"
        ),
        CheckConstraint(
            "last_health_status IN ('healthy', 'degraded', 'dead', 'unknown')",
            name="ck_proxy_health_status",
        ),
    )

    provider: Mapped[str | None] = mapped_column(String(255), nullable=True)
    host: Mapped[str] = mapped_column(String(255), nullable=False)
    port: Mapped[int] = mapped_column(Integer, nullable=False)
    protocol: Mapped[str] = mapped_column(String(10), nullable=False)
    username: Mapped[str | None] = mapped_column(String(255), nullable=True)
    password_encrypted: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
    last_health_check: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    last_health_status: Mapped[str] = mapped_column(
        String(20), default="unknown", server_default="unknown"
    )
    avg_latency_ms: Mapped[float | None] = mapped_column(Float, nullable=True)

    country_code: Mapped[str | None] = mapped_column(String(2), nullable=True)
    city: Mapped[str | None] = mapped_column(String(255), nullable=True)
    asn: Mapped[str | None] = mapped_column(String(50), nullable=True)

    pool_proxies: Mapped[list["PoolProxy"]] = relationship(
        "PoolProxy", back_populates="proxy", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Proxy {self.protocol}://{self.host}:{self.port}>"
