# PIPELINE DE GESTION DES PRÉINSCRIPTIONS - LIA WEB

Ce document détaille le pipeline complet de gestion des préinscriptions dans l'application LIA WEB, incluant les routes, templates, services et processus métier.

## Vue d'ensemble

Le système de préinscriptions permet aux candidats de soumettre leur candidature via un formulaire public, avec validation automatique de l'éligibilité, géocodage des adresses, vérification QPV et gestion des documents.

---

## 1. ARCHITECTURE GÉNÉRALE

### Technologies Utilisées
- **Backend** : FastAPI avec SQLModel
- **Frontend** : Jinja2 templates avec JavaScript
- **Base de données** : PostgreSQL avec relations complexes
- **Services externes** : API Adresse (géocodage), API Pappers (SIRET), Service QPV
- **Upload de fichiers** : FileUploadService avec validation

### Modèles Impliqués
- **Preinscription** : Demande de préinscription
- **Candidat** : Informations personnelles du candidat
- **Entreprise** : Données d'entreprise avec géolocalisation
- **Eligibilite** : Évaluation automatique de l'éligibilité
- **Document** : Fichiers uploadés par le candidat

---

## 2. ROUTES ET PIPELINES

### 2.1 Formulaire Public de Préinscription

**Route** : `GET /ACD/preinscriptions/public-form`
**Nom** : `preinscriptions_public_form`
**Template** : `programme/preinscription_public_form.html`

#### Pipeline Complet

1. **Déclenchement** : Accès direct ou via lien avec paramètre `programme`
2. **Route déclenchée** : `preinscriptions_public_form`
3. **Variables calculées** :
   ```python
   # Récupération du programme spécifique si fourni
   prog = session.exec(select(Programme).where(Programme.code == programme)).first()
   
   # Récupération de tous les programmes actifs
   programmes_actifs = session.exec(
       select(Programme).where(Programme.actif.is_(True)).order_by(Programme.code)
   ).all()
   ```
4. **Modèles interrogés** :
   - `Programme` : Programmes actifs pour la liste déroulante
