"""
Router pour la gestion du Codéveloppement
"""
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlmodel import Session, select, and_, or_, func, text
from datetime import datetime, timezone, date, timedelta

from ..core.database import get_session
from ..core.middleware import get_shared_session
from ..core.security import get_current_user
from ..core.program_schema_integration import safe_count_query, table_exists_anywhere, get_schema_from_request, get_schema_routing_service, SchemaRoutingService
import logging
from ..models.base import User, Programme, Promotion, Groupe
from ..models.codev import (
    CycleCodev, GroupeCodev, SeanceCodev, PresentationCodev, 
    ContributionCodev, MembreGroupeCodev, ParticipationSeance
)
from ..models.enums import UserRole, StatutCycleCodev, StatutGroupeCodev
from ..services.codev_service import CodevService
from ..schemas.codev import (
    CycleCodevCreate, CycleCodevUpdate, GroupeCodevCreate, SeanceCodevCreate,
    PresentationCodevCreate, ContributionCodevCreate, MembreGroupeCodevCreate,
    CycleCodevResponse, GroupeCodevResponse, SeanceCodevResponse,
    StatistiquesCycleCodev, PlanificationSeance, EngagementCandidat, RetourExperience
)
from ..templates import templates
from ..core.config import settings

router = APIRouter()

def extract_count_value(result):
    """Extrait la valeur d'un résultat COUNT(*) qui peut être un tuple ou une valeur simple"""
    if result is None:
        return 0
    if isinstance(result, tuple):
        return result[0] if result else 0
    if hasattr(result, '__iter__') and not isinstance(result, str):
        try:
            return next(iter(result)) if result else 0
        except:
            return int(result) if result else 0
    return int(result) if result else 0

def codev_access_required(current_user: User):
    """Vérifie que l'utilisateur a accès au module Codev"""
    allowed_roles = [
        UserRole.ADMINISTRATEUR.value,
        UserRole.DIRECTEUR_TECHNIQUE.value,
        UserRole.RESPONSABLE_PROGRAMME.value,
        UserRole.COORDINATEUR.value,
        UserRole.CONSEILLER.value,
        UserRole.FORMATEUR.value
    ]
    if current_user.role not in allowed_roles:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Accès non autorisé au module Codéveloppement"
        )

# ===== ROUTES WEB =====

@router.get("/", name="codev_dashboard", response_class=HTMLResponse)
async def codev_dashboard(
    request: Request,
    session: Session = Depends(get_shared_session),
    current_user: User = Depends(get_current_user),
    programme_id: Optional[int] = None,
    schema_routing_service: SchemaRoutingService = Depends(get_schema_routing_service)
):
    """Tableau de bord du codéveloppement"""
    codev_access_required(current_user)
    
    # Initialiser stats avec des valeurs par défaut dès le début
    stats = {
        'total_cycles': 0,
        'cycles_planifies': 0,
        'cycles_en_cours': 0,
        'total_groupes': 0,
        'total_seances': 0
    }
    
    # Récupérer et configurer le schéma
    schema_name = get_schema_from_request(request) or 'acd'
    schema_routing_service.set_schema(schema_name)
    
    # Configurer explicitement le search_path
    session.exec(text(f"SET search_path TO {schema_name}, public"))
    session.commit()
    
    # Forcer l'expiration de tous les objets de la session pour éviter le cache
    session.expire_all()
    
    # Récupérer le programme_id depuis le code du programme si nécessaire
    programme_param = request.query_params.get('programme', '').upper()
    if programme_param and not programme_id:
        try:
            programme_query = text("SELECT id FROM public.programme WHERE code = :code AND actif = true")
            programme_result = session.exec(programme_query.bindparams(code=programme_param)).first()
            if programme_result:
                # Extraire l'ID du résultat (peut être un Row, tuple ou objet)
                if hasattr(programme_result, '_mapping'):
                    programme_id = list(programme_result._mapping.values())[0]
                elif isinstance(programme_result, tuple):
                    programme_id = programme_result[0]
                elif hasattr(programme_result, 'id'):
                    programme_id = programme_result.id
                else:
                    programme_id = programme_result
        except Exception as e:
            print(f"⚠️ [WARNING] Erreur lors de la récupération du programme_id: {e}")
            programme_id = None
    
    # Récupérer les cycles actifs (filtrés par programme si spécifié) - SQL direct
    try:
        cycles_query = text(f"""
            SELECT * FROM {schema_name}.cycle_codev
            WHERE statut IN (:statut1, :statut2)
            {"AND programme_id = :programme_id" if programme_id else ""}
            ORDER BY date_debut DESC
        """)
        params = {
            'statut1': StatutCycleCodev.PLANIFIE.value,
            'statut2': StatutCycleCodev.EN_COURS.value
        }
        if programme_id:
            params['programme_id'] = programme_id
        
        cycles_results = session.exec(cycles_query.bindparams(**params)).all()
        cycles_actifs = [type('CycleCodev', (), dict(row._mapping))() for row in cycles_results]
    except Exception as e:
        print(f"⚠️ [WARNING] Erreur lors de la récupération des cycles CoDev: {e}")
        cycles_actifs = []
    
    # Récupérer les prochaines séances (filtrées par programme si spécifié)
    try:
        prochaines_seances = CodevService.get_prochaines_seances(session, limit=5, programme_id=programme_id, schema_name=schema_name)
    except Exception as e:
        print(f"⚠️ [WARNING] Erreur lors de la récupération des prochaines séances CoDev: {e}")
        prochaines_seances = []
    
    # Récupérer les engagements en cours (filtrés par programme si spécifié)
    try:
        engagements_en_cours = CodevService.get_engagements_en_cours(session, programme_id=programme_id, schema_name=schema_name)
    except Exception as e:
        print(f"⚠️ [WARNING] Erreur lors de la récupération des engagements CoDev: {e}")
        engagements_en_cours = []
    
    # Calculer les KPIs - SQL direct
    try:
        # Total cycles
        total_cycles_query = text(f"SELECT COUNT(*) FROM {schema_name}.cycle_codev")
        if programme_id:
            total_cycles_query = text(f"SELECT COUNT(*) FROM {schema_name}.cycle_codev WHERE programme_id = :programme_id")
        result = session.exec(total_cycles_query.bindparams(**({'programme_id': programme_id} if programme_id else {}))).one()
        stats['total_cycles'] = extract_count_value(result)
        
        # Cycles planifiés
        cycles_planifies_query = text(f"SELECT COUNT(*) FROM {schema_name}.cycle_codev WHERE statut = :statut")
        if programme_id:
            cycles_planifies_query = text(f"SELECT COUNT(*) FROM {schema_name}.cycle_codev WHERE statut = :statut AND programme_id = :programme_id")
        params_planifies = {'statut': StatutCycleCodev.PLANIFIE.value}
        if programme_id:
            params_planifies['programme_id'] = programme_id
        result = session.exec(cycles_planifies_query.bindparams(**params_planifies)).one()
        stats['cycles_planifies'] = extract_count_value(result)
        
        # Cycles en cours
        cycles_en_cours_query = text(f"SELECT COUNT(*) FROM {schema_name}.cycle_codev WHERE statut = :statut")
        if programme_id:
            cycles_en_cours_query = text(f"SELECT COUNT(*) FROM {schema_name}.cycle_codev WHERE statut = :statut AND programme_id = :programme_id")
        params_en_cours = {'statut': StatutCycleCodev.EN_COURS.value}
        if programme_id:
            params_en_cours['programme_id'] = programme_id
        result = session.exec(cycles_en_cours_query.bindparams(**params_en_cours)).one()
        stats['cycles_en_cours'] = extract_count_value(result)
        
        # Total groupes
        if programme_id:
            total_groupes_query = text(f"""
                SELECT COUNT(*) FROM {schema_name}.groupe_codev gc
                INNER JOIN {schema_name}.cycle_codev cc ON gc.cycle_id = cc.id
                WHERE cc.programme_id = :programme_id
            """)
            result = session.exec(total_groupes_query.bindparams(programme_id=programme_id)).one()
            stats['total_groupes'] = extract_count_value(result)
        else:
            total_groupes_query = text(f"SELECT COUNT(*) FROM {schema_name}.groupe_codev")
            result = session.exec(total_groupes_query).one()
            stats['total_groupes'] = extract_count_value(result)
        
        # Total séances
        if programme_id:
            total_seances_query = text(f"""
                SELECT COUNT(*) FROM {schema_name}.seance_codev s
                INNER JOIN {schema_name}.groupe_codev gc ON s.groupe_id = gc.groupe_id
                INNER JOIN {schema_name}.cycle_codev cc ON gc.cycle_id = cc.id
                WHERE cc.programme_id = :programme_id
            """)
            result = session.exec(total_seances_query.bindparams(programme_id=programme_id)).one()
            stats['total_seances'] = extract_count_value(result)
        else:
            total_seances_query = text(f"SELECT COUNT(*) FROM {schema_name}.seance_codev")
            result = session.exec(total_seances_query).one()
            stats['total_seances'] = extract_count_value(result)
        
    except Exception as e:
        print(f"⚠️ [WARNING] Erreur lors du calcul des KPIs CoDev: {e}")
        stats = {
            'total_cycles': 0,
            'cycles_planifies': 0,
            'cycles_en_cours': 0,
            'total_groupes': 0,
            'total_seances': 0
        }
    
    programme_param = request.query_params.get('programme', '').upper()
    
    return templates.TemplateResponse(
        "pages/codev/dashboard.html",
        {
            "request": request,
            "utilisateur": current_user,
            "cycles_actifs": cycles_actifs,
            "prochaines_seances": prochaines_seances,
            "engagements_en_cours": engagements_en_cours,
            "settings": settings,
            "programme_param": programme_param,
            "schema_name": schema_name,
            "stats": stats
        }
    )

@router.get("/cycles", response_class=HTMLResponse, name="codev_cycles")
async def codev_cycles(
    request: Request,
    session: Session = Depends(get_shared_session),
    current_user: User = Depends(get_current_user),
    q: Optional[str] = Query(None),
    schema_routing_service: SchemaRoutingService = Depends(get_schema_routing_service)
):
    """Liste des cycles de codéveloppement"""
    codev_access_required(current_user)
    
    # Initialiser stats avec des valeurs par défaut dès le début
    stats = {
        'total_cycles': 0,
        'cycles_planifies': 0,
        'cycles_en_cours': 0,
        'cycles_termines': 0
    }
    
    # Récupérer et configurer le schéma
    schema_name = get_schema_from_request(request) or 'acd'
    schema_routing_service.set_schema(schema_name)
    
    # Configurer explicitement le search_path
    session.exec(text(f"SET search_path TO {schema_name}, public"))
    session.commit()
    
    # Récupérer les cycles - SQL direct avec JOIN programme
    try:
        cycles_query = text(f"""
            SELECT c.*, p.nom as programme_nom, p.code as programme_code
            FROM {schema_name}.cycle_codev c
            LEFT JOIN public.programme p ON c.programme_id = p.id
            {"WHERE c.nom ILIKE :q OR c.description ILIKE :q" if q else ""}
            ORDER BY c.date_debut DESC
        """)
        params = {}
        if q:
            params['q'] = f"%{q}%"
        
        cycles_results = session.exec(cycles_query.bindparams(**params) if params else cycles_query).all()
        cycles = [type('CycleCodev', (), dict(row._mapping))() for row in cycles_results]
    except Exception as e:
        print(f"⚠️ [WARNING] Erreur lors de la récupération des cycles: {e}")
        cycles = []
    
    # Calculer les KPIs
    try:
        stats['total_cycles'] = len(cycles)
        for cycle in cycles:
            statut = cycle.statut if hasattr(cycle, 'statut') and cycle.statut else 'planifie'
            if statut == 'planifie':
                stats['cycles_planifies'] += 1
            elif statut == 'en_cours':
                stats['cycles_en_cours'] += 1
            elif statut == 'termine':
                stats['cycles_termines'] += 1
    except Exception as e:
        print(f"⚠️ [WARNING] Erreur lors du calcul des KPIs: {e}")
        # En cas d'erreur, stats garde ses valeurs par défaut
    
    programme_param = request.query_params.get('programme', '').upper()
    
    return templates.TemplateResponse(
        "pages/codev/cycles.html",
        {
            "request": request,
            "utilisateur": current_user,
            "cycles": cycles,
            "q": q or "",
            "settings": settings,
            "programme_param": programme_param,
            "schema_name": schema_name,
            "stats": stats
        }
    )

