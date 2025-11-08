"""
Schémas Pydantic pour les candidats
"""
from pydantic import BaseModel, EmailStr, Field
from typing import Optional
from datetime import date
from ..models.enums import StatutHandicap


class CandidatBase(BaseModel):
    civilite: Optional[str] = None
    nom: str = Field(..., min_length=2, max_length=50)
    prenom: str = Field(..., min_length=2, max_length=50)
    date_naissance: Optional[date] = None
    email: EmailStr
    telephone: Optional[str] = None
    adresse_personnelle: Optional[str] = None
    niveau_etudes: Optional[str] = None
    secteur_activite: Optional[str] = None
    handicap: bool = False
    type_handicap: Optional[StatutHandicap] = None
    besoins_accommodation: Optional[str] = None


class CandidatCreate(CandidatBase):
    pass


class CandidatUpdate(BaseModel):
    civilite: Optional[str] = None
    nom: Optional[str] = None
    prenom: Optional[str] = None
    date_naissance: Optional[date] = None
    telephone: Optional[str] = None
    adresse_personnelle: Optional[str] = None
    niveau_etudes: Optional[str] = None
    secteur_activite: Optional[str] = None
    handicap: Optional[bool] = None
    type_handicap: Optional[StatutHandicap] = None
    besoins_accommodation: Optional[str] = None


class CandidatResponse(CandidatBase):
    id: int

    class Config:
        from_attributes = True
