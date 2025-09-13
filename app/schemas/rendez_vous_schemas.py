# app/schemas/rendez_vous_schemas.py
from datetime import datetime
from typing import Optional
from pydantic import BaseModel
from app_lia_web.app.models.enums import TypeRDV, StatutRDV

class RendezVousBase(BaseModel):
    """Schéma de base pour un rendez-vous"""
    inscription_id: int
    conseiller_id: Optional[int] = None
    type_rdv: TypeRDV = TypeRDV.ENTRETIEN
    statut: StatutRDV = StatutRDV.PLANIFIE
    debut: datetime
    fin: Optional[datetime] = None
    lieu: Optional[str] = None
    notes: Optional[str] = None

class RendezVousCreate(RendezVousBase):
    """Schéma pour créer un rendez-vous"""
    pass

class RendezVousUpdate(BaseModel):
    """Schéma pour mettre à jour un rendez-vous"""
    conseiller_id: Optional[int] = None
    type_rdv: Optional[TypeRDV] = None
    statut: Optional[StatutRDV] = None
    debut: Optional[datetime] = None
    fin: Optional[datetime] = None
    lieu: Optional[str] = None
    notes: Optional[str] = None

class RendezVousResponse(RendezVousBase):
    """Schéma de réponse pour un rendez-vous"""
    id: int
    
    class Config:
        from_attributes = True

class RendezVousWithDetails(RendezVousResponse):
    """Schéma étendu avec les détails du candidat et du conseiller"""
    candidat_nom: Optional[str] = None
    candidat_prenom: Optional[str] = None
    candidat_email: Optional[str] = None
    candidat_telephone: Optional[str] = None
    conseiller_nom: Optional[str] = None
    programme_nom: Optional[str] = None
    entreprise_nom: Optional[str] = None

class RendezVousFilter(BaseModel):
    """Filtres pour la recherche de rendez-vous"""
    programme_id: Optional[int] = None
    conseiller_id: Optional[int] = None
    type_rdv: Optional[TypeRDV] = None
    statut: Optional[StatutRDV] = None
    date_debut: Optional[datetime] = None
    date_fin: Optional[datetime] = None
    candidat_nom: Optional[str] = None
    entreprise_nom: Optional[str] = None
