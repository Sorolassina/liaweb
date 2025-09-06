-- Script SQL pour corriger l'enum TypeDocument dans PostgreSQL
-- À exécuter dans PostgreSQL

-- Vérifier les valeurs actuelles de l'enum
SELECT enumlabel FROM pg_enum WHERE enumtypid = (
    SELECT oid FROM pg_type WHERE typname = 'typedocument'
);

-- Ajouter la valeur manquante si elle n'existe pas
DO $$ 
BEGIN
    -- Vérifier si la valeur existe déjà
    IF NOT EXISTS (
        SELECT 1 FROM pg_enum 
        WHERE enumtypid = (SELECT oid FROM pg_type WHERE typname = 'typedocument')
        AND enumlabel = 'JUSTIFICATIF_DOMICILE'
    ) THEN
        -- Ajouter la valeur
        ALTER TYPE typedocument ADD VALUE 'JUSTIFICATIF_DOMICILE';
        RAISE NOTICE 'Valeur JUSTIFICATIF_DOMICILE ajoutée à l''enum typedocument';
    ELSE
        RAISE NOTICE 'Valeur JUSTIFICATIF_DOMICILE existe déjà dans l''enum typedocument';
    END IF;
END $$;

-- Vérifier les valeurs finales
SELECT enumlabel FROM pg_enum WHERE enumtypid = (
    SELECT oid FROM pg_type WHERE typname = 'typedocument'
) ORDER BY enumlabel;
