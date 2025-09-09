-- Script pour créer la table d'émargement des RDV
-- Date: 2025-01-09

-- Créer la table emargementrdv
CREATE TABLE IF NOT EXISTS emargementrdv (
    id SERIAL PRIMARY KEY,
    rdv_id INTEGER NOT NULL REFERENCES rendezvous(id) ON DELETE CASCADE,
    type_signataire VARCHAR(20) NOT NULL CHECK (type_signataire IN ('conseiller', 'candidat')),
    signataire_id INTEGER REFERENCES "user"(id) ON DELETE CASCADE,
    candidat_id INTEGER REFERENCES candidat(id) ON DELETE CASCADE,
    signature_conseiller TEXT,
    signature_candidat TEXT,
    date_signature_conseiller TIMESTAMP WITH TIME ZONE,
    date_signature_candidat TIMESTAMP WITH TIME ZONE,
    ip_address VARCHAR(45),
    user_agent TEXT,
    cree_le TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Créer les index pour optimiser les requêtes
CREATE INDEX IF NOT EXISTS idx_emargementrdv_rdv_id ON emargementrdv(rdv_id);
CREATE INDEX IF NOT EXISTS idx_emargementrdv_type_signataire ON emargementrdv(type_signataire);
CREATE INDEX IF NOT EXISTS idx_emargementrdv_signataire_id ON emargementrdv(signataire_id);
CREATE INDEX IF NOT EXISTS idx_emargementrdv_candidat_id ON emargementrdv(candidat_id);
CREATE INDEX IF NOT EXISTS idx_emargementrdv_cree_le ON emargementrdv(cree_le);

-- Contrainte pour s'assurer qu'il n'y a qu'un seul émargement par RDV
CREATE UNIQUE INDEX IF NOT EXISTS idx_emargementrdv_unique_rdv ON emargementrdv(rdv_id);

-- Commentaires sur la table
COMMENT ON TABLE emargementrdv IS 'Table pour gérer les émargements des rendez-vous (signatures conseiller et candidat)';
COMMENT ON COLUMN emargementrdv.type_signataire IS 'Type de signataire: conseiller ou candidat';
COMMENT ON COLUMN emargementrdv.signature_conseiller IS 'Signature du conseiller (base64 ou hash)';
COMMENT ON COLUMN emargementrdv.signature_candidat IS 'Signature du candidat (base64 ou hash)';
COMMENT ON COLUMN emargementrdv.ip_address IS 'Adresse IP pour traçabilité';
COMMENT ON COLUMN emargementrdv.user_agent IS 'User agent pour traçabilité';
