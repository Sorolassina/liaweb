# app/models/rendez_vous.py
from sqlmodel import SQLModel, Field, Relationship
from typing import Optional, List
from datetime import datetime, timezone
from .enums import TypeRDV, StatutRDV

class RendezVous(SQLModel, table=True):
    __tablename__ = "rendez_vous"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    candidat_id: int = Field(foreign_key="candidat.id")
    conseiller_id: Optional[int] = Field(foreign_key="user.id")
    type_rdv: TypeRDV = TypeRDV.ENTRETIEN
    statut: StatutRDV = StatutRDV.PLANIFIE
    debut: datetime
    fin: Optional[datetime] = None
    lieu: Optional[str] = None
    notes: Optional[str] = None
    meet_link: Optional[str] = None  # Lien Google Meet unique

    # Relations
    candidat: "Candidat" = Relationship()
    conseiller: Optional["User"] = Relationship()
    emargements: List["EmargementRDV"] = Relationship(back_populates="rdv")

class EmargementRDV(SQLModel, table=True):
    __tablename__ = "emargement_rdv"
    
    """Émargement pour les rendez-vous"""
    id: Optional[int] = Field(default=None, primary_key=True)
    rdv_id: int = Field(foreign_key="rendez_vous.id", index=True)
    type_signataire: str = Field(index=True)  # "conseiller" ou "candidat"
    signataire_id: Optional[int] = Field(foreign_key="user.id", index=True)  # Pour le conseiller
    candidat_id: Optional[int] = Field(foreign_key="candidat.id", index=True)  # Pour le candidat
    signature_conseiller: Optional[str] = None  # Signature du conseiller (base64 ou hash)
    signature_candidat: Optional[str] = None    # Signature du candidat (base64 ou hash)
    date_signature_conseiller: Optional[datetime] = None
    date_signature_candidat: Optional[datetime] = None
    ip_address: Optional[str] = None  # Adresse IP pour traçabilité
    user_agent: Optional[str] = None  # User agent pour traçabilité
    cree_le: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    
    # Relations
    rdv: "RendezVous" = Relationship()
    signataire: Optional["User"] = Relationship()
    candidat: Optional["Candidat"] = Relationship(back_populates="emargements_rdv")
