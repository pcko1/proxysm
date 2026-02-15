from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.models.base import Base, TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from src.models.associations import ProjectPool


class Project(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "projects"

    name: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    slug: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    api_key_hash: Mapped[str] = mapped_column(String(128), nullable=False)

    # Phase 2: Quotas
    rate_limit_rpm: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    bandwidth_quota_bytes: Mapped[int] = mapped_column(BigInteger, default=0, server_default="0")

    # Relationships
    project_pools: Mapped[list["ProjectPool"]] = relationship(
        "ProjectPool", back_populates="project", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Project {self.name}>"
