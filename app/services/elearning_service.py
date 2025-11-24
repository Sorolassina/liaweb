# app/services/elearning_service.py
from sqlmodel import Session, select, and_, or_, func, text
from typing import List, Optional, Dict, Any
from datetime import datetime, timezone
import json
import logging
from ..core.program_schema_integration import safe_count_query, table_exists_anywhere

from ..models.elearning import (
    RessourceElearning, ModuleElearning, ProgressionElearning,
    ObjectifElearning, QuizElearning, ReponseQuiz, CertificatElearning,
    ModuleRessource
)
from ..models.base import User, Programme, Candidat
from ..schemas.elearning import (
    RessourceElearningCreate, RessourceElearningUpdate,
    ModuleElearningCreate, ModuleElearningUpdate,
    ProgressionElearningCreate, ProgressionElearningUpdate,
    ObjectifElearningCreate, ObjectifElearningUpdate,
    QuizElearningCreate, QuizElearningUpdate,
    ReponseQuizCreate, StatistiquesElearningCandidat,
    StatistiquesElearningProgramme, RapportProgressionElearning
)

class ElearningService:
    
    # === GESTION DES RESSOURCES ===
    
    @staticmethod
    def create_ressource(session: Session, ressource_data: RessourceElearningCreate, createur_id: int, schema_name: str = 'acd') -> RessourceElearning:
        """Créer une nouvelle ressource e-learning - SQL direct"""
        try:
            # S'assurer que schema_name est valide
            if not schema_name or schema_name == 'public':
                schema_name = 'acd'
                logging.warning(f"⚠️ [create_ressource] Schéma invalide, utilisation de 'acd' par défaut")
            
            # Note: Le search_path est déjà configuré dans le router, et on utilise {schema_name}.table_name explicitement
            ressource_dict = ressource_data.dict()
            
            # Construire la liste des colonnes et valeurs
            columns = ['titre', 'type_ressource', 'cree_par_id', 'cree_le']
            params = {
                'titre': ressource_dict.get('titre'),
                'type_ressource': ressource_dict.get('type_ressource'),
                'cree_par_id': createur_id
            }
            
            # Ajouter les champs optionnels
            optional_fields = [
                'description', 'url_contenu_video', 'url_contenu_document', 'url_contenu_audio', 'url_contenu_lien',
                'fichier_video_path', 'fichier_video_nom_original', 'fichier_document_path', 'fichier_document_nom_original',
                'fichier_audio_path', 'fichier_audio_nom_original', 'url_contenu', 'fichier_path', 'nom_fichier_original',
                'duree_minutes', 'difficulte', 'tags', 'ordre', 'actif'
            ]
            
            for field in optional_fields:
                if field in ressource_dict and ressource_dict[field] is not None:
                    columns.append(field)
                    params[field] = ressource_dict[field]
            
            # Construire les placeholders pour les valeurs (sauf cree_le qui utilise CURRENT_TIMESTAMP)
            # Utiliser :name pour les paramètres nommés SQLAlchemy
            values_list = []
            for col in columns:
                if col == 'cree_le':
                    values_list.append('CURRENT_TIMESTAMP')
                else:
                    values_list.append(f':{col}')
            
            # Construire la requête SQL avec le schéma explicitement dans le nom de la table
            insert_query_str = f"""
                INSERT INTO {schema_name}.ressource_elearning
                ({', '.join(columns)})
                VALUES ({', '.join(values_list)})
                RETURNING *
            """
            
            insert_query = text(insert_query_str)
            
            logging.info(f"🔍 [create_ressource] Schéma: {schema_name}, Colonnes: {columns}, Params: {list(params.keys())}")
            logging.info(f"🔍 [create_ressource] Requête SQL: {insert_query_str}")
            
            # Utiliser bindparams() avec les paramètres (syntaxe :name pour SQLAlchemy)
            ressource_result = session.exec(insert_query.bindparams(**params)).first()
            
            if not ressource_result:
                logging.error(f"❌ [create_ressource] Aucun résultat retourné par l'INSERT")
                session.rollback()
                raise Exception("L'insertion de la ressource n'a retourné aucun résultat")
            
            session.commit()
            logging.info(f"✅ [create_ressource] Ressource créée et commitée avec succès")
            
            if hasattr(ressource_result, '_mapping'):
                ressource_obj = type('RessourceElearning', (), dict(ressource_result._mapping))()
            else:
                ressource_obj = type('RessourceElearning', (), dict(ressource_result))()
            
            # Vérifier que l'ID existe
            if not hasattr(ressource_obj, 'id') or ressource_obj.id is None:
                logging.error(f"❌ [create_ressource] La ressource créée n'a pas d'ID")
                raise Exception("La ressource créée n'a pas d'ID")
            
            logging.info(f"✅ [create_ressource] Ressource créée avec ID: {ressource_obj.id}")
            return ressource_obj
            
        except Exception as e:
            logging.error(f"❌ [create_ressource] Erreur lors de la création: {str(e)}", exc_info=True)
            session.rollback()
            raise
    
    @staticmethod
    def get_ressources(session: Session, programme_id: Optional[int] = None, actif_only: bool = True, schema_name: str = 'acd') -> List[RessourceElearning]:
        """Récupérer les ressources e-learning - SQL direct"""
        # Vérifier l'existence de la table ressource_elearning
        if not table_exists_anywhere("ressource_elearning", session, schema_name):
            logging.warning(f"Table 'ressource_elearning' manquante dans le schéma {schema_name}")
            return []
        
        # Construire la requête SQL
        where_clauses = []
        params = {}
        
        if actif_only:
            where_clauses.append("actif = true")
        
        if programme_id:
            # Filtrer par programme via les modules
            where_clauses.append(f"""
                id IN (
                    SELECT mr.ressource_id
                    FROM {schema_name}.module_ressource mr
                    INNER JOIN {schema_name}.module_elearning m ON mr.module_id = m.id
                    WHERE m.programme_id = :programme_id
                )
            """)
            params['programme_id'] = programme_id
        
        where_sql = " AND ".join(where_clauses) if where_clauses else "1=1"
        
        query = text(f"""
            SELECT * FROM {schema_name}.ressource_elearning
            WHERE {where_sql}
            ORDER BY ordre, titre
        """)
        
        try:
            results = session.exec(query.bindparams(**params) if params else query).all()
            ressources = []
            for row in results:
                if hasattr(row, '_mapping'):
                    ressource = type('RessourceElearning', (), dict(row._mapping))()
                else:
                    ressource = type('RessourceElearning', (), dict(row))()
                ressources.append(ressource)
            return ressources
        except Exception as e:
            logging.warning(f"Erreur lors de la récupération des ressources e-learning: {e}")
            return []
    
    @staticmethod
    def update_ressource(session: Session, ressource_id: int, ressource_data: RessourceElearningUpdate, schema_name: str = 'acd') -> Optional[RessourceElearning]:
        """Mettre à jour une ressource - SQL direct"""
        # Vérifier que la ressource existe
        check_query = text(f"SELECT id FROM {schema_name}.ressource_elearning WHERE id = :ressource_id")
        check_result = session.exec(check_query.bindparams(ressource_id=ressource_id)).first()
        
        if not check_result:
            return None
        
        # Construire la requête UPDATE dynamiquement
        ressource_dict = ressource_data.dict(exclude_unset=True)
        if not ressource_dict:
            # Rien à mettre à jour
            select_query = text(f"SELECT * FROM {schema_name}.ressource_elearning WHERE id = :ressource_id")
            ressource_result = session.exec(select_query.bindparams(ressource_id=ressource_id)).first()
            if hasattr(ressource_result, '_mapping'):
                return type('RessourceElearning', (), dict(ressource_result._mapping))()
            else:
                return type('RessourceElearning', (), dict(ressource_result))()
        
        set_clauses = []
        params = {'ressource_id': ressource_id}
        
        for key, value in ressource_dict.items():
            set_clauses.append(f"{key} = :{key}")
            params[key] = value
        
        update_query = text(f"""
            UPDATE {schema_name}.ressource_elearning
            SET {', '.join(set_clauses)}
            WHERE id = :ressource_id
            RETURNING *
        """)
        
        ressource_result = session.exec(update_query.bindparams(**params)).first()
        session.commit()
        
        if hasattr(ressource_result, '_mapping'):
            return type('RessourceElearning', (), dict(ressource_result._mapping))()
        else:
            return type('RessourceElearning', (), dict(ressource_result))()
    
    # === GESTION DES MODULES ===
    
    @staticmethod
    def create_module(session: Session, module_data: ModuleElearningCreate, createur_id: int, schema_name: str = 'acd') -> ModuleElearning:
        """Créer un nouveau module e-learning - SQL direct"""
        insert_query = text(f"""
            INSERT INTO {schema_name}.module_elearning
            (titre, description, programme_id, objectifs, prerequis, duree_totale_minutes,
             difficulte, statut, ordre, actif, cree_par_id, cree_le)
            VALUES (:titre, :description, :programme_id, :objectifs, :prerequis, :duree_totale_minutes,
                    :difficulte, :statut, :ordre, :actif, :cree_par_id, CURRENT_TIMESTAMP)
            RETURNING *
        """)
        
        module_dict = module_data.dict()
        module_result = session.exec(insert_query.bindparams(
            titre=module_dict.get('titre'),
            description=module_dict.get('description'),
            programme_id=module_dict.get('programme_id'),
            objectifs=module_dict.get('objectifs'),
            prerequis=module_dict.get('prerequis'),
            duree_totale_minutes=module_dict.get('duree_totale_minutes'),
            difficulte=module_dict.get('difficulte', 'facile'),
            statut=module_dict.get('statut', 'brouillon'),
            ordre=module_dict.get('ordre', 0),
            actif=module_dict.get('actif', True),
            cree_par_id=createur_id
        )).first()
        
        session.commit()
        
        if hasattr(module_result, '_mapping'):
            return type('ModuleElearning', (), dict(module_result._mapping))()
        else:
            return type('ModuleElearning', (), dict(module_result))()
    
    @staticmethod
    def update_module(session: Session, module_id: int, module_data: ModuleElearningUpdate, schema_name: str = 'acd') -> Optional[ModuleElearning]:
        """Mettre à jour un module e-learning - SQL direct"""
        # Vérifier que le module existe
        check_query = text(f"SELECT id FROM {schema_name}.module_elearning WHERE id = :module_id")
        check_result = session.exec(check_query.bindparams(module_id=module_id)).first()
        
        if not check_result:
            return None
        
        # Construire la requête UPDATE dynamiquement
        module_dict = module_data.dict(exclude_unset=True)
        if not module_dict:
            # Rien à mettre à jour
            select_query = text(f"SELECT * FROM {schema_name}.module_elearning WHERE id = :module_id")
            module_result = session.exec(select_query.bindparams(module_id=module_id)).first()
            if hasattr(module_result, '_mapping'):
                return type('ModuleElearning', (), dict(module_result._mapping))()
            else:
                return type('ModuleElearning', (), dict(module_result))()
        
        set_clauses = []
        params = {'module_id': module_id}
        
        for key, value in module_dict.items():
            set_clauses.append(f"{key} = :{key}")
            params[key] = value
        
        update_query = text(f"""
            UPDATE {schema_name}.module_elearning
            SET {', '.join(set_clauses)}
            WHERE id = :module_id
            RETURNING *
        """)
        
        module_result = session.exec(update_query.bindparams(**params)).first()
        session.commit()
        
        if hasattr(module_result, '_mapping'):
            return type('ModuleElearning', (), dict(module_result._mapping))()
        else:
            return type('ModuleElearning', (), dict(module_result))()
    
    @staticmethod
    def get_modules(session: Session, programme_id: Optional[int] = None, statut: Optional[str] = None, actif_only: bool = True, difficulte: Optional[str] = None, schema_name: str = 'acd') -> List[ModuleElearning]:
        """Récupérer les modules e-learning - SQL direct"""
        # Vérifier l'existence de la table module_elearning
        if not table_exists_anywhere("module_elearning", session, schema_name):
            logging.warning(f"Table 'module_elearning' manquante dans le schéma {schema_name}")
            return []
        
        # Construire la requête SQL
        where_clauses = []
        params = {}
        
        if programme_id:
            where_clauses.append("programme_id = :programme_id")
            params['programme_id'] = programme_id
        
        if statut:
            where_clauses.append("statut = :statut")
            params['statut'] = statut
        
        if difficulte:
            where_clauses.append("difficulte = :difficulte")
            params['difficulte'] = difficulte
        
        if actif_only:
            where_clauses.append("actif = true")
        
        where_sql = " AND ".join(where_clauses) if where_clauses else "1=1"
        
        query = text(f"""
            SELECT * FROM {schema_name}.module_elearning
            WHERE {where_sql}
            ORDER BY ordre, titre
        """)
        
        try:
            results = session.exec(query.bindparams(**params) if params else query).all()
            modules = []
            for row in results:
                if hasattr(row, '_mapping'):
                    module = type('ModuleElearning', (), dict(row._mapping))()
                else:
                    module = type('ModuleElearning', (), dict(row))()
                modules.append(module)
            return modules
        except Exception as e:
            logging.warning(f"Erreur lors de la récupération des modules e-learning: {e}")
            return []
    
    @staticmethod
    def add_ressource_to_module(session: Session, module_id: int, ressource_id: int, ordre: int = 0, obligatoire: bool = True, schema_name: str = 'acd') -> bool:
        """Ajouter une ressource à un module - SQL direct"""
        try:
            logging.info(f"🔍 [add_ressource_to_module] Ajout ressource {ressource_id} au module {module_id} (schéma: {schema_name})")
            
            insert_query = text(f"""
                INSERT INTO {schema_name}.module_ressource
                (module_id, ressource_id, ordre, obligatoire)
                VALUES (:module_id, :ressource_id, :ordre, :obligatoire)
                ON CONFLICT (module_id, ressource_id) DO UPDATE
                SET ordre = EXCLUDED.ordre, obligatoire = EXCLUDED.obligatoire
            """)
            
            logging.info(f"🔍 [add_ressource_to_module] Requête: {insert_query}")
            logging.info(f"🔍 [add_ressource_to_module] Paramètres: module_id={module_id}, ressource_id={ressource_id}, ordre={ordre}, obligatoire={obligatoire}")
            
            result = session.exec(insert_query.bindparams(
                module_id=module_id,
                ressource_id=ressource_id,
                ordre=ordre,
                obligatoire=obligatoire
            ))
            session.commit()
            
            logging.info(f"✅ [add_ressource_to_module] Association créée avec succès")
            return True
        except Exception as e:
            logging.error(f"❌ [add_ressource_to_module] Erreur lors de l'ajout de la ressource au module: {e}", exc_info=True)
            session.rollback()
            return False
    
    @staticmethod
    def remove_ressource_from_module(session: Session, module_id: int, ressource_id: int, schema_name: str = 'acd') -> bool:
        """Retirer une ressource d'un module - SQL direct"""
        try:
            delete_query = text(f"""
                DELETE FROM {schema_name}.module_ressource
                WHERE module_id = :module_id AND ressource_id = :ressource_id
            """)
            
            result = session.exec(delete_query.bindparams(
                module_id=module_id,
                ressource_id=ressource_id
            ))
            session.commit()
            
            return result.rowcount > 0
        except Exception as e:
            logging.error(f"Erreur lors de la suppression de la ressource du module: {e}")
            session.rollback()
            return False
    
    # === GESTION DE LA PROGRESSION ===
    
    @staticmethod
    def start_ressource(session: Session, inscription_id: int, ressource_id: int) -> Optional[ProgressionElearning]:
        """Commencer une ressource"""
        # Vérifier si la progression existe déjà
        progression = session.exec(
            select(ProgressionElearning).where(
                and_(
                    ProgressionElearning.inscription_id == inscription_id,
                    ProgressionElearning.ressource_id == ressource_id
                )
            )
        ).first()
        
        if progression:
            # Mettre à jour si déjà existante
            progression.statut = "en_cours"
            progression.date_debut = datetime.now(timezone.utc)
            progression.derniere_activite = datetime.now(timezone.utc)
        else:
            # Créer nouvelle progression
            ressource = session.get(RessourceElearning, ressource_id)
            if not ressource:
                return None
            
            progression = ProgressionElearning(
                inscription_id=inscription_id,
                ressource_id=ressource_id,
                module_id=ressource.modules[0].id if ressource.modules else None,
                statut="en_cours",
                date_debut=datetime.now(timezone.utc),
                derniere_activite=datetime.now(timezone.utc)
            )
            session.add(progression)
        
        session.commit()
        session.refresh(progression)
        return progression
    
    @staticmethod
    def update_progression(session: Session, progression_id: int, temps_ajoute: int, notes: Optional[str] = None) -> Optional[ProgressionElearning]:
        """Mettre à jour la progression d'un candidat"""
        progression = session.get(ProgressionElearning, progression_id)
        if not progression:
            return None
        
        progression.temps_consacre_minutes += temps_ajoute
        progression.derniere_activite = datetime.now(timezone.utc)
        
        if notes is not None:
            progression.notes = notes
        
        session.add(progression)
        session.commit()
        session.refresh(progression)
        return progression
    
    @staticmethod
    def complete_ressource(session: Session, progression_id: int, score: Optional[float] = None) -> Optional[ProgressionElearning]:
        """Marquer une ressource comme terminée"""
        progression = session.get(ProgressionElearning, progression_id)
        if not progression:
            return None
        
        progression.statut = "termine"
        progression.date_fin = datetime.now(timezone.utc)
        progression.derniere_activite = datetime.now(timezone.utc)
        
        if score is not None:
            progression.score = score
        
        session.add(progression)
        session.commit()
        session.refresh(progression)
        return progression
    
    @staticmethod
    def get_progression_candidat(session: Session, inscription_id: int) -> List[ProgressionElearning]:
        """Récupérer la progression d'un candidat"""
        
        # Vérifier l'existence de la table progression_elearning
        if not table_exists_anywhere("progression_elearning", session):
            print(f"⚠️ [WARNING] Table 'progression_elearning' manquante")
            return []
        
        try:
            query = select(ProgressionElearning).where(
                ProgressionElearning.inscription_id == inscription_id
            ).order_by(ProgressionElearning.cree_le)
            
            return session.exec(query).all()
        except Exception as e:
            print(f"⚠️ [WARNING] Erreur lors de la récupération de la progression e-learning: {e}")
            return []
    
    # === GESTION DES QUIZ ===
    
    @staticmethod
    def create_quiz(session: Session, quiz_data: QuizElearningCreate) -> QuizElearning:
        """Créer un quiz"""
        quiz = QuizElearning(**quiz_data.dict())
        session.add(quiz)
        session.commit()
        session.refresh(quiz)
        return quiz
    
    @staticmethod
    def submit_quiz_response(session: Session, reponse_data: ReponseQuizCreate) -> ReponseQuiz:
        """Soumettre une réponse à un quiz"""
        quiz = session.get(QuizElearning, reponse_data.quiz_id)
        if not quiz:
            raise ValueError("Quiz non trouvé")
        
        # Vérifier si la réponse est correcte
        est_correcte = reponse_data.reponse_donnee.strip().lower() == quiz.reponse_correcte.strip().lower()
        points_obtenus = quiz.points if est_correcte else 0
        
        reponse = ReponseQuiz(
            **reponse_data.dict(),
            est_correcte=est_correcte,
            points_obtenus=points_obtenus
        )
        
        session.add(reponse)
        session.commit()
        session.refresh(reponse)
        return reponse
    
    # === GESTION DES OBJECTIFS ===
    
    @staticmethod
    def create_objectif(session: Session, objectif_data: ObjectifElearningCreate) -> ObjectifElearning:
        """Créer un objectif e-learning"""
        objectif = ObjectifElearning(**objectif_data.dict())
        session.add(objectif)
        session.commit()
        session.refresh(objectif)
        return objectif
    
    @staticmethod
    def check_objectif_atteint(session: Session, inscription_id: int, objectif_id: int) -> bool:
        """Vérifier si un objectif est atteint par un candidat"""
        objectif = session.get(ObjectifElearning, objectif_id)
        if not objectif:
            return False
        
        # Calculer le temps total passé par le candidat
        temps_total = session.exec(
            select(func.sum(ProgressionElearning.temps_consacre_minutes)).where(
                ProgressionElearning.inscription_id == inscription_id
            )
        ).first() or 0
        
        return temps_total >= objectif.temps_minimum_minutes
    
    # === STATISTIQUES ET RAPPORTS ===
    
    @staticmethod
    def get_statistiques_candidat(session: Session, inscription_id: int) -> StatistiquesElearningCandidat:
        """Obtenir les statistiques e-learning d'un candidat"""
        inscription = session.get(Inscription, inscription_id)
        if not inscription:
            raise ValueError("Inscription non trouvée")
        
        # Calculer les statistiques
        progressions = session.exec(
            select(ProgressionElearning).where(
                ProgressionElearning.inscription_id == inscription_id
            )
        ).all()
        
        temps_total = sum(p.temps_consacre_minutes for p in progressions)
        modules_termines = len(set(p.module_id for p in progressions if p.statut == "termine"))
        
        # Compter le nombre total de modules du programme
        modules_total = session.exec(
            select(func.count(ModuleElearning.id)).where(
                ModuleElearning.programme_id == inscription.programme_id
            )
        ).first() or 0
        
        # Calculer le score moyen
        scores = [p.score for p in progressions if p.score is not None]
        score_moyen = sum(scores) / len(scores) if scores else None
        
        # Dernière activité
        derniere_activite = max(
            (p.derniere_activite for p in progressions if p.derniere_activite),
            default=None
        )
        
        # Vérifier les objectifs
        objectifs = session.exec(
            select(ObjectifElearning).where(
                ObjectifElearning.programme_id == inscription.programme_id
            )
        ).all()
        
        objectif_atteint = all(
            ElearningService.check_objectif_atteint(session, inscription_id, obj.id)
            for obj in objectifs
        )
        
        return StatistiquesElearningCandidat(
            inscription_id=inscription_id,
            candidat_nom=f"{inscription.candidat.nom} {inscription.candidat.prenom}",
            programme_nom=inscription.programme.nom,
            temps_total_minutes=temps_total,
            modules_termines=modules_termines,
            modules_total=modules_total,
            score_moyen=score_moyen,
            derniere_activite=derniere_activite,
            objectif_atteint=objectif_atteint
        )
    
    @staticmethod
    def get_statistiques_programme(session: Session, programme_id: int, schema_name: str = 'acd') -> StatistiquesElearningProgramme:
        """Obtenir les statistiques e-learning d'un programme - SQL direct"""
        # Récupérer le programme - SQL direct
        programme_query = text("SELECT * FROM public.programme WHERE id = :programme_id")
        programme_result = session.exec(programme_query.bindparams(programme_id=programme_id)).first()
        
        if not programme_result:
            logging.warning(f"Programme {programme_id} non trouvé")
            return StatistiquesElearningProgramme(
                programme_id=programme_id,
                programme_nom="Programme inconnu",
                candidats_inscrits=0,
                candidats_actifs=0,
                modules_completes=0,
                ressources_consultees=0,
                taux_completion_moyen=0.0,
                temps_moyen_formation=0.0
            )
        
        programme = type('Programme', (), dict(programme_result._mapping))()
        
        # Vérifier l'existence des tables essentielles
        required_tables = ["progression_elearning", "module_elearning", "ressource_elearning"]
        missing_tables = []
        
        for table in required_tables:
            if not table_exists_anywhere(table, session, schema_name):
                missing_tables.append(table)
        
        if missing_tables:
            logging.warning(f"Tables manquantes pour les statistiques e-learning: {missing_tables}")
            return StatistiquesElearningProgramme(
                programme_id=programme_id,
                programme_nom=programme.nom,
                candidats_inscrits=0,
                candidats_actifs=0,
                modules_completes=0,
                ressources_consultees=0,
                taux_completion_moyen=0.0,
                temps_moyen_formation=0.0
            )
        
        # Candidats inscrits (validés) - SQL direct
        candidats_inscrits_query = text(f"""
            SELECT COUNT(*) FROM {schema_name}.candidat
            WHERE statut = 'VALIDE'
        """)
        candidats_inscrits_result = session.exec(candidats_inscrits_query).first()
        candidats_inscrits = candidats_inscrits_result[0] if candidats_inscrits_result else 0
        
        # Candidats actifs (ayant une progression) - SQL direct
        candidats_actifs_query = text(f"""
            SELECT COUNT(DISTINCT p.candidat_id)
            FROM {schema_name}.progression_elearning p
            INNER JOIN {schema_name}.candidat c ON p.candidat_id = c.id
            WHERE c.statut = 'VALIDE'
        """)
        candidats_actifs_result = session.exec(candidats_actifs_query).first()
        candidats_actifs = candidats_actifs_result[0] if candidats_actifs_result else 0
        
        # Temps moyen - SQL direct
        temps_moyen_query = text(f"""
            SELECT COALESCE(AVG(temps_total), 0) as temps_moyen
            FROM (
                SELECT p.candidat_id, SUM(p.temps_consacre_minutes) as temps_total
                FROM {schema_name}.progression_elearning p
                INNER JOIN {schema_name}.candidat c ON p.candidat_id = c.id
                WHERE c.statut = 'VALIDE'
                GROUP BY p.candidat_id
            ) as temps_par_candidat
        """)
        temps_moyen_result = session.exec(temps_moyen_query).first()
        temps_moyen = float(temps_moyen_result[0]) if temps_moyen_result and temps_moyen_result[0] else 0.0
        
        # Modules total - SQL direct
        modules_total_query = text(f"""
            SELECT COUNT(*) FROM {schema_name}.module_elearning
            WHERE programme_id = :programme_id
        """)
        modules_total_result = session.exec(modules_total_query.bindparams(programme_id=programme_id)).first()
        modules_total = modules_total_result[0] if modules_total_result else 1
        
        # Modules terminés - SQL direct
        modules_termines_query = text(f"""
            SELECT COUNT(DISTINCT p.module_id)
            FROM {schema_name}.progression_elearning p
            INNER JOIN {schema_name}.candidat c ON p.candidat_id = c.id
            WHERE p.statut = 'termine' AND c.statut = 'VALIDE'
        """)
        modules_termines_result = session.exec(modules_termines_query).first()
        modules_termines = modules_termines_result[0] if modules_termines_result else 0
        
        taux_completion = (modules_termines / modules_total) * 100 if modules_total > 0 else 0
        
        # Modules populaires - SQL direct
        modules_populaires_query = text(f"""
            SELECT m.titre, COUNT(p.id) as participations
            FROM {schema_name}.module_elearning m
            LEFT JOIN {schema_name}.progression_elearning p ON m.id = p.module_id
            WHERE m.programme_id = :programme_id
            GROUP BY m.id, m.titre
            ORDER BY participations DESC
            LIMIT 5
        """)
        modules_populaires_results = session.exec(modules_populaires_query.bindparams(programme_id=programme_id)).all()
        modules_populaires = []
        for row in modules_populaires_results:
            if hasattr(row, '_mapping'):
                modules_populaires.append({
                    "titre": dict(row._mapping).get('titre', ''),
                    "participations": dict(row._mapping).get('participations', 0)
                })
            else:
                modules_populaires.append({
                    "titre": row[0] if len(row) > 0 else '',
                    "participations": row[1] if len(row) > 1 else 0
                })
        
        # Nombre de ressources consultées
        ressources_consultees_query = text(f"""
            SELECT COUNT(DISTINCT p.ressource_id)
            FROM {schema_name}.progression_elearning p
            INNER JOIN {schema_name}.candidat c ON p.candidat_id = c.id
            WHERE c.statut = 'VALIDE'
        """)
        ressources_consultees_result = session.exec(ressources_consultees_query).first()
        ressources_consultees = ressources_consultees_result[0] if ressources_consultees_result else 0
        
        # Nombre de modules complétés
        modules_completes = modules_termines
        
        return StatistiquesElearningProgramme(
            programme_id=programme_id,
            programme_nom=programme.nom,
            candidats_inscrits=candidats_inscrits,
            candidats_actifs=candidats_actifs,
            temps_moyen_minutes=temps_moyen,
            taux_completion=taux_completion,
            modules_populaires=modules_populaires
        )
    
    @staticmethod
    def generate_certificat(session: Session, inscription_id: int, module_id: Optional[int] = None) -> CertificatElearning:
        """Générer un certificat de completion"""
        inscription = session.get(Inscription, inscription_id)
        if not inscription:
            raise ValueError("Inscription non trouvée")
        
        # Calculer les statistiques pour le certificat
        progressions = session.exec(
            select(ProgressionElearning).where(
                and_(
                    ProgressionElearning.inscription_id == inscription_id,
                    ProgressionElearning.module_id == module_id if module_id else True
                )
            )
        ).all()
        
        temps_total = sum(p.temps_consacre_minutes for p in progressions)
        scores = [p.score for p in progressions if p.score is not None]
        score_final = sum(scores) / len(scores) if scores else None
        
        # Créer le certificat
        certificat = CertificatElearning(
            inscription_id=inscription_id,
            module_id=module_id,
            titre=f"Certificat de completion - {inscription.programme.nom}",
            description=f"Certificat de completion du programme {inscription.programme.nom}",
            score_final=score_final,
            temps_total_minutes=temps_total
        )
        
        session.add(certificat)
        session.commit()
        session.refresh(certificat)
        return certificat
    
    # === STATISTIQUES SUPPLÉMENTAIRES ===
    
    @staticmethod
    def get_statistiques_globales(session: Session) -> Dict[str, Any]:
        """Obtenir les statistiques globales du système e-learning - Version sécurisée"""
        # Compter les modules - Version sécurisée
        total_modules = 0
        if table_exists_anywhere("module_elearning", session):
            try:
                total_modules = session.exec(select(func.count(ModuleElearning.id))).first() or 0
            except Exception as e:
                logging.warning(f"Erreur lors du comptage des modules e-learning: {e}")
        
        # Compter les ressources - Version sécurisée
        total_ressources = 0
        if table_exists_anywhere("ressource_elearning", session):
            try:
                total_ressources = session.exec(select(func.count(RessourceElearning.id))).first() or 0
            except Exception as e:
                logging.warning(f"Erreur lors du comptage des ressources e-learning: {e}")
        
        # Compter les candidats actifs - Version sécurisée
        total_candidats = 0
        if table_exists_anywhere("inscription", session):
            try:
                total_candidats = session.exec(
                    select(func.count(Inscription.id))
                    .where(Inscription.statut == "actif")
                ).first() or 0
            except Exception as e:
                logging.warning(f"Erreur lors du comptage des candidats actifs: {e}")
        
        # Temps total de formation
        temps_total = session.exec(
            select(func.sum(ProgressionElearning.temps_consacre_minutes))
        ).first() or 0
        
        # Croissance (simulée pour l'exemple)
        return {
            "total_modules": total_modules,
            "total_ressources": total_ressources,
            "total_candidats": total_candidats,
            "temps_total_heures": round(temps_total / 60, 1),
            "modules_croissance": 15,  # Simulé
            "ressources_croissance": 23,  # Simulé
            "candidats_croissance": 8,  # Simulé
            "temps_croissance": 12  # Simulé
        }
    
    @staticmethod
    def get_top_modules(session: Session, limit: int = 5) -> List[Dict[str, Any]]:
        """Obtenir les modules les plus populaires"""
        # Compter les complétions par module
        modules_completions = session.exec(
            select(
                ModuleElearning,
                func.count(ProgressionElearning.id).label('completions')
            )
            .join(ProgressionElearning)
            .where(ProgressionElearning.statut == "termine")
            .group_by(ModuleElearning.id)
            .order_by(func.count(ProgressionElearning.id).desc())
            .limit(limit)
        ).all()
        
        return [
            {
                "module": module,
                "completions": completions
            }
            for module, completions in modules_completions
        ]
    
    @staticmethod
    def get_top_candidats(session: Session, limit: int = 5) -> List[Dict[str, Any]]:
        """Obtenir les candidats les plus actifs"""
        # Compter le temps par candidat
        candidats_temps = session.exec(
            select(
                Candidat,
                func.sum(ProgressionElearning.temps_consacre_minutes).label('temps_total')
            )
            .join(ProgressionElearning)
            .group_by(Candidat.id)
            .order_by(func.sum(ProgressionElearning.temps_consacre_minutes).desc())
            .limit(limit)
        ).all()
        
        return [
            {
                "candidat": candidat,
                "temps_total": temps_total or 0
            }
            for candidat, temps_total in candidats_temps
        ]
    
    @staticmethod
    def get_stats_ressources_par_type(session: Session) -> Dict[str, int]:
        """Obtenir les statistiques par type de ressource"""
        stats = {}
        types = ["video", "document", "quiz", "lien", "audio"]
        
        for type_ressource in types:
            count = session.exec(
                select(func.count(RessourceElearning.id))
                .where(RessourceElearning.type_ressource == type_ressource)
            ).first()
            stats[type_ressource] = count or 0
        
        return stats
