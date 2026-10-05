from __future__ import annotations
from typing import Optional, List, Dict, Any
from pydantic import BaseModel


class SearchHistoryItem(BaseModel):
    id: int
    raw_query: str
    constraints: Optional[Dict[str, Any]] = None
    created_at: str
    product_count: int = 0


class HistoryResponse(BaseModel):
    searches: List[SearchHistoryItem]
    total_searches: int


class AuditLogItem(BaseModel):
    id: int
    action: str
    payload: Optional[Dict[str, Any]] = None
    created_at: str
