-- =====================================================
-- MIGRATION POUR AJOUTER LES COLONNES MANQUANTES
-- =====================================================
-- Ce script ajoute les colonnes nécessaires pour la sauvegarde
-- des ressources e-learning avec support multi-types

-- 1. Vérifier si la table existe
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'ressourceelearning') THEN
        RAISE NOTICE 'Création de la table ressourceelearning...';
        
        CREATE TABLE ressourceelearning (
            id SERIAL PRIMARY KEY,
            titre VARCHAR NOT NULL,
            description TEXT,
            type_ressource VARCHAR(20) NOT NULL,
            
            -- URLs par type de contenu
            url_contenu_video TEXT,
            url_contenu_document TEXT,
            url_contenu_audio TEXT,
            url_contenu_lien TEXT,
            
            -- Fichiers par type
            fichier_video_path TEXT,
            fichier_video_nom_original TEXT,
            fichier_document_path TEXT,
            fichier_document_nom_original TEXT,
            fichier_audio_path TEXT,
            fichier_audio_nom_original TEXT,
            
            -- Champs legacy (compatibilité)
            url_contenu TEXT,
            fichier_path TEXT,
            nom_fichier_original TEXT,
            
            -- Champs généraux
            duree_minutes INTEGER,
            difficulte VARCHAR(20) DEFAULT 'facile',
            tags TEXT,
            ordre INTEGER DEFAULT 0,
            actif BOOLEAN DEFAULT TRUE,
            
            -- Traçabilité
            cree_le TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
            cree_par_id INTEGER REFERENCES "user"(id)
        );
        
        RAISE NOTICE 'Table ressourceelearning créée avec succès';
    ELSE
        RAISE NOTICE 'Table ressourceelearning existe déjà';
    END IF;
END $$;

-- 2. Ajouter les colonnes manquantes pour les URLs par type
DO $$
BEGIN
    -- URL vidéo
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'ressourceelearning' AND column_name = 'url_contenu_video') THEN
        ALTER TABLE ressourceelearning ADD COLUMN url_contenu_video TEXT;
        RAISE NOTICE 'Colonne url_contenu_video ajoutée';
    END IF;
    
    -- URL document
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'ressourceelearning' AND column_name = 'url_contenu_document') THEN
        ALTER TABLE ressourceelearning ADD COLUMN url_contenu_document TEXT;
        RAISE NOTICE 'Colonne url_contenu_document ajoutée';
    END IF;
    
    -- URL audio
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'ressourceelearning' AND column_name = 'url_contenu_audio') THEN
        ALTER TABLE ressourceelearning ADD COLUMN url_contenu_audio TEXT;
        RAISE NOTICE 'Colonne url_contenu_audio ajoutée';
    END IF;
    
    -- URL lien
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'ressourceelearning' AND column_name = 'url_contenu_lien') THEN
        ALTER TABLE ressourceelearning ADD COLUMN url_contenu_lien TEXT;
        RAISE NOTICE 'Colonne url_contenu_lien ajoutée';
    END IF;
END $$;

-- 3. Ajouter les colonnes manquantes pour les fichiers par type
DO $$
BEGIN
    -- Fichier vidéo
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'ressourceelearning' AND column_name = 'fichier_video_path') THEN
        ALTER TABLE ressourceelearning ADD COLUMN fichier_video_path TEXT;
        RAISE NOTICE 'Colonne fichier_video_path ajoutée';
    END IF;
    
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'ressourceelearning' AND column_name = 'fichier_video_nom_original') THEN
        ALTER TABLE ressourceelearning ADD COLUMN fichier_video_nom_original TEXT;
        RAISE NOTICE 'Colonne fichier_video_nom_original ajoutée';
    END IF;
    
    -- Fichier document
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'ressourceelearning' AND column_name = 'fichier_document_path') THEN
        ALTER TABLE ressourceelearning ADD COLUMN fichier_document_path TEXT;
        RAISE NOTICE 'Colonne fichier_document_path ajoutée';
    END IF;
    
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'ressourceelearning' AND column_name = 'fichier_document_nom_original') THEN
        ALTER TABLE ressourceelearning ADD COLUMN fichier_document_nom_original TEXT;
        RAISE NOTICE 'Colonne fichier_document_nom_original ajoutée';
    END IF;
    
    -- Fichier audio
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'ressourceelearning' AND column_name = 'fichier_audio_path') THEN
        ALTER TABLE ressourceelearning ADD COLUMN fichier_audio_path TEXT;
        RAISE NOTICE 'Colonne fichier_audio_path ajoutée';
    END IF;
    
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'ressourceelearning' AND column_name = 'fichier_audio_nom_original') THEN
        ALTER TABLE ressourceelearning ADD COLUMN fichier_audio_nom_original TEXT;
        RAISE NOTICE 'Colonne fichier_audio_nom_original ajoutée';
    END IF;
END $$;

