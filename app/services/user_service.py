"""
Service de gestion des utilisateurs
"""
from typing import List, Optional
from sqlmodel import Session, select
import logging
from ..models.base import User
from ..models.enums import UserRole, TypeUtilisateur
from ..schemas.user_schemas import UserCreate, UserUpdate
from ..core.security import get_password_hash, verify_password
from ..core.config import settings

logger = logging.getLogger(__name__)


class UserService:
    """Service de gestion des utilisateurs"""
    
    @staticmethod
    def create_user(session: Session, user_data: UserCreate) -> User:
        """Crée un nouvel utilisateur"""
        user = User(
            email=user_data.email,
            nom_complet=user_data.nom_complet,
            telephone=user_data.telephone,
            role=user_data.role,
            type_utilisateur=user_data.type_utilisateur,
            mot_de_passe_hash=get_password_hash(user_data.mot_de_passe)
        )
        session.add(user)
        session.commit()
        session.refresh(user)
        return user
    
    @staticmethod
    def get_user_by_email(session: Session, email: str) -> Optional[User]:
        """Récupère un utilisateur par email"""
        return session.exec(select(User).where(User.email == email)).first()
    
    @staticmethod
    def get_users_by_role(session: Session, role: str) -> List[User]:
        """Récupère les utilisateurs par rôle"""
        return session.exec(select(User).where(User.role == role)).all()
    
    @staticmethod
    def update_user(session: Session, user_id: int, user_data: UserUpdate) -> Optional[User]:
        """Met à jour un utilisateur"""
        user = session.get(User, user_id)
        if not user:
            return None
        
        update_data = user_data.dict(exclude_unset=True)
        for field, value in update_data.items():
            setattr(user, field, value)
        
        session.add(user)
        session.commit()
        session.refresh(user)
        return user
    
    @staticmethod
    def create_admin_user(session: Session, email: str, password: str, nom_complet: str = "Administrateur") -> User:
        """Crée un utilisateur administrateur"""
        hashed_password = get_password_hash(password)
        
        admin_user = User(
            email=email,
            nom_complet=nom_complet,
            mot_de_passe_hash=hashed_password,
            role="administrateur",
            type_utilisateur=TypeUtilisateur.INTERNE,
            actif=True
        )
        
        session.add(admin_user)
        session.commit()
        session.refresh(admin_user)
        
        logger.info(f"✅ Utilisateur administrateur créé: {email}")
        return admin_user
    
    @staticmethod
    def verify_admin_credentials(session: Session, email: str, password: str) -> bool:
        """Vérifie les identifiants de l'administrateur"""
        user = UserService.get_user_by_email(session, email)
        if not user:
            return False
        
        if user.role != "administrateur":
            return False
        
        return verify_password(password, user.mot_de_passe_hash)
    
    @staticmethod
    def ensure_admin_exists(session: Session) -> bool:
        """Vérifie et crée l'administrateur si nécessaire"""
        admin_email = settings.MAIL_ADMIN
        admin_password = settings.PASSWORD_ADMIN
        
        if not admin_email or not admin_password:
            logger.error("❌ Email admin ou mot de passe admin non configuré")
            return False
        
        # Vérifier si l'admin existe déjà
        existing_admin = UserService.get_user_by_email(session, admin_email)
        
        if existing_admin:
            # L'admin existe, vérifier le mot de passe
            if UserService.verify_admin_credentials(session, admin_email, admin_password):
                logger.info(f"✅ Administrateur existant vérifié: {admin_email}")
                return True
            else:
                logger.warning(f"⚠️ Administrateur existe mais mot de passe incorrect: {admin_email}")
                logger.info("💡 L'administrateur devra réinitialiser son mot de passe")
                return False
        else:
            # L'admin n'existe pas, le créer
            try:
                UserService.create_admin_user(session, admin_email, admin_password)
                logger.info(f"🎉 Nouvel administrateur créé avec succès: {admin_email}")
                logger.info(f"🔑 Mot de passe par défaut: {admin_password}")
                return True
            except Exception as e:
                logger.error(f"❌ Erreur lors de la création de l'administrateur: {e}")
                return False
