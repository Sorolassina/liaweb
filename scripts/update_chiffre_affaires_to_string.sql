-- Script SQL pour modifier la colonne chiffre_affaires de float à varchar
-- À exécuter dans PostgreSQL

-- Vérifier le type actuel de la colonne
SELECT column_name, data_type, character_maximum_length
FROM information_schema.columns 
WHERE table_name = 'entreprise' 
AND column_name = 'chiffre_affaires';

-- Modifier le type de la colonne de float à varchar
ALTER TABLE entreprise 
ALTER COLUMN chiffre_affaires TYPE VARCHAR(100);

-- Vérifier le nouveau type
SELECT column_name, data_type, character_maximum_length
FROM information_schema.columns 
WHERE table_name = 'entreprise' 
AND column_name = 'chiffre_affaires';

-- Afficher quelques exemples
SELECT e.id, e.candidat_id, e.siret, e.chiffre_affaires
FROM entreprise e
WHERE e.chiffre_affaires IS NOT NULL
ORDER BY e.id
LIMIT 5;
