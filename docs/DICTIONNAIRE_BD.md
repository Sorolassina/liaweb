# 📊 Dictionnaire de la Base de Données - LIA WEB

## 🗂️ Vue d'ensemble

Ce document présente la structure complète de la base de données de l'application LIA WEB, incluant tous les schémas, tables, colonnes, types de données, contraintes et relations.

---

## 📋 Schémas de la Base de Données

### 1. **Schéma `public`** (Schéma principal)
- **Description** : Contient les tables centrales de l'application
- **Tables principales** : `user`, `programme`, `session`, etc.

### 2. **Schémas de programmes** (Multi-tenant)
- **Description** : Chaque programme a son propre schéma PostgreSQL
- **Exemples** : `acd`, `aci`, `act`, etc.
- **Tables** : `candidat`, `preinscription`, `inscription`, `entreprise`, etc.

---

## 🗃️ Tables du Schéma `public`

### Table `user`
**Description** : Utilisateurs de l'application (conseillers, coordinateurs, jury, etc.)

| Colonne | Type | Contraintes | Description |
|---------|------|-------------|-------------|
| `id` | `INTEGER` | PRIMARY KEY, AUTO_INCREMENT | Identifiant unique |
| `email` | `VARCHAR` | UNIQUE, NOT NULL, INDEX | Adresse email |
| `nom_complet` | `VARCHAR` | NOT NULL | Nom complet |
| `telephone` | `VARCHAR` | NULLABLE | Numéro de téléphone |
| `mot_de_passe_hash` | `VARCHAR` | NOT NULL | Hash du mot de passe |
| `role` | `ENUM` | NOT NULL | Rôle utilisateur |
| `type_utilisateur` | `ENUM` | NULLABLE | Type d'utilisateur |
| `actif` | `BOOLEAN` | DEFAULT TRUE | Statut actif/inactif |
| `derniere_connexion` | `TIMESTAMP` | NULLABLE | Dernière connexion |
| `photo_profil` | `VARCHAR` | NULLABLE | Chemin photo de profil |
| `cree_le` | `TIMESTAMP` | DEFAULT NOW() | Date de création |

**Valeurs d'enum `role`** :
- `admin` : Administrateur
- `directeur_technique` : Directeur technique
- `conseiller` : Conseiller
- `coordinateur` : Coordinateur
- `jury` : Membre du jury
- `coach` : Coach

**Valeurs d'enum `type_utilisateur`** :
- `interne` : Utilisateur interne
- `externe` : Utilisateur externe

### Table `programme`
**Description** : Programmes de formation disponibles

| Colonne | Type | Contraintes | Description |
|---------|------|-------------|-------------|
| `id` | `INTEGER` | PRIMARY KEY, AUTO_INCREMENT | Identifiant unique |
| `nom` | `VARCHAR` | NOT NULL, UNIQUE | Nom du programme |
| `description` | `TEXT` | NULLABLE | Description du programme |
| `duree_mois` | `INTEGER` | NULLABLE | Durée en mois |
| `actif` | `BOOLEAN` | DEFAULT TRUE | Statut actif/inactif |
| `cree_le` | `TIMESTAMP` | DEFAULT NOW() | Date de création |

### Table `session`
**Description** : Sessions de formation

| Colonne | Type | Contraintes | Description |
|---------|------|-------------|-------------|
| `id` | `INTEGER` | PRIMARY KEY, AUTO_INCREMENT | Identifiant unique |
| `nom` | `VARCHAR` | NOT NULL | Nom de la session |
| `programme_id` | `INTEGER` | FOREIGN KEY → programme.id | Programme associé |
| `date_debut` | `DATE` | NOT NULL | Date de début |
| `date_fin` | `DATE` | NULLABLE | Date de fin |
| `statut` | `ENUM` | DEFAULT 'planifie' | Statut de la session |
| `cree_le` | `TIMESTAMP` | DEFAULT NOW() | Date de création |

**Valeurs d'enum `statut`** :
- `planifie` : Planifiée
- `en_cours` : En cours
- `termine` : Terminée
- `annule` : Annulée

### Table `events`
**Description** : Événements du système

