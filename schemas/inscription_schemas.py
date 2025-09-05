"""
Schémas Pydantic pour les inscriptions
"""
from pydantic import BaseModel
from typing import Optional
from datetime import datetime
from ..models.enums import StatutDossier
from .programme_schemas import ProgrammeResponse
from .candidat_schemas import CandidatResponse
from .user_schemas import UserResponse


class InscriptionBase(BaseModel):
    programme_id: int
    candidat_id: int
    promotion_id: Optional[int] = None
    groupe_id: Optional[int] = None
    conseiller_id: Optional[int] = None
    referent_id: Optional[int] = None


class InscriptionCreate(InscriptionBase):
    pass


class InscriptionUpdate(BaseModel):
    promotion_id: Optional[int] = None
    groupe_id: Optional[int] = None
    conseiller_id: Optional[int] = None
    referent_id: Optional[int] = None
    statut: Optional[StatutDossier] = None
    email_confirmation_envoye: Optional[bool] = None


class InscriptionResponse(InscriptionBase):
    id: int
    statut: StatutDossier
    date_decision: Optional[datetime] = None
    email_confirmation_envoye: bool
    cree_le: datetime
    programme: ProgrammeResponse
    candidat: CandidatResponse
    conseiller: Optional[UserResponse] = None
    referent: Optional[UserResponse] = None

    class Config:
        from_attributes = True
