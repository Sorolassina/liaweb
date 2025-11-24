"""
Service de gestion du Codéveloppement
"""
from typing import List, Optional, Dict, Any
from sqlmodel import Session, select, func, and_, or_, text
from datetime import datetime, timezone, date, timedelta
import logging
from ..core.program_schema_integration import safe_count_query, table_exists_anywhere

from ..models.codev import (
    SeanceCodev, PresentationCodev, ContributionCodev, ParticipationSeance,
    CycleCodev, GroupeCodev, MembreGroupeCodev
)
from ..models.base import User, Programme, Promotion, Groupe
from ..models.enums import (
    StatutSeanceCodev, StatutPresentation, TypeContribution,
    StatutCycleCodev, StatutGroupeCodev, StatutMembreGroupe, StatutPresence
)
from ..schemas import (
    CycleCodevCreate, CycleCodevUpdate,
    GroupeCodevCreate, SeanceCodevCreate, 
    PresentationCodevCreate, ContributionCodevCreate,
    MembreGroupeCodevCreate
)

logger = logging.getLogger(__name__)

def extract_count_value(result):
    """Extrait la valeur d'un résultat COUNT(*) qui peut être un tuple ou une valeur simple"""
    if result is None:
        return 0
    if isinstance(result, tuple):
        return result[0] if result else 0
    if hasattr(result, '_mapping'):  # Handle SQLAlchemy Row objects
        return result._mapping[next(iter(result._mapping))] if result._mapping else 0
    if hasattr(result, '__iter__') and not isinstance(result, str):
        try:
            return next(iter(result)) if result else 0
        except:
            return 0
    return result

