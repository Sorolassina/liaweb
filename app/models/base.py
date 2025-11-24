# app/models/base.py
from sqlmodel import SQLModel, Field, Relationship
from typing import Optional, List
from datetime import date, datetime, timezone
from .password_recovery import PasswordRecoveryCode
from .preinscription import Preinscription, Eligibilite
from .jury import Jury, MembreJury, DecisionJuryTable, DecisionJuryCandidat
from .rendez_vous import RendezVous, EmargementRDV
from .enums import *
# Import des modèles de message pour les relations (éviter import circulaire)
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from .message import Conversation, Message

class User(SQLModel, table=True):
    __tablename__ = "user"
    
    """Utilisateur du système"""
    id: Optional[int] = Field(default=None, primary_key=True)
    email: str = Field(unique=True, index=True)
    nom_complet: str
    telephone: Optional[str] = None
    mot_de_passe_hash: str
    role: str  # Utilise la valeur string de l'enum UserRole
    type_utilisateur: TypeUtilisateur = TypeUtilisateur.INTERNE
    actif: bool = True
    derniere_connexion: Optional[datetime] = None
    photo_profil: Optional[str] = None  # Chemin vers la photo de profil
    programme_id: Optional[int] = Field(default=None, foreign_key="programme.id")
    cree_le: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    
    # Relations
    programmes_utilisateurs: List["ProgrammeUtilisateur"] = Relationship(back_populates="utilisateur")
    programme: Optional["Programme"] = Relationship(
        back_populates="utilisateurs_directs",
        sa_relationship_kwargs={
            "primaryjoin": "User.programme_id == Programme.id",
            "foreign_keys": "User.programme_id"
        }
    )
   
    documents_deposes: List["Document"] = Relationship(back_populates="depose_par")
    conversations_user1: List["Conversation"] = Relationship(
        sa_relationship_kwargs={"foreign_keys": "[Conversation.user1_id]"}
    )
    conversations_user2: List["Conversation"] = Relationship(
        sa_relationship_kwargs={"foreign_keys": "[Conversation.user2_id]"}
    )
    messages_envoyes: List["Message"] = Relationship(
        sa_relationship_kwargs={"foreign_keys": "[Message.sender_id]"}
    )

class Programme(SQLModel, table=True):
    __tablename__ = "programme"
    
    """Programme de coaching (ACD, ACI, ACT)"""
    id: Optional[int] = Field(default=None, primary_key=True)
    code: str = Field(unique=True, index=True)  # "ACD", "ACI", "ACT"
    nom: str
    objectif: Optional[str] = None
    date_debut: Optional[date] = None
    date_fin: Optional[date] = None
    actif: bool = True
    responsable_id: Optional[int] = Field(foreign_key="user.id")

    # Objectifs (nouveaux champs)
    objectif_total: Optional[int] = None            # cible de volume (inscriptions)
    cible_qpv_pct: Optional[float] = None           # % à atteindre
    cible_femmes_pct: Optional[float] = None        # % à atteindre
    
    # Seuils d'éligibilité
    ca_seuil_min: Optional[float] = None
    ca_seuil_max: Optional[float] = None
    anciennete_min_annees: Optional[int] = None
    anciennete_max_annees: Optional[int] = None
    
    # Relations
    responsable: Optional[User] = Relationship(
        sa_relationship_kwargs={
            "primaryjoin": "Programme.responsable_id == User.id",
            "foreign_keys": "Programme.responsable_id"
        }
    )
    utilisateurs: List["ProgrammeUtilisateur"] = Relationship(back_populates="programme")
    utilisateurs_directs: List["User"] = Relationship(
        back_populates="programme",
        sa_relationship_kwargs={
            "primaryjoin": "User.programme_id == Programme.id",
            "foreign_keys": "User.programme_id"
        }
    )
    promotions: List["Promotion"] = Relationship(back_populates="programme")
    preinscriptions: List["Preinscription"] = Relationship(back_populates="programme")
    # NOTE: Le modèle Inscription a été supprimé. Les candidats validés sont identifiés par leur statut dans la table Candidat.
    # inscriptions: List["Inscription"] = Relationship(back_populates="programme")
    etapes_pipeline: List["EtapePipeline"] = Relationship(back_populates="programme")
    seminaires: List["Seminaire"] = Relationship(back_populates="programme")
    events: List["Event"] = Relationship(back_populates="programme")
    sessions_programme: List["SessionProgramme"] = Relationship(back_populates="programme")

