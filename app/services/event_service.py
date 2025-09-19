from sqlmodel import Session, select
from datetime import datetime, timezone
from typing import List, Optional, Dict
import secrets
import string
from app_lia_web.app.models.event import Event, InvitationEvent, PresenceEvent
from app_lia_web.app.models.enums import TypeInvitation
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
    
    def get_events(self, db: Session, skip: int = 0, limit: int = 100, programme_id: Optional[int] = None) -> List[Event]:
        query = select(Event)
        if programme_id:
            query = query.where(Event.programme_id == programme_id)
        query = query.offset(skip).limit(limit)
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
        
        # Ne pas créer de présence ici - cela sera fait le jour de l'événement
        # ou lors de l'émargement
        
        db.commit()
        db.refresh(invitation)
        return invitation
    
    def generate_invitation_token(self) -> str:
        import random
        return ''.join(random.choices(string.ascii_letters + string.digits, k=32))
    
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
        """Marquer une présence - ne modifie QUE le statut de présence, pas l'invitation"""
        print(f"🔍 MARK_PRESENCE - Event {presence_data.event_id}, Inscription {presence_data.inscription_id}, Statut: {presence_data.presence}")
        
        existing_presence = self.get_presence_candidat(presence_data.event_id, presence_data.inscription_id, db)
        
        if existing_presence:
            print(f"   📝 Présence existante trouvée: {existing_presence.presence}")
            for field, value in presence_data.dict().items():
                if field not in ['event_id', 'inscription_id']:
                    setattr(existing_presence, field, value)
            
            # Si une signature existe (peu importe la méthode), mettre le statut à "present"
            if presence_data.signature_digitale or presence_data.signature_manuelle:
                existing_presence.presence = "present"
                print(f"   ✍️ Signature détectée - Statut automatiquement mis à 'present'")
            
            existing_presence.modifie_le = datetime.now(timezone.utc)
            db.commit()
            db.refresh(existing_presence)
            presence_obj = existing_presence
            print(f"   ✅ Présence mise à jour: {presence_obj.presence}")
        else:
            print(f"   ➕ Création nouvelle présence")
            
            # Si une signature existe (peu importe la méthode), mettre le statut à "present"
            if presence_data.signature_digitale or presence_data.signature_manuelle:
                presence_data.presence = "present"
                print(f"   ✍️ Signature détectée - Statut automatiquement mis à 'present'")
            
            presence_obj = self.create_presence(presence_data, db)
            print(f"   ✅ Nouvelle présence créée: {presence_obj.presence}")
        
        return presence_obj
    
    def get_combined_status(self, event_id: int, inscription_id: int, db: Session) -> str:
        """
        Retourne le statut imbriqué pour la page principale :
        - Avant l'événement : privilégie le statut d'invitation
        - Après l'événement : privilégie le statut de présence
        """
        from datetime import date
        
        # Récupérer l'événement pour connaître sa date
        event = db.get(Event, event_id)
        if not event:
            return "en_attente"
        
        today = date.today()
        event_passed = event.date_fin < today
        
        # Récupérer l'invitation
        invitation_query = select(InvitationEvent).where(
            InvitationEvent.event_id == event_id,
            InvitationEvent.inscription_id == inscription_id
        )
        invitation = db.exec(invitation_query).first()
        
        # Récupérer la présence
        presence = self.get_presence_candidat(event_id, inscription_id, db)
        
        if event_passed:
            # APRÈS L'ÉVÉNEMENT : privilégier le statut de présence
            if presence and presence.presence in ['present', 'absent', 'excuse']:
                return presence.presence
            else:
                # Pas de présence marquée après l'événement = absent
                return "absent"
        else:
            # AVANT L'ÉVÉNEMENT : privilégier le statut d'invitation
            if invitation:
                if invitation.statut == "refusee":
                    return "refusee"
                elif invitation.statut == "acceptee":
                    return "acceptee"
                else:
                    return "en_attente"
            else:
                return "en_attente"
    
    def get_presences_with_combined_status(self, event_id: int, db: Session) -> List[dict]:
        """
        Retourne les présences avec le statut imbriqué pour la page principale
        """
        from datetime import date
        
        # Récupérer toutes les invitations pour cet événement
        invitations_query = select(InvitationEvent).where(InvitationEvent.event_id == event_id)
        invitations = db.exec(invitations_query).all()
        
        result = []
        for invitation in invitations:
            db.refresh(invitation)
            
            # Récupérer la présence existante
            presence = self.get_presence_candidat(event_id, invitation.inscription_id, db)
            
            # Calculer le statut imbriqué
            combined_status = self.get_combined_status(event_id, invitation.inscription_id, db)
            
            # Créer l'objet de résultat
            presence_data = {
                'invitation': invitation,
                'presence': presence,
                'combined_status': combined_status,
                'inscription_id': invitation.inscription_id
            }
            
            result.append(presence_data)
        
        return result
    
    def get_presences_by_event(self, event_id: int, db: Session) -> List[PresenceEvent]:
        """Récupère toutes les présences d'un événement"""
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
    
    def debug_invitations_and_presences(self, event_id: int, db: Session) -> Dict:
        """Méthode de debug pour voir les invitations et présences"""
        from datetime import date
        
        # Récupérer toutes les invitations
        invitations_query = select(InvitationEvent).where(InvitationEvent.event_id == event_id)
        invitations = db.exec(invitations_query).all()
        
        # Récupérer toutes les présences existantes
        presences_query = select(PresenceEvent).where(PresenceEvent.event_id == event_id)
        existing_presences = db.exec(presences_query).all()
        
        # Récupérer l'événement
        event = db.get(Event, event_id)
        today = date.today()
        event_passed = event.date_fin < today if event else False
        
        debug_info = {
            'event_id': event_id,
            'event_title': event.titre if event else 'N/A',
            'event_date': event.date_fin.strftime('%Y-%m-%d') if event else 'N/A',
            'today': today.strftime('%Y-%m-%d'),
            'event_passed': event_passed,
            'total_invitations': len(invitations),
            'total_existing_presences': len(existing_presences),
            'invitations_detail': [],
            'presences_detail': []
        }
        
        # Détail des invitations
        for invitation in invitations:
            debug_info['invitations_detail'].append({
                'id': invitation.id,
                'statut': invitation.statut,
                'inscription_id': invitation.inscription_id,
                'date_envoi': invitation.date_envoi.strftime('%Y-%m-%d %H:%M') if invitation.date_envoi else None,
                'date_reponse': invitation.date_reponse.strftime('%Y-%m-%d %H:%M') if invitation.date_reponse else None
            })
        
        # Détail des présences existantes
        for presence in existing_presences:
            debug_info['presences_detail'].append({
                'id': presence.id,
                'presence': presence.presence,
                'inscription_id': presence.inscription_id,
                'methode_signature': presence.methode_signature,
                'heure_arrivee': presence.heure_arrivee.strftime('%Y-%m-%d %H:%M') if presence.heure_arrivee else None
            })
        
        return debug_info
    
    def get_presences_with_invitations(self, event_id: int, db: Session) -> List[PresenceEvent]:
        """
        Récupère toutes les présences d'un événement avec les invitations
        Utilisé pour la page d'émargement - retourne les statuts de présence purs
        """
        print(f"🔍 GET_PRESENCES_WITH_INVITATIONS - Event {event_id}")
        
        # Récupérer toutes les invitations pour cet événement
        invitations_query = select(InvitationEvent).where(InvitationEvent.event_id == event_id)
        invitations = db.exec(invitations_query).all()
        
        presences = []
        for invitation in invitations:
            db.refresh(invitation)
            existing_presence = self.get_presence_candidat(event_id, invitation.inscription_id, db)
            if existing_presence:
                db.refresh(existing_presence)
                print(f"   📝 Présence trouvée pour inscription {invitation.inscription_id}: {existing_presence.presence}")
                presences.append(existing_presence)
            else:
                from app_lia_web.app.models.seminaire import Inscription
                inscription = db.get(Inscription, invitation.inscription_id)
                if inscription:
                    # Créer une présence par défaut
                    presence_data = PresenceEventCreate(
                        event_id=event_id,
                        inscription_id=invitation.inscription_id,
                        presence="en_attente"
                    )
                    new_presence = self.create_presence(presence_data, db)
                    print(f"   ➕ Nouvelle présence créée pour inscription {invitation.inscription_id}: {new_presence.presence}")
                    presences.append(new_presence)
        
        print(f"   📊 Total présences retournées: {len(presences)}")
        return presences
    
    def update_presence_status_after_event(self, event_id: int, db: Session) -> None:
        """Met à jour les statuts de présence après qu'un événement soit passé"""
        from datetime import date
        
        event = db.get(Event, event_id)
        if not event:
            return
        
        today = date.today()
        if event.date_fin >= today:
            return  # L'événement n'est pas encore passé
        
        # Récupérer toutes les présences pour cet événement
        presences_query = select(PresenceEvent).where(PresenceEvent.event_id == event_id)
        presences = db.exec(presences_query).all()
        
        for presence in presences:
            # Si la présence est encore "en_attente" et l'événement est passé
            if presence.presence == "en_attente":
                presence.presence = "absent"
                presence.modifie_le = datetime.now(timezone.utc)
        
        db.commit()
    
    def get_presence_stats_with_invitations(self, event_id: int, db: Session) -> Dict[str, int]:
        presences = self.get_presences_with_invitations(event_id, db)
        stats = {
            'total': len(presences),
            'present': len([p for p in presences if p.presence == 'present']),
            'absent': len([p for p in presences if p.presence == 'absent']),
            'excuse': len([p for p in presences if p.presence == 'excuse']),
            'en_attente': len([p for p in presences if p.presence == 'en_attente'])
        }
        
        if stats['total'] > 0:
            stats['taux_presence'] = round((stats['present'] / stats['total']) * 100, 1)
        else:
            stats['taux_presence'] = 0
        
        return stats
    
    def send_invitations_bulk(self, event_id: int, type_invitation: TypeInvitation, 
                             target_ids: List[int], db: Session) -> List[InvitationEvent]:
        """Envoyer des invitations en masse"""
        invitations = []
        
        for target_id in target_ids:
            invitation_data = InvitationEventCreate(
                event_id=event_id,
                type_invitation=type_invitation,
                inscription_id=target_id,
                token_invitation=self.generate_invitation_token()
            )
            
            invitation = self.create_invitation(invitation_data, db)
            invitations.append(invitation)
        
        # Envoyer les emails d'invitation
        for invitation in invitations:
            self._send_invitation_email(invitation, db)
        
        return invitations
    
    def remove_participant_from_event(self, event_id: int, inscription_id: int, db: Session) -> bool:
        """Supprimer un participant d'un événement (invitation + présence)"""
        try:
            # Supprimer l'invitation
            invitation_query = select(InvitationEvent).where(
                InvitationEvent.event_id == event_id,
                InvitationEvent.inscription_id == inscription_id
            )
            invitation = db.exec(invitation_query).first()
            if invitation:
                db.delete(invitation)
                print(f"   🗑️ Invitation supprimée pour inscription {inscription_id}")
            
            # Supprimer la présence
            presence_query = select(PresenceEvent).where(
                PresenceEvent.event_id == event_id,
                PresenceEvent.inscription_id == inscription_id
            )
            presence = db.exec(presence_query).first()
            if presence:
                db.delete(presence)
                print(f"   🗑️ Présence supprimée pour inscription {inscription_id}")
            
            db.commit()
            return True
        except Exception as e:
            print(f"Erreur lors de la suppression du participant: {e}")
            db.rollback()
            return False
    
    def _send_invitation_email(self, invitation: InvitationEvent, db: Session):
        """Envoyer un email d'invitation"""
        # Récupérer les informations nécessaires
        event = db.get(Event, invitation.event_id)
        if not event:
            return
        
        if invitation.type_invitation == TypeInvitation.INDIVIDUELLE and invitation.inscription_id:
            from app_lia_web.app.models.base import Inscription
            inscription = db.get(Inscription, invitation.inscription_id)
            if inscription and inscription.candidat:
                email = inscription.candidat.email
                nom = f"{inscription.candidat.prenom} {inscription.candidat.nom}"
            else:
                return
        else:
            # Pour les invitations par promotion, on enverra un email générique
            return
        
        # Préparer le contenu de l'email
        subject = f"Invitation à l'événement : {event.titre}"
        
        # Générer les URLs dynamiquement
        from app_lia_web.core.config import settings
        base_url = settings.get_base_url_for_email()
        
        template_data = {
            'nom': nom,
            'event_titre': event.titre,
            'event_description': event.description,
            'date_debut': event.date_debut.strftime('%d/%m/%Y'),
            'date_fin': event.date_fin.strftime('%d/%m/%Y'),
            'lieu': event.lieu,
            'token': invitation.token_invitation,
            'base_url': base_url,
            'accept_url': f"{base_url}/events/invitation/{invitation.token_invitation}/accepter",
            'reject_url': f"{base_url}/events/invitation/{invitation.token_invitation}/refuser"
        }
        
        # Envoyer l'email
        try:
            self.email_service.send_template_email(
                to_email=email,
                subject=subject,
                template="event_invitation",
                data=template_data
            )
            # Marquer l'email comme envoyé
            invitation.email_envoye = email
            invitation.date_envoi = datetime.now(timezone.utc)
            db.commit()
        except Exception as e:
            print(f"Erreur envoi email invitation événement: {e}")
