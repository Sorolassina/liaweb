-- =====================================================
-- CORRECTION DES AUTRES PROBLÈMES DÉTECTÉS
-- =====================================================

-- 1. Ajouter la colonne 'statut' manquante dans la table 'programme'
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'programme' AND column_name = 'statut') THEN
        ALTER TABLE programme ADD COLUMN statut VARCHAR(20) DEFAULT 'actif';
        RAISE NOTICE '✅ Colonne statut ajoutée dans la table programme';
    ELSE
        RAISE NOTICE 'Colonne statut existe déjà dans la table programme';
    END IF;
END $$;

-- 2. Ajouter la colonne 'decision' manquante dans la table 'jury'
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'jury' AND column_name = 'decision') THEN
        ALTER TABLE jury ADD COLUMN decision VARCHAR(20);
        RAISE NOTICE '✅ Colonne decision ajoutée dans la table jury';
    ELSE
        RAISE NOTICE 'Colonne decision existe déjà dans la table jury';
    END IF;
END $$;

-- 3. Créer la table de liaison ModuleRessource si elle n'existe pas
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'moduleressource') THEN
        CREATE TABLE moduleressource (
            module_id INTEGER NOT NULL,
            ressource_id INTEGER NOT NULL,
            ordre INTEGER DEFAULT 0,
            obligatoire BOOLEAN DEFAULT TRUE,
            PRIMARY KEY (module_id, ressource_id),
            FOREIGN KEY (module_id) REFERENCES moduleelearning(id) ON DELETE CASCADE,
            FOREIGN KEY (ressource_id) REFERENCES ressourceelearning(id) ON DELETE CASCADE
        );
        RAISE NOTICE '✅ Table moduleressource créée';
    ELSE
        RAISE NOTICE 'Table moduleressource existe déjà';
    END IF;
END $$;

