import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Integer, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.models.base import Base, UUIDMixin

if TYPE_CHECKING:
    from src.models.pool import Pool
    from src.models.project import Project
    from src.models.proxy import Proxy


class PoolProxy(Base, UUIDMixin):
    __tablename__ = "pool_proxies"
    __table_args__ = (
        UniqueConstraint("pool_id", "proxy_id", name="uq_pool_proxy"),
        CheckConstraint("weight > 0", name="ck_pool_proxy_weight"),
    )

    pool_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("pools.id", ondelete="CASCADE"), nullable=False
    )
    proxy_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("proxies.id", ondelete="CASCADE"), nullable=False
    )
    added_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    # Phase 2: Weight for weighted rotation
    weight: Mapped[int] = mapped_column(
        Integer, default=1, server_default="1",
    )

    # Relationships
    pool: Mapped["Pool"] = relationship("Pool", back_populates="pool_proxies")
    proxy: Mapped["Proxy"] = relationship("Proxy", back_populates="pool_proxies")

    def __repr__(self) -> str:
        return f"<PoolProxy pool={self.pool_id} proxy={self.proxy_id}>"


class ProjectPool(Base, UUIDMixin):
    __tablename__ = "project_pools"
    __table_args__ = (
        UniqueConstraint("project_id", "pool_id", name="uq_project_pool"),
    )

    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    pool_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("pools.id", ondelete="CASCADE"), nullable=False
    )
    priority: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    assigned_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # Relationships
    project: Mapped["Project"] = relationship("Project", back_populates="project_pools")
    pool: Mapped["Pool"] = relationship("Pool", back_populates="project_pools")

    def __repr__(self) -> str:
        return f"<ProjectPool project={self.project_id} pool={self.pool_id}>"
