from pydantic import BaseModel
from datetime import datetime, date
from typing import Optional, List
from app_lia_web.app.models.event import StatutEvent, TypeInvitationEvent, StatutInvitationEvent, MethodeSignatureEvent

# === SCHÉMAS DE BASE ===

class EventBase(BaseModel):
    titre: str
    description: Optional[str] = None
    date_debut: date
    date_fin: date
    heure_debut: Optional[datetime] = None
    heure_fin: Optional[datetime] = None
    lieu: Optional[str] = None
    statut: StatutEvent = StatutEvent.PLANIFIE
    programme_id: int
    organisateur_id: int

class EventCreate(EventBase):
    pass

class EventUpdate(BaseModel):
    titre: Optional[str] = None
    description: Optional[str] = None
    date_debut: Optional[date] = None
    date_fin: Optional[date] = None
    heure_debut: Optional[datetime] = None
    heure_fin: Optional[datetime] = None
    lieu: Optional[str] = None
    statut: Optional[StatutEvent] = None
    programme_id: Optional[int] = None
    organisateur_id: Optional[int] = None

class Event(EventBase):
    id: int
    cree_le: datetime
    modifie_le: Optional[datetime] = None
    
    class Config:
        from_attributes = True

# === SCHÉMAS INVITATION EVENT ===

class InvitationEventBase(BaseModel):
    type_invitation: TypeInvitationEvent
    statut: StatutInvitationEvent = StatutInvitationEvent.EN_ATTENTE
    token_invitation: str
    date_envoi: Optional[datetime] = None
    date_reponse: Optional[datetime] = None
    event_id: int
    inscription_id: int

class InvitationEventCreate(InvitationEventBase):
    pass

class InvitationEventUpdate(BaseModel):
    statut: Optional[StatutInvitationEvent] = None
    date_reponse: Optional[datetime] = None

class InvitationEvent(InvitationEventBase):
    id: int
    cree_le: datetime
    modifie_le: Optional[datetime] = None
    
    class Config:
        from_attributes = True

# === SCHÉMAS PRESENCE EVENT ===

class PresenceEventBase(BaseModel):
    presence: str = "absent"
    methode_signature: Optional[MethodeSignatureEvent] = None
    signature_manuelle: Optional[str] = None
    signature_digitale: Optional[str] = None
    photo_signature: Optional[str] = None
    heure_arrivee: Optional[datetime] = None
    commentaire: Optional[str] = None
    ip_signature: Optional[str] = None
    event_id: int
    inscription_id: int

class PresenceEventCreate(PresenceEventBase):
    pass

class PresenceEventUpdate(BaseModel):
    presence: Optional[str] = None
    signature_manuelle: Optional[str] = None
    signature_digitale: Optional[str] = None
    photo_signature: Optional[str] = None
    heure_arrivee: Optional[datetime] = None
    commentaire: Optional[str] = None
    ip_signature: Optional[str] = None

class PresenceEvent(PresenceEventBase):
    id: int
    cree_le: datetime
    modifie_le: Optional[datetime] = None
    
    class Config:
        from_attributes = True
