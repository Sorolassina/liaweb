\pset pager off
\set ON_ERROR_STOP on

-- Variables attendues (passées par -v côté psql) :
--   -v dbname=lia_coaching  -v appuser=liauser  -v apppass=liapass123
-- Astuce debug (optionnel) :
\echo [bootstrap] dbname= :'dbname' , appuser= :'appuser'

-- 1) Créer/synchroniser le rôle applicatif
SELECT CASE 
  WHEN EXISTS (SELECT 1 FROM pg_roles WHERE rolname = :'appuser') THEN
    format('ALTER ROLE %I WITH LOGIN PASSWORD %L', :'appuser', :'apppass')
  ELSE
    format('CREATE ROLE %I WITH LOGIN PASSWORD %L', :'appuser', :'apppass')
  END AS sql_cmd
\gexec

-- 2) Créer la base en UTF-8 via template0 si absente
SELECT CASE 
  WHEN NOT EXISTS (SELECT 1 FROM pg_database WHERE datname = :'dbname') THEN
    format('CREATE DATABASE %I OWNER %I ENCODING ''UTF8'' TEMPLATE template0', :'dbname', :'appuser')
  ELSE
    'SELECT 1' -- Ne rien faire si la base existe déjà
  END AS sql_cmd
\gexec

-- 3) Accorder les privilèges DB
SELECT format('GRANT ALL PRIVILEGES ON DATABASE %I TO %I', :'dbname', :'appuser') AS sql_cmd
\gexec

-- 4) Schéma public et privilèges par défaut
\connect :dbname

SELECT format('ALTER SCHEMA public OWNER TO %I', :'appuser') AS sql_cmd
\gexec

SELECT format('GRANT ALL ON SCHEMA public TO %I', :'appuser') AS sql_cmd
\gexec

SELECT format('GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO %I', :'appuser') AS sql_cmd
\gexec

SELECT format('GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO %I', :'appuser') AS sql_cmd
\gexec

SELECT format('ALTER DEFAULT PRIVILEGES FOR ROLE %I IN SCHEMA public GRANT ALL ON TABLES TO %I', :'appuser', :'appuser') AS sql_cmd
\gexec

SELECT format('ALTER DEFAULT PRIVILEGES FOR ROLE %I IN SCHEMA public GRANT ALL ON SEQUENCES TO %I', :'appuser', :'appuser') AS sql_cmd
\gexec

SHOW server_encoding;
SELECT current_database() AS db, current_user AS usr;
