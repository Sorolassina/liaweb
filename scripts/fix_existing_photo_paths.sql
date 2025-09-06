-- Script SQL pour nettoyer les anciennes photos de profil
-- À exécuter dans PostgreSQL

-- Mettre à jour les chemins des photos existantes pour inclure l'ID de la préinscription
UPDATE candidat 
SET photo_profil = REPLACE(photo_profil, 'photo_profil.', 'photo_profil_' || (
    SELECT p.id FROM preinscription p WHERE p.candidat_id = candidat.id LIMIT 1
) || '.')
WHERE photo_profil IS NOT NULL 
AND photo_profil LIKE '%photo_profil.%'
AND photo_profil NOT LIKE '%photo_profil_%';

-- Afficher les résultats
SELECT c.id, c.nom, c.prenom, c.photo_profil, p.id as preinscription_id
FROM candidat c
LEFT JOIN preinscription p ON p.candidat_id = c.id
WHERE c.photo_profil IS NOT NULL 
ORDER BY c.id;
