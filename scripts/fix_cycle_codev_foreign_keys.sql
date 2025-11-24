-- Script pour corriger les contraintes de clé étrangère de cycle_codev
-- Les contraintes doivent référencer :
--   - public.programme pour programme_id
--   - {schema}.promotion pour promotion_id (promotion est dans le schéma du programme, pas dans public)
-- À exécuter pour chaque schéma de programme (acd, aci, act, etc.)

-- Corriger les contraintes pour tous les schémas de programme existants
DO $$
DECLARE
    schema_rec RECORD;
    fk_name TEXT;
BEGIN
    FOR schema_rec IN 
        SELECT s.schema_name 
        FROM information_schema.schemata s
        WHERE s.schema_name IN ('acd', 'aci', 'act')
        AND EXISTS (
            SELECT 1 FROM information_schema.tables t
            WHERE t.table_schema = s.schema_name 
            AND t.table_name = 'cycle_codev'
        )
    LOOP
        RAISE NOTICE 'Correction des contraintes FK pour le schéma %', schema_rec.schema_name;
        
        -- Supprimer et recréer la contrainte promotion_id
        SELECT tc.constraint_name INTO fk_name
        FROM information_schema.table_constraints tc
        JOIN information_schema.key_column_usage kcu 
            ON tc.constraint_name = kcu.constraint_name
        WHERE tc.table_schema = schema_rec.schema_name
            AND tc.table_name = 'cycle_codev'
            AND tc.constraint_type = 'FOREIGN KEY'
            AND kcu.column_name = 'promotion_id';
        
        IF fk_name IS NOT NULL THEN
            EXECUTE format('ALTER TABLE %I.cycle_codev DROP CONSTRAINT IF EXISTS %I', 
                schema_rec.schema_name, fk_name);
            RAISE NOTICE 'Contrainte % supprimée', fk_name;
        END IF;
        
        -- Recréer la contrainte promotion_id pour référencer le schéma du programme (pas public)
        IF EXISTS (
            SELECT 1 FROM information_schema.columns 
            WHERE table_schema = schema_rec.schema_name 
            AND table_name = 'cycle_codev' 
            AND column_name = 'promotion_id'
        ) AND EXISTS (
            SELECT 1 FROM information_schema.tables 
            WHERE table_schema = schema_rec.schema_name 
            AND table_name = 'promotion'
        ) THEN
            EXECUTE format('ALTER TABLE %I.cycle_codev 
                ADD CONSTRAINT cycle_codev_promotion_id_fkey 
                FOREIGN KEY (promotion_id) REFERENCES %I.promotion(id)', 
                schema_rec.schema_name, schema_rec.schema_name);
            RAISE NOTICE 'Contrainte cycle_codev_promotion_id_fkey recréée pour référencer %.promotion', schema_rec.schema_name;
        END IF;
        
        -- Vérifier et corriger la contrainte programme_id si nécessaire
        SELECT tc.constraint_name INTO fk_name
        FROM information_schema.table_constraints tc
        JOIN information_schema.key_column_usage kcu 
            ON tc.constraint_name = kcu.constraint_name
        WHERE tc.table_schema = schema_rec.schema_name
            AND tc.table_name = 'cycle_codev'
            AND tc.constraint_type = 'FOREIGN KEY'
            AND kcu.column_name = 'programme_id';
        
        -- Vérifier si la contrainte référence bien public.programme
        IF fk_name IS NOT NULL THEN
            -- Vérifier la référence actuelle
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.constraint_column_usage ccu
                WHERE ccu.constraint_name = fk_name
                AND ccu.table_schema = 'public'
                AND ccu.table_name = 'programme'
            ) THEN
                -- La contrainte ne référence pas public.programme, la recréer
                EXECUTE format('ALTER TABLE %I.cycle_codev DROP CONSTRAINT IF EXISTS %I', 
                    schema_rec.schema_name, fk_name);
                EXECUTE format('ALTER TABLE %I.cycle_codev 
                    ADD CONSTRAINT cycle_codev_programme_id_fkey 
                    FOREIGN KEY (programme_id) REFERENCES public.programme(id)', 
                    schema_rec.schema_name);
                RAISE NOTICE 'Contrainte cycle_codev_programme_id_fkey recréée pour référencer public.programme';
            ELSE
                RAISE NOTICE 'Contrainte programme_id est correcte';
            END IF;
        ELSE
            -- Créer la contrainte si elle n'existe pas
            EXECUTE format('ALTER TABLE %I.cycle_codev 
                ADD CONSTRAINT cycle_codev_programme_id_fkey 
                FOREIGN KEY (programme_id) REFERENCES public.programme(id)', 
                schema_rec.schema_name);
            RAISE NOTICE 'Contrainte cycle_codev_programme_id_fkey créée';
        END IF;
    END LOOP;
END;
$$;

-- Vérification finale
SELECT 
    tc.table_schema,
    tc.table_name,
    tc.constraint_name,
    kcu.column_name,
    ccu.table_schema AS foreign_table_schema,
    ccu.table_name AS foreign_table_name
FROM information_schema.table_constraints tc
JOIN information_schema.key_column_usage kcu 
    ON tc.constraint_name = kcu.constraint_name
LEFT JOIN information_schema.constraint_column_usage ccu 
    ON tc.constraint_name = ccu.constraint_name
WHERE tc.table_name = 'cycle_codev'
    AND tc.constraint_type = 'FOREIGN KEY'
    AND (kcu.column_name = 'programme_id' OR kcu.column_name = 'promotion_id')
ORDER BY tc.table_schema, kcu.column_name;