class ProgrammeUtilisateur(SQLModel, table=True):
    __tablename__ = "programme_utilisateur"
    
    """Affectation d'un utilisateur à un programme avec un rôle spécifique"""
    id: Optional[int] = Field(default=None, primary_key=True)
    programme_id: int = Field(foreign_key="programme.id")
    utilisateur_id: int = Field(foreign_key="user.id")
    role_programme: str  # Utilise la valeur string de l'enum UserRole
    actif: bool = True
    date_debut: Optional[date] = None
    date_fin: Optional[date] = None
    cree_le: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    
    # Relations
    programme: "Programme" = Relationship(back_populates="utilisateurs")
    utilisateur: "User" = Relationship(back_populates="programmes_utilisateurs")

class Promotion(SQLModel, table=True):
    __tablename__ = "promotion"
    
    """Promotion d'un programme"""
    id: Optional[int] = Field(default=None, primary_key=True)
    programme_id: int = Field(foreign_key="programme.id")
    libelle: str
    capacite: Optional[int] = None
    date_debut: Optional[date] = None
    date_fin: Optional[date] = None
    actif: bool = True
    
    # Relations
    programme: "Programme" = Relationship(back_populates="promotions")
    # NOTE: Le modèle Inscription a été supprimé. Les candidats validés sont identifiés par leur statut dans la table Candidat.
    # inscriptions: List["Inscription"] = Relationship(back_populates="promotion")

class Candidat(SQLModel, table=True):
    __tablename__ = "candidat"
    
    """Candidat au programme"""
    id: Optional[int] = Field(default=None, primary_key=True)
    civilite: Optional[str] = None
    nom: str
    prenom: str
    date_naissance: Optional[date] = None
    email: str = Field(unique=True, index=True)
    telephone: Optional[str] = None
    adresse_personnelle: Optional[str] = None
    niveau_etudes: Optional[str] = None
    secteur_activite: Optional[str] = None
    photo_profil: Optional[str] = None  # Chemin vers la photo de profil
    # Géocodage (nouveaux champs)
    lat: Optional[float] = Field(default=None, index=True)
    lng: Optional[float] = Field(default=None, index=True)
    
    # Gestion handicap
    handicap: bool = False
    type_handicap: Optional[StatutHandicap] = None
    besoins_accommodation: Optional[str] = None
    
    # Statut du candidat (décision du jury)
    statut: DecisionJury = Field(default=DecisionJury.EN_ATTENTE)
    
    # Relations
    entreprise: Optional["Entreprise"] = Relationship(back_populates="candidat")
    preinscriptions: List["Preinscription"] = Relationship(back_populates="candidat")
    # NOTE: Le modèle Inscription a été supprimé. Les candidats validés sont identifiés par leur statut dans la table Candidat.
    # inscriptions: List["Inscription"] = Relationship(back_populates="candidat")
    documents: List["Document"] = Relationship(back_populates="candidat")
    emargements_rdv: List["EmargementRDV"] = Relationship(back_populates="candidat")
    reorientations: List["ReorientationCandidat"] = Relationship(back_populates="candidat")
    avancement_etapes: List["AvancementEtape"] = Relationship()
    actions_handicap: List["ActionHandicap"] = Relationship()
    session_participants: List["SessionParticipant"] = Relationship()
    suivi_mensuel: List["SuiviMensuel"] = Relationship()
    decisions_jury: List["DecisionJuryTable"] = Relationship()
    progressions_elearning: List["ProgressionElearning"] = Relationship()
    reponses_quiz: List["ReponseQuiz"] = Relationship()
    certificats_elearning: List["CertificatElearning"] = Relationship()
    invitations_event: List["InvitationEvent"] = Relationship(back_populates="candidat")
    presences_event: List["PresenceEvent"] = Relationship(back_populates="candidat")
    presentations_codev: List["PresentationCodev"] = Relationship()
    contributions_codev: List["ContributionCodev"] = Relationship()
    participations_seance: List["ParticipationSeance"] = Relationship()
    membres_groupes_codev: List["MembreGroupeCodev"] = Relationship()
    invitations_seminaire: List["InvitationSeminaire"] = Relationship()
    presences_seminaire: List["PresenceSeminaire"] = Relationship()
    rendus_livrables: List["RenduLivrable"] = Relationship()

