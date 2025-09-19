# app/schemas/elearning.py
from pydantic import BaseModel, Field
from typing import Optional, List, Any
from datetime import datetime

# Schémas pour les fichiers uploadés
class FileUploadInfo(BaseModel):
    original_filename: str
    saved_filename: str
    file_path: str
    relative_path: str
    size_bytes: int
    size_mb: float
    upload_date: str
    module_id: Optional[int] = None

# Schémas pour les ressources
class RessourceElearningBase(BaseModel):
    titre: str
    description: Optional[str] = None
    type_ressource: str = Field(..., pattern="^(video|document|quiz|lien|audio)$")
    
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
    url_contenu: Optional[str] = None
    fichier_path: Optional[str] = None
    nom_fichier_original: Optional[str] = None
    
    duree_minutes: Optional[int] = None
    difficulte: str = Field(default="facile", pattern="^(facile|moyen|difficile)$")
    tags: Optional[str] = None
    ordre: int = Field(default=0)
    actif: bool = True

class RessourceElearningCreate(RessourceElearningBase):
    pass

class RessourceElearningUpdate(BaseModel):
    titre: Optional[str] = None
    description: Optional[str] = None
    type_ressource: Optional[str] = Field(None, pattern="^(video|document|quiz|lien|audio)$")
    
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
    url_contenu: Optional[str] = None
    fichier_path: Optional[str] = None
    
    duree_minutes: Optional[int] = None
    difficulte: Optional[str] = Field(None, pattern="^(facile|moyen|difficile)$")
    tags: Optional[str] = None
    ordre: Optional[int] = None
    actif: Optional[bool] = None

class RessourceElearningResponse(RessourceElearningBase):
    id: int
    actif: bool
    cree_le: datetime
    cree_par: Optional[Any] = None
    
    class Config:
        from_attributes = True

# Schémas pour les modules
class ModuleElearningBase(BaseModel):
    titre: str
    description: Optional[str] = None
    programme_id: int
    objectifs: Optional[str] = None
    prerequis: Optional[str] = None
    duree_totale_minutes: Optional[int] = None
    difficulte: str = Field(default="facile", pattern="^(facile|moyen|difficile)$")
    ordre: int = Field(default=0)

class ModuleElearningCreate(ModuleElearningBase):
    pass

class ModuleElearningUpdate(BaseModel):
    titre: Optional[str] = None
    description: Optional[str] = None
    objectifs: Optional[str] = None
    prerequis: Optional[str] = None
    duree_totale_minutes: Optional[int] = None
    difficulte: Optional[str] = Field(None, pattern="^(facile|moyen|difficile)$")
    ordre: Optional[int] = None
    statut: Optional[str] = Field(None, pattern="^(brouillon|actif|archive)$")
    actif: Optional[bool] = None

class ModuleElearningResponse(ModuleElearningBase):
    id: int
    statut: str
    actif: bool
    cree_le: datetime
    programme: Any
    cree_par: Optional[Any] = None
    ressources: List[RessourceElearningResponse] = []
    
    class Config:
        from_attributes = True

# Schémas pour la progression
class ProgressionElearningBase(BaseModel):
    inscription_id: int
    module_id: int
    ressource_id: int
    temps_consacre_minutes: int = Field(default=0)
    notes: Optional[str] = None

class ProgressionElearningCreate(ProgressionElearningBase):
    pass

class ProgressionElearningUpdate(BaseModel):
    statut: Optional[str] = Field(None, pattern="^(non_commence|en_cours|termine|abandonne)$")
    temps_consacre_minutes: Optional[int] = None
    score: Optional[float] = None
    date_fin: Optional[datetime] = None
    notes: Optional[str] = None

class ProgressionElearningResponse(ProgressionElearningBase):
    id: int
    statut: str
    score: Optional[float] = None
    date_debut: Optional[datetime] = None
    date_fin: Optional[datetime] = None
    derniere_activite: Optional[datetime] = None
    cree_le: datetime
    inscription: Any
    module: ModuleElearningResponse
    ressource: RessourceElearningResponse
    
    class Config:
        from_attributes = True

