"""
Service de métriques pour les préinscriptions
Parcourt tous les schémas de programmes et récupère les données de préinscription
"""
from typing import Dict, List, Any, Optional
from sqlmodel import Session, text
from ...models.base import Programme
from . import SchemaDiscovery, get_program_schemas, get_session_for_metrics
from ...core.database import get_session
import logging

logger = logging.getLogger(__name__)



class PreinscriptionAnalyzer:
    """Classe pour analyser les données de préinscription dans un schéma spécifique."""
    
    def __init__(self, session: Session, schema_name: str):
        self.session = session
        self.schema_name = schema_name
        self.discovery = get_program_schemas()
    
    def has_preinscription_table(self) -> bool:
        """Vérifie si ce schéma a une table preinscription."""
        return self.discovery.schema_has_table(self.schema_name, "preinscription")
    
    def get_count_by_status(self) -> Dict[str, int]:
        """
        Récupère le nombre de préinscriptions par statut pour ce schéma.
        """
        try:
            if not self.has_preinscription_table():
                return {}
            
            result = self.session.execute(text(f"""
                SELECT statut, COUNT(*) as count
                FROM "{self.schema_name}".preinscription
                GROUP BY statut
                ORDER BY statut
            """))
            
            status_counts = {}
            for row in result.fetchall():
                status_counts[row[0]] = row[1]
            
            return status_counts
        except Exception as e:
            logger.error(f"Erreur lors de la récupération des préinscriptions pour {self.schema_name}: {e}")
            return {}
    
    def get_total_count(self) -> int:
        """Récupère le nombre total de préinscriptions."""
        try:
            if not self.has_preinscription_table():
                return 0
            
            result = self.session.execute(text(f"""
                SELECT COUNT(*) FROM "{self.schema_name}".preinscription
            """))
            return result.fetchone()[0]
        except Exception as e:
            logger.error(f"Erreur lors du comptage des préinscriptions pour {self.schema_name}: {e}")
            return 0
    
    def get_recent_count(self, days: int = 30) -> int:
        """Récupère le nombre de préinscriptions récentes."""
        try:
            if not self.has_preinscription_table():
                return 0
            
            result = self.session.execute(text(f"""
                SELECT COUNT(*) FROM "{self.schema_name}".preinscription
                WHERE date_preinscription >= CURRENT_DATE - INTERVAL '{days} days'
            """))
            return result.fetchone()[0]
        except Exception as e:
            logger.error(f"Erreur lors du comptage des préinscriptions récentes pour {self.schema_name}: {e}")
            return 0
    
    def get_monthly_trend(self, months: int = 12) -> List[Dict[str, Any]]:
        """Récupère la tendance mensuelle des préinscriptions."""
        try:
            if not self.has_preinscription_table():
                return []
            
            result = self.session.execute(text(f"""
                SELECT 
                    DATE_TRUNC('month', date_preinscription) as month,
                    COUNT(*) as count
                FROM "{self.schema_name}".preinscription
                WHERE date_preinscription >= CURRENT_DATE - INTERVAL '{months} months'
                GROUP BY DATE_TRUNC('month', date_preinscription)
                ORDER BY month
            """))
            
            monthly_data = []
            for row in result.fetchall():
                monthly_data.append({
                    "month": row[0].strftime("%Y-%m"),
                    "count": row[1]
                })
            
            return monthly_data
        except Exception as e:
            logger.error(f"Erreur lors de la récupération de la tendance mensuelle pour {self.schema_name}: {e}")
            return []
    
    def get_detailed_preinscriptions(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Récupère les détails des préinscriptions avec informations candidat."""
        try:
            if not self.has_preinscription_table():
                return []
            
            result = self.session.execute(text(f"""
                SELECT 
                    p.id,
                    p.date_preinscription,
                    p.statut,
                    p.motivation,
                    c.nom,
                    c.prenom,
                    c.email,
                    c.telephone
                FROM "{self.schema_name}".preinscription p
                JOIN "{self.schema_name}".candidat c ON p.candidat_id = c.id
                ORDER BY p.date_preinscription DESC
                LIMIT :limit
            """), {"limit": limit})
            
            preinscriptions = []
            for row in result.fetchall():
                preinscriptions.append({
                    "id": row[0],
                    "date_preinscription": row[1].isoformat() if row[1] else None,
                    "statut": row[2],
                    "motivation": row[3],
                    "candidat": {
                        "nom": row[4],
                        "prenom": row[5],
                        "email": row[6],
                        "telephone": row[7]
                    }
                })
            
            return preinscriptions
        except Exception as e:
            logger.error(f"Erreur lors de la récupération des détails pour {self.schema_name}: {e}")
            return []
    
    def get_all_metrics(self) -> Dict[str, Any]:
        """Récupère toutes les métriques pour ce schéma."""
        if not self.has_preinscription_table():
            return {"error": "Table preinscription non trouvée"}
        
        return {
            "total": self.get_total_count(),
            "status_distribution": self.get_count_by_status(),
            "recent_30_days": self.get_recent_count(30),
            "monthly_trend": self.get_monthly_trend(12),
            "schema_name": self.schema_name
        }


class PreinscriptionMetricsService:
    """Service principal pour les métriques de préinscription sur tous les schémas."""
    
    def __init__(self, session: Session):
        self.session = session
        self.discovery = get_program_schemas()
    
    def get_global_metrics(self) -> Dict[str, Any]:
        """
        Récupère les métriques de préinscription pour tous les schémas.
        """
        schemas = self.discovery.get_all_program_schemas()
        
        metrics = {
            "total_schemas": len(schemas),
            "schemas_with_preinscription": 0,
            "total_preinscriptions": 0,
            "status_distribution": {},
            "by_schema": {}
        }
        
        for schema_name in schemas:
            logger.info(f"📊 Analyse du schéma: {schema_name}")
            
            analyzer = PreinscriptionAnalyzer(self.session, schema_name)
            
            if analyzer.has_preinscription_table():
                metrics["schemas_with_preinscription"] += 1
                
                # Récupérer les données de préinscription pour ce schéma
                schema_data = analyzer.get_all_metrics()
                metrics["by_schema"][schema_name] = schema_data
                
                # Agréger les totaux
                schema_total = schema_data.get("total", 0)
                metrics["total_preinscriptions"] += schema_total
                
                # Agréger la distribution des statuts
                for status, count in schema_data.get("status_distribution", {}).items():
                    metrics["status_distribution"][status] = metrics["status_distribution"].get(status, 0) + count
                
                logger.info(f"✅ {schema_name}: {schema_total} préinscriptions")
            else:
                logger.info(f"⚠️  {schema_name}: Pas de table preinscription")
                metrics["by_schema"][schema_name] = {"error": "Table preinscription non trouvée"}
        
        return metrics
    
    def get_schema_metrics(self, schema_name: str) -> Dict[str, Any]:
        """Récupère les métriques pour un schéma spécifique."""
        analyzer = PreinscriptionAnalyzer(self.session, schema_name)
        return analyzer.get_all_metrics()
    
    def get_schema_details(self, schema_name: str, limit: int = 100) -> Dict[str, Any]:
        """Récupère les détails des préinscriptions pour un schéma spécifique."""
        analyzer = PreinscriptionAnalyzer(self.session, schema_name)
        
        if not analyzer.has_preinscription_table():
            return {"error": "Table preinscription non trouvée"}
        
        preinscriptions = analyzer.get_detailed_preinscriptions(limit)
        
        return {
            "schema_name": schema_name,
            "preinscriptions": preinscriptions,
            "count": len(preinscriptions)
        }
    
    def print_summary(self):
        """Affiche un résumé des préinscriptions dans le terminal."""
        print("\n" + "="*80)
        print("📊 RÉSUMÉ DES PRÉINSCRIPTIONS PAR SCHÉMA")
        print("="*80)
        
        metrics = self.get_global_metrics()
        
        print(f"\n📈 STATISTIQUES GLOBALES:")
        print(f"   • Total schémas analysés: {metrics['total_schemas']}")
        print(f"   • Schémas avec table preinscription: {metrics['schemas_with_preinscription']}")
        print(f"   • Total préinscriptions: {metrics['total_preinscriptions']}")
        
        if metrics['status_distribution']:
            print(f"\n📊 DISTRIBUTION PAR STATUT:")
            for status, count in metrics['status_distribution'].items():
                percentage = (count / metrics['total_preinscriptions'] * 100) if metrics['total_preinscriptions'] > 0 else 0
                print(f"   • {status}: {count} ({percentage:.1f}%)")
        
        print(f"\n📋 DÉTAIL PAR SCHÉMA:")
        for schema_name, data in metrics['by_schema'].items():
            if "error" in data:
                print(f"   ⚠️  {schema_name}: {data['error']}")
            else:
                print(f"   ✅ {schema_name}:")
                print(f"      • Total: {data['total']} préinscriptions")
                print(f"      • Récentes (30j): {data['recent_30_days']}")
                if data['status_distribution']:
                    status_str = ", ".join([f"{k}: {v}" for k, v in data['status_distribution'].items()])
                    print(f"      • Par statut: {status_str}")
        
        print("\n" + "="*80)



        """Exécute les tests du service de métriques."""
        print("🧪 Test du service de métriques de préinscription...")
        
        with get_session() as session:
            service = PreinscriptionMetricsService(session)
            service.print_summary()
            
            # Test avec un schéma spécifique
            discovery = get_program_schemas()
            schemas = discovery.get_all_program_schemas()
            
            if schemas:
                first_schema = schemas[0]
                print(f"\n🔍 Test détaillé pour le schéma: {first_schema}")
                details = service.get_schema_details(first_schema, limit=5)
                
                if "error" not in details:
                    print(f"   • Préinscriptions trouvées: {details['count']}")
                    for preinscription in details['preinscriptions']:
                        print(f"     - {preinscription['candidat']['nom']} {preinscription['candidat']['prenom']} ({preinscription['statut']})")
                else:
                    print(f"   ⚠️  {details['error']}")

# Fonctions de compatibilité supprimées - utiliser directement les classes
# PreinscriptionMetricsService pour les métriques
# SchemaDiscovery pour la découverte des schémas


if __name__ == "__main__":
    PreinscriptionMetricsTest.run_test()
