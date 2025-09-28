"""
Configuration de la base de données PostgreSQL pour Tieka

Ce module configure la connexion à PostgreSQL avec SQLModel et fournit
les sessions de base de données pour l'application.
"""

# app/core/database.py
from typing import Generator
from sqlmodel import SQLModel, Session, create_engine
from sqlalchemy import text
from app_lia_web.core.config import settings
import logging
from fastapi import Request, Depends
from typing import Optional
#from app.core.security import verify_token, get_password_hash,_extract_token_from_request, _credentials_exception, _forbidden_exception

# Importer SEULEMENT les modèles qui doivent rester dans le schéma public
from app_lia_web.app.models.base import (
    User, Programme, Partenaire, Groupe, PasswordRecoveryCode, ProgrammeUtilisateur, Promotion
)
from app_lia_web.app.models.activity import ActivityLog
# Les autres modèles seront créés dans les schémas par programme
# from app_lia_web.app.models.preinscription import Preinscription, Eligibilite
# from app_lia_web.app.models.inscription import Inscription
# from app_lia_web.app.models.jury import Jury, MembreJury, DecisionJuryTable
# from app_lia_web.app.models.rendez_vous import RendezVous, EmargementRDV

from sqlmodel import select
from app_lia_web.core.config import settings
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
    """Crée SEULEMENT les tables du schéma public (système)."""
    try:
        # Créer seulement les tables qui doivent rester dans le schéma public
        public_models = [
            User, Programme, Partenaire, Groupe, PasswordRecoveryCode,
            ProgrammeUtilisateur, Promotion, ActivityLog
        ]
        
        # Créer les métadonnées pour les tables publiques seulement
        from sqlmodel import MetaData
        public_metadata = MetaData()
        
        # Ajouter les tables publiques aux métadonnées
        for model in public_models:
            if hasattr(model, '__table__'):
                public_metadata.create_all(bind=engine, tables=[model.__table__])
        
        logger.info(f"✅ Tables publiques (système) créées avec succès")
    except Exception as e:
        logger.error(f"❌ Erreur lors de la création des tables publiques: {e}")
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


