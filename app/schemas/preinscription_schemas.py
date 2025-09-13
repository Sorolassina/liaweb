"""
Schémas Pydantic pour les préinscriptions
"""
from pydantic import BaseModel
from typing import Optional
from datetime import datetime
from app_lia_web.app.models.enums import StatutDossier
from .programme_schemas import ProgrammeResponse
from .candidat_schemas import CandidatResponse


class PreinscriptionBase(BaseModel):
    programme_id: int
    candidat_id: int
    source: Optional[str] = None
    donnees_brutes_json: Optional[str] = None


class PreinscriptionCreate(PreinscriptionBase):
    pass


class PreinscriptionUpdate(BaseModel):
    source: Optional[str] = None
    donnees_brutes_json: Optional[str] = None
    statut: Optional[StatutDossier] = None


class PreinscriptionResponse(PreinscriptionBase):
    id: int
    statut: StatutDossier
    cree_le: datetime
    programme: ProgrammeResponse
    candidat: CandidatResponse

    class Config:
        from_attributes = True
