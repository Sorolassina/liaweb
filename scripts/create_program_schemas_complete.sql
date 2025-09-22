-- Script pour créer des schémas par programme avec toutes les tables existantes
-- Garde uniquement user, programme, partenaire, groupe, password_recovery_code dans public
-- Déplace toutes les autres tables vers les schémas par programme

-- Fonction pour créer un schéma complet pour un programme
CREATE OR REPLACE FUNCTION create_program_schema(program_code TEXT)
RETURNS VOID AS $$
DECLARE
    schema_name TEXT;
BEGIN
    schema_name := LOWER(program_code);
    
    -- Créer le schéma s'il n'existe pas
    EXECUTE format('CREATE SCHEMA IF NOT EXISTS %I', schema_name);
    
    -- Créer les tables dans le schéma (toutes sauf user, programme, partenaire, groupe, password_recovery_code)
    
    -- Tables de base.py
    EXECUTE format('
        CREATE TABLE IF NOT EXISTS %I.programme_utilisateur (
            id SERIAL PRIMARY KEY,
            programme_id INTEGER REFERENCES public.programme(id),
            utilisateur_id INTEGER REFERENCES public.user(id),
            role_programme VARCHAR(50),
            actif BOOLEAN DEFAULT TRUE,
            date_debut DATE,
            date_fin DATE,
            cree_le TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
        )', schema_name);

    EXECUTE format('
        CREATE TABLE IF NOT EXISTS %I.promotion (
            id SERIAL PRIMARY KEY,
            programme_id INTEGER REFERENCES public.programme(id),
            libelle VARCHAR(255) NOT NULL,
            capacite INTEGER,
            date_debut DATE,
            date_fin DATE,
            actif BOOLEAN DEFAULT TRUE
        )', schema_name);

    EXECUTE format('
        CREATE TABLE IF NOT EXISTS %I.candidat (
            id SERIAL PRIMARY KEY,
            civilite VARCHAR(10),
            nom VARCHAR(100) NOT NULL,
            prenom VARCHAR(100) NOT NULL,
            date_naissance DATE,
            email VARCHAR(255) UNIQUE NOT NULL,
            telephone VARCHAR(20),
            adresse_personnelle TEXT,
            niveau_etudes VARCHAR(100),
            secteur_activite VARCHAR(100),
            photo_profil VARCHAR(255),
            statut VARCHAR(20) DEFAULT ''EN_ATTENTE'',
            lat DECIMAL(10,8),
            lng DECIMAL(11,8),
            handicap BOOLEAN DEFAULT FALSE,
            type_handicap VARCHAR(50),
            besoins_accommodation TEXT,
            cree_le TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
            modifie_le TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
        )', schema_name);

    EXECUTE format('
        CREATE TABLE IF NOT EXISTS %I.preinscription (
            id SERIAL PRIMARY KEY,
            programme_id INTEGER REFERENCES public.programme(id),
            candidat_id INTEGER REFERENCES %I.candidat(id),
            source VARCHAR(50),
            donnees_brutes_json TEXT,
            statut VARCHAR(20) DEFAULT ''SOUMIS'',
            cree_le TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
        )', schema_name, schema_name);

    EXECUTE format('
        CREATE TABLE IF NOT EXISTS %I.inscription (
            id SERIAL PRIMARY KEY,
            programme_id INTEGER REFERENCES public.programme(id),
            candidat_id INTEGER REFERENCES %I.candidat(id),
            promotion_id INTEGER REFERENCES public.promotion(id),
            groupe_id INTEGER REFERENCES public.groupe(id),
            conseiller_id INTEGER REFERENCES public.user(id),
            referent_id INTEGER REFERENCES public.user(id),
            statut VARCHAR(20) DEFAULT ''EN_COURS'',
            date_decision TIMESTAMP WITH TIME ZONE,
            email_confirmation_envoye BOOLEAN DEFAULT FALSE,
            cree_le TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
            modifie_le TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
        )', schema_name, schema_name);

    EXECUTE format('
        CREATE TABLE IF NOT EXISTS %I.entreprise (
            id SERIAL PRIMARY KEY,
            candidat_id INTEGER REFERENCES %I.candidat(id),
            siret VARCHAR(14),
            siren VARCHAR(9),
            raison_sociale VARCHAR(255),
            code_naf VARCHAR(10),
            date_creation DATE,
            adresse TEXT,
            qpv BOOLEAN,
            chiffre_affaires VARCHAR(100),
            nombre_points_vente INTEGER,
            specialite_culinaire VARCHAR(255),
            nom_concept VARCHAR(255),
            lien_reseaux_sociaux TEXT,
            site_internet VARCHAR(255),
            territoire VARCHAR(255),
            lat DECIMAL(10,8),
            lng DECIMAL(11,8)
        )', schema_name, schema_name);

    EXECUTE format('
        CREATE TABLE IF NOT EXISTS %I.document (
            id SERIAL PRIMARY KEY,
            candidat_id INTEGER REFERENCES %I.candidat(id),
            type_document VARCHAR(50),
            titre VARCHAR(255),
            nom_fichier VARCHAR(255) NOT NULL,
            chemin_fichier TEXT NOT NULL,
            mimetype VARCHAR(100),
            taille_octets INTEGER,
            depose_par_id INTEGER REFERENCES public.user(id),
            depose_le TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
        )', schema_name, schema_name);

    EXECUTE format('
        CREATE TABLE IF NOT EXISTS %I.eligibilite (
            id SERIAL PRIMARY KEY,
            preinscription_id INTEGER REFERENCES %I.preinscription(id),
            ca_seuil_ok BOOLEAN,
            ca_score DECIMAL(5,2),
            qpv_ok BOOLEAN,
            anciennete_ok BOOLEAN,
            anciennete_annees INTEGER,
            verdict VARCHAR(20),
            details_json TEXT,
            cree_le TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
        )', schema_name, schema_name);

    EXECUTE format('
        CREATE TABLE IF NOT EXISTS %I.jury (
            id SERIAL PRIMARY KEY,
            nom VARCHAR(255) NOT NULL,
            description TEXT,
            date_creation TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
            actif BOOLEAN DEFAULT TRUE
        )', schema_name);

    EXECUTE format('
        CREATE TABLE IF NOT EXISTS %I.membre_jury (
            id SERIAL PRIMARY KEY,
            jury_id INTEGER REFERENCES %I.jury(id),
            user_id INTEGER REFERENCES public.user(id),
            role VARCHAR(50),
            cree_le TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
        )', schema_name, schema_name);

    EXECUTE format('
        CREATE TABLE IF NOT EXISTS %I.decision_jury_table (
            id SERIAL PRIMARY KEY,
            jury_id INTEGER REFERENCES %I.jury(id),
            nom VARCHAR(255) NOT NULL,
            description TEXT,
            actif BOOLEAN DEFAULT TRUE,
            cree_le TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
        )', schema_name, schema_name);

    EXECUTE format('
        CREATE TABLE IF NOT EXISTS %I.etape_pipeline (
            id SERIAL PRIMARY KEY,
            nom VARCHAR(255) NOT NULL,
            description TEXT,
            ordre INTEGER,
            actif BOOLEAN DEFAULT TRUE,
            cree_le TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
        )', schema_name);

    EXECUTE format('
        CREATE TABLE IF NOT EXISTS %I.avancement_etape (
            id SERIAL PRIMARY KEY,
            inscription_id INTEGER REFERENCES %I.inscription(id),
            etape_id INTEGER REFERENCES %I.etape_pipeline(id),
            statut VARCHAR(50),
            date_debut TIMESTAMP WITH TIME ZONE,
            date_fin TIMESTAMP WITH TIME ZONE,
            commentaires TEXT,
            cree_le TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
        )', schema_name, schema_name, schema_name);

    EXECUTE format('
        CREATE TABLE IF NOT EXISTS %I.action_handicap (
            id SERIAL PRIMARY KEY,
            candidat_id INTEGER REFERENCES %I.candidat(id),
            type_action VARCHAR(100),
            description TEXT,
            date_action TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
            responsable_id INTEGER REFERENCES public.user(id)
        )', schema_name, schema_name);

    EXECUTE format('
        CREATE TABLE IF NOT EXISTS %I.rendez_vous (
            id SERIAL PRIMARY KEY,
            candidat_id INTEGER REFERENCES %I.candidat(id),
            conseiller_id INTEGER REFERENCES public.user(id),
            date_rdv TIMESTAMP WITH TIME ZONE NOT NULL,
            duree_minutes INTEGER DEFAULT 60,
            type_rdv VARCHAR(50),
            statut VARCHAR(20) DEFAULT ''PLANIFIE'',
            notes TEXT,
            cree_le TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
            modifie_le TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
        )', schema_name, schema_name);

    EXECUTE format('
        CREATE TABLE IF NOT EXISTS %I.session_programme (
            id SERIAL PRIMARY KEY,
            programme_id INTEGER REFERENCES public.programme(id),
            nom VARCHAR(255) NOT NULL,
            description TEXT,
            date_debut TIMESTAMP WITH TIME ZONE,
            date_fin TIMESTAMP WITH TIME ZONE,
            lieu VARCHAR(255),
            max_participants INTEGER,
            cree_le TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
        )', schema_name);

    EXECUTE format('
        CREATE TABLE IF NOT EXISTS %I.session_participant (
            id SERIAL PRIMARY KEY,
            session_id INTEGER REFERENCES %I.session_programme(id),
            candidat_id INTEGER REFERENCES %I.candidat(id),
            statut VARCHAR(20) DEFAULT ''INSCRIT'',
            date_inscription TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
        )', schema_name, schema_name, schema_name);

    EXECUTE format('
        CREATE TABLE IF NOT EXISTS %I.suivi_mensuel (
            id SERIAL PRIMARY KEY,
            inscription_id INTEGER REFERENCES %I.inscription(id),
            mois DATE NOT NULL,
            chiffre_affaires_actuel DECIMAL(15,2),
            nb_stagiaires INTEGER DEFAULT 0,
            nb_alternants INTEGER DEFAULT 0,
            nb_cdd INTEGER DEFAULT 0,
            nb_cdi INTEGER DEFAULT 0,
            montant_subventions_obtenues DECIMAL(15,2),
            organismes_financeurs TEXT,
            montant_dettes_effectuees DECIMAL(15,2),
            montant_dettes_encours DECIMAL(15,2),
            montant_dettes_envisagees DECIMAL(15,2),
            montant_equity_effectue DECIMAL(15,2),
            montant_equity_encours DECIMAL(15,2),
            statut_juridique VARCHAR(100),
            adresse_entreprise TEXT,
            situation_socioprofessionnelle VARCHAR(100),
            cree_le TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
            modifie_le TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
        )', schema_name, schema_name);

    EXECUTE format('
        CREATE TABLE IF NOT EXISTS %I.decision_jury_candidat (
            id SERIAL PRIMARY KEY,
            candidat_id INTEGER REFERENCES %I.candidat(id),
            jury_id INTEGER REFERENCES %I.jury(id),
            decision VARCHAR(20),
            commentaires TEXT,
            date_decision TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
            cree_le TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
        )', schema_name, schema_name, schema_name);

    EXECUTE format('
        CREATE TABLE IF NOT EXISTS %I.reorientation_candidat (
            id SERIAL PRIMARY KEY,
            candidat_id INTEGER REFERENCES %I.candidat(id),
            programme_origine_id INTEGER REFERENCES public.programme(id),
            programme_destination_id INTEGER REFERENCES public.programme(id),
            raison TEXT,
            date_reorientation TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
            responsable_id INTEGER REFERENCES public.user(id),
            cree_le TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
        )', schema_name, schema_name);

    EXECUTE format('
        CREATE TABLE IF NOT EXISTS %I.emargement_rdv (
            id SERIAL PRIMARY KEY,
            rdv_id INTEGER REFERENCES %I.rendez_vous(id),
            participant_id INTEGER REFERENCES public.user(id),
            heure_arrivee TIMESTAMP WITH TIME ZONE,
            heure_depart TIMESTAMP WITH TIME ZONE,
            statut VARCHAR(20) DEFAULT ''PRESENT'',
            commentaires TEXT,
            cree_le TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
        )', schema_name, schema_name);

    -- Tables de seminaire.py
    EXECUTE format('
        CREATE TABLE IF NOT EXISTS %I.seminaire (
            id SERIAL PRIMARY KEY,
            programme_id INTEGER REFERENCES public.programme(id),
            titre VARCHAR(255) NOT NULL,
            description TEXT,
            date_debut TIMESTAMP WITH TIME ZONE,
            date_fin TIMESTAMP WITH TIME ZONE,
            lieu VARCHAR(255),
            max_participants INTEGER,
            statut VARCHAR(20) DEFAULT ''PLANIFIE'',
            cree_le TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
            modifie_le TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
        )', schema_name);

    EXECUTE format('
        CREATE TABLE IF NOT EXISTS %I.session_seminaire (
            id SERIAL PRIMARY KEY,
            seminaire_id INTEGER REFERENCES %I.seminaire(id),
            titre VARCHAR(255) NOT NULL,
            description TEXT,
            date_debut TIMESTAMP WITH TIME ZONE,
            date_fin TIMESTAMP WITH TIME ZONE,
            lieu VARCHAR(255),
            animateur_id INTEGER REFERENCES public.user(id),
            cree_le TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
        )', schema_name, schema_name);

    EXECUTE format('
        CREATE TABLE IF NOT EXISTS %I.invitation_seminaire (
            id SERIAL PRIMARY KEY,
            seminaire_id INTEGER REFERENCES %I.seminaire(id),
            candidat_id INTEGER REFERENCES %I.candidat(id),
            statut VARCHAR(20) DEFAULT ''EN_ATTENTE'',
            date_invitation TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
            date_reponse TIMESTAMP WITH TIME ZONE,
            cree_le TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
        )', schema_name, schema_name, schema_name);

    EXECUTE format('
        CREATE TABLE IF NOT EXISTS %I.presence_seminaire (
            id SERIAL PRIMARY KEY,
            session_id INTEGER REFERENCES %I.session_seminaire(id),
            candidat_id INTEGER REFERENCES %I.candidat(id),
            statut VARCHAR(20) DEFAULT ''PRESENT'',
            heure_arrivee TIMESTAMP WITH TIME ZONE,
            heure_depart TIMESTAMP WITH TIME ZONE,
            commentaires TEXT,
            cree_le TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
        )', schema_name, schema_name, schema_name);

    EXECUTE format('
        CREATE TABLE IF NOT EXISTS %I.livrable_seminaire (
            id SERIAL PRIMARY KEY,
            seminaire_id INTEGER REFERENCES %I.seminaire(id),
            titre VARCHAR(255) NOT NULL,
            description TEXT,
            type_livrable VARCHAR(50),
            date_limite TIMESTAMP WITH TIME ZONE,
            cree_le TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
        )', schema_name, schema_name);

    EXECUTE format('
        CREATE TABLE IF NOT EXISTS %I.rendu_livrable (
            id SERIAL PRIMARY KEY,
            livrable_id INTEGER REFERENCES %I.livrable_seminaire(id),
            candidat_id INTEGER REFERENCES %I.candidat(id),
            fichier_path VARCHAR(500),
            commentaires TEXT,
            date_rendu TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
            cree_le TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
        )', schema_name, schema_name, schema_name);

    -- Tables de event.py
    EXECUTE format('
        CREATE TABLE IF NOT EXISTS %I.event (
            id SERIAL PRIMARY KEY,
            programme_id INTEGER REFERENCES public.programme(id),
            titre VARCHAR(255) NOT NULL,
            description TEXT,
            date_debut TIMESTAMP WITH TIME ZONE,
            date_fin TIMESTAMP WITH TIME ZONE,
            lieu VARCHAR(255),
            type_event VARCHAR(50),
            statut VARCHAR(20) DEFAULT ''PLANIFIE'',
            cree_le TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
            modifie_le TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
        )', schema_name);

    EXECUTE format('
        CREATE TABLE IF NOT EXISTS %I.invitation_event (
            id SERIAL PRIMARY KEY,
            event_id INTEGER REFERENCES %I.event(id),
            candidat_id INTEGER REFERENCES %I.candidat(id),
            statut VARCHAR(20) DEFAULT ''EN_ATTENTE'',
            date_invitation TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
            date_reponse TIMESTAMP WITH TIME ZONE,
            cree_le TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
        )', schema_name, schema_name, schema_name);

    EXECUTE format('
        CREATE TABLE IF NOT EXISTS %I.presence_event (
            id SERIAL PRIMARY KEY,
            event_id INTEGER REFERENCES %I.event(id),
            candidat_id INTEGER REFERENCES %I.candidat(id),
            statut VARCHAR(20) DEFAULT ''PRESENT'',
            heure_arrivee TIMESTAMP WITH TIME ZONE,
            heure_depart TIMESTAMP WITH TIME ZONE,
            commentaires TEXT,
            cree_le TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
        )', schema_name, schema_name, schema_name);

    -- Tables de elearning.py (créer d'abord module_elearning, puis ressource_elearning)
    EXECUTE format('
        CREATE TABLE IF NOT EXISTS %I.module_elearning (
            id SERIAL PRIMARY KEY,
            programme_id INTEGER REFERENCES public.programme(id),
            titre VARCHAR(255) NOT NULL,
            description TEXT,
            difficulte VARCHAR(20),
            duree_estimee INTEGER,
            ordre INTEGER DEFAULT 0,
            actif BOOLEAN DEFAULT TRUE,
            cree_le TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
            modifie_le TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
        )', schema_name);

    EXECUTE format('
        CREATE TABLE IF NOT EXISTS %I.ressource_elearning (
            id SERIAL PRIMARY KEY,
            module_id INTEGER REFERENCES %I.module_elearning(id),
            titre VARCHAR(255) NOT NULL,
            description TEXT,
            type_ressource VARCHAR(50),
            url_contenu TEXT,
            fichier_path VARCHAR(500),
            nom_fichier_original VARCHAR(255),
            ordre INTEGER DEFAULT 0,
            actif BOOLEAN DEFAULT TRUE,
            cree_le TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
            modifie_le TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
        )', schema_name, schema_name);

    EXECUTE format('
        CREATE TABLE IF NOT EXISTS %I.progression_elearning (
            id SERIAL PRIMARY KEY,
            module_id INTEGER REFERENCES %I.module_elearning(id),
            candidat_id INTEGER REFERENCES %I.candidat(id),
            statut VARCHAR(20) DEFAULT ''EN_COURS'',
            pourcentage_completion INTEGER DEFAULT 0,
            date_debut TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
            date_fin TIMESTAMP WITH TIME ZONE,
            cree_le TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
        )', schema_name, schema_name, schema_name);

    EXECUTE format('
        CREATE TABLE IF NOT EXISTS %I.objectif_elearning (
            id SERIAL PRIMARY KEY,
            module_id INTEGER REFERENCES %I.module_elearning(id),
            titre VARCHAR(255) NOT NULL,
            description TEXT,
            ordre INTEGER DEFAULT 0,
            cree_le TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
        )', schema_name, schema_name);

    EXECUTE format('
        CREATE TABLE IF NOT EXISTS %I.quiz_elearning (
            id SERIAL PRIMARY KEY,
            module_id INTEGER REFERENCES %I.module_elearning(id),
            question TEXT NOT NULL,
            type_question VARCHAR(20),
            options_json TEXT,
            reponse_correcte TEXT,
            points INTEGER DEFAULT 1,
            ordre INTEGER DEFAULT 0,
            cree_le TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
        )', schema_name, schema_name);

    EXECUTE format('
        CREATE TABLE IF NOT EXISTS %I.reponse_quiz (
            id SERIAL PRIMARY KEY,
            quiz_id INTEGER REFERENCES %I.quiz_elearning(id),
            candidat_id INTEGER REFERENCES %I.candidat(id),
            reponse TEXT,
            est_correcte BOOLEAN,
            points_obtenus INTEGER DEFAULT 0,
            date_reponse TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
            cree_le TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
        )', schema_name, schema_name, schema_name);

    EXECUTE format('
        CREATE TABLE IF NOT EXISTS %I.certificat_elearning (
            id SERIAL PRIMARY KEY,
            module_id INTEGER REFERENCES %I.module_elearning(id),
            candidat_id INTEGER REFERENCES %I.candidat(id),
            score_final INTEGER,
            date_obtention TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
            fichier_certificat VARCHAR(500),
            cree_le TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
        )', schema_name, schema_name, schema_name);

    EXECUTE format('
        CREATE TABLE IF NOT EXISTS %I.module_ressource (
            id SERIAL PRIMARY KEY,
            module_id INTEGER REFERENCES %I.module_elearning(id),
            ressource_id INTEGER REFERENCES %I.ressource_elearning(id),
            ordre INTEGER DEFAULT 0,
            cree_le TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
        )', schema_name, schema_name, schema_name);

    -- Tables de codev.py (créer d'abord cycle_codev, puis groupe_codev, puis seance_codev)
    EXECUTE format('
        CREATE TABLE IF NOT EXISTS %I.cycle_codev (
            id SERIAL PRIMARY KEY,
            programme_id INTEGER REFERENCES public.programme(id),
            nom VARCHAR(255) NOT NULL,
            description TEXT,
            date_debut TIMESTAMP WITH TIME ZONE,
            date_fin TIMESTAMP WITH TIME ZONE,
            statut VARCHAR(20) DEFAULT ''ACTIF'',
            cree_le TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
            modifie_le TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
        )', schema_name);

    EXECUTE format('
        CREATE TABLE IF NOT EXISTS %I.groupe_codev (
            id SERIAL PRIMARY KEY,
            cycle_id INTEGER REFERENCES %I.cycle_codev(id),
            nom VARCHAR(255) NOT NULL,
            description TEXT,
            max_participants INTEGER DEFAULT 8,
            statut VARCHAR(20) DEFAULT ''ACTIF'',
            cree_le TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
            modifie_le TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
        )', schema_name, schema_name);

    EXECUTE format('
        CREATE TABLE IF NOT EXISTS %I.seance_codev (
            id SERIAL PRIMARY KEY,
            groupe_id INTEGER REFERENCES %I.groupe_codev(id),
            titre VARCHAR(255) NOT NULL,
            description TEXT,
            date_seance TIMESTAMP WITH TIME ZONE,
            duree_minutes INTEGER DEFAULT 120,
            lieu VARCHAR(255),
            animateur_id INTEGER REFERENCES public.user(id),
            statut VARCHAR(20) DEFAULT ''PLANIFIE'',
            cree_le TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
            modifie_le TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
        )', schema_name, schema_name);

    EXECUTE format('
        CREATE TABLE IF NOT EXISTS %I.presentation_codev (
            id SERIAL PRIMARY KEY,
            seance_id INTEGER REFERENCES %I.seance_codev(id),
            candidat_id INTEGER REFERENCES %I.candidat(id),
            sujet VARCHAR(255),
            description TEXT,
            duree_minutes INTEGER DEFAULT 10,
            ordre INTEGER DEFAULT 0,
            cree_le TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
        )', schema_name, schema_name, schema_name);

    EXECUTE format('
        CREATE TABLE IF NOT EXISTS %I.contribution_codev (
            id SERIAL PRIMARY KEY,
            presentation_id INTEGER REFERENCES %I.presentation_codev(id),
            participant_id INTEGER REFERENCES %I.candidat(id),
            type_contribution VARCHAR(50),
            contenu TEXT,
            cree_le TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
        )', schema_name, schema_name, schema_name);

    EXECUTE format('
        CREATE TABLE IF NOT EXISTS %I.participation_seance (
            id SERIAL PRIMARY KEY,
            seance_id INTEGER REFERENCES %I.seance_codev(id),
            candidat_id INTEGER REFERENCES %I.candidat(id),
            statut VARCHAR(20) DEFAULT ''PRESENT'',
            heure_arrivee TIMESTAMP WITH TIME ZONE,
            heure_depart TIMESTAMP WITH TIME ZONE,
            commentaires TEXT,
            cree_le TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
        )', schema_name, schema_name, schema_name);

    EXECUTE format('
        CREATE TABLE IF NOT EXISTS %I.membre_groupe_codev (
            id SERIAL PRIMARY KEY,
            groupe_id INTEGER REFERENCES %I.groupe_codev(id),
            candidat_id INTEGER REFERENCES %I.candidat(id),
            role VARCHAR(50),
            date_inscription TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
            statut VARCHAR(20) DEFAULT ''ACTIF'',
            cree_le TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
        )', schema_name, schema_name, schema_name);

    -- Créer les index
    EXECUTE format('CREATE INDEX IF NOT EXISTS idx_%I_candidat_email ON %I.candidat(email)', schema_name, schema_name);
    EXECUTE format('CREATE INDEX IF NOT EXISTS idx_%I_candidat_nom ON %I.candidat(nom)', schema_name, schema_name);
    EXECUTE format('CREATE INDEX IF NOT EXISTS idx_%I_preinscription_programme ON %I.preinscription(programme_id)', schema_name, schema_name);
    EXECUTE format('CREATE INDEX IF NOT EXISTS idx_%I_inscription_programme ON %I.inscription(programme_id)', schema_name, schema_name);
    EXECUTE format('CREATE INDEX IF NOT EXISTS idx_%I_entreprise_siret ON %I.entreprise(siret)', schema_name, schema_name);

    RAISE NOTICE 'Schéma % créé avec succès', schema_name;
END;
$$ LANGUAGE plpgsql;

-- Créer les schémas pour tous les programmes existants
DO $$
DECLARE
    prog RECORD;
BEGIN
    FOR prog IN SELECT code FROM public.programme WHERE actif = true LOOP
        PERFORM create_program_schema(prog.code);
    END LOOP;
END;
$$;

-- Fonction pour migrer les données existantes vers les nouveaux schémas
CREATE OR REPLACE FUNCTION migrate_existing_data_to_schemas()
RETURNS VOID AS $$
DECLARE
    prog RECORD;
    schema_name TEXT;
BEGIN
    FOR prog IN SELECT id, code FROM public.programme WHERE actif = true LOOP
        schema_name := LOWER(prog.code);
        
        -- Migrer les candidats (uniquement ceux liés à ce programme)
        EXECUTE format('
            INSERT INTO %I.candidat (
                id, civilite, nom, prenom, date_naissance, email, telephone,
                adresse_personnelle, niveau_etudes, secteur_activite, photo_profil,
                statut, lat, lng, handicap, type_handicap, besoins_accommodation
            )
            SELECT DISTINCT c.id, c.civilite, c.nom, c.prenom, c.date_naissance,
                   c.email, c.telephone, c.adresse_personnelle, c.niveau_etudes,
                   c.secteur_activite, c.photo_profil, c.statut, c.lat, c.lng,
                   c.handicap, c.type_handicap, c.besoins_accommodation
            FROM public.candidat c
            JOIN public.preinscription p ON p.candidat_id = c.id
            WHERE p.programme_id = %s
            ON CONFLICT (id) DO NOTHING
        ', schema_name, prog.id);

        -- Migrer les préinscriptions
        EXECUTE format('
            INSERT INTO %I.preinscription (
                id, programme_id, candidat_id, source, donnees_brutes_json,
                statut, cree_le
            )
            SELECT p.id, p.programme_id, p.candidat_id, p.source,
                   p.donnees_brutes_json, p.statut::text, p.cree_le
            FROM public.preinscription p
            WHERE p.programme_id = %s
            ON CONFLICT (id) DO NOTHING
        ', schema_name, prog.id);

        -- Migrer les inscriptions
        EXECUTE format('
            INSERT INTO %I.inscription (
                id, programme_id, candidat_id, promotion_id, groupe_id,
                conseiller_id, referent_id, statut, date_decision,
                email_confirmation_envoye, cree_le
            )
            SELECT i.id, i.programme_id, i.candidat_id, i.promotion_id,
                   i.groupe_id, i.conseiller_id, i.referent_id, i.statut::text,
                   i.date_decision, i.email_confirmation_envoye, i.cree_le
            FROM public.inscription i
            WHERE i.programme_id = %s
            ON CONFLICT (id) DO NOTHING
        ', schema_name, prog.id);

        -- Migrer les entreprises (tous les champs du modèle)
        EXECUTE format('
            INSERT INTO %I.entreprise (
                id, candidat_id, siret, siren, raison_sociale, code_naf,
                date_creation, adresse, qpv, chiffre_affaires, nombre_points_vente,
                specialite_culinaire, nom_concept, lien_reseaux_sociaux,
                site_internet, territoire, lat, lng
            )
            SELECT e.id, e.candidat_id, e.siret, e.siren, e.raison_sociale, e.code_naf,
                   e.date_creation, e.adresse, e.qpv, e.chiffre_affaires, e.nombre_points_vente,
                   e.specialite_culinaire, e.nom_concept, e.lien_reseaux_sociaux,
                   e.site_internet, e.territoire, e.lat, e.lng
            FROM public.entreprise e
            JOIN %I.candidat c ON c.id = e.candidat_id
            ON CONFLICT (id) DO NOTHING
        ', schema_name, schema_name);

        -- Migrer les documents (tous les champs du modèle)
        EXECUTE format('
            INSERT INTO %I.document (
                id, candidat_id, type_document, titre, nom_fichier, chemin_fichier,
                mimetype, taille_octets, depose_par_id, depose_le
            )
            SELECT d.id, d.candidat_id, d.type_document, d.titre, d.nom_fichier,
                   d.chemin_fichier, d.mimetype, d.taille_octets, d.depose_par_id, d.depose_le
            FROM public.document d
            JOIN %I.candidat c ON c.id = d.candidat_id
            ON CONFLICT (id) DO NOTHING
        ', schema_name, schema_name);

        -- Migrer les éligibilités
        EXECUTE format('
            INSERT INTO %I.eligibilite (
                id, preinscription_id, ca_seuil_ok, ca_score, qpv_ok,
                anciennete_ok, anciennete_annees, verdict, details_json,
                calcule_le
            )
            SELECT el.id, el.preinscription_id, el.ca_seuil_ok, el.ca_score,
                   el.qpv_ok, el.anciennete_ok, el.anciennete_annees,
                   el.verdict, el.details_json, el.calcule_le
            FROM public.eligibilite el
            JOIN %I.preinscription p ON p.id = el.preinscription_id
            ON CONFLICT (id) DO NOTHING
        ', schema_name, schema_name);

        RAISE NOTICE 'Données migrées pour le programme %', prog.code;
    END LOOP;
END;
$$ LANGUAGE plpgsql;

-- Fonction pour supprimer un schéma de programme
CREATE OR REPLACE FUNCTION drop_program_schema(program_code TEXT, backup_data BOOLEAN DEFAULT true)
RETURNS VOID AS $$
DECLARE
    schema_name TEXT;
    table_name TEXT;
    backup_file TEXT;
BEGIN
    schema_name := LOWER(program_code);

    IF backup_data THEN
        -- Créer un dossier de sauvegarde
        backup_file := format('/tmp/backup_%s_%s', schema_name, to_char(CURRENT_TIMESTAMP, 'YYYYMMDD_HH24MISS'));

        -- Exporter chaque table en CSV
        FOR table_name IN
            SELECT tablename FROM pg_tables WHERE schemaname = schema_name
        LOOP
            EXECUTE format('COPY %I.%I TO ''%s/%s.csv'' WITH CSV HEADER',
                         schema_name, table_name, backup_file, table_name);
        END LOOP;

        RAISE NOTICE 'Données sauvegardées dans %', backup_file;
    END IF;

    -- Supprimer le schéma
    EXECUTE format('DROP SCHEMA IF EXISTS %I CASCADE', schema_name);

    RAISE NOTICE 'Schéma % supprimé', schema_name;
END;
$$ LANGUAGE plpgsql;

-- ATTENTION: Décommentez ce bloc pour migrer les données existantes
DO $$
BEGIN
    PERFORM migrate_existing_data_to_schemas();
END;
$$;

COMMENT ON FUNCTION create_program_schema(TEXT) IS 'Crée un schéma complet pour un programme avec toutes les tables sauf user, programme, partenaire, groupe, password_recovery_code';
COMMENT ON FUNCTION migrate_existing_data_to_schemas() IS 'Migre les données existantes vers les nouveaux schémas par programme';
COMMENT ON FUNCTION drop_program_schema(TEXT, BOOLEAN) IS 'Supprime un schéma de programme avec option de sauvegarde';
