-- Script SQL pour créer les tables de permissions et d'archivage
-- À exécuter dans PostgreSQL

-- 1. Créer les tables de permissions
CREATE TABLE IF NOT EXISTS permissionrole (
    id SERIAL PRIMARY KEY,
    role VARCHAR(50) NOT NULL,
    ressource VARCHAR(50) NOT NULL,
    niveau_permission VARCHAR(20) NOT NULL,
    cree_le TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    modifie_le TIMESTAMP WITH TIME ZONE,
    UNIQUE(role, ressource)
);

CREATE INDEX IF NOT EXISTS idx_permissionrole_role ON permissionrole(role);
CREATE INDEX IF NOT EXISTS idx_permissionrole_ressource ON permissionrole(ressource);

CREATE TABLE IF NOT EXISTS permissionutilisateur (
    id SERIAL PRIMARY KEY,
    utilisateur_id INTEGER NOT NULL REFERENCES "user"(id) ON DELETE CASCADE,
    ressource VARCHAR(50) NOT NULL,
    niveau_permission VARCHAR(20) NOT NULL,
    accordee_par INTEGER NOT NULL REFERENCES "user"(id),
    cree_le TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    expire_le TIMESTAMP WITH TIME ZONE,
    UNIQUE(utilisateur_id, ressource)
);

CREATE INDEX IF NOT EXISTS idx_permissionutilisateur_utilisateur_id ON permissionutilisateur(utilisateur_id);
CREATE INDEX IF NOT EXISTS idx_permissionutilisateur_ressource ON permissionutilisateur(ressource);

