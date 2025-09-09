-- scripts/add_notes_to_rendezvous.sql

-- Ajouter le champ notes à la table rendezvous
BEGIN;

-- Ajouter la colonne notes si elle n'existe pas déjà
DO $$ 
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'rendezvous' AND column_name = 'notes'
    ) THEN
        ALTER TABLE rendezvous ADD COLUMN notes TEXT;
        RAISE NOTICE 'Colonne notes ajoutée à la table rendezvous';
    ELSE
        RAISE NOTICE 'Colonne notes existe déjà dans la table rendezvous';
    END IF;
END $$;

-- Vérifier le résultat
SELECT column_name, data_type, is_nullable
FROM information_schema.columns 
WHERE table_name = 'rendezvous' AND column_name = 'notes';

COMMIT;
