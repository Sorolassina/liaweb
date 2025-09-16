"""
Modèles pour le système de Codéveloppement
"""
from sqlmodel import SQLModel, Field, Relationship
from typing import Optional, List, TYPE_CHECKING
from datetime import datetime, timezone, date

if TYPE_CHECKING:
    from .base import Groupe, Inscription, User, Programme, Promotion

from .enums import *

class SeanceCodev(SQLModel, table=True):
    """Séance de codéveloppement"""
    id: Optional[int] = Field(default=None, primary_key=True)
    groupe_id: int = Field(foreign_key="groupe.id")
    numero_seance: int = Field(index=True)  # Numéro de séance dans le cycle
    date_seance: datetime
    lieu: Optional[str] = None
    animateur_id: Optional[int] = Field(foreign_key="user.id")  # Animateur/facilitateur
    statut: str = Field(default="planifie", max_length=20)
    duree_minutes: Optional[int] = 180  # Durée par défaut 3h
    objectifs: Optional[str] = None
    notes_animateur: Optional[str] = None
    cree_le: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    
    # Relations
    groupe: "Groupe" = Relationship()
    animateur: Optional["User"] = Relationship()
    presentations: List["PresentationCodev"] = Relationship(back_populates="seance")
    participants: List["ParticipationSeance"] = Relationship(back_populates="seance")

class PresentationCodev(SQLModel, table=True):
    """Présentation d'un candidat lors d'une séance"""
    id: Optional[int] = Field(default=None, primary_key=True)
    seance_id: int = Field(foreign_key="seancecodev.id")
    candidat_id: int = Field(foreign_key="inscription.id")
    ordre_presentation: int  # Ordre dans la séance (1, 2, 3...)
    probleme_expose: str  # Problématique exposée
    contexte: Optional[str] = None
    solutions_proposees: Optional[str] = None  # Solutions proposées par le groupe
    engagement_candidat: Optional[str] = None  # Ce que le candidat s'engage à faire
    delai_engagement: Optional[date] = None  # Date limite pour tester
    statut: str = Field(default="en_attente", max_length=20)
    notes_candidat: Optional[str] = None  # Notes du candidat après test
    cree_le: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    
    # Relations
    seance: SeanceCodev = Relationship(back_populates="presentations")
    candidat: "Inscription" = Relationship()
    contributions: List["ContributionCodev"] = Relationship(back_populates="presentation")

class ContributionCodev(SQLModel, table=True):
    """Contribution d'un participant à une présentation"""
    id: Optional[int] = Field(default=None, primary_key=True)
    presentation_id: int = Field(foreign_key="presentationcodev.id")
    contributeur_id: int = Field(foreign_key="inscription.id")
    type_contribution: str = Field(default="suggestion", max_length=20)
    contenu: str
    ordre_contribution: Optional[int] = None  # Ordre d'intervention
    cree_le: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    
    # Relations
    presentation: PresentationCodev = Relationship(back_populates="contributions")
    contributeur: "Inscription" = Relationship()

class ParticipationSeance(SQLModel, table=True):
    """Participation d'un candidat à une séance"""
    id: Optional[int] = Field(default=None, primary_key=True)
    seance_id: int = Field(foreign_key="seancecodev.id")
    candidat_id: int = Field(foreign_key="inscription.id")
    statut_presence: str = Field(default="absent", max_length=20)
    heure_arrivee: Optional[datetime] = None
    heure_depart: Optional[datetime] = None
    notes_participant: Optional[str] = None
    evaluation_seance: Optional[int] = None  # Note de 1 à 5
    commentaires: Optional[str] = None
    cree_le: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    
    # Relations
    seance: SeanceCodev = Relationship(back_populates="participants")
    candidat: "Inscription" = Relationship()

class CycleCodev(SQLModel, table=True):
    """Cycle de codéveloppement (série de séances)"""
    id: Optional[int] = Field(default=None, primary_key=True)
    nom: str = Field(index=True, max_length=100)
    description: Optional[str] = None
    programme_id: int = Field(foreign_key="programme.id")
    promotion_id: Optional[int] = Field(foreign_key="promotion.id")
    date_debut: date
    date_fin: date
    nombre_seances_prevues: int = Field(default=6)
    duree_seance_minutes: int = Field(default=180)
    animateur_principal_id: Optional[int] = Field(foreign_key="user.id")
    statut: str = Field(default="planifie", max_length=20)
    objectifs_cycle: Optional[str] = None
    cree_le: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    
    # Relations
    programme: "Programme" = Relationship()
    promotion: Optional["Promotion"] = Relationship()
    animateur_principal: Optional["User"] = Relationship()
    groupes: List["GroupeCodev"] = Relationship(back_populates="cycle")

class GroupeCodev(SQLModel, table=True):
    """Groupe de codéveloppement dans un cycle"""
    id: Optional[int] = Field(default=None, primary_key=True)
    cycle_id: int = Field(foreign_key="cyclecodev.id")
    groupe_id: int = Field(foreign_key="groupe.id")
    nom_groupe: str  # Nom spécifique dans ce cycle (ex: "Groupe Alpha - Cycle 2024")
    animateur_id: Optional[int] = Field(foreign_key="user.id")
    capacite_max: int = Field(default=12)
    statut: str = Field(default="en_constitution", max_length=20)
    date_creation: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    
    # Relations
    cycle: CycleCodev = Relationship(back_populates="groupes")
    groupe: "Groupe" = Relationship()
    animateur: Optional["User"] = Relationship()
    membres: List["MembreGroupeCodev"] = Relationship(back_populates="groupe_codev")

class MembreGroupeCodev(SQLModel, table=True):
    """Membre d'un groupe de codéveloppement"""
    id: Optional[int] = Field(default=None, primary_key=True)
    groupe_codev_id: int = Field(foreign_key="groupecodev.id")
    candidat_id: int = Field(foreign_key="inscription.id")
    date_integration: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    statut: str = Field(default="actif", max_length=20)
    role_special: Optional[str] = None  # Ex: "secrétaire", "rapporteur"
    notes_integration: Optional[str] = None
    
    # Relations
    groupe_codev: GroupeCodev = Relationship(back_populates="membres")
    candidat: "Inscription" = Relationship()

# Le modèle Groupe est déjà défini dans base.py
# Nous importons les relations nécessaires depuis base.py
