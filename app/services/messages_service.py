# app/services/messages_service.py
"""
Service de gestion des messages internes
"""
from typing import List, Optional, Dict, Any
from sqlmodel import Session, select, and_, or_, func
from datetime import datetime, timezone
import logging

from ..models.base import User
from ..models.message import Conversation, Message

logger = logging.getLogger(__name__)


class MessagesService:
    """Service de gestion des messages internes"""
    
    @staticmethod
    def get_or_create_conversation(session: Session, user1_id: int, user2_id: int) -> Conversation:
        """Récupère ou crée une conversation entre deux utilisateurs"""
        # Normaliser les IDs pour éviter les doublons (user1_id < user2_id)
        if user1_id > user2_id:
            user1_id, user2_id = user2_id, user1_id
        
        # Chercher une conversation existante
        conversation = session.exec(
            select(Conversation).where(
                and_(
                    Conversation.user1_id == user1_id,
                    Conversation.user2_id == user2_id
                )
            )
        ).first()
        
        if not conversation:
            # Créer une nouvelle conversation
            conversation = Conversation(
                user1_id=user1_id,
                user2_id=user2_id
            )
            session.add(conversation)
            session.commit()
            session.refresh(conversation)
        
        return conversation
    
    @staticmethod
    def send_message(session: Session, sender_id: int, receiver_id: int, content: str) -> Message:
        """Envoie un message"""
        # Récupérer ou créer la conversation
        conversation = MessagesService.get_or_create_conversation(session, sender_id, receiver_id)
        
        # Créer le message
        message = Message(
            conversation_id=conversation.id,
            sender_id=sender_id,
            content=content,
            lu=False
        )
        session.add(message)
        
        # Mettre à jour la date de modification de la conversation
        conversation.modifie_le = datetime.now(timezone.utc)
        
        session.commit()
        session.refresh(message)
        return message
    
    @staticmethod
    def get_conversations(session: Session, user_id: int) -> List[Dict[str, Any]]:
        """Récupère toutes les conversations d'un utilisateur avec leurs métadonnées"""
        # Récupérer toutes les conversations où l'utilisateur est impliqué
        conversations = session.exec(
            select(Conversation).where(
                or_(
                    Conversation.user1_id == user_id,
                    Conversation.user2_id == user_id
                )
            ).order_by(Conversation.modifie_le.desc())
        ).all()
        
        result = []
        for conv in conversations:
            # Déterminer l'autre utilisateur
            if conv.user1_id == user_id:
                other_user_id = conv.user2_id
            else:
                other_user_id = conv.user1_id
            
            # Récupérer l'autre utilisateur
            other_user = session.get(User, other_user_id)
            if not other_user:
                continue
            
            # Récupérer le dernier message
            last_message = session.exec(
                select(Message)
                .where(Message.conversation_id == conv.id)
                .order_by(Message.cree_le.desc())
                .limit(1)
            ).first()
            
            # Compter les messages non lus
            unread_count = session.exec(
                select(func.count(Message.id))
                .where(
                    and_(
                        Message.conversation_id == conv.id,
                        Message.sender_id != user_id,
                        Message.lu == False
                    )
                )
            ).one()
            
            result.append({
                "id": conv.id,
                "user1_id": conv.user1_id,
                "user2_id": conv.user2_id,
                "other_user_id": other_user_id,
                "other_user_name": other_user.nom_complet,
                "last_message_preview": last_message.content[:100] if last_message else None,
                "last_message_at": last_message.cree_le.isoformat() if last_message and last_message.cree_le else (conv.modifie_le.isoformat() if conv.modifie_le else None),
                "unread_count": unread_count or 0
            })
        
        return result
    
    @staticmethod
    def get_messages(session: Session, conversation_id: int, user_id: int) -> List[Dict[str, Any]]:
        """Récupère tous les messages d'une conversation"""
        # Vérifier que l'utilisateur fait partie de la conversation
        conversation = session.get(Conversation, conversation_id)
        if not conversation:
            return []
        
        if conversation.user1_id != user_id and conversation.user2_id != user_id:
            return []
        
        # Récupérer les messages
        messages = session.exec(
            select(Message)
            .where(Message.conversation_id == conversation_id)
            .order_by(Message.cree_le.asc())
        ).all()
        
        # Marquer les messages reçus comme lus
        for message in messages:
            if message.sender_id != user_id and not message.lu:
                message.lu = True
                session.add(message)
        
        session.commit()
        
        # Formater les messages
        result = []
        for msg in messages:
            result.append({
                "id": msg.id,
                "conversation_id": msg.conversation_id,
                "sender_id": msg.sender_id,
                "content": msg.content,
                "is_own": msg.sender_id == user_id,
                "lu": msg.lu,
                "created_at": msg.cree_le.isoformat() if msg.cree_le else None
            })
        
        return result
    
    @staticmethod
    def search_users(session: Session, user_id: int, query: Optional[str] = None) -> List[Dict[str, Any]]:
        """Recherche des utilisateurs pour démarrer une conversation"""
        # Construire la requête
        stmt = select(User).where(User.actif == True)
        
        if query:
            # Rechercher par nom ou email
            search_term = f"%{query.lower()}%"
            stmt = stmt.where(
                or_(
                    func.lower(User.nom_complet).like(search_term),
                    func.lower(User.email).like(search_term)
                )
            )
        
        # Exclure l'utilisateur actuel
        stmt = stmt.where(User.id != user_id)
        
        # Limiter les résultats
        users = session.exec(stmt.limit(20)).all()
        
        result = []
        for user in users:
            result.append({
                "id": user.id,
                "full_name": user.nom_complet,
                "email": user.email
            })
        
        return result
    
    @staticmethod
    def get_unread_count(session: Session, user_id: int) -> int:
        """Compte le nombre total de messages non lus pour un utilisateur"""
        # Récupérer toutes les conversations de l'utilisateur
        conversations = session.exec(
            select(Conversation.id).where(
                or_(
                    Conversation.user1_id == user_id,
                    Conversation.user2_id == user_id
                )
            )
        ).all()
        
        if not conversations:
            return 0
        
        # Compter les messages non lus
        unread_count = session.exec(
            select(func.count(Message.id))
            .where(
                and_(
                    Message.conversation_id.in_(conversations),
                    Message.sender_id != user_id,
                    Message.lu == False
                )
            )
        ).one()
        
        return unread_count or 0

