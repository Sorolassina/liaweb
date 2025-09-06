"""
Module de sécurité pour l'authentification et les tokens

POUR LES NON-TECHNICIENS :
- C'est le "bureau de sécurité" qui vérifie l'identité des utilisateurs
- Gère la création et validation des cartes d'accès (tokens)
- Protège les routes sensibles de l'application
"""

import datetime as dt
import os
from typing import Optional

from fastapi import HTTPException, status, Depends, Request
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlmodel import Session, select

from ..models.base import User
from ..core.config import settings
from ..core.database import get_session
import logging

# Configuration du logging  
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Schéma OAuth2 pour l'authentification (token via /auth/token)
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/token", auto_error=False)

# Contexte de hachage des mots de passe
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")



# Configuration admin - peut être surchargée par des variables d'environnement
ADMIN_EMAIL = os.getenv("ADMIN_EMAIL", "sorolassina58@gmail.com")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "ChangeMoi#2025")
ADMIN_NAME = os.getenv("ADMIN_NAME", "Soro wangboho lassina")

# Current user
# ----------------------------
async def get_current_user(
    request: Request,
    bearer_token: Optional[str] = Depends(oauth2_scheme),
    session: Session = Depends(get_session),
) -> User:
    """
    Récupère l'utilisateur authentifié à partir du JWT (cookie ou header Bearer).
    - Lève 401 si token invalide/absent
    - Lève 403 si utilisateur inactif
    - Crée automatiquement l'admin s'il n'existe pas
    """
    logger.info("\n=== AUTHENTICATION CHECK ===")
    logger.info("🌐 URL: %s", request.url)
    logger.info("🍪 Cookies disponibles: %s", request.cookies)

    token = _extract_token_from_request(request, bearer_token)
    logger.info("🔑 Token trouvé: %s", (token[:20] + "...") if token else "Aucun")
    if not token:
        raise _credentials_exception("Token manquant")

    payload = verify_token(token)
    logger.info("🔍 Payload: %s", payload)
    if not payload:
        raise _credentials_exception("Token invalide")

    email: Optional[str] = payload.get("sub")
    role_from_token: Optional[str] = payload.get("role")
    logger.info("🔍 Email: %s, Rôle (token): %s", email, role_from_token)

    if not email:
        raise _credentials_exception("Token sans 'sub' (email)")

    # ---- BOOTSTRAP ADMIN ----
    if email == ADMIN_EMAIL:
        admin_user = session.exec(select(User).where(User.email == email)).first()
        if admin_user:
            if not admin_user.actif:
                raise _forbidden_exception("Compte admin inactif")
            return admin_user

        logger.info("🔧 Admin inexistant — création en base")
        try:
            admin_user = User(
                email=email,
                role="administrateur",
                actif=True,
                nom_complet=ADMIN_NAME,
                mot_de_passe_hash=get_password_hash(ADMIN_PASSWORD),
            )
            session.add(admin_user)
            session.commit()
            session.refresh(admin_user)
            logger.info("✅ Admin créé avec ID: %s", admin_user.id)
            return admin_user
        except Exception as e:
            logger.exception("❌ Erreur création admin")
            raise _credentials_exception(f"Erreur création admin: {e}")
    
    # ---- MISE À JOUR ADMIN EXISTANT ----
    # Vérifier si les paramètres admin ont changé et mettre à jour si nécessaire
    if admin_user.nom_complet != ADMIN_NAME or not verify_password(ADMIN_PASSWORD, admin_user.mot_de_passe_hash):
        logger.info("🔧 Paramètres admin modifiés — mise à jour en base")
        try:
            admin_user.nom_complet = ADMIN_NAME
            admin_user.mot_de_passe_hash = get_password_hash(ADMIN_PASSWORD)
            session.add(admin_user)
            session.commit()
            logger.info("✅ Admin mis à jour avec les nouveaux paramètres")
        except Exception as e:
            logger.exception("❌ Erreur mise à jour admin")
            # Ne pas faire échouer la connexion pour une erreur de mise à jour

    # ---- AUTRES UTILISATEURS ----
    user = session.exec(select(User).where(User.email == email)).first()
    logger.info("🔍 User trouvé: %s", user)

    if not user:
        raise _credentials_exception("Utilisateur introuvable")
    if not user.actif:
        raise _forbidden_exception("Utilisateur inactif")

    return user


