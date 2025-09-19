-- =====================================================
-- VÉRIFICATION DE LA TABLE RessourceElearning
-- =====================================================
-- Ce script vérifie que tous les champs nécessaires 
-- pour la sauvegarde des ressources e-learning sont présents

-- 1. Vérifier l'existence de la table
SELECT 
    CASE 
        WHEN EXISTS (
            SELECT 1 FROM information_schema.tables 
            WHERE table_name = 'ressourceelearning'
        ) 
        THEN '✅ Table RessourceElearning existe'
        ELSE '❌ Table RessourceElearning manquante'
    END as table_status;

-- 2. Lister tous les champs de la table
SELECT 
    column_name as "Champ",
    data_type as "Type",
    is_nullable as "Nullable",
    column_default as "Valeur par défaut"
FROM information_schema.columns 
WHERE table_name = 'ressourceelearning'
ORDER BY ordinal_position;

-- 3. Vérifier les champs obligatoires pour la création
SELECT 
    'Champs obligatoires pour création:' as "Vérification",
    '' as "Statut";

-- Vérifier chaque champ obligatoire
SELECT 
    CASE 
        WHEN EXISTS (
            SELECT 1 FROM information_schema.columns 
            WHERE table_name = 'ressourceelearning' 
            AND column_name = 'titre' 
            AND is_nullable = 'NO'
        ) 
        THEN '✅ titre (NOT NULL)'
        ELSE '❌ titre manquant ou nullable'
    END as "Champ titre";

SELECT 
    CASE 
        WHEN EXISTS (
            SELECT 1 FROM information_schema.columns 
            WHERE table_name = 'ressourceelearning' 
            AND column_name = 'type_ressource' 
            AND is_nullable = 'NO'
        ) 
        THEN '✅ type_ressource (NOT NULL)'
        ELSE '❌ type_ressource manquant ou nullable'
    END as "Champ type_ressource";

-- 4. Vérifier les champs spécifiques par type de ressource
SELECT 
    'Champs spécifiques par type:' as "Vérification",
    '' as "Statut";

-- URLs par type
SELECT 
    CASE 
        WHEN EXISTS (
            SELECT 1 FROM information_schema.columns 
            WHERE table_name = 'ressourceelearning' 
            AND column_name = 'url_contenu_video'
        ) 
        THEN '✅ url_contenu_video'
        ELSE '❌ url_contenu_video manquant'
    END as "URL Vidéo";

SELECT 
    CASE 
        WHEN EXISTS (
            SELECT 1 FROM information_schema.columns 
            WHERE table_name = 'ressourceelearning' 
            AND column_name = 'url_contenu_document'
        ) 
        THEN '✅ url_contenu_document'
        ELSE '❌ url_contenu_document manquant'
    END as "URL Document";

SELECT 
    CASE 
        WHEN EXISTS (
            SELECT 1 FROM information_schema.columns 
            WHERE table_name = 'ressourceelearning' 
            AND column_name = 'url_contenu_audio'
        ) 
        THEN '✅ url_contenu_audio'
        ELSE '❌ url_contenu_audio manquant'
    END as "URL Audio";

SELECT 
    CASE 
        WHEN EXISTS (
            SELECT 1 FROM information_schema.columns 
            WHERE table_name = 'ressourceelearning' 
            AND column_name = 'url_contenu_lien'
        ) 
        THEN '✅ url_contenu_lien'
        ELSE '❌ url_contenu_lien manquant'
    END as "URL Lien";

-- Fichiers par type
SELECT 
    CASE 
        WHEN EXISTS (
            SELECT 1 FROM information_schema.columns 
            WHERE table_name = 'ressourceelearning' 
            AND column_name = 'fichier_video_path'
        ) 
        THEN '✅ fichier_video_path'
        ELSE '❌ fichier_video_path manquant'
    END as "Fichier Vidéo Path";

