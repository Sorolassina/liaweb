"""
Schémas Pydantic pour la recherche et les filtres
"""
from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import date
from ..models.enums import StatutDossier


class CandidatFiltres(BaseModel):
    programme_id: Optional[int] = None
    statut: Optional[StatutDossier] = None
    handicap: Optional[bool] = None
    territoire: Optional[str] = None
    date_debut: Optional[date] = None
    date_fin: Optional[date] = None


class PaginationParams(BaseModel):
    page: int = Field(1, ge=1)
    taille: int = Field(10, ge=1, le=100)


class PaginatedResponse(BaseModel):
    items: List[dict]
    total: int
    page: int
    taille: int
    pages: int
