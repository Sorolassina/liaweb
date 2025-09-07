-- Script pour migrer les documents existants vers la nouvelle structure par candidat
-- Ce script réorganise les documents dans des dossiers spécifiques par candidat

-- 1. Créer les dossiers pour chaque candidat ayant des documents
-- 2. Déplacer les fichiers vers leurs nouveaux emplacements
-- 3. Mettre à jour les chemins en base de données

-- Note: Ce script doit être exécuté depuis Python car il nécessite des opérations sur le système de fichiers

-- Vérifier la structure actuelle
SELECT 
    d.id,
    d.candidat_id,
    d.nom_fichier,
    d.chemin_fichier,
    d.type_document
FROM document d
ORDER BY d.candidat_id, d.type_document;
