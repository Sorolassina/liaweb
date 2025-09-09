-- Script d'initialisation de la table des rendez-vous
-- Ce script vérifie si la table existe et la crée si nécessaire

-- Vérifier si la table existe déjà
DO $$
BEGIN
    -- Créer la table si elle n'existe pas
    IF NOT EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'rendezvous') THEN
        CREATE TABLE rendezvous (
            id SERIAL PRIMARY KEY,
            inscription_id INTEGER NOT NULL REFERENCES inscription(id) ON DELETE CASCADE,
            conseiller_id INTEGER REFERENCES "user"(id) ON DELETE SET NULL,
            type_rdv VARCHAR(20) NOT NULL DEFAULT 'entretien',
            statut VARCHAR(20) NOT NULL DEFAULT 'planifie',
            debut TIMESTAMP WITH TIME ZONE NOT NULL,
            fin TIMESTAMP WITH TIME ZONE,
            lieu VARCHAR(255),
            notes TEXT,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
            updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
        );

        -- Créer les index pour améliorer les performances
        CREATE INDEX idx_rendezvous_inscription_id ON rendezvous(inscription_id);
        CREATE INDEX idx_rendezvous_conseiller_id ON rendezvous(conseiller_id);
        CREATE INDEX idx_rendezvous_debut ON rendezvous(debut);
        CREATE INDEX idx_rendezvous_statut ON rendezvous(statut);
        CREATE INDEX idx_rendezvous_type ON rendezvous(type_rdv);

        -- Ajouter des contraintes de validation
        ALTER TABLE rendezvous ADD CONSTRAINT chk_type_rdv 
            CHECK (type_rdv IN ('entretien', 'suivi', 'coaching', 'autre'));
        
        ALTER TABLE rendezvous ADD CONSTRAINT chk_statut_rdv 
            CHECK (statut IN ('planifie', 'termine', 'annule'));
        
        ALTER TABLE rendezvous ADD CONSTRAINT chk_date_fin 
            CHECK (fin IS NULL OR fin > debut);

        -- Créer un trigger pour mettre à jour updated_at
        CREATE OR REPLACE FUNCTION update_updated_at_column()
        RETURNS TRIGGER AS $$
        BEGIN
            NEW.updated_at = NOW();
            RETURN NEW;
        END;
        $$ language 'plpgsql';

        CREATE TRIGGER update_rendezvous_updated_at 
            BEFORE UPDATE ON rendezvous 
            FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

        RAISE NOTICE 'Table rendezvous créée avec succès';
    ELSE
        RAISE NOTICE 'Table rendezvous existe déjà';
    END IF;
END $$;

-- Insérer quelques données de test (optionnel)
-- Décommentez les lignes suivantes si vous voulez des données de test
/*
INSERT INTO rendezvous (inscription_id, conseiller_id, type_rdv, statut, debut, fin, lieu, notes)
SELECT 
    i.id,
    u.id,
    'entretien',
    'planifie',
    NOW() + INTERVAL '1 day',
    NOW() + INTERVAL '1 day 1 hour',
    'Bureau 101',
    'Premier entretien de suivi'
FROM inscription i
JOIN "user" u ON u.role IN ('conseiller', 'coordinateur')
WHERE i.statut = 'valide'
LIMIT 5
ON CONFLICT DO NOTHING;
*/