| Colonne | Type | Contraintes | Description |
|---------|------|-------------|-------------|
| `id` | `INTEGER` | PRIMARY KEY, AUTO_INCREMENT | Identifiant unique |
| `titre` | `VARCHAR` | NOT NULL | Titre de l'événement |
| `description` | `TEXT` | NULLABLE | Description |
| `date_debut` | `DATE` | NOT NULL | Date de début |
| `date_fin` | `DATE` | NULLABLE | Date de fin |
| `heure_debut` | `TIME` | NULLABLE | Heure de début |
| `heure_fin` | `TIME` | NULLABLE | Heure de fin |
| `lieu` | `VARCHAR` | NULLABLE | Lieu de l'événement |
| `statut` | `ENUM` | DEFAULT 'planifie' | Statut de l'événement |
| `programme_id` | `INTEGER` | FOREIGN KEY → programme.id | Programme associé |
| `organisateur_id` | `INTEGER` | FOREIGN KEY → user.id | Organisateur |
| `cree_le` | `TIMESTAMP` | DEFAULT NOW() | Date de création |
| `modifie_le` | `TIMESTAMP` | NULLABLE | Date de modification |

**Valeurs d'enum `statut`** :
- `planifie` : Planifié
- `en_cours` : En cours
- `termine` : Terminé
- `annule` : Annulé

### Table `rendezvous`
**Description** : Rendez-vous entre conseillers et candidats

| Colonne | Type | Contraintes | Description |
|---------|------|-------------|-------------|
| `id` | `INTEGER` | PRIMARY KEY, AUTO_INCREMENT | Identifiant unique |
| `date_rdv` | `DATE` | NOT NULL | Date du rendez-vous |
| `heure_debut` | `TIME` | NOT NULL | Heure de début |
| `heure_fin` | `TIME` | NOT NULL | Heure de fin |
| `type_rdv` | `ENUM` | NOT NULL | Type de rendez-vous |
| `statut` | `ENUM` | DEFAULT 'planifie' | Statut du rendez-vous |
| `lieu` | `VARCHAR` | NULLABLE | Lieu du rendez-vous |
| `notes` | `TEXT` | NULLABLE | Notes du rendez-vous |
| `conseiller_id` | `INTEGER` | FOREIGN KEY → user.id | Conseiller |
| `candidat_id` | `INTEGER` | NULLABLE | Candidat (référence vers schéma programme) |
| `programme_id` | `INTEGER` | FOREIGN KEY → programme.id | Programme |
| `cree_le` | `TIMESTAMP` | DEFAULT NOW() | Date de création |

**Valeurs d'enum `type_rdv`** :
- `entretien` : Entretien
- `suivi` : Suivi
- `evaluation` : Évaluation

**Valeurs d'enum `statut`** :
- `planifie` : Planifié
- `confirme` : Confirmé
- `termine` : Terminé
- `annule` : Annulé
- `reporte` : Reporté

---

## 🏢 Tables des Schémas de Programmes

*Note : Ces tables existent dans chaque schéma de programme (ex: `acd`, `aci`, `act`)*

### Table `candidat`
**Description** : Candidats aux programmes

| Colonne | Type | Contraintes | Description |
|---------|------|-------------|-------------|
| `id` | `INTEGER` | PRIMARY KEY, AUTO_INCREMENT | Identifiant unique |
| `civilite` | `VARCHAR` | NULLABLE | Civilité |
| `nom` | `VARCHAR` | NOT NULL | Nom de famille |
| `prenom` | `VARCHAR` | NOT NULL | Prénom |
| `date_naissance` | `DATE` | NULLABLE | Date de naissance |
| `email` | `VARCHAR` | UNIQUE, NOT NULL, INDEX | Adresse email |
| `telephone` | `VARCHAR` | NULLABLE | Numéro de téléphone |
| `adresse_personnelle` | `TEXT` | NULLABLE | Adresse personnelle |
| `niveau_etudes` | `VARCHAR` | NULLABLE | Niveau d'études |
| `secteur_activite` | `VARCHAR` | NULLABLE | Secteur d'activité |
| `photo_profil` | `VARCHAR` | NULLABLE | Chemin photo de profil |
| `statut` | `VARCHAR` | DEFAULT 'EN_ATTENTE' | Statut du candidat |
| `lat` | `FLOAT` | NULLABLE, INDEX | Latitude (géocodage) |
| `lng` | `FLOAT` | NULLABLE, INDEX | Longitude (géocodage) |
| `handicap` | `BOOLEAN` | DEFAULT FALSE | Présence d'un handicap |
| `type_handicap` | `ENUM` | NULLABLE | Type de handicap |
| `cree_le` | `TIMESTAMP` | DEFAULT NOW() | Date de création |
| `modifie_le` | `TIMESTAMP` | NULLABLE | Date de modification |

