-- Migration simplifiée pour le système de Codéveloppement
-- À exécuter dans PostgreSQL après avoir vérifié que les modèles s'importent correctement

-- Vérifier que les tables n'existent pas déjà
DO $$
BEGIN
    -- Créer les tables seulement si elles n'existent pas
    IF NOT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'cyclecodev') THEN
        CREATE TABLE cyclecodev (
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
        RAISE NOTICE 'Table cyclecodev créée';
    ELSE
        RAISE NOTICE 'Table cyclecodev existe déjà';
    END IF;

    IF NOT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'groupecodev') THEN
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
        RAISE NOTICE 'Table groupecodev créée';
    ELSE
        RAISE NOTICE 'Table groupecodev existe déjà';
    END IF;

    IF NOT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'membregroupecodev') THEN
        CREATE TABLE membregroupecodev (
            id SERIAL PRIMARY KEY,
            groupe_codev_id INTEGER NOT NULL REFERENCES groupecodev(id) ON DELETE CASCADE,
            candidat_id INTEGER NOT NULL REFERENCES inscription(id),
            date_integration TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
            statut VARCHAR(20) DEFAULT 'actif',
            role_special VARCHAR(50),
            notes_integration TEXT
        );
        RAISE NOTICE 'Table membregroupecodev créée';
    ELSE
        RAISE NOTICE 'Table membregroupecodev existe déjà';
    END IF;

    IF NOT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'seancecodev') THEN
        CREATE TABLE seancecodev (
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
        RAISE NOTICE 'Table seancecodev créée';
    ELSE
        RAISE NOTICE 'Table seancecodev existe déjà';
    END IF;

    IF NOT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'presentationcodev') THEN
        CREATE TABLE presentationcodev (
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
        RAISE NOTICE 'Table presentationcodev créée';
    ELSE
        RAISE NOTICE 'Table presentationcodev existe déjà';
    END IF;

    IF NOT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'contributioncodev') THEN
        CREATE TABLE contributioncodev (
            id SERIAL PRIMARY KEY,
            presentation_id INTEGER NOT NULL REFERENCES presentationcodev(id) ON DELETE CASCADE,
            contributeur_id INTEGER NOT NULL REFERENCES inscription(id),
            type_contribution VARCHAR(20) NOT NULL,
            contenu TEXT NOT NULL,
            ordre_contribution INTEGER,
            cree_le TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
        );
        RAISE NOTICE 'Table contributioncodev créée';
    ELSE
        RAISE NOTICE 'Table contributioncodev existe déjà';
    END IF;

    IF NOT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'participationseance') THEN
        CREATE TABLE participationseance (
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
        RAISE NOTICE 'Table participationseance créée';
    ELSE
        RAISE NOTICE 'Table participationseance existe déjà';
    END IF;
END $$;

-- Créer les index pour les performances
CREATE INDEX IF NOT EXISTS idx_cyclecodev_programme ON cyclecodev(programme_id);
CREATE INDEX IF NOT EXISTS idx_cyclecodev_statut ON cyclecodev(statut);
CREATE INDEX IF NOT EXISTS idx_groupecodev_cycle ON groupecodev(cycle_id);
CREATE INDEX IF NOT EXISTS idx_seancecodev_groupe ON seancecodev(groupe_id);
CREATE INDEX IF NOT EXISTS idx_seancecodev_date ON seancecodev(date_seance);
CREATE INDEX IF NOT EXISTS idx_presentationcodev_seance ON presentationcodev(seance_id);

-- Ajouter des contraintes d'unicité
DO $$
BEGIN
    -- Contraintes d'unicité seulement si elles n'existent pas
    IF NOT EXISTS (SELECT 1 FROM information_schema.table_constraints WHERE constraint_name = 'uk_cyclecodev_nom_programme') THEN
        ALTER TABLE cyclecodev ADD CONSTRAINT uk_cyclecodev_nom_programme UNIQUE (nom, programme_id);
    END IF;
    
    IF NOT EXISTS (SELECT 1 FROM information_schema.table_constraints WHERE constraint_name = 'uk_groupecodev_nom_cycle') THEN
        ALTER TABLE groupecodev ADD CONSTRAINT uk_groupecodev_nom_cycle UNIQUE (nom_groupe, cycle_id);
    END IF;
    
    IF NOT EXISTS (SELECT 1 FROM information_schema.table_constraints WHERE constraint_name = 'uk_seancecodev_numero_groupe') THEN
        ALTER TABLE seancecodev ADD CONSTRAINT uk_seancecodev_numero_groupe UNIQUE (numero_seance, groupe_id);
    END IF;
END $$;

-- Vérification finale
SELECT 'Migration du système de codéveloppement terminée avec succès' as status;

-- Afficher les tables créées
SELECT 
    tablename,
    'Créée' as status
FROM pg_tables 
WHERE tablename IN (
    'cyclecodev', 'groupecodev', 'membregroupecodev', 
    'seancecodev', 'presentationcodev', 'contributioncodev', 'participationseance'
)
ORDER BY tablename;
