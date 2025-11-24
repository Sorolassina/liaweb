"""
Service de routage dynamique vers les schémas par programme
"""
from typing import Type, Any, Optional
from sqlmodel import SQLModel, Session
from ..models.base import (
    Candidat, Preinscription,
    Entreprise, Document, Eligibilite, DecisionJuryTable
)
import logging

logger = logging.getLogger(__name__)

class ProgramSchemaRouter:
    """Routeur dynamique pour les modèles par schéma de programme"""
    
    # Mapping des modèles par schéma
    SCHEMA_MODELS = {
        'candidats': Candidat,
        'preinscriptions': Preinscription,
        # 'inscriptions': Inscription,  # NOTE: Modèle Inscription supprimé
        'entreprises': Entreprise,
        'documents': Document,
        'eligibilites': Eligibilite,
        'jury_decisions': DecisionJuryTable,
    }
    
    @classmethod
    def get_model_for_schema(cls, table_name: str, schema_name: str) -> Type[SQLModel]:
        """Retourne le modèle approprié pour un schéma donné"""
        if table_name in cls.SCHEMA_MODELS:
            model_class = cls.SCHEMA_MODELS[table_name]
            
            # Créer une classe dynamique simple
            class DynamicModel(model_class):
                __tablename__ = f"{schema_name}.{table_name}"
                __table_args__ = {'extend_existing': True}
            
            return DynamicModel
        
        raise ValueError(f"Modèle non trouvé pour la table {table_name}")
    
    @classmethod
    def get_table_name_for_schema(cls, table_name: str, schema_name: str) -> str:
        """Retourne le nom de table complet avec schéma"""
        return f"{schema_name}.{table_name}"
    
    @classmethod
    def get_session_with_schema(cls, session: Session, schema_name: str) -> Session:
        """Retourne une session configurée pour un schéma spécifique"""
        # Configurer la session pour utiliser le schéma
        session.execute(f"SET search_path TO {schema_name}, public")
        return session
    
    @classmethod
    def query_with_schema(cls, session: Session, schema_name: str, model_class: Type[SQLModel], **filters):
        """Exécute une requête dans un schéma spécifique"""
        # Configurer le schéma
        cls.get_session_with_schema(session, schema_name)
        
        # Exécuter la requête
        query = session.query(model_class)
        
        for key, value in filters.items():
            if hasattr(model_class, key):
                query = query.filter(getattr(model_class, key) == value)
        
        return query.all()
    
    @classmethod
    def create_in_schema(cls, session: Session, schema_name: str, model_class: Type[SQLModel], **data):
        """Crée un enregistrement dans un schéma spécifique"""
        # Configurer le schéma
        cls.get_session_with_schema(session, schema_name)
        
        # Créer l'instance
        instance = model_class(**data)
        session.add(instance)
        session.commit()
        session.refresh(instance)
        
        return instance
    
    @classmethod
    def update_in_schema(cls, session: Session, schema_name: str, model_class: Type[SQLModel], 
                        record_id: int, **data):
        """Met à jour un enregistrement dans un schéma spécifique"""
        # Configurer le schéma
        cls.get_session_with_schema(session, schema_name)
        
        # Trouver l'enregistrement
        instance = session.get(model_class, record_id)
        if not instance:
            raise ValueError(f"Enregistrement {record_id} non trouvé dans {schema_name}")
        
        # Mettre à jour
        for key, value in data.items():
            if hasattr(instance, key):
                setattr(instance, key, value)
        
        session.commit()
        session.refresh(instance)
        
        return instance
    
    @classmethod
    def delete_from_schema(cls, session: Session, schema_name: str, model_class: Type[SQLModel], 
                          record_id: int):
        """Supprime un enregistrement d'un schéma spécifique"""
        # Configurer le schéma
        cls.get_session_with_schema(session, schema_name)
        
        # Trouver l'enregistrement
        instance = session.get(model_class, record_id)
        if not instance:
            raise ValueError(f"Enregistrement {record_id} non trouvé dans {schema_name}")
        
        # Supprimer
        session.delete(instance)
        session.commit()
        
        return True
