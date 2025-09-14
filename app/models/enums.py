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
    EN_COURS = "en_cours"
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

class GroupeCodev(str, Enum):
    """Groupes de codéveloppement"""
    GROUPE_1 = "GROUPE_1"
    GROUPE_2 = "GROUPE_2"
    GROUPE_3 = "GROUPE_3"
    GROUPE_4 = "GROUPE_4"
    GROUPE_5 = "GROUPE_5"
    GROUPE_6 = "GROUPE_6"
    GROUPE_7 = "GROUPE_7"
    GROUPE_8 = "GROUPE_8"
    GROUPE_9 = "GROUPE_9"
    GROUPE_10 = "GROUPE_10"

class TypePromotion(str, Enum):
    """Types de promotions"""
    PROMOTION_2024_A = "PROMOTION_2024_A"
    PROMOTION_2024_B = "PROMOTION_2024_B"
    PROMOTION_2024_C = "PROMOTION_2024_C"
    PROMOTION_2025_A = "PROMOTION_2025_A"
    PROMOTION_2025_B = "PROMOTION_2025_B"
    PROMOTION_2025_C = "PROMOTION_2025_C"
    PROMOTION_2026_A = "PROMOTION_2026_A"
    PROMOTION_2026_B = "PROMOTION_2026_B"
    PROMOTION_2026_C = "PROMOTION_2026_C"

class TypeDocument(str, Enum):
    CNI = "CNI"                        # Carte d'identité / Passeport
    KBIS = "KBIS"                      # Extrait Kbis
    JUSTIFICATIF_DOMICILE = "JUSTIFICATIF_DOMICILE"
    RIB = "RIB"
    CV = "CV"
    DIPLOME = "DIPLOME"
    ATTESTATION = "ATTESTATION"
    AUTRE = "AUTRE"
    # Nouveaux types pour les documents SIRET
    COMPTE_ANNUEL = "COMPTE_ANNUEL"    # Comptes annuels
    STATUTS = "STATUTS"                # Statuts de l'entreprise
    EXTRACT_KBIS = "EXTRACT_KBIS"     # Extrait d'immatriculation
    PUBLICATION_BODACC = "PUBLICATION_BODACC"  # Publications BODACC

# Enums pour les séminaires
class StatutSeminaire(str, Enum):
    PLANIFIE = "planifie"
    EN_COURS = "en_cours"
    TERMINE = "termine"
    ANNULE = "annule"
    REPORTE = "reporte"

class TypeInvitation(str, Enum):
    INDIVIDUELLE = "individuelle"      # Invitation à un candidat spécifique
    PROMOTION = "promotion"            # Invitation à toute une promotion
    PROGRAMME = "programme"            # Invitation à tous les candidats du programme

class MethodeSignature(str, Enum):
    MANUEL = "manuel"                  # Signature sur papier/liste
    DIGITAL = "digital"                # Signature digitale sur écran
    QR_CODE = "qr_code"                # Signature via QR code
    EMAIL = "email"                    # Confirmation par email