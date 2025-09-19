-- Script de création des tables e-learning
-- Exécuter ce script dans PostgreSQL pour créer toutes les tables nécessaires

-- Table des ressources e-learning
CREATE TABLE IF NOT EXISTS ressourceelearning (
    id SERIAL PRIMARY KEY,
    titre VARCHAR(255) NOT NULL,
    description TEXT,
    type_ressource VARCHAR(20) NOT NULL CHECK (type_ressource IN ('video', 'document', 'quiz', 'lien', 'audio')),
    url_contenu TEXT,
    fichier_path TEXT,
    duree_minutes INTEGER,
    difficulte VARCHAR(20) DEFAULT 'facile' CHECK (difficulte IN ('facile', 'moyen', 'difficile')),
    tags TEXT,
    actif BOOLEAN DEFAULT TRUE,
    ordre INTEGER DEFAULT 0,
    cree_le TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    cree_par_id INTEGER REFERENCES "user"(id)
);

-- Table des modules e-learning
CREATE TABLE IF NOT EXISTS moduleelearning (
    id SERIAL PRIMARY KEY,
    titre VARCHAR(255) NOT NULL,
    description TEXT,
    programme_id INTEGER NOT NULL REFERENCES programme(id),
    objectifs TEXT,
    prerequis TEXT,
    duree_totale_minutes INTEGER,
    difficulte VARCHAR(20) DEFAULT 'facile' CHECK (difficulte IN ('facile', 'moyen', 'difficile')),
    statut VARCHAR(20) DEFAULT 'brouillon' CHECK (statut IN ('brouillon', 'actif', 'archive')),
    ordre INTEGER DEFAULT 0,
    actif BOOLEAN DEFAULT TRUE,
    cree_le TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    cree_par_id INTEGER REFERENCES "user"(id)
);

-- Table de liaison entre modules et ressources
CREATE TABLE IF NOT EXISTS moduleressource (
    module_id INTEGER NOT NULL REFERENCES moduleelearning(id) ON DELETE CASCADE,
    ressource_id INTEGER NOT NULL REFERENCES ressourceelearning(id) ON DELETE CASCADE,
    ordre INTEGER DEFAULT 0,
    obligatoire BOOLEAN DEFAULT TRUE,
    PRIMARY KEY (module_id, ressource_id)
);

