# app/models/activity.py  (ou déplace ton fichier ACD/activity.py ici pour centraliser)
from __future__ import annotations
from typing import Optional, Dict, Any
from datetime import datetime, timezone

from sqlmodel import SQLModel, Field
from sqlalchemy import Column, DateTime, Index, Text
from sqlalchemy.dialects.postgresql import JSONB

class ActivityLog(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)

    # Qui
    user_id: Optional[int] = Field(default=None, index=True)
    user_email: Optional[str] = Field(default=None, index=True)

    # Quoi
    action: str = Field(index=True)                      # ex: "PROGRAMME_CREATE"
    entity: Optional[str] = Field(default=None, index=True)
    entity_id: Optional[int] = Field(default=None, index=True)

    # Contexte
    ip: Optional[str] = Field(default=None)
    user_agent: Optional[str] = Field(default=None)

    # Données additionnelles (JSONB)
    activity_data: Optional[Dict[str, Any]] = Field(
        default=None,
        sa_column=Column(JSONB, nullable=True)
    )

    # Horodatage tz-aware (TIMESTAMP WITH TIME ZONE)
    # ⚠️ NE PAS mettre index=True si sa_column est utilisé
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column=Column(DateTime(timezone=True), nullable=False)
    )

    __table_args__ = (
        # Index dédiés (comme index=True mais côté SA, évite le conflit avec sa_column)
        Index("ix_activitylog_created_at", "created_at"),
        # GIN sur JSONB (requêtes @>, ? etc.)
        Index("ix_activitylog_activity_data_gin", "activity_data", postgresql_using="gin"),
    )
