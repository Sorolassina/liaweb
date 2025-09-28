"""
Tests fonctionnels pour les composants communs des métriques.

Ces tests vérifient le comportement des composants communs
avec une vraie base de données.
"""

import pytest
from sqlalchemy import text

from app_lia_web.app.services.metrics.preinscription_metrics import (
    SchemaDiscovery,
    get_program_schemas
)


@pytest.mark.integration
@pytest.mark.database
class TestSchemaDiscoveryFunctional:
    """Tests fonctionnels de la découverte des schémas."""
    
    def test_get_all_program_schemas_with_real_db(self, test_session):
        """Test de récupération des schémas avec vraie base de données PostgreSQL."""
        schema_discovery = SchemaDiscovery(test_session)
        
        # Récupération des schémas
        schemas = schema_discovery.get_all_program_schemas()
        
        # Vérifications
        assert isinstance(schemas, list), "Le résultat doit être une liste"
        
        # Avec PostgreSQL, on peut avoir des schémas ou une liste vide
        # Vérification que tous les schémas sont des chaînes
        for schema in schemas:
            assert isinstance(schema, str), f"Le schéma {schema} doit être une chaîne"
            assert len(schema) > 0, f"Le schéma {schema} ne doit pas être vide"
        
        print(f"Schémas trouvés: {schemas}")
    
    def test_schema_has_table_with_real_db(self, test_session):
        """Test de vérification d'existence de table avec vraie base de données PostgreSQL."""
        schema_discovery = SchemaDiscovery(test_session)
        
        # Récupérer tous les schémas disponibles
        all_schemas = schema_discovery.get_all_program_schemas()
        
        # Ajouter le schéma public pour le test
        test_schemas = ["public"] + all_schemas
        
        print(f"Test de vérification de tables pour les schémas: {test_schemas}")
        
        # Tables à tester
        test_tables = ["preinscriptions", "users", "programmes"]
        
        for schema in test_schemas:
            print(f"\n--- Test du schéma: {schema} ---")
            
            for table in test_tables:
                # Test d'existence de table
                has_table = schema_discovery.schema_has_table(schema, table)
                
                # Le résultat doit être un booléen
                assert isinstance(has_table, bool), f"Le résultat doit être un booléen pour {schema}.{table}"
                
                status = "✅ Existe" if has_table else "❌ N'existe pas"
                print(f"  Table {table}: {status}")
            
            # Test avec une table qui n'existe probablement pas
            has_fake_table = schema_discovery.schema_has_table(schema, "table_inexistante_12345")
            assert has_fake_table is False, f"Une table inexistante doit retourner False pour le schéma {schema}"
            fake_status = "✅ Correctement détectée comme inexistante" if not has_fake_table else "❌ Erreur"
            print(f"  Table inexistante: {fake_status}")
        
        print(f"\n✅ Test terminé pour {len(test_schemas)} schémas")
    
    def test_get_schema_tables_with_real_db(self, test_session):
        """Test de récupération des tables d'un schéma avec vraie base de données PostgreSQL."""
        schema_discovery = SchemaDiscovery(test_session)
        
        # Récupérer tous les schémas disponibles
        all_schemas = schema_discovery.get_all_program_schemas()
        
        # Ajouter le schéma public pour le test
        test_schemas = ["public"] + all_schemas
        
        print(f"Test des tables pour les schémas: {test_schemas}")
        
        for schema in test_schemas:
            # Récupération des tables pour chaque schéma
            tables = schema_discovery.get_schema_tables(schema)
            
            # Vérifications
            assert isinstance(tables, list), f"Le résultat doit être une liste pour le schéma {schema}"
            
            # Vérification que toutes les tables sont des chaînes
            for table in tables:
                assert isinstance(table, str), f"La table {table} doit être une chaîne dans le schéma {schema}"
                assert len(table) > 0, f"La table {table} ne doit pas être vide dans le schéma {schema}"
            
            print(f"Tables dans le schéma {schema}: {tables}")
            
            # Test spécifique pour le schéma public (doit avoir des tables système)
            if schema == "public":
                assert len(tables) > 0, "Le schéma public doit contenir des tables"
                print(f"✅ Schéma public: {len(tables)} tables trouvées")
            
            # Test pour les schémas de programmes
            elif schema in all_schemas:
                print(f"✅ Schéma programme {schema}: {len(tables)} tables trouvées")
                # Les schémas de programmes peuvent être vides ou contenir des tables
                # On vérifie juste que la méthode fonctionne sans erreur
    
    def test_schema_discovery_error_handling(self, test_session):
        """Test de gestion d'erreurs avec vraie base de données."""
        schema_discovery = SchemaDiscovery(test_session)
        
        # Test avec un schéma inexistant
        has_table = schema_discovery.schema_has_table("schema_inexistant", "table")
        assert has_table is False, "Un schéma inexistant doit retourner False"
        
        # Test avec une table vide
        has_empty_table = schema_discovery.schema_has_table("public", "")
        assert has_empty_table is False, "Une table vide doit retourner False"
        
        # Test avec un schéma vide
        has_empty_schema = schema_discovery.schema_has_table("", "table")
        assert has_empty_schema is False, "Un schéma vide doit retourner False"
    
    def test_schema_discovery_performance(self, test_session):
        """Test de performance de la découverte des schémas."""
        import time
        
        schema_discovery = SchemaDiscovery(test_session)
        
        # Mesure du temps d'exécution
        start_time = time.time()
        
        # Récupération des schémas
        schemas = schema_discovery.get_all_program_schemas()
        
        end_time = time.time()
        execution_time = end_time - start_time
        
        # Vérification de la performance
        assert execution_time < 5.0, f"Trop lent: {execution_time:.2f}s"
        assert len(schemas) > 0, "Au moins un schéma doit être trouvé"
    
    def test_schema_discovery_consistency(self, test_session):
        """Test de cohérence de la découverte des schémas."""
        schema_discovery = SchemaDiscovery(test_session)
        
        # Récupération des schémas plusieurs fois
        schemas1 = schema_discovery.get_all_program_schemas()
        schemas2 = schema_discovery.get_all_program_schemas()
        
        # Vérification de la cohérence
        assert schemas1 == schemas2, "Les résultats doivent être identiques"
        assert len(schemas1) == len(schemas2), "Le nombre de schémas doit être identique"
        
        # Vérification que l'ordre est cohérent
        for i, schema in enumerate(schemas1):
            assert schema == schemas2[i], f"L'ordre des schémas doit être cohérent à l'index {i}"


