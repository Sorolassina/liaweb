-- Script minimal pour créer les tables du système de Codéveloppement
-- À exécuter en tant qu'administrateur PostgreSQL

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

-- Table des présentations lors des séances
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

-- Table des contributions aux présentations
CREATE TABLE IF NOT EXISTS contributioncodev (
    id SERIAL PRIMARY KEY,
    presentation_id INTEGER NOT NULL REFERENCES presentationcodev(id) ON DELETE CASCADE,
    contributeur_id INTEGER NOT NULL REFERENCES inscription(id),
    type_contribution VARCHAR(20) DEFAULT 'suggestion',
    contenu TEXT NOT NULL,
    ordre_contribution INTEGER,
    cree_le TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Table de participation aux séances
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

-- Accorder les permissions à l'utilisateur liauser
GRANT ALL PRIVILEGES ON cyclecodev TO liauser;
GRANT ALL PRIVILEGES ON groupecodev TO liauser;
GRANT ALL PRIVILEGES ON membregroupecodev TO liauser;
GRANT ALL PRIVILEGES ON seancecodev TO liauser;
GRANT ALL PRIVILEGES ON presentationcodev TO liauser;
GRANT ALL PRIVILEGES ON contributioncodev TO liauser;
GRANT ALL PRIVILEGES ON participationseance TO liauser;

-- Accorder les permissions sur les séquences
GRANT ALL PRIVILEGES ON SEQUENCE cyclecodev_id_seq TO liauser;
GRANT ALL PRIVILEGES ON SEQUENCE groupecodev_id_seq TO liauser;
GRANT ALL PRIVILEGES ON SEQUENCE membregroupecodev_id_seq TO liauser;
GRANT ALL PRIVILEGES ON SEQUENCE seancecodev_id_seq TO liauser;
GRANT ALL PRIVILEGES ON SEQUENCE presentationcodev_id_seq TO liauser;
GRANT ALL PRIVILEGES ON SEQUENCE contributioncodev_id_seq TO liauser;
GRANT ALL PRIVILEGES ON SEQUENCE participationseance_id_seq TO liauser;

-- Vérification
SELECT 'Tables créées avec succès' as message;
SELECT table_name FROM information_schema.tables WHERE table_schema = 'public' AND table_name LIKE '%codev%' ORDER BY table_name;
