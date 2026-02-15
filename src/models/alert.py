from datetime import datetime

from sqlalchemy import Boolean, CheckConstraint, DateTime, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from src.models.base import Base, TimestampMixin, UUIDMixin


class AlertRule(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "alert_rules"
    __table_args__ = (
        CheckConstraint(
            "condition_type IN ('error_rate_above', 'pool_below_min_healthy', "
            "'bandwidth_exceeded', 'all_proxies_dead')",
            name="ck_alert_condition_type",
        ),
        CheckConstraint(
            "action_type IN ('webhook', 'auto_blacklist')",
            name="ck_alert_action_type",
        ),
    )

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    condition_type: Mapped[str] = mapped_column(String(50), nullable=False)
    condition_config: Mapped[dict] = mapped_column(JSONB, nullable=False)
    action_type: Mapped[str] = mapped_column(String(50), nullable=False)
    action_config: Mapped[dict] = mapped_column(JSONB, nullable=False)
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
    last_triggered_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    def __repr__(self) -> str:
        return f"<AlertRule {self.name}>"