5. **Validation schématique** : Aucune (page d'affichage)
6. **Transmission** : Template avec programmes disponibles
7. **Affichage** : Formulaire de préinscription avec sélection de programme

#### Template `preinscription_public_form.html`

**Sections principales** :
- **Sélection de programme** : Liste déroulante des programmes actifs
- **Informations personnelles** : Nom, prénom, email, téléphone, date de naissance
- **Adresse personnelle** : Champ obligatoire pour géocodage
- **Informations d'entreprise** : SIRET, raison sociale, adresse, CA, date de création
- **Upload de photo** : Photo de profil avec prévisualisation
- **Documents dynamiques** : Système de répétition pour upload de documents
- **Validation côté client** : JavaScript pour validation des champs

**Navigation disponible** :
- Soumission vers `preinscriptions_public_submit` (POST)

### 2.2 Soumission de Préinscription

**Route** : `POST /ACD/preinscriptions/submit`
**Nom** : `preinscriptions_public_submit`
**Redirection** : `preinscriptions_merci`

#### Pipeline Complet

1. **Déclenchement** : Soumission du formulaire de préinscription
2. **Route déclenchée** : `preinscriptions_public_submit`
3. **Variables calculées** :
   ```python
   # Validation du programme
   prog = session.exec(select(Programme).where(Programme.code == programme_code)).first()
   
   # Conversion des dates
   dn = _date.fromisoformat(date_naissance)
   dce = _date.fromisoformat(date_creation_entreprise) if date_creation_entreprise else None
   
   # Recherche ou création du candidat
   cand = session.exec(select(Candidat).where(Candidat.email == email)).first()
   if not cand:
       cand = Candidat(email=email, nom=nom, prenom=prenom)
       session.add(cand)
       session.flush()
   ```
4. **Modèles interrogés** :
   - `Programme` : Validation du programme sélectionné
   - `Candidat` : Recherche par email (création si inexistant)
   - `Entreprise` : Recherche par candidat_id (création si inexistant)
   - `Inscription` : Vérification de non-double inscription
   - `Preinscription` : Vérification de non-double préinscription
5. **Validation schématique** :
   - **Unicité email** : Un candidat par email
   - **Unicité préinscription** : Une préinscription par candidat/programme
   - **Validation des fichiers** : Taille, type MIME, extensions
   - **Validation des dates** : Format ISO valide
6. **Services appelés** :
   - **Géocodage** : `geocode_one(addr_for_geo)` pour coordonnées GPS
   - **Évaluation éligibilité** : `evaluate_eligibilite()` pour critères métier
   - **Upload de fichiers** : `FileUploadService.save_file()` pour photos et documents
   - **Vérification QPV** : `verif_qpv()` pour statut Quartier Prioritaire
7. **Transmission** : Redirection vers page de remerciement
8. **Affichage** : Page de confirmation avec message de succès

#### Processus de Validation

**Étapes de validation** :
1. **Programme valide** : Vérification de l'existence du programme
2. **Candidat unique** : Recherche par email, création si nécessaire
3. **Pas de double inscription** : Vérification dans `Inscription`
4. **Pas de double préinscription** : Vérification dans `Preinscription`
5. **Upload de fichiers** : Validation taille, type, sauvegarde sécurisée
6. **Géocodage** : Conversion adresse en coordonnées GPS
7. **Évaluation éligibilité** : Calcul automatique des critères
8. **Vérification QPV** : Recherche automatique du statut QPV

#### Gestion des Erreurs

**Erreurs possibles** :
- **Programme inexistant** : Retour au formulaire avec message d'erreur
- **Candidat déjà inscrit** : Message d'erreur explicite
- **Candidat déjà préinscrit** : Message d'erreur explicite
- **Upload échoué** : Validation des fichiers avec messages spécifiques
- **Géocodage échoué** : Continuation sans coordonnées GPS

### 2.3 Page de Remerciement

**Route** : `GET /ACD/preinscriptions/merci`
**Nom** : `preinscriptions_merci`
**Template** : `programme/preinscription_merci.html`

#### Pipeline Complet

1. **Déclenchement** : Redirection après soumission réussie
2. **Route déclenchée** : `preinscriptions_merci`
3. **Variables calculées** : Aucune (page statique)
4. **Modèles interrogés** : Aucun
5. **Validation schématique** : Aucune
6. **Transmission** : Template simple avec message de confirmation
7. **Affichage** : Page de remerciement avec bouton retour

#### Template `preinscription_merci.html`

**Contenu** :
- **Message de confirmation** : "Merci pour votre préinscription"
- **Instructions** : "Nous reviendrons vers vous rapidement"
- **Bouton retour** : Retour vers la liste des préinscriptions

**Navigation disponible** :
- Retour vers `preinscriptions_form` avec programme par défaut

### 2.4 Liste Administrative des Préinscriptions

**Route** : `GET /ACD/preinscriptions/form`
**Nom** : `preinscriptions_form`
**Template** : `programme/preinscriptions_list.html`

#### Pipeline Complet

1. **Déclenchement** : Accès administrateur à la liste des préinscriptions
2. **Route déclenchée** : `preinscriptions_form`
3. **Variables calculées** :
   ```python
   # Requête principale avec jointures
   stmt = (
       select(Preinscription, Candidat, Programme, Entreprise)
       .join(Candidat, Candidat.id == Preinscription.candidat_id)
       .join(Programme, Programme.id == Preinscription.programme_id)
       .join(Entreprise, Entreprise.candidat_id == Candidat.id, isouter=True)
   )
   
   # Filtres optionnels
   if programme:
       stmt = stmt.where(Programme.code == programme)
   if q:
       like = f"%{q}%"
       stmt = stmt.where(
           (Candidat.nom.ilike(like)) |
           (Candidat.prenom.ilike(like)) |
           (Candidat.email.ilike(like))
       )
   
   # KPI pour en-tête
   total = session.exec(select(func.count(Preinscription.id))).one() or 0
   total_programme = session.exec(
       select(func.count(Preinscription.id)).join(Programme).where(Programme.code == programme_code)
   ).one() or 0
   ```
4. **Modèles interrogés** :
   - `Preinscription` : Liste des préinscriptions avec jointures
   - `Candidat` : Informations personnelles des candidats
   - `Programme` : Détails des programmes
   - `Entreprise` : Données d'entreprise (optionnel)
5. **Validation schématique** : Aucune (lecture seule)
6. **Services appelés** :
   - **Génération de pins** : Coordonnées GPS pour carte interactive
7. **Transmission** : Template avec données paginées et KPI
8. **Affichage** : Liste avec filtres, recherche et carte interactive

#### Template `preinscriptions_list.html`

**Sections principales** :
- **KPI en-tête** : Total général et par programme
- **Filtres** : Par programme et recherche textuelle
- **Carte interactive** : Affichage des candidats avec coordonnées GPS
- **Tableau des préinscriptions** : Liste paginée avec informations détaillées
- **Actions** : Liens vers détails et gestion des candidats

**Navigation disponible** :
- Filtrage par programme via paramètre `programme`
- Recherche textuelle via paramètre `q`

---

## 3. SERVICES MÉTIER

### 3.1 Service d'Éligibilité (`eligibilite.py`)

**Fichier** : `app/services/ACD/eligibilite.py`
**Description** : Évaluation automatique de l'éligibilité des candidats

#### Fonctions Principales

**`evaluate_eligibilite()`** :
```python
def evaluate_eligibilite(
    adresse_perso: Optional[str],
    adresse_entreprise: Optional[str],
    chiffre_affaires: Optional[str],
    anciennete_annees: Optional[float],
    ca_min: Optional[float], ca_max: Optional[float],
    anciennete_min_annees: Optional[int]
) -> Tuple[str, dict]:
```

**Critères d'évaluation** :
- **QPV** : Vérification du statut Quartier Prioritaire
- **Chiffre d'affaires** : Comparaison avec seuils du programme
- **Ancienneté** : Vérification de l'ancienneté minimale

**Verdicts possibles** :
- `"ok"` : Tous les critères sont respectés
- `"attention"` : Critères partiellement respectés
- `"ko"` : Critères non respectés

#### Fonctions Utilitaires

**`parse_ca_intervalle()`** :
- Parse les intervalles de CA (ex: "10 000 - 50 000 €")
- Retourne les bornes min/max pour comparaison

**`compare_ca_intervalles()`** :
- Compare l'intervalle déclaré avec les seuils du programme
- Gère les cas de seuils min/max/intervalle complet

**`entreprise_age_annees()`** :
- Calcule l'ancienneté de l'entreprise en années
- Prend en compte les années bissextiles

### 3.2 Service de Géocodage (`geocoding.py`)

**Fichier** : `app/services/geocoding.py`
**Description** : Conversion d'adresses en coordonnées GPS

#### Fonction Principale

**`geocode_one()`** :
```python
async def geocode_one(address: str) -> Optional[Tuple[float, float]]:
```

**Processus** :
1. **Appel API Adresse** : `https://api-adresse.data.gouv.fr/search/`
2. **Validation de la réponse** : Vérification du format JSON
3. **Extraction des coordonnées** : Latitude et longitude
4. **Retour** : Tuple (lat, lng) ou None si échec

**Gestion des erreurs** :
- **Adresse invalide** : Retour None
- **API indisponible** : Retour None
- **Format incorrect** : Retour None

### 3.3 Service QPV (`service_qpv.py`)

**Fichier** : `app/services/ACD/service_qpv.py`
**Description** : Vérification du statut Quartier Prioritaire

#### Fonction Principale

**`verif_qpv()`** :
```python
async def verif_qpv(address_coords, request: Request):
```

**Processus** :
1. **Géocodage de l'adresse** : Conversion en coordonnées GPS
2. **Recherche QPV** : Consultation de la base QPV
3. **Calcul de distance** : Si hors QPV, calcul de la distance
4. **Génération de carte** : Carte Folium avec polygone QPV
5. **Retour des résultats** : Statut QPV et métadonnées

**Statuts possibles** :
- `"QPV"` : Adresse dans un QPV
- `"QPV limit"` : Adresse proche d'un QPV (dans la limite)
- `"Adresse à plus de X m du qpv"` : Adresse éloignée

### 3.4 Service d'Upload (`FileUploadService`)

**Fichier** : `app/services/file_upload_service.py`
**Description** : Gestion sécurisée des uploads de fichiers

#### Méthodes Principales

**`save_file()`** :
```python
async def save_file(
    file: UploadFile,
    base_folder: str,
    filename: str,
    subfolder: Optional[str] = None
) -> dict:
```

**Processus** :
1. **Validation du fichier** : Taille, type MIME, extension
2. **Génération du chemin** : Structure organisée par programme/candidat
3. **Sauvegarde sécurisée** : Création des dossiers, écriture du fichier
4. **Retour des métadonnées** : Chemin relatif, taille, nom original

**Structure des dossiers** :
```
media/
└── Preinscrits/
    └── {programme_code}/
        └── {preinscription_id}/
            ├── photo_profil_{id}.jpg
            ├── document_{id}.pdf
            └── ...
```

---

## 4. VALIDATION ET SÉCURITÉ

### 4.1 Validation des Données

**Validation côté serveur** :
- **Email unique** : Vérification de l'unicité dans la base
- **Dates valides** : Format ISO avec conversion sécurisée
- **Fichiers uploadés** : Taille, type MIME, extension
- **Champs obligatoires** : Nom, prénom, email, adresse personnelle

**Validation côté client** :
- **Champs requis** : Validation HTML5 et JavaScript
- **Format email** : Validation regex côté client
- **Taille des fichiers** : Limitation avant upload
- **Prévisualisation** : Photo de profil avec aperçu

### 4.2 Sécurité des Uploads

**Contrôles de sécurité** :
- **Types MIME autorisés** : Images et documents spécifiques
- **Taille maximale** : Limite configurable par type de fichier
- **Noms de fichiers sécurisés** : Nettoyage des caractères spéciaux
- **Structure de dossiers** : Isolation par programme et candidat

**Types de fichiers autorisés** :
- **Images** : JPG, PNG, GIF pour photos de profil
- **Documents** : PDF, DOC, DOCX pour documents administratifs

### 4.3 Protection contre les Doublons

**Vérifications d'unicité** :
- **Candidat par email** : Un seul candidat par adresse email
- **Préinscription par programme** : Une préinscription par candidat/programme
- **Inscription existante** : Vérification avant création de préinscription

**Messages d'erreur explicites** :
- **Programme inexistant** : Redirection avec message d'erreur
- **Déjà inscrit** : Message clair avec instructions
- **Déjà préinscrit** : Message clair avec instructions

---

## 5. INTÉGRATION ET SERVICES EXTERNES

### 5.1 API Adresse (Géocodage)

**Endpoint** : `https://api-adresse.data.gouv.fr/search/`
**Usage** : Conversion d'adresses en coordonnées GPS
**Gestion des erreurs** : Retour None en cas d'échec

### 5.2 API Pappers (SIRET)

**Endpoint** : `https://api.pappers.fr/v2/entreprise`
**Usage** : Vérification et enrichissement des données SIRET
**Authentification** : Token API configuré

### 5.3 Service QPV

**Source** : Base de données QPV intégrée
**Usage** : Vérification du statut Quartier Prioritaire
**Fonctionnalités** : Calcul de distance, génération de cartes

---

## 6. GESTION DES ERREURS

### 6.1 Erreurs de Validation

**Programme inexistant** :
- **Cause** : Code programme invalide
- **Action** : Retour au formulaire avec message d'erreur
- **Récupération** : Liste des programmes disponibles

**Candidat déjà inscrit** :
- **Cause** : Inscription existante pour le programme
- **Action** : Message d'erreur explicite
- **Récupération** : Aucune (blocage intentionnel)

**Candidat déjà préinscrit** :
- **Cause** : Préinscription existante pour le programme
- **Action** : Message d'erreur explicite
- **Récupération** : Aucune (blocage intentionnel)

### 6.2 Erreurs d'Upload

**Fichier trop volumineux** :
- **Cause** : Dépassement de la limite de taille
- **Action** : Rejet du fichier avec message d'erreur
- **Récupération** : Demande de fichier plus petit

**Type de fichier non autorisé** :
- **Cause** : Type MIME non autorisé
- **Action** : Rejet du fichier avec message d'erreur
- **Récupération** : Demande de fichier au bon format

### 6.3 Erreurs de Services Externes

**Géocodage échoué** :
- **Cause** : API Adresse indisponible ou adresse invalide
- **Action** : Continuation sans coordonnées GPS
- **Récupération** : Préinscription créée sans géolocalisation

**Vérification QPV échouée** :
- **Cause** : Service QPV indisponible
- **Action** : Continuation sans statut QPV
- **Récupération** : Préinscription créée sans vérification QPV

---

## 7. PERFORMANCE ET OPTIMISATION

### 7.1 Optimisation des Requêtes

**Jointures optimisées** :
- **Préinscription + Candidat + Programme + Entreprise** : Une seule requête
- **Index sur email** : Recherche rapide des candidats existants
- **Index sur programme_id** : Filtrage efficace par programme

**Pagination** :
- **Limite de 300** : Éviter les requêtes trop lourdes
- **Tri par date** : Préinscriptions les plus récentes en premier

### 7.2 Gestion des Fichiers

**Structure organisée** :
- **Séparation par programme** : Isolation des données
- **Séparation par candidat** : Organisation claire
- **Noms uniques** : Éviter les conflits de fichiers

**Optimisation des uploads** :
- **Validation préalable** : Rejet des fichiers invalides
- **Sauvegarde asynchrone** : Non-blocage de l'interface
- **Métadonnées en base** : Traçabilité des fichiers

### 7.3 Cache et Sessions

**Sessions de base de données** :
- **Pool de connexions** : Réutilisation des connexions
- **Transactions atomiques** : Rollback en cas d'erreur
- **Flush avant commit** : Récupération des IDs générés

---

## 8. MONITORING ET LOGS

### 8.1 Logs de Debug

**Activation conditionnelle** :
```python
if settings.DEBUG:
    print(f"🔍 [DEBUG] Route /ACD/preinscriptions/submit appelée")
    print(f"📝 [DEBUG] Données reçues: {programme_code}")
```

**Informations loggées** :
- **Données reçues** : Paramètres du formulaire
- **Création candidat** : Nouveau ou existant
- **Création entreprise** : Nouvelle ou existante
- **Géocodage** : Succès ou échec
- **Upload fichiers** : Nombre et types de fichiers
- **Évaluation éligibilité** : Résultats des critères

### 8.2 Métriques de Performance

**KPI calculés** :
- **Total des préinscriptions** : Comptage global
- **Préinscriptions par programme** : Comptage par programme
- **Taux de succès** : Préinscriptions créées vs erreurs

**Surveillance des services** :
- **Géocodage** : Taux de succès des appels API
- **Upload** : Taille moyenne des fichiers
- **QPV** : Temps de traitement des vérifications

---

## 9. ÉVOLUTION ET MAINTENANCE

### 9.1 Ajout de Nouveaux Champs

**Processus d'ajout** :
1. **Modification du modèle** : Ajout des champs dans `Preinscription`, `Candidat`, `Entreprise`
2. **Mise à jour du formulaire** : Ajout des champs dans le template
3. **Validation côté serveur** : Ajout des contrôles dans la route
4. **Migration de base** : Création des colonnes manquantes

### 9.2 Modification des Critères d'Éligibilité

**Processus de modification** :
1. **Mise à jour du service** : Modification de `evaluate_eligibilite()`
2. **Tests des critères** : Validation avec des cas de test
3. **Mise à jour des seuils** : Modification des seuils par programme
4. **Recalcul des éligibilités** : Script de mise à jour des données existantes

### 9.3 Ajout de Nouveaux Services

**Processus d'intégration** :
1. **Création du service** : Nouveau fichier dans `app/services/`
2. **Intégration dans la route** : Appel du service dans `preinscriptions_public_submit`
3. **Gestion des erreurs** : Traitement des échecs du service
4. **Tests d'intégration** : Validation du fonctionnement complet

---

*Document généré automatiquement - Pipeline de gestion des préinscriptions LIA WEB*
