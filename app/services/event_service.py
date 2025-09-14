from sqlmodel import Session, select
from datetime import datetime, timezone
from typing import List, Optional, Dict
import secrets
import string
from app_lia_web.app.models.event import Event, InvitationEvent, PresenceEvent
from app_lia_web.app.schemas.event_schemas import EventCreate, EventUpdate, InvitationEventCreate, PresenceEventCreate
from app_lia_web.app.services.email_service import EmailService

class EventService:
    def __init__(self):
        self.email_service = EmailService()
    
    # === GESTION DES ÉVÉNEMENTS ===
    
    def create_event(self, event_data: EventCreate, db: Session) -> Event:
        event = Event(**event_data.dict())
        db.add(event)
        db.commit()
        db.refresh(event)
        return event
    
    def get_event(self, event_id: int, db: Session) -> Optional[Event]:
        return db.get(Event, event_id)
    
    def get_events(self, db: Session, skip: int = 0, limit: int = 100) -> List[Event]:
        query = select(Event).offset(skip).limit(limit)
        return db.exec(query).all()
    
    def update_event(self, event_id: int, event_data: EventUpdate, db: Session) -> Optional[Event]:
        event = db.get(Event, event_id)
        if not event:
            return None
        
        for field, value in event_data.dict(exclude_unset=True).items():
            setattr(event, field, value)
        
        event.modifie_le = datetime.now(timezone.utc)
        db.commit()
        db.refresh(event)
        return event
    
    def delete_event(self, event_id: int, db: Session) -> bool:
        event = db.get(Event, event_id)
        if not event:
            return False
        
        db.delete(event)
        db.commit()
        return True
    
    def get_event_stats(self, db: Session) -> Dict[str, int]:
        events = db.exec(select(Event)).all()
        return {
            'total_events': len(events),
            'events_planifies': len([e for e in events if e.statut == 'planifie']),
            'events_en_cours': len([e for e in events if e.statut == 'en_cours']),
            'events_termines': len([e for e in events if e.statut == 'termine'])
        }
    
    # === GESTION DES INVITATIONS D'ÉVÉNEMENTS ===
    
    def create_invitation(self, invitation_data: InvitationEventCreate, db: Session) -> InvitationEvent:
        invitation = InvitationEvent(**invitation_data.dict())
        db.add(invitation)
        db.commit()
        db.refresh(invitation)
        return invitation
    
    def get_invitations_by_event(self, event_id: int, db: Session) -> List[InvitationEvent]:
        query = select(InvitationEvent).where(InvitationEvent.event_id == event_id)
        return db.exec(query).all()
    
    def get_invitation_by_token(self, token: str, db: Session) -> Optional[InvitationEvent]:
        query = select(InvitationEvent).where(InvitationEvent.token_invitation == token)
        return db.exec(query).first()
    
    def update_invitation_status(self, invitation_id: int, status: str, db: Session) -> Optional[InvitationEvent]:
        invitation = db.get(InvitationEvent, invitation_id)
        if not invitation:
            return None
        
        invitation.statut = status
        invitation.date_reponse = datetime.now(timezone.utc)
        invitation.modifie_le = datetime.now(timezone.utc)
        
        db.commit()
        db.refresh(invitation)
        return invitation
    
    def generate_invitation_token(self) -> str:
        return ''.join(secrets.choices(string.ascii_letters + string.digits, k=32))
    
    # === GESTION DES PRÉSENCES D'ÉVÉNEMENTS ===
    
    def create_presence(self, presence_data: PresenceEventCreate, db: Session) -> PresenceEvent:
        presence = PresenceEvent(**presence_data.dict())
        db.add(presence)
        db.commit()
        db.refresh(presence)
        return presence
    
    def get_presence_candidat(self, event_id: int, inscription_id: int, db: Session) -> Optional[PresenceEvent]:
        query = select(PresenceEvent).where(
            PresenceEvent.event_id == event_id,
            PresenceEvent.inscription_id == inscription_id
        )
        return db.exec(query).first()
    
    def mark_presence(self, presence_data: PresenceEventCreate, db: Session) -> PresenceEvent:
        existing_presence = self.get_presence_candidat(presence_data.event_id, presence_data.inscription_id, db)
        
        if existing_presence:
            for field, value in presence_data.dict().items():
                if field not in ['event_id', 'inscription_id']:
                    setattr(existing_presence, field, value)
            existing_presence.modifie_le = datetime.now(timezone.utc)
            db.commit()
            db.refresh(existing_presence)
            return existing_presence
        else:
            return self.create_presence(presence_data, db)
    
    def get_presences_by_event(self, event_id: int, db: Session) -> List[PresenceEvent]:
        query = select(PresenceEvent).where(PresenceEvent.event_id == event_id)
        return db.exec(query).all()
    
    def get_presence_stats(self, event_id: int, db: Session) -> Dict[str, int]:
        presences = self.get_presences_by_event(event_id, db)
        return {
            'total': len(presences),
            'present': len([p for p in presences if p.presence == 'present']),
            'absent': len([p for p in presences if p.presence == 'absent']),
            'excuse': len([p for p in presences if p.presence == 'excuse'])
        }
    
    def get_presences_with_invitations(self, event_id: int, db: Session) -> List[PresenceEvent]:
        # Récupérer toutes les invitations acceptées pour cet événement
        invitations_query = select(InvitationEvent).where(
            InvitationEvent.event_id == event_id,
            InvitationEvent.statut == 'acceptee'
        )
        invitations = db.exec(invitations_query).all()
        
        presences = []
        for invitation in invitations:
            db.refresh(invitation)
            existing_presence = self.get_presence_candidat(event_id, invitation.inscription_id, db)
            if existing_presence:
                db.refresh(existing_presence)
                presences.append(existing_presence)
            else:
                from app_lia_web.app.models.seminaire import Inscription
                inscription = db.get(Inscription, invitation.inscription_id)
                if inscription:
                    db.refresh(inscription)
                    if inscription.candidat:
                        db.refresh(inscription.candidat)
                    default_presence = PresenceEvent(
                        event_id=event_id,
                        inscription_id=invitation.inscription_id,
                        presence="absent"
                    )
                    db.add(default_presence)
                    db.commit()
                    db.refresh(default_presence)
                    default_presence.inscription = inscription
                    presences.append(default_presence)
        return presences
    
    def get_presence_stats_with_invitations(self, event_id: int, db: Session) -> Dict[str, int]:
        presences = self.get_presences_with_invitations(event_id, db)
        stats = {
            'total': len(presences),
            'present': len([p for p in presences if p.presence == 'present']),
            'absent': len([p for p in presences if p.presence == 'absent']),
            'excuse': len([p for p in presences if p.presence == 'excuse'])
        }
        
        if stats['total'] > 0:
            stats['taux_presence'] = round((stats['present'] / stats['total']) * 100, 1)
        else:
            stats['taux_presence'] = 0
        
        return stats
