"""SQLAlchemy ORM models."""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import Column, DateTime, Float, Integer, String, Text
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass


class EventRecord(Base):
    """A persisted analyzed news event."""

    __tablename__ = "events"

    id = Column(String(64), primary_key=True)  # content hash
    url = Column(String(1024), nullable=False, index=True)
    source = Column(String(255), nullable=False, index=True)
    title = Column(String(1024), nullable=False)
    summary = Column(Text, default="")
    published_at = Column(DateTime, nullable=True, index=True)
    fetched_at = Column(DateTime, default=datetime.utcnow, index=True)

    impact_level = Column(String(16), index=True)
    impact_direction = Column(String(16))
    time_horizon = Column(String(32))
    affected_sectors = Column(Text, default="")  # JSON-encoded list
    affected_assets = Column(Text, default="")
    affected_regions = Column(Text, default="")
    confidence = Column(Float, default=0.0)

    why_it_matters = Column(Text, default="")
    rationale = Column(Text, default="")
    analysis_summary = Column(Text, default="")


class RunRecord(Base):
    """One pipeline run."""

    __tablename__ = "runs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    started_at = Column(DateTime, default=datetime.utcnow, index=True)
    finished_at = Column(DateTime, nullable=True)
    status = Column(String(32), default="running")  # running | success | failed
    items_collected = Column(Integer, default=0)
    items_analyzed = Column(Integer, default=0)
    error = Column(Text, nullable=True)


class ReportRecord(Base):
    """A persisted daily report (HTML)."""

    __tablename__ = "reports"

    date = Column(String(10), primary_key=True)  # YYYY-MM-DD
    generated_at = Column(DateTime, default=datetime.utcnow)
    html = Column(Text)
    markdown = Column(Text)
    executive_summary = Column(Text)
