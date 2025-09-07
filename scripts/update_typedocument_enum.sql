-- Script pour mettre à jour l'enum TypeDocument dans PostgreSQL
-- Exécuter ce script dans psql ou pgAdmin

-- 1. D'abord, vérifier les valeurs actuelles de l'enum
SELECT unnest(enum_range(NULL::typedocument)) as valeurs_actuelles;

-- 2. Ajouter les nouvelles valeurs à l'enum (si elles n'existent pas déjà)
-- Note: ALTER TYPE ne permet pas de supprimer des valeurs, seulement d'en ajouter

-- Ajouter CNI si elle n'existe pas
DO $$ 
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_enum WHERE enumlabel = 'CNI' AND enumtypid = (SELECT oid FROM pg_type WHERE typname = 'typedocument')) THEN
        ALTER TYPE typedocument ADD VALUE 'CNI';
    END IF;
END $$;

-- Ajouter KBIS si elle n'existe pas
DO $$ 
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_enum WHERE enumlabel = 'KBIS' AND enumtypid = (SELECT oid FROM pg_type WHERE typname = 'typedocument')) THEN
        ALTER TYPE typedocument ADD VALUE 'KBIS';
    END IF;
END $$;

-- Ajouter JUSTIFICATIF_DOMICILE si elle n'existe pas
DO $$ 
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_enum WHERE enumlabel = 'JUSTIFICATIF_DOMICILE' AND enumtypid = (SELECT oid FROM pg_type WHERE typname = 'typedocument')) THEN
        ALTER TYPE typedocument ADD VALUE 'JUSTIFICATIF_DOMICILE';
    END IF;
END $$;

-- Ajouter RIB si elle n'existe pas
DO $$ 
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_enum WHERE enumlabel = 'RIB' AND enumtypid = (SELECT oid FROM pg_type WHERE typname = 'typedocument')) THEN
        ALTER TYPE typedocument ADD VALUE 'RIB';
    END IF;
END $$;

-- Ajouter CV si elle n'existe pas
DO $$ 
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_enum WHERE enumlabel = 'CV' AND enumtypid = (SELECT oid FROM pg_type WHERE typname = 'typedocument')) THEN
        ALTER TYPE typedocument ADD VALUE 'CV';
    END IF;
END $$;

-- Ajouter DIPLOME si elle n'existe pas
DO $$ 
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_enum WHERE enumlabel = 'DIPLOME' AND enumtypid = (SELECT oid FROM pg_type WHERE typname = 'typedocument')) THEN
        ALTER TYPE typedocument ADD VALUE 'DIPLOME';
    END IF;
END $$;

-- Ajouter ATTESTATION si elle n'existe pas
DO $$ 
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_enum WHERE enumlabel = 'ATTESTATION' AND enumtypid = (SELECT oid FROM pg_type WHERE typname = 'typedocument')) THEN
        ALTER TYPE typedocument ADD VALUE 'ATTESTATION';
    END IF;
END $$;

-- Ajouter AUTRE si elle n'existe pas
DO $$ 
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_enum WHERE enumlabel = 'AUTRE' AND enumtypid = (SELECT oid FROM pg_type WHERE typname = 'typedocument')) THEN
        ALTER TYPE typedocument ADD VALUE 'AUTRE';
    END IF;
END $$;

-- 3. Vérifier les valeurs finales de l'enum
SELECT unnest(enum_range(NULL::typedocument)) as valeurs_finales ORDER BY valeurs_finales;

-- 4. Optionnel: Si vous voulez voir toutes les valeurs avec leur ordre
SELECT 
    enumlabel as valeur,
    enumsortorder as ordre
FROM pg_enum 
WHERE enumtypid = (SELECT oid FROM pg_type WHERE typname = 'typedocument')
ORDER BY enumsortorder;