**Valeurs d'enum `type_handicap`** :
- `moteur` : Handicap moteur
- `visuel` : Handicap visuel
- `auditif` : Handicap auditif
- `mental` : Handicap mental
- `autre` : Autre type

### Table `preinscription`
**Description** : Pré-inscriptions des candidats

| Colonne | Type | Contraintes | Description |
|---------|------|-------------|-------------|
| `id` | `INTEGER` | PRIMARY KEY, AUTO_INCREMENT | Identifiant unique |
| `candidat_id` | `INTEGER` | FOREIGN KEY → candidat.id | Candidat |
| `programme_id` | `INTEGER` | FOREIGN KEY → programme.id | Programme |
| `date_preinscription` | `DATE` | DEFAULT NOW() | Date de pré-inscription |
| `statut` | `ENUM` | DEFAULT 'en_attente' | Statut de la pré-inscription |
| `motivation` | `TEXT` | NULLABLE | Lettre de motivation |
| `attentes` | `TEXT` | NULLABLE | Attentes du candidat |
| `cree_le` | `TIMESTAMP` | DEFAULT NOW() | Date de création |

**Valeurs d'enum `statut`** :
- `en_attente` : En attente
- `accepte` : Acceptée
- `refuse` : Refusée
- `annule` : Annulée

### Table `inscription`
**Description** : Inscriptions validées des candidats

| Colonne | Type | Contraintes | Description |
|---------|------|-------------|-------------|
| `id` | `INTEGER` | PRIMARY KEY, AUTO_INCREMENT | Identifiant unique |
| `candidat_id` | `INTEGER` | FOREIGN KEY → candidat.id | Candidat |
| `programme_id` | `INTEGER` | FOREIGN KEY → programme.id | Programme |
| `session_id` | `INTEGER` | FOREIGN KEY → session.id | Session |
| `date_inscription` | `DATE` | DEFAULT NOW() | Date d'inscription |
| `statut` | `ENUM` | DEFAULT 'en_examen' | Statut de l'inscription |
| `date_decision` | `DATE` | NULLABLE | Date de décision |
| `notes_jury` | `TEXT` | NULLABLE | Notes du jury |
| `cree_le` | `TIMESTAMP` | DEFAULT NOW() | Date de création |

**Valeurs d'enum `statut`** :
- `en_examen` : En examen
- `valide` : Validée
- `reoriente` : Réorientée
- `refuse` : Refusée

### Table `entreprise`
**Description** : Entreprises des candidats

| Colonne | Type | Contraintes | Description |
|---------|------|-------------|-------------|
| `id` | `INTEGER` | PRIMARY KEY, AUTO_INCREMENT | Identifiant unique |
| `candidat_id` | `INTEGER` | FOREIGN KEY → candidat.id | Candidat |
| `nom_entreprise` | `VARCHAR` | NOT NULL | Nom de l'entreprise |
| `secteur_activite` | `VARCHAR` | NULLABLE | Secteur d'activité |
| `taille_entreprise` | `VARCHAR` | NULLABLE | Taille de l'entreprise |
| `adresse_entreprise` | `TEXT` | NULLABLE | Adresse de l'entreprise |
| `poste_occupe` | `VARCHAR` | NULLABLE | Poste occupé |
| `anciennete_mois` | `INTEGER` | NULLABLE | Ancienneté en mois |
| `qpv` | `BOOLEAN` | NULLABLE | Quartier Prioritaire de la Ville |
| `qpv_limite` | `BOOLEAN` | NULLABLE | QPV limite |
| `cree_le` | `TIMESTAMP` | DEFAULT NOW() | Date de création |

### Table `document`
**Description** : Documents des candidats

| Colonne | Type | Contraintes | Description |
|---------|------|-------------|-------------|
| `id` | `INTEGER` | PRIMARY KEY, AUTO_INCREMENT | Identifiant unique |
| `candidat_id` | `INTEGER` | FOREIGN KEY → candidat.id | Candidat |
| `nom_fichier` | `VARCHAR` | NOT NULL | Nom du fichier |
| `chemin_fichier` | `VARCHAR` | NOT NULL | Chemin vers le fichier |
| `type_document` | `ENUM` | NOT NULL | Type de document |
| `taille_fichier` | `INTEGER` | NULLABLE | Taille en octets |
| `date_upload` | `TIMESTAMP` | DEFAULT NOW() | Date d'upload |
| `statut` | `ENUM` | DEFAULT 'en_attente' | Statut du document |

