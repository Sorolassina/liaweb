"""
Schémas Pydantic pour les jurys
"""
from pydantic import BaseModel
from typing import Optional
from datetime import datetime
from .programme_schemas import ProgrammeResponse


class JuryBase(BaseModel):
    programme_id: int
    promotion_id: Optional[int] = None
    session_le: datetime
    lieu: Optional[str] = None


class JuryCreate(JuryBase):
    pass


class JuryUpdate(BaseModel):
    session_le: Optional[datetime] = None
    lieu: Optional[str] = None
    statut: Optional[str] = None


class JuryResponse(JuryBase):
    id: int
    statut: str
    programme: ProgrammeResponse

    class Config:
        from_attributes = True
