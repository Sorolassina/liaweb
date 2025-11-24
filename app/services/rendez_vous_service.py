# app/services/rendez_vous_service.py
from datetime import datetime, date
from typing import List, Optional, Dict, Any
import logging
from sqlmodel import Session, select, and_, or_, text
from sqlalchemy import func

from ..models.base import Candidat, Entreprise, Programme, User
from ..models.rendez_vous import RendezVous, EmargementRDV
from ..models.enums import TypeRDV, StatutRDV
from ..schemas.rendez_vous_schemas import RendezVousCreate, RendezVousUpdate, RendezVousFilter
from ..core.program_schema_integration import table_exists_anywhere
from ..core.config import settings

logger = logging.getLogger(__name__)

class RendezVousService:
    """Service pour la gestion des rendez-vous"""
    
    def __init__(self, session: Session):
        self.session = session
    
    def create_rendez_vous(self, rdv_data: RendezVousCreate) -> RendezVous:
        """Créer un nouveau rendez-vous"""
        rdv = RendezVous(**rdv_data.model_dump())
        self.session.add(rdv)
        self.session.commit()
        self.session.refresh(rdv)
        return rdv
    
    def get_rendez_vous_by_id(self, rdv_id: int) -> Optional[RendezVous]:
        """Récupérer un rendez-vous par son ID"""
        return self.session.get(RendezVous, rdv_id)
    
    def update_rendez_vous(self, rdv_id: int, rdv_data: RendezVousUpdate) -> Optional[RendezVous]:
        """Mettre à jour un rendez-vous"""
        rdv = self.get_rendez_vous_by_id(rdv_id)
        if not rdv:
            return None
        
        update_data = rdv_data.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(rdv, field, value)
        
        self.session.commit()
        self.session.refresh(rdv)
        return rdv
    
    def delete_rendez_vous(self, rdv_id: int, schema_name: Optional[str] = None) -> bool:
        """Supprimer un rendez-vous"""
        if settings.DEBUG:
            logger.info(f"🗑️ [delete_rendez_vous] Début suppression RDV ID: {rdv_id}, Schéma: {schema_name}")
        
        rdv = self.get_rendez_vous_by_id(rdv_id)
        if not rdv:
            if settings.DEBUG:
                logger.warning(f"⚠️ [delete_rendez_vous] RDV {rdv_id} non trouvé")
            return False
        
        # Supprimer les é margements associés si la table existe dans le schéma spécifié
        # Utiliser le schéma directement pour éviter de chercher dans tous les schémas
        if settings.DEBUG:
            logger.info(f"🔍 [delete_rendez_vous] Vérification existence table emargement_rdv dans schéma: {schema_name}")
        
        if table_exists_anywhere("emargement_rdv", self.session, schema=schema_name):
            if settings.DEBUG:
                logger.info(f"✅ [delete_rendez_vous] Table emargement_rdv trouvée dans schéma {schema_name}, suppression des é margements")
            try:
                emargements_query = select(EmargementRDV).where(EmargementRDV.rdv_id == rdv_id)
                emargements = self.session.exec(emargements_query).all()
                if settings.DEBUG:
                    logger.info(f"📋 [delete_rendez_vous] {len(emargements)} é margement(s) trouvé(s) pour RDV {rdv_id}")
                for emargement in emargements:
                    self.session.delete(emargement)
                self.session.flush()  # Flush pour supprimer les é margements avant de supprimer le RDV
                if settings.DEBUG:
                    logger.info(f"✅ [delete_rendez_vous] É margements supprimés avec succès")
            except Exception as e:
                # Si la table n'existe pas dans le schéma actuel, ignorer l'erreur
                if settings.DEBUG:
                    logger.warning(f"⚠️ [delete_rendez_vous] Impossible de supprimer les é margements pour RDV {rdv_id}: {e}")
        else:
            if settings.DEBUG:
                logger.info(f"ℹ️ [delete_rendez_vous] Table emargement_rdv n'existe pas dans schéma {schema_name}, pas d'é margements à supprimer")
        
        # Retirer l'objet de la session pour éviter le chargement automatique de la relation
        # puis le supprimer directement via une requête SQL pour éviter le chargement de la relation
        if settings.DEBUG:
            logger.info(f"🗑️ [delete_rendez_vous] Suppression du RDV {rdv_id} via SQL direct")
        try:
            # Supprimer directement via SQL pour éviter le chargement de la relation
            stmt = text("DELETE FROM rendez_vous WHERE id = :rdv_id").bindparams(rdv_id=rdv_id)
            self.session.exec(stmt)
            self.session.commit()
            if settings.DEBUG:
                logger.info(f"✅ [delete_rendez_vous] RDV {rdv_id} supprimé avec succès via SQL direct")
        except Exception as e:
            # Si la suppression SQL échoue, essayer la méthode normale
            if settings.DEBUG:
                logger.warning(f"⚠️ [delete_rendez_vous] Erreur lors de la suppression SQL directe, tentative avec session.delete: {e}")
            # Retirer l'objet de la session pour éviter le chargement de la relation
            self.session.expunge(rdv)
            # Récupérer à nouveau l'objet sans charger les relations
            rdv = self.get_rendez_vous_by_id(rdv_id)
            if rdv:
                self.session.delete(rdv)
                self.session.commit()
                if settings.DEBUG:
                    logger.info(f"✅ [delete_rendez_vous] RDV {rdv_id} supprimé avec succès via session.delete")
        
        return True
    
    def get_rendez_vous_with_details(self, rdv_id: int) -> Optional[Dict[str, Any]]:
        """Récupérer un rendez-vous avec tous les détails"""
        query = (
            select(
                RendezVous,
                Candidat.nom.label("candidat_nom"),
                Candidat.prenom.label("candidat_prenom"),
                Candidat.email.label("candidat_email"),
                Candidat.telephone.label("candidat_telephone"),
                User.nom_complet.label("conseiller_nom"),
                Entreprise.raison_sociale.label("entreprise_nom")
            )
            .join(Candidat, RendezVous.candidat_id == Candidat.id)
            .outerjoin(Entreprise, Candidat.id == Entreprise.candidat_id)
            .outerjoin(User, RendezVous.conseiller_id == User.id)
            .where(RendezVous.id == rdv_id)
        )
        
        result = self.session.exec(query).first()
        if not result:
            return None
        
        rdv, *details = result
        return {
            "id": rdv.id,
            "candidat_id": rdv.candidat_id,
            "conseiller_id": rdv.conseiller_id,
            "type_rdv": rdv.type_rdv,
            "statut": rdv.statut,
            "debut": rdv.debut,
            "fin": rdv.fin,
            "lieu": rdv.lieu,
            "notes": rdv.notes,
            "candidat_nom": details[0],
            "candidat_prenom": details[1],
            "candidat_email": details[2],
            "candidat_telephone": details[3],
            "conseiller_nom": details[4],
            "entreprise_nom": details[5]
        }
    
    def search_rendez_vous(self, filters: RendezVousFilter, limit: int = 100, offset: int = 0) -> List[Dict[str, Any]]:
        """Rechercher des rendez-vous avec filtres"""
        # Vérifier l'existence des tables essentielles
        required_tables = ["rendez_vous", "candidat"]
        missing_tables = []
        
        for table in required_tables:
            if not table_exists_anywhere(table, self.session):
                missing_tables.append(table)
        
        if missing_tables:
            print(f"⚠️ [WARNING] Tables manquantes pour les rendez-vous: {missing_tables}")
            return []
        
        try:
            query = (
                select(
                    RendezVous,
                    Candidat.nom.label("candidat_nom"),
                    Candidat.prenom.label("candidat_prenom"),
                    Candidat.email.label("candidat_email"),
                    Candidat.telephone.label("candidat_telephone"),
                    User.nom_complet.label("conseiller_nom"),
                    Entreprise.raison_sociale.label("entreprise_nom")
                )
                .join(Candidat, RendezVous.candidat_id == Candidat.id)
                .outerjoin(Entreprise, Candidat.id == Entreprise.candidat_id)
                .outerjoin(User, RendezVous.conseiller_id == User.id)
            )
        except Exception as e:
            print(f"⚠️ [WARNING] Erreur lors de la construction de la requête rendez-vous: {e}")
            return []
        
        # Application des filtres
        conditions = []
        
        # Note: programme_id n'est plus disponible directement via inscription
        # Il faudrait peut-être l'ajouter comme champ dans RendezVous si nécessaire
        
        if filters.conseiller_id:
            conditions.append(RendezVous.conseiller_id == filters.conseiller_id)
        
        if filters.type_rdv:
            conditions.append(RendezVous.type_rdv == filters.type_rdv)
        
        if filters.statut:
            conditions.append(RendezVous.statut == filters.statut)
        
        if filters.date_debut:
            conditions.append(RendezVous.debut >= filters.date_debut)
        
        if filters.date_fin:
            conditions.append(RendezVous.debut <= filters.date_fin)
        
        if filters.candidat_nom:
            conditions.append(
                or_(
                    Candidat.nom.ilike(f"%{filters.candidat_nom}%"),
                    Candidat.prenom.ilike(f"%{filters.candidat_nom}%")
                )
            )
        
        if filters.entreprise_nom:
            conditions.append(Entreprise.raison_sociale.ilike(f"%{filters.entreprise_nom}%"))
        
        if conditions:
            query = query.where(and_(*conditions))
        
        # Tri par date de début
        query = query.order_by(RendezVous.debut.desc())
        
        # Pagination
        query = query.offset(offset).limit(limit)
        
        try:
            results = self.session.exec(query).all()
        except Exception as e:
            print(f"⚠️ [WARNING] Erreur lors de l'exécution de la requête rendez-vous: {e}")
            return []
        
        return [
            {
                "id": rdv.id,
                "candidat_id": rdv.candidat_id,
                "conseiller_id": rdv.conseiller_id,
                "type_rdv": rdv.type_rdv,
                "statut": rdv.statut,
                "debut": rdv.debut,
                "fin": rdv.fin,
                "lieu": rdv.lieu,
                "notes": rdv.notes,
                "candidat_nom": details[0],
                "candidat_prenom": details[1],
                "candidat_email": details[2],
                "candidat_telephone": details[3],
                "conseiller_nom": details[4],
                "entreprise_nom": details[5]
            }
            for rdv, *details in results
        ]
    
    def get_rendez_vous_by_conseiller(self, conseiller_id: int, date_debut: Optional[date] = None, date_fin: Optional[date] = None) -> List[Dict[str, Any]]:
        """Récupérer les rendez-vous d'un conseiller pour une période donnée"""
        filters = RendezVousFilter(
            conseiller_id=conseiller_id,
            date_debut=datetime.combine(date_debut, datetime.min.time()) if date_debut else None,
            date_fin=datetime.combine(date_fin, datetime.max.time()) if date_fin else None
        )
        return self.search_rendez_vous(filters)
    
    def get_rendez_vous_by_programme(self, programme_id: int, date_debut: Optional[date] = None, date_fin: Optional[date] = None) -> List[Dict[str, Any]]:
        """Récupérer les rendez-vous d'un programme pour une période donnée"""
        filters = RendezVousFilter(
            programme_id=programme_id,
            date_debut=datetime.combine(date_debut, datetime.min.time()) if date_debut else None,
            date_fin=datetime.combine(date_fin, datetime.max.time()) if date_fin else None
        )
        return self.search_rendez_vous(filters)
    
    def get_statistiques_rendez_vous(self, programme_id: Optional[int] = None, date_debut: Optional[date] = None, date_fin: Optional[date] = None) -> Dict[str, Any]:
        """Récupérer les statistiques des rendez-vous"""
        # Vérifier l'existence des tables essentielles
        required_tables = ["rendez_vous"]
        
        missing_tables = []
        for table in required_tables:
            if not table_exists_anywhere(table, self.session):
                missing_tables.append(table)
        
        if missing_tables:
            print(f"⚠️ [WARNING] Tables manquantes pour les statistiques rendez-vous: {missing_tables}")
            return {"total": 0, "a_venir": 0, "termines": 0, "annules": 0}
        
        try:
            query = select(RendezVous)
            
            # Note: programme_id n'est plus disponible directement via inscription
            # Il faudrait peut-être l'ajouter comme champ dans RendezVous si nécessaire
            
            if date_debut:
                query = query.where(RendezVous.debut >= datetime.combine(date_debut, datetime.min.time()))
            
            if date_fin:
                query = query.where(RendezVous.debut <= datetime.combine(date_fin, datetime.max.time()))
            
            rdv_list = self.session.exec(query).all()
        except Exception as e:
            print(f"⚠️ [WARNING] Erreur lors de la récupération des statistiques rendez-vous: {e}")
            return {"total": 0, "a_venir": 0, "termines": 0, "annules": 0}
        
        total = len(rdv_list)
        planifies = len([rdv for rdv in rdv_list if rdv.statut == StatutRDV.PLANIFIE])
        termines = len([rdv for rdv in rdv_list if rdv.statut == StatutRDV.TERMINE])
        annules = len([rdv for rdv in rdv_list if rdv.statut == StatutRDV.ANNULE])
        
        # Statistiques par type
        entretiens = len([rdv for rdv in rdv_list if rdv.type_rdv == TypeRDV.ENTRETIEN])
        suivis = len([rdv for rdv in rdv_list if rdv.type_rdv == TypeRDV.SUIVI])
        coachings = len([rdv for rdv in rdv_list if rdv.type_rdv == TypeRDV.COACHING])
        autres = len([rdv for rdv in rdv_list if rdv.type_rdv == TypeRDV.AUTRE])
        
        return {
            "total": total,
            "planifies": planifies,
            "termines": termines,
            "annules": annules,
            "par_type": {
                "entretiens": entretiens,
                "suivis": suivis,
                "coachings": coachings,
                "autres": autres
            },
            "taux_realisation": (termines / total * 100) if total > 0 else 0
        }
