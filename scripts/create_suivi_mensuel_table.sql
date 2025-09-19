-- Création complète de la table suivi_mensuel avec métriques business
-- Script: create_suivi_mensuel_table.sql

-- Supprimer la table si elle existe (ATTENTION: cela supprimera toutes les données)
-- DROP TABLE IF EXISTS suivi_mensuel CASCADE;

-- Créer la table suivi_mensuel complète
CREATE TABLE IF NOT EXISTS suivi_mensuel (
    id SERIAL PRIMARY KEY,
    inscription_id INTEGER NOT NULL,
    mois DATE NOT NULL,
    
    -- Métriques business principales
    chiffre_affaires_actuel DECIMAL(15,2),
    
    -- Évolution des employés
    nb_stagiaires INTEGER DEFAULT 0,
    nb_alternants INTEGER DEFAULT 0,
    nb_cdd INTEGER DEFAULT 0,
    nb_cdi INTEGER DEFAULT 0,
    
    -- Subventions et financements
    montant_subventions_obtenues DECIMAL(15,2),
    organismes_financeurs TEXT,
    
    -- Dettes
    montant_dettes_effectuees DECIMAL(15,2),
    montant_dettes_encours DECIMAL(15,2),
    montant_dettes_envisagees DECIMAL(15,2),
    
    -- Levée de fonds equity
    montant_equity_effectue DECIMAL(15,2),
    montant_equity_encours DECIMAL(15,2),
    
    -- Informations entreprise
    statut_juridique VARCHAR(100),
    adresse_entreprise TEXT,
    
    -- Situation socioprofessionnelle
    situation_socioprofessionnelle VARCHAR(200),
    
    -- Métriques générales (conservées pour compatibilité)
    score_objectifs DECIMAL(5,2) CHECK (score_objectifs >= 0 AND score_objectifs <= 100),
    commentaire TEXT,
    
    -- Métadonnées
    cree_le TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    modifie_le TIMESTAMP WITH TIME ZONE,
    
    -- Contraintes
    CONSTRAINT fk_suivi_mensuel_inscription FOREIGN KEY (inscription_id) REFERENCES inscription(id) ON DELETE CASCADE,
    CONSTRAINT unique_suivi_inscription_mois UNIQUE (inscription_id, mois)
);

-- Ajouter des contraintes de validation pour les montants
ALTER TABLE suivi_mensuel 
ADD CONSTRAINT check_chiffre_affaires_actuel CHECK (chiffre_affaires_actuel >= 0),
ADD CONSTRAINT check_nb_stagiaires CHECK (nb_stagiaires >= 0),
ADD CONSTRAINT check_nb_alternants CHECK (nb_alternants >= 0),
ADD CONSTRAINT check_nb_cdd CHECK (nb_cdd >= 0),
ADD CONSTRAINT check_nb_cdi CHECK (nb_cdi >= 0),
ADD CONSTRAINT check_montant_subventions CHECK (montant_subventions_obtenues >= 0),
ADD CONSTRAINT check_montant_dettes_effectuees CHECK (montant_dettes_effectuees >= 0),
ADD CONSTRAINT check_montant_dettes_encours CHECK (montant_dettes_encours >= 0),
ADD CONSTRAINT check_montant_dettes_envisagees CHECK (montant_dettes_envisagees >= 0),
ADD CONSTRAINT check_montant_equity_effectue CHECK (montant_equity_effectue >= 0),
ADD CONSTRAINT check_montant_equity_encours CHECK (montant_equity_encours >= 0);

-- Créer des index pour améliorer les performances
CREATE INDEX IF NOT EXISTS idx_suivi_mensuel_inscription_id ON suivi_mensuel(inscription_id);
CREATE INDEX IF NOT EXISTS idx_suivi_mensuel_mois ON suivi_mensuel(mois);
CREATE INDEX IF NOT EXISTS idx_suivi_mensuel_chiffre_affaires ON suivi_mensuel(chiffre_affaires_actuel);
CREATE INDEX IF NOT EXISTS idx_suivi_mensuel_employes ON suivi_mensuel(nb_stagiaires, nb_alternants, nb_cdd, nb_cdi);
CREATE INDEX IF NOT EXISTS idx_suivi_mensuel_subventions ON suivi_mensuel(montant_subventions_obtenues);
CREATE INDEX IF NOT EXISTS idx_suivi_mensuel_statut_juridique ON suivi_mensuel(statut_juridique);
CREATE INDEX IF NOT EXISTS idx_suivi_mensuel_score ON suivi_mensuel(score_objectifs);

