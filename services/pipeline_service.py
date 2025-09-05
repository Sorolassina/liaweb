"""
Service pour la gestion des pipelines de formation
"""
from typing import List, Dict, Any
from sqlmodel import Session, select
import logging
from ..models.base import EtapePipeline, AvancementEtape, Inscription, Candidat

logger = logging.getLogger(__name__)


class PipelineService:
    """Service pour la gestion des pipelines de formation"""
    
    @staticmethod
    def get_pipeline_etapes(session: Session, programme_id: int) -> List[dict]:
        """Récupère les étapes du pipeline d'un programme"""
        etapes = session.exec(
            select(EtapePipeline)
            .where(EtapePipeline.programme_id == programme_id)
            .order_by(EtapePipeline.ordre)
        ).all()
        
        return [
            {
                "id": etape.id,
                "nom": etape.nom,
                "description": etape.description,
                "duree_estimee": etape.duree_estimee,
                "ordre": etape.ordre,
                "active": etape.active,
                "conditions": etape.conditions
            }
            for etape in etapes
        ]
    
    @staticmethod
    def create_pipeline_etape(session: Session, programme_id: int, etape_data: dict) -> EtapePipeline:
        """Crée une nouvelle étape dans le pipeline"""
        etape = EtapePipeline(
            programme_id=programme_id,
            nom=etape_data.nom,
            description=etape_data.description,
            duree_estimee=etape_data.duree_estimee,
            ordre=etape_data.ordre,
            active=etape_data.active,
            conditions=etape_data.conditions
        )
        
        session.add(etape)
        session.commit()
        session.refresh(etape)
        return etape
    
    @staticmethod
    def update_pipeline_etape(session: Session, etape_id: int, etape_data: dict) -> EtapePipeline:
        """Met à jour une étape du pipeline"""
        etape = session.get(EtapePipeline, etape_id)
        if not etape:
            raise ValueError("Étape non trouvée")
        
        for field, value in etape_data.dict(exclude_unset=True).items():
            setattr(etape, field, value)
        
        session.add(etape)
        session.commit()
        session.refresh(etape)
        return etape
    
    @staticmethod
    def delete_pipeline_etape(session: Session, etape_id: int):
        """Supprime une étape du pipeline"""
        etape = session.get(EtapePipeline, etape_id)
        if not etape:
            raise ValueError("Étape non trouvée")
        
        session.delete(etape)
        session.commit()
    
    @staticmethod
    def toggle_pipeline_etape(session: Session, etape_id: int) -> EtapePipeline:
        """Active/désactive une étape du pipeline"""
        etape = session.get(EtapePipeline, etape_id)
        if not etape:
            raise ValueError("Étape non trouvée")
        
        etape.active = not etape.active
        session.add(etape)
        session.commit()
        session.refresh(etape)
        return etape
    
    @staticmethod
    def get_inscription_avancement(session: Session, inscription_id: int) -> List[dict]:
        """Récupère l'avancement d'un candidat dans le pipeline"""
        avancements = session.exec(
            select(AvancementEtape)
            .where(AvancementEtape.inscription_id == inscription_id)
            .order_by(AvancementEtape.etape_id)
        ).all()
        
        return [
            {
                "id": av.id,
                "etape_id": av.etape_id,
                "statut": av.statut,
                "commentaires": av.commentaires,
                "date_debut": av.date_debut,
                "date_fin": av.date_fin,
                "etape": {
                    "nom": av.etape.nom,
                    "description": av.etape.description,
                    "ordre": av.etape.ordre
                }
            }
            for av in avancements
        ]
    
    @staticmethod
    def update_inscription_avancement(session: Session, inscription_id: int, avancement_data: dict) -> AvancementEtape:
        """Met à jour l'avancement d'un candidat dans le pipeline"""
        # Vérifier si l'avancement existe déjà
        existing = session.exec(
            select(AvancementEtape)
            .where(
                AvancementEtape.inscription_id == inscription_id,
                AvancementEtape.etape_id == avancement_data.etape_id
            )
        ).first()
        
        if existing:
            # Mettre à jour l'avancement existant
            for field, value in avancement_data.dict(exclude_unset=True).items():
                setattr(existing, field, value)
            avancement = existing
        else:
            # Créer un nouvel avancement
            avancement = AvancementEtape(
                inscription_id=inscription_id,
                etape_id=avancement_data.etape_id,
                statut=avancement_data.statut,
                commentaires=avancement_data.commentaires,
                date_debut=avancement_data.date_debut,
                date_fin=avancement_data.date_fin
            )
            session.add(avancement)
        
        session.commit()
        session.refresh(avancement)
        return avancement
    
    @staticmethod
    def get_pipeline_statistiques(session: Session, programme_id: int) -> dict:
        """Récupère les statistiques du pipeline d'un programme"""
        etapes = session.exec(
            select(EtapePipeline)
            .where(EtapePipeline.programme_id == programme_id)
            .order_by(EtapePipeline.ordre)
        ).all()
        
        stats = {}
        for etape in etapes:
            candidats_count = session.exec(
                select(AvancementEtape)
                .where(AvancementEtape.etape_id == etape.id)
            ).count()
            
            stats[etape.nom] = {
                "etape_id": etape.id,
                "candidats_count": candidats_count,
                "active": etape.active
            }
        
        return stats
    
    @staticmethod
    def get_candidats_par_etape(session: Session, etape_id: int, skip: int = 0, limit: int = 10) -> List[dict]:
        """Récupère les candidats à une étape spécifique du pipeline"""
        avancements = session.exec(
            select(AvancementEtape)
            .where(AvancementEtape.etape_id == etape_id)
            .offset(skip)
            .limit(limit)
        ).all()
        
        candidats = []
        for av in avancements:
            inscription = session.get(Inscription, av.inscription_id)
            candidat = session.get(Candidat, inscription.candidat_id)
            
            candidats.append({
                "candidat_id": candidat.id,
                "nom": candidat.nom,
                "prenom": candidat.prenom,
                "statut_avancement": av.statut,
                "commentaires": av.commentaires,
                "date_debut": av.date_debut,
                "date_fin": av.date_fin
            })
        
        return candidats
    
    @staticmethod
    def reinitialiser_pipeline(session: Session, programme_id: int):
        """Réinitialise le pipeline d'un programme"""
        # Supprimer tous les avancements pour ce programme
        inscriptions = session.exec(
            select(Inscription).where(Inscription.programme_id == programme_id)
        ).all()
        
        for inscription in inscriptions:
            avancements = session.exec(
                select(AvancementEtape).where(AvancementEtape.inscription_id == inscription.id)
            ).all()
            
            for av in avancements:
                session.delete(av)
        
        session.commit()
    
    @staticmethod
    def reordonner_etapes(session: Session, etape_id: int, nouvelle_position: int):
        """Réordonne les étapes du pipeline"""
        etape = session.get(EtapePipeline, etape_id)
        if not etape:
            raise ValueError("Étape non trouvée")
        
        # Récupérer toutes les étapes du programme
        etapes = session.exec(
            select(EtapePipeline)
            .where(EtapePipeline.programme_id == etape.programme_id)
            .order_by(EtapePipeline.ordre)
        ).all()
        
        # Réordonner
        ancienne_position = etape.ordre
        if nouvelle_position < ancienne_position:
            # Déplacer vers le haut
            for e in etapes:
                if e.ordre >= nouvelle_position and e.ordre < ancienne_position:
                    e.ordre += 1
        else:
            # Déplacer vers le bas
            for e in etapes:
                if e.ordre > ancienne_position and e.ordre <= nouvelle_position:
                    e.ordre -= 1
        
        etape.ordre = nouvelle_position
        
        session.add(etape)
        session.commit()