@router.get("/cycles/creer", response_class=HTMLResponse, name="codev_cycles_create_form")
async def codev_cycles_creer(
    request: Request,
    session: Session = Depends(get_shared_session),
    current_user: User = Depends(get_current_user),
    cycle_id: Optional[int] = Query(None),
    schema_routing_service: SchemaRoutingService = Depends(get_schema_routing_service)
):
    """Formulaire de création ou modification d'un cycle"""
    codev_access_required(current_user)
    
    # Récupérer et configurer le schéma
    schema_name = get_schema_from_request(request) or 'acd'
    schema_routing_service.set_schema(schema_name)
    
    # Configurer explicitement le search_path
    session.exec(text(f"SET search_path TO {schema_name}, public"))
    session.commit()
    
    # Mode édition : récupérer le cycle existant
    cycle = None
    is_edit_mode = False
    if cycle_id:
        try:
            cycle_query = text(f"SELECT * FROM {schema_name}.cycle_codev WHERE id = :cycle_id")
            cycle_result = session.exec(cycle_query.bindparams(cycle_id=cycle_id)).first()
            if cycle_result:
                cycle = type('CycleCodev', (), dict(cycle_result._mapping))()
                is_edit_mode = True
        except Exception as e:
            logger.warning(f"⚠️ Erreur lors de la récupération du cycle {cycle_id}: {e}")
    
    # Récupérer les programmes (dans le schéma public)
    programmes_query = text("SELECT * FROM public.programme WHERE actif = true")
    programmes_results = session.exec(programmes_query).all()
    programmes = [type('Programme', (), {
        'id': p.id,
        'code': p.code,
        'nom': p.nom
    })() for p in programmes_results]
    
    # Récupérer les promotions du schéma du programme (pas public)
    promotions_query = text(f"SELECT id, libelle, programme_id, capacite, date_debut, date_fin, actif FROM {schema_name}.promotion WHERE actif = true")
    try:
        promotions_results = session.exec(promotions_query).all()
        promotions = [type('Promotion', (), {
            'id': p.id,
            'libelle': p.libelle,
            'nom': p.libelle  # Alias pour compatibilité avec les templates
        })() for p in promotions_results]
    except Exception as e:
        logger.warning(f"⚠️ Erreur lors de la récupération des promotions du schéma {schema_name}: {e}")
        promotions = []  # Liste vide si la table n'existe pas encore
    
    # Récupérer les animateurs potentiels (dans le schéma public)
    animateurs_query = text("SELECT * FROM public.\"user\" WHERE role IN (:r1, :r2, :r3, :r4)")
    animateurs_results = session.exec(animateurs_query.bindparams(
        r1=UserRole.CONSEILLER.value,
        r2=UserRole.FORMATEUR.value,
        r3=UserRole.COORDINATEUR.value,
        r4=UserRole.RESPONSABLE_PROGRAMME.value
    )).all()
    animateurs = [type('User', (), {
        'id': u.id,
        'nom_complet': u.nom_complet,
        'email': u.email,
        'role': u.role
    })() for u in animateurs_results]
    
    programme_param = request.query_params.get('programme', '').upper()
    
    # Récupérer le programme sélectionné automatiquement
    # D'abord essayer avec programme_param, sinon utiliser schema_name, sinon utiliser le cycle
    selected_programme = None
    programme_code_to_search = programme_param if programme_param else schema_name.upper() if schema_name and schema_name != 'public' else None
    
    if programme_code_to_search:
        programme_query = text("SELECT * FROM public.programme WHERE code = :code AND actif = true")
        programme_result = session.exec(programme_query.bindparams(code=programme_code_to_search)).first()
        if programme_result:
            selected_programme = type('Programme', (), {
                'id': programme_result.id,
                'code': programme_result.code,
                'nom': programme_result.nom
            })()
    elif cycle and hasattr(cycle, 'programme_id'):
        # Si on est en mode édition, utiliser le programme du cycle
        programme_query = text("SELECT * FROM public.programme WHERE id = :programme_id AND actif = true")
        programme_result = session.exec(programme_query.bindparams(programme_id=cycle.programme_id)).first()
        if programme_result:
            selected_programme = type('Programme', (), {
                'id': programme_result.id,
                'code': programme_result.code,
                'nom': programme_result.nom
            })()
    
    return templates.TemplateResponse(
        "pages/codev/cycle_form.html",
        {
            "request": request,
            "utilisateur": current_user,
            "programmes": programmes,
            "promotions": promotions,
            "animateurs": animateurs,
            "cycle": cycle,
            "is_edit_mode": is_edit_mode,
            "settings": settings,
            "programme_param": programme_param,
            "selected_programme": selected_programme,
            "schema_name": schema_name
        }
    )

@router.post("/cycles/creer", name="codev_cycles_create")
async def codev_cycles_creer_post(
    request: Request,
    nom: str = Form(...),
    description: Optional[str] = Form(None),
    programme_id: int = Form(...),
    promotion_id: Optional[int] = Form(None),
    date_debut: date = Form(...),
    date_fin: date = Form(...),
    nombre_seances_prevues: int = Form(6),
    duree_seance_minutes: int = Form(180),
    animateur_principal_id: Optional[int] = Form(None),
    objectifs_cycle: Optional[str] = Form(None),
    cycle_id: Optional[int] = Form(None),
    session: Session = Depends(get_shared_session),
    current_user: User = Depends(get_current_user),
    schema_routing_service: SchemaRoutingService = Depends(get_schema_routing_service)
):
    """Création ou modification d'un cycle de codéveloppement"""
    is_edit_mode = cycle_id is not None
    logger.info(f"🚀 [DEBUG] Route POST /cycles/creer appelée (mode: {'édition' if is_edit_mode else 'création'})")
    logger.info(f"🔍 [DEBUG] Données reçues:")
    logger.info(f"  - nom: {nom}")
    logger.info(f"  - description: {description}")
    logger.info(f"  - programme_id: {programme_id}")
    logger.info(f"  - promotion_id: {promotion_id}")
    logger.info(f"  - date_debut: {date_debut}")
    logger.info(f"  - date_fin: {date_fin}")
    logger.info(f"  - nombre_seances_prevues: {nombre_seances_prevues}")
    logger.info(f"  - duree_seance_minutes: {duree_seance_minutes}")
    logger.info(f"  - animateur_principal_id: {animateur_principal_id}")
    logger.info(f"  - objectifs_cycle: {objectifs_cycle}")
    
    codev_access_required(current_user)
    
    # Récupérer et configurer le schéma
    schema_name = get_schema_from_request(request) or 'acd'
    logger.info(f"🔍 [DEBUG] Schema name: {schema_name}")
    schema_routing_service.set_schema(schema_name)
    
    # Configurer explicitement le search_path
    session.exec(text(f"SET search_path TO {schema_name}, public"))
    session.commit()
    logger.info(f"✅ [DEBUG] Search_path configuré: {schema_name}, public")
    
    # Vérifier que la table existe
    if not table_exists_anywhere("cycle_codev", session, schema_name):
        logger.error(f"❌ [DEBUG] Table cycle_codev introuvable dans le schéma {schema_name}")
        raise HTTPException(status_code=404, detail="Table cycle_codev introuvable dans ce programme")
    
    logger.info(f"✅ [DEBUG] Table cycle_codev trouvée, {'modification' if is_edit_mode else 'création'} du cycle...")
    try:
        if is_edit_mode:
            # Mode édition : mise à jour du cycle existant
            update_query = text(f"""
                UPDATE {schema_name}.cycle_codev 
                SET nom = :nom,
                    description = :description,
                    programme_id = :programme_id,
                    promotion_id = :promotion_id,
                    date_debut = :date_debut,
                    date_fin = :date_fin,
                    nombre_seances_prevues = :nombre_seances_prevues,
                    duree_seance_minutes = :duree_seance_minutes,
                    animateur_principal_id = :animateur_principal_id,
                    objectifs_cycle = :objectifs_cycle
                WHERE id = :cycle_id
            """)
            session.exec(update_query.bindparams(
                nom=nom,
                description=description,
                programme_id=programme_id,
                promotion_id=promotion_id,
                date_debut=date_debut,
                date_fin=date_fin,
                nombre_seances_prevues=nombre_seances_prevues,
                duree_seance_minutes=duree_seance_minutes,
                animateur_principal_id=animateur_principal_id,
                objectifs_cycle=objectifs_cycle,
                cycle_id=cycle_id
            ))
            session.commit()
            logger.info(f"✅ [DEBUG] Cycle modifié avec succès, ID: {cycle_id}")
            action = "update"
        else:
            # Mode création : création d'un nouveau cycle
            cycle = CodevService.create_cycle_codev(
                session=session,
                nom=nom,
                programme_id=programme_id,
                promotion_id=promotion_id,
                date_debut=date_debut,
                date_fin=date_fin,
                nombre_seances=nombre_seances_prevues,
                animateur_principal_id=animateur_principal_id,
                schema_name=schema_name
            )
            cycle_id = cycle.get('id') if isinstance(cycle, dict) else getattr(cycle, 'id', None)
            logger.info(f"✅ [DEBUG] Cycle créé avec succès, ID: {cycle_id}")
            
            # Mettre à jour objectifs_cycle si fourni
            if objectifs_cycle and cycle_id:
                logger.info("🔍 [DEBUG] Ajout des objectifs du cycle")
                update_query = text(f"UPDATE {schema_name}.cycle_codev SET objectifs_cycle = :objectifs_cycle WHERE id = :cycle_id")
                session.exec(update_query.bindparams(objectifs_cycle=objectifs_cycle, cycle_id=cycle_id))
                session.commit()
            action = "create"
        
        programme_param = request.query_params.get('programme', '').upper()
        redirect_url = str(request.url_for("codev_cycle_detail", cycle_id=cycle_id))
        if programme_param:
            redirect_url = f"{redirect_url}?programme={programme_param}&success=1&action={action}"
        else:
            redirect_url = f"{redirect_url}?success=1&action={action}"
        
        logger.info(f"🔍 [DEBUG] Redirection vers: {redirect_url}")
        return RedirectResponse(
            url=redirect_url,
            status_code=303
        )
        
    except Exception as e:
        logger.error(f"❌ [DEBUG] Erreur création cycle: {e}")
        logger.error(f"❌ [DEBUG] Type d'erreur: {type(e).__name__}")
        import traceback
        logger.error(f"❌ [DEBUG] Traceback: {traceback.format_exc()}")
        programme_param = request.query_params.get('programme', '').upper()
        redirect_url = f"/codev/cycles/creer?error=1&message={str(e)}"
        if programme_param:
            redirect_url += f"&programme={programme_param}"
        
        logger.info(f"🔍 [DEBUG] Redirection vers (erreur): {redirect_url}")
        return RedirectResponse(
            url=redirect_url,
            status_code=303
        )

@router.get("/cycles/{cycle_id}", response_class=HTMLResponse, name="codev_cycle_detail")
async def codev_cycle_detail(
    cycle_id: int,
    request: Request,
    session: Session = Depends(get_shared_session),
    current_user: User = Depends(get_current_user),
    schema_routing_service: SchemaRoutingService = Depends(get_schema_routing_service)
):
    """Détail d'un cycle de codéveloppement"""
    codev_access_required(current_user)
    
    # Récupérer et configurer le schéma
    schema_name = get_schema_from_request(request) or 'acd'
    schema_routing_service.set_schema(schema_name)
    
    # Configurer explicitement le search_path
    session.exec(text(f"SET search_path TO {schema_name}, public"))
    session.commit()
    
    # Vérifier que la table existe
    if not table_exists_anywhere("cycle_codev", session, schema_name):
        raise HTTPException(status_code=404, detail="Cycle introuvable dans ce programme")
    
    # Récupérer le cycle avec JOIN programme et promotion - SQL direct
    cycle_query = text(f"""
        SELECT c.*, 
               p.nom as programme_nom, 
               p.code as programme_code,
               pr.libelle as promotion_nom
        FROM {schema_name}.cycle_codev c
        LEFT JOIN public.programme p ON c.programme_id = p.id
        LEFT JOIN {schema_name}.promotion pr ON c.promotion_id = pr.id
        WHERE c.id = :cycle_id
    """)
    cycle_result = session.exec(cycle_query.bindparams(cycle_id=cycle_id)).first()
    if not cycle_result:
        raise HTTPException(status_code=404, detail="Cycle introuvable")
    cycle = type('CycleCodev', (), dict(cycle_result._mapping))()
    
    # Récupérer l'animateur principal si présent
    if hasattr(cycle, 'animateur_principal_id') and cycle.animateur_principal_id:
        animateur_query = text("SELECT id, nom_complet, email FROM public.\"user\" WHERE id = :user_id")
        animateur_result = session.exec(animateur_query.bindparams(user_id=cycle.animateur_principal_id)).first()
        if animateur_result:
            cycle.animateur_principal = type('User', (), dict(animateur_result._mapping))()
    
    # Récupérer les groupes du cycle avec animateur - SQL direct
    groupes_query = text(f"""
        SELECT g.*, 
               u.nom_complet as animateur_nom_complet
        FROM {schema_name}.groupe_codev g
        LEFT JOIN public."user" u ON g.animateur_id = u.id
        WHERE g.cycle_id = :cycle_id
        ORDER BY g.nom_groupe
    """)
    groupes_results = session.exec(groupes_query.bindparams(cycle_id=cycle_id)).all()
    groupes = []
    for row in groupes_results:
        groupe = type('GroupeCodev', (), dict(row._mapping))()
        if hasattr(groupe, 'animateur_nom_complet') and groupe.animateur_nom_complet:
            groupe.animateur = type('User', (), {'nom_complet': groupe.animateur_nom_complet})()
        groupes.append(groupe)
    
    # Récupérer les statistiques
    stats = CodevService.get_statistiques_cycle(session, cycle_id, schema_name)
    
    programme_param = request.query_params.get('programme', '').upper()
    
    return templates.TemplateResponse(
        "pages/codev/cycle_detail.html",
        {
            "request": request,
            "utilisateur": current_user,
            "cycle": cycle,
            "groupes": groupes,
            "stats": stats,
            "settings": settings,
            "programme_param": programme_param,
            "schema_name": schema_name
        }
    )

