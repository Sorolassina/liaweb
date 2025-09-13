# app/scripts/test_permissions.py
"""
Script pour tester le système de permissions
"""
import sys
from pathlib import Path

# Ajouter le répertoire parent au path pour les imports
sys.path.append(str(Path(__file__).parent.parent))

from sqlmodel import Session, select
from app_lia_web.core.database import engine
from app_lia_web.app.models.base import User
from app_lia_web.app.models.ACD.permissions import TypeRessource, NiveauPermission
from app_lia_web.app.services.ACD.permissions import PermissionService
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_permissions():
    """Teste le système de permissions"""
    
    with Session(engine) as session:
        permission_service = PermissionService(session)
        
        # Initialiser les permissions par défaut
        logger.info("🔧 Initialisation des permissions par défaut...")
        permission_service.initialize_default_permissions()
        
        # Récupérer les utilisateurs
        users = session.exec(select(User)).all()
        logger.info(f"👥 {len(users)} utilisateurs trouvés")
        
        # Tester les permissions pour chaque utilisateur
        for user in users:
            logger.info(f"\n👤 Test des permissions pour: {user.nom_complet} ({user.role})")
            
            permissions = permission_service.get_user_permissions(user)
            
            for resource in TypeRessource:
                permission = permissions.get(resource)
                if permission:
                    logger.info(f"  ✅ {resource.value}: {permission.value}")
                else:
                    logger.info(f"  ❌ {resource.value}: Aucune permission")
            
            # Test spécifique pour les utilisateurs
            can_read_users = permission_service.has_permission(user, TypeRessource.UTILISATEURS, NiveauPermission.LECTURE)
            can_write_users = permission_service.has_permission(user, TypeRessource.UTILISATEURS, NiveauPermission.ECRITURE)
            can_admin_users = permission_service.has_permission(user, TypeRessource.UTILISATEURS, NiveauPermission.ADMIN)
            
            logger.info(f"  📊 Résumé utilisateurs:")
            logger.info(f"    - Lecture: {'✅' if can_read_users else '❌'}")
            logger.info(f"    - Écriture: {'✅' if can_write_users else '❌'}")
            logger.info(f"    - Admin: {'✅' if can_admin_users else '❌'}")
        
        # Afficher la matrice complète
        logger.info("\n📋 Matrice complète des permissions:")
        matrix = permission_service.get_permission_matrix()
        
        for role, permissions in matrix.items():
            logger.info(f"\n🎭 Rôle: {role}")
            for resource, level in permissions.items():
                logger.info(f"  - {resource.value}: {level.value}")

if __name__ == "__main__":
    logger.info("🚀 Test du système de permissions...")
    test_permissions()
    logger.info("✅ Test terminé")
