# app/services/seminaire_service.py
from sqlmodel import Session, select, and_, or_
from typing import List, Optional, Dict, Any
from datetime import datetime, timezone, date
import secrets
import string
from app_lia_web.core.database import get_session
from app_lia_web.app.models.seminaire import (
    Seminaire, SessionSeminaire, InvitationSeminaire, 
    PresenceSeminaire, LivrableSeminaire, RenduLivrable
)
from app_lia_web.app.models.base import Inscription, Programme, User, Promotion, Candidat
from app_lia_web.app.models.enums import StatutSeminaire, TypeInvitation, StatutPresence
from app_lia_web.app.schemas.seminaire_schemas import (
    SeminaireCreate, SeminaireUpdate, SessionSeminaireCreate,
    InvitationSeminaireCreate, PresenceSeminaireCreate, LivrableSeminaireCreate
)
from app_lia_web.app.services.email_service import EmailService

class SeminaireService:
    def __init__(self):
        self.email_service = EmailService()

    # === GESTION DES SÉMINAIRES ===
    
    def create_seminaire(self, seminaire_data: SeminaireCreate, db: Session) -> Seminaire:
        """Créer un nouveau séminaire"""
        seminaire = Seminaire(**seminaire_data.dict())
        db.add(seminaire)
        db.commit()
        db.refresh(seminaire)
        return seminaire

    def get_seminaire(self, seminaire_id: int, db: Session) -> Optional[Seminaire]:
        """Récupérer un séminaire par son ID"""
        return db.get(Seminaire, seminaire_id)

    def get_seminaires(self, db: Session, filters: Optional[Dict] = None) -> List[Seminaire]:
        """Récupérer la liste des séminaires avec filtres"""
        query = select(Seminaire)
        
        if filters:
            if filters.get('programme_id'):
                query = query.where(Seminaire.programme_id == filters['programme_id'])
            if filters.get('statut'):
                query = query.where(Seminaire.statut == filters['statut'])
            if filters.get('organisateur_id'):
                query = query.where(Seminaire.organisateur_id == filters['organisateur_id'])
            if filters.get('actif') is not None:
                query = query.where(Seminaire.actif == filters['actif'])
            if filters.get('date_debut_from'):
                query = query.where(Seminaire.date_debut >= filters['date_debut_from'])
            if filters.get('date_debut_to'):
                query = query.where(Seminaire.date_debut <= filters['date_debut_to'])
        
        query = query.order_by(Seminaire.date_debut.desc())
        return db.exec(query).all()

    def update_seminaire(self, seminaire_id: int, seminaire_data: SeminaireUpdate, db: Session) -> Optional[Seminaire]:
        """Mettre à jour un séminaire"""
        seminaire = db.get(Seminaire, seminaire_id)
        if not seminaire:
            return None
        
        update_data = seminaire_data.dict(exclude_unset=True)
        for field, value in update_data.items():
            setattr(seminaire, field, value)
        
        seminaire.modifie_le = datetime.now(timezone.utc)
        db.commit()
        db.refresh(seminaire)
        return seminaire

    def delete_seminaire(self, seminaire_id: int, db: Session) -> bool:
        """Supprimer un séminaire (soft delete)"""
        seminaire = db.get(Seminaire, seminaire_id)
        if not seminaire:
            return False
        
        seminaire.actif = False
        db.commit()
        return True
    
    def remove_participant_from_session(self, seminaire_id: int, session_id: int, inscription_id: int, db: Session) -> bool:
        """Supprimer un participant d'une session de séminaire"""
        try:
            # Supprimer l'invitation au séminaire (pas de session spécifique)
            invitation_query = select(InvitationSeminaire).where(
                InvitationSeminaire.seminaire_id == seminaire_id,
                InvitationSeminaire.inscription_id == inscription_id
            )
            invitation = db.exec(invitation_query).first()
            
            if invitation:
                db.delete(invitation)
            
            # Supprimer la présence de cette session spécifique
            presence_query = select(PresenceSeminaire).where(
                PresenceSeminaire.session_id == session_id,
                PresenceSeminaire.inscription_id == inscription_id
            )
            presence = db.exec(presence_query).first()
            
            if presence:
                db.delete(presence)
            
            db.commit()
            return True
            
        except Exception as e:
            print(f"Erreur lors de la suppression du participant: {e}")
            db.rollback()
            return False

    # === GESTION DES SESSIONS ===
    
    def create_session(self, session_data: SessionSeminaireCreate, db: Session) -> SessionSeminaire:
        """Créer une nouvelle session de séminaire"""
        session = SessionSeminaire(**session_data.dict())
        db.add(session)
        db.commit()
        db.refresh(session)
        return session

    def get_sessions_seminaire(self, seminaire_id: int, db: Session) -> List[SessionSeminaire]:
        """Récupérer toutes les sessions d'un séminaire"""
        query = select(SessionSeminaire).where(SessionSeminaire.seminaire_id == seminaire_id)
        query = query.order_by(SessionSeminaire.date_session, SessionSeminaire.heure_debut)
        return db.exec(query).all()

    def update_session(self, session_id: int, session_data: Dict, db: Session) -> Optional[SessionSeminaire]:
        """Mettre à jour une session"""
        session = db.get(SessionSeminaire, session_id)
        if not session:
            return None
        
        for field, value in session_data.items():
            if hasattr(session, field):
                setattr(session, field, value)
        
        db.commit()
        db.refresh(session)
        return session

    # === GESTION DES INVITATIONS ===
    
    def create_invitation(self, invitation_data: InvitationSeminaireCreate, db: Session) -> InvitationSeminaire:
        """Créer une invitation"""
        invitation = InvitationSeminaire(**invitation_data.dict())
        invitation.token_invitation = self._generate_invitation_token()
        db.add(invitation)
        db.commit()
        db.refresh(invitation)
        return invitation

    def send_invitations_bulk(self, seminaire_id: int, type_invitation: TypeInvitation, 
                             target_ids: List[int], db: Session) -> List[InvitationSeminaire]:
        """Envoyer des invitations en masse"""
        invitations = []
        
        for target_id in target_ids:
            invitation_data = {
                'seminaire_id': seminaire_id,
                'type_invitation': type_invitation,
                'token_invitation': self._generate_invitation_token()
            }
            
            if type_invitation == TypeInvitation.INDIVIDUELLE:
                invitation_data['inscription_id'] = target_id
            elif type_invitation == TypeInvitation.PROMOTION:
                invitation_data['promotion_id'] = target_id
            
            invitation = InvitationSeminaire(**invitation_data)
            db.add(invitation)
            invitations.append(invitation)
        
        db.commit()
        
        # Envoyer les emails d'invitation
        for invitation in invitations:
            self._send_invitation_email(invitation, db)
        
        return invitations

    def get_invitations_seminaire(self, seminaire_id: int, db: Session) -> List[InvitationSeminaire]:
        """Récupérer toutes les invitations d'un séminaire"""
        query = select(InvitationSeminaire).where(InvitationSeminaire.seminaire_id == seminaire_id)
        return db.exec(query).all()

    def accept_invitation(self, token: str, db: Session) -> Optional[InvitationSeminaire]:
        """Accepter une invitation via token"""
        query = select(InvitationSeminaire).where(InvitationSeminaire.token_invitation == token)
        invitation = db.exec(query).first()
        
        if invitation and invitation.statut == "ENVOYEE":
            invitation.statut = "ACCEPTEE"
            invitation.date_reponse = datetime.now(timezone.utc)
            db.commit()
            db.refresh(invitation)
        
        return invitation

    def reject_invitation(self, token: str, db: Session) -> Optional[InvitationSeminaire]:
        """Refuser une invitation via token"""
        query = select(InvitationSeminaire).where(InvitationSeminaire.token_invitation == token)
        invitation = db.exec(query).first()
        
        if invitation and invitation.statut == "ENVOYEE":
            invitation.statut = "REFUSEE"
            invitation.date_reponse = datetime.now(timezone.utc)
            db.commit()
            db.refresh(invitation)
        
        return invitation

    # === GESTION DE LA PRÉSENCE ===
    
    def mark_presence(self, presence_data: PresenceSeminaireCreate, db: Session) -> PresenceSeminaire:
        """Marquer la présence d'un participant"""
        # Vérifier si une présence existe déjà
        query = select(PresenceSeminaire).where(
            and_(
                PresenceSeminaire.session_id == presence_data.session_id,
                PresenceSeminaire.inscription_id == presence_data.inscription_id
            )
        )
        existing_presence = db.exec(query).first()
        
        if existing_presence:
            # Mettre à jour la présence existante
            for field, value in presence_data.dict().items():
                if field not in ['session_id', 'inscription_id']:  # Exclure les champs de clé
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
            presence = PresenceSeminaire(**presence_data.dict())
            
            # Enregistrer l'heure d'arrivée si on marque "present"
            if presence_data.presence == "present":
                presence.heure_arrivee = datetime.now(timezone.utc)
            
            db.add(presence)
            db.commit()
            db.refresh(presence)
        return presence
    
    def delete_seminaire(self, seminaire_id: int, db: Session) -> bool:
        """Supprimer un séminaire et toutes ses données associées"""
        try:
            # Récupérer le séminaire
            seminaire = db.get(Seminaire, seminaire_id)
            if not seminaire:
                return False
            
            # Supprimer manuellement les données liées dans l'ordre correct
            # 1. Supprimer les livrables du séminaire
            from app_lia_web.app.models.seminaire import LivrableSeminaire
            livrables_query = select(LivrableSeminaire).where(LivrableSeminaire.seminaire_id == seminaire_id)
            livrables = db.exec(livrables_query).all()
            for livrable in livrables:
                db.delete(livrable)
            
            # 2. Supprimer les présences des sessions du séminaire
            sessions_query = select(SessionSeminaire).where(SessionSeminaire.seminaire_id == seminaire_id)
            sessions = db.exec(sessions_query).all()
            
            for session in sessions:
                presences_query = select(PresenceSeminaire).where(PresenceSeminaire.session_id == session.id)
                presences = db.exec(presences_query).all()
                for presence in presences:
                    db.delete(presence)
            
            # 3. Supprimer les sessions du séminaire
            for session in sessions:
                db.delete(session)
            
            # 4. Supprimer les invitations du séminaire
            invitations_query = select(InvitationSeminaire).where(InvitationSeminaire.seminaire_id == seminaire_id)
            invitations = db.exec(invitations_query).all()
            for invitation in invitations:
                db.delete(invitation)
            
            # 5. Supprimer le séminaire lui-même
            db.delete(seminaire)
            db.commit()
            return True
            
        except Exception as e:
            db.rollback()
            print(f"Erreur lors de la suppression du séminaire {seminaire_id}: {e}")
            return False
    
    def delete_session(self, session_id: int, db: Session) -> bool:
        """Supprimer une session et toutes ses données associées"""
        try:
            # Récupérer la session
            session = db.get(SessionSeminaire, session_id)
            if not session:
                return False
            
            # Supprimer manuellement les données liées
            # 1. Supprimer les présences de la session
            presences_query = select(PresenceSeminaire).where(PresenceSeminaire.session_id == session_id)
            presences = db.exec(presences_query).all()
            for presence in presences:
                db.delete(presence)
            
            # 2. Supprimer la session elle-même
            db.delete(session)
            db.commit()
            return True
            
        except Exception as e:
            db.rollback()
            print(f"Erreur lors de la suppression de la session {session_id}: {e}")
            return False
    
    def get_presences_session(self, session_id: int, db: Session) -> List[PresenceSeminaire]:
        """Récupérer toutes les présences d'une session"""
        query = select(PresenceSeminaire).where(PresenceSeminaire.session_id == session_id)
        return db.exec(query).all()
    
    def get_presences_with_invitations(self, seminaire_id: int, session_id: int, db: Session) -> List[PresenceSeminaire]:
        """Récupérer toutes les présences pour une session, créant des enregistrements par défaut pour tous les invités"""
        from sqlalchemy.orm import selectinload
        
        # Récupérer toutes les invitations pour ce séminaire (acceptées ET refusées)
        query_invitations = select(InvitationSeminaire).where(
            InvitationSeminaire.seminaire_id == seminaire_id
        )
        invitations = db.exec(query_invitations).all()
        
        presences = []
        
        for invitation in invitations:
            # Charger les relations de l'invitation
            db.refresh(invitation)
            
            # Vérifier si une présence existe déjà pour cette session
            existing_presence_query = select(PresenceSeminaire).options(
                selectinload(PresenceSeminaire.inscription).selectinload(Inscription.candidat)
            ).where(
                PresenceSeminaire.session_id == session_id,
                PresenceSeminaire.inscription_id == invitation.inscription_id
            )
            existing_presence = db.exec(existing_presence_query).first()
            
            if existing_presence:
                presences.append(existing_presence)
            else:
                # Créer une présence par défaut avec statut ABSENT et la sauvegarder
                # Récupérer l'inscription avec ses relations chargées
                inscription_query = select(Inscription).options(
                    selectinload(Inscription.candidat)
                ).where(Inscription.id == invitation.inscription_id)
                inscription = db.exec(inscription_query).first()
                
                if inscription:
                    
                    # Déterminer le statut par défaut selon l'invitation et la date
                    default_status = "en_attente"  # Par défaut en attente
                    
                    # Vérifier si l'événement est déjà passé
                    session_obj = db.get(SessionSeminaire, session_id)
                    if session_obj and session_obj.date_session:
                        from datetime import date
                        today = date.today()
                        if session_obj.date_session < today:
                            # L'événement est passé, mettre absent par défaut
                            default_status = "absent"
                    
                    # Si l'invitation est refusée, mettre absent même si l'événement n'est pas passé
                    if invitation.statut == "REFUSEE":
                        default_status = "absent"
                    
                    default_presence = PresenceSeminaire(
                        session_id=session_id,
                        inscription_id=invitation.inscription_id,
                        presence=default_status
                    )
                    # Sauvegarder la présence par défaut en base
                    db.add(default_presence)
                    db.commit()
                    db.refresh(default_presence)
                    # Assigner manuellement l'inscription pour l'affichage
                    default_presence.inscription = inscription
                    presences.append(default_presence)
        
        return presences
    
    def get_presences_for_direct_emargement(self, seminaire_id: int, session_id: int, db: Session) -> List[PresenceSeminaire]:
        """Récupérer les présences pour l'émargement direct - seulement les présences existantes en base"""
        from sqlalchemy.orm import selectinload
        
        # Récupérer toutes les invitations pour ce séminaire (acceptées ET refusées)
        query_invitations = select(InvitationSeminaire).where(
            InvitationSeminaire.seminaire_id == seminaire_id
        )
        invitations = db.exec(query_invitations).all()
        
        presences = []
        
        for invitation in invitations:
            # Charger les relations de l'invitation
            db.refresh(invitation)
            
            # Vérifier si une présence existe déjà pour cette session
            existing_presence_query = select(PresenceSeminaire).options(
                selectinload(PresenceSeminaire.inscription).selectinload(Inscription.candidat)
            ).where(
                PresenceSeminaire.session_id == session_id,
                PresenceSeminaire.inscription_id == invitation.inscription_id
            )
            existing_presence = db.exec(existing_presence_query).first()
            
            if existing_presence:
                presences.append(existing_presence)
            # Ne pas créer de présences temporaires - seulement retourner celles qui existent vraiment
        
        return presences
    
    def get_presences_with_invitation_details(self, seminaire_id: int, session_id: int, db: Session) -> List[Dict]:
        """Récupérer toutes les présences avec les détails d'invitation pour une session"""
        # Récupérer toutes les invitations pour ce séminaire (acceptées ET refusées)
        query_invitations = select(InvitationSeminaire).where(
            InvitationSeminaire.seminaire_id == seminaire_id
        )
        invitations = db.exec(query_invitations).all()
        
        presences_data = []
        
        for invitation in invitations:
            # Charger les relations de l'invitation
            db.refresh(invitation)
            
            # Vérifier si une présence existe déjà pour cette session
            existing_presence = self.get_presence_candidat(session_id, invitation.inscription_id, db)
            
            if existing_presence:
                # Charger les relations de la présence existante
                db.refresh(existing_presence)
                presence_obj = existing_presence
            else:
                # Créer une présence par défaut avec statut ABSENT et la sauvegarder
                inscription = db.get(Inscription, invitation.inscription_id)
                if inscription:
                    db.refresh(inscription)
                    if inscription.candidat:
                        db.refresh(inscription.candidat)
                    
                    # Déterminer le statut par défaut selon l'invitation et la date
                    default_status = "en_attente"  # Par défaut en attente
                    
                    # Vérifier si l'événement est déjà passé
                    session_obj = db.get(SessionSeminaire, session_id)
                    if session_obj and session_obj.date_session:
                        from datetime import date
                        today = date.today()
                        if session_obj.date_session < today:
                            # L'événement est passé, mettre absent par défaut
                            default_status = "absent"
                    
                    # Si l'invitation est refusée, mettre absent même si l'événement n'est pas passé
                    if invitation.statut == "REFUSEE":
                        default_status = "absent"
                    
                    default_presence = PresenceSeminaire(
                        session_id=session_id,
                        inscription_id=invitation.inscription_id,
                        presence=default_status
                    )
                    db.add(default_presence)
                    db.commit()
                    db.refresh(default_presence)
                    default_presence.inscription = inscription
                    presence_obj = default_presence
                else:
                    continue
            
            # Créer l'objet de données enrichi
            presence_data = {
                'presence': presence_obj,
                'invitation': invitation,
                'invitation_statut': invitation.statut
            }
            presences_data.append(presence_data)
        
        return presences_data

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
        
    def get_presence_stats_with_invitations(self, seminaire_id: int, session_id: int, db: Session) -> Dict[str, int]:
        """Obtenir les statistiques de présence pour une session avec invitations"""
        presences = self.get_presences_with_invitations(seminaire_id, session_id, db)
        
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

    # === GESTION DES LIVRABLES ===
    
    def create_livrable(self, livrable_data: LivrableSeminaireCreate, db: Session) -> LivrableSeminaire:
        """Créer un livrable pour un séminaire"""
        livrable = LivrableSeminaire(**livrable_data.dict())
        db.add(livrable)
        db.commit()
        db.refresh(livrable)
        return livrable

    def get_livrables_seminaire(self, seminaire_id: int, db: Session) -> List[LivrableSeminaire]:
        """Récupérer tous les livrables d'un séminaire"""
        query = select(LivrableSeminaire).where(LivrableSeminaire.seminaire_id == seminaire_id)
        return db.exec(query).all()

    def get_inscription_candidat(self, seminaire_id: int, user_email: str, db: Session) -> Optional[Inscription]:
        """Récupérer l'inscription d'un candidat pour un séminaire"""
        # D'abord récupérer le séminaire pour obtenir le programme_id
        seminaire = self.get_seminaire(seminaire_id, db)
        if not seminaire:
            return None
            
        # Chercher l'inscription du candidat dans le programme du séminaire via l'email
        query = select(Inscription).join(Candidat).where(
            Inscription.programme_id == seminaire.programme_id,
            Candidat.email == user_email
        )
        return db.exec(query).first()
    
    def get_rendus_candidat(self, inscription_id: int, db: Session) -> List[RenduLivrable]:
        """Récupérer tous les rendus d'un candidat"""
        query = select(RenduLivrable).where(RenduLivrable.inscription_id == inscription_id)
        return list(db.exec(query).all())
    
    def get_invitations_seminaire(self, seminaire_id: int, db: Session) -> List[InvitationSeminaire]:
        """Récupérer toutes les invitations d'un séminaire (sans doublons par candidat)"""
        # Récupérer les invitations avec toutes les relations chargées
        query = select(InvitationSeminaire).where(
            InvitationSeminaire.seminaire_id == seminaire_id,
            InvitationSeminaire.inscription_id.isnot(None)
        )
        
        all_invitations = list(db.exec(query).all())
        
        # Charger toutes les relations en une fois pour éviter les requêtes N+1
        for invitation in all_invitations:
            db.refresh(invitation, ['inscription'])
            if invitation.inscription:
                db.refresh(invitation.inscription, ['candidat', 'promotion'])
        
        # Éviter les doublons par candidat (garder la plus récente)
        seen_candidates = {}
        
        for invitation in all_invitations:
            if invitation.inscription:
                candidat_id = invitation.inscription.candidat_id
                # Garder seulement la plus récente invitation par candidat
                if candidat_id not in seen_candidates or invitation.id > seen_candidates[candidat_id].id:
                    seen_candidates[candidat_id] = invitation
        
        return list(seen_candidates.values())
    
    def get_invitation(self, invitation_id: int, db: Session) -> Optional[InvitationSeminaire]:
        """Récupérer une invitation par son ID"""
        query = select(InvitationSeminaire).where(InvitationSeminaire.id == invitation_id)
        return db.exec(query).first()
    
    def get_invitation_by_token(self, token: str, db: Session) -> Optional[InvitationSeminaire]:
        """Récupérer une invitation par son token"""
        query = select(InvitationSeminaire).where(InvitationSeminaire.token_invitation == token)
        return db.exec(query).first()
    
    def get_session(self, session_id: int, db: Session) -> Optional[SessionSeminaire]:
        """Récupérer une session par son ID"""
        query = select(SessionSeminaire).where(SessionSeminaire.id == session_id)
        return db.exec(query).first()
    
    def get_presence_candidat(self, session_id: int, inscription_id: int, db: Session) -> Optional[PresenceSeminaire]:
        """Récupérer la présence d'un candidat pour une session"""
        query = select(PresenceSeminaire).where(
            PresenceSeminaire.session_id == session_id,
            PresenceSeminaire.inscription_id == inscription_id
        )
        presence = db.exec(query).first()
        if presence:
            # Charger les relations
            db.refresh(presence)
            if presence.inscription and presence.inscription.candidat:
                db.refresh(presence.inscription.candidat)
        return presence
    
    def create_presence(self, presence_data: PresenceSeminaireCreate, db: Session) -> PresenceSeminaire:
        """Créer une nouvelle présence"""
        presence = PresenceSeminaire(**presence_data.dict())
        db.add(presence)
        db.commit()
        db.refresh(presence)
        return presence
    
    def submit_livrable(self, livrable_id: int, inscription_id: int, 
                       file_data: Dict, db: Session) -> RenduLivrable:
        """Soumettre un rendu de livrable"""
        rendu = RenduLivrable(
            livrable_id=livrable_id,
            inscription_id=inscription_id,
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

    def _send_invitation_email(self, invitation: InvitationSeminaire, db: Session):
        """Envoyer un email d'invitation"""
        # Récupérer les informations nécessaires
        seminaire = db.get(Seminaire, invitation.seminaire_id)
        if not seminaire:
            return
        
        if invitation.type_invitation == TypeInvitation.INDIVIDUELLE and invitation.inscription_id:
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
        subject = f"Invitation au séminaire : {seminaire.titre}"
        
        # Générer les URLs dynamiquement
        from app_lia_web.core.config import settings
        base_url = settings.get_base_url_for_email()
        
        template_data = {
            'nom': nom,
            'seminaire_titre': seminaire.titre,
            'seminaire_description': seminaire.description,
            'date_debut': seminaire.date_debut.strftime('%d/%m/%Y'),
            'date_fin': seminaire.date_fin.strftime('%d/%m/%Y'),
            'lieu': seminaire.lieu,
            'token': invitation.token_invitation,
            'base_url': base_url,
            'accept_url': f"{base_url}/seminaires/invitation/{invitation.token_invitation}/accepter",
            'reject_url': f"{base_url}/seminaires/invitation/{invitation.token_invitation}/refuser"
        }
        
        # Envoyer l'email
        try:
            self.email_service.send_template_email(
                to_email=email,
                subject=subject,
                template="seminaire_invitation",
                data=template_data
            )
            invitation.email_envoye = email
            invitation.date_envoi = datetime.now(timezone.utc)
            db.commit()
        except Exception as e:
            print(f"Erreur envoi email invitation: {e}")

    def get_seminaire_stats(self, db: Session) -> Dict[str, Any]:
        """Obtenir les statistiques globales des séminaires"""
        seminaires = db.exec(select(Seminaire)).all()
        
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
