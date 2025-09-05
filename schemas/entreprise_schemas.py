"""
Schémas Pydantic pour les entreprises
"""
from pydantic import BaseModel, Field
from typing import Optional
from datetime import date


class EntrepriseBase(BaseModel):
    siret: Optional[str] = Field(None, min_length=14, max_length=14)
    siren: Optional[str] = Field(None, min_length=9, max_length=9)
    raison_sociale: Optional[str] = None
    code_naf: Optional[str] = None
    date_creation: Optional[date] = None
    adresse: Optional[str] = None
    qpv: Optional[bool] = None
    chiffre_affaires: Optional[float] = None
    nombre_points_vente: Optional[int] = None
    specialite_culinaire: Optional[str] = None
    nom_concept: Optional[str] = None
    lien_reseaux_sociaux: Optional[str] = None
    site_internet: Optional[str] = None
    territoire: Optional[str] = None


class EntrepriseCreate(EntrepriseBase):
    candidat_id: int


class EntrepriseUpdate(BaseModel):
    siret: Optional[str] = None
    siren: Optional[str] = None
    raison_sociale: Optional[str] = None
    code_naf: Optional[str] = None
    date_creation: Optional[date] = None
    adresse: Optional[str] = None
    qpv: Optional[bool] = None
    chiffre_affaires: Optional[float] = None
    nombre_points_vente: Optional[int] = None
    specialite_culinaire: Optional[str] = None
    nom_concept: Optional[str] = None
    lien_reseaux_sociaux: Optional[str] = None
    site_internet: Optional[str] = None
    territoire: Optional[str] = None


class EntrepriseResponse(EntrepriseBase):
    id: int
    candidat_id: int

    class Config:
        from_attributes = True
