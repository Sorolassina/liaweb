from sqlmodel import Session, select, func
from typing import List, Optional, Dict, Any
from datetime import date, datetime, timezone
from app_lia_web.app.models.base import SuiviMensuel, Inscription, Candidat, Programme
from app_lia_web.app.schemas.suivi_mensuel_schemas import (
    SuiviMensuelCreate, SuiviMensuelUpdate, SuiviMensuelFilter, SuiviMensuelStats, SuiviMensuelWithCandidat
)

class SuiviMensuelService:
    """Service pour la gestion des suivis mensuels avec métriques business"""
    
    def get_suivi_mensuel(self, db: Session, suivi_id: int) -> Optional[SuiviMensuel]:
        """Récupérer un suivi mensuel par ID"""
        return db.get(SuiviMensuel, suivi_id)

    def get_suivis_mensuels(
        self, db: Session, filters: SuiviMensuelFilter, skip: int = 0, limit: int = 100
    ) -> List[SuiviMensuelWithCandidat]:
        """Récupérer les suivis mensuels avec filtres"""
        query = select(
            SuiviMensuel,
            Candidat.prenom,
            Candidat.nom,
            Programme.nom.label("programme_nom")
        ).join(Inscription, Inscription.id == SuiviMensuel.inscription_id)\
        .join(Candidat, Candidat.id == Inscription.candidat_id)\
        .join(Programme, Programme.id == Inscription.programme_id)

        if filters.programme_id:
            query = query.where(Inscription.programme_id == filters.programme_id)
        if filters.candidat_id:
            query = query.where(Inscription.candidat_id == filters.candidat_id)
        if filters.mois_debut:
            query = query.where(SuiviMensuel.mois >= filters.mois_debut)
        if filters.mois_fin:
            query = query.where(SuiviMensuel.mois <= filters.mois_fin)
        if filters.score_min is not None:
            query = query.where(SuiviMensuel.score_objectifs >= filters.score_min)
        if filters.score_max is not None:
            query = query.where(SuiviMensuel.score_objectifs <= filters.score_max)
        if filters.has_commentaire is not None:
            if filters.has_commentaire:
                query = query.where(SuiviMensuel.commentaire.is_not(None))
            else:
                query = query.where(SuiviMensuel.commentaire.is_(None))
        if filters.search_candidat:
            search_pattern = f"%{filters.search_candidat}%"
            query = query.where(
                (Candidat.prenom.ilike(search_pattern)) |
                (Candidat.nom.ilike(search_pattern))
            )

        query = query.order_by(SuiviMensuel.mois.desc(), SuiviMensuel.cree_le.desc())
        
        results = db.exec(query.offset(skip).limit(limit)).all()
        
        return [
            SuiviMensuelWithCandidat(
                id=s.id,
                inscription_id=s.inscription_id,
                mois=s.mois,
                chiffre_affaires_actuel=s.chiffre_affaires_actuel,
                nb_stagiaires=s.nb_stagiaires,
                nb_alternants=s.nb_alternants,
                nb_cdd=s.nb_cdd,
                nb_cdi=s.nb_cdi,
                montant_subventions_obtenues=s.montant_subventions_obtenues,
                organismes_financeurs=s.organismes_financeurs,
                montant_dettes_effectuees=s.montant_dettes_effectuees,
                montant_dettes_encours=s.montant_dettes_encours,
                montant_dettes_envisagees=s.montant_dettes_envisagees,
                montant_equity_effectue=s.montant_equity_effectue,
                montant_equity_encours=s.montant_equity_encours,
                statut_juridique=s.statut_juridique,
                adresse_entreprise=s.adresse_entreprise,
                situation_socioprofessionnelle=s.situation_socioprofessionnelle,
                score_objectifs=s.score_objectifs,
                commentaire=s.commentaire,
                cree_le=s.cree_le,
                modifie_le=s.modifie_le,
                candidat_nom_complet=f"{prenom} {nom}",
                programme_nom=programme_nom
            ) for s, prenom, nom, programme_nom in results
        ]

    def create_suivi_mensuel(self, db: Session, suivi_create: SuiviMensuelCreate) -> SuiviMensuel:
        """Créer un nouveau suivi mensuel"""
        # Check for existing suivi for the same inscription and month
        existing_suivi = db.exec(
            select(SuiviMensuel)
            .where(SuiviMensuel.inscription_id == suivi_create.inscription_id)
            .where(SuiviMensuel.mois == suivi_create.mois)
        ).first()
        if existing_suivi:
            raise ValueError("Un suivi existe déjà pour cette inscription et ce mois.")

        suivi = SuiviMensuel(**suivi_create.dict())
        db.add(suivi)
        db.commit()
        db.refresh(suivi)
        return suivi

    def update_suivi_mensuel(self, db: Session, suivi_id: int, suivi_update: SuiviMensuelUpdate) -> Optional[SuiviMensuel]:
        """Mettre à jour un suivi mensuel"""
        suivi = db.get(SuiviMensuel, suivi_id)
        if not suivi:
            return None
        
        # Check for existing suivi for the same inscription and month if month or inscription_id is updated
        if suivi_update.mois and suivi_update.mois != suivi.mois or \
           suivi_update.inscription_id and suivi_update.inscription_id != suivi.inscription_id:
            existing_suivi = db.exec(
                select(SuiviMensuel)
                .where(SuiviMensuel.inscription_id == (suivi_update.inscription_id or suivi.inscription_id))
                .where(SuiviMensuel.mois == (suivi_update.mois or suivi.mois))
                .where(SuiviMensuel.id != suivi_id)
            ).first()
            if existing_suivi:
                raise ValueError("Un autre suivi existe déjà pour cette inscription et ce mois.")

        update_data = suivi_update.dict(exclude_unset=True)
        for key, value in update_data.items():
            setattr(suivi, key, value)
        
        # Mettre à jour la date de modification
        suivi.modifie_le = datetime.now(timezone.utc)
        
        db.add(suivi)
        db.commit()
        db.refresh(suivi)
        return suivi

    def delete_suivi_mensuel(self, db: Session, suivi_id: int) -> bool:
        """Supprimer un suivi mensuel"""
        suivi = db.get(SuiviMensuel, suivi_id)
        if not suivi:
            return False
        db.delete(suivi)
        db.commit()
        return True

    def get_suivi_mensuel_stats(self, db: Session, filters: SuiviMensuelFilter) -> SuiviMensuelStats:
        """Calculer les statistiques des suivis mensuels"""
        query = select(SuiviMensuel).join(Inscription).join(Candidat).join(Programme)

        if filters.programme_id:
            query = query.where(Inscription.programme_id == filters.programme_id)
        if filters.candidat_id:
            query = query.where(Inscription.candidat_id == filters.candidat_id)
        if filters.mois_debut:
            query = query.where(SuiviMensuel.mois >= filters.mois_debut)
        if filters.mois_fin:
            query = query.where(SuiviMensuel.mois <= filters.mois_fin)
        if filters.score_min is not None:
            query = query.where(SuiviMensuel.score_objectifs >= filters.score_min)
        if filters.score_max is not None:
            query = query.where(SuiviMensuel.score_objectifs <= filters.score_max)
        if filters.has_commentaire is not None:
            if filters.has_commentaire:
                query = query.where(SuiviMensuel.commentaire.is_not(None))
            else:
                query = query.where(SuiviMensuel.commentaire.is_(None))
        if filters.search_candidat:
            search_pattern = f"%{filters.search_candidat}%"
            query = query.where(
                (Candidat.prenom.ilike(search_pattern)) |
                (Candidat.nom.ilike(search_pattern))
            )

        suivis = db.exec(query).all()

        # Calculer les statistiques business
        total_suivis = len(suivis)
        score_moyen = None
        suivis_avec_commentaire = 0
        ca_moyen = None
        total_employes = 0
        montant_subventions_total = 0
        montant_dettes_total = 0
        montant_equity_total = 0

        if total_suivis > 0:
            scores = [s.score_objectifs for s in suivis if s.score_objectifs is not None]
            score_moyen = sum(scores) / len(scores) if scores else None
            
            suivis_avec_commentaire = sum(1 for s in suivis if s.commentaire)
            
            # Statistiques business
            ca_values = [s.chiffre_affaires_actuel for s in suivis if s.chiffre_affaires_actuel is not None]
            ca_moyen = sum(ca_values) / len(ca_values) if ca_values else None
            
            total_employes = sum(
                (s.nb_stagiaires or 0) + (s.nb_alternants or 0) + 
                (s.nb_cdd or 0) + (s.nb_cdi or 0) 
                for s in suivis
            )
            
            montant_subventions_total = sum(
                s.montant_subventions_obtenues for s in suivis 
                if s.montant_subventions_obtenues is not None
            )
            
            montant_dettes_total = sum(
                (s.montant_dettes_effectuees or 0) + (s.montant_dettes_encours or 0) + 
                (s.montant_dettes_envisagees or 0) for s in suivis
            )
            
            montant_equity_total = sum(
                (s.montant_equity_effectue or 0) + (s.montant_equity_encours or 0) 
                for s in suivis
            )

        # Find candidates without any suivi for the given program
        candidats_sans_suivi_list = []
        if filters.programme_id:
            candidats_with_suivi_subquery = select(Inscription.candidat_id).join(SuiviMensuel).where(Inscription.programme_id == filters.programme_id).subquery()
            candidats_sans_suivi_query = select(Candidat.prenom, Candidat.nom).join(Inscription)\
                .where(Inscription.programme_id == filters.programme_id)\
                .where(Candidat.id.not_in(candidats_with_suivi_subquery))
            
            candidats_sans_suivi_results = db.exec(candidats_sans_suivi_query).all()
            candidats_sans_suivi_list = [f"{p} {n}" for p, n in candidats_sans_suivi_results]

        return SuiviMensuelStats(
            total_suivis=total_suivis,
            score_moyen=round(score_moyen, 1) if score_moyen is not None else None,
            suivis_avec_commentaire=suivis_avec_commentaire,
            suivis_sans_commentaire=total_suivis - suivis_avec_commentaire,
            candidats_sans_suivi=candidats_sans_suivi_list,
            ca_moyen=round(ca_moyen, 2) if ca_moyen is not None else None,
            total_employes=total_employes,
            montant_subventions_total=round(montant_subventions_total, 2),
            montant_dettes_total=round(montant_dettes_total, 2),
            montant_equity_total=round(montant_equity_total, 2)
        )

    def get_inscriptions_for_form(self, db: Session) -> List[dict]:
        """Récupérer les inscriptions pour le formulaire"""
        inscriptions = db.exec(
            select(Inscription.id, Candidat.prenom, Candidat.nom, Programme.nom)
            .join(Candidat)
            .join(Programme)
            .order_by(Programme.nom, Candidat.nom, Candidat.prenom)
        ).all()
        return [
            {"id": i_id, "nom_complet": f"{c_prenom} {c_nom}", "programme_nom": p_nom}
            for i_id, c_prenom, c_nom, p_nom in inscriptions
        ]