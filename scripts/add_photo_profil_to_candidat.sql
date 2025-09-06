-- Script SQL pour ajouter la colonne photo_profil à la table candidat
-- À exécuter dans PostgreSQL

-- Vérifier si la colonne existe déjà
DO $$ 
BEGIN
    -- Vérifier si la colonne photo_profil existe déjà
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'candidat' 
        AND column_name = 'photo_profil'
    ) THEN
        -- Ajouter la colonne
        ALTER TABLE candidat ADD COLUMN photo_profil VARCHAR(255);
        RAISE NOTICE 'Colonne photo_profil ajoutée à la table candidat';
    ELSE
        RAISE NOTICE 'Colonne photo_profil existe déjà dans la table candidat';
    END IF;
END $$;

-- Vérifier la structure de la table candidat
SELECT column_name, data_type, is_nullable 
FROM information_schema.columns 
WHERE table_name = 'candidat' 
ORDER BY ordinal_position;
