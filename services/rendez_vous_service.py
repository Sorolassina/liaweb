# app/services/rendez_vous_service.py
from datetime import datetime, date
from typing import List, Optional, Dict, Any
from sqlmodel import Session, select, and_, or_
from sqlalchemy import func

from ..models.base import RendezVous, Inscription, Candidat, Entreprise, Programme, User
from ..models.enums import TypeRDV, StatutRDV
from ..schemas.rendez_vous_schemas import RendezVousCreate, RendezVousUpdate, RendezVousFilter

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
    
    def delete_rendez_vous(self, rdv_id: int) -> bool:
        """Supprimer un rendez-vous"""
        rdv = self.get_rendez_vous_by_id(rdv_id)
        if not rdv:
            return False
        
        self.session.delete(rdv)
        self.session.commit()
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
                Programme.nom.label("programme_nom"),
                Entreprise.raison_sociale.label("entreprise_nom")
            )
            .join(Inscription, RendezVous.inscription_id == Inscription.id)
            .join(Candidat, Inscription.candidat_id == Candidat.id)
            .join(Programme, Inscription.programme_id == Programme.id)
            .join(Entreprise, Candidat.id == Entreprise.candidat_id)
            .outerjoin(User, RendezVous.conseiller_id == User.id)
            .where(RendezVous.id == rdv_id)
        )
        
        result = self.session.exec(query).first()
        if not result:
            return None
        
        rdv, *details = result
        return {
            "id": rdv.id,
            "inscription_id": rdv.inscription_id,
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
            "programme_nom": details[5],
            "entreprise_nom": details[6]
        }
    
    def search_rendez_vous(self, filters: RendezVousFilter, limit: int = 100, offset: int = 0) -> List[Dict[str, Any]]:
        """Rechercher des rendez-vous avec filtres"""
        query = (
            select(
                RendezVous,
                Candidat.nom.label("candidat_nom"),
                Candidat.prenom.label("candidat_prenom"),
                Candidat.email.label("candidat_email"),
                Candidat.telephone.label("candidat_telephone"),
                User.nom_complet.label("conseiller_nom"),
                Programme.nom.label("programme_nom"),
                Programme.id.label("programme_id"),
                Entreprise.raison_sociale.label("entreprise_nom")
            )
            .join(Inscription, RendezVous.inscription_id == Inscription.id)
            .join(Candidat, Inscription.candidat_id == Candidat.id)
            .join(Programme, Inscription.programme_id == Programme.id)
            .join(Entreprise, Candidat.id == Entreprise.candidat_id)
            .outerjoin(User, RendezVous.conseiller_id == User.id)
        )
        
        # Application des filtres
        conditions = []
        
        if filters.programme_id:
            conditions.append(Programme.id == filters.programme_id)
        
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
        
        results = self.session.exec(query).all()
        
        return [
            {
                "id": rdv.id,
                "inscription_id": rdv.inscription_id,
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
                "programme_nom": details[5],
                "programme_id": details[6],
                "entreprise_nom": details[7]
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
        query = select(RendezVous)
        
        if programme_id:
            query = query.join(Inscription, RendezVous.inscription_id == Inscription.id).where(Inscription.programme_id == programme_id)
        
        if date_debut:
            query = query.where(RendezVous.debut >= datetime.combine(date_debut, datetime.min.time()))
        
        if date_fin:
            query = query.where(RendezVous.debut <= datetime.combine(date_fin, datetime.max.time()))
        
        rdv_list = self.session.exec(query).all()
        
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