@router.get("/groupes", response_class=HTMLResponse, name="codev_groupes")
async def codev_groupes(
    request: Request,
    session: Session = Depends(get_shared_session),
    current_user: User = Depends(get_current_user),
    cycle_id: Optional[int] = Query(None),
    schema_routing_service: SchemaRoutingService = Depends(get_schema_routing_service)
):
    """Liste des groupes de codéveloppement"""
    codev_access_required(current_user)
    
    # Initialiser stats avec des valeurs par défaut dès le début
    stats = {
        'total_groupes': 0,
        'groupes_en_constitution': 0,
        'groupes_actifs': 0,
        'groupes_termines': 0
    }
    
    # Récupérer et configurer le schéma
    schema_name = get_schema_from_request(request) or 'acd'
    schema_routing_service.set_schema(schema_name)
    
    # Configurer explicitement le search_path
    session.exec(text(f"SET search_path TO {schema_name}, public"))
    session.commit()
    
    # Récupérer les groupes - SQL direct avec JOIN cycle
    try:
        groupes_query = text(f"""
            SELECT g.*, c.nom as cycle_nom, c.date_debut as cycle_date_debut, c.date_fin as cycle_date_fin
            FROM {schema_name}.groupe_codev g
            LEFT JOIN {schema_name}.cycle_codev c ON g.cycle_id = c.id
            {"WHERE g.cycle_id = :cycle_id" if cycle_id else ""}
            ORDER BY g.nom_groupe
        """)
        params = {}
        if cycle_id:
            params['cycle_id'] = cycle_id
        
        groupes_results = session.exec(groupes_query.bindparams(**params) if params else groupes_query).all()
        # Convertir les résultats en objets simples avec accès aux attributs
        groupes = []
        for row in groupes_results:
            if hasattr(row, '_asdict'):
                # Row SQLAlchemy
                row_dict = row._asdict()
            elif hasattr(row, '__dict__'):
                # Objet avec __dict__
                row_dict = row.__dict__
            elif isinstance(row, dict):
                # Déjà un dict
                row_dict = row
            else:
                # Fallback: créer un dict depuis les attributs
                row_dict = {key: getattr(row, key) for key in dir(row) if not key.startswith('_')}
            
            # Créer un objet simple avec accès aux attributs
            groupe_obj = type('GroupeCodev', (), row_dict)()
            groupes.append(groupe_obj)
    except Exception as e:
        print(f"⚠️ [WARNING] Erreur lors de la récupération des groupes: {e}")
        groupes = []
    
    # Récupérer les cycles pour le filtre - SQL direct
    try:
        cycles_query = text(f"SELECT * FROM {schema_name}.cycle_codev ORDER BY date_debut DESC")
        cycles_results = session.exec(cycles_query).all()
        cycles = [type('CycleCodev', (), dict(row._mapping))() for row in cycles_results]
    except Exception as e:
        print(f"⚠️ [WARNING] Erreur lors de la récupération des cycles: {e}")
        cycles = []
    
    # Calculer les KPIs
    try:
        stats['total_groupes'] = len(groupes)
        for groupe in groupes:
            # Accéder au statut via getattr ou directement depuis le dict si c'est un Row
            if hasattr(groupe, 'statut'):
                statut = getattr(groupe, 'statut', 'en_constitution')
            elif hasattr(groupe, '__dict__'):
                statut = groupe.__dict__.get('statut', 'en_constitution')
            else:
                # Si c'est un Row SQLAlchemy, accéder via index ou key
                try:
                    statut = groupe['statut'] if isinstance(groupe, dict) else getattr(groupe, 'statut', 'en_constitution')
                except:
                    statut = 'en_constitution'
            
            if not statut:
                statut = 'en_constitution'
            
            if statut == 'en_constitution':
                stats['groupes_en_constitution'] += 1
            elif statut == 'actif':
                stats['groupes_actifs'] += 1
            elif statut == 'termine':
                stats['groupes_termines'] += 1
    except Exception as e:
        print(f"⚠️ [WARNING] Erreur lors du calcul des KPIs: {e}")
        import traceback
        traceback.print_exc()
        # En cas d'erreur, stats garde ses valeurs par défaut
    
    programme_param = request.query_params.get('programme', '').upper()
    
    # S'assurer que stats est toujours défini
    if 'stats' not in locals() or stats is None:
        stats = {
            'total_groupes': 0,
            'groupes_en_constitution': 0,
            'groupes_actifs': 0,
            'groupes_termines': 0
        }
    
    return templates.TemplateResponse(
        "pages/codev/groupes.html",
        {
            "request": request,
            "utilisateur": current_user,
            "groupes": groupes if 'groupes' in locals() else [],
            "cycles": cycles if 'cycles' in locals() else [],
            "cycle_id": cycle_id,
            "settings": settings,
            "programme_param": programme_param,
            "schema_name": schema_name if 'schema_name' in locals() else 'acd',
            "stats": stats
        }
    )

@router.get("/groupes/creer", response_class=HTMLResponse, name="codev_groupes_create_form")
async def codev_groupes_creer(
    request: Request,
    session: Session = Depends(get_shared_session),
    current_user: User = Depends(get_current_user),
    cycle_id: Optional[int] = Query(None),
    schema_routing_service: SchemaRoutingService = Depends(get_schema_routing_service)
):
    """Formulaire de création d'un groupe de codéveloppement"""
    codev_access_required(current_user)
    
    # Récupérer et configurer le schéma
    schema_name = get_schema_from_request(request) or 'acd'
    schema_routing_service.set_schema(schema_name)
    
    # Configurer explicitement le search_path
    session.exec(text(f"SET search_path TO {schema_name}, public"))
    session.commit()
    
    # Récupérer les cycles disponibles - SQL direct
    try:
        cycles_query = text(f"SELECT * FROM {schema_name}.cycle_codev ORDER BY date_debut DESC")
        cycles_results = session.exec(cycles_query).all()
        cycles = []
        for row in cycles_results:
            if hasattr(row, '_asdict'):
                row_dict = row._asdict()
            elif hasattr(row, '__dict__'):
                row_dict = row.__dict__
            elif isinstance(row, dict):
                row_dict = row
            else:
                row_dict = {key: getattr(row, key) for key in dir(row) if not key.startswith('_')}
            cycle_obj = type('CycleCodev', (), row_dict)()
            cycles.append(cycle_obj)
    except Exception as e:
        print(f"⚠️ [WARNING] Erreur lors de la récupération des cycles: {e}")
        cycles = []
    
    # Récupérer les groupes disponibles - SQL direct (table public.groupe)
    try:
        groupes_query = text("SELECT * FROM public.groupe ORDER BY nom")
        groupes_results = session.exec(groupes_query).all()
        groupes = []
        for row in groupes_results:
            if hasattr(row, '_asdict'):
                row_dict = row._asdict()
            elif hasattr(row, '__dict__'):
                row_dict = row.__dict__
            elif isinstance(row, dict):
                row_dict = row
            else:
                row_dict = {key: getattr(row, key) for key in dir(row) if not key.startswith('_')}
            groupe_obj = type('Groupe', (), row_dict)()
            groupes.append(groupe_obj)
    except Exception as e:
        print(f"⚠️ [WARNING] Erreur lors de la récupération des groupes: {e}")
        groupes = []
    
    # Récupérer les utilisateurs pouvant être animateurs - SQL direct
    try:
        animateurs_query = text("""
            SELECT * FROM public."user"
            WHERE role IN ('responsable_programme', 'conseiller', 'coordinateur', 'formateur', 'accompagnateur')
            ORDER BY nom_complet
        """)
        animateurs_results = session.exec(animateurs_query).all()
        animateurs = []
        for row in animateurs_results:
            if hasattr(row, '_asdict'):
                row_dict = row._asdict()
            elif hasattr(row, '__dict__'):
                row_dict = row.__dict__
            elif isinstance(row, dict):
                row_dict = row
            else:
                row_dict = {key: getattr(row, key) for key in dir(row) if not key.startswith('_')}
            animateur_obj = type('User', (), row_dict)()
            animateurs.append(animateur_obj)
    except Exception as e:
        print(f"⚠️ [WARNING] Erreur lors de la récupération des animateurs: {e}")
        animateurs = []
    
    programme_param = request.query_params.get('programme', '').upper()
    
    return templates.TemplateResponse(
        "pages/codev/groupe_form.html",
        {
            "request": request,
            "utilisateur": current_user,
            "cycles": cycles,
            "groupes": groupes,
            "animateurs": animateurs,
            "cycle_id": cycle_id,
            "settings": settings,
            "programme_param": programme_param,
            "schema_name": schema_name
        }
    )

@router.post("/groupes/creer", name="codev_groupes_create")
async def codev_groupes_creer_post(
    request: Request,
    cycle_id: int = Form(...),
    groupe_id: int = Form(...),
    nom_groupe: str = Form(...),
    animateur_id: Optional[int] = Form(None),
    capacite_max: int = Form(12),
    session: Session = Depends(get_shared_session),
    current_user: User = Depends(get_current_user)
):
    """Création d'un groupe de codéveloppement"""
    codev_access_required(current_user)
    
    try:
        groupe_codev = CodevService.create_groupe_codev(
            session=session,
            cycle_id=cycle_id,
            groupe_id=groupe_id,
            nom_groupe=nom_groupe,
            animateur_id=animateur_id,
            capacite_max=capacite_max
        )
        
        programme_param = request.query_params.get('programme', '').upper()
        redirect_url = f"/codev/groupes?cycle_id={cycle_id}&success=1&action=create"
        if programme_param:
            redirect_url += f"&programme={programme_param}"
        
        return RedirectResponse(
            url=redirect_url,
            status_code=303
        )
        
    except Exception as e:
        logger.error(f"Erreur création groupe: {e}")
        programme_param = request.query_params.get('programme', '').upper()
        redirect_url = f"/codev/groupes/creer?error=1&message={str(e)}"
        if programme_param:
            redirect_url += f"&programme={programme_param}"
        
        return RedirectResponse(
            url=redirect_url,
            status_code=303
        )

