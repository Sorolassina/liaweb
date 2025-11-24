# app/models/seminaire.py
from sqlmodel import SQLModel, Field, Relationship
from sqlalchemy import UniqueConstraint
from typing import Optional, List
from datetime import datetime, timezone, date
from .enums import TypeSession, StatutPresence, StatutSeminaire, TypeInvitation
from .base import Programme, User, Candidat

class Seminaire(SQLModel, table=True):
    __tablename__ = "seminaire"
    """Séminaire multi-jours avec programmes matin/soir"""
    id: Optional[int] = Field(default=None, primary_key=True)
    
    # Informations générales
    titre: str
    description: Optional[str] = None
    programme_id: int = Field(foreign_key="programme.id", index=True)
    
    # Dates et lieu
    date_debut: date
    date_fin: date
    lieu: Optional[str] = None
    adresse_complete: Optional[str] = None
    
    # Organisation
    organisateur: str  # Nom de l'organisateur (string)
    capacite_max: Optional[int] = None
    
    # Statut et configuration
    statut: StatutSeminaire = StatutSeminaire.PLANIFIE
    actif: bool = True
    
    # Configuration des invitations
    invitation_auto: bool = False  # Invitation automatique à tous les candidats
    invitation_promos: bool = False  # Invitation par promotions
    
    # Métadonnées
    cree_le: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    modifie_le: Optional[datetime] = None
    
    # Relations
    programme: "Programme" = Relationship(back_populates="seminaires")
    sessions: List["SessionSeminaire"] = Relationship(back_populates="seminaire")
    invitations: List["InvitationSeminaire"] = Relationship(back_populates="seminaire")
    livrables: List["LivrableSeminaire"] = Relationship(back_populates="seminaire")

class SessionSeminaire(SQLModel, table=True):
    __tablename__ = "session_seminaire"
    
    """Session individuelle d'un séminaire (matin/soir)"""
    id: Optional[int] = Field(default=None, primary_key=True)
    seminaire_id: int = Field(foreign_key="seminaire.id", index=True)
    
    # Informations de la session
    titre: str
    description: Optional[str] = None
    type_session: TypeSession = TypeSession.SEMINAIRE
    
    # Horaires
    date_session: date
    heure_debut: datetime
    heure_fin: Optional[datetime] = None
    
    # Lieu spécifique (peut différer du séminaire)
    lieu: Optional[str] = None
    visioconf_url: Optional[str] = None
    
    # Configuration
    capacite: Optional[int] = None
    obligatoire: bool = True
    
    # Métadonnées
    cree_le: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    
    # Relations
    seminaire: "Seminaire" = Relationship(back_populates="sessions")
    participants: List["PresenceSeminaire"] = Relationship(back_populates="session")

class InvitationSeminaire(SQLModel, table=True):
    __tablename__ = "invitation_seminaire"
    
    """Invitation d'un candidat/promotion à un séminaire"""
    id: Optional[int] = Field(default=None, primary_key=True)
    seminaire_id: int = Field(foreign_key="seminaire.id", index=True)
    
    # Type d'invitation
    type_invitation: TypeInvitation
    
    # Cible de l'invitation
    candidat_id: Optional[int] = Field(foreign_key="candidat.id", index=True)
    promotion_id: Optional[int] = Field(foreign_key="promotion.id", index=True)
    
    # Statut de l'invitation
    statut: str = Field(default="ENVOYEE")  # ENVOYEE, ACCEPTEE, REFUSEE, EXPIRED
    
    # Informations d'envoi
    email_envoye: Optional[str] = None
    date_envoi: Optional[datetime] = None
    date_reponse: Optional[datetime] = None
    
    # Token pour les liens d'invitation
    token_invitation: Optional[str] = None
    
    # Métadonnées
    cree_le: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    
    # Relations
    seminaire: "Seminaire" = Relationship(back_populates="invitations")
    candidat: Optional["Candidat"] = Relationship()

