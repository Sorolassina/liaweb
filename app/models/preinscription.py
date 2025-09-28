# app/models/preinscription.py
from sqlmodel import SQLModel, Field, Relationship
from typing import Optional, List
from datetime import datetime, timezone
from .enums import StatutDossier

class Preinscription(SQLModel, table=True):
    __tablename__ = "preinscription"
    
    """Préinscription d'un candidat"""
    id: Optional[int] = Field(default=None, primary_key=True)
    programme_id: int = Field(foreign_key="programme.id")
    candidat_id: int = Field(foreign_key="candidat.id")
    source: Optional[str] = None  # "formulaire", "import", etc.
    donnees_brutes_json: Optional[str] = None  # données du formulaire
    statut: StatutDossier = StatutDossier.SOUMIS
    cree_le: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    
    # Relations
    programme: "Programme" = Relationship(back_populates="preinscriptions")
    candidat: "Candidat" = Relationship(back_populates="preinscriptions")
    eligibilite: Optional["Eligibilite"] = Relationship(back_populates="preinscription")

class Eligibilite(SQLModel, table=True):
    __tablename__ = "eligibilite"
    
    """Calcul d'éligibilité d'une préinscription"""
    id: Optional[int] = Field(default=None, primary_key=True)
    preinscription_id: int = Field(foreign_key="preinscription.id")
    ca_seuil_ok: Optional[bool] = None
    ca_score: Optional[float] = None
    qpv_ok: Optional[bool] = None
    anciennete_ok: Optional[bool] = None
    anciennete_annees: Optional[float] = None
    verdict: Optional[str] = None  # "ok" | "attention" | "ko"
    details_json: Optional[str] = None
    calcule_le: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    
    # Relations
    preinscription: Preinscription = Relationship(back_populates="eligibilite")
