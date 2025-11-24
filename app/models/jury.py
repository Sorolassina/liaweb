# app/models/jury.py
from sqlmodel import SQLModel, Field, Relationship
from sqlalchemy import ForeignKeyConstraint
from typing import Optional, List
from datetime import datetime, timezone
from .enums import DecisionJury

class Jury(SQLModel, table=True):
    __tablename__ = "jury"
    
    """Session de jury"""
    id: Optional[int] = Field(default=None, primary_key=True)
    programme_id: int = Field(foreign_key="programme.id")
    promotion_id: Optional[int] = Field(foreign_key="promotion.id")
    session_le: datetime
    lieu: Optional[str] = None
    statut: str = "planifie"  # "planifie", "en_cours", "termine"
    
    # Relations
    programme: "Programme" = Relationship()
    promotion: Optional["Promotion"] = Relationship()
    membres: List["MembreJury"] = Relationship(back_populates="jury")
    decisions: List["DecisionJuryTable"] = Relationship(back_populates="jury")

class MembreJury(SQLModel, table=True):
    __tablename__ = "membre_jury"
    
    """Membre d'un jury"""
    id: Optional[int] = Field(default=None, primary_key=True)
    jury_id: int = Field(foreign_key="jury.id")
    utilisateur_id: int = Field(foreign_key="user.id")
    role: Optional[str] = None  # "president" | "membre"
    
    # Relations
    jury: Jury = Relationship(back_populates="membres")
    utilisateur: "User" = Relationship()

class DecisionJuryTable(SQLModel, table=True):
    __tablename__ = "decision_jury_table"
    
    """Décision d'un jury sur un candidat"""
    id: Optional[int] = Field(default=None, primary_key=True)
    candidat_id: int = Field(foreign_key="candidat.id")
    jury_id: int = Field(foreign_key="jury.id")
    decision: DecisionJury
    commentaires: Optional[str] = None
    prises_en_charge_json: Optional[str] = None  # actions suite à handicap etc.
    decide_le: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    
    # Relations
    candidat: "Candidat" = Relationship()
    jury: Jury = Relationship(back_populates="decisions")

class DecisionJuryCandidat(SQLModel, table=True):
    __tablename__ = "decision_jury_candidat"
    
    """Décisions du jury pour chaque candidat"""
    id: Optional[int] = Field(default=None, primary_key=True)
    candidat_id: int = Field(foreign_key="candidat.id", index=True)
    # jury_id référence public.jury.id (la contrainte en base référence public.jury)
    # On utilise "jury.id" pour SQLModel, mais la contrainte en base référence public.jury
    jury_id: int = Field(foreign_key="jury.id", index=True)
    decision: DecisionJury = Field(default=DecisionJury.EN_ATTENTE)
    commentaires: Optional[str] = None
    conseiller_id: Optional[int] = Field(foreign_key="user.id", default=None)  # Si validé
    groupe_id: Optional[int] = Field(foreign_key="groupe.id", default=None)  # Si validé
    promotion_id: Optional[int] = Field(foreign_key="promotion.id", default=None)  # Si validé
    partenaire_id: Optional[int] = Field(foreign_key="partenaire.id", default=None)  # Si réorienté
    envoyer_mail_candidat: bool = Field(default=False)
    envoyer_mail_conseiller: bool = Field(default=False)
    envoyer_mail_partenaire: bool = Field(default=False)
    date_decision: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    cree_le: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    
    # Relations
    candidat: "Candidat" = Relationship()
    # Relation vers Jury - la clé étrangère est définie dans le Field ci-dessus
    jury: "Jury" = Relationship()
    conseiller: Optional["User"] = Relationship()
    groupe: Optional["Groupe"] = Relationship()
    promotion: Optional["Promotion"] = Relationship()
    partenaire: Optional["Partenaire"] = Relationship()
    reorientations: List["ReorientationCandidat"] = Relationship(back_populates="decision_jury")