-- Ajouter des commentaires pour documenter les champs
COMMENT ON TABLE suivi_mensuel IS 'Suivi mensuel des candidats avec métriques business';
COMMENT ON COLUMN suivi_mensuel.id IS 'Identifiant unique du suivi';
COMMENT ON COLUMN suivi_mensuel.inscription_id IS 'Référence à l''inscription';
COMMENT ON COLUMN suivi_mensuel.mois IS 'Mois du suivi (1er du mois)';
COMMENT ON COLUMN suivi_mensuel.chiffre_affaires_actuel IS 'Chiffre d''affaires actuel en euros';
COMMENT ON COLUMN suivi_mensuel.nb_stagiaires IS 'Nombre de stagiaires employés';
COMMENT ON COLUMN suivi_mensuel.nb_alternants IS 'Nombre d''alternants employés';
COMMENT ON COLUMN suivi_mensuel.nb_cdd IS 'Nombre de CDD employés';
COMMENT ON COLUMN suivi_mensuel.nb_cdi IS 'Nombre de CDI employés';
COMMENT ON COLUMN suivi_mensuel.montant_subventions_obtenues IS 'Montant des subventions obtenues en euros';
COMMENT ON COLUMN suivi_mensuel.organismes_financeurs IS 'Liste des organismes ayant financé';
COMMENT ON COLUMN suivi_mensuel.montant_dettes_effectuees IS 'Montant des dettes payées en euros';
COMMENT ON COLUMN suivi_mensuel.montant_dettes_encours IS 'Montant des dettes en cours en euros';
COMMENT ON COLUMN suivi_mensuel.montant_dettes_envisagees IS 'Montant des dettes prévues en euros';
COMMENT ON COLUMN suivi_mensuel.montant_equity_effectue IS 'Montant de levée de fonds equity réalisée en euros';
COMMENT ON COLUMN suivi_mensuel.montant_equity_encours IS 'Montant de levée de fonds equity en cours en euros';
COMMENT ON COLUMN suivi_mensuel.statut_juridique IS 'Statut juridique de l''entreprise (SAS, SARL, etc.)';
COMMENT ON COLUMN suivi_mensuel.adresse_entreprise IS 'Adresse de l''entreprise si changement';
COMMENT ON COLUMN suivi_mensuel.situation_socioprofessionnelle IS 'Situation socioprofessionnelle du candidat';
COMMENT ON COLUMN suivi_mensuel.score_objectifs IS 'Score global des objectifs (0-100)';
COMMENT ON COLUMN suivi_mensuel.commentaire IS 'Commentaires libres';
COMMENT ON COLUMN suivi_mensuel.cree_le IS 'Date de création';
COMMENT ON COLUMN suivi_mensuel.modifie_le IS 'Date de dernière modification';

-- Vérifier que la table inscription existe
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'inscription') THEN
        RAISE EXCEPTION 'La table inscription n''existe pas. Veuillez d''abord créer les tables de base.';
    END IF;
END $$;

-- Insérer des données de test pour vérifier le fonctionnement
-- (Seulement si des inscriptions existent)
DO $$
DECLARE
    inscription_count INTEGER;
    test_inscription_id INTEGER;
BEGIN
    -- Vérifier s'il y a des inscriptions
    SELECT COUNT(*) INTO inscription_count FROM inscription;
    
    IF inscription_count > 0 THEN
        -- Prendre la première inscription disponible
        SELECT id INTO test_inscription_id FROM inscription LIMIT 1;
        
        -- Insérer un suivi de test
        INSERT INTO suivi_mensuel (
            inscription_id, 
            mois, 
            chiffre_affaires_actuel,
            nb_stagiaires,
            nb_alternants,
            nb_cdd,
            nb_cdi,
            montant_subventions_obtenues,
            organismes_financeurs,
            montant_dettes_effectuees,
            montant_dettes_encours,
            montant_dettes_envisagees,
            montant_equity_effectue,
            montant_equity_encours,
            statut_juridique,
            adresse_entreprise,
            situation_socioprofessionnelle,
            score_objectifs,
            commentaire
        ) VALUES (
            test_inscription_id,
            '2024-01-01',
            50000.00,
            2,
            1,
            3,
            5,
            10000.00,
            'Bpifrance, Région Île-de-France',
            5000.00,
            15000.00,
            8000.00,
            200000.00,
            0.00,
            'SAS',
            '123 Rue de la Tech, 75001 Paris',
            'Dirigeant d''entreprise',
            85.0,
            'Très bonne évolution du chiffre d''affaires et de l''équipe'
        ) ON CONFLICT (inscription_id, mois) DO NOTHING;
        
        RAISE NOTICE 'Données de test insérées avec succès pour l''inscription ID: %', test_inscription_id;
    ELSE
        RAISE NOTICE 'Aucune inscription trouvée. Veuillez d''abord créer des inscriptions.';
    END IF;
END $$;

-- Vérifier la structure de la table créée
\d suivi_mensuel;

-- Afficher les données de test si elles existent
SELECT 
    sm.id,
    sm.mois,
    sm.chiffre_affaires_actuel,
    sm.nb_stagiaires + sm.nb_alternants + sm.nb_cdd + sm.nb_cdi as total_employes,
    sm.montant_subventions_obtenues,
    sm.statut_juridique,
    sm.score_objectifs,
    sm.commentaire
FROM suivi_mensuel sm
WHERE sm.chiffre_affaires_actuel IS NOT NULL
ORDER BY sm.mois DESC;
