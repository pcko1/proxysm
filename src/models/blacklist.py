import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.models.base import Base, UUIDMixin

if TYPE_CHECKING:
    from src.models.project import Project
    from src.models.proxy import Proxy


class ProjectProxyBlacklist(Base, UUIDMixin):
    __tablename__ = "project_proxy_blacklist"
    __table_args__ = (
        UniqueConstraint(
            "project_id", "proxy_id", "target_domain",
            name="uq_blacklist_project_proxy_domain",
        ),
    )

    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    proxy_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("proxies.id", ondelete="CASCADE"), nullable=False
    )
    target_domain: Mapped[str | None] = mapped_column(String(255), nullable=True)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    auto_generated: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
    blacklisted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Relationships
    project: Mapped["Project"] = relationship("Project")
    proxy: Mapped["Proxy"] = relationship("Proxy")

    def __repr__(self) -> str:
        return f"<Blacklist project={self.project_id} proxy={self.proxy_id}>"
