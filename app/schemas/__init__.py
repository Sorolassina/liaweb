"""
Schémas Pydantic pour l'application LIA Coaching
"""
# Schémas utilisateurs
from .user_schemas import UserBase, UserCreate, UserUpdate, UserResponse

# Schémas programmes
from .programme_schemas import ProgrammeBase, ProgrammeCreate, ProgrammeUpdate, ProgrammeResponse

# Schémas candidats
from .candidat_schemas import CandidatBase, CandidatCreate, CandidatUpdate, CandidatResponse

# Schémas entreprises
from .entreprise_schemas import EntrepriseBase, EntrepriseCreate, EntrepriseUpdate, EntrepriseResponse

# Schémas préinscriptions
from .preinscription_schemas import PreinscriptionBase, PreinscriptionCreate, PreinscriptionUpdate, PreinscriptionResponse

# Schémas documents
from .document_schemas import DocumentBase, DocumentCreate, DocumentResponse

# Schémas éligibilité
from .eligibilite_schemas import EligibiliteBase, EligibiliteCreate, EligibiliteResponse

# Schémas inscriptions
from .inscription_schemas import InscriptionBase, InscriptionCreate, InscriptionUpdate, InscriptionResponse

# Schémas jurys
from .jury_schemas import JuryBase, JuryCreate, JuryUpdate, JuryResponse

# Schémas décisions jury
from .decision_jury_schemas import DecisionJuryBase, DecisionJuryCreate, DecisionJuryResponse

# Schémas authentification
from .auth_schemas import LoginRequest, TokenResponse

# Schémas statistiques
from .statistiques_schemas import StatistiquesResponse

# Schémas recherche et filtres
from .recherche_schemas import CandidatFiltres, PaginationParams, PaginatedResponse

# Schémas pipelines
from .pipeline_schemas import EtapePipelineCreate, EtapePipelineUpdate, AvancementEtapeCreate

# Schémas codéveloppement
from .codev import (
    CycleCodevCreate, CycleCodevUpdate, CycleCodevResponse,
    GroupeCodevCreate, GroupeCodevResponse,
    SeanceCodevCreate, SeanceCodevUpdate, SeanceCodevResponse,
    PresentationCodevCreate, PresentationCodevUpdate, PresentationCodevResponse,
    ContributionCodevCreate, ContributionCodevResponse,
    MembreGroupeCodevCreate, MembreGroupeCodevUpdate, MembreGroupeCodevResponse,
    ParticipationSeanceResponse,
    StatistiquesCycleCodev, StatistiquesGroupeCodev,
    PlanificationSeance, EngagementCandidat, RetourExperience
)

# Schémas e-learning
from .elearning import (
    RessourceElearningCreate, RessourceElearningUpdate, RessourceElearningResponse,
    ModuleElearningCreate, ModuleElearningUpdate, ModuleElearningResponse,
    ProgressionElearningCreate, ProgressionElearningUpdate, ProgressionElearningResponse,
    ObjectifElearningCreate, ObjectifElearningUpdate, ObjectifElearningResponse,
    QuizElearningCreate, QuizElearningUpdate, QuizElearningResponse,
    ReponseQuizCreate, ReponseQuizResponse,
    CertificatElearningCreate, CertificatElearningResponse,
    StatistiquesElearningCandidat, StatistiquesElearningProgramme,
    RapportProgressionElearning
)

__all__ = [
    # Utilisateurs
    "UserBase", "UserCreate", "UserUpdate", "UserResponse",
    
    # Programmes
    "ProgrammeBase", "ProgrammeCreate", "ProgrammeUpdate", "ProgrammeResponse",
    
    # Candidats
    "CandidatBase", "CandidatCreate", "CandidatUpdate", "CandidatResponse",
    
    # Entreprises
    "EntrepriseBase", "EntrepriseCreate", "EntrepriseUpdate", "EntrepriseResponse",
    
    # Préinscriptions
    "PreinscriptionBase", "PreinscriptionCreate", "PreinscriptionUpdate", "PreinscriptionResponse",
    
    # Documents
    "DocumentBase", "DocumentCreate", "DocumentResponse",
    
    # Éligibilité
    "EligibiliteBase", "EligibiliteCreate", "EligibiliteResponse",
    
    # Inscriptions
    "InscriptionBase", "InscriptionCreate", "InscriptionUpdate", "InscriptionResponse",
    
    # Jurys
    "JuryBase", "JuryCreate", "JuryUpdate", "JuryResponse",
    
    # Décisions jury
    "DecisionJuryBase", "DecisionJuryCreate", "DecisionJuryResponse",
    
    # Authentification
    "LoginRequest", "TokenResponse",
    
    # Statistiques
    "StatistiquesResponse",
    
    # Recherche et filtres
    "CandidatFiltres", "PaginationParams", "PaginatedResponse",
    
    # Pipelines
    "EtapePipelineCreate", "EtapePipelineUpdate", "AvancementEtapeCreate",
    
    # Codéveloppement
    "CycleCodevCreate", "CycleCodevUpdate", "CycleCodevResponse",
    "GroupeCodevCreate", "GroupeCodevResponse",
    "SeanceCodevCreate", "SeanceCodevUpdate", "SeanceCodevResponse",
    "PresentationCodevCreate", "PresentationCodevUpdate", "PresentationCodevResponse",
    "ContributionCodevCreate", "ContributionCodevResponse",
    "MembreGroupeCodevCreate", "MembreGroupeCodevUpdate", "MembreGroupeCodevResponse",
    "ParticipationSeanceResponse",
    "StatistiquesCycleCodev", "StatistiquesGroupeCodev",
    "PlanificationSeance", "EngagementCandidat", "RetourExperience",
    
    # E-learning
    "RessourceElearningCreate", "RessourceElearningUpdate", "RessourceElearningResponse",
    "ModuleElearningCreate", "ModuleElearningUpdate", "ModuleElearningResponse",
    "ProgressionElearningCreate", "ProgressionElearningUpdate", "ProgressionElearningResponse",
    "ObjectifElearningCreate", "ObjectifElearningUpdate", "ObjectifElearningResponse",
    "QuizElearningCreate", "QuizElearningUpdate", "QuizElearningResponse",
    "ReponseQuizCreate", "ReponseQuizResponse",
    "CertificatElearningCreate", "CertificatElearningResponse",
    "StatistiquesElearningCandidat", "StatistiquesElearningProgramme",
    "RapportProgressionElearning",
]
