# app/models/preinscription.py
from sqlmodel import SQLModel, Field, Relationship
from sqlalchemy import Column, Text
from typing import Optional, List
from datetime import datetime, timezone, date
from .enums import StatutDossier

class Preinscription(SQLModel, table=True):
    __tablename__ = "preinscription"
    
    """Préinscription d'un candidat"""
    id: Optional[int] = Field(default=None, primary_key=True)
    programme_id: int = Field(foreign_key="programme.id")
    candidat_id: int = Field(foreign_key="candidat.id")
    source: Optional[str] = None  # "formulaire", "import", etc.
    statut: StatutDossier = StatutDossier.SOUMIS
    cree_le: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    
    # Données du formulaire Excel/Formulaire (au lieu de JSON)
    # Candidat
    civilite: Optional[str] = None
    nom: Optional[str] = None
    prenom: Optional[str] = None
    date_naissance: Optional[date] = None
    email: Optional[str] = None
    telephone: Optional[str] = None
    
    # Adresse personnelle (décomposée)
    numero_personnel: Optional[str] = None
    rue_personnel: Optional[str] = None
    code_postal_personnel: Optional[str] = None
    ville_personnel: Optional[str] = None
    
    # Adresse entreprise (décomposée)
    numero_entreprise: Optional[str] = None
    rue_entreprise: Optional[str] = None
    code_postal_entreprise: Optional[str] = None
    ville_entreprise: Optional[str] = None
    
    # Entreprise
    date_creation_entreprise: Optional[date] = None
    siret: Optional[str] = None
    chiffre_affaires: Optional[str] = None
    niveau_etudes: Optional[str] = None
    secteur_activite: Optional[str] = None
    
    # Relations
    programme: "Programme" = Relationship(back_populates="preinscriptions")
    candidat: "Candidat" = Relationship(back_populates="preinscriptions")
    eligibilite: Optional["Eligibilite"] = Relationship(back_populates="preinscription")

class Eligibilite(SQLModel, table=True):
    __tablename__ = "eligibilite"
    
    """Calcul d'éligibilité d'une préinscription"""
    id: Optional[int] = Field(default=None, primary_key=True)
    preinscription_id: int = Field(foreign_key="preinscription.id")
    ca_seuil_ok: Optional[str] = None
    ca_score: Optional[str] = None  # Stocke la condition CA (ex: "50000 <= 75000 <= 100000")
    qpv_ok: Optional[str] = None  # Stocke le résultat de verif_qpv (nom_qp): "QPV:nom", "QPV limit:nom", ou "Aucun QPV"
    anciennete_ok: Optional[str] = None
    anciennete_annees: Optional[str] = None  # Stocke la condition ancienneté (ex: "2 >= 3" ou "2 <= 5")
    verdict: Optional[str] = None  # "ok" | "attention" | "ko"
    details_json: Optional[str] = Field(default=None, sa_column=Column(Text))  # JSON text pour stocker les détails (peut être volumineux)
    # URLs des fichiers QPV générés
    qpv_carte_url: Optional[str] = None  # URL de la carte HTML interactive
    qpv_image_url: Optional[str] = None  # URL de l'image PNG de la carte
    calcule_le: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    
    # Relations
    preinscription: Preinscription = Relationship(back_populates="eligibilite")
