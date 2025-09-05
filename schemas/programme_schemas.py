"""
Schémas Pydantic pour les programmes
"""
from pydantic import BaseModel, Field
from typing import Optional
from datetime import date
from .user_schemas import UserResponse


class ProgrammeBase(BaseModel):
    code: str = Field(..., min_length=2, max_length=10)
    nom: str = Field(..., min_length=2, max_length=100)
    objectif: Optional[str] = None
    date_debut: Optional[date] = None
    date_fin: Optional[date] = None
    ca_seuil_min: Optional[float] = None
    ca_seuil_max: Optional[float] = None
    anciennete_min_annees: Optional[int] = None


class ProgrammeCreate(ProgrammeBase):
    responsable_id: Optional[int] = None


class ProgrammeUpdate(BaseModel):
    nom: Optional[str] = None
    objectif: Optional[str] = None
    date_debut: Optional[date] = None
    date_fin: Optional[date] = None
    actif: Optional[bool] = None
    ca_seuil_min: Optional[float] = None
    ca_seuil_max: Optional[float] = None
    anciennete_min_annees: Optional[int] = None
    responsable_id: Optional[int] = None


class ProgrammeResponse(ProgrammeBase):
    id: int
    actif: bool
    responsable_id: Optional[int] = None
    responsable: Optional[UserResponse] = None

    class Config:
        from_attributes = True
