-- Script de migration pour changer contribution_codev de presentation_id vers seance_id
-- Ce script doit être exécuté pour chaque schéma (acd, etc.)

-- Étape 1: Ajouter la colonne seance_id si elle n'existe pas
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_schema = 'acd' 
        AND table_name = 'contribution_codev' 
        AND column_name = 'seance_id'
    ) THEN
        ALTER TABLE acd.contribution_codev ADD COLUMN seance_id INTEGER;
    END IF;
END $$;

-- Étape 2: Remplir seance_id à partir de presentation_id
UPDATE acd.contribution_codev c
SET seance_id = p.seance_id
FROM acd.presentation_codev p
WHERE c.presentation_id = p.id
AND c.seance_id IS NULL;

-- Étape 3: Vérifier qu'il n'y a pas de contributions orphelines
-- (contributions avec presentation_id mais sans seance_id correspondant)
DO $$
DECLARE
    orphan_count INTEGER;
BEGIN
    SELECT COUNT(*) INTO orphan_count
    FROM acd.contribution_codev c
    LEFT JOIN acd.presentation_codev p ON c.presentation_id = p.id
    WHERE c.seance_id IS NULL AND p.id IS NULL;
    
    IF orphan_count > 0 THEN
        RAISE NOTICE 'ATTENTION: % contributions orphelines trouvées (sans présentation correspondante)', orphan_count;
    END IF;
END $$;

-- Étape 4: Supprimer l'ancienne contrainte de clé étrangère sur presentation_id
DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.table_constraints 
        WHERE constraint_schema = 'acd' 
        AND table_name = 'contribution_codev' 
        AND constraint_name = 'contribution_codev_presentation_id_fkey'
    ) THEN
        ALTER TABLE acd.contribution_codev 
        DROP CONSTRAINT contribution_codev_presentation_id_fkey;
    END IF;
END $$;

-- Étape 5: Ajouter la nouvelle contrainte de clé étrangère sur seance_id
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.table_constraints 
        WHERE constraint_schema = 'acd' 
        AND table_name = 'contribution_codev' 
        AND constraint_name = 'contribution_codev_seance_id_fkey'
    ) THEN
        ALTER TABLE acd.contribution_codev
        ADD CONSTRAINT contribution_codev_seance_id_fkey
        FOREIGN KEY (seance_id) REFERENCES acd.seance_codev(id) ON DELETE CASCADE;
    END IF;
END $$;

-- Étape 6: Rendre seance_id NOT NULL (après avoir rempli toutes les valeurs)
DO $$
BEGIN
    -- Vérifier qu'il n'y a pas de valeurs NULL
    IF NOT EXISTS (SELECT 1 FROM acd.contribution_codev WHERE seance_id IS NULL) THEN
        ALTER TABLE acd.contribution_codev ALTER COLUMN seance_id SET NOT NULL;
    ELSE
        RAISE NOTICE 'ATTENTION: Il reste des contributions avec seance_id NULL. Ne pas rendre la colonne NOT NULL.';
    END IF;
END $$;

-- Étape 7: Supprimer l'ancienne colonne presentation_id (optionnel, à faire après vérification)
-- ATTENTION: Ne décommenter que si vous êtes sûr que tout fonctionne correctement
-- ALTER TABLE acd.contribution_codev DROP COLUMN presentation_id;

-- Pour appliquer à d'autres schémas, remplacer 'acd' par le nom du schéma souhaité