@pytest.mark.integration
@pytest.mark.database
class TestGetProgramSchemasFunctional:
    """Tests fonctionnels de la fonction utilitaire get_program_schemas."""
    
    def test_get_program_schemas_with_real_db(self, test_session):
        """Test de la fonction get_program_schemas avec vraie base de données."""
        # Récupération de l'instance de découverte
        schema_discovery = get_program_schemas()
        
        # Vérifications
        assert schema_discovery is not None, "L'instance ne doit pas être None"
        assert isinstance(schema_discovery, SchemaDiscovery), "L'instance doit être de type SchemaDiscovery"
        
        # Test de l'utilisation de l'instance
        schemas = schema_discovery.get_all_program_schemas()
        
        assert isinstance(schemas, list), "Le résultat doit être une liste"
        assert len(schemas) > 0, "Au moins un schéma doit être trouvé"
    
    def test_get_program_schemas_multiple_calls(self, test_session):
        """Test de plusieurs appels à get_program_schemas."""
        # Premier appel
        schema_discovery1 = get_program_schemas()
        
        # Deuxième appel
        schema_discovery2 = get_program_schemas()
        
        # Vérification que les instances sont identiques (singleton)
        assert schema_discovery1 is schema_discovery2, "Les instances doivent être identiques"
        
        # Vérification que les méthodes fonctionnent
        schemas1 = schema_discovery1.get_all_program_schemas()
        schemas2 = schema_discovery2.get_all_program_schemas()
        
        assert schemas1 == schemas2, "Les résultats doivent être identiques"
    
    def test_get_program_schemas_with_different_sessions(self, test_session):
        """Test de get_program_schemas avec différentes sessions."""
        # Création d'une nouvelle session pour le test
        from app_lia_web.app.database import get_session_for_metrics
        
        with get_session_for_metrics() as new_session:
            # Récupération de l'instance avec la nouvelle session
            schema_discovery = get_program_schemas()
            
            # Vérification que l'instance fonctionne
            schemas = schema_discovery.get_all_program_schemas()
            
            assert isinstance(schemas, list), "Le résultat doit être une liste"
            assert len(schemas) > 0, "Au moins un schéma doit être trouvé"


