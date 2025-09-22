# app/models/base.py
from sqlmodel import SQLModel, Field, Relationship
from typing import Optional, List
from datetime import date, datetime, timezone
from .password_recovery import PasswordRecoveryCode
from .enums import *

class User(SQLModel, table=True):
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
    cree_le: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    
    # Relations
    programmes_responsable: List["Programme"] = Relationship(back_populates="responsable")
    programmes_utilisateurs: List["ProgrammeUtilisateur"] = Relationship(back_populates="utilisateur")
    inscriptions_conseiller: List["Inscription"] = Relationship(
        back_populates="conseiller",
        sa_relationship_kwargs={"foreign_keys": "[Inscription.conseiller_id]"}
    )
    inscriptions_referent: List["Inscription"] = Relationship(
        back_populates="referent", 
        sa_relationship_kwargs={"foreign_keys": "[Inscription.referent_id]"}
    )
    documents_deposes: List["Document"] = Relationship(back_populates="depose_par")

class Programme(SQLModel, table=True):
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
    
    # Relations
    responsable: Optional[User] = Relationship(back_populates="programmes_responsable")
    utilisateurs: List["ProgrammeUtilisateur"] = Relationship(back_populates="programme")
    promotions: List["Promotion"] = Relationship(back_populates="programme")
    preinscriptions: List["Preinscription"] = Relationship(back_populates="programme")
    inscriptions: List["Inscription"] = Relationship(back_populates="programme")
    etapes_pipeline: List["EtapePipeline"] = Relationship(back_populates="programme")
    seminaires: List["Seminaire"] = Relationship(back_populates="programme")
    events: List["Event"] = Relationship(back_populates="programme")

class ProgrammeUtilisateur(SQLModel, table=True):
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
    programme: Programme = Relationship(back_populates="utilisateurs")
    utilisateur: User = Relationship(back_populates="programmes_utilisateurs")

class Promotion(SQLModel, table=True):
    """Promotion d'un programme"""
    id: Optional[int] = Field(default=None, primary_key=True)
    programme_id: int = Field(foreign_key="programme.id")
    libelle: str
    capacite: Optional[int] = None
    date_debut: Optional[date] = None
    date_fin: Optional[date] = None
    actif: bool = True
    
    # Relations
    programme: Programme = Relationship(back_populates="promotions")
    inscriptions: List["Inscription"] = Relationship(back_populates="promotion")

class Candidat(SQLModel, table=True):
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
    statut: Optional[str] = Field(default="EN_ATTENTE")  # Statut du candidat
    # Géocodage (nouveaux champs)
    lat: Optional[float] = Field(default=None, index=True)
    lng: Optional[float] = Field(default=None, index=True)
    
    # Gestion handicap
    handicap: bool = False
    type_handicap: Optional[StatutHandicap] = None
    besoins_accommodation: Optional[str] = None
    
    # Relations
    entreprise: Optional["Entreprise"] = Relationship(back_populates="candidat")
    preinscriptions: List["Preinscription"] = Relationship(back_populates="candidat")
    inscriptions: List["Inscription"] = Relationship(back_populates="candidat")
    documents: List["Document"] = Relationship(back_populates="candidat")

class Entreprise(SQLModel, table=True):
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
    candidat: Candidat = Relationship(back_populates="entreprise")

class Preinscription(SQLModel, table=True):
    """Préinscription d'un candidat"""
    id: Optional[int] = Field(default=None, primary_key=True)
    programme_id: int = Field(foreign_key="programme.id")
    candidat_id: int = Field(foreign_key="candidat.id")
    source: Optional[str] = None  # "formulaire", "import", etc.
    donnees_brutes_json: Optional[str] = None  # données du formulaire
    statut: StatutDossier = StatutDossier.SOUMIS
    cree_le: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    
    # Relations
    programme: Programme = Relationship(back_populates="preinscriptions")
    candidat: Candidat = Relationship(back_populates="preinscriptions")
    eligibilite: Optional["Eligibilite"] = Relationship(back_populates="preinscription")

class Document(SQLModel, table=True):
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
    candidat: Candidat = Relationship(back_populates="documents")
    depose_par: Optional[User] = Relationship(back_populates="documents_deposes")

class Eligibilite(SQLModel, table=True):
    """Calcul d'éligibilité d'une préinscription"""
    id: Optional[int] = Field(default=None, primary_key=True)
    preinscription_id: int = Field(foreign_key="preinscription.id")
    ca_seuil_ok: Optional[bool] = None
    ca_score: Optional[float] = None
    qpv_ok: Optional[bool] = None
    anciennete_ok: Optional[bool] = None
    anciennete_annees: Optional[float] = None
    verdict: Optional[str] = None  # "ok" | "attention" | "ko"
    details_json: Optional[str] = None
    calcule_le: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    
    # Relations
    preinscription: Preinscription = Relationship(back_populates="eligibilite")

