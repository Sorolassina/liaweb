"""
Routeur pour la récupération de mot de passe
"""
from fastapi import APIRouter, Depends, HTTPException, status, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlmodel import Session
from typing import Optional
import logging

from app_lia_web.core.database import get_session
from app_lia_web.core.config import settings
from app_lia_web.app.services.password_recovery_service import PasswordRecoveryService
from app_lia_web.app.schemas.password_recovery_schemas import (
    PasswordRecoveryRequest,
    PasswordRecoveryVerify,
    PasswordReset,
    PasswordRecoveryResponse
)

logger = logging.getLogger(__name__)

router = APIRouter()
templates = Jinja2Templates(directory=str(settings.TEMPLATE_DIR))
recovery_service = PasswordRecoveryService()


@router.get("/mot-de-passe-oublie", response_class=HTMLResponse)
async def forgot_password_page(request: Request):
    """Page de demande de récupération de mot de passe"""
    return templates.TemplateResponse(
        "password_recovery/forgot_password.html",
        {
            "request": request,
            "app_name": settings.APP_NAME,
            "version": settings.VERSION,
            "author": settings.AUTHOR,
            "current_year": settings.VERSION.split('.')[0] if '.' in settings.VERSION else "2024"
        }
    )


@router.post("/mot-de-passe-oublie", response_class=HTMLResponse)
async def request_password_recovery(
    request: Request,
    email: str = Form(...),
    session: Session = Depends(get_session)
):
    """Traite la demande de récupération de mot de passe"""
    try:
        # Récupérer l'adresse IP pour la sécurité
        client_ip = request.client.host if request.client else None
        
        # Demander la récupération
        success = recovery_service.request_password_recovery(session, email, client_ip)
        
        if success:
            # Rediriger vers la page de vérification avec un message de succès
            return RedirectResponse(
                url=f"/verification-code?email={email}&success=true",
                status_code=302
            )
        else:
            # Afficher un message d'erreur (sans révéler si l'email existe)
            return templates.TemplateResponse(
                "password_recovery/forgot_password.html",
                {
                    "request": request,
                    "app_name": settings.APP_NAME,
                    "version": settings.VERSION,
                    "author": settings.AUTHOR,
                    "current_year": settings.VERSION.split('.')[0] if '.' in settings.VERSION else "2024",
                    "message": "Si cet email existe dans notre système, vous recevrez un code de récupération.",
                    "message_type": "info"
                }
            )
    
    except Exception as e:
        logger.error(f"Erreur lors de la demande de récupération: {e}")
        return templates.TemplateResponse(
            "password_recovery/forgot_password.html",
            {
                "request": request,
                "app_name": settings.APP_NAME,
                "version": settings.VERSION,
                "author": settings.AUTHOR,
                "current_year": settings.VERSION.split('.')[0] if '.' in settings.VERSION else "2024",
                "error": "Une erreur est survenue. Veuillez réessayer."
            }
        )


@router.get("/verification-code", response_class=HTMLResponse)
async def verify_code_page(request: Request, email: Optional[str] = None, success: Optional[str] = None):
    """Page de vérification du code de récupération"""
    return templates.TemplateResponse(
        "password_recovery/verify_code.html",
        {
            "request": request,
            "email": email,
            "success": success == "true",
            "app_name": settings.APP_NAME,
            "version": settings.VERSION,
            "author": settings.AUTHOR,
            "current_year": settings.VERSION.split('.')[0] if '.' in settings.VERSION else "2024"
        }
    )


@router.post("/verification-code", response_class=HTMLResponse)
async def verify_recovery_code(
    request: Request,
    email: str = Form(...),
    code: str = Form(...),
    session: Session = Depends(get_session)
):
    """Vérifie le code de récupération"""
    try:
        # Vérifier le code
        is_valid = recovery_service.verify_recovery_code(session, email, code)
        
        if is_valid:
            # Rediriger vers la page de réinitialisation
            return RedirectResponse(
                url=f"/reinitialiser-mot-de-passe?email={email}&code={code}",
                status_code=302
            )
        else:
            # Afficher un message d'erreur
            return templates.TemplateResponse(
                "password_recovery/verify_code.html",
                {
                    "request": request,
                    "email": email,
                    "app_name": settings.APP_NAME,
                    "version": settings.VERSION,
                    "author": settings.AUTHOR,
                    "current_year": settings.VERSION.split('.')[0] if '.' in settings.VERSION else "2024",
                    "error": "Code invalide ou expiré. Veuillez vérifier et réessayer."
                }
            )
    
    except Exception as e:
        logger.error(f"Erreur lors de la vérification du code: {e}")
        return templates.TemplateResponse(
            "password_recovery/verify_code.html",
            {
                "request": request,
                "email": email,
                "app_name": settings.APP_NAME,
                "version": settings.VERSION,
                "author": settings.AUTHOR,
                "current_year": settings.VERSION.split('.')[0] if '.' in settings.VERSION else "2024",
                "error": "Une erreur est survenue. Veuillez réessayer."
            }
        )


@router.get("/reinitialiser-mot-de-passe", response_class=HTMLResponse)
async def reset_password_page(request: Request, email: Optional[str] = None, code: Optional[str] = None):
    """Page de réinitialisation du mot de passe"""
    if not email or not code:
        return RedirectResponse(url="/mot-de-passe-oublie", status_code=302)
    
    return templates.TemplateResponse(
        "password_recovery/reset_password.html",
        {
            "request": request,
            "email": email,
            "code": code,
            "app_name": settings.APP_NAME,
            "version": settings.VERSION,
            "author": settings.AUTHOR,
            "current_year": settings.VERSION.split('.')[0] if '.' in settings.VERSION else "2024"
        }
    )