class CodevService:
    """Service de gestion du codéveloppement"""
    
    @staticmethod
    def create_cycle_codev(
        session: Session, 
        nom: str,
        programme_id: int,
        promotion_id: Optional[int] = None,
        date_debut: date = None,
        date_fin: date = None,
        nombre_seances: int = 6,
        animateur_principal_id: Optional[int] = None,
        schema_name: str = 'acd'
    ) -> Dict[str, Any]:
        """Crée un nouveau cycle de codéveloppement - SQL direct"""
        
        # Configurer le search_path
        session.exec(text(f"SET search_path TO {schema_name}, public"))
        session.commit()
        
        if not date_debut:
            date_debut = date.today()
        if not date_fin:
            date_fin = date_debut + timedelta(weeks=nombre_seances * 2)  # 1 séance toutes les 2 semaines
        
        # Vérifier que le programme existe dans public.programme
        check_programme_query = text("SELECT id FROM public.programme WHERE id = :programme_id AND actif = true")
        programme_exists = session.exec(check_programme_query.bindparams(programme_id=programme_id)).first()
        if not programme_exists:
            raise ValueError(f"Programme ID {programme_id} n'existe pas dans public.programme")
        
        # Vérifier que la promotion existe dans le schéma du programme si promotion_id est fourni
        if promotion_id is not None:
            logger.info(f"🔍 [DEBUG] Vérification promotion_id={promotion_id} dans {schema_name}.promotion")
            check_promotion_query = text(f"SELECT id FROM {schema_name}.promotion WHERE id = :promotion_id AND actif = true")
            promotion_exists = session.exec(check_promotion_query.bindparams(promotion_id=promotion_id)).first()
            logger.info(f"🔍 [DEBUG] Résultat vérification promotion: {promotion_exists}")
            if not promotion_exists:
                logger.warning(f"⚠️ Promotion ID {promotion_id} n'existe pas dans {schema_name}.promotion, mise à NULL")
                promotion_id = None
            else:
                logger.info(f"✅ Promotion ID {promotion_id} trouvée dans {schema_name}.promotion")
        
        # Insertion SQL directe
        insert_query = text(f"""
            INSERT INTO {schema_name}.cycle_codev 
            (nom, programme_id, promotion_id, date_debut, date_fin, nombre_seances_prevues, 
             animateur_principal_id, statut, cree_le)
            VALUES (:nom, :programme_id, :promotion_id, :date_debut, :date_fin, :nombre_seances, 
                    :animateur_principal_id, :statut, CURRENT_TIMESTAMP)
            RETURNING *
        """)
        
        logger.info(f"🔍 [DEBUG] Valeurs avant insertion:")
        logger.info(f"  - promotion_id: {promotion_id}")
        logger.info(f"  - programme_id: {programme_id}")
        
        cycle_result = session.exec(insert_query.bindparams(
            nom=nom,
            programme_id=programme_id,
            promotion_id=promotion_id,
            date_debut=date_debut,
            date_fin=date_fin,
            nombre_seances=nombre_seances,
            animateur_principal_id=animateur_principal_id,
            statut=StatutCycleCodev.PLANIFIE.value
        )).first()
        
        session.commit()
        
        # Convertir le Row object en dictionnaire
        cycle_dict = dict(cycle_result._mapping) if cycle_result else {}
        logger.info(f"Cycle de codéveloppement créé: {nom} (ID: {cycle_dict.get('id')})")
        return cycle_dict
    
    @staticmethod
    def create_groupe_codev(
        session: Session,
        cycle_id: int,
        groupe_id: int,
        nom_groupe: str,
        animateur_id: Optional[int] = None,
        capacite_max: int = 12
    ) -> GroupeCodev:
        """Crée un groupe de codéveloppement dans un cycle"""
        
        groupe_codev = GroupeCodev(
            cycle_id=cycle_id,
            groupe_id=groupe_id,
            nom_groupe=nom_groupe,
            animateur_id=animateur_id,
            capacite_max=capacite_max,
            statut=StatutGroupeCodev.EN_CONSTITUTION.value
        )
        
        session.add(groupe_codev)
        session.commit()
        session.refresh(groupe_codev)
        
        logger.info(f"Groupe de codéveloppement créé: {nom_groupe} (ID: {groupe_codev.id})")
        return groupe_codev
    
    @staticmethod
    def add_membre_groupe(
        session: Session,
        groupe_codev_id: int,
        candidat_id: int,
        role_special: Optional[str] = None,
        schema_name: str = 'acd'
    ) -> Dict[str, Any]:
        """Ajoute un candidat à un groupe de codéveloppement - SQL direct"""
        
        from datetime import datetime, timezone
        
        # Configurer le search_path
        session.exec(text(f"SET search_path TO {schema_name}, public"))
        session.commit()
        
        # Vérifier que le groupe existe et récupérer sa capacité
        groupe_query = text(f"SELECT * FROM {schema_name}.groupe_codev WHERE id = :groupe_id")
        groupe_result = session.exec(groupe_query.bindparams(groupe_id=groupe_codev_id)).first()
        if not groupe_result:
            raise ValueError("Groupe de codéveloppement introuvable")
        groupe = dict(groupe_result._mapping)
        
        # Vérifier que le candidat existe avec statut VALIDE
        candidat_query = text(f"SELECT id FROM {schema_name}.candidat WHERE id = :candidat_id AND statut = 'VALIDE'")
        candidat_result = session.exec(candidat_query.bindparams(candidat_id=candidat_id)).first()
        if not candidat_result:
            raise ValueError("Candidat introuvable ou non validé")
        
        # Compter les membres du groupe (tous les membres, sans filtre de statut)
        membres_count_query = text(f"""
            SELECT COUNT(*) FROM {schema_name}.membre_groupe_codev
            WHERE groupe_codev_id = :groupe_id
        """)
        membres_count_result = session.exec(membres_count_query.bindparams(groupe_id=groupe_codev_id)).one()
        membres_count = extract_count_value(membres_count_result)
        
        if membres_count >= groupe.get('capacite_max', 12):
            raise ValueError("Le groupe est complet")
        
        # Vérifier que le candidat n'est pas déjà dans le groupe (sans filtre de statut)
        existing_query = text(f"""
            SELECT id FROM {schema_name}.membre_groupe_codev
            WHERE groupe_codev_id = :groupe_id AND candidat_id = :candidat_id
        """)
        existing = session.exec(existing_query.bindparams(groupe_id=groupe_codev_id, candidat_id=candidat_id)).first()
        
        if existing:
            raise ValueError("Le candidat est déjà dans ce groupe")
        
        # Insérer le membre avec SQL direct
        insert_query = text(f"""
            INSERT INTO {schema_name}.membre_groupe_codev
            (groupe_codev_id, candidat_id, date_integration, statut, role_special, notes_integration)
            VALUES (:groupe_codev_id, :candidat_id, :date_integration, :statut, :role_special, :notes_integration)
            RETURNING *
        """)
        
        membre_result = session.exec(insert_query.bindparams(
            groupe_codev_id=groupe_codev_id,
            candidat_id=candidat_id,
            date_integration=datetime.now(timezone.utc),
            statut='actif',
            role_special=role_special,
            notes_integration=None
        )).first()
        
        session.commit()
        
        membre = dict(membre_result._mapping) if membre_result else {}
        logger.info(f"Candidat {candidat_id} ajouté au groupe {groupe_codev_id}")
        return membre
    
    @staticmethod
    @staticmethod
    def create_seance_codev(
        session: Session,
        groupe_id: int,
        numero_seance: int,
        date_seance: date,
        lieu: Optional[str] = None,
        animateur_id: Optional[int] = None,
        duree_minutes: int = 180,
        schema_name: str = 'acd'
    ) -> Dict[str, Any]:
        """Crée une séance de codéveloppement - SQL direct"""
        
        # Configurer le search_path
        session.exec(text(f"SET search_path TO {schema_name}, public"))
        session.commit()
        
        # Insérer la séance
        insert_query = text(f"""
            INSERT INTO {schema_name}.seance_codev 
            (groupe_id, numero_seance, date_seance, lieu, animateur_id, duree_minutes, statut, cree_le)
            VALUES (:groupe_id, :numero_seance, :date_seance, :lieu, :animateur_id, :duree_minutes, :statut, :cree_le)
            RETURNING id
        """)
        
        result = session.exec(insert_query.bindparams(
            groupe_id=groupe_id,
            numero_seance=numero_seance,
            date_seance=date_seance,
            lieu=lieu,
            animateur_id=animateur_id,
            duree_minutes=duree_minutes,
            statut=StatutSeanceCodev.PLANIFIEE.value,
            cree_le=datetime.now(timezone.utc)
        )).one()
        
        session.commit()
        
        seance_id = result if isinstance(result, int) else result[0] if isinstance(result, tuple) else result.id
        
        logger.info(f"Séance {numero_seance} créée pour le groupe {groupe_id} (ID: {seance_id})")
        
        # Récupérer la séance créée
        select_query = text(f"SELECT * FROM {schema_name}.seance_codev WHERE id = :seance_id")
        seance_result = session.exec(select_query.bindparams(seance_id=seance_id)).one()
        
        if hasattr(seance_result, '_asdict'):
            return seance_result._asdict()
        elif hasattr(seance_result, '__dict__'):
            return seance_result.__dict__
        elif isinstance(seance_result, dict):
            return seance_result
        else:
            return {key: getattr(seance_result, key) for key in dir(seance_result) if not key.startswith('_')}
    
    @staticmethod
    def planifier_presentations_seance(
        session: Session,
        seance_id: int,
        candidats_ids: List[int],
        ordre_presentations: Optional[List[int]] = None
    ) -> List[PresentationCodev]:
        """Planifie les présentations pour une séance"""
        
        seance = session.get(SeanceCodev, seance_id)
        if not seance:
            raise ValueError("Séance introuvable")
        
        presentations = []
        
        # Si pas d'ordre spécifié, utiliser l'ordre de la liste
        if not ordre_presentations:
            ordre_presentations = list(range(1, len(candidats_ids) + 1))
        
        for i, candidat_id in enumerate(candidats_ids):
            presentation = PresentationCodev(
                seance_id=seance_id,
                candidat_id=candidat_id,
                ordre_presentation=ordre_presentations[i],
                probleme_expose="",  # À remplir par le candidat
                statut=StatutPresentation.EN_ATTENTE.value
            )
            session.add(presentation)
            presentations.append(presentation)
        
        session.commit()
        
        for presentation in presentations:
            session.refresh(presentation)
        
        logger.info(f"{len(presentations)} présentations planifiées pour la séance {seance_id}")
        return presentations
    
    @staticmethod
    def add_contribution(
        session: Session,
        presentation_id: int,
        contributeur_id: int,
        type_contribution: TypeContribution,
        contenu: str,
        ordre_contribution: Optional[int] = None
    ) -> ContributionCodev:
        """Ajoute une contribution à une présentation"""
        
        # Déterminer l'ordre automatiquement si non spécifié
        if not ordre_contribution:
            max_ordre = session.exec(
                select(func.max(ContributionCodev.ordre_contribution))
                .where(ContributionCodev.presentation_id == presentation_id)
            ).one() or 0
            ordre_contribution = max_ordre + 1
        
        contribution = ContributionCodev(
            presentation_id=presentation_id,
            contributeur_id=contributeur_id,
            type_contribution=type_contribution,
            contenu=contenu,
            ordre_contribution=ordre_contribution
        )
        
        session.add(contribution)
        session.commit()
        session.refresh(contribution)
        
        logger.info(f"Contribution ajoutée à la présentation {presentation_id}")
        return contribution
    
    @staticmethod
    def get_statistiques_cycle(session: Session, cycle_id: int, schema_name: str = 'acd') -> Dict[str, Any]:
        """Récupère les statistiques d'un cycle de codéveloppement"""
        
        # Configurer le search_path
        session.exec(text(f"SET search_path TO {schema_name}, public"))
        session.commit()
        
        # Récupérer le cycle - SQL direct
        cycle_query = text(f"SELECT * FROM {schema_name}.cycle_codev WHERE id = :cycle_id")
        cycle_result = session.exec(cycle_query.bindparams(cycle_id=cycle_id)).first()
        if not cycle_result:
            return {}
        
        cycle = type('CycleCodev', (), dict(cycle_result._mapping))()
        
        # Nombre de groupes - SQL direct
        try:
            nb_groupes_query = text(f"SELECT COUNT(*) FROM {schema_name}.groupe_codev WHERE cycle_id = :cycle_id")
            nb_groupes_result = session.exec(nb_groupes_query.bindparams(cycle_id=cycle_id)).one()
            nb_groupes = extract_count_value(nb_groupes_result)
        except Exception as e:
            logger.warning(f"Erreur lors du comptage des groupes: {e}")
            nb_groupes = 0
        
        # Nombre total de membres - SQL direct
        try:
            nb_membres_query = text(f"""
                SELECT COUNT(*) FROM {schema_name}.membre_groupe_codev mgc
                INNER JOIN {schema_name}.groupe_codev gc ON mgc.groupe_codev_id = gc.id
                WHERE gc.cycle_id = :cycle_id
            """)
            nb_membres_result = session.exec(nb_membres_query.bindparams(cycle_id=cycle_id)).one()
            nb_membres = extract_count_value(nb_membres_result)
        except Exception as e:
            logger.warning(f"Erreur lors du comptage des membres du cycle: {e}")
            nb_membres = 0
        
        # Nombre de séances réalisées - SQL direct
        try:
            nb_seances_query = text(f"""
                SELECT COUNT(*) FROM {schema_name}.seance_codev s
                INNER JOIN {schema_name}.groupe_codev gc ON s.groupe_id = gc.groupe_id
                WHERE gc.cycle_id = :cycle_id
                AND s.statut = :statut
            """)
            nb_seances_result = session.exec(nb_seances_query.bindparams(
                cycle_id=cycle_id,
                statut=StatutSeanceCodev.TERMINEE.value
            )).one()
            nb_seances = extract_count_value(nb_seances_result)
        except Exception as e:
            logger.warning(f"Erreur lors du comptage des séances: {e}")
            nb_seances = 0
        
        # Nombre de présentations terminées - SQL direct
        try:
            nb_presentations_query = text(f"""
                SELECT COUNT(*) FROM {schema_name}.presentation_codev p
                INNER JOIN {schema_name}.seance_codev s ON p.seance_id = s.id
                INNER JOIN {schema_name}.groupe_codev gc ON s.groupe_id = gc.groupe_id
                WHERE gc.cycle_id = :cycle_id
                AND p.statut = :statut
            """)
            nb_presentations_result = session.exec(nb_presentations_query.bindparams(
                cycle_id=cycle_id,
                statut=StatutPresentation.RETOUR_FAIT.value
            )).one()
            nb_presentations = extract_count_value(nb_presentations_result)
        except Exception as e:
            logger.warning(f"Erreur lors du comptage des présentations: {e}")
            nb_presentations = 0
        
        return {
            "cycle": cycle,
            "nb_groupes": nb_groupes,
            "nb_membres": nb_membres,
            "nb_seances": nb_seances,
            "nb_presentations": nb_presentations,
            "taux_realisation": (nb_seances / cycle.nombre_seances_prevues * 100) if cycle.nombre_seances_prevues > 0 else 0
        }
    
    @staticmethod
    def get_prochaines_seances(session: Session, limit: int = 10, programme_id: Optional[int] = None, schema_name: str = 'acd') -> List[SeanceCodev]:
        """Récupère les prochaines séances de codéveloppement"""
        
        # Configurer le search_path
        session.exec(text(f"SET search_path TO {schema_name}, public"))
        session.commit()
        
        # Forcer l'expiration de tous les objets de la session pour éviter le cache
        session.expire_all()
        
        # Vérifier l'existence des tables essentielles
        required_tables = ["seance_codev"]
        if programme_id:
            required_tables.extend(["groupe_codev", "cycle_codev"])
        
        missing_tables = []
        for table in required_tables:
            if not table_exists_anywhere(table, session, schema_name):
                missing_tables.append(table)
        
        if missing_tables:
            print(f"⚠️ [WARNING] Tables manquantes pour les prochaines séances CoDev: {missing_tables}")
            return []
        
        try:
            maintenant = datetime.now(timezone.utc)
            
            # SQL direct
            if programme_id:
                seances_query = text(f"""
                    SELECT s.* FROM {schema_name}.seance_codev s
                    INNER JOIN {schema_name}.groupe_codev gc ON s.groupe_id = gc.groupe_id
                    INNER JOIN {schema_name}.cycle_codev cc ON gc.cycle_id = cc.id
                    WHERE s.date_seance >= :maintenant
                    AND s.statut = :statut
                    AND cc.programme_id = :programme_id
                    ORDER BY s.date_seance
                    LIMIT :limit
                """)
                seances_results = session.exec(seances_query.bindparams(
                    maintenant=maintenant,
                    statut=StatutSeanceCodev.PLANIFIEE.value,
                    programme_id=programme_id,
                    limit=limit
                )).all()
            else:
                seances_query = text(f"""
                    SELECT * FROM {schema_name}.seance_codev
                    WHERE date_seance >= :maintenant
                    AND statut = :statut
                    ORDER BY date_seance
                    LIMIT :limit
                """)
                seances_results = session.exec(seances_query.bindparams(
                    maintenant=maintenant,
                    statut=StatutSeanceCodev.PLANIFIEE.value,
                    limit=limit
                )).all()
            
            seances = [type('SeanceCodev', (), dict(row._mapping))() for row in seances_results]
            return seances
        except Exception as e:
            print(f"⚠️ [WARNING] Erreur lors de la récupération des prochaines séances CoDev: {e}")
            return []
    
    @staticmethod
    def get_engagements_en_cours(session: Session, programme_id: Optional[int] = None, schema_name: str = 'acd') -> List[PresentationCodev]:
        """Récupère les engagements en cours de test"""
        
        # Configurer le search_path
        session.exec(text(f"SET search_path TO {schema_name}, public"))
        session.commit()
        
        # Vérifier l'existence des tables essentielles
        required_tables = ["presentation_codev"]
        if programme_id:
            required_tables.extend(["seance_codev", "groupe_codev", "cycle_codev"])
        
        missing_tables = []
        for table in required_tables:
            if not table_exists_anywhere(table, session, schema_name):
                missing_tables.append(table)
        
        if missing_tables:
            print(f"⚠️ [WARNING] Tables manquantes pour les engagements CoDev: {missing_tables}")
            return []
        
        try:
            maintenant = datetime.now(timezone.utc)
            
            # SQL direct avec JOIN candidat
            if programme_id:
                presentations_query = text(f"""
                    SELECT p.*, c.nom as candidat_nom, c.prenom as candidat_prenom, c.email as candidat_email
                    FROM {schema_name}.presentation_codev p
                    INNER JOIN {schema_name}.candidat c ON p.candidat_id = c.id
                    INNER JOIN {schema_name}.seance_codev s ON p.seance_id = s.id
                    INNER JOIN {schema_name}.groupe_codev gc ON s.groupe_id = gc.groupe_id
                    INNER JOIN {schema_name}.cycle_codev cc ON gc.cycle_id = cc.id
                    WHERE p.statut = :statut
                    AND p.delai_engagement >= :maintenant_date
                    AND cc.programme_id = :programme_id
                    ORDER BY p.delai_engagement
                """)
                presentations_results = session.exec(presentations_query.bindparams(
                    statut=StatutPresentation.TEST_EN_COURS.value,
                    maintenant_date=maintenant.date(),
                    programme_id=programme_id
                )).all()
            else:
                presentations_query = text(f"""
                    SELECT p.*, c.nom as candidat_nom, c.prenom as candidat_prenom, c.email as candidat_email
                    FROM {schema_name}.presentation_codev p
                    INNER JOIN {schema_name}.candidat c ON p.candidat_id = c.id
                    WHERE p.statut = :statut
                    AND p.delai_engagement >= :maintenant_date
                    ORDER BY p.delai_engagement
                """)
                presentations_results = session.exec(presentations_query.bindparams(
                    statut=StatutPresentation.TEST_EN_COURS.value,
                    maintenant_date=maintenant.date()
                )).all()
            
            # Créer des objets avec candidat inclus
            presentations = []
            for row in presentations_results:
                row_dict = dict(row._mapping) if hasattr(row, '_mapping') else dict(row)
                presentation_obj = type('PresentationCodev', (), row_dict)()
                # Ajouter l'objet candidat
                candidat_obj = type('Candidat', (), {
                    'nom': row_dict.get('candidat_nom', ''),
                    'prenom': row_dict.get('candidat_prenom', ''),
                    'email': row_dict.get('candidat_email', '')
                })()
                presentation_obj.candidat = candidat_obj
                presentations.append(presentation_obj)
        except Exception as e:
            print(f"⚠️ [WARNING] Erreur lors de la récupération des engagements CoDev: {e}")
            return []
        
        return presentations
    
    @staticmethod
    def marquer_engagement_pris(
        session: Session,
        presentation_id: int,
        engagement: str,
        delai_engagement: date
    ) -> PresentationCodev:
        """Marque qu'un engagement a été pris par le candidat"""
        
        presentation = session.get(PresentationCodev, presentation_id)
        if not presentation:
            raise ValueError("Présentation introuvable")
        
        presentation.engagement_candidat = engagement
        presentation.delai_engagement = delai_engagement
        presentation.statut = StatutPresentation.ENGAGEMENT_PRIS.value
        
        session.commit()
        session.refresh(presentation)
        
        logger.info(f"Engagement pris pour la présentation {presentation_id}")
        return presentation
    
    @staticmethod
    def marquer_test_en_cours(session: Session, presentation_id: int) -> PresentationCodev:
        """Marque qu'un test est en cours"""
        
        presentation = session.get(PresentationCodev, presentation_id)
        if not presentation:
            raise ValueError("Présentation introuvable")
        
        presentation.statut = StatutPresentation.TEST_EN_COURS.value
        
        session.commit()
        session.refresh(presentation)
        
        logger.info(f"Test marqué en cours pour la présentation {presentation_id}")
        return presentation
    
    @staticmethod
    def ajouter_retour_experience(
        session: Session,
        presentation_id: int,
        notes_candidat: str
    ) -> PresentationCodev:
        """Ajoute le retour d'expérience du candidat"""
        
        presentation = session.get(PresentationCodev, presentation_id)
        if not presentation:
            raise ValueError("Présentation introuvable")
        
        presentation.notes_candidat = notes_candidat
        presentation.statut = StatutPresentation.RETOUR_FAIT.value
        
        session.commit()
        session.refresh(presentation)
        
        logger.info(f"Retour d'expérience ajouté pour la présentation {presentation_id}")
        return presentation
