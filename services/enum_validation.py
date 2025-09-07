# app/services/enum_validation.py
"""
Service de validation et cohérence des enums
Vérifie la cohérence entre les enums Python et les données en base
"""

from typing import Dict, List, Set, Optional, Any
from sqlmodel import Session, select, text
from ..models.enums import *
from ..models.base import DecisionJuryCandidat, User, Programme
import logging

logger = logging.getLogger(__name__)

class EnumValidationService:
    """Service pour valider et maintenir la cohérence des enums"""
    
    def __init__(self, session: Session):
        self.session = session
    
    def validate_all_enums(self) -> Dict[str, Any]:
        """Valide tous les enums et retourne un rapport complet"""
        report = {
            "status": "success",
            "timestamp": None,
            "validations": {},
            "recommendations": [],
            "errors": []
        }
        
        try:
            # Validation des décisions de jury
            report["validations"]["decision_jury"] = self._validate_decision_jury()
            
            # Validation des groupes codev
            report["validations"]["groupe_codev"] = self._validate_groupe_codev()
            
            # Validation des types de documents
            report["validations"]["type_document"] = self._validate_type_document()
            
            # Validation des rôles utilisateurs
            report["validations"]["user_role"] = self._validate_user_role()
            
            # Générer les recommandations
            report["recommendations"] = self._generate_recommendations(report["validations"])
            
            # Déterminer le statut global
            has_errors = any(v.get("has_errors", False) for v in report["validations"].values())
            report["status"] = "error" if has_errors else "success"
            
        except Exception as e:
            logger.error(f"Erreur lors de la validation des enums: {e}")
            report["status"] = "error"
            report["errors"].append(str(e))
        
        return report
    
    def _validate_decision_jury(self) -> Dict[str, Any]:
        """Valide les décisions de jury"""
        result = {
            "enum_values": [d.value for d in DecisionJury],
            "db_values": set(),
            "invalid_values": [],
            "has_errors": False
        }
        
        # Récupérer toutes les valeurs uniques en base
        query = select(DecisionJuryCandidat.decision).distinct()
        db_decisions = self.session.exec(query).all()
        result["db_values"] = set(str(d) for d in db_decisions)
        
        # Vérifier les valeurs invalides
        valid_values = set(result["enum_values"])
        result["invalid_values"] = list(result["db_values"] - valid_values)
        result["has_errors"] = len(result["invalid_values"]) > 0
        
        return result
    
    def _validate_groupe_codev(self) -> Dict[str, Any]:
        """Valide les groupes de codéveloppement"""
        result = {
            "enum_values": [g.value for g in GroupeCodev],
            "db_values": set(),
            "invalid_values": [],
            "has_errors": False
        }
        
        # Récupérer toutes les valeurs uniques en base (non null)
        query = select(DecisionJuryCandidat.groupe_codev).where(
            DecisionJuryCandidat.groupe_codev.is_not(None)
        ).distinct()
        db_groupes = self.session.exec(query).all()
        result["db_values"] = set(g for g in db_groupes if g)
        
        # Vérifier les valeurs invalides
        valid_values = set(result["enum_values"])
        result["invalid_values"] = list(result["db_values"] - valid_values)
        result["has_errors"] = len(result["invalid_values"]) > 0
        
        return result
    
    def _validate_type_document(self) -> Dict[str, Any]:
        """Valide les types de documents"""
        result = {
            "enum_values": [t.value for t in TypeDocument],
            "db_values": set(),
            "invalid_values": [],
            "has_errors": False
        }
        
        # Récupérer toutes les valeurs uniques en base
        query = text("SELECT DISTINCT type_document FROM document WHERE type_document IS NOT NULL")
        db_types = self.session.exec(query).all()
        result["db_values"] = set(t[0] for t in db_types)
        
        # Vérifier les valeurs invalides
        valid_values = set(result["enum_values"])
        result["invalid_values"] = list(result["db_values"] - valid_values)
        result["has_errors"] = len(result["invalid_values"]) > 0
        
        return result
    
    def _validate_user_role(self) -> Dict[str, Any]:
        """Valide les rôles utilisateurs"""
        result = {
            "enum_values": [r.value for r in UserRole],
            "db_values": set(),
            "invalid_values": [],
            "has_errors": False
        }
        
        # Récupérer toutes les valeurs uniques en base
        query = select(User.role).distinct()
        db_roles = self.session.exec(query).all()
        result["db_values"] = set(str(r) for r in db_roles)
        
        # Vérifier les valeurs invalides
        valid_values = set(result["enum_values"])
        result["invalid_values"] = list(result["db_values"] - valid_values)
        result["has_errors"] = len(result["invalid_values"]) > 0
        
        return result
    
    def _generate_recommendations(self, validations: Dict[str, Any]) -> List[str]:
        """Génère des recommandations basées sur les validations"""
        recommendations = []
        
        for enum_name, validation in validations.items():
            if validation.get("has_errors", False):
                invalid_values = validation.get("invalid_values", [])
                if invalid_values:
                    recommendations.append(
                        f"Enum {enum_name}: Valeurs invalides détectées: {', '.join(invalid_values)}. "
                        f"Considérez les ajouter à l'enum ou migrer les données."
                    )
        
        return recommendations
    
    def fix_invalid_values(self, enum_name: str, mapping: Dict[str, str]) -> Dict[str, Any]:
        """Corrige les valeurs invalides en les mappant vers des valeurs valides"""
        result = {
            "success": False,
            "updated_count": 0,
            "errors": []
        }
        
        try:
            if enum_name == "groupe_codev":
                for old_value, new_value in mapping.items():
                    query = text("""
                        UPDATE decisionjurycandidat 
                        SET groupe_codev = :new_value 
                        WHERE groupe_codev = :old_value
                    """)
                    result_obj = self.session.exec(query, {
                        "old_value": old_value,
                        "new_value": new_value
                    })
                    result["updated_count"] += result_obj.rowcount
            
            self.session.commit()
            result["success"] = True
            
        except Exception as e:
            self.session.rollback()
            result["errors"].append(str(e))
            logger.error(f"Erreur lors de la correction des valeurs {enum_name}: {e}")
        
        return result
    
    def get_enum_usage_stats(self) -> Dict[str, Any]:
        """Retourne les statistiques d'utilisation des enums"""
        stats = {}
        
        # Statistiques des décisions de jury
        query = text("""
            SELECT decision, COUNT(*) as count 
            FROM decisionjurycandidat 
            GROUP BY decision 
            ORDER BY count DESC
        """)
        decision_stats = self.session.exec(query).all()
        stats["decision_jury"] = {row[0]: row[1] for row in decision_stats}
        
        # Statistiques des groupes codev
        query = text("""
            SELECT groupe_codev, COUNT(*) as count 
            FROM decisionjurycandidat 
            WHERE groupe_codev IS NOT NULL 
            GROUP BY groupe_codev 
            ORDER BY count DESC
        """)
        groupe_stats = self.session.exec(query).all()
        stats["groupe_codev"] = {row[0]: row[1] for row in groupe_stats}
        
        return stats