@router.get("/groupes/{groupe_id}", response_class=HTMLResponse, name="codev_groupe_detail")
async def codev_groupe_detail(
    groupe_id: int,
    request: Request,
    session: Session = Depends(get_shared_session),
    current_user: User = Depends(get_current_user),
    schema_routing_service: SchemaRoutingService = Depends(get_schema_routing_service)
):
    """Détail d'un groupe de codéveloppement"""
    codev_access_required(current_user)
    
    # Récupérer et configurer le schéma
    schema_name = get_schema_from_request(request) or 'acd'
    schema_routing_service.set_schema(schema_name)
    
    # Configurer explicitement le search_path
    session.exec(text(f"SET search_path TO {schema_name}, public"))
    session.commit()
    
    # Vérifier que la table existe
    if not table_exists_anywhere("groupe_codev", session, schema_name):
        raise HTTPException(status_code=404, detail="Groupe introuvable dans ce programme")
    
    # Récupérer le groupe avec JOIN cycle - SQL direct
    groupe_query = text(f"""
        SELECT g.*, 
               c.nom as cycle_nom,
               c.programme_id as cycle_programme_id,
               u.nom_complet as animateur_nom_complet
        FROM {schema_name}.groupe_codev g
        LEFT JOIN {schema_name}.cycle_codev c ON g.cycle_id = c.id
        LEFT JOIN public."user" u ON g.animateur_id = u.id
        WHERE g.id = :groupe_id
    """)
    groupe_result = session.exec(groupe_query.bindparams(groupe_id=groupe_id)).first()
    if not groupe_result:
        raise HTTPException(status_code=404, detail="Groupe introuvable")
    groupe = type('GroupeCodev', (), dict(groupe_result._mapping))()
    
    # Récupérer tous les membres du groupe (sans filtre de statut)
    membres_query = text(f"""
        SELECT m.*,
               c.nom as candidat_nom,
               c.prenom as candidat_prenom,
               c.email as candidat_email
        FROM {schema_name}.membre_groupe_codev m
        LEFT JOIN {schema_name}.candidat c ON m.candidat_id = c.id
        WHERE m.groupe_codev_id = :groupe_id
        ORDER BY m.date_integration ASC
    """)
    membres_results = session.exec(membres_query.bindparams(groupe_id=groupe_id)).all()
    membres = []
    for row in membres_results:
        membre = type('MembreGroupeCodev', (), dict(row._mapping))()
        # Construire le nom complet même si candidat_nom ou candidat_prenom est None
        if getattr(membre, 'candidat_nom', None) or getattr(membre, 'candidat_prenom', None):
            membre.candidat_nom_complet = f"{membre.candidat_prenom or ''} {membre.candidat_nom or ''}".strip()
        else:
            membre.candidat_nom_complet = f"Candidat ID {membre.candidat_id}" if hasattr(membre, 'candidat_id') else "Membre inconnu"
        membres.append(membre)
    
    # Récupérer les candidats disponibles (non membres du groupe) avec statut VALIDE
    candidats_disponibles_query = text(f"""
        SELECT c.*
        FROM {schema_name}.candidat c
        WHERE c.statut = 'VALIDE'
        AND c.id NOT IN (
            SELECT m.candidat_id 
            FROM {schema_name}.membre_groupe_codev m 
            WHERE m.groupe_codev_id = :groupe_id
        )
        ORDER BY c.nom, c.prenom
    """)
    candidats_disponibles_results = session.exec(candidats_disponibles_query.bindparams(groupe_id=groupe_id)).all()
    candidats_disponibles = []
    for row in candidats_disponibles_results:
        candidat = type('Candidat', (), dict(row._mapping))()
        if getattr(candidat, 'nom', None) and getattr(candidat, 'prenom', None):
            candidat.nom_complet = f"{candidat.prenom or ''} {candidat.nom or ''}".strip()
        candidats_disponibles.append(candidat)
    
    programme_param = request.query_params.get('programme', '').upper()
    
    return templates.TemplateResponse(
        "pages/codev/groupe_detail.html",
        {
            "request": request,
            "utilisateur": current_user,
            "groupe": groupe,
            "membres": membres,
            "candidats_disponibles": candidats_disponibles,
            "settings": settings,
            "programme_param": programme_param,
            "schema_name": schema_name
        }
    )

@router.post("/groupes/{groupe_id}/membres/ajouter", name="codev_groupe_add_membre")
async def codev_groupe_add_membre(
    groupe_id: int,
    request: Request,
    candidat_id: int = Form(...),
    session: Session = Depends(get_shared_session),
    current_user: User = Depends(get_current_user),
    schema_routing_service: SchemaRoutingService = Depends(get_schema_routing_service)
):
    """Ajouter un membre à un groupe"""
    codev_access_required(current_user)
    
    schema_name = get_schema_from_request(request) or 'acd'
    schema_routing_service.set_schema(schema_name)
    session.exec(text(f"SET search_path TO {schema_name}, public"))
    session.commit()
    
    try:
        CodevService.add_membre_groupe(
            session=session,
            groupe_codev_id=groupe_id,
            candidat_id=candidat_id,
            schema_name=schema_name
        )
        
        programme_param = request.query_params.get('programme', '').upper()
        redirect_url = f"/codev/groupes/{groupe_id}?success=1&action=add_membre"
        if programme_param:
            redirect_url += f"&programme={programme_param}"
        
        return RedirectResponse(url=redirect_url, status_code=303)
        
    except Exception as e:
        logger.error(f"Erreur ajout membre: {e}")
        programme_param = request.query_params.get('programme', '').upper()
        redirect_url = f"/codev/groupes/{groupe_id}?error=1&message={str(e)}"
        if programme_param:
            redirect_url += f"&programme={programme_param}"
        return RedirectResponse(url=redirect_url, status_code=303)

@router.post("/groupes/{groupe_id}/membres/{membre_id}/retirer", name="codev_groupe_remove_membre")
async def codev_groupe_remove_membre(
    groupe_id: int,
    membre_id: int,
    request: Request,
    session: Session = Depends(get_shared_session),
    current_user: User = Depends(get_current_user),
    schema_routing_service: SchemaRoutingService = Depends(get_schema_routing_service)
):
    """Retirer un membre d'un groupe"""
    codev_access_required(current_user)
    
    schema_name = get_schema_from_request(request) or 'acd'
    schema_routing_service.set_schema(schema_name)
    session.exec(text(f"SET search_path TO {schema_name}, public"))
    session.commit()
    
    try:
        # Vérifier que le membre existe
        check_query = text(f"""
            SELECT id FROM {schema_name}.membre_groupe_codev
            WHERE id = :membre_id AND groupe_codev_id = :groupe_id
        """)
        check_result = session.exec(check_query.bindparams(membre_id=membre_id, groupe_id=groupe_id)).first()
        
        if not check_result:
            raise ValueError("Membre introuvable")
        
        # Supprimer complètement le membre de la table
        delete_query = text(f"""
            DELETE FROM {schema_name}.membre_groupe_codev
            WHERE id = :membre_id AND groupe_codev_id = :groupe_id
        """)
        result = session.exec(delete_query.bindparams(membre_id=membre_id, groupe_id=groupe_id))
        session.commit()
        
        # Vérifier que la suppression a bien été effectuée
        if result.rowcount == 0:
            raise ValueError("Aucun membre n'a été supprimé")
        
        programme_param = request.query_params.get('programme', '').upper()
        redirect_url = f"/codev/groupes/{groupe_id}?success=1&action=remove_membre"
        if programme_param:
            redirect_url += f"&programme={programme_param}"
        
        return RedirectResponse(url=redirect_url, status_code=303)
        
    except Exception as e:
        logger.error(f"Erreur retrait membre: {e}")
        programme_param = request.query_params.get('programme', '').upper()
        redirect_url = f"/codev/groupes/{groupe_id}?error=1&message={str(e)}"
        if programme_param:
            redirect_url += f"&programme={programme_param}"
        return RedirectResponse(url=redirect_url, status_code=303)

@router.get("/statistiques", response_class=HTMLResponse, name="codev_statistiques")
async def codev_statistiques(
    request: Request,
    session: Session = Depends(get_shared_session),
    current_user: User = Depends(get_current_user),
    schema_routing_service: SchemaRoutingService = Depends(get_schema_routing_service)
):
    """Statistiques du système de codéveloppement"""
    codev_access_required(current_user)
    
    # Initialiser stats avec des valeurs par défaut
    stats = {
        'total_cycles': 0,
        'total_groupes': 0,
        'total_membres': 0,
        'total_seances': 0,
        'total_presentations': 0
    }
    
    # Initialiser les listes
    cycles_par_statut = []
    groupes_par_statut = []
    seances_par_statut = []
    presentations_par_statut = []
    cycles_recents = []
    groupes_populaires = []
    
    # Récupérer et configurer le schéma
    schema_name = get_schema_from_request(request) or 'acd'
    schema_routing_service.set_schema(schema_name)
    
    # Configurer explicitement le search_path
    session.exec(text(f"SET search_path TO {schema_name}, public"))
    session.commit()
    
    # Statistiques générales - SQL direct
    try:
        # Total cycles
        cycles_count_query = text(f"SELECT COUNT(*) FROM {schema_name}.cycle_codev")
        result = session.exec(cycles_count_query).one()
        stats['total_cycles'] = extract_count_value(result)
    except Exception as e:
        print(f"⚠️ [WARNING] Erreur lors du comptage des cycles: {e}")
        stats['total_cycles'] = 0
    
    try:
        # Total groupes
        groupes_count_query = text(f"SELECT COUNT(*) FROM {schema_name}.groupe_codev")
        result = session.exec(groupes_count_query).one()
        stats['total_groupes'] = extract_count_value(result)
    except Exception as e:
        print(f"⚠️ [WARNING] Erreur lors du comptage des groupes: {e}")
        stats['total_groupes'] = 0
    
    try:
        # Total membres
        membres_count_query = text(f"SELECT COUNT(*) FROM {schema_name}.membre_groupe_codev")
        result = session.exec(membres_count_query).one()
        stats['total_membres'] = extract_count_value(result)
    except Exception as e:
        print(f"⚠️ [WARNING] Erreur lors du comptage des membres: {e}")
        stats['total_membres'] = 0
    
    try:
        # Total séances
        seances_count_query = text(f"SELECT COUNT(*) FROM {schema_name}.seance_codev")
        result = session.exec(seances_count_query).one()
        stats['total_seances'] = extract_count_value(result)
    except Exception as e:
        print(f"⚠️ [WARNING] Erreur lors du comptage des séances: {e}")
        stats['total_seances'] = 0
    
    try:
        # Total présentations
        presentations_count_query = text(f"SELECT COUNT(*) FROM {schema_name}.presentation_codev")
        result = session.exec(presentations_count_query).one()
        stats['total_presentations'] = extract_count_value(result)
    except Exception as e:
        print(f"⚠️ [WARNING] Erreur lors du comptage des présentations: {e}")
        stats['total_presentations'] = 0
    
    # Cycles par statut - SQL direct
    try:
        cycles_statut_query = text(f"""
            SELECT statut, COUNT(*) as count
            FROM {schema_name}.cycle_codev
            GROUP BY statut
        """)
        cycles_statut_results = session.exec(cycles_statut_query).all()
        cycles_par_statut = []
        for row in cycles_statut_results:
            if isinstance(row, tuple):
                statut_val = row[0]
                count_val = row[1]
                # Extraire la valeur du tuple si nécessaire
                if isinstance(count_val, tuple):
                    count_val = count_val[0] if count_val else 0
                elif not isinstance(count_val, int):
                    count_val = int(count_val) if count_val else 0
                cycles_par_statut.append({'statut': statut_val, 'count': count_val})
            elif hasattr(row, '_asdict'):
                row_dict = row._asdict()
                count_val = row_dict.get('count', 0)
                if isinstance(count_val, tuple):
                    count_val = count_val[0] if count_val else 0
                cycles_par_statut.append({'statut': row_dict.get('statut'), 'count': count_val})
            else:
                count_val = getattr(row, 'count', 0)
                if isinstance(count_val, tuple):
                    count_val = count_val[0] if count_val else 0
                cycles_par_statut.append({'statut': getattr(row, 'statut', None), 'count': count_val})
    except Exception as e:
        print(f"⚠️ [WARNING] Erreur lors de la récupération des cycles par statut: {e}")
        cycles_par_statut = []
    
    # Groupes par statut - SQL direct
    try:
        groupes_statut_query = text(f"""
            SELECT statut, COUNT(*) as count
            FROM {schema_name}.groupe_codev
            GROUP BY statut
        """)
        groupes_statut_results = session.exec(groupes_statut_query).all()
        groupes_par_statut = []
        for row in groupes_statut_results:
            if isinstance(row, tuple):
                statut_val = row[0]
                count_val = row[1]
                # Extraire la valeur du tuple si nécessaire
                if isinstance(count_val, tuple):
                    count_val = count_val[0] if count_val else 0
                elif not isinstance(count_val, int):
                    count_val = int(count_val) if count_val else 0
                groupes_par_statut.append({'statut': statut_val, 'count': count_val})
            elif hasattr(row, '_asdict'):
                row_dict = row._asdict()
                count_val = row_dict.get('count', 0)
                if isinstance(count_val, tuple):
                    count_val = count_val[0] if count_val else 0
                groupes_par_statut.append({'statut': row_dict.get('statut'), 'count': count_val})
            else:
                count_val = getattr(row, 'count', 0)
                if isinstance(count_val, tuple):
                    count_val = count_val[0] if count_val else 0
                groupes_par_statut.append({'statut': getattr(row, 'statut', None), 'count': count_val})
    except Exception as e:
        print(f"⚠️ [WARNING] Erreur lors de la récupération des groupes par statut: {e}")
        groupes_par_statut = []
    
    # Séances par statut - SQL direct
    try:
        seances_statut_query = text(f"""
            SELECT statut, COUNT(*) as count
            FROM {schema_name}.seance_codev
            GROUP BY statut
        """)
        seances_statut_results = session.exec(seances_statut_query).all()
        seances_par_statut = []
        for row in seances_statut_results:
            if isinstance(row, tuple):
                statut_val = row[0]
                count_val = row[1]
                # Extraire la valeur du tuple si nécessaire
                if isinstance(count_val, tuple):
                    count_val = count_val[0] if count_val else 0
                elif not isinstance(count_val, int):
                    count_val = int(count_val) if count_val else 0
                seances_par_statut.append({'statut': statut_val, 'count': count_val})
            elif hasattr(row, '_asdict'):
                row_dict = row._asdict()
                count_val = row_dict.get('count', 0)
                if isinstance(count_val, tuple):
                    count_val = count_val[0] if count_val else 0
                seances_par_statut.append({'statut': row_dict.get('statut'), 'count': count_val})
            else:
                count_val = getattr(row, 'count', 0)
                if isinstance(count_val, tuple):
                    count_val = count_val[0] if count_val else 0
                seances_par_statut.append({'statut': getattr(row, 'statut', None), 'count': count_val})
    except Exception as e:
        print(f"⚠️ [WARNING] Erreur lors de la récupération des séances par statut: {e}")
        seances_par_statut = []
    
    # Présentations par statut - SQL direct
    try:
        presentations_statut_query = text(f"""
            SELECT statut, COUNT(*) as count
            FROM {schema_name}.presentation_codev
            GROUP BY statut
        """)
        presentations_statut_results = session.exec(presentations_statut_query).all()
        presentations_par_statut = []
        for row in presentations_statut_results:
            if isinstance(row, tuple):
                statut_val = row[0]
                count_val = row[1]
                # Extraire la valeur du tuple si nécessaire
                if isinstance(count_val, tuple):
                    count_val = count_val[0] if count_val else 0
                elif not isinstance(count_val, int):
                    count_val = int(count_val) if count_val else 0
                presentations_par_statut.append({'statut': statut_val, 'count': count_val})
            elif hasattr(row, '_asdict'):
                row_dict = row._asdict()
                count_val = row_dict.get('count', 0)
                if isinstance(count_val, tuple):
                    count_val = count_val[0] if count_val else 0
                presentations_par_statut.append({'statut': row_dict.get('statut'), 'count': count_val})
            else:
                count_val = getattr(row, 'count', 0)
                if isinstance(count_val, tuple):
                    count_val = count_val[0] if count_val else 0
                presentations_par_statut.append({'statut': getattr(row, 'statut', None), 'count': count_val})
    except Exception as e:
        print(f"⚠️ [WARNING] Erreur lors de la récupération des présentations par statut: {e}")
        presentations_par_statut = []
    
    # Cycles récents - SQL direct
    try:
        cycles_recents_query = text(f"""
            SELECT * FROM {schema_name}.cycle_codev
            ORDER BY cree_le DESC
            LIMIT 5
        """)
        cycles_recents_results = session.exec(cycles_recents_query).all()
        cycles_recents = []
        for row in cycles_recents_results:
            if hasattr(row, '_asdict'):
                row_dict = row._asdict()
            elif hasattr(row, '__dict__'):
                row_dict = row.__dict__
            elif isinstance(row, dict):
                row_dict = row
            else:
                row_dict = {key: getattr(row, key) for key in dir(row) if not key.startswith('_')}
            cycle_obj = type('CycleCodev', (), row_dict)()
            cycles_recents.append(cycle_obj)
    except Exception as e:
        print(f"⚠️ [WARNING] Erreur lors de la récupération des cycles récents: {e}")
        cycles_recents = []
    
    # Groupes avec le plus de membres - SQL direct
    try:
        groupes_populaires_query = text(f"""
            SELECT g.*, COUNT(m.id) as nb_membres
            FROM {schema_name}.groupe_codev g
            LEFT JOIN {schema_name}.membre_groupe_codev m ON g.id = m.groupe_codev_id
            GROUP BY g.id
            ORDER BY nb_membres DESC
            LIMIT 5
        """)
        groupes_populaires_results = session.exec(groupes_populaires_query).all()
        groupes_populaires = []
        for row in groupes_populaires_results:
            if hasattr(row, '_asdict'):
                row_dict = row._asdict()
            elif hasattr(row, '__dict__'):
                row_dict = row.__dict__
            elif isinstance(row, dict):
                row_dict = row
            else:
                row_dict = {key: getattr(row, key) for key in dir(row) if not key.startswith('_')}
            groupe_obj = type('GroupeCodev', (), row_dict)()
            groupes_populaires.append(groupe_obj)
    except Exception as e:
        print(f"⚠️ [WARNING] Erreur lors de la récupération des groupes populaires: {e}")
        groupes_populaires = []
    
    programme_param = request.query_params.get('programme', '').upper()
    
    return templates.TemplateResponse(
        "pages/codev/statistiques.html",
        {
            "request": request,
            "utilisateur": current_user,
            "stats": stats,
            "cycles_par_statut": cycles_par_statut,
            "groupes_par_statut": groupes_par_statut,
            "seances_par_statut": seances_par_statut,
            "presentations_par_statut": presentations_par_statut,
            "cycles_recents": cycles_recents,
            "groupes_populaires": groupes_populaires,
            "settings": settings,
            "programme_param": programme_param,
            "schema_name": schema_name
        }
    )

