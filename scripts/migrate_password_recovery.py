"""
Script de migration pour ajouter la table de récupération de mot de passe
"""
import os
import sys
import logging
from sqlmodel import Session, text
from app_lia_web.core.database import get_session

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def create_password_recovery_table():
    """Crée la table passwordrecoverycode si elle n'existe pas"""
    
    session = next(get_session())
    
    try:
        # Vérifier si la table existe déjà
        result = session.exec(text("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables 
                WHERE table_schema = 'public' 
                AND table_name = 'passwordrecoverycode'
            );
        """)).first()
        
        if result:
            logger.info("✅ La table passwordrecoverycode existe déjà")
            return True
        
        # Créer la table
        session.exec(text("""
            CREATE TABLE passwordrecoverycode (
                id SERIAL PRIMARY KEY,
                email VARCHAR(255) NOT NULL,
                code VARCHAR(6) NOT NULL,
                expires_at TIMESTAMP WITH TIME ZONE NOT NULL,
                used BOOLEAN DEFAULT FALSE,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                used_at TIMESTAMP WITH TIME ZONE,
                ip_address VARCHAR(45)
            );
        """))
        
        # Créer les index
        session.exec(text("CREATE INDEX ix_passwordrecoverycode_email ON passwordrecoverycode (email);"))
        session.exec(text("CREATE INDEX ix_passwordrecoverycode_expires_at ON passwordrecoverycode (expires_at);"))
        session.exec(text("CREATE INDEX ix_passwordrecoverycode_used ON passwordrecoverycode (used);"))
        
        session.commit()
        logger.info("✅ Table passwordrecoverycode créée avec succès")
        return True
        
    except Exception as e:
        logger.error(f"❌ Erreur lors de la création de la table : {e}")
        session.rollback()
        return False
    
    finally:
        session.close()


def cleanup_old_codes():
    """Nettoie les codes expirés existants"""
    
    session = next(get_session())
    
    try:
        result = session.exec(text("""
            DELETE FROM passwordrecoverycode 
            WHERE expires_at < NOW() OR used = TRUE;
        """))
        
        session.commit()
        logger.info(f"🧹 Nettoyage terminé : {result.rowcount} codes supprimés")
        return result.rowcount
        
    except Exception as e:
        logger.error(f"❌ Erreur lors du nettoyage : {e}")
        session.rollback()
        return 0
    
    finally:
        session.close()


if __name__ == "__main__":
    print("🚀 Migration de la table de récupération de mot de passe")
    print("=" * 55)
    
    # Créer la table
    if create_password_recovery_table():
        print("✅ Migration réussie")
        
        # Nettoyer les codes expirés
        count = cleanup_old_codes()
        print(f"🧹 {count} codes expirés nettoyés")
        
        print("\n🎉 Migration terminée avec succès !")
    else:
        print("❌ Échec de la migration")
        exit(1)
