# app/schemas/suivi_mensuel_schemas.py
from datetime import date, datetime
from typing import Optional, List
from pydantic import BaseModel, Field, validator

class SuiviMensuelBase(BaseModel):
    """Schéma de base pour le suivi mensuel avec métriques business"""
    inscription_id: int = Field(..., description="ID de l'inscription")
    mois: date = Field(..., description="Mois du suivi (1er du mois)")
    
    # Métriques business principales
    chiffre_affaires_actuel: Optional[float] = Field(None, ge=0, description="Chiffre d'affaires en euros")
    
    # Évolution des employés
    nb_stagiaires: Optional[int] = Field(None, ge=0, description="Nombre de stagiaires")
    nb_alternants: Optional[int] = Field(None, ge=0, description="Nombre d'alternants")
    nb_cdd: Optional[int] = Field(None, ge=0, description="Nombre de CDD")
    nb_cdi: Optional[int] = Field(None, ge=0, description="Nombre de CDI")
    
    # Subventions et financements
    montant_subventions_obtenues: Optional[float] = Field(None, ge=0, description="Montant des subventions en euros")
    organismes_financeurs: Optional[str] = Field(None, description="Liste des organismes financeurs")
    
    # Dettes
    montant_dettes_effectuees: Optional[float] = Field(None, ge=0, description="Montant des dettes payées en euros")
    montant_dettes_encours: Optional[float] = Field(None, ge=0, description="Montant des dettes en cours en euros")
    montant_dettes_envisagees: Optional[float] = Field(None, ge=0, description="Montant des dettes prévues en euros")
    
    # Levée de fonds equity
    montant_equity_effectue: Optional[float] = Field(None, ge=0, description="Montant de levée de fonds réalisée en euros")
    montant_equity_encours: Optional[float] = Field(None, ge=0, description="Montant de levée de fonds en cours en euros")
    
    # Informations entreprise
    statut_juridique: Optional[str] = Field(None, description="Statut juridique de l'entreprise")
    adresse_entreprise: Optional[str] = Field(None, description="Adresse de l'entreprise")
    
    # Situation socioprofessionnelle
    situation_socioprofessionnelle: Optional[str] = Field(None, description="Situation socioprofessionnelle du candidat")
    
    # Métriques générales
    score_objectifs: Optional[float] = Field(None, ge=0, le=100, description="Score global des objectifs (0-100)")
    commentaire: Optional[str] = Field(None, max_length=2000, description="Commentaires libres")

    @validator('mois', pre=True)
    def set_day_to_first_of_month(cls, v):
        """S'assurer que le jour est le 1er du mois"""
        if isinstance(v, str):
            try:
                # Si c'est déjà au format YYYY-MM-DD, parser directement
                if len(v) == 10 and v.count('-') == 2:
                    parsed_date = datetime.strptime(v, '%Y-%m-%d').date()
                    return parsed_date.replace(day=1)
                # Si c'est au format YYYY-MM, ajouter le jour 1
                elif len(v) == 7 and v.count('-') == 1:
                    parsed_date = datetime.strptime(v, '%Y-%m').date()
                    return parsed_date.replace(day=1)
                else:
                    raise ValueError("Format de date invalide")
            except ValueError:
                raise ValueError("Date format must be YYYY-MM-DD or YYYY-MM")
        elif isinstance(v, date):
            return v.replace(day=1)
        return v

class SuiviMensuelCreate(SuiviMensuelBase):
    """Schéma pour créer un suivi mensuel"""
    pass

