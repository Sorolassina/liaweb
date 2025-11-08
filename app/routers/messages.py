# app/routers/messages.py
"""
Router pour la messagerie interne
"""
from fastapi import APIRouter, Depends, HTTPException, status, Query
from fastapi.responses import JSONResponse
from sqlmodel import Session
from typing import List, Optional

from ..core.database import get_session
from ..core.middleware import get_shared_session
from ..core.security import get_current_user
from ..models.base import User
from ..schemas.message_schemas import (
    MessageCreate, MessageResponse, ConversationResponse,
    UserSearchResponse, UnreadCountResponse
)
from ..services.messages_service import MessagesService

router = APIRouter()


@router.post("/send", name="send_message")
async def send_message(
    message_data: MessageCreate,
    session: Session = Depends(get_shared_session),
    current_user: User = Depends(get_current_user)
):
    """Envoie un message à un utilisateur"""
    # Vérifier que le destinataire existe
    receiver = session.get(User, message_data.receiver_id)
    if not receiver:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Destinataire non trouvé"
        )
    
    if receiver.id == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Vous ne pouvez pas vous envoyer un message"
        )
    
    # Envoyer le message
    message = MessagesService.send_message(
        session,
        current_user.id,
        message_data.receiver_id,
        message_data.content
    )
    
    # Retourner le message avec conversation_id pour que le frontend puisse l'utiliser
    return {
        "id": message.id,
        "conversation_id": message.conversation_id,
        "sender_id": message.sender_id,
        "content": message.content,
        "lu": message.lu,
        "created_at": message.cree_le.isoformat() if message.cree_le else None
    }


@router.get("/conversations", name="get_conversations")
async def get_conversations(
    session: Session = Depends(get_shared_session),
    current_user: User = Depends(get_current_user)
):
    """Récupère toutes les conversations de l'utilisateur connecté"""
    conversations = MessagesService.get_conversations(session, current_user.id)
    
    # Convertir les dates en format ISO string pour JSON
    result = []
    for conv in conversations:
        last_message_at = conv["last_message_at"]
        if hasattr(last_message_at, 'isoformat'):
            last_message_at = last_message_at.isoformat()
        
        result.append({
            "id": conv["id"],
            "user1_id": conv["user1_id"],
            "user2_id": conv["user2_id"],
            "other_user_id": conv["other_user_id"],
            "other_user_name": conv["other_user_name"],
            "last_message_preview": conv["last_message_preview"],
            "last_message_at": last_message_at,
            "unread_count": conv["unread_count"]
        })
    
    return result


@router.get("/conversations/{conversation_id}/messages", name="get_messages")
async def get_messages(
    conversation_id: int,
    session: Session = Depends(get_shared_session),
    current_user: User = Depends(get_current_user)
):
    """Récupère tous les messages d'une conversation"""
    messages = MessagesService.get_messages(session, conversation_id, current_user.id)
    
    if not messages:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversation non trouvée ou accès refusé"
        )
    
    # Convertir les dates en format ISO string pour JSON
    result = []
    for msg in messages:
        created_at = msg["created_at"]
        if hasattr(created_at, 'isoformat'):
            created_at = created_at.isoformat()
        
        result.append({
            "id": msg["id"],
            "conversation_id": msg["conversation_id"],
            "sender_id": msg["sender_id"],
            "content": msg["content"],
            "is_own": msg["is_own"],
            "lu": msg["lu"],
            "created_at": created_at
        })
    
    return result


@router.get("/users/search", name="search_users")
async def search_users(
    q: Optional[str] = Query(None, description="Terme de recherche"),
    session: Session = Depends(get_shared_session),
    current_user: User = Depends(get_current_user)
):
    """Recherche des utilisateurs pour démarrer une conversation"""
    users = MessagesService.search_users(session, current_user.id, q)
    
    return users


@router.get("/unread-count", name="get_unread_count")
async def get_unread_count(
    session: Session = Depends(get_shared_session),
    current_user: User = Depends(get_current_user)
):
    """Récupère le nombre de messages non lus de l'utilisateur connecté"""
    unread_count = MessagesService.get_unread_count(session, current_user.id)
    
    return {"unread_count": unread_count}

