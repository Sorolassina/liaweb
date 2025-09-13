# app/models/preinscription.py
from __future__ import annotations
from typing import Optional
from datetime import date, datetime, timezone
from sqlmodel import SQLModel, Field, Relationship
from app_lia_web.app.models.enums import StatutDossier  # réutilise ton enum existant
from app_lia_web.app.models.base import Programme, Candidat, Eligibilite

class Preinscription(SQLModel, table=True):
    """
    Formulaire de préinscription (public, sans connexion).
    - Conserve un snapshot des données saisies
    - Peut être associé ensuite à un Candidat/Entreprise
    - Sert d’entrée au calcul d’éligibilité (résultat dans table Eligibilite)
    """
    id: Optional[int] = Field(default=None, primary_key=True)

    # Rattachements
    programme_id: int = Field(index=True, foreign_key="programme.id")
    candidat_id: Optional[int] = Field(default=None, foreign_key="candidat.id", index=True)

    # Métadonnées
    source: Optional[str] = Field(default="formulaire")   # "formulaire", "invitation", "import", etc.
    statut: StatutDossier = Field(default=StatutDossier.SOUMIS)
    cree_le: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), index=True)

    # --------- Snapshot des champs saisis (côté prospect) ---------
    # Identité
    civilite: Optional[str] = None
    nom: str
    prenom: str
    date_naissance: date
    email: str = Field(index=True)  # on ne met pas unique ici pour autoriser plusieurs préinscriptions si besoin
    telephone: Optional[str] = None

    # Adresses
    adresse_personnelle: str
    adresse_entreprise: Optional[str] = None

    # Entreprise (déclaratif prospect)
    date_creation_entreprise: Optional[date] = None
    chiffre_affaires: Optional[float] = Field(default=None, description="En euros")
    siret: Optional[str] = Field(default=None, index=True)

    # Profil
    niveau_etudes: Optional[str] = None
    secteur_activite: Optional[str] = None

    # Géocodage (point principal : on privilégie adresse_entreprise, sinon adresse_personnelle)
    lat: Optional[float] = Field(default=None, index=True)
    lng: Optional[float] = Field(default=None, index=True)

    # Indicateurs bruts utiles pour l’éligibilité (facultatif mais pratique pour filtres rapides)
    qpv_addr_perso: Optional[bool] = None
    qpv_addr_entreprise: Optional[bool] = None

    # JSON libre si tu veux garder l’original du formulaire
    donnees_brutes_json: Optional[str] = None

    # --------- Relations ---------
    programme: "Programme" = Relationship(back_populates="preinscriptions")
    candidat: Optional["Candidat"] = Relationship(back_populates="preinscriptions")
    eligibilite: Optional["Eligibilite"] = Relationship(back_populates="preinscription")
