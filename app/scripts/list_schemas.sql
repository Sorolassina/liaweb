-- Script SQL pour lister tous les schémas de la base de données
-- Utilisation: psql -U votre_user -d votre_db -f scripts/list_schemas.sql

-- Lister tous les schémas disponibles
SELECT 
    schema_name AS "Nom du schéma",
    schema_owner AS "Propriétaire",
    CASE 
        WHEN schema_name IN ('pg_catalog', 'information_schema', 'pg_toast', 'pg_temp_1', 'pg_toast_temp_1') THEN 'Système'
        WHEN schema_name = 'public' THEN 'Public'
        ELSE 'Programme'
    END AS "Type"
FROM information_schema.schemata
WHERE schema_name NOT LIKE 'pg_%' 
  AND schema_name != 'information_schema'
ORDER BY 
    CASE 
        WHEN schema_name = 'public' THEN 1
        ELSE 2
    END,
    schema_name;

-- Compter les schémas par type
SELECT 
    CASE 
        WHEN schema_name = 'public' THEN 'Public'
        ELSE 'Programme'
    END AS "Type de schéma",
    COUNT(*) AS "Nombre de schémas",
    STRING_AGG(schema_name, ', ' ORDER BY schema_name) AS "Noms des schémas"
FROM information_schema.schemata
WHERE schema_name NOT LIKE 'pg_%' 
  AND schema_name != 'information_schema'
GROUP BY 
    CASE 
        WHEN schema_name = 'public' THEN 'Public'
        ELSE 'Programme'
    END;

-- Lister les tables dans chaque schéma
SELECT 
    table_schema AS "Schéma",
    table_name AS "Table",
    table_type AS "Type"
FROM information_schema.tables
WHERE table_schema NOT IN ('pg_catalog', 'information_schema')
  AND table_schema NOT LIKE 'pg_%'
ORDER BY table_schema, table_name;

-- Détail des tables pour chaque schéma de programme
SELECT 
    table_schema AS "Schéma",
    COUNT(*) AS "Nombre de tables",
    STRING_AGG(table_name, ', ' ORDER BY table_name) AS "Tables"
FROM information_schema.tables
WHERE table_schema NOT IN ('pg_catalog', 'information_schema')
  AND table_schema NOT LIKE 'pg_%'
GROUP BY table_schema
ORDER BY table_schema;

