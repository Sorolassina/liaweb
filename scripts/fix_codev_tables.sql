-- Script corrigé pour créer les tables manquantes du système de Codéveloppement
-- À exécuter dans PostgreSQL

-- Supprimer le type existant s'il existe (résout le conflit de nom)
DROP TYPE IF EXISTS groupecodev CASCADE;

-- Supprimer les tables si elles existent déjà
DROP TABLE IF EXISTS groupecodev CASCADE;
DROP TABLE IF EXISTS membregroupecodev CASCADE;

-- Créer la table des groupes de codéveloppement dans un cycle
CREATE TABLE groupecodev (
    id SERIAL PRIMARY KEY,
    cycle_id INTEGER NOT NULL REFERENCES cyclecodev(id) ON DELETE CASCADE,
    groupe_id INTEGER NOT NULL REFERENCES groupe(id),
    nom_groupe VARCHAR(100) NOT NULL,
    animateur_id INTEGER REFERENCES "user"(id),
    capacite_max INTEGER DEFAULT 12,
    statut VARCHAR(20) DEFAULT 'en_constitution',
    date_creation TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Créer la table des membres d'un groupe de codéveloppement
CREATE TABLE membregroupecodev (
    id SERIAL PRIMARY KEY,
    groupe_codev_id INTEGER NOT NULL REFERENCES groupecodev(id) ON DELETE CASCADE,
    candidat_id INTEGER NOT NULL REFERENCES inscription(id),
    date_integration TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    statut VARCHAR(20) DEFAULT 'actif',
    role_special VARCHAR(50),
    notes_integration TEXT
);

-- Accorder les permissions à l'utilisateur liauser
GRANT ALL PRIVILEGES ON groupecodev TO liauser;
GRANT ALL PRIVILEGES ON membregroupecodev TO liauser;

-- Accorder les permissions sur les séquences
GRANT ALL PRIVILEGES ON SEQUENCE groupecodev_id_seq TO liauser;
GRANT ALL PRIVILEGES ON SEQUENCE membregroupecodev_id_seq TO liauser;

-- Créer des index pour améliorer les performances
CREATE INDEX IF NOT EXISTS idx_groupecodev_cycle ON groupecodev(cycle_id);
CREATE INDEX IF NOT EXISTS idx_groupecodev_groupe ON groupecodev(groupe_id);
CREATE INDEX IF NOT EXISTS idx_groupecodev_statut ON groupecodev(statut);
CREATE INDEX IF NOT EXISTS idx_membregroupecodev_groupe ON membregroupecodev(groupe_codev_id);
CREATE INDEX IF NOT EXISTS idx_membregroupecodev_candidat ON membregroupecodev(candidat_id);
CREATE INDEX IF NOT EXISTS idx_membregroupecodev_statut ON membregroupecodev(statut);

-- Vérification que toutes les tables existent maintenant
SELECT 
    table_name,
    CASE 
        WHEN table_name IN ('cyclecodev', 'groupecodev', 'membregroupecodev', 'seancecodev', 'presentationcodev', 'contributioncodev', 'participationseance') 
        THEN '✅ Table créée'
        ELSE '❌ Table manquante'
    END as statut
FROM information_schema.tables 
WHERE table_schema = 'public' 
AND (table_name LIKE '%codev%' OR table_name = 'participationseance')
ORDER BY table_name;

-- Vérifier les permissions pour l'utilisateur liauser sur les nouvelles tables
SELECT 
    table_name,
    privilege_type
FROM information_schema.table_privileges 
WHERE grantee = 'liauser' 
AND table_name IN ('groupecodev', 'membregroupecodev')
ORDER BY table_name, privilege_type;

-- Message de confirmation
SELECT 'Tables groupecodev et membregroupecodev créées avec succès !' as message;
