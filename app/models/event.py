from sqlmodel import SQLModel, Field, Relationship
from datetime import datetime, date
from typing import Optional, List
from enum import Enum
from .enums import StatutEvent, TypeInvitationEvent, StatutInvitationEvent, MethodeSignatureEvent



class Event(SQLModel, table=True):
    __tablename__ = "event"

    id: Optional[int] = Field(default=None, primary_key=True)
    titre: str = Field(max_length=255)
    description: Optional[str] = Field(default=None)
    date_debut: date
    date_fin: date
    heure_debut: Optional[datetime] = Field(default=None)
    heure_fin: Optional[datetime] = Field(default=None)
    lieu: Optional[str] = Field(default=None, max_length=255)
    statut: StatutEvent = Field(default=StatutEvent.PLANIFIE)
    
    # Relations
    programme_id: int = Field(foreign_key="programme.id")
    programme: Optional["Programme"] = Relationship(back_populates="events")
    
    organisateur_id: int = Field(foreign_key="user.id")
    organisateur: Optional["User"] = Relationship()
    
    # Timestamps
    cree_le: datetime = Field(default_factory=lambda: datetime.now())
    modifie_le: Optional[datetime] = Field(default=None)
    
    # Relations avec les invitations et présences d'événements
    invitations: List["InvitationEvent"] = Relationship(back_populates="event")
    presences: List["PresenceEvent"] = Relationship(back_populates="event")

class InvitationEvent(SQLModel, table=True):
    __tablename__ = "invitation_event"

    id: Optional[int] = Field(default=None, primary_key=True)
    type_invitation: TypeInvitationEvent
    statut: StatutInvitationEvent = Field(default=StatutInvitationEvent.EN_ATTENTE)
    token_invitation: str = Field(unique=True, max_length=255)
    date_envoi: Optional[datetime] = Field(default=None)
    date_reponse: Optional[datetime] = Field(default=None)
    
    # Relations
    event_id: int = Field(foreign_key="event.id")
    event: Optional["Event"] = Relationship(back_populates="invitations")
    
    candidat_id: int = Field(foreign_key="candidat.id")
    candidat: Optional["Candidat"] = Relationship(back_populates="invitations_event")
    
    # Timestamps
    cree_le: datetime = Field(default_factory=lambda: datetime.now())
    modifie_le: Optional[datetime] = Field(default=None)

class PresenceEvent(SQLModel, table=True):
    __tablename__ = "presence_event"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    presence: str = Field(default="en_attente")
    methode_signature: Optional[MethodeSignatureEvent] = Field(default=None)
    signature_manuelle: Optional[str] = Field(default=None)
    signature_digitale: Optional[str] = Field(default=None)
    photo_signature: Optional[str] = Field(default=None)
    heure_arrivee: Optional[datetime] = Field(default=None)
    commentaire: Optional[str] = Field(default=None)
    ip_signature: Optional[str] = Field(default=None)
    
    # Relations
    event_id: int = Field(foreign_key="event.id")
    event: Optional["Event"] = Relationship(back_populates="presences")
    
    candidat_id: int = Field(foreign_key="candidat.id")
    candidat: Optional["Candidat"] = Relationship(back_populates="presences_event")
    
    # Timestamps
    cree_le: datetime = Field(default_factory=lambda: datetime.now())
    modifie_le: Optional[datetime] = Field(default=None)
