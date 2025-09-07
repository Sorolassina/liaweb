-- Script pour vérifier les types de documents disponibles dans l'enum PostgreSQL
-- À exécuter dans la base de données PostgreSQL

-- Vérifier tous les types de documents disponibles
SELECT unnest(enum_range(NULL::typedocument)) as type_document_values
ORDER BY type_document_values;

-- Vérifier les documents récents
SELECT 
    id,
    candidat_id,
    nom_fichier,
    type_document,
    chemin_fichier,
    taille_fichier,
    date_upload
FROM document 
ORDER BY date_upload DESC 
LIMIT 10;
