# app/models/seminaire.py
from sqlmodel import SQLModel, Field, Relationship
from typing import Optional, List
from datetime import datetime, timezone, date
from .enums import TypeSession, StatutPresence, StatutSeminaire, TypeInvitation
from .base import Programme, User, Inscription

class Seminaire(SQLModel, table=True):
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
    organisateur_id: int = Field(foreign_key="user.id")
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
    programme: Programme = Relationship(back_populates="seminaires")
    organisateur: User = Relationship()
    sessions: List["SessionSeminaire"] = Relationship(back_populates="seminaire")
    invitations: List["InvitationSeminaire"] = Relationship(back_populates="seminaire")
    livrables: List["LivrableSeminaire"] = Relationship(back_populates="seminaire")

class SessionSeminaire(SQLModel, table=True):
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
    seminaire: Seminaire = Relationship(back_populates="sessions")
    participants: List["PresenceSeminaire"] = Relationship(back_populates="session")

class InvitationSeminaire(SQLModel, table=True):
    """Invitation d'un candidat/promotion à un séminaire"""
    id: Optional[int] = Field(default=None, primary_key=True)
    seminaire_id: int = Field(foreign_key="seminaire.id", index=True)
    
    # Type d'invitation
    type_invitation: TypeInvitation
    
    # Cible de l'invitation
    inscription_id: Optional[int] = Field(foreign_key="inscription.id", index=True)
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
    seminaire: Seminaire = Relationship(back_populates="invitations")
    inscription: Optional[Inscription] = Relationship()

class PresenceSeminaire(SQLModel, table=True):
    """Présence d'un candidat à une session de séminaire"""
    id: Optional[int] = Field(default=None, primary_key=True)
    session_id: int = Field(foreign_key="sessionseminaire.id", index=True)
    inscription_id: int = Field(foreign_key="inscription.id", index=True)
    
    # Statut de présence
    presence: str = Field(default="absent")  # "absent", "present", "excuse"
    
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
    session: SessionSeminaire = Relationship(back_populates="participants")
    inscription: Inscription = Relationship()

class LivrableSeminaire(SQLModel, table=True):
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
    seminaire: Seminaire = Relationship(back_populates="livrables")
    rendus: List["RenduLivrable"] = Relationship(back_populates="livrable")

class RenduLivrable(SQLModel, table=True):
    """Rendu d'un livrable par un candidat"""
    id: Optional[int] = Field(default=None, primary_key=True)
    livrable_id: int = Field(foreign_key="livrableseminaire.id", index=True)
    inscription_id: int = Field(foreign_key="inscription.id", index=True)
    
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
    livrable: LivrableSeminaire = Relationship(back_populates="rendus")
    inscription: Inscription = Relationship()
    evaluateur: Optional[User] = Relationship()