class Entreprise(SQLModel, table=True):
    __tablename__ = "entreprise"
    
    """Entreprise du candidat"""
    id: Optional[int] = Field(default=None, primary_key=True)
    candidat_id: int = Field(foreign_key="candidat.id")
    siret: Optional[str] = None
    siren: Optional[str] = None
    raison_sociale: Optional[str] = None
    code_naf: Optional[str] = None
    date_creation: Optional[date] = None
    adresse: Optional[str] = None
    qpv: Optional[bool] = None
    chiffre_affaires: Optional[str] = None  # Intervalle de CA (ex: "10 000 - 50 000 €")
    nombre_points_vente: Optional[int] = None
    specialite_culinaire: Optional[str] = None
    nom_concept: Optional[str] = None
    lien_reseaux_sociaux: Optional[str] = None
    site_internet: Optional[str] = None
    territoire: Optional[str] = None

    # Géocodage (nouveaux champs)
    lat: Optional[float] = Field(default=None, index=True)
    lng: Optional[float] = Field(default=None, index=True)
    
    # Relations
    candidat: "Candidat" = Relationship(back_populates="entreprise")

# Preinscription et Eligibilite déplacés vers preinscription.py

class Document(SQLModel, table=True):
    __tablename__ = "document"
    
    """Document joint par un candidat"""
    id: Optional[int] = Field(default=None, primary_key=True)
    candidat_id: int = Field(foreign_key="candidat.id")
    type_document: TypeDocument
    titre: Optional[str] = None
    nom_fichier: str
    chemin_fichier: str
    mimetype: Optional[str] = None
    taille_octets: Optional[int] = None
    depose_par_id: Optional[int] = Field(foreign_key="user.id")
    depose_le: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    
    # Relations
    candidat: "Candidat" = Relationship(back_populates="documents")
    depose_par: Optional["User"] = Relationship(back_populates="documents_deposes")



class EtapePipeline(SQLModel, table=True):
    __tablename__ = "etape_pipeline"
    
    """Étape du pipeline de formation"""
    id: Optional[int] = Field(default=None, primary_key=True)
    programme_id: int = Field(foreign_key="programme.id")
    code: str          # "webinaire", "e_learning_n1", "seminaire_1", etc.
    libelle: str
    ordre: int
    active: bool = True
    type_etape: Optional[str] = None  # "formation", "evaluation", "accompagnement"
    
    # Relations
    programme: "Programme" = Relationship(back_populates="etapes_pipeline")
    avancements: List["AvancementEtape"] = Relationship(back_populates="etape")

class AvancementEtape(SQLModel, table=True):
    __tablename__ = "avancement_etape"
    
    """Avancement d'un candidat dans une étape du pipeline"""
    id: Optional[int] = Field(default=None, primary_key=True)
    candidat_id: int = Field(foreign_key="candidat.id")
    etape_id: int = Field(foreign_key="etape_pipeline.id")
    statut: StatutEtape = StatutEtape.A_FAIRE
    debut_le: Optional[datetime] = None
    termine_le: Optional[datetime] = None
    notes: Optional[str] = None
    
    # Relations
    candidat: "Candidat" = Relationship()
    etape: EtapePipeline = Relationship(back_populates="avancements")

class ActionHandicap(SQLModel, table=True):
    __tablename__ = "action_handicap"
    
    """Actions d'accommodation pour handicap"""
    id: Optional[int] = Field(default=None, primary_key=True)
    candidat_id: int = Field(foreign_key="candidat.id")
    type_action: str  # "formation", "accompagnement", "materiel", etc.
    description: str
    responsable_id: Optional[int] = Field(foreign_key="user.id")
    date_echeance: Optional[date] = None
    statut: str = "a_faire"  # "a_faire", "en_cours", "termine"
    cree_le: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    
    # Relations
    candidat: "Candidat" = Relationship()
    responsable: Optional["User"] = Relationship()

# RendezVous déplacé vers rendez_vous.py

class SessionProgramme(SQLModel, table=True):
    __tablename__ = "session_programme"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    programme_id: int = Field(foreign_key="programme.id", index=True)
    type_session: TypeSession
    titre: str
    debut: datetime
    fin: Optional[datetime] = None
    lieu: Optional[str] = None
    visioconf_url: Optional[str] = None
    capacite: Optional[int] = None
    cree_le: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    programme: Programme = Relationship(back_populates="sessions_programme")
    participants: List["SessionParticipant"] = Relationship(back_populates="session")