CREATE TABLE IF NOT EXISTS logpermission (
    id SERIAL PRIMARY KEY,
    utilisateur_id INTEGER NOT NULL REFERENCES "user"(id),
    utilisateur_cible_id INTEGER REFERENCES "user"(id),
    action VARCHAR(20) NOT NULL,
    ressource VARCHAR(50) NOT NULL,
    ancienne_permission VARCHAR(20),
    nouvelle_permission VARCHAR(20),
    raison TEXT,
    cree_le TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_logpermission_utilisateur_id ON logpermission(utilisateur_id);
CREATE INDEX IF NOT EXISTS idx_logpermission_utilisateur_cible_id ON logpermission(utilisateur_cible_id);
CREATE INDEX IF NOT EXISTS idx_logpermission_cree_le ON logpermission(cree_le);

-- 2. Créer les tables d'archivage
CREATE TABLE IF NOT EXISTS archive (
    id SERIAL PRIMARY KEY,
    nom VARCHAR(255) NOT NULL,
    type_archive VARCHAR(20) NOT NULL,
    statut VARCHAR(20) NOT NULL DEFAULT 'en_attente',
    chemin_fichier TEXT,
    taille_fichier BIGINT,
    description TEXT,
    cree_par INTEGER NOT NULL REFERENCES "user"(id),
    cree_le TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    termine_le TIMESTAMP WITH TIME ZONE,
    expire_le TIMESTAMP WITH TIME ZONE,
    metadonnees JSONB,
    message_erreur TEXT
);

CREATE INDEX IF NOT EXISTS idx_archive_cree_par ON archive(cree_par);
CREATE INDEX IF NOT EXISTS idx_archive_statut ON archive(statut);
CREATE INDEX IF NOT EXISTS idx_archive_cree_le ON archive(cree_le);

CREATE TABLE IF NOT EXISTS reglenettoyage (
    id SERIAL PRIMARY KEY,
    nom VARCHAR(255) NOT NULL,
    nom_table VARCHAR(100) NOT NULL,
    condition TEXT NOT NULL,
    jours_retention INTEGER NOT NULL,
    active BOOLEAN DEFAULT TRUE,
    derniere_execution TIMESTAMP WITH TIME ZONE,
    cree_par INTEGER NOT NULL REFERENCES "user"(id),
    cree_le TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_reglenettoyage_active ON reglenettoyage(active);
CREATE INDEX IF NOT EXISTS idx_reglenettoyage_nom_table ON reglenettoyage(nom_table);

CREATE TABLE IF NOT EXISTS lognettoyage (
    id SERIAL PRIMARY KEY,
    regle_id INTEGER NOT NULL REFERENCES reglenettoyage(id) ON DELETE CASCADE,
    enregistrements_supprimes INTEGER DEFAULT 0,
    temps_execution FLOAT NOT NULL,
    statut VARCHAR(20) NOT NULL,
    message_erreur TEXT,
    execute_par INTEGER NOT NULL REFERENCES "user"(id),
    execute_le TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_lognettoyage_regle_id ON lognettoyage(regle_id);
CREATE INDEX IF NOT EXISTS idx_lognettoyage_execute_le ON lognettoyage(execute_le);

-- 3. Insérer les permissions par défaut
INSERT INTO permissionrole (role, ressource, niveau_permission) VALUES
-- Administrateur (tous les droits)
('administrateur', 'utilisateurs', 'admin'),
('administrateur', 'programmes', 'admin'),
('administrateur', 'candidats', 'admin'),
('administrateur', 'inscriptions', 'admin'),
('administrateur', 'jurys', 'admin'),
('administrateur', 'documents', 'admin'),
('administrateur', 'logs', 'admin'),
('administrateur', 'parametres', 'admin'),
('administrateur', 'sauvegarde', 'admin'),
('administrateur', 'archive', 'admin'),

-- Directeur général
('directeur_general', 'utilisateurs', 'ecriture'),
('directeur_general', 'programmes', 'admin'),
('directeur_general', 'candidats', 'ecriture'),
('directeur_general', 'inscriptions', 'ecriture'),
('directeur_general', 'jurys', 'ecriture'),
('directeur_general', 'documents', 'ecriture'),
('directeur_general', 'logs', 'lecture'),
('directeur_general', 'parametres', 'ecriture'),
('directeur_general', 'sauvegarde', 'ecriture'),
('directeur_general', 'archive', 'ecriture'),

-- Responsable programme
('responsable_programme', 'utilisateurs', 'lecture'),
('responsable_programme', 'programmes', 'ecriture'),
('responsable_programme', 'candidats', 'ecriture'),
('responsable_programme', 'inscriptions', 'ecriture'),
('responsable_programme', 'jurys', 'ecriture'),
('responsable_programme', 'documents', 'ecriture'),
('responsable_programme', 'logs', 'lecture'),
('responsable_programme', 'parametres', 'lecture'),
('responsable_programme', 'sauvegarde', 'lecture'),
('responsable_programme', 'archive', 'lecture'),

-- Conseiller
('conseiller', 'utilisateurs', 'lecture'),
('conseiller', 'programmes', 'lecture'),
('conseiller', 'candidats', 'ecriture'),
('conseiller', 'inscriptions', 'ecriture'),
('conseiller', 'jurys', 'lecture'),
('conseiller', 'documents', 'ecriture'),
('conseiller', 'logs', 'lecture'),
('conseiller', 'parametres', 'lecture'),
('conseiller', 'sauvegarde', 'lecture'),
('conseiller', 'archive', 'lecture')

ON CONFLICT (role, ressource) DO NOTHING;

-- 4. Insérer des règles de nettoyage par défaut
INSERT INTO reglenettoyage (nom, nom_table, condition, jours_retention, cree_par) VALUES
('Logs anciens', 'activitylog', 'created_at < NOW() - INTERVAL ''90 days''', 90, 1),
('Sessions expirées', 'session', 'expires_at < NOW()', 7, 1),
('Documents temporaires', 'document', 'created_at < NOW() - INTERVAL ''365 days'' AND status = ''temporary''', 365, 1)

ON CONFLICT DO NOTHING;

-- 5. Afficher les statistiques
SELECT 
    'Tables créées' as operation,
    COUNT(*) as count
FROM information_schema.tables 
WHERE table_name IN ('permissionrole', 'permissionutilisateur', 'logpermission', 'archive', 'reglenettoyage', 'lognettoyage')

UNION ALL

SELECT 
    'Permissions par défaut' as operation,
    COUNT(*) as count
FROM permissionrole

UNION ALL

SELECT 
    'Règles de nettoyage' as operation,
    COUNT(*) as count
FROM reglenettoyage;
