"""
Configuration de la base de données PostgreSQL pour Tieka

Ce module configure la connexion à PostgreSQL avec SQLModel et fournit
les sessions de base de données pour l'application.
"""

# app/core/database.py
from typing import Generator
from sqlmodel import SQLModel, Session, create_engine
from sqlalchemy import text
from ..core.config import settings
import logging
from fastapi import Request, Depends
from typing import Optional
#from app.core.security import verify_token, get_password_hash,_extract_token_from_request, _credentials_exception, _forbidden_exception

# Importer tous les modèles pour que SQLModel.metadata.create_all() fonctionne
from ..models.base import (
    User, Programme, Promotion, Candidat, Entreprise,
    Preinscription, Document, Eligibilite, Inscription, Jury,
    MembreJury, DecisionJuryTable, EtapePipeline, AvancementEtape,
    ActionHandicap
)

from sqlmodel import select
from ..core.config import settings
from fastapi.security import OAuth2PasswordBearer


# Configuration du logging  
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Schéma OAuth2 pour l'authentification (token via /auth/token)
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/token", auto_error=False)


# Engine SQLModel
CONNECT_ARGS = {
    "options": "-c client_encoding=UTF8",
    "client_encoding": "utf8"
}
engine = create_engine(
    settings.DATABASE_URL,   # ex: "postgresql://user:pass@localhost:5432/db"
    pool_pre_ping=True,
    echo=settings.DEBUG,
    connect_args=CONNECT_ARGS
)
print("✅",settings.DATABASE_URL)

def create_db_and_tables() -> None:
    """Crée les tables de la base de données avec gestion d'erreur."""
    try:
        # Essayer de créer les tables
        SQLModel.metadata.create_all(engine)
        logger.info(f"✅ Tables créées avec succès")
    except Exception as e:
        logger.error(f"❌ Erreur lors de la création des tables: {e}")
        logger.info("💡 Merci de que votre base de données soit configurée correctement...")
        
        

# Dépendance FastAPI : ouvre/ferme une session par requête
def get_session() -> Generator[Session, None, None]:
    with Session(engine) as session:
        yield session

# (facultatif) Test de connexion
def test_db_connection() -> bool:
    with engine.connect() as conn:
        conn.execute(text("SELECT 1"))
    return True