# ----------------------------
# Password utils
# ----------------------------
def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Vérifie si un mot de passe correspond à son hash."""
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    """Génère un hash sécurisé pour un mot de passe."""
    return pwd_context.hash(password)


# ----------------------------
# JWT utils
# ----------------------------
def create_access_token(data: dict, expires_delta: Optional[dt.timedelta] = None) -> str:
    """
    Crée un token d'accès JWT.
    - data: payload (ex: {"sub": email, "role": "manager_general"})
    """
    to_encode = data.copy()
    expire = dt.datetime.now(dt.timezone.utc) + (
        expires_delta or dt.timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def verify_token(token: str) -> Optional[dict]:
    """Décode/valide un token JWT. Retourne le payload si valide, sinon None."""
    try:
        return jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
    except JWTError:
        return None


# ----------------------------
# Authentication utils
# ----------------------------
def authenticate_user(session: Session, email: str, password: str) -> Optional[User]:
    """
    Authentifie un utilisateur par email/mot de passe.
    Retourne l'utilisateur si ok, sinon None.
    """
    user = session.exec(select(User).where(User.email == email)).first()
    if not user:
        return None
    if not verify_password(password, user.mot_de_passe_hash):
        return None
    if not user.actif:
        return None

    # Met à jour la dernière connexion
    user.derniere_connexion = dt.datetime.now(dt.timezone.utc)
    session.add(user)
    session.commit()
    session.refresh(user)
    return user


# ----------------------------
# Exceptions helpers
# ----------------------------
def _credentials_exception(detail: str = "Identifiants invalides") -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=detail,
        headers={"WWW-Authenticate": "Bearer"},
    )


def _forbidden_exception(detail: str = "Permissions insuffisantes") -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail=detail,
    )


# ----------------------------
# Token extraction
# ----------------------------
def _extract_token_from_request(request: Request, bearer_token: Optional[str]) -> Optional[str]:
    """
    Récupère le token soit depuis le cookie 'access_token',
    soit depuis le header Authorization: Bearer <token>.
    """
    token = request.cookies.get("access_token")
    if token:
        if token.startswith("Bearer "):
            token = token[7:]
        return token

    if bearer_token:
        return bearer_token
    return None


# ----------------------------

# ----------------------------
# Permissions
# ----------------------------
def require_permission(user: User, allowed_roles: list) -> None:
    """
    Vérifie que l'utilisateur a un des rôles autorisés.
    Lève une exception HTTPException si les permissions sont insuffisantes.
    """
    if user.role not in allowed_roles:
        raise _forbidden_exception(f"Permissions insuffisantes. Rôles autorisés: {allowed_roles}")


async def check_admin_permission(
    current_user: User = Depends(get_current_user),
) -> User:
    """Vérifie que l'utilisateur est admin."""
    print(f"✅ Je suis dans check_admin_permission : {current_user}")
    if current_user.role != "administrateur" and current_user.email != ADMIN_EMAIL:
        print(f"❌ Je n'ai pas les permissions dans check_admin_permission : {current_user}")
        raise _forbidden_exception("Pas assez de permissions")
    return current_user


async def check_manager_permission(
    current_user: User = Depends(get_current_user),
) -> User:
    """Vérifie que l'utilisateur est manager ou admin."""
    if current_user.role not in ("general_manager", "manager_contrat"):
        raise _forbidden_exception("Pas assez de permissions")
    return current_user