# Schémas pour les objectifs
class ObjectifElearningBase(BaseModel):
    programme_id: int
    titre: str
    description: Optional[str] = None
    temps_minimum_minutes: int
    modules_obligatoires: Optional[str] = None
    date_debut: Optional[datetime] = None
    date_fin: Optional[datetime] = None

class ObjectifElearningCreate(ObjectifElearningBase):
    pass

class ObjectifElearningUpdate(BaseModel):
    titre: Optional[str] = None
    description: Optional[str] = None
    temps_minimum_minutes: Optional[int] = None
    modules_obligatoires: Optional[str] = None
    date_debut: Optional[datetime] = None
    date_fin: Optional[datetime] = None
    actif: Optional[bool] = None

class ObjectifElearningResponse(ObjectifElearningBase):
    id: int
    actif: bool
    cree_le: datetime
    programme: Any
    
    class Config:
        from_attributes = True

# Schémas pour les quiz
class QuizElearningBase(BaseModel):
    ressource_id: int
    question: str
    type_question: str = Field(..., pattern="^(choix_multiple|vrai_faux|texte_libre)$")
    options: Optional[str] = None
    reponse_correcte: str
    explication: Optional[str] = None
    points: int = Field(default=1)
    ordre: int = Field(default=0)

class QuizElearningCreate(QuizElearningBase):
    pass

class QuizElearningUpdate(BaseModel):
    question: Optional[str] = None
    type_question: Optional[str] = Field(None, pattern="^(choix_multiple|vrai_faux|texte_libre)$")
    options: Optional[str] = None
    reponse_correcte: Optional[str] = None
    explication: Optional[str] = None
    points: Optional[int] = None
    ordre: Optional[int] = None
    actif: Optional[bool] = None

class QuizElearningResponse(QuizElearningBase):
    id: int
    actif: bool
    ressource: RessourceElearningResponse
    
    class Config:
        from_attributes = True

# Schémas pour les réponses de quiz
class ReponseQuizBase(BaseModel):
    inscription_id: int
    quiz_id: int
    reponse_donnee: str

class ReponseQuizCreate(ReponseQuizBase):
    pass

class ReponseQuizResponse(ReponseQuizBase):
    id: int
    est_correcte: bool
    points_obtenus: int
    date_reponse: datetime
    inscription: Any
    quiz: QuizElearningResponse
    
    class Config:
        from_attributes = True

# Schémas pour les certificats
class CertificatElearningBase(BaseModel):
    inscription_id: int
    module_id: Optional[int] = None
    titre: str
    description: Optional[str] = None
    score_final: Optional[float] = None
    temps_total_minutes: int

class CertificatElearningCreate(CertificatElearningBase):
    pass

class CertificatElearningResponse(CertificatElearningBase):
    id: int
    date_obtention: datetime
    fichier_certificat: Optional[str] = None
    valide: bool
    inscription: Any
    module: Optional[ModuleElearningResponse] = None
    
    class Config:
        from_attributes = True

# Schémas pour les statistiques et rapports
class StatistiquesElearningCandidat(BaseModel):
    inscription_id: int
    candidat_nom: str
    programme_nom: str
    temps_total_minutes: int
    modules_termines: int
    modules_total: int
    score_moyen: Optional[float] = None
    derniere_activite: Optional[datetime] = None
    objectif_atteint: bool

class StatistiquesElearningProgramme(BaseModel):
    programme_id: int
    programme_nom: str
    candidats_inscrits: int
    candidats_actifs: int
    temps_moyen_minutes: float
    taux_completion: float
    modules_populaires: List[dict]

class RapportProgressionElearning(BaseModel):
    inscription_id: int
    candidat: Any
    modules: List[dict]  # Détail de chaque module avec progression
    temps_total: int
    score_global: Optional[float] = None
    certificats: List[CertificatElearningResponse] = []
