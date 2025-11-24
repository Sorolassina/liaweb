# app/services/seminaire_service.py
from sqlmodel import Session, select, and_, or_
from sqlalchemy import text
from typing import List, Optional, Dict, Any
from datetime import datetime, timezone, date
import secrets
import string
import logging
from ..core.database import get_session
from ..core.program_schema_integration import table_exists_anywhere

logger = logging.getLogger(__name__)
from ..models.seminaire import (
    Seminaire, SessionSeminaire, InvitationSeminaire, 
    PresenceSeminaire, LivrableSeminaire, RenduLivrable
)
from ..models.base import Programme, User, Promotion, Candidat
from ..models.enums import StatutSeminaire, TypeInvitation, StatutPresence
from ..schemas.seminaire_schemas import (
    SeminaireCreate, SeminaireUpdate, SessionSeminaireCreate,
    InvitationSeminaireCreate, PresenceSeminaireCreate, LivrableSeminaireCreate
)
from .email_service import EmailService

class SeminaireService:
    def __init__(self):
        self.email_service = EmailService()

    # === GESTION DES SÉMINAIRES ===
    
    def create_seminaire(self, seminaire_data: SeminaireCreate, db: Session, schema_name: str = 'acd') -> Optional[Dict]:
        """Créer un nouveau séminaire avec requête SQL directe"""
        try:
            # Configurer le search_path
            db.exec(text(f"SET search_path TO {schema_name}, public"))
            
            # Préparer les valeurs pour l'insertion
            now = datetime.now(timezone.utc)
            statut = 'PLANIFIE'
            
            # Construire la requête INSERT avec le schéma explicite
            insert_query = text(f"""
                INSERT INTO {schema_name}.seminaire 
                (titre, description, programme_id, date_debut, date_fin, lieu, adresse_complete, 
                 organisateur, capacite_max, statut, actif, invitation_auto, invitation_promos, cree_le)
                VALUES 
                (:titre, :description, :programme_id, :date_debut, :date_fin, :lieu, :adresse_complete,
                 :organisateur, :capacite_max, :statut, :actif, :invitation_auto, :invitation_promos, :cree_le)
                RETURNING id
            """)
            
            params = {
                "titre": seminaire_data.titre,
                "description": seminaire_data.description,
                "programme_id": seminaire_data.programme_id,
                "date_debut": seminaire_data.date_debut,
                "date_fin": seminaire_data.date_fin,
                "lieu": seminaire_data.lieu,
                "adresse_complete": seminaire_data.adresse_complete,
                "organisateur": seminaire_data.organisateur,
                "capacite_max": seminaire_data.capacite_max,
                "statut": statut,
                "actif": True,
                "invitation_auto": seminaire_data.invitation_auto,
                "invitation_promos": seminaire_data.invitation_promos,
                "cree_le": now
            }
            
            query = insert_query.bindparams(**params)
            result = db.exec(query)
            seminaire_id = result.scalar_one()
            db.commit()
            
            # Retourner un dictionnaire avec l'ID
            return {"id": seminaire_id}
        except Exception as e:
            db.rollback()
            raise e

    def get_seminaire(self, seminaire_id: int, db: Session, schema_name: str = 'acd') -> Optional[Dict]:
        """Récupérer un séminaire par son ID avec requête SQL directe"""
        try:
            # Configurer le search_path
            db.exec(text(f"SET search_path TO {schema_name}, public"))
            
            # Récupérer le séminaire via requête SQL directe
            seminaire_query = text(f"""
                SELECT s.id, s.titre, s.description, s.programme_id, s.date_debut, s.date_fin,
                       s.lieu, s.adresse_complete, s.organisateur, s.capacite_max, s.statut,
                       s.actif, s.invitation_auto, s.invitation_promos, s.cree_le, s.modifie_le
                FROM {schema_name}.seminaire s
                WHERE s.id = :seminaire_id
            """)
            
            result = db.exec(seminaire_query.bindparams(seminaire_id=seminaire_id)).first()
            if not result:
                return None
            
            # Convertir en dictionnaire
            return {
                "id": result.id,
                "titre": result.titre,
                "description": result.description,
                "programme_id": result.programme_id,
                "date_debut": result.date_debut,
                "date_fin": result.date_fin,
                "lieu": result.lieu,
                "adresse_complete": result.adresse_complete,
                "organisateur": result.organisateur,
                "capacite_max": result.capacite_max,
                "statut": result.statut,
                "actif": result.actif,
                "invitation_auto": result.invitation_auto,
                "invitation_promos": result.invitation_promos,
                "cree_le": result.cree_le,
                "modifie_le": result.modifie_le
            }
        except Exception as e:
            raise e

    def get_seminaires(self, db: Session, schema_name: str = 'acd', filters: Optional[Dict] = None) -> List[Dict]:
        """Récupérer la liste des séminaires avec filtres via requête SQL directe"""
        try:
            # Configurer le search_path
            db.exec(text(f"SET search_path TO {schema_name}, public"))
            
            # Construire la requête SQL avec filtres
            base_query = f"""
                SELECT s.id, s.titre, s.description, s.programme_id, s.date_debut, s.date_fin,
                       s.lieu, s.adresse_complete, s.organisateur, s.capacite_max, s.statut,
                       s.actif, s.invitation_auto, s.invitation_promos, s.cree_le, s.modifie_le,
                       s.organisateur as organisateur_nom, p.nom as programme_nom, p.code as programme_code
                FROM {schema_name}.seminaire s
                LEFT JOIN public.programme p ON s.programme_id = p.id
            """
            
            where_conditions = []
            params = {}
            
            if filters:
                if filters.get('programme_id'):
                    where_conditions.append("s.programme_id = :programme_id")
                    params['programme_id'] = filters['programme_id']
                if filters.get('statut'):
                    where_conditions.append("LOWER(s.statut) = LOWER(:statut)")
                    params['statut'] = filters['statut']
                if filters.get('organisateur'):
                    where_conditions.append("s.organisateur = :organisateur")
                    params['organisateur'] = filters['organisateur']
                if filters.get('actif') is not None:
                    where_conditions.append("s.actif = :actif")
                    params['actif'] = filters['actif']
                if filters.get('date_debut_from'):
                    where_conditions.append("s.date_debut >= :date_debut_from")
                    params['date_debut_from'] = filters['date_debut_from']
                if filters.get('date_debut_to'):
                    where_conditions.append("s.date_debut <= :date_debut_to")
                    params['date_debut_to'] = filters['date_debut_to']
            
            if where_conditions:
                base_query += " WHERE " + " AND ".join(where_conditions)
            
            base_query += " ORDER BY s.date_debut DESC"
            
            query = text(base_query)
            if params:
                query = query.bindparams(**params)
            
            results = db.exec(query).all()
            
            # Convertir les résultats en dictionnaires
            seminaires = []
            for row in results:
                seminaires.append({
                    'id': row.id,
                    'titre': row.titre,
                    'description': row.description,
                    'programme_id': row.programme_id,
                    'date_debut': row.date_debut,
                    'date_fin': row.date_fin,
                    'lieu': row.lieu,
                    'adresse_complete': row.adresse_complete,
                    'organisateur': row.organisateur,
                    'capacite_max': row.capacite_max,
                    'statut': row.statut,
                    'actif': row.actif,
                    'invitation_auto': row.invitation_auto,
                    'invitation_promos': row.invitation_promos,
                    'cree_le': row.cree_le,
                    'modifie_le': row.modifie_le,
                    'organisateur_nom': row.organisateur_nom,
                    'programme_nom': row.programme_nom,
                    'programme_code': row.programme_code
                })
            
            return seminaires
        except Exception as e:
            print(f"⚠️ [WARNING] Erreur lors de la récupération des séminaires: {e}")
            return []

    def update_seminaire(self, seminaire_id: int, seminaire_data: SeminaireUpdate, db: Session, schema_name: str = 'acd') -> Optional[Dict]:
        """Mettre à jour un séminaire avec requête SQL directe"""
        try:
            # Configurer le search_path
            db.exec(text(f"SET search_path TO {schema_name}, public"))
            
            # Vérifier que le séminaire existe
            check_query = text(f"SELECT id FROM {schema_name}.seminaire WHERE id = :seminaire_id")
            exists = db.exec(check_query.bindparams(seminaire_id=seminaire_id)).first()
            if not exists:
                return None
            
            # Construire la requête UPDATE dynamiquement
            update_data = seminaire_data.dict(exclude_unset=True)
            if not update_data:
                # Aucune donnée à mettre à jour
                return self.get_seminaire(seminaire_id, db, schema_name)
            
            # Construire les clauses SET
            set_clauses = []
            params = {"seminaire_id": seminaire_id}
            
            for field, value in update_data.items():
                set_clauses.append(f"{field} = :{field}")
                params[field] = value
            
            # Toujours mettre à jour modifie_le
            set_clauses.append("modifie_le = :modifie_le")
            params["modifie_le"] = datetime.now(timezone.utc)
            
            update_query = text(f"""
                UPDATE {schema_name}.seminaire 
                SET {', '.join(set_clauses)}
                WHERE id = :seminaire_id
            """)
            
            query = update_query.bindparams(**params)
            db.exec(query)
            db.commit()
            
            # Retourner le séminaire mis à jour
            return self.get_seminaire(seminaire_id, db, schema_name)
        except Exception as e:
            db.rollback()
            raise e

    def delete_seminaire(self, seminaire_id: int, db: Session, schema_name: str = 'acd') -> bool:
        """Supprimer définitivement un séminaire de la base de données"""
        import logging
        logger = logging.getLogger(__name__)
        
        try:
            logger.info(f"🔍 [delete_seminaire] Début - seminaire_id={seminaire_id}, schema_name={schema_name}")
            
            # Configurer le search_path
            logger.info(f"🔍 [delete_seminaire] Configuration du search_path: {schema_name}, public")
            db.exec(text(f"SET search_path TO {schema_name}, public"))
            
            # Vérifier que le séminaire existe
            logger.info(f"🔍 [delete_seminaire] Vérification de l'existence du séminaire {seminaire_id}")
            check_query = text(f"SELECT id FROM {schema_name}.seminaire WHERE id = :seminaire_id")
            exists = db.exec(check_query.bindparams(seminaire_id=seminaire_id)).first()
            
            if not exists:
                logger.warning(f"⚠️ [delete_seminaire] Séminaire {seminaire_id} non trouvé dans le schéma {schema_name}")
                return False
            
            logger.info(f"🔍 [delete_seminaire] Séminaire trouvé - id={exists.id if hasattr(exists, 'id') else exists[0]}")
            
            # Hard delete : supprimer définitivement le séminaire
            # Note: Les contraintes de clé étrangère avec CASCADE supprimeront automatiquement
            # les sessions, invitations, présences, livrables associés
            logger.info(f"🔍 [delete_seminaire] Suppression définitive du séminaire {seminaire_id}")
            delete_query = text(f"""
                DELETE FROM {schema_name}.seminaire 
                WHERE id = :seminaire_id
            """)
            
            result = db.exec(delete_query.bindparams(seminaire_id=seminaire_id))
            logger.info(f"🔍 [delete_seminaire] Requête DELETE exécutée - rows affected: {result.rowcount if hasattr(result, 'rowcount') else 'N/A'}")
            
            logger.info(f"🔍 [delete_seminaire] Commit de la transaction")
            db.commit()
            
            # Vérifier que la suppression a bien été effectuée
            verify_query = text(f"SELECT id FROM {schema_name}.seminaire WHERE id = :seminaire_id")
            verify_result = db.exec(verify_query.bindparams(seminaire_id=seminaire_id)).first()
            if verify_result:
                logger.warning(f"⚠️ [delete_seminaire] Le séminaire {seminaire_id} existe encore après la suppression")
            else:
                logger.info(f"🔍 [delete_seminaire] Vérification post-delete - séminaire {seminaire_id} supprimé avec succès")
            
            logger.info(f"✅ [delete_seminaire] Suppression réussie pour seminaire_id={seminaire_id}")
            return True
        except Exception as e:
            logger.error(f"❌ [delete_seminaire] Erreur lors de la suppression du séminaire {seminaire_id}: {str(e)}", exc_info=True)
            db.rollback()
            raise e
    
    def remove_participant_from_session(self, seminaire_id: int, session_id: int, candidat_id: int, db: Session, schema_name: str = 'acd') -> bool:
        """Supprimer un participant d'une session de séminaire via requête SQL directe"""
        try:
            # Configurer le search_path
            db.exec(text(f"SET search_path TO {schema_name}, public"))
            
            # Supprimer l'invitation au séminaire (pas de session spécifique)
            delete_invitation_query = text(f"""
                DELETE FROM {schema_name}.invitation_seminaire
                WHERE seminaire_id = :seminaire_id AND candidat_id = :candidat_id
            """)
            db.exec(delete_invitation_query.bindparams(seminaire_id=seminaire_id, candidat_id=candidat_id))
            
            # Supprimer la présence de cette session spécifique
            delete_presence_query = text(f"""
                DELETE FROM {schema_name}.presence_seminaire
                WHERE session_id = :session_id AND candidat_id = :candidat_id
            """)
            db.exec(delete_presence_query.bindparams(session_id=session_id, candidat_id=candidat_id))
            
            db.commit()
            return True
            
        except Exception as e:
            db.rollback()
            raise e

    # === GESTION DES SESSIONS ===
    
    def create_session(self, session_data: SessionSeminaireCreate, db: Session, schema_name: str = 'acd') -> Dict:
        """Créer une nouvelle session de séminaire via requête SQL directe"""
        try:
            # Configurer le search_path
            db.exec(text(f"SET search_path TO {schema_name}, public"))
            
            # Préparer les valeurs pour l'insertion
            now = datetime.now(timezone.utc)
            session_dict = session_data.dict()
            
            # Construire la requête INSERT avec le schéma explicite
            insert_query = text(f"""
                INSERT INTO {schema_name}.session_seminaire 
                (seminaire_id, titre, description, type_session, date_session, heure_debut, heure_fin, 
                 lieu, visioconf_url, capacite, obligatoire, cree_le)
                VALUES 
                (:seminaire_id, :titre, :description, :type_session, :date_session, :heure_debut, :heure_fin,
                 :lieu, :visioconf_url, :capacite, :obligatoire, :cree_le)
                RETURNING id
            """)
            
            params = {
                "seminaire_id": session_dict.get('seminaire_id'),
                "titre": session_dict.get('titre'),
                "description": session_dict.get('description'),
                "type_session": str(session_dict.get('type_session', 'SEMINAIRE')),
                "date_session": session_dict.get('date_session'),
                "heure_debut": session_dict.get('heure_debut'),
                "heure_fin": session_dict.get('heure_fin'),
                "lieu": session_dict.get('lieu'),
                "visioconf_url": session_dict.get('visioconf_url'),
                "capacite": session_dict.get('capacite'),
                "obligatoire": session_dict.get('obligatoire', True),
                "cree_le": now
            }
            
            result = db.exec(insert_query.bindparams(**params)).first()
            db.commit()
            
            # Récupérer la session créée
            return self.get_session(result.id, db, schema_name) if result else None
            
        except Exception as e:
            db.rollback()
            raise e

    def get_sessions_seminaire(self, seminaire_id: int, db: Session, schema_name: str = 'acd') -> List[Dict]:
        """Récupérer toutes les sessions d'un séminaire via requête SQL directe"""
        try:
            # Configurer le search_path
            db.exec(text(f"SET search_path TO {schema_name}, public"))
            
            query = text(f"""
                SELECT id, seminaire_id, titre, description, type_session, date_session,
                       heure_debut, heure_fin, lieu, visioconf_url, capacite, obligatoire, cree_le
                FROM {schema_name}.session_seminaire
                WHERE seminaire_id = :seminaire_id
                ORDER BY date_session, heure_debut
            """)
            
            results = db.exec(query.bindparams(seminaire_id=seminaire_id)).all()
            
            # Convertir les résultats en dictionnaires
            sessions = []
            for row in results:
                sessions.append({
                    'id': row.id,
                    'seminaire_id': row.seminaire_id,
                    'titre': row.titre,
                    'description': row.description,
                    'type_session': row.type_session,
                    'date_session': row.date_session,
                    'heure_debut': row.heure_debut,
                    'heure_fin': row.heure_fin,
                    'lieu': row.lieu,
                    'visioconf_url': row.visioconf_url,
                    'capacite': row.capacite,
                    'obligatoire': row.obligatoire,
                    'cree_le': row.cree_le
                })
            
            return sessions
        except Exception as e:
            raise e

    def update_session(self, session_id: int, session_data: Dict, db: Session, schema_name: str = 'acd') -> Optional[Dict]:
        """Mettre à jour une session via requête SQL directe"""
        try:
            # Configurer le search_path
            db.exec(text(f"SET search_path TO {schema_name}, public"))
            
            # Vérifier que la session existe
            check_query = text(f"SELECT id FROM {schema_name}.session_seminaire WHERE id = :session_id")
            exists = db.exec(check_query.bindparams(session_id=session_id)).first()
            if not exists:
                return None
            
            # Construire la requête UPDATE dynamiquement
            set_clauses = []
            params = {"session_id": session_id}
            
            for field, value in session_data.items():
                if value is not None:
                    set_clauses.append(f"{field} = :{field}")
                    params[field] = value
            
            if not set_clauses:
                # Aucune donnée à mettre à jour
                return self.get_session(session_id, db, schema_name)
            
            update_query = text(f"""
                UPDATE {schema_name}.session_seminaire 
                SET {', '.join(set_clauses)}
                WHERE id = :session_id
            """)
            
            db.exec(update_query.bindparams(**params))
            db.commit()
            
            # Retourner la session mise à jour
            return self.get_session(session_id, db, schema_name)
        except Exception as e:
            db.rollback()
            raise e

    # === GESTION DES INVITATIONS ===
    
    def create_invitation(self, invitation_data: InvitationSeminaireCreate, db: Session, schema_name: str = 'acd') -> Dict:
        """Créer une invitation via requête SQL directe"""
        try:
            # Configurer le search_path
            db.exec(text(f"SET search_path TO {schema_name}, public"))
            
            # Utiliser directement candidat_id (inscription_id n'existe plus)
            candidat_id = invitation_data.candidat_id if hasattr(invitation_data, 'candidat_id') and invitation_data.candidat_id else None
            if not candidat_id and hasattr(invitation_data, 'inscription_id') and invitation_data.inscription_id:
                # Si le schéma utilise encore inscription_id, on le traite comme candidat_id
                candidat_id = invitation_data.inscription_id
            
            # Préparer les valeurs pour l'insertion
            now = datetime.now(timezone.utc)
            token = self._generate_invitation_token()
            
            # Construire la requête INSERT avec le schéma explicite
            insert_query = text(f"""
                INSERT INTO {schema_name}.invitation_seminaire 
                (seminaire_id, type_invitation, candidat_id, promotion_id, statut, token_invitation, cree_le)
                VALUES 
                (:seminaire_id, :type_invitation, :candidat_id, :promotion_id, :statut, :token_invitation, :cree_le)
                RETURNING id
            """)
            
            params = {
                "seminaire_id": invitation_data.seminaire_id,
                "type_invitation": str(invitation_data.type_invitation),
                "candidat_id": candidat_id,
                "promotion_id": invitation_data.promotion_id,
                "statut": "ENVOYEE",
                "token_invitation": token,
                "cree_le": now
            }
            
            result = db.exec(insert_query.bindparams(**params)).first()
            db.commit()
            
            # Récupérer l'invitation créée
            return self.get_invitation(result.id, db, schema_name) if result else None
            
        except Exception as e:
            db.rollback()
            raise e

    def send_invitations_bulk(self, seminaire_id: int, type_invitation: TypeInvitation, 
                             target_ids: List[int], db: Session, schema_name: str = 'acd') -> List[Dict]:
        """Envoyer des invitations en masse via requête SQL directe"""
        try:
            # Configurer le search_path
            db.exec(text(f"SET search_path TO {schema_name}, public"))
            
            invitations = []
            now = datetime.now(timezone.utc)
            
            for target_id in target_ids:
                candidat_id = None
                promotion_id = None
                
                if type_invitation == TypeInvitation.INDIVIDUELLE:
                    # Les IDs passés sont déjà des candidat_id
                    candidat_id = target_id
                elif type_invitation == TypeInvitation.PROMOTION:
                    promotion_id = target_id
                
                if not candidat_id and not promotion_id:
                    continue
                
                token = self._generate_invitation_token()
                
                insert_query = text(f"""
                    INSERT INTO {schema_name}.invitation_seminaire 
                    (seminaire_id, type_invitation, candidat_id, promotion_id, statut, token_invitation, cree_le)
                    VALUES 
                    (:seminaire_id, :type_invitation, :candidat_id, :promotion_id, :statut, :token_invitation, :cree_le)
                    RETURNING id
                """)
                
                params = {
                    "seminaire_id": seminaire_id,
                    "type_invitation": str(type_invitation),
                    "candidat_id": candidat_id,
                    "promotion_id": promotion_id,
                    "statut": "ENVOYEE",
                    "token_invitation": token,
                    "cree_le": now
                }
                
                result = db.exec(insert_query.bindparams(**params)).first()
                if result:
                    invitation = self.get_invitation(result.id, db, schema_name)
                    if invitation:
                        invitations.append(invitation)
                        # Envoyer l'email d'invitation
                        self._send_invitation_email(invitation, db, schema_name)
            
            db.commit()
            return invitations
            
        except Exception as e:
            db.rollback()
            raise e

    def get_invitations_seminaire(self, seminaire_id: int, db: Session, schema_name: str = 'acd') -> List[Dict]:
        """Récupérer toutes les invitations d'un séminaire via requête SQL directe"""
        try:
            # Configurer le search_path
            db.exec(text(f"SET search_path TO {schema_name}, public"))
            
            query = text(f"""
                SELECT i.id, i.seminaire_id, i.type_invitation, i.candidat_id, i.promotion_id,
                       i.statut, i.email_envoye, i.date_envoi, i.date_reponse, i.token_invitation, i.cree_le,
                       c.nom as candidat_nom, c.prenom as candidat_prenom, c.email as candidat_email
                FROM {schema_name}.invitation_seminaire i
                LEFT JOIN {schema_name}.candidat c ON i.candidat_id = c.id
                WHERE i.seminaire_id = :seminaire_id
                ORDER BY i.cree_le DESC
            """)
            
            results = db.exec(query.bindparams(seminaire_id=seminaire_id)).all()
            
            # Convertir les résultats en dictionnaires
            invitations = []
            for row in results:
                invitations.append({
                    'id': row.id,
                    'seminaire_id': row.seminaire_id,
                    'type_invitation': row.type_invitation,
                    'candidat_id': row.candidat_id,
                    'promotion_id': row.promotion_id,
                    'statut': row.statut,
                    'email_envoye': row.email_envoye,
                    'date_envoi': row.date_envoi,
                    'date_reponse': row.date_reponse,
                    'token_invitation': row.token_invitation,
                    'cree_le': row.cree_le,
                    'candidat_nom': row.candidat_nom,
                    'candidat_prenom': row.candidat_prenom,
                    'candidat_email': row.candidat_email
                })
            
            return invitations
        except Exception as e:
            raise e

    def accept_invitation(self, token: str, db: Session, schema_name: str = 'acd') -> Optional[Dict]:
        """Accepter une invitation via token avec requête SQL directe"""
        try:
            # Configurer le search_path
            db.exec(text(f"SET search_path TO {schema_name}, public"))
            
            # Récupérer l'invitation
            invitation = self.get_invitation_by_token(token, db, schema_name)
            if not invitation or invitation.get('statut') != "ENVOYEE":
                return invitation
            
            # Mettre à jour le statut
            now = datetime.now(timezone.utc)
            update_query = text(f"""
                UPDATE {schema_name}.invitation_seminaire
                SET statut = 'ACCEPTEE', date_reponse = :date_reponse
                WHERE token_invitation = :token
            """)
            db.exec(update_query.bindparams(token=token, date_reponse=now))
            db.commit()
            
            # Retourner l'invitation mise à jour
            return self.get_invitation_by_token(token, db, schema_name)
        except Exception as e:
            db.rollback()
            raise e

    def reject_invitation(self, token: str, db: Session, schema_name: str = 'acd') -> Optional[Dict]:
        """Refuser une invitation via token avec requête SQL directe"""
        try:
            # Configurer le search_path
            db.exec(text(f"SET search_path TO {schema_name}, public"))
            
            # Récupérer l'invitation
            invitation = self.get_invitation_by_token(token, db, schema_name)
            if not invitation or invitation.get('statut') != "ENVOYEE":
                return invitation
            
            # Mettre à jour le statut
            now = datetime.now(timezone.utc)
            update_query = text(f"""
                UPDATE {schema_name}.invitation_seminaire
                SET statut = 'REFUSEE', date_reponse = :date_reponse
                WHERE token_invitation = :token
            """)
            db.exec(update_query.bindparams(token=token, date_reponse=now))
            db.commit()
            
            # Retourner l'invitation mise à jour
            return self.get_invitation_by_token(token, db, schema_name)
        except Exception as e:
            db.rollback()
            raise e

    # === GESTION DE LA PRÉSENCE ===
    
    def mark_presence(self, presence_data: PresenceSeminaireCreate, db: Session) -> PresenceSeminaire:
        """Marquer la présence d'un participant
        
        IMPORTANT : 
        - Un émargement est attaché à une SESSION de séminaire (pas au séminaire)
        - Un candidat peut avoir plusieurs présences pour un même séminaire (une par session)
        - Un candidat ne peut avoir qu'une seule présence par session
        - Si une présence existe déjà pour cette session et ce candidat, elle est mise à jour
        """
        # Utiliser directement candidat_id (inscription_id n'existe plus)
        candidat_id = None
        if hasattr(presence_data, 'candidat_id') and presence_data.candidat_id:
            candidat_id = presence_data.candidat_id
        elif hasattr(presence_data, 'inscription_id') and presence_data.inscription_id:
            # Si le schéma utilise encore inscription_id, on le traite comme candidat_id
            candidat_id = presence_data.inscription_id
        
        if not candidat_id:
            raise ValueError("candidat_id est requis pour marquer la présence")
        
        # Vérifier si une présence existe déjà
        query = select(PresenceSeminaire).where(
            and_(
                PresenceSeminaire.session_id == presence_data.session_id,
                PresenceSeminaire.candidat_id == candidat_id
            )
        )
        existing_presence = db.exec(query).first()
        
        if existing_presence:
            # Mettre à jour la présence existante
            presence_dict = presence_data.dict(exclude={'session_id', 'inscription_id'})
            for field, value in presence_dict.items():
                if field != 'candidat_id':  # Ne pas écraser candidat_id
                    setattr(existing_presence, field, value)
            
            # Enregistrer l'heure d'arrivée si c'est la première fois qu'on marque "present"
            if presence_data.presence == "present" and not existing_presence.heure_arrivee:
                existing_presence.heure_arrivee = datetime.now(timezone.utc)
            
            existing_presence.modifie_le = datetime.now(timezone.utc)
            db.commit()
            db.refresh(existing_presence)
            return existing_presence
        else:
            # Créer une nouvelle présence
            presence_dict = presence_data.dict(exclude={'inscription_id'})
            presence_dict['candidat_id'] = candidat_id
            presence = PresenceSeminaire(**presence_dict)
            
            # Enregistrer l'heure d'arrivée si on marque "present"
            if presence_data.presence == "present":
                presence.heure_arrivee = datetime.now(timezone.utc)
            
            db.add(presence)
            db.commit()
            db.refresh(presence)
        return presence
    
    def delete_session(self, session_id: int, db: Session, schema_name: str = 'acd') -> bool:
        """Supprimer une session et toutes ses données associées avec requête SQL directe"""
        try:
            # Configurer le search_path
            db.exec(text(f"SET search_path TO {schema_name}, public"))
            
            # Vérifier que la session existe
            check_query = text(f"SELECT id FROM {schema_name}.session_seminaire WHERE id = :session_id")
            exists = db.exec(check_query.bindparams(session_id=session_id)).first()
            if not exists:
                return False
            
            # Supprimer les présences de la session via requête SQL directe
            delete_presences_query = text(f"DELETE FROM {schema_name}.presence_seminaire WHERE session_id = :session_id")
            db.exec(delete_presences_query.bindparams(session_id=session_id))
            
            # Supprimer la session elle-même via requête SQL directe
            delete_session_query = text(f"DELETE FROM {schema_name}.session_seminaire WHERE id = :session_id")
            db.exec(delete_session_query.bindparams(session_id=session_id))
            
            db.commit()
            return True
            
        except Exception as e:
            db.rollback()
            raise e
    
    def get_presences_session(self, session_id: int, db: Session) -> List[PresenceSeminaire]:
        """Récupérer toutes les présences d'une session"""
        query = select(PresenceSeminaire).where(PresenceSeminaire.session_id == session_id)
        return db.exec(query).all()
    
    def get_presences_seminaire(self, seminaire_id: int, db: Session, schema_name: str = 'acd') -> List[Dict]:
        """Récupérer toutes les présences de toutes les sessions d'un séminaire avec détails des candidats"""
        try:
            # Configurer le search_path
            db.exec(text(f"SET search_path TO {schema_name}, public"))
            
            # Récupérer toutes les présences avec les détails des candidats et des sessions
            query = text(f"""
                SELECT p.id, p.session_id, p.candidat_id, p.presence, p.methode_signature,
                       p.signature_manuelle, p.signature_digitale, p.photo_signature,
                       p.heure_arrivee, p.heure_depart, p.note, p.ip_signature, p.user_agent, p.cree_le,
                       c.nom as candidat_nom, c.prenom as candidat_prenom, c.email as candidat_email, c.photo_profil as candidat_photo_profil,
                       s.titre as session_titre, s.date_session as session_date, s.heure_debut as session_heure_debut
                FROM {schema_name}.presence_seminaire p
                LEFT JOIN {schema_name}.candidat c ON p.candidat_id = c.id
                LEFT JOIN {schema_name}.session_seminaire s ON p.session_id = s.id
                WHERE s.seminaire_id = :seminaire_id AND p.presence = 'present'
                ORDER BY s.date_session, s.heure_debut, p.heure_arrivee
            """)
            
            results = db.exec(query.bindparams(seminaire_id=seminaire_id)).all()
            
            # Convertir les résultats en dictionnaires
            presences = []
            for row in results:
                presences.append({
                    'id': row.id,
                    'session_id': row.session_id,
                    'session_titre': row.session_titre,
                    'session_date': row.session_date,
                    'session_heure_debut': row.session_heure_debut,
                    'candidat_id': row.candidat_id,
                    'candidat_nom': row.candidat_nom,
                    'candidat_prenom': row.candidat_prenom,
                    'candidat_email': row.candidat_email,
                    'candidat_photo_profil': row.candidat_photo_profil,
                    'presence': row.presence,
                    'methode_signature': row.methode_signature,
                    'signature_manuelle': row.signature_manuelle,
                    'signature_digitale': row.signature_digitale,
                    'photo_signature': row.photo_signature,
                    'heure_arrivee': row.heure_arrivee,
                    'heure_depart': row.heure_depart,
                    'note': row.note,
                    'ip_signature': row.ip_signature,
                    'user_agent': row.user_agent,
                    'cree_le': row.cree_le
                })
            
            return presences
        except Exception as e:
            logger.error(f"Erreur lors de la récupération des présences du séminaire: {e}")
            return []
    
    def get_presences_with_invitations(self, seminaire_id: int, session_id: int, db: Session, schema_name: str = 'acd') -> List[PresenceSeminaire]:
        """Récupérer toutes les présences pour une session, créant des enregistrements par défaut pour tous les invités"""
        try:
            # Configurer le search_path
            db.exec(text(f"SET search_path TO {schema_name}, public"))
            
            # Récupérer toutes les invitations pour ce séminaire via requête SQL directe
            invitations_query = text(f"""
                SELECT id, seminaire_id, type_invitation, candidat_id, promotion_id,
                       statut, email_envoye, date_envoi, date_reponse, token_invitation, cree_le
                FROM {schema_name}.invitation_seminaire
                WHERE seminaire_id = :seminaire_id AND candidat_id IS NOT NULL
            """)
            invitations_results = db.exec(invitations_query.bindparams(seminaire_id=seminaire_id)).all()
            
            # Récupérer toutes les présences existantes pour cette session
            presences_query = text(f"""
                SELECT id, session_id, candidat_id, presence, methode_signature,
                       signature_manuelle, signature_digitale, photo_signature,
                       heure_arrivee, heure_depart, note, ip_signature, user_agent, cree_le, modifie_le
                FROM {schema_name}.presence_seminaire
                WHERE session_id = :session_id
            """)
            presences_results = db.exec(presences_query.bindparams(session_id=session_id)).all()
            
            # Créer un dictionnaire des présences par candidat_id pour accès rapide
            presences_by_candidat = {}
            for pres_row in presences_results:
                presences_by_candidat[pres_row.candidat_id] = PresenceSeminaire(
                    id=pres_row.id,
                    session_id=pres_row.session_id,
                    candidat_id=pres_row.candidat_id,
                    presence=pres_row.presence,
                    methode_signature=pres_row.methode_signature,
                    signature_manuelle=pres_row.signature_manuelle,
                    signature_digitale=pres_row.signature_digitale,
                    photo_signature=pres_row.photo_signature,
                    heure_arrivee=pres_row.heure_arrivee,
                    heure_depart=pres_row.heure_depart,
                    note=pres_row.note,
                    ip_signature=pres_row.ip_signature,
                    user_agent=pres_row.user_agent,
                    cree_le=pres_row.cree_le,
                    modifie_le=pres_row.modifie_le
                )
            
            # Récupérer les informations de la session pour déterminer le statut par défaut
            session_query = text(f"""
                SELECT id, date_session
                FROM {schema_name}.session_seminaire
                WHERE id = :session_id
            """)
            session_result = db.exec(session_query.bindparams(session_id=session_id)).first()
            session_date = session_result.date_session if session_result else None
            
            presences = []
            
            for inv_row in invitations_results:
                candidat_id = inv_row.candidat_id
                if not candidat_id:
                    continue
                
                # Vérifier si une présence existe déjà
                existing_presence = presences_by_candidat.get(candidat_id)
                
                if existing_presence:
                    # Si la présence existe avec le statut "absent" mais que l'invitation n'est pas refusée,
                    # mettre à jour le statut à "en_attente" (toujours en attente si pas présent)
                    if existing_presence.presence == "absent" or existing_presence.presence == StatutPresence.ABSENT:
                        statut_str = str(inv_row.statut).lower() if inv_row.statut else 'envoyee'
                        if statut_str != "refusee":
                            # Mettre à jour le statut à "en_attente" si l'invitation n'est pas refusée
                            existing_presence.presence = "en_attente"
                            db.add(existing_presence)
                            db.commit()
                            db.refresh(existing_presence)
                            logger.info(f"🔄 Présence mise à jour de 'absent' à 'en_attente' pour candidat {candidat_id}")
                    presences.append(existing_presence)
                else:
                    # Vérifier que le candidat existe
                    candidat_query = text(f"""
                        SELECT id FROM {schema_name}.candidat WHERE id = :candidat_id
                    """)
                    candidat_result = db.exec(candidat_query.bindparams(candidat_id=candidat_id)).first()
                    
                    if candidat_result:
                        # Déterminer le statut par défaut selon l'invitation
                        # Par défaut, toujours "en_attente" si le candidat n'est pas présent
                        default_status = "en_attente"
                        
                        # Si l'invitation est refusée, mettre absent
                        statut_str = str(inv_row.statut).lower() if inv_row.statut else 'envoyee'
                        if statut_str == "refusee":
                            default_status = "absent"
                            logger.info(f"❌ Invitation refusée, statut mis à 'absent'")
                        
                        # Le statut reste "en_attente" jusqu'à ce que le candidat signe (présent/absent/excusé) ou qu'on le marque manuellement
                        # On ne met plus "absent" automatiquement même si la session est passée
                        
                        logger.info(f"✅ Création présence pour candidat {candidat_id}, session {session_id}, statut: {default_status}")
                        
                        # Créer la présence par défaut
                        default_presence = PresenceSeminaire(
                            session_id=session_id,
                            candidat_id=candidat_id,
                            presence=default_status
                        )
                        db.add(default_presence)
                        db.commit()
                        db.refresh(default_presence)
                        presences.append(default_presence)
            
            return presences
        except Exception as e:
            logger.error(f"Erreur lors de la récupération des présences avec invitations: {e}")
            return []
    
    def get_presences_for_direct_emargement(self, seminaire_id: int, session_id: int, db: Session, schema_name: str = 'acd') -> List[PresenceSeminaire]:
        """Récupérer les présences pour l'émargement direct - seulement les présences existantes en base"""
        try:
            # Configurer le search_path
            db.exec(text(f"SET search_path TO {schema_name}, public"))
            
            # Récupérer toutes les présences existantes pour cette session via requête SQL directe
            query = text(f"""
                SELECT p.id, p.session_id, p.candidat_id, p.presence, p.methode_signature,
                       p.signature_manuelle, p.signature_digitale, p.photo_signature,
                       p.heure_arrivee, p.heure_depart, p.note, p.ip_signature, p.user_agent, p.cree_le, p.modifie_le
                FROM {schema_name}.presence_seminaire p
                WHERE p.session_id = :session_id
                ORDER BY p.heure_arrivee DESC NULLS LAST, p.cree_le DESC
            """)
            
            results = db.exec(query.bindparams(session_id=session_id)).all()
            
            # Convertir les résultats en objets PresenceSeminaire
            presences = []
            for row in results:
                presence = PresenceSeminaire(
                    id=row.id,
                    session_id=row.session_id,
                    candidat_id=row.candidat_id,
                    presence=row.presence,
                    methode_signature=row.methode_signature,
                    signature_manuelle=row.signature_manuelle,
                    signature_digitale=row.signature_digitale,
                    photo_signature=row.photo_signature,
                    heure_arrivee=row.heure_arrivee,
                    heure_depart=row.heure_depart,
                    note=row.note,
                    ip_signature=row.ip_signature,
                    user_agent=row.user_agent,
                    cree_le=row.cree_le,
                    modifie_le=row.modifie_le
                )
                presences.append(presence)
            
            return presences
        except Exception as e:
            logger.error(f"Erreur lors de la récupération des présences pour l'émargement direct: {e}")
            return []
    
    def get_presences_with_invitation_details(self, seminaire_id: int, session_id: int, db: Session, schema_name: str = 'acd') -> List[Dict]:
        """Récupérer toutes les présences avec les détails d'invitation pour une session"""
        try:
            # Configurer le search_path
            db.exec(text(f"SET search_path TO {schema_name}, public"))
            
            # Récupérer toutes les invitations avec les détails des candidats via requête SQL directe
            invitations_query = text(f"""
                SELECT i.id, i.seminaire_id, i.type_invitation, i.candidat_id, i.promotion_id,
                       i.statut, i.email_envoye, i.date_envoi, i.date_reponse, i.token_invitation, i.cree_le,
                       c.id as candidat_id_full, c.nom as candidat_nom, c.prenom as candidat_prenom, 
                       c.email as candidat_email, c.photo_profil as candidat_photo_profil
                FROM {schema_name}.invitation_seminaire i
                LEFT JOIN {schema_name}.candidat c ON i.candidat_id = c.id
                WHERE i.seminaire_id = :seminaire_id AND i.candidat_id IS NOT NULL
                ORDER BY c.nom, c.prenom
            """)
            invitations_results = db.exec(invitations_query.bindparams(seminaire_id=seminaire_id)).all()
            
            # Récupérer toutes les présences existantes pour cette session
            presences_query = text(f"""
                SELECT p.id, p.session_id, p.candidat_id, p.presence, p.methode_signature,
                       p.signature_manuelle, p.signature_digitale, p.photo_signature,
                       p.heure_arrivee, p.heure_depart, p.note, p.ip_signature, p.user_agent, p.cree_le, p.modifie_le
                FROM {schema_name}.presence_seminaire p
                WHERE p.session_id = :session_id
            """)
            presences_results = db.exec(presences_query.bindparams(session_id=session_id)).all()
            
            # Créer un dictionnaire des présences par candidat_id pour accès rapide
            presences_by_candidat = {}
            for pres_row in presences_results:
                presences_by_candidat[pres_row.candidat_id] = {
                    'id': pres_row.id,
                    'session_id': pres_row.session_id,
                    'candidat_id': pres_row.candidat_id,
                    'presence': pres_row.presence,
                    'methode_signature': pres_row.methode_signature,
                    'signature_manuelle': pres_row.signature_manuelle,
                    'signature_digitale': pres_row.signature_digitale,
                    'photo_signature': pres_row.photo_signature,
                    'heure_arrivee': pres_row.heure_arrivee,
                    'heure_depart': pres_row.heure_depart,
                    'note': pres_row.note,
                    'ip_signature': pres_row.ip_signature,
                    'user_agent': pres_row.user_agent,
                    'cree_le': pres_row.cree_le,
                    'modifie_le': pres_row.modifie_le
                }
            
            # Récupérer les informations de la session pour déterminer le statut par défaut
            session_query = text(f"""
                SELECT id, date_session
                FROM {schema_name}.session_seminaire
                WHERE id = :session_id
            """)
            session_result = db.exec(session_query.bindparams(session_id=session_id)).first()
            session_date = session_result.date_session if session_result else None
            
            presences_data = []
            
            for inv_row in invitations_results:
                candidat_id = inv_row.candidat_id
                if not candidat_id:
                    continue
                
                # Vérifier si une présence existe déjà
                presence_dict = presences_by_candidat.get(candidat_id)
                
                if presence_dict:
                    # Si la présence existe avec le statut "absent" mais que l'invitation n'est pas refusée,
                    # mettre à jour le statut à "en_attente" (toujours en attente si pas présent)
                    if presence_dict.get('presence') == "absent" or presence_dict.get('presence') == StatutPresence.ABSENT:
                        statut_str = str(inv_row.statut).lower() if inv_row.statut else 'envoyee'
                        if statut_str != "refusee":
                            # Mettre à jour le statut à "en_attente" si l'invitation n'est pas refusée
                            update_query = text(f"""
                                UPDATE {schema_name}.presence_seminaire
                                SET presence = 'en_attente', modifie_le = :modifie_le
                                WHERE id = :presence_id
                            """)
                            db.exec(update_query.bindparams(
                                presence_id=presence_dict['id'],
                                modifie_le=datetime.now(timezone.utc)
                            ))
                            db.commit()
                            presence_dict['presence'] = "en_attente"
                            logger.info(f"🔄 Présence mise à jour de 'absent' à 'en_attente' pour candidat {candidat_id}")
                
                if not presence_dict:
                    # Créer une présence par défaut
                    # Par défaut, toujours "en_attente" si le candidat n'est pas présent
                    default_status = "en_attente"
                    
                    # Si l'invitation est refusée, mettre absent
                    statut_str = str(inv_row.statut).lower() if inv_row.statut else 'envoyee'
                    if statut_str == "refusee":
                        default_status = "absent"
                        logger.info(f"❌ Invitation refusée, statut mis à 'absent'")
                    
                    # Le statut reste "en_attente" jusqu'à ce que le candidat signe (présent/absent/excusé) ou qu'on le marque manuellement
                    # On ne met plus "absent" automatiquement même si la session est passée
                    
                    logger.info(f"✅ Création présence pour candidat {candidat_id}, session {session_id}, statut: {default_status}")
                    
                    # Créer la présence par défaut en base
                    default_presence = PresenceSeminaire(
                        session_id=session_id,
                        candidat_id=candidat_id,
                        presence=default_status
                    )
                    db.add(default_presence)
                    db.commit()
                    db.refresh(default_presence)
                    
                    presence_dict = {
                        'id': default_presence.id,
                        'session_id': default_presence.session_id,
                        'candidat_id': default_presence.candidat_id,
                        'presence': default_presence.presence,
                        'methode_signature': default_presence.methode_signature,
                        'signature_manuelle': default_presence.signature_manuelle,
                        'signature_digitale': default_presence.signature_digitale,
                        'photo_signature': default_presence.photo_signature,
                        'heure_arrivee': default_presence.heure_arrivee,
                        'heure_depart': default_presence.heure_depart,
                        'note': default_presence.note,
                        'ip_signature': default_presence.ip_signature,
                        'user_agent': default_presence.user_agent,
                        'cree_le': default_presence.cree_le,
                        'modifie_le': default_presence.modifie_le
                    }
                
                # Convertir les enums en strings
                statut_str = str(inv_row.statut).lower() if inv_row.statut else 'envoyee'
                type_inv_str = None
                if inv_row.type_invitation:
                    if hasattr(inv_row.type_invitation, 'value'):
                        type_inv_str = inv_row.type_invitation.value.lower()
                    else:
                        type_inv_str = str(inv_row.type_invitation).lower()
                
                # Créer les objets pour le template
                invitation_obj = type('InvitationSeminaire', (), {
                    'id': inv_row.id,
                    'seminaire_id': inv_row.seminaire_id,
                    'type_invitation': type_inv_str,
                    'candidat_id': inv_row.candidat_id,
                    'promotion_id': inv_row.promotion_id,
                    'statut': statut_str,
                    'email_envoye': inv_row.email_envoye,
                    'date_envoi': inv_row.date_envoi,
                    'date_reponse': inv_row.date_reponse,
                    'token_invitation': inv_row.token_invitation,
                    'cree_le': inv_row.cree_le,
                    'candidat': type('Candidat', (), {
                        'id': inv_row.candidat_id_full,
                        'nom': inv_row.candidat_nom,
                        'prenom': inv_row.candidat_prenom,
                        'email': inv_row.candidat_email,
                        'photo_profil': inv_row.candidat_photo_profil
                    })() if inv_row.candidat_id_full else None
                })()
                
                presence_obj = type('PresenceSeminaire', (), {
                    'id': presence_dict['id'],
                    'session_id': presence_dict['session_id'],
                    'candidat_id': presence_dict['candidat_id'],
                    'presence': presence_dict['presence'],
                    'methode_signature': presence_dict['methode_signature'],
                    'signature_manuelle': presence_dict['signature_manuelle'],
                    'signature_digitale': presence_dict['signature_digitale'],
                    'photo_signature': presence_dict['photo_signature'],
                    'heure_arrivee': presence_dict['heure_arrivee'],
                    'heure_depart': presence_dict['heure_depart'],
                    'note': presence_dict['note'],
                    'ip_signature': presence_dict['ip_signature'],
                    'user_agent': presence_dict['user_agent'],
                    'cree_le': presence_dict['cree_le'],
                    'modifie_le': presence_dict['modifie_le'],
                    'candidat': invitation_obj.candidat if invitation_obj.candidat else None
                })()
                
                # Créer l'objet de données enrichi
                presence_data = {
                    'presence': presence_obj,
                    'invitation': invitation_obj,
                    'invitation_statut': statut_str
                }
                presences_data.append(presence_data)
            
            return presences_data
        except Exception as e:
            logger.error(f"Erreur lors de la récupération des présences avec détails d'invitation: {e}")
            return []

    def get_presence_stats(self, session_id: int, db: Session) -> Dict[str, int]:
        """Obtenir les statistiques de présence pour une session"""
        presences = self.get_presences_session(session_id, db)
        
        stats = {
            'total': len(presences),
            'present': len([p for p in presences if p.presence == StatutPresence.PRESENT]),
            'absent': len([p for p in presences if p.presence == StatutPresence.ABSENT]),
            'excuse': len([p for p in presences if p.presence == StatutPresence.EXCUSE])
        }
        
        if stats['total'] > 0:
            stats['taux_presence'] = round((stats['present'] / stats['total']) * 100, 2)
        else:
            stats['taux_presence'] = 0
        
        return stats
        
    def get_presence_stats_with_invitations(self, seminaire_id: int, session_id: int, db: Session, schema_name: str = 'acd') -> Dict[str, int]:
        """Obtenir les statistiques de présence pour une session avec invitations"""
        presences = self.get_presences_with_invitations(seminaire_id, session_id, db, schema_name)
        
        stats = {
            'total': len(presences),
            'present': len([p for p in presences if p.presence == 'present' or p.presence == StatutPresence.PRESENT]),
            'absent': len([p for p in presences if p.presence == 'absent' or p.presence == StatutPresence.ABSENT]),
            'excuse': len([p for p in presences if p.presence == 'excuse' or p.presence == StatutPresence.EXCUSE])
        }
        
        if stats['total'] > 0:
            stats['taux_presence'] = round((stats['present'] / stats['total']) * 100, 2)
        else:
            stats['taux_presence'] = 0
        
        return stats

    # === GESTION DES LIVRABLES ===
    
    def create_livrable(self, livrable_data: LivrableSeminaireCreate, db: Session) -> LivrableSeminaire:
        """Créer un livrable pour un séminaire"""
        livrable = LivrableSeminaire(**livrable_data.dict())
        db.add(livrable)
        db.commit()
        db.refresh(livrable)
        return livrable

    def get_livrables_seminaire(self, seminaire_id: int, db: Session, schema_name: str = 'acd') -> List[LivrableSeminaire]:
        """Récupérer tous les livrables d'un séminaire"""
        try:
            # Configurer le search_path
            db.exec(text(f"SET search_path TO {schema_name}, public"))
            
            # Récupérer les livrables via requête SQL directe
            query = text(f"""
                SELECT id, seminaire_id, titre, description, type_livrable, obligatoire,
                       date_limite, consignes, format_accepte, taille_max_mb, cree_le
                FROM {schema_name}.livrable_seminaire
                WHERE seminaire_id = :seminaire_id
                ORDER BY cree_le DESC
            """)
            
            results = db.exec(query.bindparams(seminaire_id=seminaire_id)).all()
            
            # Convertir les résultats en objets LivrableSeminaire
            livrables = []
            for row in results:
                livrable = LivrableSeminaire(
                    id=row.id,
                    seminaire_id=row.seminaire_id,
                    titre=row.titre,
                    description=row.description,
                    type_livrable=row.type_livrable,
                    obligatoire=row.obligatoire,
                    date_limite=row.date_limite,
                    consignes=row.consignes,
                    format_accepte=row.format_accepte,
                    taille_max_mb=row.taille_max_mb,
                    cree_le=row.cree_le
                )
                livrables.append(livrable)
            
            return livrables
        except Exception as e:
            logger.error(f"Erreur lors de la récupération des livrables: {e}")
            return []

    def get_livrable_by_id(self, livrable_id: int, db: Session, schema_name: str = 'acd') -> Optional[LivrableSeminaire]:
        """Récupérer un livrable par son ID"""
        try:
            db.exec(text(f"SET search_path TO {schema_name}, public"))
            
            query = text(f"""
                SELECT id, seminaire_id, titre, description, type_livrable, obligatoire,
                       date_limite, consignes, format_accepte, taille_max_mb, cree_le
                FROM {schema_name}.livrable_seminaire
                WHERE id = :livrable_id
            """)
            
            result = db.exec(query.bindparams(livrable_id=livrable_id)).first()
            if not result:
                return None
            
            return LivrableSeminaire(
                id=result.id,
                seminaire_id=result.seminaire_id,
                titre=result.titre,
                description=result.description,
                type_livrable=result.type_livrable,
                obligatoire=result.obligatoire,
                date_limite=result.date_limite,
                consignes=result.consignes,
                format_accepte=result.format_accepte,
                taille_max_mb=result.taille_max_mb,
                cree_le=result.cree_le
            )
        except Exception as e:
            logger.error(f"Erreur lors de la récupération du livrable: {e}")
            return None

    def update_livrable(self, livrable_id: int, livrable_data: LivrableSeminaireCreate, db: Session, schema_name: str = 'acd') -> Optional[LivrableSeminaire]:
        """Mettre à jour un livrable"""
        try:
            db.exec(text(f"SET search_path TO {schema_name}, public"))
            
            query = text(f"""
                UPDATE {schema_name}.livrable_seminaire
                SET titre = :titre,
                    description = :description,
                    type_livrable = :type_livrable,
                    obligatoire = :obligatoire,
                    date_limite = :date_limite,
                    consignes = :consignes,
                    format_accepte = :format_accepte,
                    taille_max_mb = :taille_max_mb
                WHERE id = :livrable_id
                RETURNING id, seminaire_id, titre, description, type_livrable, obligatoire,
                          date_limite, consignes, format_accepte, taille_max_mb, cree_le
            """)
            
            result = db.exec(query.bindparams(
                livrable_id=livrable_id,
                titre=livrable_data.titre,
                description=livrable_data.description or "",
                type_livrable=livrable_data.type_livrable,
                obligatoire=livrable_data.obligatoire,
                date_limite=livrable_data.date_limite,
                consignes=livrable_data.consignes or "",
                format_accepte=livrable_data.format_accepte or "",
                taille_max_mb=livrable_data.taille_max_mb
            )).first()
            
            if not result:
                return None
            
            db.commit()
            
            return LivrableSeminaire(
                id=result.id,
                seminaire_id=result.seminaire_id,
                titre=result.titre,
                description=result.description,
                type_livrable=result.type_livrable,
                obligatoire=result.obligatoire,
                date_limite=result.date_limite,
                consignes=result.consignes,
                format_accepte=result.format_accepte,
                taille_max_mb=result.taille_max_mb,
                cree_le=result.cree_le
            )
        except Exception as e:
            logger.error(f"Erreur lors de la mise à jour du livrable: {e}")
            db.rollback()
            return None

    def get_inscription_candidat(self, seminaire_id: int, user_email: str, db: Session):
        """Récupérer le candidat pour un séminaire - NOTE: Le modèle Inscription n'existe plus"""
        # D'abord récupérer le séminaire pour obtenir le programme_id
        seminaire = self.get_seminaire(seminaire_id, db)
        if not seminaire:
            return None
            
        # NOTE: Le modèle Inscription a été supprimé. Récupérer directement le candidat.
        # Chercher le candidat via l'email
        query = select(Candidat).where(
            Candidat.email == user_email
        )
        return db.exec(query).first()
    
    def get_rendus_candidat(self, candidat_id: int, db: Session) -> List[RenduLivrable]:
        """Récupérer tous les rendus d'un candidat"""
        query = select(RenduLivrable).where(RenduLivrable.candidat_id == candidat_id)
        return list(db.exec(query).all())
    
    def get_invitations_seminaire(self, seminaire_id: int, db: Session, schema_name: str = 'acd') -> List[Dict]:
        """Récupérer toutes les invitations d'un séminaire (sans doublons par candidat) via requête SQL directe"""
        try:
            # Configurer le search_path
            db.exec(text(f"SET search_path TO {schema_name}, public"))
            
            # Récupérer les invitations avec les informations du candidat via requête SQL directe
            query = text(f"""
                SELECT i.id, i.seminaire_id, i.type_invitation, i.candidat_id, i.promotion_id,
                       i.statut, i.email_envoye, i.date_envoi, i.date_reponse, i.token_invitation, i.cree_le,
                       c.nom as candidat_nom, c.prenom as candidat_prenom, c.email as candidat_email,
                       c.photo_profil as candidat_photo_profil
                FROM {schema_name}.invitation_seminaire i
                LEFT JOIN {schema_name}.candidat c ON i.candidat_id = c.id
                WHERE i.seminaire_id = :seminaire_id AND i.candidat_id IS NOT NULL
                ORDER BY i.cree_le DESC
            """)
            
            results = db.exec(query.bindparams(seminaire_id=seminaire_id)).all()
            
            # Convertir en dictionnaires avec les informations du candidat
            all_invitations = []
            for row in results:
                all_invitations.append({
                    'id': row.id,
                    'seminaire_id': row.seminaire_id,
                    'type_invitation': row.type_invitation,
                    'candidat_id': row.candidat_id,
                    'promotion_id': row.promotion_id,
                    'statut': row.statut,
                    'email_envoye': row.email_envoye,
                    'date_envoi': row.date_envoi,
                    'date_reponse': row.date_reponse,
                    'token_invitation': row.token_invitation,
                    'cree_le': row.cree_le,
                    'candidat': {
                        'id': row.candidat_id,
                        'nom': row.candidat_nom,
                        'prenom': row.candidat_prenom,
                        'email': row.candidat_email,
                        'photo_profil': row.candidat_photo_profil
                    } if row.candidat_id else None
                })
            
            # Éviter les doublons par candidat (garder la plus récente)
            seen_candidates = {}
            
            for invitation in all_invitations:
                if invitation['candidat_id']:
                    candidat_id = invitation['candidat_id']
                    # Garder seulement la plus récente invitation par candidat
                    if candidat_id not in seen_candidates or invitation['id'] > seen_candidates[candidat_id]['id']:
                        seen_candidates[candidat_id] = invitation
            
            return list(seen_candidates.values())
        except Exception as e:
            logger.error(f"Erreur lors de la récupération des invitations: {e}")
            return []
    
    def get_invitation(self, invitation_id: int, db: Session, schema_name: str = 'acd') -> Optional[Dict]:
        """Récupérer une invitation par son ID via requête SQL directe"""
        try:
            # Configurer le search_path
            db.exec(text(f"SET search_path TO {schema_name}, public"))
            
            query = text(f"""
                SELECT i.id, i.seminaire_id, i.type_invitation, i.candidat_id, i.promotion_id,
                       i.statut, i.email_envoye, i.date_envoi, i.date_reponse, i.token_invitation, i.cree_le,
                       c.nom as candidat_nom, c.prenom as candidat_prenom, c.email as candidat_email
                FROM {schema_name}.invitation_seminaire i
                LEFT JOIN {schema_name}.candidat c ON i.candidat_id = c.id
                WHERE i.id = :invitation_id
            """)
            
            result = db.exec(query.bindparams(invitation_id=invitation_id)).first()
            if not result:
                return None
            
            invitation_dict = {
                'id': result.id,
                'seminaire_id': result.seminaire_id,
                'type_invitation': result.type_invitation,
                'candidat_id': result.candidat_id,
                'promotion_id': result.promotion_id,
                'statut': result.statut,
                'email_envoye': result.email_envoye,
                'date_envoi': result.date_envoi,
                'date_reponse': result.date_reponse,
                'token_invitation': result.token_invitation,
                'cree_le': result.cree_le,
                'candidat_nom': result.candidat_nom,
                'candidat_prenom': result.candidat_prenom,
                'candidat_email': result.candidat_email
            }
            
            # Ajouter les informations du candidat dans un dictionnaire candidat
            if result.candidat_id and result.candidat_nom:
                invitation_dict['candidat'] = {
                    'id': result.candidat_id,
                    'nom': result.candidat_nom,
                    'prenom': result.candidat_prenom,
                    'email': result.candidat_email
                }
            
            return invitation_dict
        except Exception as e:
            raise e
    
    def get_invitation_by_token(self, token: str, db: Session, schema_name: str = 'acd') -> Optional[Dict]:
        """Récupérer une invitation par son token via requête SQL directe"""
        try:
            # Configurer le search_path
            db.exec(text(f"SET search_path TO {schema_name}, public"))
            
            query = text(f"""
                SELECT i.id, i.seminaire_id, i.type_invitation, i.candidat_id, i.promotion_id,
                       i.statut, i.email_envoye, i.date_envoi, i.date_reponse, i.token_invitation, i.cree_le,
                       c.nom as candidat_nom, c.prenom as candidat_prenom, c.email as candidat_email
                FROM {schema_name}.invitation_seminaire i
                LEFT JOIN {schema_name}.candidat c ON i.candidat_id = c.id
                WHERE i.token_invitation = :token
            """)
            
            result = db.exec(query.bindparams(token=token)).first()
            if not result:
                return None
            
            return {
                'id': result.id,
                'seminaire_id': result.seminaire_id,
                'type_invitation': result.type_invitation,
                'candidat_id': result.candidat_id,
                'promotion_id': result.promotion_id,
                'statut': result.statut,
                'email_envoye': result.email_envoye,
                'date_envoi': result.date_envoi,
                'date_reponse': result.date_reponse,
                'token_invitation': result.token_invitation,
                'cree_le': result.cree_le,
                'candidat_nom': result.candidat_nom,
                'candidat_prenom': result.candidat_prenom,
                'candidat_email': result.candidat_email
            }
        except Exception as e:
            raise e
    
    def get_session(self, session_id: int, db: Session, schema_name: str = 'acd') -> Optional[Dict]:
        """Récupérer une session par son ID via requête SQL directe"""
        try:
            # Configurer le search_path
            db.exec(text(f"SET search_path TO {schema_name}, public"))
            
            query = text(f"""
                SELECT id, seminaire_id, titre, description, type_session, date_session,
                       heure_debut, heure_fin, lieu, visioconf_url, capacite, obligatoire, cree_le
                FROM {schema_name}.session_seminaire
                WHERE id = :session_id
            """)
            
            result = db.exec(query.bindparams(session_id=session_id)).first()
            if not result:
                return None
            
            return {
                'id': result.id,
                'seminaire_id': result.seminaire_id,
                'titre': result.titre,
                'description': result.description,
                'type_session': result.type_session,
                'date_session': result.date_session,
                'heure_debut': result.heure_debut,
                'heure_fin': result.heure_fin,
                'lieu': result.lieu,
                'visioconf_url': result.visioconf_url,
                'capacite': result.capacite,
                'obligatoire': result.obligatoire,
                'cree_le': result.cree_le
            }
        except Exception as e:
            raise e
    
    def get_presence_candidat(self, session_id: int, candidat_id: int, db: Session) -> Optional[PresenceSeminaire]:
        """Récupérer la présence d'un candidat pour une session"""
        query = select(PresenceSeminaire).where(
            PresenceSeminaire.session_id == session_id,
            PresenceSeminaire.candidat_id == candidat_id
        )
        presence = db.exec(query).first()
        if presence:
            # Charger les relations
            db.refresh(presence)
            if presence.candidat_id:
                db.refresh(presence, ['candidat'])
        return presence
    
    def create_presence(self, presence_data: PresenceSeminaireCreate, db: Session) -> PresenceSeminaire:
        """Créer une nouvelle présence"""
        presence = PresenceSeminaire(**presence_data.dict())
        db.add(presence)
        db.commit()
        db.refresh(presence)
        return presence
    
    def submit_livrable(self, livrable_id: int, candidat_id: int, 
                       file_data: Dict, db: Session) -> RenduLivrable:
        """Soumettre un rendu de livrable"""
        rendu = RenduLivrable(
            livrable_id=livrable_id,
            candidat_id=candidat_id,
            nom_fichier=file_data['nom_fichier'],
            chemin_fichier=file_data['chemin_fichier'],
            taille_fichier=file_data['taille_fichier'],
            type_mime=file_data['type_mime'],
            commentaire_candidat=file_data.get('commentaire_candidat')
        )
        db.add(rendu)
        db.commit()
        db.refresh(rendu)
        return rendu

    def get_rendus_livrable(self, livrable_id: int, db: Session) -> List[RenduLivrable]:
        """Récupérer tous les rendus d'un livrable"""
        query = select(RenduLivrable).where(RenduLivrable.livrable_id == livrable_id)
        return db.exec(query).all()

    # === MÉTHODES UTILITAIRES ===
    
    def _generate_invitation_token(self) -> str:
        """Générer un token unique pour les invitations"""
        return ''.join(secrets.choice(string.ascii_letters + string.digits) for _ in range(32))

    def _send_invitation_email(self, invitation: Dict, db: Session, schema_name: str = 'acd'):
        """Envoyer un email d'invitation"""
        try:
            # Configurer le search_path
            db.exec(text(f"SET search_path TO {schema_name}, public"))
            
            # Récupérer les informations du séminaire via requête SQL directe
            seminaire_query = text(f"""
                SELECT id, titre, description, date_debut, date_fin, lieu
                FROM {schema_name}.seminaire
                WHERE id = :seminaire_id
            """)
            seminaire_result = db.exec(seminaire_query.bindparams(seminaire_id=invitation['seminaire_id'])).first()
            if not seminaire_result:
                return
            
            # Récupérer les informations du candidat
            if invitation.get('type_invitation') == TypeInvitation.INDIVIDUELLE.value or str(invitation.get('type_invitation')) == 'TypeInvitation.INDIVIDUELLE':
                candidat_id = invitation.get('candidat_id')
                if not candidat_id:
                    return
                
                # Utiliser les données du candidat déjà dans l'invitation si disponibles
                if invitation.get('candidat'):
                    candidat = invitation['candidat']
                    email = candidat.get('email')
                    nom = f"{candidat.get('prenom', '')} {candidat.get('nom', '')}".strip()
                elif invitation.get('candidat_email'):
                    # Utiliser les champs candidat_* directement
                    email = invitation.get('candidat_email')
                    nom = f"{invitation.get('candidat_prenom', '')} {invitation.get('candidat_nom', '')}".strip()
                else:
                    # Sinon, récupérer depuis la base
                    candidat_query = text(f"""
                        SELECT nom, prenom, email
                        FROM {schema_name}.candidat
                        WHERE id = :candidat_id
                    """)
                    candidat_result = db.exec(candidat_query.bindparams(candidat_id=candidat_id)).first()
                    if not candidat_result:
                        return
                    email = candidat_result.email
                    nom = f"{candidat_result.prenom} {candidat_result.nom}"
            else:
                # Pour les invitations par promotion, on enverra un email générique
                return
            
            # Préparer le contenu de l'email
            subject = f"Invitation au séminaire : {seminaire_result.titre}"
            
            # Générer les URLs dynamiquement
            from ..core.config import settings
            base_url = settings.get_base_url_for_email()
            
            token = invitation.get('token_invitation', '')
            seminaire_id = invitation['seminaire_id']
            
            # Récupérer les sessions du séminaire pour générer les liens d'émargement
            sessions = self.get_sessions_seminaire(seminaire_id, db, schema_name)
            liens_emargement = []
            
            for session in sessions:
                session_id = session['id']
                session_titre = session.get('titre', 'Session')
                # Générer le lien d'émargement pour cette session
                lien_emargement = f"{base_url}/seminaires/{seminaire_id}/sessions/{session_id}/emargement/lien/{token}?programme={schema_name.upper()}"
                liens_emargement.append({
                    'session_id': session_id,
                    'titre': session_titre,
                    'date': session.get('date_session'),
                    'lien': lien_emargement
                })
            
            # Générer les URLs d'acceptation et de refus
            accept_url = f"{base_url}/seminaires/invitation/{token}/accepter?programme={schema_name.upper()}"
            reject_url = f"{base_url}/seminaires/invitation/{token}/refuser?programme={schema_name.upper()}"
            
            template_data = {
                'nom': nom,
                'seminaire_titre': seminaire_result.titre,
                'seminaire_description': seminaire_result.description or '',
                'date_debut': seminaire_result.date_debut.strftime('%d/%m/%Y') if seminaire_result.date_debut else '',
                'date_fin': seminaire_result.date_fin.strftime('%d/%m/%Y') if seminaire_result.date_fin else '',
                'lieu': seminaire_result.lieu or '',
                'token': token,
                'base_url': base_url,
                'liens_emargement': liens_emargement,
                'accept_url': accept_url,
                'reject_url': reject_url
            }
            
            # Mettre à jour les paramètres SMTP depuis la base de données
            # Utiliser le schéma public pour accéder à la table app_setting
            db.exec(text("SET search_path TO public, public"))
            self.email_service.update_smtp_settings(db)
            
            # Envoyer l'email
            try:
                logger.info(f"📧 Tentative d'envoi d'email à {email} pour l'invitation {invitation.get('id')}")
                email_sent = self.email_service.send_template_email(
                    to_email=email,
                    subject=subject,
                    template="seminaire_invitation",
                    data=template_data
                )
                
                if email_sent:
                    # Mettre à jour l'invitation dans la base seulement si l'email a été envoyé avec succès
                    update_query = text(f"""
                        UPDATE {schema_name}.invitation_seminaire
                        SET email_envoye = :email, date_envoi = :date_envoi
                        WHERE id = :invitation_id
                    """)
                    db.exec(update_query.bindparams(
                        email=email,
                        date_envoi=datetime.now(timezone.utc),
                        invitation_id=invitation['id']
                    ))
                    db.commit()
                    logger.info(f"✅ Email envoyé avec succès à {email} et invitation mise à jour")
                else:
                    logger.error(f"❌ Échec de l'envoi de l'email à {email} - invitation non mise à jour")
            except Exception as e:
                logger.error(f"❌ Erreur lors de l'envoi de l'email invitation: {e}", exc_info=True)
        except Exception as e:
            logger.error(f"Erreur dans _send_invitation_email: {e}")

    def get_seminaire_stats(self, db: Session) -> Dict[str, Any]:
        """Obtenir les statistiques globales des séminaires"""
        # Vérifier l'existence de la table seminaire
        if not table_exists_anywhere("seminaire", db):
            print(f"⚠️ [WARNING] Table 'seminaire' manquante pour les statistiques")
            return {"total": 0, "actifs": 0, "programmes": 0}
        
        try:
            seminaires = db.exec(select(Seminaire)).all()
        except Exception as e:
            print(f"⚠️ [WARNING] Erreur lors de la récupération des statistiques séminaires: {e}")
            return {"total": 0, "actifs": 0, "programmes": 0}
        
        stats = {
            'total_seminaires': len(seminaires),
            'seminaires_planifies': len([s for s in seminaires if s.statut == StatutSeminaire.PLANIFIE]),
            'seminaires_en_cours': len([s for s in seminaires if s.statut == StatutSeminaire.EN_COURS]),
            'seminaires_termines': len([s for s in seminaires if s.statut == StatutSeminaire.TERMINE]),
            'total_participants': 0,
            'taux_presence_moyen': 0
        }
        
        # Calculer le taux de présence moyen
        total_presences = 0
        total_present = 0
        
        for seminaire in seminaires:
            sessions = self.get_sessions_seminaire(seminaire.id, db)
            for session in sessions:
                session_stats = self.get_presence_stats(session.id, db)
                total_presences += session_stats['total']
                total_present += session_stats['present']
        
        if total_presences > 0:
            stats['taux_presence_moyen'] = round((total_present / total_presences) * 100, 2)
        
        return stats
