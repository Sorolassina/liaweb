-- Script SQL pour ajouter la colonne statut à la table candidat
-- À exécuter dans PostgreSQL

-- Vérifier si la colonne existe déjà
DO $$ 
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'candidat' 
        AND column_name = 'statut'
    ) THEN
        -- Ajouter la colonne avec valeur par défaut
        ALTER TABLE candidat ADD COLUMN statut VARCHAR(20) DEFAULT 'EN_ATTENTE';
        RAISE NOTICE 'Colonne statut ajoutée à la table candidat';
    ELSE
        RAISE NOTICE 'Colonne statut existe déjà dans la table candidat';
    END IF;
END $$;

-- Mettre à jour les candidats existants sans statut
UPDATE candidat 
SET statut = 'EN_ATTENTE' 
WHERE statut IS NULL;

-- Vérifier la structure de la table candidat
SELECT column_name, data_type, is_nullable, column_default
FROM information_schema.columns 
WHERE table_name = 'candidat' 
AND column_name IN ('statut', 'photo_profil')
ORDER BY ordinal_position;

-- Afficher quelques exemples
SELECT c.id, c.nom, c.prenom, c.statut
FROM candidat c
ORDER BY c.id
LIMIT 5;
