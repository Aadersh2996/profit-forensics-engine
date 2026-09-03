"""SQLAlchemy models for persisted investigation results."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import DateTime, Float, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    """Base class for all ORM entities."""


class Investigation(Base):
    __tablename__ = "investigations"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utc_now, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utc_now, onupdate=_utc_now, nullable=False
    )
    confidence: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    current_hypothesis: Mapped[str | None] = mapped_column(Text, nullable=True)
    estimated_monthly_loss: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    estimated_annual_loss: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    executive_summary: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)

    case_files: Mapped[list[CaseFileORM]] = relationship(
        back_populates="investigation", cascade="all, delete-orphan"
    )
    timeline_events: Mapped[list[TimelineEventORM]] = relationship(
        back_populates="investigation", cascade="all, delete-orphan"
    )
    recommendations: Mapped[list[RecommendationORM]] = relationship(
        back_populates="investigation", cascade="all, delete-orphan"
    )


class CaseFileORM(Base):
    __tablename__ = "case_files"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    investigation_id: Mapped[str] = mapped_column(
        ForeignKey("investigations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    evidence: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list, nullable=False)
    root_cause: Mapped[str | None] = mapped_column(Text, nullable=True)
    estimated_monthly_loss: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    estimated_annual_loss: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    recommendation: Mapped[str | None] = mapped_column(Text, nullable=True)
    priority: Mapped[int] = mapped_column(Integer, nullable=False)

    investigation: Mapped[Investigation] = relationship(back_populates="case_files")


class TimelineEventORM(Base):
    __tablename__ = "timeline_events"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    investigation_id: Mapped[str] = mapped_column(
        ForeignKey("investigations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    title: Mapped[str] = mapped_column(String(160), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    stage: Mapped[str] = mapped_column(String(80), nullable=False)
    progress: Mapped[float] = mapped_column(Float, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utc_now, nullable=False
    )

    investigation: Mapped[Investigation] = relationship(back_populates="timeline_events")


class RecommendationORM(Base):
    __tablename__ = "recommendations"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    investigation_id: Mapped[str] = mapped_column(
        ForeignKey("investigations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    priority: Mapped[int] = mapped_column(Integer, nullable=False)
    expected_monthly_impact: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    related_case_file_ids: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)

    investigation: Mapped[Investigation] = relationship(back_populates="recommendations")
