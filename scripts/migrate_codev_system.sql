-- Migration pour le système de Codéveloppement
-- À exécuter dans PostgreSQL

-- 1. Créer les tables pour le codéveloppement

-- Table des cycles de codéveloppement
CREATE TABLE IF NOT EXISTS cyclecodev (
    id SERIAL PRIMARY KEY,
    nom VARCHAR(100) NOT NULL,
    description VARCHAR(500),
    programme_id INTEGER NOT NULL REFERENCES programme(id),
    promotion_id INTEGER REFERENCES promotion(id),
    date_debut DATE NOT NULL,
    date_fin DATE NOT NULL,
    nombre_seances_prevues INTEGER DEFAULT 6,
    duree_seance_minutes INTEGER DEFAULT 180,
    animateur_principal_id INTEGER REFERENCES "user"(id),
    statut VARCHAR(20) DEFAULT 'planifie',
    objectifs_cycle TEXT,
    cree_le TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Table des groupes de codéveloppement dans un cycle
CREATE TABLE IF NOT EXISTS groupecodev (
    id SERIAL PRIMARY KEY,
    cycle_id INTEGER NOT NULL REFERENCES cyclecodev(id) ON DELETE CASCADE,
    groupe_id INTEGER NOT NULL REFERENCES groupe(id),
    nom_groupe VARCHAR(100) NOT NULL,
    animateur_id INTEGER REFERENCES "user"(id),
    capacite_max INTEGER DEFAULT 12,
    statut VARCHAR(20) DEFAULT 'en_constitution',
    date_creation TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Table des membres d'un groupe de codéveloppement
CREATE TABLE IF NOT EXISTS membregroupecodev (
    id SERIAL PRIMARY KEY,
    groupe_codev_id INTEGER NOT NULL REFERENCES groupecodev(id) ON DELETE CASCADE,
    candidat_id INTEGER NOT NULL REFERENCES inscription(id),
    date_integration TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    statut VARCHAR(20) DEFAULT 'actif',
    role_special VARCHAR(50),
    notes_integration TEXT
);

-- Table des séances de codéveloppement
CREATE TABLE IF NOT EXISTS seancecodev (
    id SERIAL PRIMARY KEY,
    groupe_id INTEGER NOT NULL REFERENCES groupe(id),
    numero_seance INTEGER NOT NULL,
    date_seance TIMESTAMP WITH TIME ZONE NOT NULL,
    lieu VARCHAR(200),
    animateur_id INTEGER REFERENCES "user"(id),
    statut VARCHAR(20) DEFAULT 'planifiee',
    duree_minutes INTEGER DEFAULT 180,
    objectifs TEXT,
    notes_animateur TEXT,
    cree_le TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Table des présentations lors d'une séance
CREATE TABLE IF NOT EXISTS presentationcodev (
    id SERIAL PRIMARY KEY,
    seance_id INTEGER NOT NULL REFERENCES seancecodev(id) ON DELETE CASCADE,
    candidat_id INTEGER NOT NULL REFERENCES inscription(id),
    ordre_presentation INTEGER NOT NULL,
    probleme_expose TEXT NOT NULL,
    contexte TEXT,
    solutions_proposees TEXT,
    engagement_candidat TEXT,
    delai_engagement DATE,
    statut VARCHAR(20) DEFAULT 'en_attente',
    notes_candidat TEXT,
    cree_le TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Table des contributions à une présentation
CREATE TABLE IF NOT EXISTS contributioncodev (
    id SERIAL PRIMARY KEY,
    presentation_id INTEGER NOT NULL REFERENCES presentationcodev(id) ON DELETE CASCADE,
    contributeur_id INTEGER NOT NULL REFERENCES inscription(id),
    type_contribution VARCHAR(20) NOT NULL,
    contenu TEXT NOT NULL,
    ordre_contribution INTEGER,
    cree_le TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Table des participations aux séances
CREATE TABLE IF NOT EXISTS participationseance (
    id SERIAL PRIMARY KEY,
    seance_id INTEGER NOT NULL REFERENCES seancecodev(id) ON DELETE CASCADE,
    candidat_id INTEGER NOT NULL REFERENCES inscription(id),
    statut_presence VARCHAR(20) DEFAULT 'absent',
    heure_arrivee TIMESTAMP WITH TIME ZONE,
    heure_depart TIMESTAMP WITH TIME ZONE,
    notes_participant TEXT,
    evaluation_seance INTEGER CHECK (evaluation_seance >= 1 AND evaluation_seance <= 5),
    commentaires TEXT,
    cree_le TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- 2. Créer les index pour les performances

CREATE INDEX IF NOT EXISTS idx_cyclecodev_programme ON cyclecodev(programme_id);
CREATE INDEX IF NOT EXISTS idx_cyclecodev_promotion ON cyclecodev(promotion_id);
CREATE INDEX IF NOT EXISTS idx_cyclecodev_statut ON cyclecodev(statut);
CREATE INDEX IF NOT EXISTS idx_cyclecodev_dates ON cyclecodev(date_debut, date_fin);

CREATE INDEX IF NOT EXISTS idx_groupecodev_cycle ON groupecodev(cycle_id);
CREATE INDEX IF NOT EXISTS idx_groupecodev_groupe ON groupecodev(groupe_id);
CREATE INDEX IF NOT EXISTS idx_groupecodev_statut ON groupecodev(statut);

CREATE INDEX IF NOT EXISTS idx_membregroupecodev_groupe ON membregroupecodev(groupe_codev_id);
CREATE INDEX IF NOT EXISTS idx_membregroupecodev_candidat ON membregroupecodev(candidat_id);
CREATE INDEX IF NOT EXISTS idx_membregroupecodev_statut ON membregroupecodev(statut);

CREATE INDEX IF NOT EXISTS idx_seancecodev_groupe ON seancecodev(groupe_id);
CREATE INDEX IF NOT EXISTS idx_seancecodev_date ON seancecodev(date_seance);
CREATE INDEX IF NOT EXISTS idx_seancecodev_statut ON seancecodev(statut);
CREATE INDEX IF NOT EXISTS idx_seancecodev_numero ON seancecodev(numero_seance);

CREATE INDEX IF NOT EXISTS idx_presentationcodev_seance ON presentationcodev(seance_id);
CREATE INDEX IF NOT EXISTS idx_presentationcodev_candidat ON presentationcodev(candidat_id);
CREATE INDEX IF NOT EXISTS idx_presentationcodev_statut ON presentationcodev(statut);
CREATE INDEX IF NOT EXISTS idx_presentationcodev_ordre ON presentationcodev(ordre_presentation);

CREATE INDEX IF NOT EXISTS idx_contributioncodev_presentation ON contributioncodev(presentation_id);
CREATE INDEX IF NOT EXISTS idx_contributioncodev_contributeur ON contributioncodev(contributeur_id);
CREATE INDEX IF NOT EXISTS idx_contributioncodev_type ON contributioncodev(type_contribution);

CREATE INDEX IF NOT EXISTS idx_participationseance_seance ON participationseance(seance_id);
CREATE INDEX IF NOT EXISTS idx_participationseance_candidat ON participationseance(candidat_id);
CREATE INDEX IF NOT EXISTS idx_participationseance_statut ON participationseance(statut_presence);

-- 3. Ajouter des contraintes d'unicité

ALTER TABLE cyclecodev ADD CONSTRAINT uk_cyclecodev_nom_programme UNIQUE (nom, programme_id);
ALTER TABLE groupecodev ADD CONSTRAINT uk_groupecodev_nom_cycle UNIQUE (nom_groupe, cycle_id);
ALTER TABLE membregroupecodev ADD CONSTRAINT uk_membregroupecodev_candidat_groupe UNIQUE (candidat_id, groupe_codev_id);
ALTER TABLE seancecodev ADD CONSTRAINT uk_seancecodev_numero_groupe UNIQUE (numero_seance, groupe_id);
ALTER TABLE presentationcodev ADD CONSTRAINT uk_presentationcodev_ordre_seance UNIQUE (ordre_presentation, seance_id);
ALTER TABLE participationseance ADD CONSTRAINT uk_participationseance_candidat_seance UNIQUE (candidat_id, seance_id);

-- 4. Insérer des données de test (optionnel)

-- Créer un cycle de test
INSERT INTO cyclecodev (nom, programme_id, date_debut, date_fin, nombre_seances_prevues, statut) 
VALUES ('Cycle Test ACD 2024', 1, '2024-01-15', '2024-04-15', 6, 'planifie')
ON CONFLICT (nom, programme_id) DO NOTHING;

-- Récupérer l'ID du cycle créé
DO $$
DECLARE
    cycle_id_var INTEGER;
    groupe_id_var INTEGER;
BEGIN
    -- Récupérer l'ID du cycle de test
    SELECT id INTO cycle_id_var FROM cyclecodev WHERE nom = 'Cycle Test ACD 2024' LIMIT 1;
    
    -- Récupérer l'ID du premier groupe
    SELECT id INTO groupe_id_var FROM groupe WHERE actif = true LIMIT 1;
    
    -- Créer un groupe de codéveloppement de test
    IF cycle_id_var IS NOT NULL AND groupe_id_var IS NOT NULL THEN
        INSERT INTO groupecodev (cycle_id, groupe_id, nom_groupe, capacite_max, statut)
        VALUES (cycle_id_var, groupe_id_var, 'Groupe Alpha - Cycle Test', 12, 'en_constitution')
        ON CONFLICT (nom_groupe, cycle_id) DO NOTHING;
    END IF;
END $$;

-- 5. Ajouter des commentaires pour la documentation

COMMENT ON TABLE cyclecodev IS 'Cycles de codéveloppement - Série de séances organisées';
COMMENT ON TABLE groupecodev IS 'Groupes de codéveloppement dans un cycle';
COMMENT ON TABLE membregroupecodev IS 'Membres d''un groupe de codéveloppement';
COMMENT ON TABLE seancecodev IS 'Séances individuelles de codéveloppement';
COMMENT ON TABLE presentationcodev IS 'Présentations de problématiques lors des séances';
COMMENT ON TABLE contributioncodev IS 'Contributions des participants aux présentations';
COMMENT ON TABLE participationseance IS 'Participation et présence aux séances';

-- 6. Vérification finale
SELECT 'Migration du système de codéveloppement terminée avec succès' as status;

-- Afficher les tables créées
SELECT 
    schemaname,
    tablename,
    tableowner
FROM pg_tables 
WHERE tablename IN (
    'cyclecodev', 'groupecodev', 'membregroupecodev', 
    'seancecodev', 'presentationcodev', 'contributioncodev', 'participationseance'
)
ORDER BY tablename;
