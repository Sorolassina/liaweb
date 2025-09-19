# app/models/elearning.py
from sqlmodel import SQLModel, Field, Relationship
from typing import Optional, List
from datetime import datetime, timezone
from .enums import *

class RessourceElearning(SQLModel, table=True):
    """Ressource pédagogique (vidéo, document, quiz, etc.)"""
    id: Optional[int] = Field(default=None, primary_key=True)
    titre: str
    description: Optional[str] = None
    type_ressource: str = Field(max_length=20)  # "video", "document", "quiz", "lien", "audio"
    
    # URLs pour chaque type de contenu
    url_contenu_video: Optional[str] = None
    url_contenu_document: Optional[str] = None
    url_contenu_audio: Optional[str] = None
    url_contenu_lien: Optional[str] = None
    
    # Fichiers pour chaque type
    fichier_video_path: Optional[str] = None
    fichier_video_nom_original: Optional[str] = None
    fichier_document_path: Optional[str] = None
    fichier_document_nom_original: Optional[str] = None
    fichier_audio_path: Optional[str] = None
    fichier_audio_nom_original: Optional[str] = None
    
    # Champs généraux (pour compatibilité)
    url_contenu: Optional[str] = None  # URL vers le contenu (legacy)
    fichier_path: Optional[str] = None  # Chemin vers le fichier local (legacy)
    nom_fichier_original: Optional[str] = None  # Nom original du fichier uploadé (legacy)
    
    duree_minutes: Optional[int] = None  # Durée estimée en minutes
    difficulte: str = Field(default="facile", max_length=20)  # "facile", "moyen", "difficile"
    tags: Optional[str] = None  # Tags séparés par des virgules
    actif: bool = True
    ordre: int = Field(default=0)  # Ordre d'affichage
    cree_le: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    cree_par_id: Optional[int] = Field(foreign_key="user.id")
    
    # Relations
    cree_par: Optional["User"] = Relationship()
    # modules: List["ModuleElearning"] = Relationship(back_populates="ressources")
    progressions: List["ProgressionElearning"] = Relationship(back_populates="ressource")

class ModuleElearning(SQLModel, table=True):
    """Module de formation e-learning"""
    id: Optional[int] = Field(default=None, primary_key=True)
    titre: str
    description: Optional[str] = None
    programme_id: int = Field(foreign_key="programme.id")
    objectifs: Optional[str] = None  # Objectifs pédagogiques
    prerequis: Optional[str] = None  # Prérequis
    duree_totale_minutes: Optional[int] = None  # Durée totale estimée
    difficulte: str = Field(default="facile", max_length=20)
    statut: str = Field(default="brouillon", max_length=20)  # "brouillon", "actif", "archive"
    ordre: int = Field(default=0)
    actif: bool = True
    cree_le: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    cree_par_id: Optional[int] = Field(foreign_key="user.id")
    
    # Relations
    programme: "Programme" = Relationship()
    cree_par: Optional["User"] = Relationship()
    # ressources: List["RessourceElearning"] = Relationship(back_populates="modules")
    progressions: List["ProgressionElearning"] = Relationship(back_populates="module")

class ProgressionElearning(SQLModel, table=True):
    """Progression d'un candidat dans le e-learning"""
    id: Optional[int] = Field(default=None, primary_key=True)
    inscription_id: int = Field(foreign_key="inscription.id")
    module_id: int = Field(foreign_key="moduleelearning.id")
    ressource_id: int = Field(foreign_key="ressourceelearning.id")
    statut: str = Field(default="non_commence", max_length=20)  # "non_commence", "en_cours", "termine", "abandonne"
    temps_consacre_minutes: int = Field(default=0)  # Temps passé sur la ressource
    score: Optional[float] = None  # Score obtenu (pour les quiz)
    date_debut: Optional[datetime] = None
    date_fin: Optional[datetime] = None
    derniere_activite: Optional[datetime] = None
    notes: Optional[str] = None  # Notes personnelles du candidat
    cree_le: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    
    # Relations
    inscription: "Inscription" = Relationship()
    module: "ModuleElearning" = Relationship(back_populates="progressions")
    ressource: "RessourceElearning" = Relationship(back_populates="progressions")

class ObjectifElearning(SQLModel, table=True):
    """Objectifs e-learning obligatoires par programme"""
    id: Optional[int] = Field(default=None, primary_key=True)
    programme_id: int = Field(foreign_key="programme.id")
    titre: str
    description: Optional[str] = None
    temps_minimum_minutes: int  # Temps minimum obligatoire
    modules_obligatoires: Optional[str] = None  # IDs des modules obligatoires séparés par des virgules
    date_debut: Optional[datetime] = None
    date_fin: Optional[datetime] = None
    actif: bool = True
    cree_le: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    
    # Relations
    programme: "Programme" = Relationship()

class QuizElearning(SQLModel, table=True):
    """Quiz associé à une ressource"""
    id: Optional[int] = Field(default=None, primary_key=True)
    ressource_id: int = Field(foreign_key="ressourceelearning.id")
    question: str
    type_question: str = Field(max_length=20)  # "choix_multiple", "vrai_faux", "texte_libre"
    options: Optional[str] = None  # JSON des options pour choix multiple
    reponse_correcte: str
    explication: Optional[str] = None
    points: int = Field(default=1)
    ordre: int = Field(default=0)
    actif: bool = True
    
    # Relations
    ressource: "RessourceElearning" = Relationship()
    reponses: List["ReponseQuiz"] = Relationship(back_populates="quiz")

class ReponseQuiz(SQLModel, table=True):
    """Réponse d'un candidat à un quiz"""
    id: Optional[int] = Field(default=None, primary_key=True)
    inscription_id: int = Field(foreign_key="inscription.id")
    quiz_id: int = Field(foreign_key="quizelearning.id")
    reponse_donnee: str
    est_correcte: bool
    points_obtenus: int = Field(default=0)
    date_reponse: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    
    # Relations
    inscription: "Inscription" = Relationship()
    quiz: "QuizElearning" = Relationship(back_populates="reponses")

class CertificatElearning(SQLModel, table=True):
    """Certificat de completion e-learning"""
    id: Optional[int] = Field(default=None, primary_key=True)
    inscription_id: int = Field(foreign_key="inscription.id")
    module_id: Optional[int] = Field(foreign_key="moduleelearning.id")
    titre: str
    description: Optional[str] = None
    score_final: Optional[float] = None
    temps_total_minutes: int
    date_obtention: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    fichier_certificat: Optional[str] = None  # Chemin vers le PDF du certificat
    valide: bool = True
    
    # Relations
    inscription: "Inscription" = Relationship()
    module: Optional["ModuleElearning"] = Relationship()

# Table de liaison pour ModuleElearning <-> RessourceElearning
class ModuleRessource(SQLModel, table=True):
    """Table de liaison entre modules et ressources"""
    module_id: int = Field(foreign_key="moduleelearning.id", primary_key=True)
    ressource_id: int = Field(foreign_key="ressourceelearning.id", primary_key=True)
    ordre: int = Field(default=0)
    obligatoire: bool = Field(default=True)
