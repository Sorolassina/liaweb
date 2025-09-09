-- Migration pour convertir le champ statutrdv de enum vers text
-- Script: convert_statutrdv_enum_to_text.sql

-- 1. Ajouter une nouvelle colonne temporaire de type text
ALTER TABLE rendezvous ADD COLUMN statut_temp TEXT;

-- 2. Copier les valeurs de l'ancienne colonne vers la nouvelle
UPDATE rendezvous SET statut_temp = statut::text;

-- 3. Supprimer l'ancienne colonne enum
ALTER TABLE rendezvous DROP COLUMN statut;

-- 4. Renommer la colonne temporaire
ALTER TABLE rendezvous RENAME COLUMN statut_temp TO statut;

-- 5. Optionnel : Supprimer le type enum s'il n'est plus utilisé
-- DROP TYPE IF EXISTS statutrdv;

-- Vérification
SELECT column_name, data_type 
FROM information_schema.columns 
WHERE table_name = 'rendezvous' AND column_name = 'statut';