@router.get("/seances/{seance_id}", response_class=HTMLResponse, name="codev_seance_detail")
async def codev_seance_detail(
    seance_id: int,
    request: Request,
    session: Session = Depends(get_shared_session),
    current_user: User = Depends(get_current_user),
    schema_routing_service: SchemaRoutingService = Depends(get_schema_routing_service)
):
    """Détail d'une séance de codéveloppement"""
    codev_access_required(current_user)
    
    # Récupérer et configurer le schéma
    schema_name = get_schema_from_request(request) or 'acd'
    schema_routing_service.set_schema(schema_name)
    
    # Configurer explicitement le search_path
    session.exec(text(f"SET search_path TO {schema_name}, public"))
    session.commit()
    
    # Vérifier que la table existe
    if not table_exists_anywhere("seance_codev", session, schema_name):
        raise HTTPException(status_code=404, detail="Séance introuvable dans ce programme")
    
    # Récupérer la séance avec JOIN groupe et cycle - SQL direct
    seance_query = text(f"""
        SELECT s.*, 
               g.nom_groupe as groupe_nom,
               g.cycle_id as groupe_cycle_id,
               c.nom as cycle_nom
        FROM {schema_name}.seance_codev s
        LEFT JOIN {schema_name}.groupe_codev g ON s.groupe_id = g.id
        LEFT JOIN {schema_name}.cycle_codev c ON g.cycle_id = c.id
        WHERE s.id = :seance_id
    """)
    seance_result = session.exec(seance_query.bindparams(seance_id=seance_id)).first()
    if not seance_result:
        raise HTTPException(status_code=404, detail="Séance introuvable")
    seance = type('SeanceCodev', (), dict(seance_result._mapping))()
    
    # Récupérer l'animateur si présent
    if getattr(seance, 'animateur_id', None):
        animateur_query = text("SELECT id, nom_complet, email FROM public.\"user\" WHERE id = :user_id")
        animateur_result = session.exec(animateur_query.bindparams(user_id=seance.animateur_id)).first()
        if animateur_result:
            seance.animateur = type('User', (), dict(animateur_result._mapping))()
    
    # Récupérer les présentations de cette séance
    presentations_query = text(f"""
        SELECT p.*, 
               c.nom as candidat_nom,
               c.prenom as candidat_prenom
        FROM {schema_name}.presentation_codev p
        LEFT JOIN {schema_name}.candidat c ON p.candidat_id = c.id
        WHERE p.seance_id = :seance_id
        ORDER BY p.ordre_presentation
    """)
    presentations_results = session.exec(presentations_query.bindparams(seance_id=seance_id)).all()
    presentations = []
    for row in presentations_results:
        presentation = type('PresentationCodev', (), dict(row._mapping))()
        if getattr(presentation, 'candidat_nom', None) or getattr(presentation, 'candidat_prenom', None):
            presentation.candidat_nom_complet = f"{presentation.candidat_prenom or ''} {presentation.candidat_nom or ''}".strip()
        else:
            presentation.candidat_nom_complet = f"Candidat ID {presentation.candidat_id}" if hasattr(presentation, 'candidat_id') else "Candidat inconnu"
        presentations.append(presentation)
    
    # Récupérer les contributions de cette séance
    contributions_query = text(f"""
        SELECT cont.*,
               c.nom as contributeur_nom,
               c.prenom as contributeur_prenom
        FROM {schema_name}.contribution_codev cont
        LEFT JOIN {schema_name}.candidat c ON cont.contributeur_id = c.id
        WHERE cont.seance_id = :seance_id
        ORDER BY cont.ordre_contribution, cont.cree_le
    """)
    contributions_results = session.exec(contributions_query.bindparams(seance_id=seance_id)).all()
    contributions = []
    for row in contributions_results:
        contribution = type('ContributionCodev', (), dict(row._mapping))()
        if getattr(contribution, 'contributeur_nom', None) or getattr(contribution, 'contributeur_prenom', None):
            contribution.contributeur_nom_complet = f"{contribution.contributeur_prenom or ''} {contribution.contributeur_nom or ''}".strip()
        else:
            contribution.contributeur_nom_complet = f"Candidat ID {contribution.contributeur_id}" if hasattr(contribution, 'contributeur_id') else "Contributeur inconnu"
        contributions.append(contribution)
    
    # Récupérer les membres du groupe pour permettre d'ajouter des contributions
    groupe_query = text(f"""
        SELECT g.id as groupe_codev_id
        FROM {schema_name}.groupe_codev g
        WHERE g.id = :groupe_id
    """)
    groupe_result = session.exec(groupe_query.bindparams(groupe_id=seance.groupe_id)).first()
    groupe_codev_id = None
    if groupe_result:
        groupe_codev_id = dict(groupe_result._mapping).get('groupe_codev_id')
    
    membres = []
    if groupe_codev_id:
        membres_query = text(f"""
            SELECT m.candidat_id,
                   c.nom as candidat_nom,
                   c.prenom as candidat_prenom
            FROM {schema_name}.membre_groupe_codev m
            LEFT JOIN {schema_name}.candidat c ON m.candidat_id = c.id
            WHERE m.groupe_codev_id = :groupe_codev_id
            ORDER BY m.date_integration
        """)
        membres_results = session.exec(membres_query.bindparams(groupe_codev_id=groupe_codev_id)).all()
        for row in membres_results:
            membre = type('MembreGroupeCodev', (), dict(row._mapping))()
            if getattr(membre, 'candidat_nom', None) or getattr(membre, 'candidat_prenom', None):
                membre.candidat_nom_complet = f"{membre.candidat_prenom or ''} {membre.candidat_nom or ''}".strip()
            membres.append(membre)
    
    programme_param = request.query_params.get('programme', '').upper()
    
    return templates.TemplateResponse(
        "pages/codev/seance_detail.html",
        {
            "request": request,
            "utilisateur": current_user,
            "seance": seance,
            "presentations": presentations,
            "contributions": contributions,
            "membres": membres,
            "settings": settings,
            "programme_param": programme_param,
            "schema_name": schema_name
        }
    )

