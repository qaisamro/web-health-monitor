from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from db import Base


class Monitor(Base):
    __tablename__ = "monitors"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    url = Column(String, nullable=False)
    interval_seconds = Column(Integer, default=60)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    checks = relationship("CheckResult", back_populates="monitor", cascade="all, delete-orphan")


class CheckResult(Base):
    __tablename__ = "check_results"

    id = Column(Integer, primary_key=True, index=True)
    monitor_id = Column(Integer, ForeignKey("monitors.id"), nullable=False)

    checked_at = Column(DateTime(timezone=True), server_default=func.now())
    is_up = Column(Boolean, nullable=False)
    status_code = Column(Integer, nullable=True)
    response_ms = Column(Integer, nullable=True)
    error = Column(String, nullable=True)

    monitor = relationship("Monitor", back_populates="checks")