-- 4. Ajouter les colonnes manquantes pour les champs généraux
DO $$
BEGIN
    -- Description
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'ressourceelearning' AND column_name = 'description') THEN
        ALTER TABLE ressourceelearning ADD COLUMN description TEXT;
        RAISE NOTICE 'Colonne description ajoutée';
    END IF;
    
    -- Durée
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'ressourceelearning' AND column_name = 'duree_minutes') THEN
        ALTER TABLE ressourceelearning ADD COLUMN duree_minutes INTEGER;
        RAISE NOTICE 'Colonne duree_minutes ajoutée';
    END IF;
    
    -- Difficulté
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'ressourceelearning' AND column_name = 'difficulte') THEN
        ALTER TABLE ressourceelearning ADD COLUMN difficulte VARCHAR(20) DEFAULT 'facile';
        RAISE NOTICE 'Colonne difficulte ajoutée';
    END IF;
    
    -- Tags
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'ressourceelearning' AND column_name = 'tags') THEN
        ALTER TABLE ressourceelearning ADD COLUMN tags TEXT;
        RAISE NOTICE 'Colonne tags ajoutée';
    END IF;
    
    -- Ordre
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'ressourceelearning' AND column_name = 'ordre') THEN
        ALTER TABLE ressourceelearning ADD COLUMN ordre INTEGER DEFAULT 0;
        RAISE NOTICE 'Colonne ordre ajoutée';
    END IF;
    
    -- Actif
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'ressourceelearning' AND column_name = 'actif') THEN
        ALTER TABLE ressourceelearning ADD COLUMN actif BOOLEAN DEFAULT TRUE;
        RAISE NOTICE 'Colonne actif ajoutée';
    END IF;
END $$;

-- 5. Ajouter les colonnes manquantes pour la traçabilité
DO $$
BEGIN
    -- Créé le
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'ressourceelearning' AND column_name = 'cree_le') THEN
        ALTER TABLE ressourceelearning ADD COLUMN cree_le TIMESTAMP WITH TIME ZONE DEFAULT NOW();
        RAISE NOTICE 'Colonne cree_le ajoutée';
    END IF;
    
    -- Créé par
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'ressourceelearning' AND column_name = 'cree_par_id') THEN
        ALTER TABLE ressourceelearning ADD COLUMN cree_par_id INTEGER REFERENCES "user"(id);
        RAISE NOTICE 'Colonne cree_par_id ajoutée';
    END IF;
END $$;

-- 6. Ajouter les colonnes legacy si elles n'existent pas
DO $$
BEGIN
    -- URL contenu legacy
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'ressourceelearning' AND column_name = 'url_contenu') THEN
        ALTER TABLE ressourceelearning ADD COLUMN url_contenu TEXT;
        RAISE NOTICE 'Colonne url_contenu (legacy) ajoutée';
    END IF;
    
    -- Fichier path legacy
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'ressourceelearning' AND column_name = 'fichier_path') THEN
        ALTER TABLE ressourceelearning ADD COLUMN fichier_path TEXT;
        RAISE NOTICE 'Colonne fichier_path (legacy) ajoutée';
    END IF;
    
    -- Nom fichier original legacy
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'ressourceelearning' AND column_name = 'nom_fichier_original') THEN
        ALTER TABLE ressourceelearning ADD COLUMN nom_fichier_original TEXT;
        RAISE NOTICE 'Colonne nom_fichier_original (legacy) ajoutée';
    END IF;
END $$;

-- 7. Vérification finale
DO $$
DECLARE
    col_count INTEGER;
BEGIN
    SELECT COUNT(*) INTO col_count
    FROM information_schema.columns 
    WHERE table_name = 'ressourceelearning';
    
    RAISE NOTICE 'Migration terminée. Nombre total de colonnes: %', col_count;
    
    -- Lister toutes les colonnes
    RAISE NOTICE 'Colonnes présentes:';
    FOR rec IN 
        SELECT column_name, data_type, is_nullable, column_default
        FROM information_schema.columns 
        WHERE table_name = 'ressourceelearning'
        ORDER BY ordinal_position
    LOOP
        RAISE NOTICE '  - % (%): nullable=%, default=%', 
            rec.column_name, rec.data_type, rec.is_nullable, rec.column_default;
    END LOOP;
END $$;

-- 8. Créer des index pour améliorer les performances
CREATE INDEX IF NOT EXISTS idx_ressourceelearning_type ON ressourceelearning(type_ressource);
CREATE INDEX IF NOT EXISTS idx_ressourceelearning_actif ON ressourceelearning(actif);
CREATE INDEX IF NOT EXISTS idx_ressourceelearning_cree_par ON ressourceelearning(cree_par_id);
CREATE INDEX IF NOT EXISTS idx_ressourceelearning_ordre ON ressourceelearning(ordre);

RAISE NOTICE 'Index créés pour améliorer les performances';

-- 9. Message de fin
DO $$
BEGIN
    RAISE NOTICE 'Migration de la table ressourceelearning terminée avec succès !';
    RAISE NOTICE 'Tous les champs nécessaires pour la sauvegarde multi-types sont maintenant disponibles';
END $$;
