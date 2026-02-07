from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from datetime import timedelta
from typing import List

from db import SessionLocal
from models import Monitor, CheckResult
from auth import (
    create_access_token, get_current_user, check_role, 
    verify_password, USERS_DB, Token, User, ACCESS_TOKEN_EXPIRE_MINUTES
)
from pydantic import BaseModel, HttpUrl, Field
from messaging import publish_check

router = APIRouter(prefix="/api/v1", tags=["v1"])

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# -------------------- Schemas --------------------
class MonitorCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=120, example="Google")
    url: HttpUrl = Field(..., example="https://google.com")
    interval_seconds: int = Field(60, ge=10, le=3600, example=60)
    strategy: str = Field("mobile", example="mobile")

class MonitorResponse(BaseModel):
    id: int
    name: str
    url: str
    interval_seconds: int
    is_active: bool
    perf_score: float | None = None
    perf_fcp: float | None = None
    perf_lcp: float | None = None
    perf_cls: float | None = None
    perf_seo: float | None = None
    perf_accessible: float | None = None
    perf_best_practices: float | None = None
    perf_details: list | None = None
    perf_screenshot: str | None = None
    perf_thumbnails: list | None = None
    perf_tbt: float | None = None
    strategy: str | None = "mobile"
    class Config:
        from_attributes = True

# -------------------- Auth Endpoints --------------------
@router.post("/auth/login", response_model=Token)
async def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends()):
    user = USERS_DB.get(form_data.username)
    if not user or not verify_password(form_data.password, user["password_hash"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user["username"], "role": user["role"]}, expires_delta=access_token_expires
    )
    return {"access_token": access_token, "token_type": "bearer"}

# -------------------- Monitor Endpoints --------------------
@router.get("/monitors", response_model=List[MonitorResponse])
def list_monitors(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return db.query(Monitor).all()

@router.post("/monitors", response_model=MonitorResponse, status_code=status.HTTP_201_CREATED)
def create_monitor(
    payload: MonitorCreate, 
    db: Session = Depends(get_db), 
    current_user: User = Depends(check_role("admin"))
):
    m = Monitor(
        name=payload.name,
        url=str(payload.url),
        interval_seconds=payload.interval_seconds,
        is_active=True,
        strategy=payload.strategy
    )
    db.add(m)
    db.commit()
    db.refresh(m)
    db.refresh(m)
    
    # Trigger initial check and performance audit
    publish_check(m.id, task_type="check")
    publish_check(m.id, task_type="audit", strategy=payload.strategy)
    
    return m

@router.delete("/monitors/{monitor_id}")
def delete_monitor(
    monitor_id: int, 
    db: Session = Depends(get_db), 
    current_user: User = Depends(check_role("admin"))
):
    m = db.query(Monitor).filter(Monitor.id == monitor_id).first()
    if not m:
        raise HTTPException(status_code=404, detail="Monitor not found")
    db.delete(m)
    db.commit()
    return {"ok": True}
