# app/models/activity.py  (ou déplace ton fichier ACD/activity.py ici pour centraliser)
from __future__ import annotations
from typing import Optional, Dict, Any
from datetime import datetime, timezone

from sqlmodel import SQLModel, Field, Relationship
from sqlalchemy import Column, DateTime, Index, Text, ForeignKey
from sqlalchemy.dialects.postgresql import JSONB

class ActivityLog(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)

    # Qui - Stockage en dur pour traçabilité permanente
    user_id: Optional[int] = Field(default=None, index=True)  # ID de référence (peut devenir orphelin)
    user_email: Optional[str] = Field(default=None, index=True)
    user_nom_complet: Optional[str] = Field(default=None)  # Nom stocké en dur
    user_role: Optional[str] = Field(default=None)  # Rôle stocké en dur

    # Quoi
    action: str = Field(index=True)                      # ex: "PROGRAMME_CREATE"
    entity: Optional[str] = Field(default=None, index=True)
    entity_id: Optional[int] = Field(default=None, index=True)

    # Contexte
    ip_address: Optional[str] = Field(default=None)
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
