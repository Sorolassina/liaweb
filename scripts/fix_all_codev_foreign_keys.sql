-- Script combiné pour corriger toutes les contraintes de clé étrangère du module Codev
-- Ces contraintes pointent actuellement vers inscription mais doivent pointer vers candidat
-- 
-- Exécutez ce script dans votre base de données PostgreSQL pour corriger toutes les contraintes

-- Pour chaque schéma de programme (acd, etc.)
DO $$
DECLARE
    schema_rec RECORD;
    constraint_exists BOOLEAN;
BEGIN
    -- Parcourir tous les schémas qui contiennent des tables codev
    FOR schema_rec IN 
        SELECT DISTINCT table_schema as schema_name
        FROM information_schema.tables 
        WHERE table_name IN ('membre_groupe_codev', 'presentation_codev', 'contribution_codev')
        AND table_schema NOT IN ('information_schema', 'pg_catalog', 'pg_toast', 'public')
    LOOP
        RAISE NOTICE '========================================';
        RAISE NOTICE 'Traitement du schéma: %', schema_rec.schema_name;
        RAISE NOTICE '========================================';
        
        -- 1. Corriger membre_groupe_codev_candidat_id_fkey
        IF EXISTS (
            SELECT 1 FROM information_schema.tables 
            WHERE table_schema = schema_rec.schema_name AND table_name = 'membre_groupe_codev'
        ) THEN
            SELECT EXISTS (
                SELECT 1 
                FROM information_schema.table_constraints tc
                WHERE tc.table_schema = schema_rec.schema_name
                AND tc.table_name = 'membre_groupe_codev'
                AND tc.constraint_name = 'membre_groupe_codev_candidat_id_fkey'
            ) INTO constraint_exists;
            
            IF constraint_exists THEN
                EXECUTE format('ALTER TABLE %I.membre_groupe_codev DROP CONSTRAINT IF EXISTS membre_groupe_codev_candidat_id_fkey', schema_rec.schema_name);
                RAISE NOTICE '✓ Contrainte membre_groupe_codev_candidat_id_fkey supprimée';
            END IF;
            
            IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_schema = schema_rec.schema_name AND table_name = 'candidat') THEN
                EXECUTE format('
                    ALTER TABLE %I.membre_groupe_codev 
                    ADD CONSTRAINT membre_groupe_codev_candidat_id_fkey 
                    FOREIGN KEY (candidat_id) 
                    REFERENCES %I.candidat(id) 
                    ON DELETE CASCADE
                ', schema_rec.schema_name, schema_rec.schema_name);
                RAISE NOTICE '✓ Contrainte membre_groupe_codev_candidat_id_fkey créée';
            ELSE
                RAISE WARNING '✗ Table candidat non trouvée dans le schéma: %', schema_rec.schema_name;
            END IF;
        END IF;
        
        -- 2. Corriger presentation_codev_candidat_id_fkey
        IF EXISTS (
            SELECT 1 FROM information_schema.tables 
            WHERE table_schema = schema_rec.schema_name AND table_name = 'presentation_codev'
        ) THEN
            SELECT EXISTS (
                SELECT 1 
                FROM information_schema.table_constraints tc
                WHERE tc.table_schema = schema_rec.schema_name
                AND tc.table_name = 'presentation_codev'
                AND tc.constraint_name = 'presentation_codev_candidat_id_fkey'
            ) INTO constraint_exists;
            
            IF constraint_exists THEN
                EXECUTE format('ALTER TABLE %I.presentation_codev DROP CONSTRAINT IF EXISTS presentation_codev_candidat_id_fkey', schema_rec.schema_name);
                RAISE NOTICE '✓ Contrainte presentation_codev_candidat_id_fkey supprimée';
            END IF;
            
            IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_schema = schema_rec.schema_name AND table_name = 'candidat') THEN
                EXECUTE format('
                    ALTER TABLE %I.presentation_codev 
                    ADD CONSTRAINT presentation_codev_candidat_id_fkey 
                    FOREIGN KEY (candidat_id) 
                    REFERENCES %I.candidat(id) 
                    ON DELETE CASCADE
                ', schema_rec.schema_name, schema_rec.schema_name);
                RAISE NOTICE '✓ Contrainte presentation_codev_candidat_id_fkey créée';
            ELSE
                RAISE WARNING '✗ Table candidat non trouvée dans le schéma: %', schema_rec.schema_name;
            END IF;
        END IF;
        
        -- 3. Corriger contribution_codev_contributeur_id_fkey
        IF EXISTS (
            SELECT 1 FROM information_schema.tables 
            WHERE table_schema = schema_rec.schema_name AND table_name = 'contribution_codev'
        ) THEN
            SELECT EXISTS (
                SELECT 1 
                FROM information_schema.table_constraints tc
                WHERE tc.table_schema = schema_rec.schema_name
                AND tc.table_name = 'contribution_codev'
                AND tc.constraint_name = 'contribution_codev_contributeur_id_fkey'
            ) INTO constraint_exists;
            
            IF constraint_exists THEN
                EXECUTE format('ALTER TABLE %I.contribution_codev DROP CONSTRAINT IF EXISTS contribution_codev_contributeur_id_fkey', schema_rec.schema_name);
                RAISE NOTICE '✓ Contrainte contribution_codev_contributeur_id_fkey supprimée';
            END IF;
            
            IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_schema = schema_rec.schema_name AND table_name = 'candidat') THEN
                EXECUTE format('
                    ALTER TABLE %I.contribution_codev 
                    ADD CONSTRAINT contribution_codev_contributeur_id_fkey 
                    FOREIGN KEY (contributeur_id) 
                    REFERENCES %I.candidat(id) 
                    ON DELETE CASCADE
                ', schema_rec.schema_name, schema_rec.schema_name);
                RAISE NOTICE '✓ Contrainte contribution_codev_contributeur_id_fkey créée';
            ELSE
                RAISE WARNING '✗ Table candidat non trouvée dans le schéma: %', schema_rec.schema_name;
            END IF;
        END IF;
        
        RAISE NOTICE '✓ Schéma % traité avec succès', schema_rec.schema_name;
        RAISE NOTICE '';
    END LOOP;
    
    RAISE NOTICE '========================================';
    RAISE NOTICE '✓ Tous les schémas ont été traités';
    RAISE NOTICE '========================================';
END $$;

