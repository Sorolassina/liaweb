from sqlmodel import Session, select
from sqlalchemy import text
from datetime import datetime, timezone
from typing import List, Optional, Dict
import secrets
import string
import logging
from ..models.event import Event, InvitationEvent, PresenceEvent
from ..models.enums import TypeInvitation
from ..schemas.event_schemas import EventCreate, EventUpdate, InvitationEventCreate, PresenceEventCreate
from .email_service import EmailService
from ..core.program_schema_integration import table_exists_anywhere

logger = logging.getLogger(__name__)

class EventService:
    def __init__(self):
        self.email_service = EmailService()
    
    # === GESTION DES ÉVÉNEMENTS ===
    
    def create_event(self, event_data: EventCreate, db: Session, schema_name: str = 'acd') -> Optional[Dict]:
        """Créer un nouvel événement avec requête SQL directe"""
        try:
            # Rollback en cas de transaction échouée
            try:
                db.rollback()
            except:
                pass
            
            # Configurer le search_path
            db.exec(text(f"SET search_path TO {schema_name}, public"))
            
            # Préparer les valeurs pour l'insertion
            now = datetime.now(timezone.utc)
            statut = 'PLANIFIE'
            
            # Construire la requête INSERT avec le schéma explicite
            insert_query = text(f"""
                INSERT INTO {schema_name}.event 
                (titre, description, programme_id, date_debut, date_fin, heure_debut, heure_fin, 
                 lieu, statut, organisateur_id, cree_le)
                VALUES 
                (:titre, :description, :programme_id, :date_debut, :date_fin, :heure_debut, :heure_fin,
                 :lieu, :statut, :organisateur_id, :cree_le)
                RETURNING id
            """)
            
            result = db.exec(insert_query.bindparams(
                titre=event_data.titre,
                description=event_data.description,
                programme_id=event_data.programme_id,
                date_debut=event_data.date_debut,
                date_fin=event_data.date_fin,
                heure_debut=event_data.heure_debut,
                heure_fin=event_data.heure_fin,
                lieu=event_data.lieu,
                statut=statut,
                organisateur_id=event_data.organisateur_id,
                cree_le=now
            )).first()
            
            db.commit()
            
            if result:
                return {"id": result.id}
            return None
        except Exception as e:
            db.rollback()
            logger.error(f"❌ Erreur lors de la création de l'événement: {str(e)}", exc_info=True)
            return None
    
    def get_event(self, event_id: int, db: Session, schema_name: str = 'acd') -> Optional[Dict]:
        """Récupérer un événement avec requête SQL directe"""
        try:
            # Rollback en cas de transaction échouée
            try:
                db.rollback()
            except:
                pass
            
            # Configurer le search_path
            db.exec(text(f"SET search_path TO {schema_name}, public"))
            
            # Requête SQL directe
            query = text(f"""
                SELECT e.id, e.titre, e.description, e.programme_id, e.date_debut, e.date_fin,
                       e.heure_debut, e.heure_fin, e.lieu, e.statut, e.organisateur_id,
                       e.cree_le, e.modifie_le,
                       p.nom as programme_nom, p.code as programme_code,
                       u.nom_complet as organisateur_nom
                FROM {schema_name}.event e
                LEFT JOIN public.programme p ON e.programme_id = p.id
                LEFT JOIN public."user" u ON e.organisateur_id = u.id
                WHERE e.id = :event_id
            """)
            
            result = db.exec(query.bindparams(event_id=event_id)).first()
            
            if result:
                return {
                    'id': result.id,
                    'titre': result.titre,
                    'description': result.description,
                    'programme_id': result.programme_id,
                    'date_debut': result.date_debut,
                    'date_fin': result.date_fin,
                    'heure_debut': result.heure_debut,
                    'heure_fin': result.heure_fin,
                    'lieu': result.lieu,
                    'statut': result.statut,
                    'organisateur_id': result.organisateur_id,
                    'organisateur_nom': result.organisateur_nom,
                    'programme_nom': result.programme_nom,
                    'programme_code': result.programme_code,
                    'cree_le': result.cree_le,
                    'modifie_le': result.modifie_le
                }
            return None
        except Exception as e:
            logger.error(f"❌ Erreur lors de la récupération de l'événement: {str(e)}", exc_info=True)
            return None
    
    def get_events(self, db: Session, skip: int = 0, limit: int = 100, programme_id: Optional[int] = None) -> List[Event]:
        # Vérifier l'existence de la table event
        if not table_exists_anywhere("event", db):
            print(f"⚠️ [WARNING] Table 'event' manquante")
            return []
        
        try:
            query = select(Event)
            if programme_id:
                query = query.where(Event.programme_id == programme_id)
            query = query.offset(skip).limit(limit)
            return db.exec(query).all()
        except Exception as e:
            print(f"⚠️ [WARNING] Erreur lors de la récupération des événements: {e}")
            return []
    
    def update_event(self, event_id: int, event_data: EventUpdate, db: Session, schema_name: str = 'acd') -> Optional[Dict]:
        """Mettre à jour un événement avec requête SQL directe"""
        try:
            # Rollback en cas de transaction échouée
            try:
                db.rollback()
            except:
                pass
            
            # Configurer le search_path
            db.exec(text(f"SET search_path TO {schema_name}, public"))
            
            # Construire la requête UPDATE
            update_fields = []
            params = {"event_id": event_id}
            
            event_dict = event_data.dict(exclude_unset=True)
            for field, value in event_dict.items():
                if field in ['titre', 'description', 'date_debut', 'date_fin', 'heure_debut', 'heure_fin', 'lieu', 'programme_id', 'statut']:
                    update_fields.append(f"{field} = :{field}")
                    params[field] = value
            
            if not update_fields:
                return None
            
            update_fields.append("modifie_le = CURRENT_TIMESTAMP")
            
            update_query = text(f"""
                UPDATE {schema_name}.event
                SET {', '.join(update_fields)}
                WHERE id = :event_id
                RETURNING id, titre, description, programme_id, date_debut, date_fin,
                          heure_debut, heure_fin, lieu, statut, organisateur_id,
                          cree_le, modifie_le
            """)
            
            result = db.exec(update_query.bindparams(**params)).first()
            db.commit()
            
            if result:
                return {
                    'id': result.id,
                    'titre': result.titre,
                    'description': result.description,
                    'programme_id': result.programme_id,
                    'date_debut': result.date_debut,
                    'date_fin': result.date_fin,
                    'heure_debut': result.heure_debut,
                    'heure_fin': result.heure_fin,
                    'lieu': result.lieu,
                    'statut': result.statut,
                    'organisateur_id': result.organisateur_id,
                    'cree_le': result.cree_le,
                    'modifie_le': result.modifie_le
                }
            return None
        except Exception as e:
            db.rollback()
            logger.error(f"❌ Erreur lors de la mise à jour de l'événement: {str(e)}", exc_info=True)
            raise
    
    def delete_event(self, event_id: int, db: Session) -> bool:
        event = db.get(Event, event_id)
        if not event:
            return False
        
        db.delete(event)
        db.commit()
        return True
    
    def get_event_stats(self, db: Session, schema_name: str = 'acd') -> Dict[str, int]:
        """Récupérer les statistiques des événements avec requête SQL directe"""
        try:
            from sqlalchemy import text
            
            # Configurer le search_path
            db.exec(text(f"SET search_path TO {schema_name}, public"))
            
            # Vérifier l'existence de la table event
            if not table_exists_anywhere("event", db, schema_name):
                logger.warning(f"⚠️ Table 'event' manquante pour les statistiques")
                return {"total_events": 0, "events_planifies": 0, "events_en_cours": 0, "events_termines": 0}
            
            # Requête SQL directe
            query = text(f"""
                SELECT 
                    COUNT(*) as total,
                    COUNT(*) FILTER (WHERE LOWER(statut) = 'planifie') as planifies,
                    COUNT(*) FILTER (WHERE LOWER(statut) = 'en_cours') as en_cours,
                    COUNT(*) FILTER (WHERE LOWER(statut) = 'termine') as termines
                FROM {schema_name}.event
            """)
            
            result = db.exec(query).first()
            
            return {
                'total_events': result.total if result else 0,
                'events_planifies': result.planifies if result else 0,
                'events_en_cours': result.en_cours if result else 0,
                'events_termines': result.termines if result else 0
            }
        except Exception as e:
            logger.error(f"❌ Erreur lors de la récupération des statistiques événements: {e}")
            return {"total_events": 0, "events_planifies": 0, "events_en_cours": 0, "events_termines": 0}
    
    # === GESTION DES INVITATIONS D'ÉVÉNEMENTS ===
    
    def create_invitation(self, invitation_data: InvitationEventCreate, db: Session, schema_name: str = 'acd') -> dict:
        """Créer une invitation avec requête SQL directe"""
        try:
            # Rollback en cas de transaction échouée
            try:
                db.rollback()
            except:
                pass
            
            # Configurer le search_path
            db.exec(text(f"SET search_path TO {schema_name}, public"))
            
            # Convertir les enums en strings
            type_invitation_str = invitation_data.type_invitation.value if hasattr(invitation_data.type_invitation, 'value') else str(invitation_data.type_invitation)
            # Le statut est toujours "envoyee" lors de la création (comme pour les séminaires)
            statut_str = "envoyee"
            
            # Requête SQL directe pour insérer l'invitation
            query = text(f"""
                INSERT INTO {schema_name}.invitation_event 
                (type_invitation, statut, token_invitation, date_envoi, date_reponse, event_id, candidat_id, cree_le, modifie_le)
                VALUES (:type_invitation, :statut, :token_invitation, :date_envoi, :date_reponse, :event_id, :candidat_id, :cree_le, :modifie_le)
                RETURNING id, type_invitation, statut, token_invitation, date_envoi, date_reponse, event_id, candidat_id, cree_le, modifie_le
            """)
            
            result = db.exec(query.bindparams(
                type_invitation=type_invitation_str,
                statut=statut_str,
                token_invitation=invitation_data.token_invitation,
                date_envoi=invitation_data.date_envoi,
                date_reponse=invitation_data.date_reponse,
                event_id=invitation_data.event_id,
                candidat_id=invitation_data.candidat_id,
                cree_le=datetime.now(timezone.utc),
                modifie_le=None
            )).first()
            
            db.commit()
            
            # Retourner un dictionnaire avec la structure attendue
            return {
                'id': result.id,
                'type_invitation': result.type_invitation,
                'statut': result.statut,
                'token_invitation': result.token_invitation,
                'date_envoi': result.date_envoi,
                'date_reponse': result.date_reponse,
                'event_id': result.event_id,
                'candidat_id': result.candidat_id,
                'cree_le': result.cree_le,
                'modifie_le': result.modifie_le
            }
        except Exception as e:
            db.rollback()
            logger.error(f"❌ Erreur lors de la création de l'invitation: {str(e)}", exc_info=True)
            raise
    
    def get_invitations_by_event(self, event_id: int, db: Session, schema_name: str = 'acd') -> List[dict]:
        """Récupérer les invitations d'un événement avec requête SQL directe"""
        try:
            # Rollback en cas de transaction échouée
            try:
                db.rollback()
            except:
                pass
            
            # Configurer le search_path
            db.exec(text(f"SET search_path TO {schema_name}, public"))
            
            # Requête SQL directe
            query = text(f"""
                SELECT i.id, i.event_id, i.type_invitation, i.candidat_id, i.statut,
                       i.date_envoi, i.date_reponse, i.token_invitation, i.cree_le,
                       c.nom as candidat_nom, c.prenom as candidat_prenom, c.email as candidat_email,
                       c.photo_profil as candidat_photo_profil
                FROM {schema_name}.invitation_event i
                LEFT JOIN {schema_name}.candidat c ON i.candidat_id = c.id
                WHERE i.event_id = :event_id
                ORDER BY c.nom, c.prenom
            """)
            
            results = db.exec(query.bindparams(event_id=event_id)).all()
            
            invitations = []
            for row in results:
                # Convertir le type_invitation en string si c'est un enum
                type_invitation_str = str(row.type_invitation)
                if hasattr(row.type_invitation, 'value'):
                    type_invitation_str = row.type_invitation.value
                
                # Convertir le statut en string si c'est un enum
                statut_str = str(row.statut)
                if hasattr(row.statut, 'value'):
                    statut_str = row.statut.value
                
                invitation_dict = {
                    'id': row.id,
                    'event_id': row.event_id,
                    'type_invitation': type_invitation_str,
                    'candidat_id': row.candidat_id,
                    'statut': statut_str,
                    'date_envoi': row.date_envoi,
                    'date_reponse': row.date_reponse,
                    'token_invitation': row.token_invitation,
                    'cree_le': row.cree_le,
                    'candidat_nom': row.candidat_nom,
                    'candidat_prenom': row.candidat_prenom,
                    'candidat_email': row.candidat_email,
                    'candidat_photo_profil': row.candidat_photo_profil,
                    'candidat': type('Candidat', (), {
                        'id': row.candidat_id,
                        'nom': row.candidat_nom,
                        'prenom': row.candidat_prenom,
                        'email': row.candidat_email,
                        'photo_profil': row.candidat_photo_profil
                    })() if row.candidat_id else None
                }
                invitations.append(invitation_dict)
            
            return invitations
        except Exception as e:
            logger.error(f"❌ Erreur lors de la récupération des invitations: {str(e)}", exc_info=True)
            # Rollback en cas d'erreur
            try:
                db.rollback()
            except:
                pass
            return []
    
    def get_invitation_by_token(self, token: str, db: Session, schema_name: str = 'acd') -> Optional[dict]:
        """Récupérer une invitation par token avec requête SQL directe"""
        try:
            # Configurer le search_path
            db.exec(text(f"SET search_path TO {schema_name}, public"))
            
            # Requête SQL directe
            query = text(f"""
                SELECT i.id, i.event_id, i.type_invitation, i.candidat_id, i.statut,
                       i.date_envoi, i.date_reponse, i.token_invitation, i.cree_le,
                       c.nom as candidat_nom, c.prenom as candidat_prenom, c.email as candidat_email,
                       c.photo_profil as candidat_photo_profil
                FROM {schema_name}.invitation_event i
                LEFT JOIN {schema_name}.candidat c ON i.candidat_id = c.id
                WHERE i.token_invitation = :token
            """)
            
            result = db.exec(query.bindparams(token=token)).first()
            if not result:
                return None
            
            # Convertir le type_invitation en string si c'est un enum
            type_invitation_str = str(result.type_invitation)
            if hasattr(result.type_invitation, 'value'):
                type_invitation_str = result.type_invitation.value
            
            # Convertir le statut en string si c'est un enum
            statut_str = str(result.statut)
            if hasattr(result.statut, 'value'):
                statut_str = result.statut.value
            
            return {
                'id': result.id,
                'event_id': result.event_id,
                'type_invitation': type_invitation_str,
                'candidat_id': result.candidat_id,
                'statut': statut_str,
                'date_envoi': result.date_envoi,
                'date_reponse': result.date_reponse,
                'token_invitation': result.token_invitation,
                'cree_le': result.cree_le,
                'candidat_nom': result.candidat_nom,
                'candidat_prenom': result.candidat_prenom,
                'candidat_email': result.candidat_email,
                'candidat_photo_profil': result.candidat_photo_profil
            }
        except Exception as e:
            logger.error(f"❌ Erreur lors de la récupération de l'invitation: {str(e)}", exc_info=True)
            return None
    
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
    
    def accept_invitation(self, token: str, db: Session, schema_name: str = 'acd') -> Optional[dict]:
        """Accepter une invitation via token avec requête SQL directe"""
        try:
            # Configurer le search_path
            db.exec(text(f"SET search_path TO {schema_name}, public"))
            
            # Récupérer l'invitation
            invitation = self.get_invitation_by_token(token, db, schema_name)
            if not invitation or str(invitation.get('statut', '')).lower() != "envoyee":
                return invitation
            
            # Mettre à jour le statut
            now = datetime.now(timezone.utc)
            update_query = text(f"""
                UPDATE {schema_name}.invitation_event
                SET statut = 'acceptee', date_reponse = :date_reponse
                WHERE token_invitation = :token
            """)
            db.exec(update_query.bindparams(token=token, date_reponse=now))
            db.commit()
            
            # Retourner l'invitation mise à jour
            return self.get_invitation_by_token(token, db, schema_name)
        except Exception as e:
            db.rollback()
            logger.error(f"❌ Erreur lors de l'acceptation de l'invitation: {str(e)}", exc_info=True)
            raise e

    def reject_invitation(self, token: str, db: Session, schema_name: str = 'acd') -> Optional[dict]:
        """Refuser une invitation via token avec requête SQL directe"""
        try:
            # Configurer le search_path
            db.exec(text(f"SET search_path TO {schema_name}, public"))
            
            # Récupérer l'invitation
            invitation = self.get_invitation_by_token(token, db, schema_name)
            if not invitation or str(invitation.get('statut', '')).lower() != "envoyee":
                return invitation
            
            # Mettre à jour le statut
            now = datetime.now(timezone.utc)
            update_query = text(f"""
                UPDATE {schema_name}.invitation_event
                SET statut = 'refusee', date_reponse = :date_reponse
                WHERE token_invitation = :token
            """)
            db.exec(update_query.bindparams(token=token, date_reponse=now))
            db.commit()
            
            # Retourner l'invitation mise à jour
            return self.get_invitation_by_token(token, db, schema_name)
        except Exception as e:
            db.rollback()
            logger.error(f"❌ Erreur lors du refus de l'invitation: {str(e)}", exc_info=True)
            raise e
    
    # === GESTION DES PRÉSENCES D'ÉVÉNEMENTS ===
    
    def create_presence(self, presence_data: PresenceEventCreate, db: Session, schema_name: str = 'acd') -> Dict:
        """Créer une présence avec requête SQL directe"""
        try:
            # Rollback en cas de transaction échouée
            try:
                db.rollback()
            except:
                pass
            
            # Configurer le search_path
            db.exec(text(f"SET search_path TO {schema_name}, public"))
            
            # Préparer les données
            presence_dict = presence_data.dict()
            if presence_data.signature_digitale or presence_data.signature_manuelle:
                presence_dict['presence'] = "present"
            
            # Construire la requête INSERT
            insert_query = text(f"""
                INSERT INTO {schema_name}.presence_event 
                (event_id, candidat_id, presence, methode_signature, signature_manuelle, 
                 signature_digitale, photo_signature, heure_arrivee, heure_depart, commentaire, 
                 ip_signature, user_agent, cree_le)
                VALUES 
                (:event_id, :candidat_id, :presence, :methode_signature, :signature_manuelle,
                 :signature_digitale, :photo_signature, :heure_arrivee, :heure_depart, :commentaire,
                 :ip_signature, :user_agent, CURRENT_TIMESTAMP)
                RETURNING id, event_id, candidat_id, presence, methode_signature,
                          signature_manuelle, signature_digitale, photo_signature,
                          heure_arrivee, heure_depart, commentaire, cree_le, modifie_le
            """)
            
            params = {
                'event_id': presence_dict.get('event_id'),
                'candidat_id': presence_dict.get('candidat_id'),
                'presence': presence_dict.get('presence', 'en_attente'),
                'methode_signature': presence_dict.get('methode_signature'),
                'signature_manuelle': presence_dict.get('signature_manuelle'),
                'signature_digitale': presence_dict.get('signature_digitale'),
                'photo_signature': presence_dict.get('photo_signature'),
                'heure_arrivee': presence_dict.get('heure_arrivee'),
                'heure_depart': presence_dict.get('heure_depart'),
                'commentaire': presence_dict.get('commentaire'),
                'ip_signature': presence_dict.get('ip_signature'),
                'user_agent': presence_dict.get('user_agent')
            }
            
            result = db.exec(insert_query.bindparams(**params)).first()
            db.commit()
            
            if result:
                return {
                    'id': result.id,
                    'event_id': result.event_id,
                    'candidat_id': result.candidat_id,
                    'presence': result.presence,
                    'methode_signature': result.methode_signature,
                    'signature_manuelle': result.signature_manuelle,
                    'signature_digitale': result.signature_digitale,
                    'photo_signature': result.photo_signature,
                    'heure_arrivee': result.heure_arrivee,
                    'heure_depart': result.heure_depart,
                    'commentaire': result.commentaire,
                    'cree_le': result.cree_le,
                    'modifie_le': result.modifie_le
                }
            raise Exception("Erreur lors de la création de la présence")
        except Exception as e:
            db.rollback()
            logger.error(f"❌ Erreur lors de la création de la présence: {str(e)}", exc_info=True)
            raise
    
    def get_presence_candidat(self, event_id: int, candidat_id: int, db: Session, schema_name: str = 'acd') -> Optional[dict]:
        """Récupérer la présence d'un candidat avec requête SQL directe"""
        try:
            # Rollback en cas de transaction échouée
            try:
                db.rollback()
            except:
                pass
            
            # Configurer le search_path
            db.exec(text(f"SET search_path TO {schema_name}, public"))
            
            # Requête SQL directe
            query = text(f"""
                SELECT id, event_id, candidat_id, presence, methode_signature,
                       signature_manuelle, signature_digitale, photo_signature,
                       heure_arrivee, commentaire, ip_signature, cree_le, modifie_le
                FROM {schema_name}.presence_event
                WHERE event_id = :event_id AND candidat_id = :candidat_id
            """)
            
            result = db.exec(query.bindparams(event_id=event_id, candidat_id=candidat_id)).first()
            
            if result:
                return {
                    'id': result.id,
                    'event_id': result.event_id,
                    'candidat_id': result.candidat_id,
                    'presence': result.presence,
                    'methode_signature': str(result.methode_signature) if result.methode_signature else None,
                    'signature_manuelle': result.signature_manuelle,
                    'signature_digitale': result.signature_digitale,
                    'photo_signature': result.photo_signature,
                    'heure_arrivee': result.heure_arrivee,
                    'commentaire': result.commentaire,
                    'ip_signature': result.ip_signature,
                    'cree_le': result.cree_le,
                    'modifie_le': result.modifie_le
                }
            return None
        except Exception as e:
            logger.error(f"❌ Erreur lors de la récupération de la présence: {str(e)}", exc_info=True)
            return None
    
    def mark_presence(self, presence_data: PresenceEventCreate, db: Session, schema_name: str = 'acd') -> Dict:
        """Marquer une présence - ne modifie QUE le statut de présence, pas l'invitation"""
        logger.debug(f"🔍 MARK_PRESENCE - Event {presence_data.event_id}, Candidat {presence_data.candidat_id}, Statut: {presence_data.presence}")
        
        # Rollback en cas de transaction échouée
        try:
            db.rollback()
        except:
            pass
        
        # Configurer le search_path
        db.exec(text(f"SET search_path TO {schema_name}, public"))
        
        existing_presence = self.get_presence_candidat(presence_data.event_id, presence_data.candidat_id, db, schema_name)
        
        # Préparer les données
        presence_dict = presence_data.dict()
        if presence_data.signature_digitale or presence_data.signature_manuelle:
            presence_dict['presence'] = "present"
            logger.debug(f"   ✍️ Signature détectée - Statut automatiquement mis à 'present'")
        
        if existing_presence:
            logger.debug(f"   📝 Présence existante trouvée: {existing_presence.get('presence')}")
            
            # Construire la requête UPDATE
            update_fields = []
            params = {
                "event_id": presence_data.event_id,
                "candidat_id": presence_data.candidat_id
            }
            
            for field, value in presence_dict.items():
                if field not in ['event_id', 'candidat_id'] and value is not None:
                    update_fields.append(f"{field} = :{field}")
                    params[field] = value
            
            if update_fields:
                update_fields.append("modifie_le = CURRENT_TIMESTAMP")
                
                update_query = text(f"""
                    UPDATE {schema_name}.presence_event
                    SET {', '.join(update_fields)}
                    WHERE event_id = :event_id AND candidat_id = :candidat_id
                    RETURNING id, event_id, candidat_id, presence, methode_signature,
                              signature_manuelle, signature_digitale, photo_signature,
                              heure_arrivee, heure_depart, commentaire, cree_le, modifie_le
                """)
                
                result = db.exec(update_query.bindparams(**params)).first()
                db.commit()
                
                if result:
                    presence_obj = {
                        'id': result.id,
                        'event_id': result.event_id,
                        'candidat_id': result.candidat_id,
                        'presence': result.presence,
                        'methode_signature': result.methode_signature,
                        'signature_manuelle': result.signature_manuelle,
                        'signature_digitale': result.signature_digitale,
                        'photo_signature': result.photo_signature,
                        'heure_arrivee': result.heure_arrivee,
                        'heure_depart': result.heure_depart,
                        'commentaire': result.commentaire,
                        'cree_le': result.cree_le,
                        'modifie_le': result.modifie_le
                    }
                    logger.debug(f"   ✅ Présence mise à jour: {presence_obj['presence']}")
                    return presence_obj
        else:
            logger.debug(f"   ➕ Création nouvelle présence")
            presence_obj = self.create_presence(presence_data, db, schema_name)
            logger.debug(f"   ✅ Nouvelle présence créée: {presence_obj.get('presence') if isinstance(presence_obj, dict) else presence_obj.presence}")
            return presence_obj
        
        raise Exception("Erreur lors de la mise à jour de la présence")
    
    def get_combined_status(self, event_id: int, candidat_id: int, db: Session, schema_name: str = 'acd') -> str:
        """
        Retourne le statut imbriqué pour la page principale :
        - Avant l'événement : privilégie le statut d'invitation
        - Après l'événement : privilégie le statut de présence
        """
        try:
            from datetime import date
            
            # Rollback en cas de transaction échouée
            try:
                db.rollback()
            except:
                pass
            
            # Configurer le search_path
            db.exec(text(f"SET search_path TO {schema_name}, public"))
            
            # Récupérer l'événement pour connaître sa date
            event_dict = self.get_event(event_id, db, schema_name)
            if not event_dict:
                return "en_attente"
            
            today = date.today()
            event_passed = event_dict['date_fin'] < today if event_dict['date_fin'] else False
            
            # Récupérer l'invitation avec requête SQL directe
            invitation_query = text(f"""
                SELECT statut
                FROM {schema_name}.invitation_event
                WHERE event_id = :event_id AND candidat_id = :candidat_id
            """)
            invitation_result = db.exec(invitation_query.bindparams(event_id=event_id, candidat_id=candidat_id)).first()
            
            # Récupérer la présence
            presence = self.get_presence_candidat(event_id, candidat_id, db, schema_name)
            
            if event_passed:
                # APRÈS L'ÉVÉNEMENT : privilégier le statut de présence
                if presence and presence.get('presence') in ['present', 'absent', 'excuse']:
                    return presence.get('presence')
                else:
                    # Pas de présence marquée après l'événement = absent
                    return "absent"
            else:
                # AVANT L'ÉVÉNEMENT : privilégier le statut d'invitation
                if invitation_result:
                    statut_str = str(invitation_result.statut).upper()
                    if statut_str == "REFUSEE":
                        return "refusee"
                    elif statut_str == "ACCEPTEE":
                        return "acceptee"
                    else:
                        return "en_attente"
                else:
                    return "en_attente"
        except Exception as e:
            logger.error(f"❌ Erreur dans get_combined_status: {str(e)}", exc_info=True)
            return "en_attente"
    
    def get_presences_with_combined_status(self, event_id: int, db: Session, schema_name: str = 'acd') -> List[dict]:
        """
        Retourne les présences avec le statut imbriqué pour la page principale
        """
        try:
            # Rollback en cas de transaction échouée
            try:
                db.rollback()
            except:
                pass
            
            # Configurer le search_path
            db.exec(text(f"SET search_path TO {schema_name}, public"))
            
            # Récupérer toutes les invitations pour cet événement avec requête SQL directe
            invitations_query = text(f"""
                SELECT i.id, i.event_id, i.type_invitation, i.candidat_id, i.statut,
                       i.date_envoi, i.date_reponse, i.token_invitation, i.cree_le,
                       c.nom as candidat_nom, c.prenom as candidat_prenom, c.email as candidat_email,
                       c.photo_profil as candidat_photo_profil
                FROM {schema_name}.invitation_event i
                LEFT JOIN {schema_name}.candidat c ON i.candidat_id = c.id
                WHERE i.event_id = :event_id
                ORDER BY c.nom, c.prenom
            """)
            invitations_results = db.exec(invitations_query.bindparams(event_id=event_id)).all()
            
            result = []
            for row in invitations_results:
                # Convertir le type_invitation en string si c'est un enum
                type_invitation_str = str(row.type_invitation)
                if hasattr(row.type_invitation, 'value'):
                    type_invitation_str = row.type_invitation.value
                
                # Convertir le statut en string si c'est un enum
                statut_str = str(row.statut)
                if hasattr(row.statut, 'value'):
                    statut_str = row.statut.value
                
                invitation_dict = {
                    'id': row.id,
                    'event_id': row.event_id,
                    'type_invitation': type_invitation_str,
                    'candidat_id': row.candidat_id,
                    'statut': statut_str,
                    'date_envoi': row.date_envoi,
                    'date_reponse': row.date_reponse,
                    'token_invitation': row.token_invitation,
                    'cree_le': row.cree_le,
                    'candidat_nom': row.candidat_nom,
                    'candidat_prenom': row.candidat_prenom,
                    'candidat_email': row.candidat_email,
                    'candidat_photo_profil': row.candidat_photo_profil
                }
                
                # Récupérer la présence existante
                presence = self.get_presence_candidat(event_id, row.candidat_id, db, schema_name)
                
                # Calculer le statut imbriqué
                combined_status = self.get_combined_status(event_id, row.candidat_id, db, schema_name)
                
                # Créer l'objet de résultat
                presence_data = {
                    'invitation': invitation_dict,
                    'presence': presence,
                    'combined_status': combined_status,
                    'candidat_id': row.candidat_id
                }
                
                result.append(presence_data)
            
            return result
        except Exception as e:
            logger.error(f"❌ Erreur dans get_presences_with_combined_status: {str(e)}", exc_info=True)
            return []
    
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
                'candidat_id': invitation.candidat_id,
                'date_envoi': invitation.date_envoi.strftime('%Y-%m-%d %H:%M') if invitation.date_envoi else None,
                'date_reponse': invitation.date_reponse.strftime('%Y-%m-%d %H:%M') if invitation.date_reponse else None
            })
        
        # Détail des présences existantes
        for presence in existing_presences:
            debug_info['presences_detail'].append({
                'id': presence.id,
                'presence': presence.presence,
                'candidat_id': presence.candidat_id,
                'methode_signature': presence.methode_signature,
                'heure_arrivee': presence.heure_arrivee.strftime('%Y-%m-%d %H:%M') if presence.heure_arrivee else None
            })
        
        return debug_info
    
    def get_presences_with_invitations(self, event_id: int, db: Session, schema_name: str = 'acd') -> List[dict]:
        """
        Récupère toutes les présences d'un événement avec les invitations
        Utilisé pour la page d'émargement - retourne les statuts de présence purs
        """
        try:
            # Rollback en cas de transaction échouée
            try:
                db.rollback()
            except:
                pass
            
            # Configurer le search_path
            db.exec(text(f"SET search_path TO {schema_name}, public"))
            
            logger.debug(f"🔍 GET_PRESENCES_WITH_INVITATIONS - Event {event_id}, Schema {schema_name}")
            
            # Récupérer toutes les invitations pour cet événement avec requête SQL directe
            invitations_query = text(f"""
                SELECT i.id, i.event_id, i.type_invitation, i.candidat_id, i.statut,
                       i.date_envoi, i.date_reponse, i.token_invitation, i.cree_le,
                       c.nom as candidat_nom, c.prenom as candidat_prenom, c.email as candidat_email,
                       c.photo_profil as candidat_photo_profil
                FROM {schema_name}.invitation_event i
                LEFT JOIN {schema_name}.candidat c ON i.candidat_id = c.id
                WHERE i.event_id = :event_id AND i.candidat_id IS NOT NULL
                ORDER BY c.nom, c.prenom
            """)
            invitations_results = db.exec(invitations_query.bindparams(event_id=event_id)).all()
            
            presences = []
            for row in invitations_results:
                candidat_id = row.candidat_id
                
                # Récupérer la présence existante avec requête SQL directe
                presence_query = text(f"""
                    SELECT id, event_id, candidat_id, presence, methode_signature,
                           signature_manuelle, signature_digitale, photo_signature,
                           heure_arrivee, commentaire, ip_signature, cree_le, modifie_le
                    FROM {schema_name}.presence_event
                    WHERE event_id = :event_id AND candidat_id = :candidat_id
                """)
                presence_result = db.exec(presence_query.bindparams(event_id=event_id, candidat_id=candidat_id)).first()
                
                if presence_result:
                    logger.debug(f"   📝 Présence trouvée pour candidat {candidat_id}: {presence_result.presence}")
                    # Convertir le statut en string si c'est un enum
                    statut_str = str(row.statut)
                    if hasattr(row.statut, 'value'):
                        statut_str = row.statut.value
                    presences.append({
                        'id': presence_result.id,
                        'event_id': presence_result.event_id,
                        'candidat_id': presence_result.candidat_id,
                        'presence': presence_result.presence,
                        'methode_signature': str(presence_result.methode_signature) if presence_result.methode_signature else None,
                        'signature_manuelle': presence_result.signature_manuelle,
                        'signature_digitale': presence_result.signature_digitale,
                        'photo_signature': presence_result.photo_signature,
                        'heure_arrivee': presence_result.heure_arrivee,
                        'commentaire': presence_result.commentaire,
                        'ip_signature': presence_result.ip_signature,
                        'cree_le': presence_result.cree_le,
                        'modifie_le': presence_result.modifie_le,
                        'candidat_nom': row.candidat_nom,
                        'candidat_prenom': row.candidat_prenom,
                        'candidat_email': row.candidat_email,
                        'candidat_photo_profil': row.candidat_photo_profil,
                        'invitation_statut': statut_str
                    })
                else:
                    # Créer une présence par défaut avec requête SQL directe
                    now = datetime.now(timezone.utc)
                    insert_query = text(f"""
                        INSERT INTO {schema_name}.presence_event
                        (event_id, candidat_id, presence, cree_le)
                        VALUES (:event_id, :candidat_id, 'en_attente', :cree_le)
                        RETURNING id, event_id, candidat_id, presence, cree_le
                    """)
                    new_presence_result = db.exec(insert_query.bindparams(
                        event_id=event_id,
                        candidat_id=candidat_id,
                        cree_le=now
                    )).first()
                    
                    if new_presence_result:
                        logger.debug(f"   ➕ Nouvelle présence créée pour candidat {candidat_id}: {new_presence_result.presence}")
                        # Convertir le statut en string si c'est un enum
                        statut_str = str(row.statut)
                        if hasattr(row.statut, 'value'):
                            statut_str = row.statut.value
                        presences.append({
                            'id': new_presence_result.id,
                            'event_id': new_presence_result.event_id,
                            'candidat_id': new_presence_result.candidat_id,
                            'presence': new_presence_result.presence,
                            'methode_signature': None,
                            'signature_manuelle': None,
                            'signature_digitale': None,
                            'photo_signature': None,
                            'heure_arrivee': None,
                            'commentaire': None,
                            'ip_signature': None,
                            'cree_le': new_presence_result.cree_le,
                            'modifie_le': None,
                            'candidat_nom': row.candidat_nom,
                            'candidat_prenom': row.candidat_prenom,
                            'candidat_email': row.candidat_email,
                            'candidat_photo_profil': row.candidat_photo_profil,
                            'invitation_statut': statut_str
                        })
            
            db.commit()
            logger.debug(f"   📊 Total présences retournées: {len(presences)}")
            return presences
        except Exception as e:
            db.rollback()
            logger.error(f"❌ Erreur dans get_presences_with_invitations: {str(e)}", exc_info=True)
            return []
    
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
    
    def get_presence_stats_with_invitations(self, event_id: int, db: Session, schema_name: str = 'acd') -> Dict[str, int]:
        presences = self.get_presences_with_invitations(event_id, db, schema_name)
        stats = {
            'total': len(presences),
            'present': len([p for p in presences if p.get('presence') == 'present']),
            'absent': len([p for p in presences if p.get('presence') == 'absent']),
            'excuse': len([p for p in presences if p.get('presence') == 'excuse']),
            'en_attente': len([p for p in presences if p.get('presence') == 'en_attente'])
        }
        
        if stats['total'] > 0:
            stats['taux_presence'] = round((stats['present'] / stats['total']) * 100, 1)
        else:
            stats['taux_presence'] = 0
        
        return stats
    
    def send_invitations_bulk(self, event_id: int, type_invitation: TypeInvitation, 
                             target_ids: List[int], db: Session, schema_name: str = 'acd') -> List[dict]:
        """Envoyer des invitations en masse avec requête SQL directe"""
        logger.info(f"🚀 [send_invitations_bulk] Début - Event {event_id}, Type: {type_invitation}, Candidats: {len(target_ids)}, Schema: {schema_name}")
        logger.debug(f"   📋 Liste target_ids: {target_ids}")
        invitations = []
        
        try:
            # Rollback en cas de transaction échouée
            try:
                db.rollback()
            except:
                pass
            
            # Configurer le search_path
            db.exec(text(f"SET search_path TO {schema_name}, public"))
            
            for target_id in target_ids:
                invitation_data = InvitationEventCreate(
                    event_id=event_id,
                    type_invitation=type_invitation,
                    candidat_id=target_id,
                    token_invitation=self.generate_invitation_token()
                )
                
                invitation = self.create_invitation(invitation_data, db, schema_name)
                invitations.append(invitation)
            
            db.commit()
            
            # Envoyer les emails d'invitation
            logger.info(f"📧 Envoi de {len(invitations)} emails d'invitation pour l'événement {event_id}")
            for invitation in invitations:
                try:
                    logger.debug(f"   📧 Envoi invitation {invitation.get('id')} pour candidat {invitation.get('candidat_id')}")
                    self._send_invitation_email(invitation, db, schema_name)
                except Exception as e:
                    logger.error(f"❌ Erreur lors de l'envoi de l'invitation {invitation.get('id')}: {str(e)}", exc_info=True)
            
            logger.info(f"✅ Traitement de {len(invitations)} invitations terminé")
            return invitations
        except Exception as e:
            db.rollback()
            logger.error(f"❌ Erreur lors de l'envoi des invitations: {str(e)}", exc_info=True)
            raise
    
    def remove_participant_from_event(self, event_id: int, candidat_id: int, db: Session, schema_name: str = 'acd') -> bool:
        """Supprimer un participant d'un événement (invitation + présence)"""
        try:
            # Rollback en cas de transaction échouée
            try:
                db.rollback()
            except:
                pass
            
            # Configurer le search_path
            db.exec(text(f"SET search_path TO {schema_name}, public"))
            
            # Supprimer l'invitation avec requête SQL directe
            invitation_query = text(f"""
                DELETE FROM {schema_name}.invitation_event
                WHERE event_id = :event_id AND candidat_id = :candidat_id
            """)
            db.exec(invitation_query.bindparams(event_id=event_id, candidat_id=candidat_id))
            logger.debug(f"🗑️ Invitation supprimée pour candidat {candidat_id}")
            
            # Supprimer la présence avec requête SQL directe
            presence_query = text(f"""
                DELETE FROM {schema_name}.presence_event
                WHERE event_id = :event_id AND candidat_id = :candidat_id
            """)
            db.exec(presence_query.bindparams(event_id=event_id, candidat_id=candidat_id))
            logger.debug(f"🗑️ Présence supprimée pour candidat {candidat_id}")
            
            db.commit()
            return True
        except Exception as e:
            logger.error(f"❌ Erreur lors de la suppression du participant: {str(e)}", exc_info=True)
            db.rollback()
            return False
    
    def _send_invitation_email(self, invitation: dict, db: Session, schema_name: str = 'acd'):
        """Envoyer un email d'invitation avec requête SQL directe"""
        try:
            logger.info(f"📧 [_send_invitation_email] Début - Invitation {invitation.get('id')}, Type: {invitation.get('type_invitation')}, Candidat: {invitation.get('candidat_id')}")
            # Récupérer l'événement avec requête SQL directe
            event_query = text(f"""
                SELECT id, titre, description, date_debut, date_fin, lieu
                FROM {schema_name}.event
                WHERE id = :event_id
            """)
            event_result = db.exec(event_query.bindparams(event_id=invitation['event_id'])).first()
            if not event_result:
                return
            
            # Convertir en dictionnaire
            event = {
                'id': event_result.id,
                'titre': event_result.titre,
                'description': event_result.description,
                'date_debut': event_result.date_debut,
                'date_fin': event_result.date_fin,
                'lieu': event_result.lieu
            }
            
            # Vérifier le type d'invitation (insensible à la casse)
            type_inv = str(invitation.get('type_invitation', '')).upper()
            logger.debug(f"   🔍 Type invitation: {invitation.get('type_invitation')} -> {type_inv}, Candidat ID: {invitation.get('candidat_id')}")
            if type_inv == 'INDIVIDUELLE' and invitation.get('candidat_id'):
                # Récupérer le candidat avec requête SQL directe
                candidat_query = text(f"""
                    SELECT id, nom, prenom, email
                    FROM {schema_name}.candidat
                    WHERE id = :candidat_id
                """)
                candidat_result = db.exec(candidat_query.bindparams(candidat_id=invitation['candidat_id'])).first()
                if candidat_result:
                    email = candidat_result.email
                    nom = f"{candidat_result.prenom} {candidat_result.nom}"
                    logger.debug(f"   ✅ Candidat trouvé: {nom} ({email})")
                else:
                    logger.warning(f"   ⚠️ Candidat {invitation['candidat_id']} non trouvé")
                    return
            else:
                # Pour les invitations par promotion, on enverra un email générique
                logger.warning(f"   ⚠️ Type d'invitation non individuelle ou candidat_id manquant: type={type_inv}, candidat_id={invitation.get('candidat_id')}")
                return
        
            # Préparer le contenu de l'email
            subject = f"Invitation à l'événement : {event['titre']}"
            
            # Générer les URLs dynamiquement avec le paramètre programme
            from ..core.config import settings
            base_url = settings.get_base_url_for_email()
            
            # Inclure le paramètre programme dans les URLs (comme pour les séminaires)
            accept_url = f"{base_url}/events/invitation/{invitation['token_invitation']}/accepter?programme={schema_name.upper()}"
            reject_url = f"{base_url}/events/invitation/{invitation['token_invitation']}/refuser?programme={schema_name.upper()}"
            
            template_data = {
                'nom': nom,
                'event_titre': event['titre'],
                'event_description': event['description'],
                'date_debut': event['date_debut'].strftime('%d/%m/%Y') if event['date_debut'] else '',
                'date_fin': event['date_fin'].strftime('%d/%m/%Y') if event['date_fin'] else '',
                'lieu': event['lieu'],
                'token': invitation['token_invitation'],
                'base_url': base_url,
                'accept_url': accept_url,
                'reject_url': reject_url
            }
            
            # Envoyer l'email
            try:
                logger.info(f"📧 Tentative d'envoi d'email d'invitation événement à {email}")
                logger.debug(f"   📋 Données template: {template_data}")
                
                email_sent = self.email_service.send_template_email(
                    to_email=email,
                    subject=subject,
                    template="event_invitation",
                    data=template_data
                )
                
                if email_sent:
                    logger.info(f"✅ Email d'invitation événement envoyé avec succès à {email}")
                    # Marquer l'email comme envoyé (mise à jour de date_envoi uniquement)
                    update_query = text(f"""
                        UPDATE {schema_name}.invitation_event
                        SET date_envoi = :date_envoi
                        WHERE id = :invitation_id
                    """)
                    db.exec(update_query.bindparams(
                        date_envoi=datetime.now(timezone.utc),
                        invitation_id=invitation['id']
                    ))
                    db.commit()
                else:
                    logger.error(f"❌ Échec de l'envoi d'email d'invitation événement à {email}")
            except Exception as e:
                logger.error(f"❌ Erreur envoi email invitation événement: {e}", exc_info=True)
        except Exception as e:
            logger.error(f"❌ Erreur dans _send_invitation_email: {str(e)}", exc_info=True)
