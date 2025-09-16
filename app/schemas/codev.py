"""
Schémas Pydantic pour le système de Codéveloppement
"""
from typing import Optional, List
from datetime import datetime, date
from pydantic import BaseModel, Field

from app_lia_web.app.models.enums import (
    StatutSeanceCodev, StatutPresentation, TypeContribution,
    StatutCycleCodev, StatutGroupeCodev, StatutMembreGroupe, StatutPresence
)

# ===== SCHÉMAS DE CRÉATION =====

class CycleCodevCreate(BaseModel):
    nom: str = Field(..., min_length=1, max_length=100)
    description: Optional[str] = Field(None, max_length=500)
    programme_id: int
    promotion_id: Optional[int] = None
    date_debut: date
    date_fin: date
    nombre_seances_prevues: int = Field(default=6, ge=1, le=20)
    duree_seance_minutes: int = Field(default=180, ge=60, le=480)
    animateur_principal_id: Optional[int] = None
    objectifs_cycle: Optional[str] = None

class GroupeCodevCreate(BaseModel):
    cycle_id: int
    groupe_id: int
    nom_groupe: str = Field(..., min_length=1, max_length=100)
    animateur_id: Optional[int] = None
    capacite_max: int = Field(default=12, ge=4, le=20)

class SeanceCodevCreate(BaseModel):
    groupe_id: int
    numero_seance: int = Field(..., ge=1)
    date_seance: datetime
    lieu: Optional[str] = Field(None, max_length=200)
    animateur_id: Optional[int] = None
    duree_minutes: int = Field(default=180, ge=60, le=480)
    objectifs: Optional[str] = None

class PresentationCodevCreate(BaseModel):
    seance_id: int
    candidat_id: int
    ordre_presentation: int = Field(..., ge=1)
    probleme_expose: str = Field(..., min_length=10)
    contexte: Optional[str] = None

class ContributionCodevCreate(BaseModel):
    presentation_id: int
    contributeur_id: int
    type_contribution: TypeContribution
    contenu: str = Field(..., min_length=5)
    ordre_contribution: Optional[int] = None

class MembreGroupeCodevCreate(BaseModel):
    groupe_codev_id: int
    candidat_id: int
    role_special: Optional[str] = Field(None, max_length=50)

# ===== SCHÉMAS DE MISE À JOUR =====

class CycleCodevUpdate(BaseModel):
    nom: Optional[str] = Field(None, min_length=1, max_length=100)
    description: Optional[str] = Field(None, max_length=500)
    date_debut: Optional[date] = None
    date_fin: Optional[date] = None
    nombre_seances_prevues: Optional[int] = Field(None, ge=1, le=20)
    duree_seance_minutes: Optional[int] = Field(None, ge=60, le=480)
    animateur_principal_id: Optional[int] = None
    statut: Optional[StatutCycleCodev] = None
    objectifs_cycle: Optional[str] = None

class SeanceCodevUpdate(BaseModel):
    date_seance: Optional[datetime] = None
    lieu: Optional[str] = Field(None, max_length=200)
    animateur_id: Optional[int] = None
    duree_minutes: Optional[int] = Field(None, ge=60, le=480)
    statut: Optional[StatutSeanceCodev] = None
    objectifs: Optional[str] = None
    notes_animateur: Optional[str] = None

class PresentationCodevUpdate(BaseModel):
    probleme_expose: Optional[str] = Field(None, min_length=10)
    contexte: Optional[str] = None
    solutions_proposees: Optional[str] = None
    engagement_candidat: Optional[str] = None
    delai_engagement: Optional[date] = None
    statut: Optional[StatutPresentation] = None
    notes_candidat: Optional[str] = None

class MembreGroupeCodevUpdate(BaseModel):
    statut: Optional[StatutMembreGroupe] = None
    role_special: Optional[str] = Field(None, max_length=50)
    notes_integration: Optional[str] = None

# ===== SCHÉMAS DE RÉPONSE =====

class ContributionCodevResponse(BaseModel):
    id: int
    contributeur_id: int
    contributeur_nom: Optional[str] = None
    type_contribution: TypeContribution
    contenu: str
    ordre_contribution: Optional[int]
    cree_le: datetime
    
    class Config:
        from_attributes = True