class Inscription(SQLModel, table=True):
    """Inscription validée d'un candidat"""
    id: Optional[int] = Field(default=None, primary_key=True)
    programme_id: int = Field(foreign_key="programme.id")
    candidat_id: int = Field(foreign_key="candidat.id")
    promotion_id: Optional[int] = Field(foreign_key="promotion.id")
    groupe_id: Optional[int] = None
    conseiller_id: Optional[int] = Field(foreign_key="user.id")
    referent_id: Optional[int] = Field(foreign_key="user.id")
    statut: StatutDossier = StatutDossier.EN_EXAMEN
    date_decision: Optional[datetime] = None
    email_confirmation_envoye: bool = False
    cree_le: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    
    # Relations
    programme: Programme = Relationship(back_populates="inscriptions")
    candidat: Candidat = Relationship(back_populates="inscriptions")
    promotion: Optional[Promotion] = Relationship(back_populates="inscriptions")
    conseiller: Optional[User] = Relationship(
        back_populates="inscriptions_conseiller",
        sa_relationship_kwargs={"foreign_keys": "[Inscription.conseiller_id]"}
    )
    referent: Optional[User] = Relationship(
        back_populates="inscriptions_referent",
        sa_relationship_kwargs={"foreign_keys": "[Inscription.referent_id]"}
    )
    decisions_jury: List["DecisionJuryTable"] = Relationship(back_populates="inscription")
    avancement_etapes: List["AvancementEtape"] = Relationship(back_populates="inscription")

class Jury(SQLModel, table=True):
    """Session de jury"""
    id: Optional[int] = Field(default=None, primary_key=True)
    programme_id: int = Field(foreign_key="programme.id")
    promotion_id: Optional[int] = Field(foreign_key="promotion.id")
    session_le: datetime
    lieu: Optional[str] = None
    statut: str = "planifie"  # "planifie", "en_cours", "termine"
    
    # Relations
    programme: Programme = Relationship()
    promotion: Optional[Promotion] = Relationship()
    membres: List["MembreJury"] = Relationship(back_populates="jury")
    decisions: List["DecisionJuryTable"] = Relationship(back_populates="jury")

class MembreJury(SQLModel, table=True):
    """Membre d'un jury"""
    id: Optional[int] = Field(default=None, primary_key=True)
    jury_id: int = Field(foreign_key="jury.id")
    utilisateur_id: int = Field(foreign_key="user.id")
    role: Optional[str] = None  # "president" | "membre"
    
    # Relations
    jury: Jury = Relationship(back_populates="membres")
    utilisateur: User = Relationship()

class DecisionJuryTable(SQLModel, table=True):
    """Décision d'un jury sur une inscription"""
    id: Optional[int] = Field(default=None, primary_key=True)
    inscription_id: int = Field(foreign_key="inscription.id")
    jury_id: int = Field(foreign_key="jury.id")
    decision: DecisionJury
    commentaires: Optional[str] = None
    prises_en_charge_json: Optional[str] = None  # actions suite à handicap etc.
    decide_le: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    
    # Relations
    inscription: Inscription = Relationship(back_populates="decisions_jury")
    jury: Jury = Relationship(back_populates="decisions")

class EtapePipeline(SQLModel, table=True):
    """Étape du pipeline de formation"""
    id: Optional[int] = Field(default=None, primary_key=True)
    programme_id: int = Field(foreign_key="programme.id")
    code: str          # "webinaire", "e_learning_n1", "seminaire_1", etc.
    libelle: str
    ordre: int
    active: bool = True
    type_etape: Optional[str] = None  # "formation", "evaluation", "accompagnement"
    
    # Relations
    programme: Programme = Relationship(back_populates="etapes_pipeline")
    avancements: List["AvancementEtape"] = Relationship(back_populates="etape")

class AvancementEtape(SQLModel, table=True):
    """Avancement d'un candidat dans une étape du pipeline"""
    id: Optional[int] = Field(default=None, primary_key=True)
    inscription_id: int = Field(foreign_key="inscription.id")
    etape_id: int = Field(foreign_key="etapepipeline.id")
    statut: StatutEtape = StatutEtape.A_FAIRE
    debut_le: Optional[datetime] = None
    termine_le: Optional[datetime] = None
    notes: Optional[str] = None
    
    # Relations
    inscription: Inscription = Relationship(back_populates="avancement_etapes")
    etape: EtapePipeline = Relationship(back_populates="avancements")

class ActionHandicap(SQLModel, table=True):
    """Actions d'accommodation pour handicap"""
    id: Optional[int] = Field(default=None, primary_key=True)
    inscription_id: int = Field(foreign_key="inscription.id")
    type_action: str  # "formation", "accompagnement", "materiel", etc.
    description: str
    responsable_id: Optional[int] = Field(foreign_key="user.id")
    date_echeance: Optional[date] = None
    statut: str = "a_faire"  # "a_faire", "en_cours", "termine"
    cree_le: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    
    # Relations
    inscription: Inscription = Relationship()
    responsable: Optional[User] = Relationship()

