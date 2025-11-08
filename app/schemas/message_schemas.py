# app/schemas/message_schemas.py
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime

class MessageCreate(BaseModel):
    """Schéma pour créer un message"""
    receiver_id: int
    content: str = Field(..., min_length=1, max_length=5000)

class MessageResponse(BaseModel):
    """Schéma de réponse pour un message"""
    id: int
    conversation_id: int
    sender_id: int
    content: str
    lu: bool
    created_at: datetime
    
    class Config:
        from_attributes = True

class ConversationResponse(BaseModel):
    """Schéma de réponse pour une conversation"""
    id: int
    user1_id: int
    user2_id: int
    other_user_id: int
    other_user_name: str
    last_message_preview: Optional[str] = None
    last_message_at: Optional[datetime] = None
    unread_count: int = 0
    
    class Config:
        from_attributes = True

class UserSearchResponse(BaseModel):
    """Schéma pour les résultats de recherche d'utilisateurs"""
    id: int
    full_name: str
    email: str
    
    class Config:
        from_attributes = True

class UnreadCountResponse(BaseModel):
    """Schéma pour le nombre de messages non lus"""
    unread_count: int

