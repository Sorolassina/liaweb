-- Script SQL complet pour synchroniser l'enum TypeDocument avec le code Python
-- À exécuter dans PostgreSQL

-- Vérifier les valeurs actuelles de l'enum
SELECT 'Valeurs actuelles:' as info;
SELECT enumlabel FROM pg_enum WHERE enumtypid = (
    SELECT oid FROM pg_type WHERE typname = 'typedocument'
) ORDER BY enumlabel;

-- Valeurs attendues selon le code Python
-- CNI, KBIS, JUSTIFICATIF_DOMICILE, RIB, CV, DIPLOME, ATTESTATION, AUTRE

-- Ajouter toutes les valeurs manquantes
DO $$ 
DECLARE
    enum_type_oid oid;
    missing_values text[] := ARRAY['CNI', 'KBIS', 'JUSTIFICATIF_DOMICILE', 'RIB', 'CV', 'DIPLOME', 'ATTESTATION', 'AUTRE'];
    value text;
BEGIN
    -- Récupérer l'OID du type enum
    SELECT oid INTO enum_type_oid FROM pg_type WHERE typname = 'typedocument';
    
    -- Parcourir toutes les valeurs attendues
    FOREACH value IN ARRAY missing_values
    LOOP
        -- Vérifier si la valeur existe déjà
        IF NOT EXISTS (
            SELECT 1 FROM pg_enum 
            WHERE enumtypid = enum_type_oid
            AND enumlabel = value
        ) THEN
            -- Ajouter la valeur
            ALTER TYPE typedocument ADD VALUE value;
            RAISE NOTICE 'Valeur % ajoutée à l''enum typedocument', value;
        ELSE
            RAISE NOTICE 'Valeur % existe déjà dans l''enum typedocument', value;
        END IF;
    END LOOP;
END $$;

-- Vérifier les valeurs finales
SELECT 'Valeurs finales:' as info;
SELECT enumlabel FROM pg_enum WHERE enumtypid = (
    SELECT oid FROM pg_type WHERE typname = 'typedocument'
) ORDER BY enumlabel;

-- Compter le nombre de valeurs
SELECT 'Nombre total de valeurs:' as info, COUNT(*) as count FROM pg_enum WHERE enumtypid = (
    SELECT oid FROM pg_type WHERE typname = 'typedocument'
);
