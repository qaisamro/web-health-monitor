from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, Float, Index
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from db import Base


class Monitor(Base):
    __tablename__ = "monitors"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    url = Column(String, nullable=False, index=True)  # فهرس للبحث السريع
    interval_seconds = Column(Integer, default=60)
    is_active = Column(Boolean, default=True, index=True)  # فهرس للتصفية
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # حقول جديدة للإحصائيات
    last_check_at = Column(DateTime(timezone=True), nullable=True)
    last_status = Column(Boolean, nullable=True)  # آخر حالة (up/down)
    uptime_percentage = Column(Float, default=100.0)  # نسبة التشغيل
    total_checks = Column(Integer, default=0)  # إجمالي الفحوصات
    successful_checks = Column(Integer, default=0)  # الفحوصات الناجحة
    avg_response_ms = Column(Integer, nullable=True)  # متوسط وقت الاستجابة
    
    # إعدادات متقدمة
    timeout_seconds = Column(Integer, default=10)  # مهلة الاتصال
    retry_count = Column(Integer, default=2)  # عدد المحاولات
    
    checks = relationship("CheckResult", back_populates="monitor", cascade="all, delete-orphan")

    def update_stats(self, is_up: bool, response_ms: int = None):
        """تحديث الإحصائيات بعد كل فحص."""
        self.total_checks += 1
        if is_up:
            self.successful_checks += 1
        
        # حساب نسبة التشغيل
        if self.total_checks > 0:
            self.uptime_percentage = round((self.successful_checks / self.total_checks) * 100, 2)
        
        # حساب متوسط وقت الاستجابة (moving average)
        if response_ms is not None and is_up:
            if self.avg_response_ms is None:
                self.avg_response_ms = response_ms
            else:
                # Exponential moving average
                self.avg_response_ms = int(self.avg_response_ms * 0.8 + response_ms * 0.2)
        
        self.last_status = is_up
        self.last_check_at = func.now()


class CheckResult(Base):
    __tablename__ = "check_results"

    id = Column(Integer, primary_key=True, index=True)
    monitor_id = Column(Integer, ForeignKey("monitors.id", ondelete="CASCADE"), nullable=False)

    checked_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    is_up = Column(Boolean, nullable=False, index=True)
    status_code = Column(Integer, nullable=True)
    response_ms = Column(Integer, nullable=True)
    error = Column(String, nullable=True)
    
    # حقول جديدة
    retry_attempts = Column(Integer, default=0)  # عدد المحاولات المستخدمة
    ssl_valid = Column(Boolean, nullable=True)  # حالة شهادة SSL
    
    monitor = relationship("Monitor", back_populates="checks")

    # فهرس مركب للاستعلامات السريعة
    __table_args__ = (
        Index('ix_check_results_monitor_checked', 'monitor_id', 'checked_at'),
    )