class RendezVous(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    inscription_id: int = Field(foreign_key="inscription.id")
    conseiller_id: Optional[int] = Field(foreign_key="user.id")
    type_rdv: TypeRDV = TypeRDV.ENTRETIEN
    statut: StatutRDV = StatutRDV.PLANIFIE
    debut: datetime
    fin: Optional[datetime] = None
    lieu: Optional[str] = None
    notes: Optional[str] = None
    meet_link: Optional[str] = None  # Lien Google Meet unique

    # Relations
    inscription: "Inscription" = Relationship()
    conseiller: Optional["User"] = Relationship()

class SessionProgramme(SQLModel, table=True):
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

    programme: Programme = Relationship()
    participants: List["SessionParticipant"] = Relationship(back_populates="session")

class SessionParticipant(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    session_id: int = Field(foreign_key="sessionprogramme.id", index=True)
    inscription_id: int = Field(foreign_key="inscription.id", index=True)
    presence: StatutPresence = StatutPresence.ABSENT
    note: Optional[str] = None

    session: SessionProgramme = Relationship(back_populates="participants")
    inscription: "Inscription" = Relationship()

class SuiviMensuel(SQLModel, table=True):
    """Suivi mensuel des candidats avec métriques business"""
    id: Optional[int] = Field(default=None, primary_key=True)
    inscription_id: int = Field(foreign_key="inscription.id", index=True)
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

    inscription: "Inscription" = Relationship()

class Partenaire(SQLModel, table=True):
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

class DecisionJuryCandidat(SQLModel, table=True):
    """Décisions du jury pour chaque candidat"""
    id: Optional[int] = Field(default=None, primary_key=True)
    candidat_id: int = Field(foreign_key="candidat.id", index=True)
    jury_id: int = Field(foreign_key="jury.id", index=True)
    decision: DecisionJury = Field(default=DecisionJury.EN_ATTENTE)
    commentaires: Optional[str] = None
    conseiller_id: Optional[int] = Field(foreign_key="user.id", default=None)  # Si validé
    groupe_id: Optional[int] = Field(foreign_key="groupe.id", default=None)  # Si validé
    promotion_id: Optional[int] = Field(foreign_key="promotion.id", default=None)  # Si validé
    partenaire_id: Optional[int] = Field(foreign_key="partenaire.id", default=None)  # Si réorienté
    envoyer_mail_candidat: bool = Field(default=False)
    envoyer_mail_conseiller: bool = Field(default=False)
    envoyer_mail_partenaire: bool = Field(default=False)
    date_decision: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    cree_le: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    
    # Relations
    candidat: "Candidat" = Relationship()
    jury: "Jury" = Relationship()
    conseiller: Optional["User"] = Relationship()
    groupe: Optional["Groupe"] = Relationship()
    promotion: Optional["Promotion"] = Relationship()
    partenaire: Optional["Partenaire"] = Relationship()

class ReorientationCandidat(SQLModel, table=True):
    """Historique des réorientations"""
    id: Optional[int] = Field(default=None, primary_key=True)
    candidat_id: int = Field(foreign_key="candidat.id", index=True)
    partenaire_id: int = Field(foreign_key="partenaire.id", index=True)
    decision_jury_id: int = Field(foreign_key="decisionjurycandidat.id", index=True)
    motif: Optional[str] = None
    mail_envoye: bool = Field(default=False)
    date_reorientation: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    
    # Relations
    candidat: "Candidat" = Relationship()
    partenaire: "Partenaire" = Relationship(back_populates="reorientations")
    decision_jury: "DecisionJuryCandidat" = Relationship()

class Groupe(SQLModel, table=True):
    """Groupes de codéveloppement"""
    id: Optional[int] = Field(default=None, primary_key=True)
    nom: str = Field(index=True, max_length=100)
    description: Optional[str] = Field(default=None, max_length=500)
    capacite_max: Optional[int] = Field(default=None)
    actif: bool = Field(default=True)
    date_creation: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    date_modification: Optional[datetime] = Field(default=None)
    
    # Relations pour le codev (ajoutées dynamiquement)
    # seances: List["SeanceCodev"] = Relationship(back_populates="groupe")
    # groupes_codev: List["GroupeCodev"] = Relationship(back_populates="groupe")

class EmargementRDV(SQLModel, table=True):
    """Émargement pour les rendez-vous"""
    id: Optional[int] = Field(default=None, primary_key=True)
    rdv_id: int = Field(foreign_key="rendezvous.id", index=True)
    type_signataire: str = Field(index=True)  # "conseiller" ou "candidat"
    signataire_id: Optional[int] = Field(foreign_key="user.id", index=True)  # Pour le conseiller
    candidat_id: Optional[int] = Field(foreign_key="candidat.id", index=True)  # Pour le candidat
    signature_conseiller: Optional[str] = None  # Signature du conseiller (base64 ou hash)
    signature_candidat: Optional[str] = None    # Signature du candidat (base64 ou hash)
    date_signature_conseiller: Optional[datetime] = None
    date_signature_candidat: Optional[datetime] = None
    ip_address: Optional[str] = None  # Adresse IP pour traçabilité
    user_agent: Optional[str] = None  # User agent pour traçabilité
    cree_le: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    
    # Relations
    rdv: "RendezVous" = Relationship()
    signataire: Optional["User"] = Relationship()
    candidat: Optional["Candidat"] = Relationship()