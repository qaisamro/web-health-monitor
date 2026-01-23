from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker, declarative_base
from sqlalchemy.pool import QueuePool
from contextlib import contextmanager

DATABASE_URL = "sqlite:///./monitor.db"

# إنشاء Engine محسّن مع Connection Pool
engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=QueuePool,
    pool_size=5,           # عدد الاتصالات الأساسية
    max_overflow=10,       # اتصالات إضافية عند الحاجة
    pool_pre_ping=True,    # فحص صحة الاتصال قبل الاستخدام
    echo=False,            # تعطيل SQL logging للأداء
)

# تفعيل Foreign Keys لـ SQLite
@event.listens_for(engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.execute("PRAGMA journal_mode=WAL")  # أداء أفضل للكتابة
    cursor.close()

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


# Context Manager لإدارة الجلسات بشكل آمن
@contextmanager
def get_db_session():
    """Context manager للتعامل الآمن مع جلسات قاعدة البيانات."""
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def cleanup_old_results(db, days: int = 30):
    """حذف نتائج الفحص القديمة - تنظيف دوري."""
    from datetime import datetime, timedelta
    from models import CheckResult
    
    cutoff = datetime.utcnow() - timedelta(days=days)
    deleted = db.query(CheckResult).filter(CheckResult.checked_at < cutoff).delete()
    db.commit()
    return deleted
