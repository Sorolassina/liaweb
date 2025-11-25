-- Migration pour ajouter les champs de statut dans le programme
-- Script: add_statut_programme_fields.sql
-- 
-- Ce script ajoute :
-- 1. La colonne situation_entree à la table candidat (situation à la rentrée)
-- 2. Les colonnes statut_programme et raison_abandon à la table suivi_mensuel

-- Ajouter la colonne situation_entree à candidat
ALTER TABLE candidat 
ADD COLUMN IF NOT EXISTS situation_entree VARCHAR(200);

-- Ajouter les colonnes statut_programme et raison_abandon à suivi_mensuel
ALTER TABLE suivi_mensuel 
ADD COLUMN IF NOT EXISTS statut_programme VARCHAR(50),  -- "dans_programme", "abandonne", "termine"
ADD COLUMN IF NOT EXISTS raison_abandon TEXT;

-- Créer un index sur statut_programme pour améliorer les performances des requêtes
CREATE INDEX IF NOT EXISTS idx_suivi_mensuel_statut_programme ON suivi_mensuel(statut_programme);

-- Commentaire sur les colonnes
COMMENT ON COLUMN candidat.situation_entree IS 'Situation socioprofessionnelle du candidat à l''entrée du programme';
COMMENT ON COLUMN suivi_mensuel.statut_programme IS 'Statut du candidat dans le programme: dans_programme, abandonne, termine';
COMMENT ON COLUMN suivi_mensuel.raison_abandon IS 'Raison de l''abandon si statut_programme = abandonne';

