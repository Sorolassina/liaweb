-- Script SQL pour corriger les chemins de photos de profil
-- Convertit les chemins absolus Windows en chemins relatifs

-- Mettre à jour les chemins de photos existants
UPDATE candidat 
SET photo_profil = CASE 
    WHEN photo_profil LIKE '%Preinscrits%' THEN 
        SUBSTRING(photo_profil FROM 'Preinscrits.*$')
    ELSE photo_profil
END
WHERE photo_profil IS NOT NULL 
AND photo_profil LIKE '%Preinscrits%';

-- Afficher les résultats
SELECT c.id, c.nom, c.prenom, c.photo_profil
FROM candidat c
WHERE c.photo_profil IS NOT NULL 
ORDER BY c.id;
