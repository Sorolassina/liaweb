# app/models/message.py
from sqlmodel import SQLModel, Field, Relationship
from typing import Optional, List
from datetime import datetime, timezone

class Conversation(SQLModel, table=True):
    """Conversation entre deux utilisateurs"""
    __tablename__ = "conversation"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    user1_id: int = Field(foreign_key="user.id", index=True)
    user2_id: int = Field(foreign_key="user.id", index=True)
    cree_le: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    modifie_le: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    
    # Relations
    user1: "User" = Relationship(
        sa_relationship_kwargs={"foreign_keys": "[Conversation.user1_id]"}
    )
    user2: "User" = Relationship(
        sa_relationship_kwargs={"foreign_keys": "[Conversation.user2_id]"}
    )
    messages: List["Message"] = Relationship(back_populates="conversation")


class Message(SQLModel, table=True):
    """Message dans une conversation"""
    __tablename__ = "message"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    conversation_id: int = Field(foreign_key="conversation.id", index=True)
    sender_id: int = Field(foreign_key="user.id", index=True)
    content: str
    lu: bool = Field(default=False, index=True)
    cree_le: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    
    # Relations
    conversation: Conversation = Relationship(back_populates="messages")
    sender: "User" = Relationship()

