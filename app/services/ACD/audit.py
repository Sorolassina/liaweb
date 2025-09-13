# app/services/audit.py
from __future__ import annotations
from typing import Optional, Any, Dict
from fastapi import Request
from sqlmodel import Session
from app_lia_web.app.models.ACD.activity import ActivityLog
from app_lia_web.app.models.base import User

def _client_ip(req: Optional[Request]) -> Optional[str]:
    if not req: return None
    # X-Forwarded-For chain aware
    fwd = req.headers.get("x-forwarded-for")
    if fwd:
        return fwd.split(",")[0].strip()
    return req.client.host if req.client else None

def _ua(req: Optional[Request]) -> Optional[str]:
    if not req: return None
    return req.headers.get("user-agent")

def log_activity(
    session: Session,
    *,
    user: Optional[User],
    action: str,
    entity: Optional[str] = None,
    entity_id: Optional[int] = None,
    activity_data: Optional[Dict[str, Any]] = None,
    request: Optional[Request] = None
) -> None:
    row = ActivityLog(
        user_id=user.id if user else None,
        user_email=user.email if user else None,
        user_nom_complet=user.nom_complet if user else None,  # Stockage en dur
        user_role=user.role if user else None,  # Stockage en dur
        action=action,
        entity=entity,
        entity_id=entity_id,
        ip_address=_client_ip(request),  # Corrigé le nom du champ
        user_agent=_ua(request),
        activity_data=activity_data or {},
    )
    session.add(row)
    # on ne commit PAS ici : laisse l’appelant gérer la transaction