class SuiviMensuelUpdate(BaseModel):
    """Schéma pour mettre à jour un suivi mensuel (tous les champs optionnels)"""
    inscription_id: Optional[int] = None
    mois: Optional[date] = None
    
    # Métriques business principales
    chiffre_affaires_actuel: Optional[float] = Field(None, ge=0)
    
    # Évolution des employés
    nb_stagiaires: Optional[int] = Field(None, ge=0)
    nb_alternants: Optional[int] = Field(None, ge=0)
    nb_cdd: Optional[int] = Field(None, ge=0)
    nb_cdi: Optional[int] = Field(None, ge=0)
    
    # Subventions et financements
    montant_subventions_obtenues: Optional[float] = Field(None, ge=0)
    organismes_financeurs: Optional[str] = None
    
    # Dettes
    montant_dettes_effectuees: Optional[float] = Field(None, ge=0)
    montant_dettes_encours: Optional[float] = Field(None, ge=0)
    montant_dettes_envisagees: Optional[float] = Field(None, ge=0)
    
    # Levée de fonds equity
    montant_equity_effectue: Optional[float] = Field(None, ge=0)
    montant_equity_encours: Optional[float] = Field(None, ge=0)
    
    # Informations entreprise
    statut_juridique: Optional[str] = None
    adresse_entreprise: Optional[str] = None
    
    # Situation socioprofessionnelle
    situation_socioprofessionnelle: Optional[str] = None
    
    # Métriques générales
    score_objectifs: Optional[float] = Field(None, ge=0, le=100)
    commentaire: Optional[str] = Field(None, max_length=2000)

    @validator('mois', pre=True)
    def set_day_to_first_of_month_update(cls, v):
        """S'assurer que le jour est le 1er du mois pour les mises à jour"""
        if v is None:
            return v
        if isinstance(v, str):
            try:
                # Si c'est déjà au format YYYY-MM-DD, parser directement
                if len(v) == 10 and v.count('-') == 2:
                    parsed_date = datetime.strptime(v, '%Y-%m-%d').date()
                    return parsed_date.replace(day=1)
                # Si c'est au format YYYY-MM, ajouter le jour 1
                elif len(v) == 7 and v.count('-') == 1:
                    parsed_date = datetime.strptime(v, '%Y-%m').date()
                    return parsed_date.replace(day=1)
                else:
                    raise ValueError("Format de date invalide")
            except ValueError:
                raise ValueError("Date format must be YYYY-MM-DD or YYYY-MM")
        elif isinstance(v, date):
            return v.replace(day=1)
        return v

class SuiviMensuelResponse(SuiviMensuelBase):
    """Schéma de réponse pour le suivi mensuel"""
    id: int
    cree_le: datetime
    modifie_le: Optional[datetime] = None

    class Config:
        from_attributes = True

class SuiviMensuelWithCandidat(SuiviMensuelResponse):
    """Schéma de réponse avec informations du candidat"""
    candidat_nom_complet: str
    programme_nom: str

class SuiviMensuelFilter(BaseModel):
    """Filtres pour la recherche de suivis mensuels"""
    programme_id: Optional[int] = None
    candidat_id: Optional[int] = None
    mois_debut: Optional[date] = None
    mois_fin: Optional[date] = None
    score_min: Optional[float] = Field(None, ge=0, le=100)
    score_max: Optional[float] = Field(None, ge=0, le=100)
    has_commentaire: Optional[bool] = None
    search_candidat: Optional[str] = None

    @validator('mois_debut', 'mois_fin', pre=True)
    def set_day_to_first_of_month_filter(cls, v):
        """S'assurer que les dates de filtre sont au 1er du mois"""
        if v is None:
            return v
        if isinstance(v, str):
            try:
                # Si c'est déjà au format YYYY-MM-DD, parser directement
                if len(v) == 10 and v.count('-') == 2:
                    parsed_date = datetime.strptime(v, '%Y-%m-%d').date()
                    return parsed_date.replace(day=1)
                # Si c'est au format YYYY-MM, ajouter le jour 1
                elif len(v) == 7 and v.count('-') == 1:
                    parsed_date = datetime.strptime(v, '%Y-%m').date()
                    return parsed_date.replace(day=1)
                else:
                    raise ValueError("Format de date invalide")
            except ValueError:
                raise ValueError("Date format for filters must be YYYY-MM-DD or YYYY-MM")
        elif isinstance(v, date):
            return v.replace(day=1)
        return v

class SuiviMensuelStats(BaseModel):
    """Statistiques des suivis mensuels"""
    total_suivis: int
    score_moyen: Optional[float] = None
    suivis_avec_commentaire: int
    suivis_sans_commentaire: int
    candidats_sans_suivi: List[str] = []
    
    # Statistiques business
    ca_moyen: Optional[float] = None
    total_employes: Optional[int] = None
    montant_subventions_total: Optional[float] = None
    montant_dettes_total: Optional[float] = None
    montant_equity_total: Optional[float] = None