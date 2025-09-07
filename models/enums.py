# app/models/enums.py
from enum import Enum

class StatutDossier(str, Enum):
    BROUILLON = "brouillon"
    SOUMIS = "soumis"
    EN_EXAMEN = "en_examen"
    A_COMPLETER = "a_completer"
    VALIDE = "valide"
    EN_ATTENTE = "en_attente"
    REORIENTE = "reoriente"
    REFUSE = "refuse"
    CLOTURE = "cloture"

class DecisionJury(str, Enum):
    VALIDE = "valide"
    EN_ATTENTE = "en_attente"
    REORIENTE = "reoriente"
    REFUSE = "refuse"

class StatutCandidat(str, Enum):
    EN_ATTENTE = "EN_ATTENTE"
    VALIDE = "VALIDE"
    REORIENTE = "REORIENTE"
    REJETE = "REJETE"

class StatutEtape(str, Enum):
    A_FAIRE = "a_faire"
    EN_COURS = "en_cours"
    TERMINE = "termine"
    IGNORE = "ignore"

class UserRole(str, Enum):
    DIRECTEUR_GENERAL = "directeur_general"
    DIRECTEUR_TECHNIQUE = "directeur_technique"
    RESPONSABLE_PROGRAMME = "responsable_programme"
    CONSEILLER = "conseiller"
    COORDINATEUR = "coordinateur"
    FORMATEUR = "formateur"
    EVALUATEUR = "evaluateur"
    ACCOMPAGNATEUR = "accompagnateur"
    ADMINISTRATEUR = "administrateur"
    DRH = "drh"
    RESPONSABLE_STRUCTURE = "responsable_structure"
    COACH_EXTERNE = "coach_externe"
    JURY_EXTERNE = "jury_externe"
    CANDIDAT = "candidat"
    RESPONSABLE_COMMUNICATION = "responsable_communication"
    ASSISTANT_COMMUNICATION = "assistant_communication"


class TypeUtilisateur(str, Enum):
    INTERNE = "interne"
    EXTERNE = "externe"

class StatutHandicap(str, Enum):
    AUCUN = "aucun"
    MOBILITE = "mobilite"
    VISUEL = "visuel"
    AUDITIF = "auditif"
    COGNITIF = "cognitif"
    AUTRE = "autre"

class TypeRDV(str, Enum):
    ENTRETIEN = "entretien"
    SUIVI = "suivi"
    COACHING = "coaching"
    AUTRE = "autre"

class StatutRDV(str, Enum):
    PLANIFIE = "planifie"
    TERMINE = "termine"
    ANNULE = "annule"

class TypeSession(str, Enum):
    SEMINAIRE = "seminaire"
    CODEV = "codev"
    WEBINAIRE = "webinaire"

class StatutPresence(str, Enum):
    ABSENT = "absent"
    PRESENT = "present"
    EXCUSE = "excuse"

class DecisionJury(str, Enum):
    VALIDE = "VALIDE"
    REORIENTE = "REORIENTE"
    REJETE = "REJETE"
    EN_ATTENTE = "EN_ATTENTE"

class TypeDocument(str, Enum):
    CNI = "CNI"                        # Carte d'identité / Passeport
    KBIS = "KBIS"                      # Extrait Kbis
    JUSTIFICATIF_DOMICILE = "JUSTIFICATIF_DOMICILE"
    RIB = "RIB"
    CV = "CV"
    DIPLOME = "DIPLOME"
    ATTESTATION = "ATTESTATION"
    AUTRE = "AUTRE"