**Valeurs d'enum `type_document`** :
- `cv` : CV
- `lettre_motivation` : Lettre de motivation
- `piece_identite` : Pièce d'identité
- `justificatif_revenus` : Justificatif de revenus
- `autre` : Autre

**Valeurs d'enum `statut`** :
- `en_attente` : En attente
- `valide` : Validé
- `refuse` : Refusé

### Table `decision_jury_table`
**Description** : Décisions du jury pour les candidats

| Colonne | Type | Contraintes | Description |
|---------|------|-------------|-------------|
| `id` | `INTEGER` | PRIMARY KEY, AUTO_INCREMENT | Identifiant unique |
| `candidat_id` | `INTEGER` | FOREIGN KEY → candidat.id | Candidat |
| `jury_id` | `INTEGER` | FOREIGN KEY → user.id | Membre du jury |
| `decision` | `ENUM` | NOT NULL | Décision du jury |
| `notes` | `TEXT` | NULLABLE | Notes du jury |
| `date_decision` | `TIMESTAMP` | DEFAULT NOW() | Date de décision |
| `cree_le` | `TIMESTAMP` | DEFAULT NOW() | Date de création |

**Valeurs d'enum `decision`** :
- `valide` : Validé
- `reoriente` : Réorienté
- `refuse` : Refusé
- `en_attente` : En attente

### Table `eligibilite`
**Description** : Critères d'éligibilité des candidats

| Colonne | Type | Contraintes | Description |
|---------|------|-------------|-------------|
| `id` | `INTEGER` | PRIMARY KEY, AUTO_INCREMENT | Identifiant unique |
| `candidat_id` | `INTEGER` | FOREIGN KEY → candidat.id | Candidat |
| `critere` | `VARCHAR` | NOT NULL | Nom du critère |
| `valeur` | `VARCHAR` | NOT NULL | Valeur du critère |
| `verifie` | `BOOLEAN` | DEFAULT FALSE | Critère vérifié |
| `date_verification` | `TIMESTAMP` | NULLABLE | Date de vérification |
| `cree_le` | `TIMESTAMP` | DEFAULT NOW() | Date de création |

---

## 🔗 Relations Principales

### Relations du schéma `public`
- `session.programme_id` → `programme.id`
- `events.programme_id` → `programme.id`
- `events.organisateur_id` → `user.id`
- `rendezvous.conseiller_id` → `user.id`
- `rendezvous.programme_id` → `programme.id`

### Relations des schémas de programmes
- `preinscription.candidat_id` → `candidat.id`
- `preinscription.programme_id` → `programme.id`
- `inscription.candidat_id` → `candidat.id`
- `inscription.programme_id` → `programme.id`
- `inscription.session_id` → `session.id`
- `entreprise.candidat_id` → `candidat.id`
- `document.candidat_id` → `candidat.id`
- `decision_jury_table.candidat_id` → `candidat.id`
- `decision_jury_table.jury_id` → `user.id`
- `eligibilite.candidat_id` → `candidat.id`

---

## 📊 Index et Contraintes

### Index uniques
- `user.email`
- `candidat.email` (dans chaque schéma)
- `programme.nom`

### Index de performance
- `candidat.lat, candidat.lng` (géocodage)
- `user.role`
- `inscription.statut`
- `rendezvous.statut`

### Contraintes de clés étrangères
- Toutes les relations sont protégées par des contraintes de clés étrangères
- Suppression en cascade pour les relations dépendantes

---

## 🔄 Architecture Multi-Tenant

### Principe
- **Schéma public** : Tables centrales partagées
- **Schémas programmes** : Données spécifiques à chaque programme
- **Routage dynamique** : L'application route automatiquement vers le bon schéma

### Avantages
- **Isolation des données** : Chaque programme a ses propres données
- **Scalabilité** : Facile d'ajouter de nouveaux programmes
- **Sécurité** : Isolation au niveau de la base de données

---

## 📝 Notes Techniques

### Gestion des Enums
- Les enums sont stockés sous forme de chaînes en minuscules
- Valeurs définies dans `app/models/enums.py`
- Cohérence maintenue entre l'application et la base de données

### Géocodage
- Coordonnées GPS stockées dans `candidat.lat` et `candidat.lng`
- Index spatial pour les requêtes de proximité
- Utilisé pour la répartition géographique des candidats

### Gestion des fichiers
- Documents stockés dans le système de fichiers
- Chemins relatifs stockés en base
- Types de documents standardisés

---

*Dernière mise à jour : $(date)*
*Version de l'application : LIA WEB v1.0*
