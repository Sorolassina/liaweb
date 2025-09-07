-- Script SQL pour nettoyer complètement les chemins de photos
-- Supprime tous les caractères non-ASCII et corrige les chemins

-- Afficher l'état actuel
SELECT 'État actuel:' as info;
SELECT c.id, c.nom, c.prenom, c.photo_profil, 
       LENGTH(c.photo_profil) as longueur,
       ENCODE(c.photo_profil::bytea, 'hex') as hex_representation
FROM candidat c
WHERE c.photo_profil IS NOT NULL 
ORDER BY c.id;

-- Nettoyer les chemins de photos
UPDATE candidat 
SET photo_profil = CASE 
    WHEN photo_profil LIKE '%Preinscrits%' THEN 
        'Preinscrits/ACD/' || SUBSTRING(photo_profil FROM 'photo_profil_[0-9]+')
    ELSE photo_profil
END
WHERE photo_profil IS NOT NULL 
AND photo_profil LIKE '%Preinscrits%';

-- Afficher l'état après nettoyage
SELECT 'État après nettoyage:' as info;
SELECT c.id, c.nom, c.prenom, c.photo_profil
FROM candidat c
WHERE c.photo_profil IS NOT NULL 
ORDER BY c.id;