@router.post("/reinitialiser-mot-de-passe", response_class=HTMLResponse)
async def reset_password(
    request: Request,
    email: str = Form(...),
    code: str = Form(...),
    new_password: str = Form(...),
    confirm_password: str = Form(...),
    session: Session = Depends(get_session)
):
    """Réinitialise le mot de passe"""
    try:
        # Vérifier que les mots de passe correspondent
        if new_password != confirm_password:
            return templates.TemplateResponse(
                "password_recovery/reset_password.html",
                {
                    "request": request,
                    "email": email,
                    "code": code,
                    "app_name": settings.APP_NAME,
                    "version": settings.VERSION,
                    "author": settings.AUTHOR,
                    "current_year": settings.VERSION.split('.')[0] if '.' in settings.VERSION else "2024",
                    "error": "Les mots de passe ne correspondent pas."
                }
            )
        
        # Vérifier la force du mot de passe
        if len(new_password) < 8:
            return templates.TemplateResponse(
                "password_recovery/reset_password.html",
                {
                    "request": request,
                    "email": email,
                    "code": code,
                    "app_name": settings.APP_NAME,
                    "version": settings.VERSION,
                    "author": settings.AUTHOR,
                    "current_year": settings.VERSION.split('.')[0] if '.' in settings.VERSION else "2024",
                    "error": "Le mot de passe doit contenir au moins 8 caractères."
                }
            )
        
        # Réinitialiser le mot de passe
        success = recovery_service.reset_password(session, email, code, new_password)
        
        if success:
            # Rediriger vers la page de connexion avec un message de succès
            return RedirectResponse(
                url="/?password_reset=success",
                status_code=302
            )
        else:
            # Afficher un message d'erreur
            return templates.TemplateResponse(
                "password_recovery/reset_password.html",
                {
                    "request": request,
                    "email": email,
                    "code": code,
                    "app_name": settings.APP_NAME,
                    "version": settings.VERSION,
                    "author": settings.AUTHOR,
                    "current_year": settings.VERSION.split('.')[0] if '.' in settings.VERSION else "2024",
                    "error": "Code invalide ou expiré. Veuillez recommencer le processus."
                }
            )
    
    except Exception as e:
        logger.error(f"Erreur lors de la réinitialisation du mot de passe: {e}")
        return templates.TemplateResponse(
            "password_recovery/reset_password.html",
            {
                "request": request,
                "email": email,
                "code": code,
                "app_name": settings.APP_NAME,
                "version": settings.VERSION,
                "author": settings.AUTHOR,
                "current_year": settings.VERSION.split('.')[0] if '.' in settings.VERSION else "2024",
                "error": "Une erreur est survenue. Veuillez réessayer."
            }
        )


# Routes API pour intégration avec d'autres systèmes
@router.post("/api/password-recovery/request", response_model=PasswordRecoveryResponse)
async def api_request_password_recovery(
    request_data: PasswordRecoveryRequest,
    request: Request,
    session: Session = Depends(get_session)
):
    """API pour demander une récupération de mot de passe"""
    try:
        client_ip = request.client.host if request.client else None
        success = recovery_service.request_password_recovery(session, request_data.email, client_ip)
        
        return PasswordRecoveryResponse(
            success=success,
            message="Si cet email existe dans notre système, vous recevrez un code de récupération."
        )
    
    except Exception as e:
        logger.error(f"Erreur API récupération: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erreur interne du serveur"
        )


@router.post("/api/password-recovery/verify", response_model=PasswordRecoveryResponse)
async def api_verify_recovery_code(
    request_data: PasswordRecoveryVerify,
    session: Session = Depends(get_session)
):
    """API pour vérifier un code de récupération"""
    try:
        is_valid = recovery_service.verify_recovery_code(session, request_data.email, request_data.code)
        
        return PasswordRecoveryResponse(
            success=is_valid,
            message="Code valide" if is_valid else "Code invalide ou expiré"
        )
    
    except Exception as e:
        logger.error(f"Erreur API vérification: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erreur interne du serveur"
        )


@router.post("/api/password-recovery/reset", response_model=PasswordRecoveryResponse)
async def api_reset_password(
    request_data: PasswordReset,
    session: Session = Depends(get_session)
):
    """API pour réinitialiser le mot de passe"""
    try:
        success = recovery_service.reset_password(
            session, 
            request_data.email, 
            request_data.code, 
            request_data.new_password
        )
        
        return PasswordRecoveryResponse(
            success=success,
            message="Mot de passe réinitialisé avec succès" if success else "Code invalide ou expiré"
        )
    
    except Exception as e:
        logger.error(f"Erreur API réinitialisation: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erreur interne du serveur"
        )


@router.post("/api/password-recovery/cleanup")
async def cleanup_expired_codes(session: Session = Depends(get_session)):
    """API pour nettoyer les codes expirés (utilisé par un cron job)"""
    try:
        count = recovery_service.cleanup_expired_codes(session)
        return {"success": True, "cleaned_codes": count}
    
    except Exception as e:
        logger.error(f"Erreur nettoyage codes: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erreur interne du serveur"
        )
