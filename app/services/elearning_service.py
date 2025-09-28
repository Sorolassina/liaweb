# app/services/elearning_service.py
from sqlmodel import Session, select, and_, or_, func
from typing import List, Optional, Dict, Any
from datetime import datetime, timezone
import json
import logging
from app_lia_web.core.program_schema_integration import safe_count_query, table_exists_anywhere

from app_lia_web.app.models.elearning import (
    RessourceElearning, ModuleElearning, ProgressionElearning,
    ObjectifElearning, QuizElearning, ReponseQuiz, CertificatElearning,
    ModuleRessource
)
from app_lia_web.app.models.base import Inscription, User, Programme
from app_lia_web.app.schemas.elearning import (
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
    def create_ressource(session: Session, ressource_data: RessourceElearningCreate, createur_id: int) -> RessourceElearning:
        """Créer une nouvelle ressource e-learning"""
        ressource = RessourceElearning(
            **ressource_data.dict(),
            cree_par_id=createur_id
        )
        session.add(ressource)
        session.commit()
        session.refresh(ressource)
        return ressource
    
    @staticmethod
    def get_ressources(session: Session, programme_id: Optional[int] = None, actif_only: bool = True) -> List[RessourceElearning]:
        """Récupérer les ressources e-learning"""
        
        # Vérifier l'existence de la table ressource_elearning
        if not table_exists_anywhere("ressource_elearning", session):
            print(f"⚠️ [WARNING] Table 'ressource_elearning' manquante")
            return []
        
        try:
            query = select(RessourceElearning)
        except Exception as e:
            print(f"⚠️ [WARNING] Erreur lors de la construction de la requête ressources e-learning: {e}")
            return []
        
        if actif_only:
            query = query.where(RessourceElearning.actif == True)
        
        if programme_id:
            # Filtrer par programme via les modules
            query = query.join(ModuleRessource).join(ModuleElearning).where(
                ModuleElearning.programme_id == programme_id
            )
        
        query = query.order_by(RessourceElearning.ordre, RessourceElearning.titre)
        
        try:
            return session.exec(query).all()
        except Exception as e:
            print(f"⚠️ [WARNING] Erreur lors de l'exécution de la requête ressources e-learning: {e}")
            return []
    
    @staticmethod
    def update_ressource(session: Session, ressource_id: int, ressource_data: RessourceElearningUpdate) -> Optional[RessourceElearning]:
        """Mettre à jour une ressource"""
        ressource = session.get(RessourceElearning, ressource_id)
        if not ressource:
            return None
        
        for key, value in ressource_data.dict(exclude_unset=True).items():
            setattr(ressource, key, value)
        
        session.add(ressource)
        session.commit()
        session.refresh(ressource)
        return ressource
    
    # === GESTION DES MODULES ===
    
    @staticmethod
    def create_module(session: Session, module_data: ModuleElearningCreate, createur_id: int) -> ModuleElearning:
        """Créer un nouveau module e-learning"""
        module = ModuleElearning(
            **module_data.dict(),
            cree_par_id=createur_id
        )
        session.add(module)
        session.commit()
        session.refresh(module)
        return module
    
    @staticmethod
    def update_module(session: Session, module_id: int, module_data: ModuleElearningUpdate) -> ModuleElearning:
        """Mettre à jour un module e-learning"""
        module = session.get(ModuleElearning, module_id)
        if not module:
            return None
        
        # Mettre à jour les champs
        for field, value in module_data.dict(exclude_unset=True).items():
            setattr(module, field, value)
        
        session.commit()
        session.refresh(module)
        return module
    
    @staticmethod
    def get_modules(session: Session, programme_id: Optional[int] = None, statut: Optional[str] = None, actif_only: bool = True, difficulte: Optional[str] = None) -> List[ModuleElearning]:
        """Récupérer les modules e-learning"""
        print(f"🔍 SERVICE get_modules: programme_id={programme_id}, statut={statut}, actif_only={actif_only}, difficulte={difficulte}")
        
        # Pas de rollback - la session partagée gère les transactions
        
        # Vérifier l'existence de la table module_elearning
        if not table_exists_anywhere("module_elearning", session):
            print(f"⚠️ [WARNING] Table 'module_elearning' manquante")
            return []
        
        try:
            query = select(ModuleElearning)
        except Exception as e:
            print(f"⚠️ [WARNING] Erreur lors de la construction de la requête modules e-learning: {e}")
            return []
        
        if programme_id:
            query = query.where(ModuleElearning.programme_id == programme_id)
            print(f"🔍 SERVICE: Filtre programme_id={programme_id} appliqué")
        
        if statut:
            query = query.where(ModuleElearning.statut == statut)
            print(f"🔍 SERVICE: Filtre statut={statut} appliqué")
        
        if difficulte:
            query = query.where(ModuleElearning.difficulte == difficulte)
            print(f"🔍 SERVICE: Filtre difficulte={difficulte} appliqué")
        
        # Filtrer par actif seulement si actif_only est True
        if actif_only:
            query = query.where(ModuleElearning.actif == True)
            print(f"🔍 SERVICE: Filtre actif=True appliqué")
        else:
            print(f"🔍 SERVICE: Pas de filtre actif - tous les modules")
        
        query = query.order_by(ModuleElearning.ordre, ModuleElearning.titre)
        
        try:
            result = session.exec(query).all()
        except Exception as e:
            print(f"⚠️ [WARNING] Erreur lors de l'exécution de la requête modules e-learning: {e}")
            return []
        print(f"🔍 SERVICE: {len(result)} modules retournés")
        for m in result:
            print(f"  - Module {m.id}: {m.titre} (statut: {m.statut}, actif: {m.actif}, difficulte: {m.difficulte})")
        
        return result
    
    @staticmethod
    def add_ressource_to_module(session: Session, module_id: int, ressource_id: int, ordre: int = 0, obligatoire: bool = True) -> bool:
        """Ajouter une ressource à un module"""
        try:
            module_ressource = ModuleRessource(
                module_id=module_id,
                ressource_id=ressource_id,
                ordre=ordre,
                obligatoire=obligatoire
            )
            session.add(module_ressource)
            session.commit()
            return True
        except Exception:
            session.rollback()
            return False
    
    @staticmethod
    def remove_ressource_from_module(session: Session, module_id: int, ressource_id: int) -> bool:
        """Retirer une ressource d'un module"""
        try:
            module_ressource = session.exec(
                select(ModuleRessource).where(
                    and_(
                        ModuleRessource.module_id == module_id,
                        ModuleRessource.ressource_id == ressource_id
                    )
                )
            ).first()
            
            if module_ressource:
                session.delete(module_ressource)
                session.commit()
                return True
            return False
        except Exception:
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
    def get_statistiques_programme(session: Session, programme_id: int) -> StatistiquesElearningProgramme:
        """Obtenir les statistiques e-learning d'un programme"""
        print(f"🔍 DEBUG SERVICE: Début calcul stats pour programme {programme_id}")
        
        # Vérifier l'existence des tables essentielles
        required_tables = ["inscription", "progression_elearning", "module_elearning", "ressource_elearning"]
        missing_tables = []
        
        for table in required_tables:
            if not table_exists_anywhere(table, session):
                missing_tables.append(table)
        
        if missing_tables:
            print(f"⚠️ [WARNING] Tables manquantes pour les statistiques e-learning: {missing_tables}")
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
        
        try:
            programme = session.get(Programme, programme_id)
            if not programme:
                print(f"❌ DEBUG SERVICE: Programme {programme_id} non trouvé")
                raise ValueError("Programme non trouvé")
            
            print(f"✅ DEBUG SERVICE: Programme trouvé: {programme.nom}")
            
            # Candidats inscrits au programme
            candidats_inscrits = session.exec(
                select(func.count(Inscription.id)).where(
                    Inscription.programme_id == programme_id
                )
            ).first() or 0
        except Exception as e:
            print(f"⚠️ [WARNING] Erreur lors du calcul des statistiques e-learning: {e}")
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
        
        print(f"🔍 DEBUG SERVICE: {candidats_inscrits} candidats inscrits")
        
        # Candidats actifs (ayant une progression)
        candidats_actifs = session.exec(
            select(func.count(func.distinct(ProgressionElearning.inscription_id))).where(
                ProgressionElearning.inscription_id.in_(
                    select(Inscription.id).where(Inscription.programme_id == programme_id)
                )
            )
        ).first() or 0
        
        print(f"🔍 DEBUG SERVICE: {candidats_actifs} candidats actifs")
        
        # Temps moyen - Correction de la requête SQL imbriquée
        # D'abord calculer le temps total par candidat, puis la moyenne
        temps_par_candidat = session.exec(
            select(
                ProgressionElearning.inscription_id,
                func.sum(ProgressionElearning.temps_consacre_minutes).label('temps_total')
            ).where(
                ProgressionElearning.inscription_id.in_(
                    select(Inscription.id).where(Inscription.programme_id == programme_id)
                )
            ).group_by(ProgressionElearning.inscription_id)
        ).all()
        
        # Calculer la moyenne des temps totaux
        if temps_par_candidat:
            temps_moyen = sum(t[1] for t in temps_par_candidat) / len(temps_par_candidat)
        else:
            temps_moyen = 0
        
        print(f"🔍 DEBUG SERVICE: Temps moyen: {temps_moyen} minutes")
        
        # Taux de completion
        modules_total = session.exec(
            select(func.count(ModuleElearning.id)).where(
                ModuleElearning.programme_id == programme_id
            )
        ).first() or 1
        
        print(f"🔍 DEBUG SERVICE: {modules_total} modules total")
        
        modules_termines = session.exec(
            select(func.count(func.distinct(ProgressionElearning.module_id))).where(
                and_(
                    ProgressionElearning.statut == "termine",
                    ProgressionElearning.inscription_id.in_(
                        select(Inscription.id).where(Inscription.programme_id == programme_id)
                    )
                )
            )
        ).first() or 0
        
        print(f"🔍 DEBUG SERVICE: {modules_termines} modules terminés")
        
        taux_completion = (modules_termines / modules_total) * 100 if modules_total > 0 else 0
        
        print(f"🔍 DEBUG SERVICE: Taux completion: {taux_completion}%")
        
        # Modules populaires
        modules_populaires = session.exec(
            select(
                ModuleElearning.titre,
                func.count(ProgressionElearning.id).label('participations')
            ).join(ProgressionElearning).where(
                ModuleElearning.programme_id == programme_id
            ).group_by(ModuleElearning.id).order_by(
                func.count(ProgressionElearning.id).desc()
            ).limit(5)
        ).all()
        
        print(f"🔍 DEBUG SERVICE: {len(modules_populaires)} modules populaires trouvés")
        
        result = StatistiquesElearningProgramme(
            programme_id=programme_id,
            programme_nom=programme.nom,
            candidats_inscrits=candidats_inscrits,
            candidats_actifs=candidats_actifs,
            temps_moyen_minutes=float(temps_moyen) if temps_moyen else 0,
            taux_completion=taux_completion,
            modules_populaires=[{"titre": m[0], "participations": m[1]} for m in modules_populaires]
        )
        
        print(f"✅ DEBUG SERVICE: Statistiques créées avec succès")
        return result
    
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
                Inscription,
                func.sum(ProgressionElearning.temps_consacre_minutes).label('temps_total')
            )
            .join(ProgressionElearning)
            .group_by(Inscription.id)
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
