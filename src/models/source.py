from typing import TYPE_CHECKING

from sqlalchemy import Boolean, CheckConstraint, Integer, String, Text, DateTime
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.models.base import Base, TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from src.models.proxy import Proxy


class ProxySource(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "proxy_sources"
    __table_args__ = (
        CheckConstraint(
            "type IN ('url', 'file', 'manual')",
            name="ck_proxy_source_type",
        ),
    )

    name: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    type: Mapped[str] = mapped_column(String(10), nullable=False)
    url: Mapped[str | None] = mapped_column(Text, nullable=True)
    provider: Mapped[str | None] = mapped_column(String(255), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
    last_polled_at: Mapped[None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_status_code: Mapped[int | None] = mapped_column(Integer, nullable=True)
    consecutive_failures: Mapped[int] = mapped_column(Integer, default=0, server_default="0")

    proxies: Mapped[list["Proxy"]] = relationship(
        "Proxy", back_populates="source", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<ProxySource {self.type}:{self.name}>"