SELECT 
    CASE 
        WHEN EXISTS (
            SELECT 1 FROM information_schema.columns 
            WHERE table_name = 'ressourceelearning' 
            AND column_name = 'fichier_video_nom_original'
        ) 
        THEN '✅ fichier_video_nom_original'
        ELSE '❌ fichier_video_nom_original manquant'
    END as "Fichier Vidéo Nom";

SELECT 
    CASE 
        WHEN EXISTS (
            SELECT 1 FROM information_schema.columns 
            WHERE table_name = 'ressourceelearning' 
            AND column_name = 'fichier_document_path'
        ) 
        THEN '✅ fichier_document_path'
        ELSE '❌ fichier_document_path manquant'
    END as "Fichier Document Path";

SELECT 
    CASE 
        WHEN EXISTS (
            SELECT 1 FROM information_schema.columns 
            WHERE table_name = 'ressourceelearning' 
            AND column_name = 'fichier_document_nom_original'
        ) 
        THEN '✅ fichier_document_nom_original'
        ELSE '❌ fichier_document_nom_original manquant'
    END as "Fichier Document Nom";

SELECT 
    CASE 
        WHEN EXISTS (
            SELECT 1 FROM information_schema.columns 
            WHERE table_name = 'ressourceelearning' 
            AND column_name = 'fichier_audio_path'
        ) 
        THEN '✅ fichier_audio_path'
        ELSE '❌ fichier_audio_path manquant'
    END as "Fichier Audio Path";

SELECT 
    CASE 
        WHEN EXISTS (
            SELECT 1 FROM information_schema.columns 
            WHERE table_name = 'ressourceelearning' 
            AND column_name = 'fichier_audio_nom_original'
        ) 
        THEN '✅ fichier_audio_nom_original'
        ELSE '❌ fichier_audio_nom_original manquant'
    END as "Fichier Audio Nom";

-- 5. Vérifier les champs généraux
SELECT 
    'Champs généraux:' as "Vérification",
    '' as "Statut";

SELECT 
    CASE 
        WHEN EXISTS (
            SELECT 1 FROM information_schema.columns 
            WHERE table_name = 'ressourceelearning' 
            AND column_name = 'description'
        ) 
        THEN '✅ description'
        ELSE '❌ description manquant'
    END as "Description";

SELECT 
    CASE 
        WHEN EXISTS (
            SELECT 1 FROM information_schema.columns 
            WHERE table_name = 'ressourceelearning' 
            AND column_name = 'duree_minutes'
        ) 
        THEN '✅ duree_minutes'
        ELSE '❌ duree_minutes manquant'
    END as "Durée";

SELECT 
    CASE 
        WHEN EXISTS (
            SELECT 1 FROM information_schema.columns 
            WHERE table_name = 'ressourceelearning' 
            AND column_name = 'difficulte'
        ) 
        THEN '✅ difficulte'
        ELSE '❌ difficulte manquant'
    END as "Difficulté";

SELECT 
    CASE 
        WHEN EXISTS (
            SELECT 1 FROM information_schema.columns 
            WHERE table_name = 'ressourceelearning' 
            AND column_name = 'tags'
        ) 
        THEN '✅ tags'
        ELSE '❌ tags manquant'
    END as "Tags";

SELECT 
    CASE 
        WHEN EXISTS (
            SELECT 1 FROM information_schema.columns 
            WHERE table_name = 'ressourceelearning' 
            AND column_name = 'ordre'
        ) 
        THEN '✅ ordre'
        ELSE '❌ ordre manquant'
    END as "Ordre";

SELECT 
    CASE 
        WHEN EXISTS (
            SELECT 1 FROM information_schema.columns 
            WHERE table_name = 'ressourceelearning' 
            AND column_name = 'actif'
        ) 
        THEN '✅ actif'
        ELSE '❌ actif manquant'
    END as "Actif";

-- 6. Vérifier les champs de traçabilité
SELECT 
    'Champs de traçabilité:' as "Vérification",
    '' as "Statut";

SELECT 
    CASE 
        WHEN EXISTS (
            SELECT 1 FROM information_schema.columns 
            WHERE table_name = 'ressourceelearning' 
            AND column_name = 'cree_le'
        ) 
        THEN '✅ cree_le'
        ELSE '❌ cree_le manquant'
    END as "Créé le";

