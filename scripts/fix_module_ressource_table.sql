-- Script de correction de la table module_ressource dans tous les schémas de programme
-- Ce script corrige la structure pour correspondre au modèle Python :
-- - Supprime la colonne id (si elle existe)
-- - Définit module_id et ressource_id comme clés primaires composites
-- - Ajoute la colonne obligatoire si elle n'existe pas

DO $$
DECLARE
    schema_record RECORD;
    schema_name TEXT;
BEGIN
    -- Parcourir tous les schémas de programme
    FOR schema_record IN 
        SELECT s.schema_name 
        FROM information_schema.schemata s
        WHERE s.schema_name NOT IN ('information_schema', 'pg_catalog', 'pg_toast', 'public')
        AND s.schema_name NOT LIKE 'pg_%'
    LOOP
        schema_name := schema_record.schema_name;
        
        RAISE NOTICE 'Traitement du schéma: %', schema_name;
        
        -- Vérifier si la table existe
        IF EXISTS (
            SELECT 1 
            FROM information_schema.tables 
            WHERE table_schema = schema_name 
            AND table_name = 'module_ressource'
        ) THEN
            -- Supprimer la contrainte de clé primaire existante si elle existe
            BEGIN
                EXECUTE format('ALTER TABLE %I.module_ressource DROP CONSTRAINT IF EXISTS module_ressource_pkey', schema_name);
            EXCEPTION WHEN OTHERS THEN
                RAISE NOTICE 'Erreur lors de la suppression de la contrainte PK dans %: %', schema_name, SQLERRM;
            END;
            
            -- Supprimer la colonne id si elle existe
            BEGIN
                EXECUTE format('ALTER TABLE %I.module_ressource DROP COLUMN IF EXISTS id', schema_name);
            EXCEPTION WHEN OTHERS THEN
                RAISE NOTICE 'Erreur lors de la suppression de la colonne id dans %: %', schema_name, SQLERRM;
            END;
            
            -- Supprimer la séquence id si elle existe
            BEGIN
                EXECUTE format('DROP SEQUENCE IF EXISTS %I.module_ressource_id_seq CASCADE', schema_name);
            EXCEPTION WHEN OTHERS THEN
                RAISE NOTICE 'Erreur lors de la suppression de la séquence dans %: %', schema_name, SQLERRM;
            END;
            
            -- Ajouter la colonne obligatoire si elle n'existe pas
            BEGIN
                IF NOT EXISTS (
                    SELECT 1 
                    FROM information_schema.columns 
                    WHERE table_schema = schema_name 
                    AND table_name = 'module_ressource' 
                    AND column_name = 'obligatoire'
                ) THEN
                    EXECUTE format('ALTER TABLE %I.module_ressource ADD COLUMN obligatoire BOOLEAN DEFAULT TRUE', schema_name);
                    RAISE NOTICE 'Colonne obligatoire ajoutée dans %', schema_name;
                END IF;
            EXCEPTION WHEN OTHERS THEN
                RAISE NOTICE 'Erreur lors de l''ajout de la colonne obligatoire dans %: %', schema_name, SQLERRM;
            END;
            
            -- S'assurer que module_id et ressource_id existent et sont NOT NULL
            BEGIN
                EXECUTE format('ALTER TABLE %I.module_ressource ALTER COLUMN module_id SET NOT NULL', schema_name);
                EXECUTE format('ALTER TABLE %I.module_ressource ALTER COLUMN ressource_id SET NOT NULL', schema_name);
            EXCEPTION WHEN OTHERS THEN
                RAISE NOTICE 'Erreur lors de la modification des colonnes dans %: %', schema_name, SQLERRM;
            END;
            
            -- Créer la contrainte de clé primaire composite
            BEGIN
                EXECUTE format('ALTER TABLE %I.module_ressource ADD CONSTRAINT module_ressource_pkey PRIMARY KEY (module_id, ressource_id)', schema_name);
                RAISE NOTICE 'Clé primaire composite créée dans %', schema_name;
            EXCEPTION WHEN OTHERS THEN
                RAISE NOTICE 'Erreur lors de la création de la PK composite dans %: %', schema_name, SQLERRM;
            END;
            
            -- S'assurer que les contraintes de clé étrangère existent
            BEGIN
                -- Vérifier et créer FK vers module_elearning
                IF NOT EXISTS (
                    SELECT 1 
                    FROM information_schema.table_constraints 
                    WHERE constraint_schema = schema_name 
                    AND table_name = 'module_ressource' 
                    AND constraint_type = 'FOREIGN KEY'
                    AND constraint_name LIKE '%module_id%'
                ) THEN
                    EXECUTE format('ALTER TABLE %I.module_ressource ADD CONSTRAINT module_ressource_module_id_fkey FOREIGN KEY (module_id) REFERENCES %I.module_elearning(id) ON DELETE CASCADE', schema_name, schema_name);
                END IF;
                
                -- Vérifier et créer FK vers ressource_elearning
                IF NOT EXISTS (
                    SELECT 1 
                    FROM information_schema.table_constraints 
                    WHERE constraint_schema = schema_name 
                    AND table_name = 'module_ressource' 
                    AND constraint_type = 'FOREIGN KEY'
                    AND constraint_name LIKE '%ressource_id%'
                ) THEN
                    EXECUTE format('ALTER TABLE %I.module_ressource ADD CONSTRAINT module_ressource_ressource_id_fkey FOREIGN KEY (ressource_id) REFERENCES %I.ressource_elearning(id) ON DELETE CASCADE', schema_name, schema_name);
                END IF;
            EXCEPTION WHEN OTHERS THEN
                RAISE NOTICE 'Erreur lors de la création des FK dans %: %', schema_name, SQLERRM;
            END;
            
        ELSE
            -- Créer la table si elle n'existe pas
            BEGIN
                EXECUTE format('
                    CREATE TABLE %I.module_ressource (
                        module_id INTEGER NOT NULL REFERENCES %I.module_elearning(id) ON DELETE CASCADE,
                        ressource_id INTEGER NOT NULL REFERENCES %I.ressource_elearning(id) ON DELETE CASCADE,
                        ordre INTEGER DEFAULT 0,
                        obligatoire BOOLEAN DEFAULT TRUE,
                        PRIMARY KEY (module_id, ressource_id)
                    )', schema_name, schema_name, schema_name);
                RAISE NOTICE 'Table module_ressource créée dans %', schema_name;
            EXCEPTION WHEN OTHERS THEN
                RAISE NOTICE 'Erreur lors de la création de la table dans %: %', schema_name, SQLERRM;
            END;
        END IF;
        
    END LOOP;
    
    RAISE NOTICE 'Migration terminée pour tous les schémas';
END $$;