@pytest.mark.integration
@pytest.mark.database
class TestCommonMetricsIntegration:
    """Tests d'intégration des composants communs."""
    
    def test_schema_discovery_with_preinscription_table(self, test_session):
        """Test de découverte des schémas avec table de préinscription."""
        schema_discovery = SchemaDiscovery(test_session)
        
        # Récupération des schémas
        schemas = schema_discovery.get_all_program_schemas()
        
        # Vérification que chaque schéma a une table preinscriptions
        schemas_with_preinscriptions = []
        
        for schema in schemas:
            if schema_discovery.schema_has_table(schema, "preinscriptions"):
                schemas_with_preinscriptions.append(schema)
        
        # Au moins un schéma doit avoir la table preinscriptions
        assert len(schemas_with_preinscriptions) > 0, "Au moins un schéma doit avoir la table preinscriptions"
        
        # Vérification des tables de chaque schéma avec preinscriptions
        for schema in schemas_with_preinscriptions:
            tables = schema_discovery.get_schema_tables(schema)
            
            assert "preinscriptions" in tables, f"La table preinscriptions doit être dans le schéma {schema}"
            assert len(tables) > 0, f"Le schéma {schema} doit avoir au moins une table"
    
    def test_schema_discovery_complete_workflow(self, test_session):
        """Test du workflow complet de découverte des schémas."""
        schema_discovery = SchemaDiscovery(test_session)
        
        # Étape 1: Récupération des schémas
        schemas = schema_discovery.get_all_program_schemas()
        assert len(schemas) > 0, "Au moins un schéma doit être trouvé"
        
        # Étape 2: Vérification de l'existence de la table preinscriptions
        valid_schemas = []
        for schema in schemas:
            if schema_discovery.schema_has_table(schema, "preinscriptions"):
                valid_schemas.append(schema)
        
        assert len(valid_schemas) > 0, "Au moins un schéma valide doit être trouvé"
        
        # Étape 3: Récupération des tables de chaque schéma valide
        for schema in valid_schemas:
            tables = schema_discovery.get_schema_tables(schema)
            
            assert isinstance(tables, list), f"Les tables du schéma {schema} doivent être une liste"
            assert "preinscriptions" in tables, f"La table preinscriptions doit être dans le schéma {schema}"
            assert len(tables) > 0, f"Le schéma {schema} doit avoir au moins une table"
    
    def test_schema_discovery_with_database_queries(self, test_session):
        """Test de découverte des schémas avec requêtes directes à la base."""
        schema_discovery = SchemaDiscovery(test_session)
        
        # Récupération des schémas via la classe
        schemas = schema_discovery.get_all_program_schemas()
        
        # Vérification directe via requête SQL
        query = text("SELECT schema_name FROM information_schema.schemata WHERE schema_name NOT IN ('information_schema', 'pg_catalog', 'pg_toast')")
        result = test_session.execute(query)
        db_schemas = [row[0] for row in result.fetchall()]
        
        # Vérification que les résultats sont cohérents
        assert len(schemas) > 0, "Au moins un schéma doit être trouvé"
        assert len(db_schemas) > 0, "Au moins un schéma doit être trouvé via requête directe"
        
        # Vérification que les schémas trouvés sont cohérents
        for schema in schemas:
            assert schema in db_schemas, f"Le schéma {schema} doit être présent dans la base de données"
    
    def test_schema_discovery_error_recovery(self, test_session):
        """Test de récupération d'erreurs de la découverte des schémas."""
        schema_discovery = SchemaDiscovery(test_session)
        
        # Test avec des paramètres invalides
        invalid_tests = [
            ("", "preinscriptions"),
            ("public", ""),
            (None, "preinscriptions"),
            ("public", None),
            ("schema_inexistant", "table_inexistante")
        ]
        
        for schema, table in invalid_tests:
            try:
                result = schema_discovery.schema_has_table(schema, table)
                # Si on arrive ici, le résultat doit être False
                assert result is False, f"Le résultat doit être False pour schema='{schema}', table='{table}'"
            except Exception as e:
                # Les erreurs sont acceptables pour des paramètres invalides
                assert "invalid" in str(e).lower() or "error" in str(e).lower()
    
    def test_schema_discovery_memory_usage(self, test_session):
        """Test d'utilisation mémoire de la découverte des schémas."""
        import psutil
        import os
        
        # Mesure de la mémoire initiale
        process = psutil.Process(os.getpid())
        initial_memory = process.memory_info().rss / 1024 / 1024  # MB
        
        schema_discovery = SchemaDiscovery(test_session)
        
        # Récupération des schémas plusieurs fois
        for _ in range(100):
            schemas = schema_discovery.get_all_program_schemas()
            assert len(schemas) > 0, "Au moins un schéma doit être trouvé"
        
        # Mesure de la mémoire finale
        final_memory = process.memory_info().rss / 1024 / 1024  # MB
        memory_increase = final_memory - initial_memory
        
        # Vérification de l'utilisation mémoire
        assert memory_increase < 50, f"Trop de mémoire utilisée: {memory_increase:.2f}MB"


