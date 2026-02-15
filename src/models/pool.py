from typing import TYPE_CHECKING

from sqlalchemy import Boolean, CheckConstraint, Float, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.models.base import Base, TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from src.models.associations import PoolProxy, ProjectPool


class Pool(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "pools"
    __table_args__ = (
        CheckConstraint(
            "rotation_strategy IN ('round_robin', 'random', 'weighted_random', 'least_connections')",
            name="ck_pool_rotation_strategy",
        ),
    )

    name: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    rotation_strategy: Mapped[str] = mapped_column(
        String(30), default="round_robin", server_default="round_robin"
    )

    # Phase 2: Pool configuration
    is_exclusive: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    sticky_session_ttl: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    health_check_interval: Mapped[int] = mapped_column(Integer, default=60, server_default="60")
    blacklist_threshold: Mapped[float] = mapped_column(Float, default=0.20, server_default="0.20")
    blacklist_window_seconds: Mapped[int] = mapped_column(
        Integer, default=300, server_default="300"
    )
    blacklist_cooldown_seconds: Mapped[int] = mapped_column(
        Integer, default=1800, server_default="1800"
    )
    min_healthy_proxies: Mapped[int] = mapped_column(Integer, default=1, server_default="1")

    # Relationships
    pool_proxies: Mapped[list["PoolProxy"]] = relationship(
        "PoolProxy", back_populates="pool", cascade="all, delete-orphan"
    )
    project_pools: Mapped[list["ProjectPool"]] = relationship(
        "ProjectPool", back_populates="pool", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Pool {self.name}>"
