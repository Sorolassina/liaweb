"""
Services de l'application LIA Coaching
"""
from .user_service import UserService
from .programme_service import ProgrammeService
from .candidat_service import CandidatService
from .entreprise_service import EntrepriseService
# from .preinscription_service import PreinscriptionService  # Non utilisé
from .inscription_service import InscriptionService
from .jury_service import JuryService
from .jury_decision_service import JuryDecisionService
from .candidat_email_service import CandidatEmailService
from .statistiques_service import StatistiquesService
from .pipeline_service import PipelineService

__all__ = [
    "UserService",
    "ProgrammeService",
    "CandidatService", 
    "EntrepriseService",
    # "PreinscriptionService",  # Non utilisé
    "InscriptionService",
    "JuryService",
    "JuryDecisionService",
    "CandidatEmailService",
    "StatistiquesService",
    "PipelineService"
]
