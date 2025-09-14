# app/schemas/seminaire_schemas.py
from pydantic import BaseModel, Field, validator
from typing import Optional, List
from datetime import datetime, date
from app_lia_web.app.models.enums import StatutSeminaire, TypeInvitation, StatutPresence, MethodeSignature

# Schémas pour les séminaires
class SeminaireBase(BaseModel):
    titre: str = Field(..., min_length=1, max_length=200)
    description: Optional[str] = None
    programme_id: int
    date_debut: date
    date_fin: date
    lieu: Optional[str] = None
    adresse_complete: Optional[str] = None
    organisateur_id: int
    capacite_max: Optional[int] = Field(None, gt=0)
    invitation_auto: bool = False
    invitation_promos: bool = False

    @validator('date_fin')
    def date_fin_after_debut(cls, v, values):
        if 'date_debut' in values and v < values['date_debut']:
            raise ValueError('La date de fin doit être postérieure à la date de début')
        return v

class SeminaireCreate(SeminaireBase):
    pass

class SeminaireUpdate(BaseModel):
    titre: Optional[str] = Field(None, min_length=1, max_length=200)
    description: Optional[str] = None
    date_debut: Optional[date] = None
    date_fin: Optional[date] = None
    lieu: Optional[str] = None
    adresse_complete: Optional[str] = None
    capacite_max: Optional[int] = Field(None, gt=0)
    statut: Optional[StatutSeminaire] = None
    invitation_auto: Optional[bool] = None
    invitation_promos: Optional[bool] = None

class SeminaireResponse(SeminaireBase):
    id: int
    statut: StatutSeminaire
    actif: bool
    cree_le: datetime
    modifie_le: Optional[datetime] = None

    class Config:
        from_attributes = True

# Schémas pour les sessions de séminaire
class SessionSeminaireBase(BaseModel):
    titre: str = Field(..., min_length=1, max_length=200)
    description: Optional[str] = None
    date_session: date
    heure_debut: datetime
    heure_fin: Optional[datetime] = None
    lieu: Optional[str] = None
    visioconf_url: Optional[str] = None
    capacite: Optional[int] = Field(None, gt=0)
    obligatoire: bool = True

    @validator('heure_fin')
    def heure_fin_after_debut(cls, v, values):
        if v and 'heure_debut' in values and v <= values['heure_debut']:
            raise ValueError('L\'heure de fin doit être postérieure à l\'heure de début')
        return v

class SessionSeminaireCreate(SessionSeminaireBase):
    seminaire_id: int

class SessionSeminaireUpdate(BaseModel):
    titre: Optional[str] = Field(None, min_length=1, max_length=200)
    description: Optional[str] = None
    date_session: Optional[date] = None
    heure_debut: Optional[datetime] = None
    heure_fin: Optional[datetime] = None
    lieu: Optional[str] = None
    visioconf_url: Optional[str] = None
    capacite: Optional[int] = Field(None, gt=0)
    obligatoire: Optional[bool] = None

class SessionSeminaireResponse(SessionSeminaireBase):
    id: int
    seminaire_id: int
    cree_le: datetime

    class Config:
        from_attributes = True

# Schémas pour les invitations
class InvitationSeminaireBase(BaseModel):
    type_invitation: TypeInvitation
    inscription_id: Optional[int] = None
    promotion_id: Optional[int] = None

class InvitationSeminaireCreate(InvitationSeminaireBase):
    seminaire_id: int

class InvitationSeminaireUpdate(BaseModel):
    statut: Optional[str] = None
    note: Optional[str] = None

class InvitationSeminaireResponse(InvitationSeminaireBase):
    id: int
    seminaire_id: int
    statut: str
    email_envoye: Optional[str] = None
    date_envoi: Optional[datetime] = None
    date_reponse: Optional[datetime] = None
    token_invitation: Optional[str] = None
    cree_le: datetime

    class Config:
        from_attributes = True

# Schémas pour la présence
class PresenceSeminaireBase(BaseModel):
    presence: str = "absent"  # "absent", "present", "excuse"
    methode_signature: Optional[MethodeSignature] = None
    signature_manuelle: Optional[str] = None
    signature_digitale: Optional[str] = None
    photo_signature: Optional[str] = None
    heure_arrivee: Optional[datetime] = None
    heure_depart: Optional[datetime] = None
    note: Optional[str] = None

