# Système E-Learning LIA Coaching

## Vue d'ensemble

Le système e-learning permet aux candidats de suivre des formations en ligne avec des ressources pédagogiques variées (vidéos, documents, quiz, etc.). Il inclut un système de progression, de certification et de statistiques.

## Architecture

### Modèles de données

#### 1. RessourceElearning
- **Rôle** : Contenu pédagogique individuel (vidéo, document, quiz, lien, audio)
- **Champs clés** :
  - `type_ressource` : Type de contenu (video, document, quiz, lien, audio)
  - `duree_minutes` : Durée estimée
  - `difficulte` : Niveau de difficulté (facile, moyen, difficile)
  - `url_contenu` / `fichier_path` : Localisation du contenu

#### 2. ModuleElearning
- **Rôle** : Regroupement de ressources pédagogiques
- **Champs clés** :
  - `programme_id` : Programme associé
  - `objectifs` : Objectifs pédagogiques
  - `duree_totale_minutes` : Durée totale du module
  - `statut` : État du module (brouillon, actif, archive)

#### 3. ProgressionElearning
- **Rôle** : Suivi de la progression d'un candidat
- **Champs clés** :
  - `inscription_id` : Candidat concerné
  - `statut` : État de progression (non_commence, en_cours, termine, abandonne)
  - `temps_consacre_minutes` : Temps passé sur la ressource
  - `score` : Score obtenu (pour les quiz)

#### 4. ObjectifElearning
- **Rôle** : Objectifs obligatoires par programme
- **Champs clés** :
  - `temps_minimum_minutes` : Temps minimum requis
  - `modules_obligatoires` : Modules obligatoires

#### 5. QuizElearning & ReponseQuiz
- **Rôle** : Système de quiz avec évaluation
- **Types de questions** : Choix multiple, Vrai/Faux, Texte libre

#### 6. CertificatElearning
- **Rôle** : Certificats de completion
- **Génération automatique** lors de la completion des objectifs

## Fonctionnalités

### 1. Gestion des Ressources
- **Création** : Ajout de ressources multimédias
- **Organisation** : Classement par type, difficulté, tags
- **Validation** : Système de validation des contenus

### 2. Construction des Modules
- **Assemblage** : Combinaison de ressources en modules cohérents
- **Séquencement** : Ordre d'apprentissage défini
- **Prérequis** : Gestion des dépendances entre modules

### 3. Suivi de Progression
- **Temps réel** : Suivi en temps réel de l'activité
- **Sauvegarde automatique** : Progression sauvegardée automatiquement
- **Reprise** : Possibilité de reprendre où on s'est arrêté

### 4. Évaluation
- **Quiz intégrés** : Questions d'évaluation dans les ressources
- **Scores** : Calcul automatique des scores
- **Feedback** : Explications des bonnes/mauvaises réponses

### 5. Certification
- **Génération automatique** : Certificats générés automatiquement
- **Validation** : Vérification des objectifs atteints
- **Export** : Certificats téléchargeables en PDF

### 6. Statistiques et Rapports
- **Candidat** : Progression individuelle, temps passé, scores
- **Programme** : Statistiques globales, taux de completion
- **Ressources** : Popularité, efficacité des contenus

## Interface Utilisateur

### Dashboard E-Learning
- **Vue d'ensemble** : Statistiques générales
- **Programmes** : État des programmes e-learning
- **Métriques clés** : Candidats actifs, temps moyen, taux de completion

### Gestion des Modules
- **Liste** : Affichage des modules avec filtres
- **Détail** : Vue détaillée d'un module
- **Édition** : Création/modification des modules

### Suivi Candidat
- **Progression** : Vue détaillée de la progression
- **Ressources** : Accès aux ressources du module
- **Certificats** : Certificats obtenus

## API Endpoints

### Ressources
- `POST /elearning/ressources` : Créer une ressource
- `GET /elearning/ressources` : Lister les ressources
- `PUT /elearning/ressources/{id}` : Modifier une ressource

### Modules
- `POST /elearning/modules` : Créer un module
- `GET /elearning/modules` : Lister les modules
- `POST /elearning/modules/{id}/ressources/{ressource_id}` : Ajouter une ressource

### Progression
- `POST /elearning/progression/start` : Commencer une ressource
- `PUT /elearning/progression/{id}` : Mettre à jour la progression
- `POST /elearning/progression/{id}/complete` : Terminer une ressource

### Quiz
- `POST /elearning/quiz` : Créer un quiz
- `POST /elearning/quiz/reponse` : Soumettre une réponse

### Statistiques
- `GET /elearning/statistiques/candidat/{id}` : Stats d'un candidat
- `GET /elearning/statistiques/programme/{id}` : Stats d'un programme

## Sécurité et Permissions

### Rôles autorisés
- **Administrateur** : Accès complet
- **Responsable Programme** : Gestion des modules de son programme
- **Formateur** : Création/modification de ressources
- **Candidat** : Accès à ses modules et progression

### Contrôles d'accès
- **Authentification** : Token JWT requis
- **Autorisation** : Vérification des rôles
- **Isolation** : Candidats voient uniquement leurs données

## Installation et Configuration

### 1. Création des tables
```bash
psql -U liauser -d liacoaching -f scripts/create_elearning_tables.sql
```

### 2. Configuration des médias
- **Dossier uploads** : `/static/uploads/elearning/`
- **Types autorisés** : PDF, MP4, MP3, DOCX, PPTX
- **Taille max** : 100MB par fichier

### 3. Intégration dans l'application
- **Routeur** : Ajout du routeur e-learning
- **Navigation** : Ajout des liens dans le menu
- **Permissions** : Configuration des rôles

## Utilisation

### Pour les Administrateurs
1. **Créer des ressources** : Ajouter du contenu pédagogique
2. **Construire des modules** : Organiser les ressources
3. **Définir des objectifs** : Fixer les exigences par programme
4. **Suivre les statistiques** : Analyser l'efficacité

### Pour les Candidats
1. **Accéder aux modules** : Via leur espace personnel
2. **Suivre la progression** : Temps passé, scores obtenus
3. **Passer les quiz** : Évaluation des acquis
4. **Obtenir des certificats** : Validation des objectifs

## Évolutions possibles

### Fonctionnalités avancées
- **Gamification** : Points, badges, classements
- **Social Learning** : Forums, discussions
- **Adaptive Learning** : Contenu adaptatif selon le niveau
- **Mobile Learning** : Application mobile dédiée

### Intégrations
- **LMS externes** : Moodle, Canvas, Blackboard
- **Outils de création** : Articulate, Captivate
- **Analytics** : Google Analytics, Mixpanel
- **Vidéoconférence** : Intégration Zoom/Teams

## Maintenance

### Sauvegarde
- **Base de données** : Sauvegarde quotidienne des tables e-learning
- **Fichiers médias** : Sauvegarde des uploads
- **Certificats** : Archivage des certificats générés

### Monitoring
- **Performance** : Temps de chargement des ressources
- **Utilisation** : Statistiques d'usage
- **Erreurs** : Logs des erreurs d'accès

### Mise à jour
- **Contenu** : Mise à jour régulière des ressources
- **Sécurité** : Mise à jour des permissions
- **Fonctionnalités** : Ajout de nouvelles fonctionnalités
