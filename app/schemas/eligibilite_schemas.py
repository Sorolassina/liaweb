"""
Schémas Pydantic pour l'éligibilité
"""
from pydantic import BaseModel
from typing import Optional
from datetime import datetime


class EligibiliteBase(BaseModel):
    preinscription_id: int


class EligibiliteCreate(EligibiliteBase):
    ca_seuil_ok: Optional[bool] = None
    ca_score: Optional[float] = None
    qpv_ok: Optional[bool] = None
    anciennete_ok: Optional[bool] = None
    anciennete_annees: Optional[float] = None
    verdict: Optional[str] = None
    details_json: Optional[str] = None


class EligibiliteResponse(EligibiliteBase):
    id: int
    ca_seuil_ok: Optional[bool] = None
    ca_score: Optional[float] = None
    qpv_ok: Optional[bool] = None
    anciennete_ok: Optional[bool] = None
    anciennete_annees: Optional[float] = None
    verdict: Optional[str] = None
    details_json: Optional[str] = None
    calcule_le: datetime

    class Config:
        from_attributes = True