class PresenceSeminaire(SQLModel, table=True):
    __tablename__ = "presence_seminaire"
    __table_args__ = (
        # Contrainte unique : un candidat ne peut avoir qu'une seule présence par session
        # Mais peut avoir plusieurs présences pour différentes sessions du même séminaire
        # IMPORTANT : L'émargement est attaché à une SESSION, pas au séminaire
        # L'acceptation d'invitation est attachée au SÉMINAIRE
        UniqueConstraint('session_id', 'candidat_id', name='uq_presence_session_candidat'),
    )
    
    """Présence d'un candidat à une session de séminaire
    
    IMPORTANT : 
    - Un émargement (présence) est attaché à une SESSION de séminaire
    - Une acceptation (invitation) est attachée à un SÉMINAIRE
    - Un candidat peut avoir plusieurs présences pour un même séminaire (une par session)
    - Un candidat ne peut avoir qu'une seule présence par session (contrainte unique)
    """
    id: Optional[int] = Field(default=None, primary_key=True)
    session_id: int = Field(foreign_key="session_seminaire.id", index=True)
    candidat_id: int = Field(foreign_key="candidat.id", index=True)
    
    # Statut de présence
    presence: str = Field(default="en_attente")  # "en_attente", "absent", "present", "excuse"
    
    # Méthode de signature
    methode_signature: Optional[str] = None  # "MANUEL", "DIGITAL", "QR_CODE"
    
    # Informations de signature
    signature_manuelle: Optional[str] = None  # Base64 de la signature
    signature_digitale: Optional[str] = None  # Hash de la signature digitale
    photo_signature: Optional[str] = None  # Base64 de la photo de signature
    ip_signature: Optional[str] = None
    user_agent: Optional[str] = None
    
    # Horaires
    heure_arrivee: Optional[datetime] = None
    heure_depart: Optional[datetime] = None
    
    # Notes
    note: Optional[str] = None
    
    # Métadonnées
    cree_le: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    modifie_le: Optional[datetime] = None
    
    # Relations
    session: "SessionSeminaire" = Relationship(back_populates="participants")
    candidat: "Candidat" = Relationship()

class LivrableSeminaire(SQLModel, table=True):
    __tablename__ = "livrable_seminaire"
    
    """Livrables à rendre à la fin du séminaire"""
    id: Optional[int] = Field(default=None, primary_key=True)
    seminaire_id: int = Field(foreign_key="seminaire.id", index=True)
    
    # Informations du livrable
    titre: str
    description: Optional[str] = None
    type_livrable: str  # "DOCUMENT", "PRESENTATION", "RAPPORT", "AUTRE"
    
    # Configuration
    obligatoire: bool = True
    date_limite: Optional[datetime] = None
    
    # Instructions
    consignes: Optional[str] = None
    format_accepte: Optional[str] = None  # "PDF", "DOCX", "PPTX", etc.
    taille_max_mb: Optional[int] = None
    
    # Métadonnées
    cree_le: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    
    # Relations
    seminaire: "Seminaire" = Relationship(back_populates="livrables")
    rendus: List["RenduLivrable"] = Relationship(back_populates="livrable")

class RenduLivrable(SQLModel, table=True):
    __tablename__ = "rendu_livrable"
    
    """Rendu d'un livrable par un candidat"""
    id: Optional[int] = Field(default=None, primary_key=True)
    livrable_id: int = Field(foreign_key="livrable_seminaire.id", index=True)
    candidat_id: int = Field(foreign_key="candidat.id", index=True)
    
    # Fichier rendu
    nom_fichier: str
    chemin_fichier: str
    taille_fichier: int  # en bytes
    type_mime: str
    
    # Statut
    statut: str = Field(default="DEPOSE")  # DEPOSE, VALIDE, REJETE, EN_ATTENTE
    
    # Commentaires
    commentaire_candidat: Optional[str] = None
    commentaire_evaluateur: Optional[str] = None
    
    # Métadonnées
    depose_le: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    evalue_le: Optional[datetime] = None
    evaluateur_id: Optional[int] = Field(foreign_key="user.id")
    
    # Relations
    livrable: "LivrableSeminaire" = Relationship(back_populates="rendus")
    candidat: "Candidat" = Relationship()
    evaluateur: Optional["User"] = Relationship()