class PresenceSeminaireCreate(PresenceSeminaireBase):
    session_id: int
    inscription_id: int

class PresenceSeminaireUpdate(BaseModel):
    presence: Optional[StatutPresence] = None
    methode_signature: Optional[MethodeSignature] = None
    signature_manuelle: Optional[str] = None
    signature_digitale: Optional[str] = None
    photo_signature: Optional[str] = None
    heure_arrivee: Optional[datetime] = None
    heure_depart: Optional[datetime] = None
    note: Optional[str] = None

class PresenceSeminaireResponse(PresenceSeminaireBase):
    id: int
    session_id: int
    inscription_id: int
    ip_signature: Optional[str] = None
    user_agent: Optional[str] = None
    cree_le: datetime
    modifie_le: Optional[datetime] = None

    class Config:
        from_attributes = True

# Schémas pour les livrables
class LivrableSeminaireBase(BaseModel):
    titre: str = Field(..., min_length=1, max_length=200)
    description: Optional[str] = None
    type_livrable: str = Field(..., min_length=1, max_length=50)
    obligatoire: bool = True
    date_limite: Optional[datetime] = None
    consignes: Optional[str] = None
    format_accepte: Optional[str] = None
    taille_max_mb: Optional[int] = Field(None, gt=0)

class LivrableSeminaireCreate(LivrableSeminaireBase):
    seminaire_id: int

class LivrableSeminaireUpdate(BaseModel):
    titre: Optional[str] = Field(None, min_length=1, max_length=200)
    description: Optional[str] = None
    type_livrable: Optional[str] = Field(None, min_length=1, max_length=50)
    obligatoire: Optional[bool] = None
    date_limite: Optional[datetime] = None
    consignes: Optional[str] = None
    format_accepte: Optional[str] = None
    taille_max_mb: Optional[int] = Field(None, gt=0)

class LivrableSeminaireResponse(LivrableSeminaireBase):
    id: int
    seminaire_id: int
    cree_le: datetime

    class Config:
        from_attributes = True

# Schémas pour les rendus de livrables
class RenduLivrableBase(BaseModel):
    commentaire_candidat: Optional[str] = None

class RenduLivrableCreate(RenduLivrableBase):
    livrable_id: int
    inscription_id: int
    nom_fichier: str
    chemin_fichier: str
    taille_fichier: int
    type_mime: str

class RenduLivrableUpdate(BaseModel):
    statut: Optional[str] = None
    commentaire_candidat: Optional[str] = None
    commentaire_evaluateur: Optional[str] = None

class RenduLivrableResponse(RenduLivrableBase):
    id: int
    livrable_id: int
    inscription_id: int
    nom_fichier: str
    chemin_fichier: str
    taille_fichier: int
    type_mime: str
    statut: str
    commentaire_evaluateur: Optional[str] = None
    depose_le: datetime
    evalue_le: Optional[datetime] = None
    evaluateur_id: Optional[int] = None

    class Config:
        from_attributes = True

# Schémas pour les statistiques
class SeminaireStats(BaseModel):
    total_seminaires: int
    seminaires_planifies: int
    seminaires_en_cours: int
    seminaires_termines: int
    total_participants: int
    taux_presence_moyen: float

class SessionStats(BaseModel):
    session_id: int
    titre: str
    total_invites: int
    presents: int
    absents: int
    excuses: int
    taux_presence: float

# Schémas pour les listes et filtres
class SeminaireFilter(BaseModel):
    programme_id: Optional[int] = None
    statut: Optional[StatutSeminaire] = None
    organisateur_id: Optional[int] = None
    date_debut_from: Optional[date] = None
    date_debut_to: Optional[date] = None
    actif: Optional[bool] = None

class PresenceFilter(BaseModel):
    session_id: Optional[int] = None
    inscription_id: Optional[int] = None
    presence: Optional[StatutPresence] = None
    methode_signature: Optional[MethodeSignature] = None
