from sqlmodel import Session, select, func
from sqlalchemy import text
from typing import List, Optional, Dict, Any
from datetime import date, datetime, timezone
from ..models.base import SuiviMensuel, Candidat, Programme
from ..core.program_schema_integration import table_exists_anywhere
from ..schemas.suivi_mensuel_schemas import (
    SuiviMensuelCreate, SuiviMensuelUpdate, SuiviMensuelFilter, SuiviMensuelStats, SuiviMensuelWithCandidat
)

class SuiviMensuelService:
    """Service pour la gestion des suivis mensuels avec métriques business"""
    
    def get_suivi_mensuel(self, db: Session, suivi_id: int) -> Optional[SuiviMensuel]:
        """Récupérer un suivi mensuel par ID"""
        return db.get(SuiviMensuel, suivi_id)

    def get_suivis_mensuels(
        self, db: Session, filters: SuiviMensuelFilter, skip: int = 0, limit: int = 100, schema_name: str = 'acd'
    ) -> List[SuiviMensuelWithCandidat]:
        """Récupérer les suivis mensuels avec filtres - Utilise SQL direct pour gérer les schémas"""
        
        # Construire la requête SQL de base
        base_query = f"""
            SELECT 
                sm.*,
                c.prenom,
                c.nom,
                COALESCE(p.nom, 'N/A') AS programme_nom
            FROM {schema_name}.suivi_mensuel sm
            INNER JOIN {schema_name}.candidat c ON c.id = sm.candidat_id
            LEFT JOIN {schema_name}.preinscription pr ON pr.candidat_id = c.id
            LEFT JOIN public.programme p ON p.id = pr.programme_id
        """
        
        where_conditions = []
        params = {}
        
        # Appliquer les filtres
        if filters.candidat_id:
            where_conditions.append("sm.candidat_id = :candidat_id")
            params["candidat_id"] = filters.candidat_id
        
        if filters.mois_debut:
            where_conditions.append("sm.mois >= :mois_debut")
            params["mois_debut"] = filters.mois_debut
        
        if filters.mois_fin:
            where_conditions.append("sm.mois <= :mois_fin")
            params["mois_fin"] = filters.mois_fin
        
        if filters.score_min is not None:
            where_conditions.append("sm.score_objectifs >= :score_min")
            params["score_min"] = filters.score_min
        
        if filters.score_max is not None:
            where_conditions.append("sm.score_objectifs <= :score_max")
            params["score_max"] = filters.score_max
        
        if filters.has_commentaire is not None:
            if filters.has_commentaire:
                where_conditions.append("sm.commentaire IS NOT NULL")
            else:
                where_conditions.append("sm.commentaire IS NULL")
        
        if filters.search_candidat:
            where_conditions.append("(LOWER(c.prenom) LIKE :search_pattern OR LOWER(c.nom) LIKE :search_pattern)")
            params["search_pattern"] = f"%{filters.search_candidat.lower()}%"
        
        # Ajouter les conditions WHERE
        if where_conditions:
            base_query += " WHERE " + " AND ".join(where_conditions)
        
        # Ajouter ORDER BY et LIMIT
        base_query += " ORDER BY sm.mois DESC, sm.cree_le DESC"
        base_query += f" LIMIT {limit} OFFSET {skip}"
        
        try:
            query = text(base_query)
            results = db.exec(query.bindparams(**params)).all()
            
            suivis_list = []
            for row in results:
                row_dict = dict(row._mapping) if hasattr(row, '_mapping') else dict(row)
                
                # Créer un objet SuiviMensuel factice
                suivi = type('SuiviMensuel', (), {
                    'id': row_dict.get('id'),
                    'candidat_id': row_dict.get('candidat_id'),
                    'mois': row_dict.get('mois'),
                    'chiffre_affaires_actuel': row_dict.get('chiffre_affaires_actuel'),
                    'nb_stagiaires': row_dict.get('nb_stagiaires'),
                    'nb_alternants': row_dict.get('nb_alternants'),
                    'nb_cdd': row_dict.get('nb_cdd'),
                    'nb_cdi': row_dict.get('nb_cdi'),
                    'montant_subventions_obtenues': row_dict.get('montant_subventions_obtenues'),
                    'organismes_financeurs': row_dict.get('organismes_financeurs'),
                    'montant_dettes_effectuees': row_dict.get('montant_dettes_effectuees'),
                    'montant_dettes_encours': row_dict.get('montant_dettes_encours'),
                    'montant_dettes_envisagees': row_dict.get('montant_dettes_envisagees'),
                    'montant_equity_effectue': row_dict.get('montant_equity_effectue'),
                    'montant_equity_encours': row_dict.get('montant_equity_encours'),
                    'statut_juridique': row_dict.get('statut_juridique'),
                    'adresse_entreprise': row_dict.get('adresse_entreprise'),
                    'situation_socioprofessionnelle': row_dict.get('situation_socioprofessionnelle'),
                    'score_objectifs': row_dict.get('score_objectifs'),
                    'commentaire': row_dict.get('commentaire'),
                    'cree_le': row_dict.get('cree_le'),
                    'modifie_le': row_dict.get('modifie_le')
                })()
                
                suivis_list.append(
                    SuiviMensuelWithCandidat(
                        id=suivi.id,
                        inscription_id=suivi.candidat_id,  # NOTE: inscription_id dans le schéma correspond à candidat_id dans le modèle
                        mois=suivi.mois,
                        chiffre_affaires_actuel=suivi.chiffre_affaires_actuel,
                        nb_stagiaires=suivi.nb_stagiaires,
                        nb_alternants=suivi.nb_alternants,
                        nb_cdd=suivi.nb_cdd,
                        nb_cdi=suivi.nb_cdi,
                        montant_subventions_obtenues=suivi.montant_subventions_obtenues,
                        organismes_financeurs=suivi.organismes_financeurs,
                        montant_dettes_effectuees=suivi.montant_dettes_effectuees,
                        montant_dettes_encours=suivi.montant_dettes_encours,
                        montant_dettes_envisagees=suivi.montant_dettes_envisagees,
                        montant_equity_effectue=suivi.montant_equity_effectue,
                        montant_equity_encours=suivi.montant_equity_encours,
                        statut_juridique=suivi.statut_juridique,
                        adresse_entreprise=suivi.adresse_entreprise,
                        situation_socioprofessionnelle=suivi.situation_socioprofessionnelle,
                        score_objectifs=suivi.score_objectifs,
                        commentaire=suivi.commentaire,
                        cree_le=suivi.cree_le,
                        modifie_le=suivi.modifie_le,
                        candidat_nom_complet=f"{row_dict.get('prenom', '')} {row_dict.get('nom', '')}",
                        programme_nom=row_dict.get('programme_nom', 'N/A')
                    )
                )
            
            return suivis_list
        except Exception as e:
            print(f"❌ ERREUR lors de la récupération des suivis mensuels: {e}")
            import traceback
            traceback.print_exc()
            return []

    def create_suivi_mensuel(self, db: Session, suivi_create: SuiviMensuelCreate) -> SuiviMensuel:
        """Créer un nouveau suivi mensuel"""
        try:
            # NOTE: inscription_id dans le schéma correspond à candidat_id dans le modèle
            candidat_id = suivi_create.inscription_id
            
            # Check for existing suivi for the same candidat and month
            existing_suivi = db.exec(
                select(SuiviMensuel)
                .where(SuiviMensuel.candidat_id == candidat_id)
                .where(SuiviMensuel.mois == suivi_create.mois)
            ).first()
            if existing_suivi:
                raise ValueError("Un suivi existe déjà pour ce candidat et ce mois.")

            # Convertir inscription_id en candidat_id pour le modèle
            # Utiliser model_dump() pour Pydantic v2, ou dict() pour v1
            try:
                suivi_dict = suivi_create.model_dump() if hasattr(suivi_create, 'model_dump') else suivi_create.dict()
            except AttributeError:
                suivi_dict = suivi_create.dict()
            suivi_dict['candidat_id'] = suivi_dict.pop('inscription_id')
            
            suivi = SuiviMensuel(**suivi_dict)
            db.add(suivi)
            db.commit()
            db.refresh(suivi)
            return suivi
        except Exception as e:
            db.rollback()
            print(f"❌ ERREUR lors de la création du suivi mensuel: {e}")
            print(f"   Type d'erreur: {type(e).__name__}")
            import traceback
            traceback.print_exc()
            raise

    def update_suivi_mensuel(self, db: Session, suivi_id: int, suivi_update: SuiviMensuelUpdate) -> Optional[SuiviMensuel]:
        """Mettre à jour un suivi mensuel"""
        suivi = db.get(SuiviMensuel, suivi_id)
        if not suivi:
            return None
        
        # NOTE: inscription_id dans le schéma correspond à candidat_id dans le modèle
        # Check for existing suivi for the same candidat and month if month or inscription_id is updated
        new_candidat_id = suivi_update.inscription_id if suivi_update.inscription_id else suivi.candidat_id
        new_mois = suivi_update.mois if suivi_update.mois else suivi.mois
        
        if (suivi_update.mois and suivi_update.mois != suivi.mois) or \
           (suivi_update.inscription_id and suivi_update.inscription_id != suivi.candidat_id):
            existing_suivi = db.exec(
                select(SuiviMensuel)
                .where(SuiviMensuel.candidat_id == new_candidat_id)
                .where(SuiviMensuel.mois == new_mois)
                .where(SuiviMensuel.id != suivi_id)
            ).first()
            if existing_suivi:
                raise ValueError("Un autre suivi existe déjà pour ce candidat et ce mois.")

        # Utiliser model_dump() pour Pydantic v2, ou dict() pour v1
        try:
            update_data = suivi_update.model_dump(exclude_unset=True) if hasattr(suivi_update, 'model_dump') else suivi_update.dict(exclude_unset=True)
        except AttributeError:
            update_data = suivi_update.dict(exclude_unset=True)
        # Convertir inscription_id en candidat_id si présent
        if 'inscription_id' in update_data:
            update_data['candidat_id'] = update_data.pop('inscription_id')
        
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

    def get_suivi_mensuel_stats(self, db: Session, filters: SuiviMensuelFilter, schema_name: str = 'acd') -> SuiviMensuelStats:
        """Calculer les statistiques des suivis mensuels - Utilise SQL direct pour gérer les schémas"""
        
        # Construire la requête SQL de base
        base_query = f"""
            SELECT 
                sm.*,
                c.prenom,
                c.nom
            FROM {schema_name}.suivi_mensuel sm
            INNER JOIN {schema_name}.candidat c ON c.id = sm.candidat_id
        """
        
        where_conditions = []
        params = {}
        
        # Appliquer les filtres
        if filters.candidat_id:
            where_conditions.append("sm.candidat_id = :candidat_id")
            params["candidat_id"] = filters.candidat_id
        
        if filters.mois_debut:
            where_conditions.append("sm.mois >= :mois_debut")
            params["mois_debut"] = filters.mois_debut
        
        if filters.mois_fin:
            where_conditions.append("sm.mois <= :mois_fin")
            params["mois_fin"] = filters.mois_fin
        
        if filters.score_min is not None:
            where_conditions.append("sm.score_objectifs >= :score_min")
            params["score_min"] = filters.score_min
        
        if filters.score_max is not None:
            where_conditions.append("sm.score_objectifs <= :score_max")
            params["score_max"] = filters.score_max
        
        if filters.has_commentaire is not None:
            if filters.has_commentaire:
                where_conditions.append("sm.commentaire IS NOT NULL")
            else:
                where_conditions.append("sm.commentaire IS NULL")
        
        if filters.search_candidat:
            where_conditions.append("(LOWER(c.prenom) LIKE :search_pattern OR LOWER(c.nom) LIKE :search_pattern)")
            params["search_pattern"] = f"%{filters.search_candidat.lower()}%"
        
        # Ajouter les conditions WHERE
        if where_conditions:
            base_query += " WHERE " + " AND ".join(where_conditions)
        
        try:
            query = text(base_query)
            results = db.exec(query.bindparams(**params)).all()
            
            # Convertir les résultats en objets SuiviMensuel factices
            suivis = []
            for row in results:
                row_dict = dict(row._mapping) if hasattr(row, '_mapping') else dict(row)
                suivi = type('SuiviMensuel', (), {
                    'id': row_dict.get('id'),
                    'candidat_id': row_dict.get('candidat_id'),
                    'mois': row_dict.get('mois'),
                    'chiffre_affaires_actuel': row_dict.get('chiffre_affaires_actuel'),
                    'nb_stagiaires': row_dict.get('nb_stagiaires'),
                    'nb_alternants': row_dict.get('nb_alternants'),
                    'nb_cdd': row_dict.get('nb_cdd'),
                    'nb_cdi': row_dict.get('nb_cdi'),
                    'montant_subventions_obtenues': row_dict.get('montant_subventions_obtenues'),
                    'montant_dettes_effectuees': row_dict.get('montant_dettes_effectuees'),
                    'montant_dettes_encours': row_dict.get('montant_dettes_encours'),
                    'montant_dettes_envisagees': row_dict.get('montant_dettes_envisagees'),
                    'montant_equity_effectue': row_dict.get('montant_equity_effectue'),
                    'montant_equity_encours': row_dict.get('montant_equity_encours'),
                    'score_objectifs': row_dict.get('score_objectifs'),
                    'commentaire': row_dict.get('commentaire')
                })()
                suivis.append(suivi)
        except Exception as e:
            print(f"❌ ERREUR lors du calcul des statistiques: {e}")
            import traceback
            traceback.print_exc()
            suivis = []

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
        # NOTE: Le modèle Inscription a été supprimé. Utiliser directement candidat_id.
        if filters.programme_id:
            # candidats_with_suivi_subquery = select(Inscription.candidat_id).join(SuiviMensuel).where(Inscription.programme_id == filters.programme_id).subquery()
            candidats_with_suivi_subquery = select(SuiviMensuel.candidat_id).subquery()
            candidats_sans_suivi_query = select(Candidat.prenom, Candidat.nom)\
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

    def get_inscriptions_for_form(self, db: Session, schema_name: str = 'acd') -> List[dict]:
        """Récupérer les candidats validés pour le formulaire - NOTE: Le modèle Inscription a été supprimé"""
        from ..models.enums import DecisionJury
        
        # Utiliser une requête SQL directe pour joindre candidat (schéma programme) avec programme (schéma public)
        query = text(f"""
            SELECT 
                c.id,
                c.prenom,
                c.nom,
                p.nom AS programme_nom
            FROM {schema_name}.candidat c
            INNER JOIN {schema_name}.preinscription pr ON pr.candidat_id = c.id
            INNER JOIN public.programme p ON p.id = pr.programme_id
            WHERE c.statut = :statut_valide
            ORDER BY p.nom, c.nom, c.prenom
        """)
        
        results = db.exec(query.bindparams(statut_valide=DecisionJury.VALIDE.value)).all()
        
        inscriptions_list = []
        for row in results:
            # Accéder aux colonnes via _mapping ou directement par nom
            row_dict = dict(row._mapping) if hasattr(row, '_mapping') else dict(row)
            inscriptions_list.append({
                "id": row_dict.get('id'),
                "nom_complet": f"{row_dict.get('prenom', '')} {row_dict.get('nom', '')}",
                "programme_nom": row_dict.get('programme_nom', '')
            })
        
        return inscriptions_list