-- Table de progression des candidats
CREATE TABLE IF NOT EXISTS progressionelearning (
    id SERIAL PRIMARY KEY,
    inscription_id INTEGER NOT NULL REFERENCES inscription(id),
    module_id INTEGER NOT NULL REFERENCES moduleelearning(id),
    ressource_id INTEGER NOT NULL REFERENCES ressourceelearning(id),
    statut VARCHAR(20) DEFAULT 'non_commence' CHECK (statut IN ('non_commence', 'en_cours', 'termine', 'abandonne')),
    temps_consacre_minutes INTEGER DEFAULT 0,
    score DECIMAL(5,2),
    date_debut TIMESTAMP WITH TIME ZONE,
    date_fin TIMESTAMP WITH TIME ZONE,
    derniere_activite TIMESTAMP WITH TIME ZONE,
    notes TEXT,
    cree_le TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Table des objectifs e-learning
CREATE TABLE IF NOT EXISTS objectifelearning (
    id SERIAL PRIMARY KEY,
    programme_id INTEGER NOT NULL REFERENCES programme(id),
    titre VARCHAR(255) NOT NULL,
    description TEXT,
    temps_minimum_minutes INTEGER NOT NULL,
    modules_obligatoires TEXT,
    date_debut TIMESTAMP WITH TIME ZONE,
    date_fin TIMESTAMP WITH TIME ZONE,
    actif BOOLEAN DEFAULT TRUE,
    cree_le TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Table des quiz
CREATE TABLE IF NOT EXISTS quizelearning (
    id SERIAL PRIMARY KEY,
    ressource_id INTEGER NOT NULL REFERENCES ressourceelearning(id) ON DELETE CASCADE,
    question TEXT NOT NULL,
    type_question VARCHAR(20) DEFAULT 'choix_multiple' CHECK (type_question IN ('choix_multiple', 'vrai_faux', 'texte_libre')),
    options_reponse JSONB,
    reponse_correcte TEXT NOT NULL,
    points INTEGER DEFAULT 1,
    ordre INTEGER DEFAULT 0,
    explication TEXT,
    actif BOOLEAN DEFAULT TRUE,
    cree_le TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Table des réponses aux quiz
CREATE TABLE IF NOT EXISTS reponsequiz (
    id SERIAL PRIMARY KEY,
    progression_id INTEGER NOT NULL REFERENCES progressionelearning(id),
    quiz_id INTEGER NOT NULL REFERENCES quizelearning(id),
    reponse_candidat TEXT NOT NULL,
    est_correcte BOOLEAN,
    points_obtenus INTEGER DEFAULT 0,
    temps_reponse_secondes INTEGER,
    cree_le TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Table des certificats
CREATE TABLE IF NOT EXISTS certificat_elearning (
    id SERIAL PRIMARY KEY,
    inscription_id INTEGER NOT NULL REFERENCES inscription(id),
    module_id INTEGER REFERENCES moduleelearning(id),
    titre VARCHAR(255) NOT NULL,
    description TEXT,
    score_final DECIMAL(5,2),
    temps_total_minutes INTEGER,
    date_obtention TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    fichier_certificat TEXT,
    actif BOOLEAN DEFAULT TRUE,
    cree_le TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Création des index pour améliorer les performances
CREATE INDEX IF NOT EXISTS idx_ressourceelearning_type ON ressourceelearning(type_ressource);
CREATE INDEX IF NOT EXISTS idx_ressourceelearning_actif ON ressourceelearning(actif);
CREATE INDEX IF NOT EXISTS idx_moduleelearning_programme ON moduleelearning(programme_id);
CREATE INDEX IF NOT EXISTS idx_moduleelearning_statut ON moduleelearning(statut);
CREATE INDEX IF NOT EXISTS idx_progressionelearning_inscription ON progressionelearning(inscription_id);
CREATE INDEX IF NOT EXISTS idx_progressionelearning_module ON progressionelearning(module_id);
CREATE INDEX IF NOT EXISTS idx_progressionelearning_ressource ON progressionelearning(ressource_id);
CREATE INDEX IF NOT EXISTS idx_progressionelearning_statut ON progressionelearning(statut);
CREATE INDEX IF NOT EXISTS idx_objectifelearning_programme ON objectifelearning(programme_id);
CREATE INDEX IF NOT EXISTS idx_quizelearning_ressource ON quizelearning(ressource_id);
CREATE INDEX IF NOT EXISTS idx_reponsequiz_progression ON reponsequiz(progression_id);
CREATE INDEX IF NOT EXISTS idx_certificat_inscription ON certificat_elearning(inscription_id);

-- Attribution des permissions à l'utilisateur liauser
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO liauser;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO liauser;

-- Commentaires sur les tables
COMMENT ON TABLE ressourceelearning IS 'Ressources pédagogiques (vidéos, documents, quiz, etc.)';
COMMENT ON TABLE moduleelearning IS 'Modules de formation e-learning';
COMMENT ON TABLE moduleressource IS 'Liaison entre modules et ressources';
COMMENT ON TABLE progressionelearning IS 'Progression des candidats dans le e-learning';
COMMENT ON TABLE objectifelearning IS 'Objectifs e-learning obligatoires par programme';
COMMENT ON TABLE quizelearning IS 'Questions de quiz associées aux ressources';
COMMENT ON TABLE reponsequiz IS 'Réponses des candidats aux quiz';
COMMENT ON TABLE certificat_elearning IS 'Certificats de completion e-learning';

-- Insertion de données de test (optionnel)
-- Vous pouvez décommenter ces lignes pour ajouter des données de test

/*
-- Programme de test
INSERT INTO programme (nom, description, actif) VALUES 
('Formation E-learning Test', 'Programme de test pour l''e-learning', true)
ON CONFLICT DO NOTHING;

-- Module de test
INSERT INTO moduleelearning (titre, description, programme_id, objectifs, statut, actif) VALUES 
('Module Test', 'Module de test pour l''e-learning', 1, 'Apprendre les bases de l''e-learning', 'actif', true)
ON CONFLICT DO NOTHING;

-- Ressource de test
INSERT INTO ressourceelearning (titre, description, type_ressource, url_contenu, duree_minutes, difficulte, actif) VALUES 
('Vidéo Introduction', 'Vidéo d''introduction à l''e-learning', 'video', 'https://example.com/video', 15, 'facile', true)
ON CONFLICT DO NOTHING;

-- Liaison module-ressource
INSERT INTO moduleressource (module_id, ressource_id, ordre, obligatoire) VALUES 
(1, 1, 1, true)
ON CONFLICT DO NOTHING;
*/

-- Message de confirmation
DO $$
BEGIN
    RAISE NOTICE 'Tables e-learning créées avec succès !';
    RAISE NOTICE 'Permissions accordées à l''utilisateur liauser';
    RAISE NOTICE 'Index créés pour optimiser les performances';
END $$;