from __future__ import annotations
from typing import List
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.models import SearchHistory, AgentAuditLog
from backend.schemas.history import SearchHistoryItem, HistoryResponse, AuditLogItem

router = APIRouter(prefix="/api/history", tags=["History & Audit"])


@router.get("", response_model=HistoryResponse)
def get_search_history(
    user_id: int = Query(1, description="User ID"),
    limit: int = Query(20, description="Max history items"),
    db: Session = Depends(get_db),
):
    rows = (
        db.query(SearchHistory)
        .filter(SearchHistory.user_id == user_id)
        .order_by(SearchHistory.created_at.desc())
        .limit(limit)
        .all()
    )

    items: List[SearchHistoryItem] = []
    for r in rows:
        items.append(
            SearchHistoryItem(
                id=r.id,
                raw_query=r.raw_query,
                constraints=r.constraints_json,
                created_at=r.created_at.isoformat() if r.created_at else "",
                product_count=len(r.products),
            )
        )

    return HistoryResponse(
        searches=items,
        total_searches=len(items),
    )


@router.get("/audit", response_model=List[AuditLogItem])
def get_audit_logs(
    user_id: int = Query(1, description="User ID"),
    limit: int = Query(20, description="Max audit items"),
    db: Session = Depends(get_db),
):
    rows = (
        db.query(AgentAuditLog)
        .filter(AgentAuditLog.user_id == user_id)
        .order_by(AgentAuditLog.created_at.desc())
        .limit(limit)
        .all()
    )

    return [
        AuditLogItem(
            id=r.id,
            action=r.action,
            payload=r.payload_json,
            created_at=r.created_at.isoformat() if r.created_at else "",
        )
        for r in rows
    ]
