-- Script pour ajouter les nouveaux enums à la base de données PostgreSQL
-- À exécuter dans psql ou via un client PostgreSQL

-- Ajouter les valeurs pour l'enum GroupeCodev
-- Note: PostgreSQL ne permet pas de modifier un enum existant directement
-- Nous devons créer un nouveau type et migrer les données

-- 1. Créer le nouveau type enum pour GroupeCodev
DO $$ 
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'groupecodev') THEN
        CREATE TYPE groupecodev AS ENUM (
            'GROUPE_A', 'GROUPE_B', 'GROUPE_C', 'GROUPE_D', 'GROUPE_E',
            'GROUPE_F', 'GROUPE_G', 'GROUPE_H', 'GROUPE_I', 'GROUPE_J'
        );
    END IF;
END $$;

-- 2. Créer le nouveau type enum pour TypePromotion
DO $$ 
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'typepromotion') THEN
        CREATE TYPE typepromotion AS ENUM (
            'PROMOTION_2024_A', 'PROMOTION_2024_B', 'PROMOTION_2024_C',
            'PROMOTION_2025_A', 'PROMOTION_2025_B', 'PROMOTION_2025_C',
            'PROMOTION_2026_A', 'PROMOTION_2026_B', 'PROMOTION_2026_C'
        );
    END IF;
END $$;

-- 3. Ajouter une colonne temporaire pour groupe_codev avec le nouveau type
ALTER TABLE decisionjurycandidat ADD COLUMN IF NOT EXISTS groupe_codev_new groupecodev;

-- 4. Migrer les données existantes (si il y en a)
-- Cette partie peut être adaptée selon vos données existantes
UPDATE decisionjurycandidat 
SET groupe_codev_new = CASE 
    WHEN groupe_codev ILIKE '%groupe a%' OR groupe_codev ILIKE '%groupe_a%' THEN 'GROUPE_A'::groupecodev
    WHEN groupe_codev ILIKE '%groupe b%' OR groupe_codev ILIKE '%groupe_b%' THEN 'GROUPE_B'::groupecodev
    WHEN groupe_codev ILIKE '%groupe c%' OR groupe_codev ILIKE '%groupe_c%' THEN 'GROUPE_C'::groupecodev
    WHEN groupe_codev ILIKE '%groupe d%' OR groupe_codev ILIKE '%groupe_d%' THEN 'GROUPE_D'::groupecodev
    WHEN groupe_codev ILIKE '%groupe e%' OR groupe_codev ILIKE '%groupe_e%' THEN 'GROUPE_E'::groupecodev
    WHEN groupe_codev ILIKE '%groupe f%' OR groupe_codev ILIKE '%groupe_f%' THEN 'GROUPE_F'::groupecodev
    WHEN groupe_codev ILIKE '%groupe g%' OR groupe_codev ILIKE '%groupe_g%' THEN 'GROUPE_G'::groupecodev
    WHEN groupe_codev ILIKE '%groupe h%' OR groupe_codev ILIKE '%groupe_h%' THEN 'GROUPE_H'::groupecodev
    WHEN groupe_codev ILIKE '%groupe i%' OR groupe_codev ILIKE '%groupe_i%' THEN 'GROUPE_I'::groupecodev
    WHEN groupe_codev ILIKE '%groupe j%' OR groupe_codev ILIKE '%groupe_j%' THEN 'GROUPE_J'::groupecodev
    ELSE NULL
END
WHERE groupe_codev IS NOT NULL AND groupe_codev != '';

-- 5. Supprimer l'ancienne colonne et renommer la nouvelle
ALTER TABLE decisionjurycandidat DROP COLUMN IF EXISTS groupe_codev;
ALTER TABLE decisionjurycandidat RENAME COLUMN groupe_codev_new TO groupe_codev;

-- 6. Ajouter un commentaire pour documenter le changement
COMMENT ON COLUMN decisionjurycandidat.groupe_codev IS 'Groupe de codéveloppement - enum GroupeCodev';

-- Vérification
SELECT 'Migration terminée avec succès' as status;
SELECT COUNT(*) as total_decisions, COUNT(groupe_codev) as avec_groupe 
FROM decisionjurycandidat;