@router.get("/seances", response_class=HTMLResponse, name="codev_seances")
async def codev_seances(
    request: Request,
    session: Session = Depends(get_shared_session),
    current_user: User = Depends(get_current_user),
    groupe_id: Optional[int] = Query(None),
    statut: Optional[str] = Query(None),
    schema_routing_service: SchemaRoutingService = Depends(get_schema_routing_service)
):
    """Liste des séances de codéveloppement"""
    codev_access_required(current_user)
    
    # Initialiser stats avec des valeurs par défaut dès le début
    stats = {
        'total_seances': 0,
        'seances_planifiees': 0,
        'seances_en_cours': 0,
        'seances_terminees': 0
    }
    
    # Récupérer et configurer le schéma
    schema_name = get_schema_from_request(request) or 'acd'
    schema_routing_service.set_schema(schema_name)
    
    # Configurer explicitement le search_path
    session.exec(text(f"SET search_path TO {schema_name}, public"))
    session.commit()
    
    # Récupérer les séances - SQL direct avec JOIN groupe
    try:
        seances_query = text(f"""
            SELECT s.*, g.nom_groupe as groupe_nom, g.cycle_id as groupe_cycle_id
            FROM {schema_name}.seance_codev s
            LEFT JOIN {schema_name}.groupe_codev g ON s.groupe_id = g.id
            {"WHERE s.groupe_id = :groupe_id" if groupe_id else ""}
            {"AND s.statut = :statut" if statut else ""}
            ORDER BY s.date_seance DESC
        """)
        params = {}
        if groupe_id:
            params['groupe_id'] = groupe_id
        if statut:
            params['statut'] = statut
        
        seances_results = session.exec(seances_query.bindparams(**params) if params else seances_query).all()
        # Convertir les résultats en objets simples avec accès aux attributs
        seances = []
        for row in seances_results:
            if hasattr(row, '_asdict'):
                row_dict = row._asdict()
            elif hasattr(row, '__dict__'):
                row_dict = row.__dict__
            elif isinstance(row, dict):
                row_dict = row
            else:
                row_dict = {key: getattr(row, key) for key in dir(row) if not key.startswith('_')}
            seance_obj = type('SeanceCodev', (), row_dict)()
            seances.append(seance_obj)
    except Exception as e:
        print(f"⚠️ [WARNING] Erreur lors de la récupération des séances: {e}")
        import traceback
        traceback.print_exc()
        seances = []
    
    # Récupérer les groupes pour le filtre - SQL direct
    try:
        groupes_query = text(f"SELECT * FROM {schema_name}.groupe_codev ORDER BY nom_groupe")
        groupes_results = session.exec(groupes_query).all()
        groupes = []
        for row in groupes_results:
            if hasattr(row, '_asdict'):
                row_dict = row._asdict()
            elif hasattr(row, '__dict__'):
                row_dict = row.__dict__
            elif isinstance(row, dict):
                row_dict = row
            else:
                row_dict = {key: getattr(row, key) for key in dir(row) if not key.startswith('_')}
            groupe_obj = type('GroupeCodev', (), row_dict)()
            groupes.append(groupe_obj)
    except Exception as e:
        print(f"⚠️ [WARNING] Erreur lors de la récupération des groupes: {e}")
        groupes = []
    
    # Calculer les KPIs
    try:
        stats['total_seances'] = len(seances)
        for seance in seances:
            # Accéder au statut
            if hasattr(seance, 'statut'):
                seance_statut = getattr(seance, 'statut', 'planifiee')
            elif hasattr(seance, '__dict__'):
                seance_statut = seance.__dict__.get('statut', 'planifiee')
            else:
                seance_statut = 'planifiee'
            
            if not seance_statut:
                seance_statut = 'planifiee'
            
            if seance_statut == 'planifiee':
                stats['seances_planifiees'] += 1
            elif seance_statut == 'en_cours':
                stats['seances_en_cours'] += 1
            elif seance_statut == 'terminee':
                stats['seances_terminees'] += 1
    except Exception as e:
        print(f"⚠️ [WARNING] Erreur lors du calcul des KPIs: {e}")
        import traceback
        traceback.print_exc()
    
    programme_param = request.query_params.get('programme', '').upper()
    
    # S'assurer que stats est toujours défini
    if 'stats' not in locals() or stats is None:
        stats = {
            'total_seances': 0,
            'seances_planifiees': 0,
            'seances_en_cours': 0,
            'seances_terminees': 0
        }
    
    return templates.TemplateResponse(
        "pages/codev/seances.html",
        {
            "request": request,
            "utilisateur": current_user,
            "seances": seances if 'seances' in locals() else [],
            "groupes": groupes if 'groupes' in locals() else [],
            "groupe_id": groupe_id,
            "statut": statut,
            "settings": settings,
            "programme_param": programme_param,
            "schema_name": schema_name if 'schema_name' in locals() else 'acd',
            "stats": stats
        }
    )

@router.get("/seances/creer", response_class=HTMLResponse, name="codev_seance_create_form")
async def codev_seance_creer_form(
    request: Request,
    session: Session = Depends(get_shared_session),
    current_user: User = Depends(get_current_user),
    schema_routing_service: SchemaRoutingService = Depends(get_schema_routing_service)
):
    """Formulaire de création d'une séance"""
    codev_access_required(current_user)
    
    # Récupérer et configurer le schéma
    schema_name = get_schema_from_request(request) or 'acd'
    schema_routing_service.set_schema(schema_name)
    
    # Configurer explicitement le search_path
    session.exec(text(f"SET search_path TO {schema_name}, public"))
    session.commit()
    
    # Récupérer les groupes disponibles - SQL direct
    try:
        groupes_query = text(f"SELECT * FROM {schema_name}.groupe_codev ORDER BY nom_groupe")
        groupes_results = session.exec(groupes_query).all()
        groupes = []
        for row in groupes_results:
            if hasattr(row, '_asdict'):
                row_dict = row._asdict()
            elif hasattr(row, '__dict__'):
                row_dict = row.__dict__
            elif isinstance(row, dict):
                row_dict = row
            else:
                row_dict = {key: getattr(row, key) for key in dir(row) if not key.startswith('_')}
            groupe_obj = type('GroupeCodev', (), row_dict)()
            groupes.append(groupe_obj)
    except Exception as e:
        print(f"⚠️ [WARNING] Erreur lors de la récupération des groupes: {e}")
        groupes = []
    
    # Récupérer les utilisateurs animateurs - SQL direct
    try:
        animateurs_query = text(f"""
            SELECT * FROM public."user"
            WHERE role IN ('administrateur', 'coach_externe', 'formateur', 'accompagnateur')
            ORDER BY nom_complet
        """)
        animateurs_results = session.exec(animateurs_query).all()
        animateurs = []
        for row in animateurs_results:
            if hasattr(row, '_asdict'):
                row_dict = row._asdict()
            elif hasattr(row, '__dict__'):
                row_dict = row.__dict__
            elif isinstance(row, dict):
                row_dict = row
            else:
                row_dict = {key: getattr(row, key) for key in dir(row) if not key.startswith('_')}
            animateur_obj = type('User', (), row_dict)()
            animateurs.append(animateur_obj)
    except Exception as e:
        print(f"⚠️ [WARNING] Erreur lors de la récupération des animateurs: {e}")
        animateurs = []
    
    programme_param = request.query_params.get('programme', '').upper()
    
    return templates.TemplateResponse(
        "pages/codev/seance_form.html",
        {
            "request": request,
            "utilisateur": current_user,
            "groupes": groupes,
            "animateurs": animateurs,
            "settings": settings,
            "programme_param": programme_param,
            "schema_name": schema_name
        }
    )

@router.post("/seances/creer", name="codev_seance_create")
async def codev_seance_creer(
    request: Request,
    session: Session = Depends(get_shared_session),
    current_user: User = Depends(get_current_user),
    groupe_id: int = Form(...),
    numero_seance: int = Form(...),
    date_seance: str = Form(...),
    lieu: Optional[str] = Form(None),
    animateur_id: Optional[int] = Form(None),
    duree_minutes: int = Form(180),
    objectifs: Optional[str] = Form(None),
    schema_routing_service: SchemaRoutingService = Depends(get_schema_routing_service)
):
    """Création d'une séance de codéveloppement"""
    codev_access_required(current_user)
    
    # Récupérer et configurer le schéma
    schema_name = get_schema_from_request(request) or 'acd'
    schema_routing_service.set_schema(schema_name)
    
    # Configurer explicitement le search_path
    session.exec(text(f"SET search_path TO {schema_name}, public"))
    session.commit()
    
    try:
        # Convertir la date string en date
        from datetime import datetime, date
        try:
            # Si c'est un datetime string
            if 'T' in date_seance or ' ' in date_seance:
                date_seance_dt = datetime.fromisoformat(date_seance.replace('Z', '+00:00'))
                date_seance_obj = date_seance_dt.date()
            else:
                # Si c'est juste une date
                date_seance_obj = datetime.strptime(date_seance, '%Y-%m-%d').date()
        except Exception as e:
            logger.error(f"Erreur conversion date: {e}")
            raise ValueError(f"Format de date invalide: {date_seance}")
        
        # Créer la séance
        seance = CodevService.create_seance_codev(
            session=session,
            groupe_id=groupe_id,
            numero_seance=numero_seance,
            date_seance=date_seance_obj,
            lieu=lieu,
            animateur_id=animateur_id,
            duree_minutes=duree_minutes,
            schema_name=schema_name
        )
        
        programme_param = request.query_params.get('programme', '').upper()
        redirect_url = f"/codev/seances?success=1&message=Séance créée avec succès"
        if programme_param:
            redirect_url += f"&programme={programme_param}"
        
        return RedirectResponse(url=redirect_url, status_code=303)
        
    except Exception as e:
        logger.error(f"Erreur création séance: {e}")
        programme_param = request.query_params.get('programme', '').upper()
        redirect_url = f"/codev/seances/creer?error=1&message={str(e)}"
        if programme_param:
            redirect_url += f"&programme={programme_param}"
        return RedirectResponse(url=redirect_url, status_code=303)

@router.get("/seances/{seance_id}/presentations/creer", response_class=HTMLResponse, name="codev_presentation_create_form")
async def codev_presentation_create_form(
    seance_id: int,
    request: Request,
    session: Session = Depends(get_shared_session),
    current_user: User = Depends(get_current_user),
    schema_routing_service: SchemaRoutingService = Depends(get_schema_routing_service)
):
    """Formulaire de création d'une présentation"""
    codev_access_required(current_user)
    
    schema_name = get_schema_from_request(request) or 'acd'
    schema_routing_service.set_schema(schema_name)
    session.exec(text(f"SET search_path TO {schema_name}, public"))
    session.commit()
    
    # Récupérer la séance
    seance_query = text(f"""
        SELECT s.*, g.id as groupe_codev_id
        FROM {schema_name}.seance_codev s
        LEFT JOIN {schema_name}.groupe_codev g ON s.groupe_id = g.id
        WHERE s.id = :seance_id
    """)
    seance_result = session.exec(seance_query.bindparams(seance_id=seance_id)).first()
    if not seance_result:
        raise HTTPException(status_code=404, detail="Séance introuvable")
    seance = type('SeanceCodev', (), dict(seance_result._mapping))()
    seance_dict = dict(seance_result._mapping)
    groupe_codev_id = seance_dict.get('groupe_codev_id')
    
    # Récupérer les membres du groupe
    membres_query = text(f"""
        SELECT m.candidat_id,
               c.nom as candidat_nom,
               c.prenom as candidat_prenom
        FROM {schema_name}.membre_groupe_codev m
        LEFT JOIN {schema_name}.candidat c ON m.candidat_id = c.id
        WHERE m.groupe_codev_id = :groupe_id
        ORDER BY c.nom, c.prenom
    """)
    membres_results = session.exec(membres_query.bindparams(groupe_id=groupe_codev_id)).all()
    membres = []
    for row in membres_results:
        membre = type('Membre', (), dict(row._mapping))()
        if getattr(membre, 'candidat_nom', None) or getattr(membre, 'candidat_prenom', None):
            membre.candidat_nom_complet = f"{membre.candidat_prenom or ''} {membre.candidat_nom or ''}".strip()
        membres.append(membre)
    
    # Récupérer le nombre de présentations existantes pour déterminer l'ordre
    ordre_query = text(f"""
        SELECT COALESCE(MAX(ordre_presentation), 0) + 1 as next_ordre
        FROM {schema_name}.presentation_codev
        WHERE seance_id = :seance_id
    """)
    ordre_result = session.exec(ordre_query.bindparams(seance_id=seance_id)).first()
    next_ordre = ordre_result[0] if ordre_result else 1
    
    programme_param = request.query_params.get('programme', '').upper()
    
    return templates.TemplateResponse(
        "pages/codev/presentation_form.html",
        {
            "request": request,
            "utilisateur": current_user,
            "seance": seance,
            "membres": membres,
            "next_ordre": next_ordre,
            "settings": settings,
            "programme_param": programme_param,
            "schema_name": schema_name
        }
    )

@router.post("/seances/{seance_id}/presentations/creer", name="codev_presentation_create")
async def codev_presentation_create(
    seance_id: int,
    request: Request,
    candidat_id: int = Form(...),
    ordre_presentation: int = Form(...),
    probleme_expose: str = Form(...),
    contexte: Optional[str] = Form(None),
    solutions_proposees: Optional[str] = Form(None),
    engagement_candidat: Optional[str] = Form(None),
    delai_engagement: Optional[str] = Form(None),
    programme: Optional[str] = Form(None),
    session: Session = Depends(get_shared_session),
    current_user: User = Depends(get_current_user),
    schema_routing_service: SchemaRoutingService = Depends(get_schema_routing_service)
):
    """Créer une présentation"""
    codev_access_required(current_user)
    
    # Récupérer le programme depuis le formulaire ou la query string
    programme_param = programme or request.query_params.get('programme', '')
    schema_name = get_schema_from_request(request) or (programme_param.lower() if programme_param else 'acd')
    schema_routing_service.set_schema(schema_name)
    session.exec(text(f"SET search_path TO {schema_name}, public"))
    session.commit()
    
    try:
        logger.info(f"Tentative de création de présentation pour séance {seance_id}, candidat {candidat_id}")
        
        # Convertir delai_engagement en date si fourni
        delai_engagement_date = None
        if delai_engagement:
            from datetime import datetime
            try:
                delai_engagement_date = datetime.strptime(delai_engagement, '%Y-%m-%d').date()
            except Exception as date_err:
                logger.warning(f"Erreur conversion date delai_engagement: {date_err}")
        
        # Insérer la présentation
        insert_query = text(f"""
            INSERT INTO {schema_name}.presentation_codev
            (seance_id, candidat_id, ordre_presentation, probleme_expose, contexte, 
             solutions_proposees, engagement_candidat, delai_engagement, statut, cree_le)
            VALUES (:seance_id, :candidat_id, :ordre_presentation, :probleme_expose, :contexte,
                    :solutions_proposees, :engagement_candidat, :delai_engagement, :statut, CURRENT_TIMESTAMP)
            RETURNING *
        """)
        
        presentation_result = session.exec(insert_query.bindparams(
            seance_id=seance_id,
            candidat_id=candidat_id,
            ordre_presentation=ordre_presentation,
            probleme_expose=probleme_expose,
            contexte=contexte,
            solutions_proposees=solutions_proposees,
            engagement_candidat=engagement_candidat,
            delai_engagement=delai_engagement_date,
            statut='en_attente'
        )).first()
        
        if not presentation_result:
            raise ValueError("La présentation n'a pas pu être créée")
        
        session.commit()
        logger.info(f"Présentation créée avec succès: ID {dict(presentation_result._mapping).get('id')}")
        
        programme_param = (programme or request.query_params.get('programme', '')).upper()
        redirect_url = f"/codev/seances/{seance_id}?success=1&action=create_presentation"
        if programme_param:
            redirect_url += f"&programme={programme_param}"
        
        return RedirectResponse(url=redirect_url, status_code=303)
        
    except Exception as e:
        logger.error(f"Erreur création présentation: {e}", exc_info=True)
        session.rollback()
        programme_param = (programme or request.query_params.get('programme', '')).upper()
        import urllib.parse
        error_message = urllib.parse.quote(str(e))
        redirect_url = f"/codev/seances/{seance_id}/presentations/creer?error=1&message={error_message}"
        if programme_param:
            redirect_url += f"&programme={programme_param}"
        return RedirectResponse(url=redirect_url, status_code=303)

