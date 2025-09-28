# app/models/inscription.py
from sqlmodel import SQLModel, Field, Relationship
from typing import Optional, List
from datetime import datetime, timezone
from .enums import StatutDossier

class Inscription(SQLModel, table=True):
    __tablename__ = "inscription"
    
    """Inscription validée d'un candidat"""
    id: Optional[int] = Field(default=None, primary_key=True)
    programme_id: int = Field(foreign_key="programme.id")
    candidat_id: int = Field(foreign_key="candidat.id")
    promotion_id: Optional[int] = Field(foreign_key="promotion.id")
    groupe_id: Optional[int] = None
    conseiller_id: Optional[int] = Field(foreign_key="user.id")
    referent_id: Optional[int] = Field(foreign_key="user.id")
    statut: StatutDossier = StatutDossier.EN_EXAMEN
    date_decision: Optional[datetime] = None
    email_confirmation_envoye: bool = False
    cree_le: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    
    # Relations
    programme: "Programme" = Relationship(back_populates="inscriptions")
    candidat: "Candidat" = Relationship(back_populates="inscriptions")
    promotion: Optional["Promotion"] = Relationship(back_populates="inscriptions")
    conseiller: Optional["User"] = Relationship(
        back_populates="inscriptions_conseiller",
        sa_relationship_kwargs={"foreign_keys": "[Inscription.conseiller_id]"}
    )
    referent: Optional["User"] = Relationship(
        back_populates="inscriptions_referent",
        sa_relationship_kwargs={"foreign_keys": "[Inscription.referent_id]"}
    )
    decisions_jury: List["DecisionJuryTable"] = Relationship(back_populates="inscription")
    avancement_etapes: List["AvancementEtape"] = Relationship(back_populates="inscription")
    rendez_vous: List["RendezVous"] = Relationship(back_populates="inscription")
    session_participants: List["SessionParticipant"] = Relationship(back_populates="inscription")
    suivi_mensuel: List["SuiviMensuel"] = Relationship(back_populates="inscription")
    actions_handicap: List["ActionHandicap"] = Relationship(back_populates="inscription")
    progressions_elearning: List["ProgressionElearning"] = Relationship(back_populates="inscription")
    reponses_quiz: List["ReponseQuiz"] = Relationship(back_populates="inscription")
    certificats_elearning: List["CertificatElearning"] = Relationship(back_populates="inscription")
    presentations_codev: List["PresentationCodev"] = Relationship(back_populates="candidat")
    contributions_codev: List["ContributionCodev"] = Relationship(back_populates="contributeur")
    participations_seance: List["ParticipationSeance"] = Relationship(back_populates="candidat")
    membres_groupes_codev: List["MembreGroupeCodev"] = Relationship(back_populates="candidat")
    invitations_event: List["InvitationEvent"] = Relationship(back_populates="inscription")
    presences_event: List["PresenceEvent"] = Relationship(back_populates="inscription")
