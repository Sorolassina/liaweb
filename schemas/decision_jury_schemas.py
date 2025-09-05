"""
Schémas Pydantic pour les décisions de jury
"""
from pydantic import BaseModel
from typing import Optional
from datetime import datetime
from ..models.enums import DecisionJury


class DecisionJuryBase(BaseModel):
    inscription_id: int
    jury_id: int
    decision: DecisionJury
    commentaires: Optional[str] = None
    prises_en_charge_json: Optional[str] = None


class DecisionJuryCreate(DecisionJuryBase):
    pass


class DecisionJuryResponse(DecisionJuryBase):
    id: int
    decide_le: datetime

    class Config:
        from_attributes = True