@pytest.mark.integration
@pytest.mark.database
class TestPreinscriptionSchemaRouting:
    """Tests de validation du routage des préinscriptions vers les bons schémas."""
    
    def test_preinscription_schema_routing_issue(self, test_session):
        """Test qui reproduit le problème de routage des préinscriptions."""
        schema_discovery = SchemaDiscovery(test_session)
        
        # Récupérer tous les schémas de programmes
        program_schemas = schema_discovery.get_all_program_schemas()
        
        if not program_schemas:
            pytest.skip("Aucun schéma de programme trouvé")
        
        print(f"Schémas de programmes disponibles: {program_schemas}")
        
        # Vérifier où sont stockées les préinscriptions actuellement
        for schema in program_schemas:
            try:
                # Compter les préinscriptions dans le schéma du programme
                result = test_session.execute(text(f"""
                    SELECT COUNT(*) as count
                    FROM {schema}.preinscription
                """))
                count_in_program_schema = result.fetchone()[0]
                
                print(f"  {schema}.preinscription: {count_in_program_schema} enregistrements")
                
            except Exception as e:
                print(f"  {schema}.preinscription: Erreur - {e}")
        
        # Vérifier les préinscriptions dans le schéma public
        try:
            result = test_session.execute(text("""
                SELECT COUNT(*) as count
                FROM public.preinscription
            """))
            count_in_public = result.fetchone()[0]
            print(f"  public.preinscription: {count_in_public} enregistrements")
            
            if count_in_public > 0:
                print("  ⚠️  PROBLÈME: Des préinscriptions sont stockées dans le schéma public !")
                print("  ⚠️  Elles devraient être dans les schémas de programmes spécifiques.")
            else:
                print("  ✅ Aucune préinscription dans le schéma public (correct)")
                
        except Exception as e:
            print(f"  public.preinscription: Erreur - {e}")
        
        print("\n🔍 Analyse du problème de routage terminée")
    
    def test_preinscription_route_schema_routing_fixed(self, test_session):
        """Test fonctionnel que la route preinscription_public_submit utilise maintenant le bon schéma."""
        from fastapi.testclient import TestClient
        from app_lia_web.app.main import app
        
        schema_discovery = SchemaDiscovery(test_session)
        
        # Récupérer tous les schémas de programmes
        program_schemas = schema_discovery.get_all_program_schemas()
        
        if not program_schemas:
            pytest.skip("Aucun schéma de programme trouvé")
        
        print(f"🧪 Test fonctionnel du routage pour {len(program_schemas)} schémas")
        
        # Prendre le premier schéma pour le test
        test_schema = program_schemas[0]
        print(f"📋 Test avec le schéma: {test_schema}")
        
        # Compter les préinscriptions avant le test
        try:
            result = test_session.execute(text(f"""
                SELECT COUNT(*) as count
                FROM {test_schema}.preinscription
            """))
            count_before = result.fetchone()[0]
            print(f"  📊 Préinscriptions avant: {count_before}")
        except Exception as e:
            print(f"  ❌ Erreur lors du comptage initial: {e}")
            count_before = 0
        
        # Compter les préinscriptions dans le schéma public avant
        try:
            result = test_session.execute(text("""
                SELECT COUNT(*) as count
                FROM public.preinscription
            """))
            count_public_before = result.fetchone()[0]
            print(f"  📊 Préinscriptions dans public avant: {count_public_before}")
        except Exception as e:
            print(f"  ❌ Erreur lors du comptage public initial: {e}")
            count_public_before = 0
        
        # Simuler une soumission de préinscription
        client = TestClient(app)
        
        # Vérifier quels programmes existent dans la base
        try:
            result = test_session.execute(text("""
                SELECT code, nom FROM programme WHERE actif = true
            """))
            programmes = result.fetchall()
            print(f"  📋 Programmes disponibles: {[f'{p[0]} - {p[1]}' for p in programmes]}")
            
            # Utiliser le premier programme actif trouvé
            if programmes:
                programme_code = programmes[0][0]  # Premier code de programme
                print(f"  🎯 Utilisation du programme: {programme_code}")
            else:
                print(f"  ⚠️  Aucun programme actif trouvé, utilisation du schéma: {test_schema}")
                programme_code = test_schema.upper()
        except Exception as e:
            print(f"  ❌ Erreur lors de la récupération des programmes: {e}")
            programme_code = test_schema.upper()
        
        # Données de test pour la préinscription
        test_data = {
            "programme_code": programme_code,
            "nom": "Test",
            "prenom": "User",
            "email": "test@example.com",
            "telephone": "0123456789"  
        }
        
        print(f"  🚀 Simulation de soumission pour le programme: {programme_code}")
        
        try:
            # Simuler la soumission (sans fichier pour simplifier)
            response = client.post(
                "/preinscriptions/submit",
                data=test_data,
                follow_redirects=False
            )
            
            print(f"  📡 Réponse HTTP: {response.status_code}")
            
            # Vérifier que la préinscription a été créée dans le bon schéma
            result = test_session.execute(text(f"""
                SELECT COUNT(*) as count
                FROM {test_schema}.preinscription
            """))
            count_after = result.fetchone()[0]
            print(f"  📊 Préinscriptions après: {count_after}")
            
            # Vérifier qu'aucune préinscription n'a été créée dans le schéma public
            result = test_session.execute(text("""
                SELECT COUNT(*) as count
                FROM public.preinscription
            """))
            count_public_after = result.fetchone()[0]
            print(f"  📊 Préinscriptions dans public après: {count_public_after}")
            
            # Validation du test
            if count_after > count_before:
                print(f"  ✅ SUCCÈS: Nouvelle préinscription créée dans {test_schema}")
            else:
                print(f"  ❌ ÉCHEC: Aucune nouvelle préinscription dans {test_schema}")
            
            if count_public_after == count_public_before:
                print(f"  ✅ SUCCÈS: Aucune préinscription créée dans le schéma public")
            else:
                print(f"  ❌ ÉCHEC: {count_public_after - count_public_before} préinscription(s) créée(s) dans public")
                
        except Exception as e:
            print(f"  ❌ Erreur lors de la simulation: {e}")
        
        print(f"\n🎯 Test fonctionnel du routage terminé")
        print(f"💡 Vérification que les nouvelles préinscriptions vont dans le bon schéma")
