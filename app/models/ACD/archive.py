# app/models/ACD/archive.py
from __future__ import annotations
from typing import Optional, Dict, Any
from datetime import datetime, timezone
from sqlmodel import SQLModel, Field
from sqlalchemy import Column, JSON
from enum import Enum

class TypeArchive(str, Enum):
    """Types d'archivage"""
    SAUVEGARDE_COMPLETE = "sauvegarde_complete"      # Sauvegarde complète
    DONNEES_UNIQUEMENT = "donnees_uniquement"          # Données uniquement
    FICHIERS_UNIQUEMENT = "fichiers_uniquement"        # Fichiers uniquement
    SELECTIF = "selectif"                            # Archivage sélectif

class StatutArchive(str, Enum):
    """Statuts d'archivage"""
    EN_ATTENTE = "en_attente"              # En attente
    EN_COURS = "en_cours"                  # En cours
    TERMINE = "termine"                    # Terminé
    ECHEC = "echec"                       # Échec
    EXPIRE = "expire"                     # Expiré

class Archive(SQLModel, table=True):
    """Enregistrement des archives créées"""
    id: Optional[int] = Field(default=None, primary_key=True)
    nom: str = Field()  # Nom de l'archive
    type_archive: TypeArchive = Field()
    statut: StatutArchive = Field(default=StatutArchive.EN_ATTENTE)
    chemin_fichier: Optional[str] = None  # Chemin vers le fichier d'archive
    taille_fichier: Optional[int] = None  # Taille en bytes
    description: Optional[str] = None
    cree_par: int = Field(foreign_key="user.id")
    cree_le: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    termine_le: Optional[datetime] = None
    expire_le: Optional[datetime] = None  # Date d'expiration de l'archive
    metadonnees: Optional[Dict[str, Any]] = Field(default=None, sa_column=Column(JSON, nullable=True))
    message_erreur: Optional[str] = None

class RegleNettoyage(SQLModel, table=True):
    """Règles de nettoyage automatique"""
    id: Optional[int] = Field(default=None, primary_key=True)
    nom: str = Field()
    nom_table: str = Field()  # Table à nettoyer
    condition: str = Field()  # Condition SQL pour identifier les données à supprimer
    jours_retention: int = Field()  # Nombre de jours de rétention
    active: bool = Field(default=True)
    derniere_execution: Optional[datetime] = None
    cree_par: int = Field(foreign_key="user.id")
    cree_le: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class LogNettoyage(SQLModel, table=True):
    """Log des opérations de nettoyage"""
    id: Optional[int] = Field(default=None, primary_key=True)
    regle_id: int = Field(foreign_key="reglenettoyage.id")
    enregistrements_supprimes: int = Field(default=0)
    temps_execution: float = Field()  # Temps d'exécution en secondes
    statut: str = Field()  # SUCCES, ECHEC, PARTIEL
    message_erreur: Optional[str] = None
    execute_par: int = Field(foreign_key="user.id")
    execute_le: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
