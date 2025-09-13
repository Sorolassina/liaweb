# app/models/ACD/permissions.py
from __future__ import annotations
from typing import Dict, List, Optional, Set
from sqlmodel import SQLModel, Field, Relationship
from datetime import datetime, timezone
from enum import Enum

class NiveauPermission(str, Enum):
    """Niveaux de permission"""
    LECTURE = "lecture"           # Lecture seule
    ECRITURE = "ecriture"         # Lecture + écriture
    SUPPRESSION = "suppression"   # Lecture + écriture + suppression
    ADMIN = "admin"              # Tous les droits

class TypeRessource(str, Enum):
    """Types de ressources dans le système"""
    UTILISATEURS = "utilisateurs"
    PROGRAMMES = "programmes"
    CANDIDATS = "candidats"
    INSCRIPTIONS = "inscriptions"
    JURYS = "jurys"
    DOCUMENTS = "documents"
    LOGS = "logs"
    PARAMETRES = "parametres"
    SAUVEGARDE = "sauvegarde"
    ARCHIVE = "archive"

class PermissionRole(SQLModel, table=True):
    """Matrice des permissions par rôle"""
    id: Optional[int] = Field(default=None, primary_key=True)
    role: str = Field(index=True)  # Rôle utilisateur
    ressource: TypeRessource = Field(index=True)  # Type de ressource
    niveau_permission: NiveauPermission = Field()  # Niveau de permission
    cree_le: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    modifie_le: Optional[datetime] = None

class PermissionUtilisateur(SQLModel, table=True):
    """Permissions spécifiques à un utilisateur (surcharge des permissions de rôle)"""
    id: Optional[int] = Field(default=None, primary_key=True)
    utilisateur_id: int = Field(foreign_key="user.id", index=True)
    ressource: TypeRessource = Field(index=True)
    niveau_permission: NiveauPermission = Field()
    accordee_par: int = Field(foreign_key="user.id")  # Qui a accordé cette permission
    cree_le: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    expire_le: Optional[datetime] = None  # Permission temporaire

class LogPermission(SQLModel, table=True):
    """Log des modifications de permissions"""
    id: Optional[int] = Field(default=None, primary_key=True)
    utilisateur_id: int = Field(foreign_key="user.id", index=True)
    utilisateur_cible_id: Optional[int] = Field(foreign_key="user.id", default=None)
    action: str = Field()  # ACCORDER, REVOQUER, MODIFIER
    ressource: TypeRessource = Field()
    ancienne_permission: Optional[NiveauPermission] = None
    nouvelle_permission: Optional[NiveauPermission] = None
    raison: Optional[str] = None
    cree_le: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