@router.get("/presentations/{presentation_id}/modifier", response_class=HTMLResponse, name="codev_presentation_edit_form")
async def codev_presentation_edit_form(
    presentation_id: int,
    request: Request,
    session: Session = Depends(get_shared_session),
    current_user: User = Depends(get_current_user),
    schema_routing_service: SchemaRoutingService = Depends(get_schema_routing_service)
):
    """Formulaire de modification d'une présentation"""
    codev_access_required(current_user)
    
    schema_name = get_schema_from_request(request) or 'acd'
    schema_routing_service.set_schema(schema_name)
    session.exec(text(f"SET search_path TO {schema_name}, public"))
    session.commit()
    
    # Récupérer la présentation
    presentation_query = text(f"""
        SELECT * FROM {schema_name}.presentation_codev
        WHERE id = :presentation_id
    """)
    presentation_result = session.exec(presentation_query.bindparams(presentation_id=presentation_id)).first()
    if not presentation_result:
        raise HTTPException(status_code=404, detail="Présentation introuvable")
    presentation = type('PresentationCodev', (), dict(presentation_result._mapping))()
    
    # Récupérer la séance
    seance_query = text(f"""
        SELECT s.*, g.id as groupe_codev_id
        FROM {schema_name}.seance_codev s
        LEFT JOIN {schema_name}.groupe_codev g ON s.groupe_id = g.id
        WHERE s.id = :seance_id
    """)
    seance_result = session.exec(seance_query.bindparams(seance_id=presentation.seance_id)).first()
    if not seance_result:
        raise HTTPException(status_code=404, detail="Séance introuvable")
    seance = type('SeanceCodev', (), dict(seance_result._mapping))()
    seance_dict = dict(seance_result._mapping)
    groupe_codev_id = seance_dict.get('groupe_codev_id')
    
    # Récupérer les membres du groupe
    membres_query = text(f"""
        SELECT m.candidat_id,
               c.nom as candidat_nom,
               c.prenom as candidat_prenom
        FROM {schema_name}.membre_groupe_codev m
        LEFT JOIN {schema_name}.candidat c ON m.candidat_id = c.id
        WHERE m.groupe_codev_id = :groupe_id
        ORDER BY c.nom, c.prenom
    """)
    membres_results = session.exec(membres_query.bindparams(groupe_id=groupe_codev_id)).all()
    membres = []
    for row in membres_results:
        membre = type('Membre', (), dict(row._mapping))()
        if getattr(membre, 'candidat_nom', None) or getattr(membre, 'candidat_prenom', None):
            membre.candidat_nom_complet = f"{membre.candidat_prenom or ''} {membre.candidat_nom or ''}".strip()
        membres.append(membre)
    
    programme_param = request.query_params.get('programme', '').upper()
    
    return templates.TemplateResponse(
        "pages/codev/presentation_form.html",
        {
            "request": request,
            "utilisateur": current_user,
            "seance": seance,
            "presentation": presentation,
            "membres": membres,
            "is_edit": True,
            "settings": settings,
            "programme_param": programme_param,
            "schema_name": schema_name
        }
    )

@router.post("/presentations/{presentation_id}/modifier", name="codev_presentation_update")
async def codev_presentation_update(
    presentation_id: int,
    request: Request,
    candidat_id: int = Form(...),
    ordre_presentation: int = Form(...),
    probleme_expose: str = Form(...),
    contexte: Optional[str] = Form(None),
    solutions_proposees: Optional[str] = Form(None),
    engagement_candidat: Optional[str] = Form(None),
    delai_engagement: Optional[str] = Form(None),
    programme: Optional[str] = Form(None),
    session: Session = Depends(get_shared_session),
    current_user: User = Depends(get_current_user),
    schema_routing_service: SchemaRoutingService = Depends(get_schema_routing_service)
):
    """Modifier une présentation"""
    codev_access_required(current_user)
    
    programme_param = programme or request.query_params.get('programme', '')
    schema_name = get_schema_from_request(request) or (programme_param.lower() if programme_param else 'acd')
    schema_routing_service.set_schema(schema_name)
    session.exec(text(f"SET search_path TO {schema_name}, public"))
    session.commit()
    
    try:
        logger.info(f"Tentative de modification de présentation {presentation_id}")
        
        # Vérifier que la présentation existe
        check_query = text(f"SELECT seance_id FROM {schema_name}.presentation_codev WHERE id = :presentation_id")
        check_result = session.exec(check_query.bindparams(presentation_id=presentation_id)).first()
        if not check_result:
            raise ValueError("Présentation introuvable")
        seance_id = dict(check_result._mapping)['seance_id']
        
        # Convertir delai_engagement en date si fourni
        delai_engagement_date = None
        if delai_engagement:
            from datetime import datetime
            try:
                delai_engagement_date = datetime.strptime(delai_engagement, '%Y-%m-%d').date()
            except Exception as date_err:
                logger.warning(f"Erreur conversion date delai_engagement: {date_err}")
        
        # Mettre à jour la présentation
        update_query = text(f"""
            UPDATE {schema_name}.presentation_codev
            SET candidat_id = :candidat_id,
                ordre_presentation = :ordre_presentation,
                probleme_expose = :probleme_expose,
                contexte = :contexte,
                solutions_proposees = :solutions_proposees,
                engagement_candidat = :engagement_candidat,
                delai_engagement = :delai_engagement
            WHERE id = :presentation_id
            RETURNING *
        """)
        
        update_result = session.exec(update_query.bindparams(
            presentation_id=presentation_id,
            candidat_id=candidat_id,
            ordre_presentation=ordre_presentation,
            probleme_expose=probleme_expose,
            contexte=contexte,
            solutions_proposees=solutions_proposees,
            engagement_candidat=engagement_candidat,
            delai_engagement=delai_engagement_date
        )).first()
        
        if not update_result:
            raise ValueError("La présentation n'a pas pu être modifiée")
        
        session.commit()
        logger.info(f"Présentation {presentation_id} modifiée avec succès")
        
        programme_param = (programme or request.query_params.get('programme', '')).upper()
        redirect_url = f"/codev/presentations/{presentation_id}?success=1&action=update_presentation"
        if programme_param:
            redirect_url += f"&programme={programme_param}"
        
        return RedirectResponse(url=redirect_url, status_code=303)
        
    except Exception as e:
        logger.error(f"Erreur modification présentation: {e}", exc_info=True)
        session.rollback()
        programme_param = (programme or request.query_params.get('programme', '')).upper()
        import urllib.parse
        error_message = urllib.parse.quote(str(e))
        redirect_url = f"/codev/presentations/{presentation_id}/modifier?error=1&message={error_message}"
        if programme_param:
            redirect_url += f"&programme={programme_param}"
        return RedirectResponse(url=redirect_url, status_code=303)

@router.post("/seances/{seance_id}/contributions/ajouter", name="codev_seance_add_contribution")
async def codev_seance_add_contribution(
    seance_id: int,
    request: Request,
    contributeur_id: int = Form(...),
    type_contribution: str = Form(...),
    contenu: str = Form(...),
    programme: Optional[str] = Form(None),
    session: Session = Depends(get_shared_session),
    current_user: User = Depends(get_current_user),
    schema_routing_service: SchemaRoutingService = Depends(get_schema_routing_service)
):
    """Ajouter une contribution à une séance"""
    codev_access_required(current_user)
    
    # Récupérer le programme depuis le formulaire ou la query string
    programme_param = programme or request.query_params.get('programme', '')
    schema_name = get_schema_from_request(request) or (programme_param.lower() if programme_param else 'acd')
    schema_routing_service.set_schema(schema_name)
    session.exec(text(f"SET search_path TO {schema_name}, public"))
    session.commit()
    
    try:
        logger.info(f"Tentative d'ajout de contribution pour séance {seance_id}, contributeur {contributeur_id}")
        
        # Vérifier que la séance existe
        seance_query = text(f"SELECT id FROM {schema_name}.seance_codev WHERE id = :seance_id")
        seance_result = session.exec(seance_query.bindparams(seance_id=seance_id)).first()
        if not seance_result:
            raise ValueError("Séance introuvable")
        
        # Déterminer l'ordre de la contribution
        ordre_query = text(f"""
            SELECT COALESCE(MAX(ordre_contribution), 0) + 1 as next_ordre
            FROM {schema_name}.contribution_codev
            WHERE seance_id = :seance_id
        """)
        ordre_result = session.exec(ordre_query.bindparams(seance_id=seance_id)).first()
        next_ordre = ordre_result[0] if ordre_result else 1
        
        # Insérer la contribution
        insert_query = text(f"""
            INSERT INTO {schema_name}.contribution_codev
            (seance_id, contributeur_id, type_contribution, contenu, ordre_contribution, cree_le)
            VALUES (:seance_id, :contributeur_id, :type_contribution, :contenu, :ordre_contribution, CURRENT_TIMESTAMP)
            RETURNING *
        """)
        
        contribution_result = session.exec(insert_query.bindparams(
            seance_id=seance_id,
            contributeur_id=contributeur_id,
            type_contribution=type_contribution,
            contenu=contenu,
            ordre_contribution=next_ordre
        )).first()
        
        if not contribution_result:
            raise ValueError("La contribution n'a pas pu être créée")
        
        session.commit()
        logger.info(f"Contribution créée avec succès: ID {dict(contribution_result._mapping).get('id')}")
        
        programme_param = (programme or request.query_params.get('programme', '')).upper()
        redirect_url = f"/codev/seances/{seance_id}?success=1&action=add_contribution"
        if programme_param:
            redirect_url += f"&programme={programme_param}"
        
        return RedirectResponse(url=redirect_url, status_code=303)
        
    except Exception as e:
        logger.error(f"Erreur ajout contribution: {e}", exc_info=True)
        session.rollback()
        programme_param = (programme or request.query_params.get('programme', '')).upper()
        import urllib.parse
        error_message = urllib.parse.quote(str(e))
        redirect_url = f"/codev/seances/{seance_id}?error=1&message={error_message}"
        if programme_param:
            redirect_url += f"&programme={programme_param}"
        return RedirectResponse(url=redirect_url, status_code=303)

