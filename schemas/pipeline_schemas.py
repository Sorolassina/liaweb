"""
Schémas Pydantic pour les pipelines
"""
from pydantic import BaseModel
from typing import Optional
from datetime import datetime


class EtapePipelineCreate(BaseModel):
    nom: str
    description: Optional[str] = None
    duree_estimee: Optional[int] = None  # en jours
    ordre: int
    active: bool = True
    conditions: Optional[str] = None


class EtapePipelineUpdate(BaseModel):
    nom: Optional[str] = None
    description: Optional[str] = None
    duree_estimee: Optional[int] = None
    ordre: Optional[int] = None
    active: Optional[bool] = None
    conditions: Optional[str] = None


class AvancementEtapeCreate(BaseModel):
    etape_id: int
    statut: str  # "en_cours", "terminee", "en_attente"
    commentaires: Optional[str] = None
    date_debut: Optional[datetime] = None
    date_fin: Optional[datetime] = None
