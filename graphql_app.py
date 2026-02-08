import strawberry
from typing import List, Optional
from strawberry.fastapi import GraphQLRouter
from sqlalchemy.orm import Session
from db import SessionLocal
from models import Monitor as MonitorModel, CheckResult as CheckResultModel


@strawberry.type
class CheckResult:
    id: int
    monitor_id: int
    checked_at: str
    is_up: bool
    status_code: Optional[int]
    response_ms: int
    error: Optional[str]


@strawberry.type
class Monitor:
    id: int
    name: str
    url: str
    interval_seconds: int
    is_active: bool

    @strawberry.field
    def checks(self, limit: int = 10) -> List[CheckResult]:
        db = SessionLocal()
        try:
            results = (
                db.query(CheckResultModel)
                .filter(CheckResultModel.monitor_id == self.id)
                .order_by(CheckResultModel.checked_at.desc())
                .limit(limit)
                .all()
            )
            return [
                CheckResult(
                    id=r.id,
                    monitor_id=r.monitor_id,
                    checked_at=r.checked_at.isoformat(),
                    is_up=r.is_up,
                    status_code=r.status_code,
                    response_ms=r.response_ms,
                    error=r.error,
                )
                for r in results
            ]
        finally:
            db.close()


@strawberry.type
class Query:
    @strawberry.field
    def monitors(self) -> List[Monitor]:
        db = SessionLocal()
        try:
            monitors = db.query(MonitorModel).all()
            return [
                Monitor(
                    id=m.id,
                    name=m.name,
                    url=m.url,
                    interval_seconds=m.interval_seconds,
                    is_active=m.is_active,
                )
                for m in monitors
            ]
        finally:
            db.close()


schema = strawberry.Schema(query=Query)
graphql_app = GraphQLRouter(schema)
