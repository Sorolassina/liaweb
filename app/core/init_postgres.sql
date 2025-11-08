\pset pager off
\set ON_ERROR_STOP on

-- ============================================================================
-- SCRIPT D'INITIALISATION POSTGRESQL OPTIMISÉ POUR LIA COACHING
-- ============================================================================
-- Variables attendues (passées par -v côté psql) :
--   -v dbname=lia_coaching  -v appuser=liauser  -v apppass=liapass123
-- ============================================================================

\echo [BOOTSTRAP] Démarrage de l'initialisation PostgreSQL
\echo [BOOTSTRAP] Base: :'dbname' | Utilisateur: :'appuser'

-- ============================================================================
-- ÉTAPE 1: CRÉATION/SYNCHRONISATION DU RÔLE APPLICATIF
-- ============================================================================
\echo [ÉTAPE 1] Création/synchronisation du rôle applicatif...

-- Créer ou mettre à jour le rôle avec tous les privilèges nécessaires
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = :'appuser') THEN
        EXECUTE format('ALTER ROLE %I WITH LOGIN PASSWORD %L CREATEDB CREATEROLE', :'appuser', :'apppass');
        RAISE NOTICE 'Rôle % mis à jour', :'appuser';
    ELSE
        EXECUTE format('CREATE ROLE %I WITH LOGIN PASSWORD %L CREATEDB CREATEROLE', :'appuser', :'apppass');
        RAISE NOTICE 'Rôle % créé', :'appuser';
    END IF;
END $$;

-- ============================================================================
-- ÉTAPE 2: CRÉATION DE LA BASE DE DONNÉES
-- ============================================================================
\echo [ÉTAPE 2] Création de la base de données...

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_database WHERE datname = :'dbname') THEN
        EXECUTE format('CREATE DATABASE %I OWNER %I ENCODING ''UTF8'' TEMPLATE template0 LC_COLLATE ''C'' LC_CTYPE ''C''', :'dbname', :'appuser');
        RAISE NOTICE 'Base de données % créée', :'dbname';
    ELSE
        RAISE NOTICE 'Base de données % existe déjà', :'dbname';
    END IF;
END $$;

-- ============================================================================
-- ÉTAPE 3: CONNEXION À LA BASE ET CONFIGURATION DES PRIVILÈGES
-- ============================================================================
\echo [ÉTAPE 3] Connexion à la base et configuration des privilèges...

\connect :dbname

-- Configuration des privilèges de base
GRANT ALL PRIVILEGES ON DATABASE :dbname TO :appuser;
GRANT CREATE ON DATABASE :dbname TO :appuser;

-- ============================================================================
-- ÉTAPE 4: CONFIGURATION DU SCHÉMA PUBLIC
-- ============================================================================
\echo [ÉTAPE 4] Configuration du schéma public...

-- Propriétaire et privilèges du schéma public
ALTER SCHEMA public OWNER TO :appuser;
GRANT ALL ON SCHEMA public TO :appuser;

-- Privilèges sur les objets existants
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO :appuser;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO :appuser;
GRANT ALL PRIVILEGES ON ALL FUNCTIONS IN SCHEMA public TO :appuser;

-- Privilèges par défaut pour les futurs objets
ALTER DEFAULT PRIVILEGES FOR ROLE :appuser IN SCHEMA public GRANT ALL ON TABLES TO :appuser;
ALTER DEFAULT PRIVILEGES FOR ROLE :appuser IN SCHEMA public GRANT ALL ON SEQUENCES TO :appuser;
ALTER DEFAULT PRIVILEGES FOR ROLE :appuser IN SCHEMA public GRANT ALL ON FUNCTIONS TO :appuser;

-- ============================================================================
-- ÉTAPE 5: CONFIGURATION DES SCHÉMAS PAR PROGRAMME (OPTIMISÉE)
-- ============================================================================
\echo [ÉTAPE 5] Configuration des schémas par programme...

-- Fonction optimisée pour configurer tous les schémas en une seule transaction
DO $$
DECLARE
    schema_record RECORD;
    system_schemas TEXT[] := ARRAY['information_schema', 'pg_catalog', 'pg_toast', 'pg_temp_1', 'pg_toast_temp_1'];
BEGIN
    -- Parcourir tous les schémas non-système de cette base
    FOR schema_record IN 
        SELECT schema_name 
        FROM information_schema.schemata 
        WHERE schema_name != ALL(system_schemas)
        AND catalog_name = :'dbname'
    LOOP
        -- Accorder les privilèges sur le schéma
        EXECUTE format('GRANT ALL ON SCHEMA %I TO %I', schema_record.schema_name, :'appuser');
        
        -- Accorder les privilèges sur tous les objets existants
        EXECUTE format('GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA %I TO %I', schema_record.schema_name, :'appuser');
        EXECUTE format('GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA %I TO %I', schema_record.schema_name, :'appuser');
        EXECUTE format('GRANT ALL PRIVILEGES ON ALL FUNCTIONS IN SCHEMA %I TO %I', schema_record.schema_name, :'appuser');
        
        -- Configurer les privilèges par défaut pour les futurs objets
        EXECUTE format('ALTER DEFAULT PRIVILEGES FOR ROLE %I IN SCHEMA %I GRANT ALL ON TABLES TO %I', :'appuser', schema_record.schema_name, :'appuser');
        EXECUTE format('ALTER DEFAULT PRIVILEGES FOR ROLE %I IN SCHEMA %I GRANT ALL ON SEQUENCES TO %I', :'appuser', schema_record.schema_name, :'appuser');
        EXECUTE format('ALTER DEFAULT PRIVILEGES FOR ROLE %I IN SCHEMA %I GRANT ALL ON FUNCTIONS TO %I', :'appuser', schema_record.schema_name, :'appuser');
        
        RAISE NOTICE 'Schéma % configuré', schema_record.schema_name;
    END LOOP;
END $$;

-- ============================================================================
-- ÉTAPE 6: CONFIGURATION DES EXTENSIONS ET OPTIMISATIONS
-- ============================================================================
\echo [ÉTAPE 6] Configuration des extensions...

-- Créer les extensions utiles si elles n'existent pas
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";
CREATE EXTENSION IF NOT EXISTS "unaccent";

-- Accorder les privilèges sur les extensions
GRANT USAGE ON SCHEMA public TO :appuser;

-- ============================================================================
-- ÉTAPE 7: VÉRIFICATION ET RAPPORT FINAL
-- ============================================================================
\echo [ÉTAPE 7] Vérification finale...

-- Afficher les informations de configuration
SELECT 
    'Configuration finale' AS status,
    current_database() AS database,
    current_user AS user,
    version() AS postgresql_version,
    server_encoding AS encoding;

-- Vérifier les privilèges accordés
SELECT 
    'Privilèges accordés' AS status,
    schemaname,
    tablename,
    privilege_type
FROM information_schema.table_privileges 
WHERE grantee = :'appuser'
AND table_schema NOT IN ('information_schema', 'pg_catalog', 'pg_toast')
ORDER BY schemaname, tablename
LIMIT 10;

\echo [BOOTSTRAP] ✅ Initialisation PostgreSQL terminée avec succès !
\echo [BOOTSTRAP] Base: :'dbname' | Utilisateur: :'appuser' | Privilèges: CONFIGURÉS