from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, Float, JSON
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
    strategy = Column(String, default="mobile")
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Performance Stats
    perf_score = Column(Float, nullable=True) # 0-100
    perf_fcp = Column(Float, nullable=True)   # First Contentful Paint (s)
    perf_lcp = Column(Float, nullable=True)   # Largest Contentful Paint (s)
    perf_cls = Column(Float, nullable=True)   # Cumulative Layout Shift
    
    perf_seo = Column(Float, nullable=True)
    perf_accessible = Column(Float, nullable=True)
    perf_best_practices = Column(Float, nullable=True)
    perf_details = Column(JSON, nullable=True) # List of failing audits/errors
    perf_screenshot = Column(String, nullable=True) # Base64 webp screenshot
    perf_thumbnails = Column(JSON, nullable=True) # Animated filmstrip thumbnails
    perf_tbt = Column(Float, nullable=True)

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
