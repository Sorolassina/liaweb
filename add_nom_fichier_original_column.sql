-- Migration pour ajouter la colonne nom_fichier_original à la table ressourceelearning
-- Exécuter cette requête dans votre base de données PostgreSQL

ALTER TABLE ressourceelearning 
ADD COLUMN nom_fichier_original VARCHAR(255);

-- Commentaire pour documenter la colonne
COMMENT ON COLUMN ressourceelearning.nom_fichier_original IS 'Nom original du fichier uploadé par l''utilisateur';