-- 4. Vérifier et créer les autres tables e-learning si nécessaire
DO $$
BEGIN
    -- Table ModuleElearning
    IF NOT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'moduleelearning') THEN
        CREATE TABLE moduleelearning (
            id SERIAL PRIMARY KEY,
            titre VARCHAR NOT NULL,
            description TEXT,
            programme_id INTEGER NOT NULL REFERENCES programme(id),
            objectifs TEXT,
            prerequis TEXT,
            duree_totale_minutes INTEGER,
            difficulte VARCHAR(20) DEFAULT 'facile',
            statut VARCHAR(20) DEFAULT 'brouillon',
            ordre INTEGER DEFAULT 0,
            actif BOOLEAN DEFAULT TRUE,
            cree_le TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
            cree_par_id INTEGER REFERENCES "user"(id)
        );
        RAISE NOTICE '✅ Table moduleelearning créée';
    END IF;
    
    -- Table ProgressionElearning
    IF NOT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'progressionelearning') THEN
        CREATE TABLE progressionelearning (
            id SERIAL PRIMARY KEY,
            inscription_id INTEGER NOT NULL REFERENCES inscription(id),
            module_id INTEGER NOT NULL REFERENCES moduleelearning(id),
            ressource_id INTEGER NOT NULL REFERENCES ressourceelearning(id),
            statut VARCHAR(20) DEFAULT 'non_commence',
            temps_consacre_minutes INTEGER DEFAULT 0,
            score FLOAT,
            date_debut TIMESTAMP WITH TIME ZONE,
            date_fin TIMESTAMP WITH TIME ZONE,
            derniere_activite TIMESTAMP WITH TIME ZONE,
            notes TEXT,
            cree_le TIMESTAMP WITH TIME ZONE DEFAULT NOW()
        );
        RAISE NOTICE '✅ Table progressionelearning créée';
    END IF;
    
    -- Table QuizElearning
    IF NOT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'quizelearning') THEN
        CREATE TABLE quizelearning (
            id SERIAL PRIMARY KEY,
            ressource_id INTEGER NOT NULL REFERENCES ressourceelearning(id),
            question TEXT NOT NULL,
            type_question VARCHAR(20) NOT NULL,
            options TEXT,
            reponse_correcte TEXT NOT NULL,
            explication TEXT,
            points INTEGER DEFAULT 1,
            ordre INTEGER DEFAULT 0,
            actif BOOLEAN DEFAULT TRUE
        );
        RAISE NOTICE '✅ Table quizelearning créée';
    END IF;
    
    -- Table ReponseQuiz
    IF NOT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'reponsequiz') THEN
        CREATE TABLE reponsequiz (
            id SERIAL PRIMARY KEY,
            inscription_id INTEGER NOT NULL REFERENCES inscription(id),
            quiz_id INTEGER NOT NULL REFERENCES quizelearning(id),
            reponse_donnee TEXT NOT NULL,
            est_correcte BOOLEAN NOT NULL,
            points_obtenus INTEGER DEFAULT 0,
            date_reponse TIMESTAMP WITH TIME ZONE DEFAULT NOW()
        );
        RAISE NOTICE '✅ Table reponsequiz créée';
    END IF;
    
    -- Table CertificatElearning
    IF NOT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'certificatelearning') THEN
        CREATE TABLE certificatelearning (
            id SERIAL PRIMARY KEY,
            inscription_id INTEGER NOT NULL REFERENCES inscription(id),
            module_id INTEGER REFERENCES moduleelearning(id),
            titre VARCHAR NOT NULL,
            description TEXT,
            score_final FLOAT,
            temps_total_minutes INTEGER NOT NULL,
            date_obtention TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
            fichier_certificat TEXT,
            valide BOOLEAN DEFAULT TRUE
        );
        RAISE NOTICE '✅ Table certificatelearning créée';
    END IF;
    
    -- Table ObjectifElearning
    IF NOT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'objectifelearning') THEN
        CREATE TABLE objectifelearning (
            id SERIAL PRIMARY KEY,
            programme_id INTEGER NOT NULL REFERENCES programme(id),
            titre VARCHAR NOT NULL,
            description TEXT,
            temps_minimum_minutes INTEGER NOT NULL,
            modules_obligatoires TEXT,
            date_debut TIMESTAMP WITH TIME ZONE,
            date_fin TIMESTAMP WITH TIME ZONE,
            actif BOOLEAN DEFAULT TRUE,
            cree_le TIMESTAMP WITH TIME ZONE DEFAULT NOW()
        );
        RAISE NOTICE '✅ Table objectifelearning créée';
    END IF;
END $$;

-- 5. Créer des index pour améliorer les performances
CREATE INDEX IF NOT EXISTS idx_moduleelearning_programme ON moduleelearning(programme_id);
CREATE INDEX IF NOT EXISTS idx_moduleelearning_actif ON moduleelearning(actif);
CREATE INDEX IF NOT EXISTS idx_progressionelearning_inscription ON progressionelearning(inscription_id);
CREATE INDEX IF NOT EXISTS idx_progressionelearning_module ON progressionelearning(module_id);
CREATE INDEX IF NOT EXISTS idx_progressionelearning_ressource ON progressionelearning(ressource_id);
CREATE INDEX IF NOT EXISTS idx_quizelearning_ressource ON quizelearning(ressource_id);
CREATE INDEX IF NOT EXISTS idx_reponsequiz_inscription ON reponsequiz(inscription_id);
CREATE INDEX IF NOT EXISTS idx_reponsequiz_quiz ON reponsequiz(quiz_id);
CREATE INDEX IF NOT EXISTS idx_certificatelearning_inscription ON certificatelearning(inscription_id);
CREATE INDEX IF NOT EXISTS idx_objectifelearning_programme ON objectifelearning(programme_id);

-- 6. Message de fin
DO $$
BEGIN
    RAISE NOTICE '🎉 Correction des problèmes de base de données terminée !';
    RAISE NOTICE '📊 Toutes les tables e-learning sont maintenant disponibles';
    RAISE NOTICE '🔧 Colonnes manquantes ajoutées';
    RAISE NOTICE '⚡ Index de performance créés';
END $$;
