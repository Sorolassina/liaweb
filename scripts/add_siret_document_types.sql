-- Script pour ajouter les nouveaux types de documents SIRET à l'enum PostgreSQL
-- À exécuter dans la base de données PostgreSQL

-- Ajouter les nouveaux types de documents SIRET
ALTER TYPE typedocument ADD VALUE IF NOT EXISTS 'COMPTE_ANNUEL';
ALTER TYPE typedocument ADD VALUE IF NOT EXISTS 'STATUTS';
ALTER TYPE typedocument ADD VALUE IF NOT EXISTS 'EXTRACT_KBIS';
ALTER TYPE typedocument ADD VALUE IF NOT EXISTS 'PUBLICATION_BODACC';

-- Vérifier que tous les types ont été ajoutés
SELECT unnest(enum_range(NULL::typedocument)) as type_document_values;