class SessionParticipant(SQLModel, table=True):
    __tablename__ = "session_participant"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    session_id: int = Field(foreign_key="session_programme.id", index=True)
    candidat_id: int = Field(foreign_key="candidat.id", index=True)
    presence: StatutPresence = StatutPresence.ABSENT
    note: Optional[str] = None

    session: "SessionProgramme" = Relationship(back_populates="participants")
    candidat: "Candidat" = Relationship()

class SuiviMensuel(SQLModel, table=True):
    __tablename__ = "suivi_mensuel"
    
    """Suivi mensuel des candidats avec métriques business"""
    id: Optional[int] = Field(default=None, primary_key=True)
    candidat_id: int = Field(foreign_key="candidat.id", index=True)
    mois: date                                    # par convention, jour = 1er du mois
    
    # Métriques business principales
    chiffre_affaires_actuel: Optional[float] = None      # CA en euros
    
    # Évolution des employés
    nb_stagiaires: Optional[int] = None
    nb_alternants: Optional[int] = None
    nb_cdd: Optional[int] = None
    nb_cdi: Optional[int] = None
    
    # Subventions et financements
    montant_subventions_obtenues: Optional[float] = None  # en euros
    organismes_financeurs: Optional[str] = None           # liste des organismes
    
    # Dettes
    montant_dettes_effectuees: Optional[float] = None      # dettes payées
    montant_dettes_encours: Optional[float] = None       # dettes en cours
    montant_dettes_envisagees: Optional[float] = None     # dettes prévues
    
    # Levée de fonds equity
    montant_equity_effectue: Optional[float] = None       # levée réalisée
    montant_equity_encours: Optional[float] = None        # levée en cours
    
    # Informations entreprise
    statut_juridique: Optional[str] = None                # SAS, SARL, etc.
    adresse_entreprise: Optional[str] = None             # nouvelle adresse si changement
    
    # Situation socioprofessionnelle
    situation_socioprofessionnelle: Optional[str] = None # statut du candidat
    
    # Métriques générales (conservées pour compatibilité)
    score_objectifs: Optional[float] = None             # 0..100 (score global)
    commentaire: Optional[str] = None                    # commentaires libres
    
    # Métadonnées
    cree_le: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    modifie_le: Optional[datetime] = None

    candidat: "Candidat" = Relationship()

class Partenaire(SQLModel, table=True):
    __tablename__ = "partenaire"
    
    """Partenaires pour la réorientation des candidats"""
    id: Optional[int] = Field(default=None, primary_key=True)
    nom: str = Field(index=True)
    description: Optional[str] = None
    email: Optional[str] = None
    telephone: Optional[str] = None
    adresse: Optional[str] = None
    site_web: Optional[str] = None
    specialites: Optional[str] = None  # JSON string des spécialités
    actif: bool = Field(default=True)
    cree_le: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    
    # Relations
    reorientations: List["ReorientationCandidat"] = Relationship(back_populates="partenaire")

# DecisionJuryCandidat déplacé vers jury.py

class ReorientationCandidat(SQLModel, table=True):
    __tablename__ = "reorientation_candidat"
    
    """Historique des réorientations"""
    id: Optional[int] = Field(default=None, primary_key=True)
    candidat_id: int = Field(foreign_key="candidat.id", index=True)
    partenaire_id: int = Field(foreign_key="partenaire.id", index=True)
    decision_jury_id: int = Field(foreign_key="decision_jury_candidat.id", index=True)
    motif: Optional[str] = None
    mail_envoye: bool = Field(default=False)
    date_reorientation: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    
    # Relations
    candidat: "Candidat" = Relationship(back_populates="reorientations")
    partenaire: "Partenaire" = Relationship(back_populates="reorientations")
    decision_jury: "DecisionJuryCandidat" = Relationship(back_populates="reorientations")

class Groupe(SQLModel, table=True):
    __tablename__ = "groupe"
    
    """Groupes de codéveloppement"""
    id: Optional[int] = Field(default=None, primary_key=True)
    nom: str = Field(index=True, max_length=100)
    description: Optional[str] = Field(default=None, max_length=500)
    capacite_max: Optional[int] = Field(default=None)
    actif: bool = Field(default=True)
    date_creation: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    date_modification: Optional[datetime] = Field(default=None)
    
    # Relations pour le codev
    seances: List["SeanceCodev"] = Relationship(back_populates="groupe")
    groupes_codev: List["GroupeCodev"] = Relationship(back_populates="groupe")

# EmargementRDV déplacé vers rendez_vous.py