SELECT 
    CASE 
        WHEN EXISTS (
            SELECT 1 FROM information_schema.columns 
            WHERE table_name = 'ressourceelearning' 
            AND column_name = 'cree_par_id'
        ) 
        THEN '✅ cree_par_id'
        ELSE '❌ cree_par_id manquant'
    END as "Créé par";

-- 7. Vérifier les champs legacy (compatibilité)
SELECT 
    'Champs legacy (compatibilité):' as "Vérification",
    '' as "Statut";

SELECT 
    CASE 
        WHEN EXISTS (
            SELECT 1 FROM information_schema.columns 
            WHERE table_name = 'ressourceelearning' 
            AND column_name = 'url_contenu'
        ) 
        THEN '✅ url_contenu (legacy)'
        ELSE '❌ url_contenu manquant'
    END as "URL Contenu Legacy";

SELECT 
    CASE 
        WHEN EXISTS (
            SELECT 1 FROM information_schema.columns 
            WHERE table_name = 'ressourceelearning' 
            AND column_name = 'fichier_path'
        ) 
        THEN '✅ fichier_path (legacy)'
        ELSE '❌ fichier_path manquant'
    END as "Fichier Path Legacy";

SELECT 
    CASE 
        WHEN EXISTS (
            SELECT 1 FROM information_schema.columns 
            WHERE table_name = 'ressourceelearning' 
            AND column_name = 'nom_fichier_original'
        ) 
        THEN '✅ nom_fichier_original (legacy)'
        ELSE '❌ nom_fichier_original manquant'
    END as "Nom Fichier Legacy";

-- 8. Résumé des vérifications
SELECT 
    'RÉSUMÉ DES VÉRIFICATIONS' as "====",
    '' as "=====";

SELECT 
    COUNT(*) as "Total des champs détectés"
FROM information_schema.columns 
WHERE table_name = 'ressourceelearning';

-- 9. Script de création de la table si elle n'existe pas
SELECT 
    'SCRIPT DE CRÉATION DE LA TABLE:' as "====",
    '' as "=====";

-- Afficher le script de création
SELECT 
    'CREATE TABLE IF NOT EXISTS ressourceelearning (' as "Script",
    '    id SERIAL PRIMARY KEY,' as "Script",
    '    titre VARCHAR NOT NULL,' as "Script",
    '    description TEXT,' as "Script",
    '    type_ressource VARCHAR(20) NOT NULL,' as "Script",
    '    -- URLs par type' as "Script",
    '    url_contenu_video TEXT,' as "Script",
    '    url_contenu_document TEXT,' as "Script",
    '    url_contenu_audio TEXT,' as "Script",
    '    url_contenu_lien TEXT,' as "Script",
    '    -- Fichiers par type' as "Script",
    '    fichier_video_path TEXT,' as "Script",
    '    fichier_video_nom_original TEXT,' as "Script",
    '    fichier_document_path TEXT,' as "Script",
    '    fichier_document_nom_original TEXT,' as "Script",
    '    fichier_audio_path TEXT,' as "Script",
    '    fichier_audio_nom_original TEXT,' as "Script",
    '    -- Champs legacy' as "Script",
    '    url_contenu TEXT,' as "Script",
    '    fichier_path TEXT,' as "Script",
    '    nom_fichier_original TEXT,' as "Script",
    '    -- Champs généraux' as "Script",
    '    duree_minutes INTEGER,' as "Script",
    '    difficulte VARCHAR(20) DEFAULT ''facile'',' as "Script",
    '    tags TEXT,' as "Script",
    '    ordre INTEGER DEFAULT 0,' as "Script",
    '    actif BOOLEAN DEFAULT TRUE,' as "Script",
    '    -- Traçabilité' as "Script",
    '    cree_le TIMESTAMP WITH TIME ZONE DEFAULT NOW(),' as "Script",
    '    cree_par_id INTEGER REFERENCES "user"(id)' as "Script",
    ');' as "Script";