class PresentationCodevResponse(BaseModel):
    id: int
    candidat_id: int
    candidat_nom: Optional[str] = None
    ordre_presentation: int
    probleme_expose: str
    contexte: Optional[str]
    solutions_proposees: Optional[str]
    engagement_candidat: Optional[str]
    delai_engagement: Optional[date]
    statut: StatutPresentation
    notes_candidat: Optional[str]
    cree_le: datetime
    contributions: List[ContributionCodevResponse] = []
    
    class Config:
        from_attributes = True

class ParticipationSeanceResponse(BaseModel):
    id: int
    candidat_id: int
    candidat_nom: Optional[str] = None
    statut_presence: StatutPresence
    heure_arrivee: Optional[datetime]
    heure_depart: Optional[datetime]
    notes_participant: Optional[str]
    evaluation_seance: Optional[int]
    commentaires: Optional[str]
    
    class Config:
        from_attributes = True

class SeanceCodevResponse(BaseModel):
    id: int
    groupe_id: int
    groupe_nom: Optional[str] = None
    numero_seance: int
    date_seance: datetime
    lieu: Optional[str]
    animateur_id: Optional[int]
    animateur_nom: Optional[str] = None
    statut: StatutSeanceCodev
    duree_minutes: Optional[int]
    objectifs: Optional[str]
    notes_animateur: Optional[str]
    cree_le: datetime
    presentations: List[PresentationCodevResponse] = []
    participants: List[ParticipationSeanceResponse] = []
    
    class Config:
        from_attributes = True

class MembreGroupeCodevResponse(BaseModel):
    id: int
    candidat_id: int
    candidat_nom: Optional[str] = None
    candidat_entreprise: Optional[str] = None
    date_integration: datetime
    statut: StatutMembreGroupe
    role_special: Optional[str]
    notes_integration: Optional[str]
    
    class Config:
        from_attributes = True

class GroupeCodevResponse(BaseModel):
    id: int
    cycle_id: int
    groupe_id: int
    groupe_nom: Optional[str] = None
    nom_groupe: str
    animateur_id: Optional[int]
    animateur_nom: Optional[str] = None
    capacite_max: int
    statut: StatutGroupeCodev
    date_creation: datetime
    membres: List[MembreGroupeCodevResponse] = []
    
    class Config:
        from_attributes = True

class CycleCodevResponse(BaseModel):
    id: int
    nom: str
    description: Optional[str]
    programme_id: int
    programme_nom: Optional[str] = None
    promotion_id: Optional[int]
    promotion_nom: Optional[str] = None
    date_debut: date
    date_fin: date
    nombre_seances_prevues: int
    duree_seance_minutes: int
    animateur_principal_id: Optional[int]
    animateur_principal_nom: Optional[str] = None
    statut: StatutCycleCodev
    objectifs_cycle: Optional[str]
    cree_le: datetime
    groupes: List[GroupeCodevResponse] = []
    
    class Config:
        from_attributes = True

# ===== SCHÉMAS DE STATISTIQUES =====

class StatistiquesCycleCodev(BaseModel):
    cycle: CycleCodevResponse
    nb_groupes: int
    nb_membres: int
    nb_seances: int
    nb_presentations: int
    taux_realisation: float
    nb_engagements_en_cours: int
    nb_retours_faits: int

class StatistiquesGroupeCodev(BaseModel):
    groupe: GroupeCodevResponse
    nb_membres_actifs: int
    nb_seances_terminees: int
    nb_presentations_terminees: int
    taux_participation: float
    moyenne_evaluations: Optional[float]

# ===== SCHÉMAS DE PLANIFICATION =====

class PlanificationSeance(BaseModel):
    seance_id: int
    candidats_ids: List[int]
    ordre_presentations: Optional[List[int]] = None

class EngagementCandidat(BaseModel):
    presentation_id: int
    engagement: str = Field(..., min_length=10)
    delai_engagement: date

class RetourExperience(BaseModel):
    presentation_id: int
    notes_candidat: str = Field(..., min_length=10)