@router.post("/presentations/{presentation_id}/contributions/ajouter", name="codev_presentation_add_contribution")
async def codev_presentation_add_contribution(
    presentation_id: int,
    request: Request,
    contributeur_id: int = Form(...),
    type_contribution: str = Form(...),
    contenu: str = Form(...),
    programme: Optional[str] = Form(None),
    session: Session = Depends(get_shared_session),
    current_user: User = Depends(get_current_user),
    schema_routing_service: SchemaRoutingService = Depends(get_schema_routing_service)
):
    """Ajouter une contribution à une présentation (redirige vers la séance)"""
    codev_access_required(current_user)
    
    programme_param = programme or request.query_params.get('programme', '')
    schema_name = get_schema_from_request(request) or (programme_param.lower() if programme_param else 'acd')
    schema_routing_service.set_schema(schema_name)
    session.exec(text(f"SET search_path TO {schema_name}, public"))
    session.commit()
    
    try:
        # Récupérer la présentation pour obtenir seance_id
        presentation_query = text(f"SELECT seance_id FROM {schema_name}.presentation_codev WHERE id = :presentation_id")
        presentation_result = session.exec(presentation_query.bindparams(presentation_id=presentation_id)).first()
        if not presentation_result:
            raise ValueError("Présentation introuvable")
        seance_id = dict(presentation_result._mapping)['seance_id']
        
        # Rediriger vers la route de séance
        redirect_url = f"/codev/seances/{seance_id}/contributions/ajouter"
        if programme_param:
            redirect_url += f"?programme={programme_param}"
        # Ajouter les paramètres du formulaire
        import urllib.parse
        params = {
            'contributeur_id': contributeur_id,
            'type_contribution': type_contribution,
            'contenu': contenu
        }
        if programme_param:
            params['programme'] = programme_param
        redirect_url += '&' + urllib.parse.urlencode(params)
        
        return RedirectResponse(url=redirect_url, status_code=303)
        
    except Exception as e:
        logger.error(f"Erreur redirection contribution: {e}", exc_info=True)
        programme_param = (programme or request.query_params.get('programme', '')).upper()
        import urllib.parse
        error_message = urllib.parse.quote(str(e))
        redirect_url = f"/codev/presentations/{presentation_id}?error=1&message={error_message}"
        if programme_param:
            redirect_url += f"&programme={programme_param}"
        return RedirectResponse(url=redirect_url, status_code=303)

@router.post("/seances/{seance_id}/contributions/{contribution_id}/supprimer", name="codev_seance_remove_contribution")
async def codev_seance_remove_contribution(
    seance_id: int,
    contribution_id: int,
    request: Request,
    programme: Optional[str] = Form(None),
    session: Session = Depends(get_shared_session),
    current_user: User = Depends(get_current_user),
    schema_routing_service: SchemaRoutingService = Depends(get_schema_routing_service)
):
    """Supprimer une contribution d'une séance"""
    codev_access_required(current_user)
    
    programme_param = programme or request.query_params.get('programme', '')
    schema_name = get_schema_from_request(request) or (programme_param.lower() if programme_param else 'acd')
    schema_routing_service.set_schema(schema_name)
    session.exec(text(f"SET search_path TO {schema_name}, public"))
    session.commit()
    
    try:
        logger.info(f"Tentative de suppression de contribution {contribution_id} de séance {seance_id}")
        
        # Vérifier que la contribution existe et appartient à la séance
        check_query = text(f"""
            SELECT id FROM {schema_name}.contribution_codev
            WHERE id = :contribution_id AND seance_id = :seance_id
        """)
        check_result = session.exec(check_query.bindparams(contribution_id=contribution_id, seance_id=seance_id)).first()
        
        if not check_result:
            raise ValueError("Contribution introuvable ou n'appartient pas à cette séance")
        
        # Supprimer la contribution
        delete_query = text(f"""
            DELETE FROM {schema_name}.contribution_codev
            WHERE id = :contribution_id AND seance_id = :seance_id
        """)
        result = session.exec(delete_query.bindparams(contribution_id=contribution_id, seance_id=seance_id))
        session.commit()
        
        if result.rowcount == 0:
            raise ValueError("Aucune contribution n'a été supprimée")
        
        logger.info(f"Contribution {contribution_id} supprimée avec succès")
        
        programme_param = (programme or request.query_params.get('programme', '')).upper()
        redirect_url = f"/codev/seances/{seance_id}?success=1&action=remove_contribution"
        if programme_param:
            redirect_url += f"&programme={programme_param}"
        
        return RedirectResponse(url=redirect_url, status_code=303)
        
    except Exception as e:
        logger.error(f"Erreur suppression contribution: {e}", exc_info=True)
        session.rollback()
        programme_param = (programme or request.query_params.get('programme', '')).upper()
        import urllib.parse
        error_message = urllib.parse.quote(str(e))
        redirect_url = f"/codev/seances/{seance_id}?error=1&message={error_message}"
        if programme_param:
            redirect_url += f"&programme={programme_param}"
        return RedirectResponse(url=redirect_url, status_code=303)

@router.post("/presentations/{presentation_id}/contributions/{contribution_id}/supprimer", name="codev_presentation_remove_contribution")
async def codev_presentation_remove_contribution(
    presentation_id: int,
    contribution_id: int,
    request: Request,
    programme: Optional[str] = Form(None),
    session: Session = Depends(get_shared_session),
    current_user: User = Depends(get_current_user),
    schema_routing_service: SchemaRoutingService = Depends(get_schema_routing_service)
):
    """Supprimer une contribution d'une présentation (redirige vers la séance)"""
    codev_access_required(current_user)
    
    programme_param = programme or request.query_params.get('programme', '')
    schema_name = get_schema_from_request(request) or (programme_param.lower() if programme_param else 'acd')
    schema_routing_service.set_schema(schema_name)
    session.exec(text(f"SET search_path TO {schema_name}, public"))
    session.commit()
    
    try:
        # Récupérer la présentation pour obtenir seance_id
        presentation_query = text(f"SELECT seance_id FROM {schema_name}.presentation_codev WHERE id = :presentation_id")
        presentation_result = session.exec(presentation_query.bindparams(presentation_id=presentation_id)).first()
        if not presentation_result:
            raise ValueError("Présentation introuvable")
        seance_id = dict(presentation_result._mapping)['seance_id']
        
        # Rediriger vers la route de séance
        redirect_url = f"/codev/seances/{seance_id}/contributions/{contribution_id}/supprimer"
        if programme_param:
            redirect_url += f"?programme={programme_param}"
        
        return RedirectResponse(url=redirect_url, status_code=303)
        
    except Exception as e:
        logger.error(f"Erreur redirection suppression contribution: {e}", exc_info=True)
        programme_param = (programme or request.query_params.get('programme', '')).upper()
        import urllib.parse
        error_message = urllib.parse.quote(str(e))
        redirect_url = f"/codev/presentations/{presentation_id}?error=1&message={error_message}"
        if programme_param:
            redirect_url += f"&programme={programme_param}"
        return RedirectResponse(url=redirect_url, status_code=303)

@router.get("/presentations/{presentation_id}", response_class=HTMLResponse, name="codev_presentation_detail")
async def codev_presentation_detail(
    presentation_id: int,
    request: Request,
    session: Session = Depends(get_shared_session),
    current_user: User = Depends(get_current_user),
    schema_routing_service: SchemaRoutingService = Depends(get_schema_routing_service)
):
    """Détail d'une présentation de codéveloppement"""
    codev_access_required(current_user)
    
    # Récupérer et configurer le schéma
    schema_name = get_schema_from_request(request) or 'acd'
    schema_routing_service.set_schema(schema_name)
    
    # Configurer explicitement le search_path
    session.exec(text(f"SET search_path TO {schema_name}, public"))
    session.commit()
    
    # Récupérer la présentation avec SQL direct
    presentation_query = text(f"""
        SELECT * FROM {schema_name}.presentation_codev
        WHERE id = :presentation_id
    """)
    presentation_result = session.exec(presentation_query.bindparams(presentation_id=presentation_id)).first()
    if not presentation_result:
        raise HTTPException(status_code=404, detail="Présentation introuvable")
    presentation = type('PresentationCodev', (), dict(presentation_result._mapping))()
    
    # Récupérer la séance associée
    seance_query = text(f"""
        SELECT s.*, 
               g.nom_groupe as groupe_nom,
               g.cycle_id as groupe_cycle_id,
               c.nom as cycle_nom
        FROM {schema_name}.seance_codev s
        LEFT JOIN {schema_name}.groupe_codev g ON s.groupe_id = g.id
        LEFT JOIN {schema_name}.cycle_codev c ON g.cycle_id = c.id
        WHERE s.id = :seance_id
    """)
    seance_result = session.exec(seance_query.bindparams(seance_id=presentation.seance_id)).first()
    if not seance_result:
        raise HTTPException(status_code=404, detail="Séance introuvable")
    seance = type('SeanceCodev', (), dict(seance_result._mapping))()
    
    # Récupérer le candidat avec statut VALIDE
    candidat_query = text(f"SELECT * FROM {schema_name}.candidat WHERE id = :candidat_id AND statut = 'VALIDE'")
    candidat_result = session.exec(candidat_query.bindparams(candidat_id=presentation.candidat_id)).first()
    candidat = None
    if candidat_result:
        candidat = type('Candidat', (), dict(candidat_result._mapping))()
    
    # Les contributions sont maintenant liées à la séance, pas à la présentation
    # Pas besoin de les récupérer ici
    
    programme_param = request.query_params.get('programme', '').upper()
    
    return templates.TemplateResponse(
        "pages/codev/presentation_detail.html",
        {
            "request": request,
            "utilisateur": current_user,
            "presentation": presentation,
            "seance": seance,
            "candidat": candidat,
            "settings": settings,
            "programme_param": programme_param,
            "schema_name": schema_name
        }
    )

# ===== ROUTES API =====

@router.get("/api/codev/cycles", response_model=List[CycleCodevResponse], name="api_codev_cycles")
async def api_cycles(
    session: Session = Depends(get_shared_session),
    current_user: User = Depends(get_current_user),
    statut: Optional[StatutCycleCodev] = Query(None)
):
    """API: Liste des cycles de codéveloppement"""
    codev_access_required(current_user)
    
    stmt = select(CycleCodev)
    if statut:
        stmt = stmt.where(CycleCodev.statut == statut)
    
    cycles = session.exec(stmt.order_by(CycleCodev.date_debut.desc())).all()
    return cycles

@router.post("/api/codev/cycles", response_model=CycleCodevResponse, name="api_codev_create_cycle")
async def api_create_cycle(
    cycle_data: CycleCodevCreate,
    request: Request,
    session: Session = Depends(get_shared_session),
    current_user: User = Depends(get_current_user),
    schema_routing_service: SchemaRoutingService = Depends(get_schema_routing_service)
):
    """API: Création d'un cycle de codéveloppement"""
    codev_access_required(current_user)
    
    # Récupérer et configurer le schéma
    schema_name = get_schema_from_request(request) or 'acd'
    schema_routing_service.set_schema(schema_name)
    
    cycle = CodevService.create_cycle_codev(
        session=session,
        nom=cycle_data.nom,
        programme_id=cycle_data.programme_id,
        promotion_id=cycle_data.promotion_id,
        date_debut=cycle_data.date_debut,
        date_fin=cycle_data.date_fin,
        nombre_seances=cycle_data.nombre_seances_prevues,
        animateur_principal_id=cycle_data.animateur_principal_id,
        schema_name=schema_name
    )
    
    return cycle

@router.get("/api/codev/cycles/{cycle_id}/statistiques", response_model=StatistiquesCycleCodev, name="api_codev_cycle_stats")
async def api_cycle_stats(
    cycle_id: int,
    session: Session = Depends(get_shared_session),
    current_user: User = Depends(get_current_user)
):
    """API: Statistiques d'un cycle de codéveloppement"""
    codev_access_required(current_user)
    
    stats = CodevService.get_statistiques_cycle(session, cycle_id)
    return stats

@router.post("/api/codev/seances/{seance_id}/planifier", name="api_codev_planifier_seance")
async def api_planifier_seance(
    seance_id: int,
    planification: PlanificationSeance,
    session: Session = Depends(get_shared_session),
    current_user: User = Depends(get_current_user)
):
    """API: Planifier les présentations d'une séance"""
    codev_access_required(current_user)
    
    presentations = CodevService.planifier_presentations_seance(
        session=session,
        seance_id=seance_id,
        candidats_ids=planification.candidats_ids,
        ordre_presentations=planification.ordre_presentations
    )
    
    return {"message": f"{len(presentations)} présentations planifiées"}

@router.post("/api/codev/presentations/{presentation_id}/engagement", name="api_codev_prendre_engagement")
async def api_prendre_engagement(
    presentation_id: int,
    engagement: EngagementCandidat,
    session: Session = Depends(get_shared_session),
    current_user: User = Depends(get_current_user)
):
    """API: Prendre un engagement pour une présentation"""
    codev_access_required(current_user)
    
    presentation = CodevService.marquer_engagement_pris(
        session=session,
        presentation_id=presentation_id,
        engagement=engagement.engagement,
        delai_engagement=engagement.delai_engagement
    )
    
    return {"message": "Engagement pris avec succès"}

@router.post("/api/codev/presentations/{presentation_id}/retour", name="api_codev_ajouter_retour")
async def api_ajouter_retour(
    presentation_id: int,
    retour: RetourExperience,
    session: Session = Depends(get_shared_session),
    current_user: User = Depends(get_current_user)
):
    """API: Ajouter un retour d'expérience"""
    codev_access_required(current_user)
    
    presentation = CodevService.ajouter_retour_experience(
        session=session,
        presentation_id=presentation_id,
        notes_candidat=retour.notes_candidat
    )
    
    return {"message": "Retour d'expérience ajouté avec succès"}

import logging
logger = logging.getLogger(__name__)
