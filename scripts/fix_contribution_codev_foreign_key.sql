-- Script pour corriger la contrainte de clé étrangère contribution_codev_contributeur_id_fkey
-- Cette contrainte pointe actuellement vers inscription mais doit pointer vers candidat

-- Pour chaque schéma de programme (acd, etc.)
DO $$
DECLARE
    schema_rec RECORD;
    constraint_exists BOOLEAN;
BEGIN
    -- Parcourir tous les schémas qui contiennent la table contribution_codev
    FOR schema_rec IN 
        SELECT table_schema as schema_name
        FROM information_schema.tables 
        WHERE table_name = 'contribution_codev' 
        AND table_schema NOT IN ('information_schema', 'pg_catalog', 'pg_toast')
    LOOP
        RAISE NOTICE 'Traitement du schéma: %', schema_rec.schema_name;
        
        -- Vérifier si la contrainte existe
        SELECT EXISTS (
            SELECT 1 
            FROM information_schema.table_constraints tc
            JOIN information_schema.key_column_usage kcu 
                ON tc.constraint_name = kcu.constraint_name
                AND tc.table_schema = kcu.table_schema
            WHERE tc.table_schema = schema_rec.schema_name
            AND tc.table_name = 'contribution_codev'
            AND tc.constraint_name = 'contribution_codev_contributeur_id_fkey'
        ) INTO constraint_exists;
        
        IF constraint_exists THEN
            -- Supprimer l'ancienne contrainte
            EXECUTE format('ALTER TABLE %I.contribution_codev DROP CONSTRAINT IF EXISTS contribution_codev_contributeur_id_fkey', schema_rec.schema_name);
            RAISE NOTICE 'Contrainte supprimée dans le schéma: %', schema_rec.schema_name;
        END IF;
        
        -- Vérifier si la table candidat existe dans ce schéma
        IF EXISTS (
            SELECT 1 
            FROM information_schema.tables 
            WHERE table_schema = schema_rec.schema_name 
            AND table_name = 'candidat'
        ) THEN
            -- Créer la nouvelle contrainte pointant vers candidat
            EXECUTE format('
                ALTER TABLE %I.contribution_codev 
                ADD CONSTRAINT contribution_codev_contributeur_id_fkey 
                FOREIGN KEY (contributeur_id) 
                REFERENCES %I.candidat(id) 
                ON DELETE CASCADE
            ', schema_rec.schema_name, schema_rec.schema_name);
            RAISE NOTICE 'Nouvelle contrainte créée dans le schéma: %', schema_rec.schema_name;
        ELSE
            RAISE WARNING 'Table candidat non trouvée dans le schéma: %', schema_rec.schema_name;
        END IF;
    END LOOP;
END $$;

