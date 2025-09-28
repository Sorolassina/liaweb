# PIPELINE DE GESTION DES INSCRIPTIONS - LIA WEB

Ce document détaille le pipeline complet de gestion des inscriptions dans l'application LIA WEB, incluant les routes, templates, services et processus métier pour la conversion des préinscriptions en inscriptions.

## Vue d'ensemble

Le système d'inscriptions permet aux administrateurs de gérer le processus complet de conversion des préinscriptions en inscriptions, avec gestion du pipeline, évaluation de l'éligibilité, gestion des documents, et prise de décisions de jury.

---

## 1. ARCHITECTURE GÉNÉRALE

### Technologies Utilisées
- **Backend** : FastAPI avec SQLModel
- **Frontend** : Jinja2 templates avec JavaScript interactif
- **Base de données** : PostgreSQL avec relations complexes
- **Services externes** : API QPV, API SIRET/Pappers, Géocodage
- **Upload de fichiers** : FileUploadService avec validation
- **Pipeline de traitement** : Gestion des étapes avec avancement

### Modèles Impliqués
- **Inscription** : Inscription validée avec conseiller et référent
- **Preinscription** : Demande de préinscription source
- **Candidat** : Informations personnelles du candidat
- **Entreprise** : Données d'entreprise avec géolocalisation
- **Eligibilite** : Évaluation de l'éligibilité
- **AvancementEtape** : Suivi du pipeline de traitement
- **DecisionJuryCandidat** : Décisions du jury
- **Document** : Fichiers associés au candidat

---

## 2. ROUTES ET PIPELINES

### 2.1 Interface d'Inscription Principale

**Route** : `GET /inscriptions/form`
**Nom** : `form_inscriptions_display`
**Template** : `programme/inscription.html`

#### Pipeline Complet

1. **Déclenchement** : Accès administrateur à l'interface d'inscription
2. **Route déclenchée** : `form_inscriptions_display`
3. **Variables calculées** :
   ```python
   # Récupération du programme
   prog = _prog_by_code(session, programme)
   
   # Liste des préinscriptions avec jointures
   stmt = (
       select(Preinscription, Candidat, Entreprise, Eligibilite)
       .join(Candidat, Candidat.id==Preinscription.candidat_id)
       .join(Entreprise, Entreprise.candidat_id==Candidat.id, isouter=True)
       .join(Eligibilite, Eligibilite.preinscription_id==Preinscription.id, isouter=True)
       .where(Preinscription.programme_id==prog.id)
   )
   
   # KPI pour le tableau de bord
   total_pre = session.exec(select(func.count(Preinscription.id)).where(Preinscription.programme_id==prog.id)).one() or 0
   total_insc = session.exec(select(func.count(Inscription.id)).where(Inscription.programme_id==prog.id)).one() or 0
   taux_conv = round((total_insc / total_pre * 100), 1) if total_pre else 0.0
   
   # Objectif QPV
   qpv_ok_count = session.exec(
       select(func.count(Eligibilite.id)).join(Preinscription).where(
           (Preinscription.programme_id==prog.id) & (Eligibilite.qpv_ok.is_(True))
       )
   ).one() or 0
   objectif_qpv_atteint = round((qpv_ok_count / total_pre * 100), 1) if total_pre else 0.0
   ```
4. **Modèles interrogés** :
   - `Preinscription` : Liste des préinscriptions avec jointures
   - `Candidat` : Informations personnelles des candidats
   - `Entreprise` : Données d'entreprise (optionnel)
   - `Eligibilite` : Évaluation de l'éligibilité (optionnel)
   - `Inscription` : Inscriptions existantes pour le programme
   - `AvancementEtape` : Pipeline de traitement
   - `Jury` : Sessions de jury
   - `DecisionJuryCandidat` : Décisions du jury avec relations
   - `User` : Conseillers disponibles
   - `Promotion` : Promotions disponibles
   - `Partenaire` : Partenaires actifs
   - `Groupe` : Groupes de codéveloppement
5. **Validation schématique** : Aucune (lecture seule)
6. **Services appelés** :
   - **Extraction QPV** : Parsing des détails JSON pour nom QPV
7. **Transmission** : Template avec données complètes et KPI
8. **Affichage** : Interface split-screen avec liste des préinscriptions et détails

#### Template `inscription.html`

**Sections principales** :
- **KPI en-tête** : Total préinscriptions, inscriptions, taux de conversion, objectif QPV
- **Pan gauche** : Liste des préinscriptions avec recherche et filtres
- **Pan droit** : Détails du candidat sélectionné avec onglets
  - **Informations personnelles** : Données candidat et entreprise
  - **Éligibilité** : Évaluation automatique des critères
  - **Documents** : Gestion des fichiers uploadés
  - **Pipeline** : Suivi des étapes de traitement
  - **Décisions jury** : Historique des décisions
  - **Actions** : Boutons d'action (créer inscription, avancer étape, etc.)

**Navigation disponible** :
- Sélection de préinscription via paramètre `pre_id`
- Filtrage par programme via paramètre `programme`
- Recherche textuelle via paramètre `q`

### 2.2 Création d'Inscription depuis Préinscription

**Route** : `POST /inscriptions/create-from-pre`
**Nom** : `create_inscription_from_preinscription`
**Redirection** : `form_inscriptions_display`

#### Pipeline Complet

1. **Déclenchement** : Clic sur "Créer inscription" dans l'interface
2. **Route déclenchée** : `create_inscription_from_preinscription`
3. **Variables calculées** :
   ```python
   # Récupération de la préinscription
   pre = session.get(Preinscription, pre_id)
   prog = session.get(Programme, pre.programme_id)
   
   # Vérification d'unicité
   exists = session.exec(
       select(Inscription).where(
           (Inscription.programme_id==pre.programme_id) & 
           (Inscription.candidat_id==pre.candidat_id)
       )
   ).first()
   ```
4. **Modèles interrogés** :
   - `Preinscription` : Préinscription source
   - `Programme` : Programme associé
   - `Inscription` : Vérification d'unicité
   - `EtapePipeline` : Étapes du pipeline du programme
5. **Validation schématique** :
   - **Unicité inscription** : Une seule inscription par candidat/programme
   - **Préinscription existante** : Vérification de l'existence
   - **Programme valide** : Vérification de l'existence
6. **Services appelés** :
   - **Initialisation pipeline** : Création des étapes d'avancement
7. **Transmission** : Redirection vers l'interface avec préinscription sélectionnée
8. **Affichage** : Interface mise à jour avec inscription créée

#### Processus de Création

**Étapes de création** :
1. **Validation de la préinscription** : Vérification de l'existence
2. **Validation du programme** : Vérification de l'existence
3. **Vérification d'unicité** : Pas de double inscription
4. **Création de l'inscription** : Nouvel enregistrement avec statut de la préinscription
5. **Initialisation du pipeline** : Création des étapes d'avancement
6. **Commit de la transaction** : Sauvegarde atomique

### 2.3 Mise à Jour des Informations Candidat/Entreprise

**Route** : `POST /inscriptions/update-infos`
**Nom** : `update_infos_inscription`
**Redirection** : `form_inscriptions_display`

#### Pipeline Complet

1. **Déclenchement** : Soumission du formulaire de mise à jour
2. **Route déclenchée** : `update_infos_inscription`
3. **Variables calculées** :
   ```python
   # Récupération des entités
   pre = session.get(Preinscription, pre_id)
   cand = session.get(Candidat, pre.candidat_id)
   ent = session.exec(select(Entreprise).where(Entreprise.candidat_id==cand.id)).first()
   
   # Conversion des dates
   if date_naissance:
       cand.date_naissance = _date.fromisoformat(date_naissance)
   if date_creation:
       ent.date_creation = _date.fromisoformat(date_creation)
   
   # Conversion des coordonnées GPS
   if lat and lat.strip():
       cand.lat = float(lat)
   if lng and lng.strip():
       cand.lng = float(lng)
   ```
4. **Modèles interrogés** :
   - `Preinscription` : Préinscription source
   - `Candidat` : Candidat à mettre à jour
   - `Entreprise` : Entreprise à mettre à jour (création si inexistante)
   - `Document` : Documents existants du candidat
5. **Validation schématique** :
   - **Conversion des dates** : Format ISO valide
   - **Conversion des coordonnées** : Valeurs numériques valides
   - **Upload de photo** : Validation taille, type MIME
6. **Services appelés** :
   - **Validation upload** : `validate_upload()` pour la photo
   - **FileUploadService** : Sauvegarde sécurisée de la photo
   - **Suppression ancienne photo** : Nettoyage des fichiers
   - **Audit** : `log_activity()` pour traçabilité
7. **Transmission** : Redirection vers l'interface avec message de succès
8. **Affichage** : Interface mise à jour avec nouvelles informations

#### Gestion des Uploads

**Processus d'upload de photo** :
1. **Validation du fichier** : Taille, type MIME, extension
2. **Suppression ancienne photo** : Nettoyage des fichiers existants
3. **Génération du chemin** : Structure organisée par programme/candidat
4. **Sauvegarde sécurisée** : Utilisation de FileUploadService
5. **Mise à jour du candidat** : Chemin relatif de la nouvelle photo

### 2.4 Recalcul de l'Éligibilité

**Route** : `POST /inscriptions/eligibilite/recalc`
**Nom** : `eligibilite_recalc`
**Redirection** : `form_inscriptions_display`

#### Pipeline Complet

1. **Déclenchement** : Clic sur "Recalculer éligibilité"
2. **Route déclenchée** : `eligibilite_recalc`
3. **Variables calculées** :
   ```python
   # Récupération des entités
   pre = session.get(Preinscription, pre_id)
   prog = session.get(Programme, pre.programme_id)
   cand = session.get(Candidat, pre.candidat_id)
   ent = session.exec(select(Entreprise).where(Entreprise.candidat_id==cand.id)).first()
   
   # Calcul de l'ancienneté
   anc = entreprise_age_annees(ent.date_creation)
   
   # Évaluation de l'éligibilité
   verdict, details = evaluate_eligibilite(
       adresse_perso=cand.adresse_personnelle,
       adresse_entreprise=ent.adresse,
       chiffre_affaires=ent.chiffre_affaires,
       anciennete_annees=anc,
       ca_min=prog.ca_seuil_min,
       ca_max=prog.ca_seuil_max,
       anciennete_min_annees=prog.anciennete_min_annees
   )
   ```
4. **Modèles interrogés** :
   - `Preinscription` : Préinscription source
   - `Programme` : Programme avec seuils
   - `Candidat` : Candidat avec adresse personnelle
   - `Entreprise` : Entreprise avec CA et date de création
   - `Eligibilite` : Éligibilité existante (création si inexistante)
5. **Validation schématique** :
   - **Existence des entités** : Vérification de l'existence
   - **Calculs métier** : Ancienneté, évaluation des critères
6. **Services appelés** :
   - **Calcul ancienneté** : `entreprise_age_annees()`
   - **Évaluation éligibilité** : `evaluate_eligibilite()`
7. **Transmission** : Redirection vers l'interface avec éligibilité mise à jour
8. **Affichage** : Interface mise à jour avec nouveaux critères d'éligibilité

### 2.5 Gestion des Documents

#### Ajout de Document

**Route** : `POST /inscriptions/add-document`
**Nom** : `add_document_inscription`
**Redirection** : `form_inscriptions_display`

#### Pipeline Complet

1. **Déclenchement** : Upload de document via formulaire
2. **Route déclenchée** : `add_document_inscription`
3. **Variables calculées** :
   ```python
   # Validation du candidat
   candidat = session.get(Candidat, candidat_id)
   
   # Validation du fichier
   file_content = document_file.file.read()
   if len(file_content) > 10 * 1024 * 1024:  # 10MB
       raise HTTPException(status_code=400, detail="Fichier trop volumineux")
   
   # Préparation du répertoire
   subfolder = f"documents/candidat_{candidat_id}"
   base_filename = f"{type_document.lower()}_{candidat_id}{file_ext}"
   ```
4. **Modèles interrogés** :
   - `Candidat` : Candidat destinataire
   - `Document` : Création du nouvel enregistrement
5. **Validation schématique** :
   - **Taille du fichier** : Maximum 10MB
   - **Extension autorisée** : PDF, DOC, DOCX, JPG, JPEG, PNG
   - **Type de document** : Validation via enum TypeDocument
6. **Services appelés** :
   - **FileUploadService** : Sauvegarde sécurisée du fichier
7. **Transmission** : Redirection vers l'interface avec message de succès
8. **Affichage** : Interface mise à jour avec nouveau document

#### Suppression de Document

**Route** : `POST /inscriptions/delete-document`
**Nom** : `delete_document_inscription`
**Redirection** : `form_inscriptions_display`

#### Pipeline Complet

1. **Déclenchement** : Clic sur "Supprimer" dans la liste des documents
2. **Route déclenchée** : `delete_document_inscription`
3. **Variables calculées** :
   ```python
   # Récupération du document
   doc = session.get(Document, document_id)
   
   # Suppression du fichier physique
   if doc.chemin_fichier and os.path.exists(doc.chemin_fichier):
       os.remove(doc.chemin_fichier)
   ```
4. **Modèles interrogés** :
   - `Document` : Document à supprimer
5. **Validation schématique** : Aucune (suppression)
6. **Services appelés** :
   - **Suppression fichier** : Suppression physique du fichier
7. **Transmission** : Redirection vers l'interface avec message de succès
8. **Affichage** : Interface mise à jour sans le document supprimé

### 2.6 Avancement d'Étape du Pipeline

**Route** : `POST /inscriptions/etape/advance`
**Nom** : `etape_advance_inscription`
**Redirection** : `form_inscriptions_display`

#### Pipeline Complet

1. **Déclenchement** : Clic sur bouton d'avancement d'étape
2. **Route déclenchée** : `etape_advance_inscription`
3. **Variables calculées** :
   ```python
   # Récupération de l'avancement
   av = session.get(AvancementEtape, avancement_id)
   
   # Conversion du statut
   new_status = StatutEtape[statut]
   
   # Mise à jour des timestamps
   now = _dt.utcnow()
   if new_status.name == "EN_COURS" and not av.debut_le:
       av.debut_le = now
   if new_status.name == "TERMINE":
       if not av.debut_le: av.debut_le = now
       av.termine_le = now
   ```
4. **Modèles interrogés** :
   - `AvancementEtape` : Étape à mettre à jour
   - `Inscription` : Inscription associée
   - `Programme` : Programme pour redirection
   - `Preinscription` : Préinscription pour redirection
5. **Validation schématique** :
   - **Statut valide** : Valeur dans l'enum StatutEtape
   - **Avancement existant** : Vérification de l'existence
6. **Services appelés** : Aucun
7. **Transmission** : Redirection vers l'interface avec étape mise à jour
8. **Affichage** : Interface mise à jour avec nouveau statut d'étape

---

## 3. GESTION DES DÉCISIONS DE JURY

### 3.1 Création de Décision de Jury

**Route** : `POST /inscriptions/jury/decision`
**Nom** : `create_jury_decision_inscription`
**Redirection** : `form_inscriptions_display`

#### Pipeline Complet

1. **Déclenchement** : Soumission du formulaire de décision de jury
2. **Route déclenchée** : `create_jury_decision_inscription`
3. **Variables calculées** :
   ```python
   # Conversion sécurisée des IDs
   def safe_int_convert(value):
       if value is None or (isinstance(value, str) and not value.strip()):
           return None
       try:
           return int(value)
       except ValueError:
           return None
   
   promotion_id_int = safe_int_convert(promotion_id)
   partenaire_id_int = safe_int_convert(partenaire_id)
   conseiller_id_int = safe_int_convert(conseiller_id)
   groupe_id_int = safe_int_convert(groupe_id)
   
   # Vérification d'unicité
   existing = session.exec(
       select(DecisionJuryCandidat).where(
           (DecisionJuryCandidat.candidat_id == candidat_id) &
           (DecisionJuryCandidat.jury_id == jury_id)
       )
   ).first()
   ```
4. **Modèles interrogés** :
   - `Candidat` : Candidat concerné
   - `Jury` : Jury de décision (optionnel)
   - `DecisionJuryCandidat` : Vérification d'unicité
   - `Groupe` : Vérification de l'existence
   - `ReorientationCandidat` : Création si réorientation
5. **Validation schématique** :
   - **Unicité décision** : Une seule décision par candidat/jury
   - **Conversion des IDs** : Valeurs numériques valides
   - **Existence des entités** : Vérification des références
6. **Services appelés** :
   - **Audit** : `log_activity()` pour traçabilité
7. **Transmission** : Redirection vers l'interface avec décision créée
8. **Affichage** : Interface mise à jour avec nouvelle décision

#### Processus de Décision

**Étapes de création** :
1. **Validation du candidat** : Vérification de l'existence
2. **Validation du jury** : Vérification de l'existence (si fourni)
3. **Vérification d'unicité** : Pas de double décision
4. **Conversion des IDs** : Transformation sécurisée des paramètres
5. **Création de la décision** : Nouvel enregistrement avec métadonnées
6. **Mise à jour du statut candidat** : Statut selon la décision
7. **Création de réorientation** : Si décision "REORIENTE"
8. **Commit de la transaction** : Sauvegarde atomique

### 3.2 Suppression de Décision de Jury

**Route** : `POST /inscriptions/jury/decision/{decision_id}/delete`
**Nom** : `delete_jury_decision_inscription`
**Redirection** : `form_inscriptions_display`

#### Pipeline Complet

1. **Déclenchement** : Clic sur "Supprimer" dans la liste des décisions
2. **Route déclenchée** : `delete_jury_decision_inscription`
3. **Variables calculées** :
   ```python
   # Récupération de la décision
   decision_obj = session.get(DecisionJuryCandidat, decision_id)
   candidat_id = decision_obj.candidat_id
   
   # Remise en attente du candidat
   candidat = session.get(Candidat, candidat_id)
   if candidat:
       candidat.statut = DecisionJury.EN_ATTENTE.value
   
   # Suppression des réorientations associées
   session.exec(
       select(ReorientationCandidat).where(
           ReorientationCandidat.decision_jury_id == decision_id
       )
   )
   ```
4. **Modèles interrogés** :
   - `DecisionJuryCandidat` : Décision à supprimer
   - `Candidat` : Candidat à remettre en attente
   - `ReorientationCandidat` : Réorientations à supprimer
5. **Validation schématique** : Aucune (suppression)
6. **Services appelés** :
   - **Audit** : `log_activity()` pour traçabilité
7. **Transmission** : Redirection vers l'interface avec décision supprimée
8. **Affichage** : Interface mise à jour sans la décision supprimée

---

## 4. INTÉGRATION SERVICES EXTERNES

### 4.1 Vérification QPV

**Route** : `POST /inscriptions/qpv-check`
**Nom** : `check_qpv_candidate_inscription`
**Retour** : JSON avec résultats

#### Pipeline Complet

1. **Déclenchement** : Clic sur "Vérifier QPV" dans l'interface
2. **Route déclenchée** : `check_qpv_candidate_inscription`
3. **Variables calculées** :
   ```python
   # Récupération du candidat
   candidat = session.get(Candidat, candidat_id)
   
   # Récupération des adresses depuis la base si non fournies
   if not adresse_personnelle or not adresse_entreprise:
       entreprise = session.exec(select(Entreprise).where(Entreprise.candidat_id == candidat_id)).first()
       if not adresse_personnelle:
           adresse_personnelle = candidat.adresse_personnelle
       if not adresse_entreprise and entreprise:
           adresse_entreprise = entreprise.adresse
   
   # Vérification du cache existant
   preinscription = session.exec(select(Preinscription).where(Preinscription.candidat_id == candidat_id)).first()
   if preinscription:
       eligibilite = session.exec(select(Eligibilite).where(Eligibilite.preinscription_id == preinscription.id)).first()
       if eligibilite and eligibilite.qpv_ok is not None and eligibilite.details_json:
           # Utilisation des données en cache si adresses identiques
   ```
4. **Modèles interrogés** :
   - `Candidat` : Candidat concerné
   - `Entreprise` : Entreprise associée
   - `Preinscription` : Préinscription associée
   - `Eligibilite` : Éligibilité existante
5. **Validation schématique** :
   - **Existence du candidat** : Vérification de l'existence
   - **Adresses valides** : Vérification de la qualité des adresses
6. **Services appelés** :
   - **Service QPV** : `verif_qpv()` pour chaque adresse
   - **Audit** : `log_activity()` pour traçabilité
7. **Transmission** : JSON avec résultats détaillés
8. **Affichage** : Mise à jour de l'interface avec statut QPV

#### Processus de Vérification

**Étapes de vérification** :
1. **Vérification du cache** : Utilisation des données existantes si adresses identiques
2. **Analyse adresse personnelle** : Appel du service QPV
3. **Analyse adresse entreprise** : Appel du service QPV
4. **Détermination du statut final** : QPV si au moins une adresse est QPV
5. **Mise à jour de l'éligibilité** : Sauvegarde des résultats
6. **Retour des résultats** : JSON avec détails complets

### 4.2 Vérification SIRET

**Route** : `POST /inscriptions/siret-check`
**Nom** : `check_siret_candidate_inscription`
**Retour** : JSON avec résultats

#### Pipeline Complet

1. **Déclenchement** : Clic sur "Vérifier SIRET" dans l'interface
2. **Route déclenchée** : `check_siret_candidate_inscription`
3. **Variables calculées** :
   ```python
   # Validation du format SIRET
   siret_request = SiretRequest(numero_siret=numero_siret)
   
   # Appel du service SIRET
   siret_info = await get_entreprise_process(siret_request.numero_siret[:9], request)
   
   # Mise à jour de l'entreprise
   entreprise = session.exec(select(Entreprise).where(Entreprise.candidat_id == candidat_id)).first()
   if not entreprise:
       entreprise = Entreprise(candidat_id=candidat_id)
       session.add(entreprise)
   
   if siret_info.get("entreprise_data"):
       data = siret_info["entreprise_data"]
       entreprise.siret = data.get("siege", {}).get("siret")
       entreprise.siren = data.get("siren")
       entreprise.raison_sociale = data.get("nom_entreprise")
       entreprise.code_naf = data.get("code_naf")
       entreprise.date_creation = data.get("date_creation")
   ```
4. **Modèles interrogés** :
   - `Candidat` : Candidat concerné
   - `Entreprise` : Entreprise à mettre à jour
5. **Validation schématique** :
   - **Format SIRET** : Validation via schema SiretRequest
   - **Existence du candidat** : Vérification de l'existence
6. **Services appelés** :
   - **Service SIRET** : `get_entreprise_process()` pour enrichissement
   - **Audit** : `log_activity()` pour traçabilité
7. **Transmission** : JSON avec résultats de la vérification
8. **Affichage** : Mise à jour de l'interface avec données enrichies

### 4.3 Téléchargement de Document SIRET

**Route** : `POST /inscriptions/download-siret-document`
**Nom** : `download_siret_document_inscription`
**Retour** : JSON avec statut

#### Pipeline Complet

1. **Déclenchement** : Clic sur "Télécharger" dans la liste des documents SIRET
2. **Route déclenchée** : `download_siret_document_inscription`
3. **Variables calculées** :
   ```python
   # Récupération des paramètres
   data = await request.json()
   candidat_id = data.get("candidat_id")
   token = data.get("token")
   nom_fichier = data.get("nom_fichier", "document_siret.pdf")
   
   # Téléchargement depuis l'API Pappers
   pappers_url = f"https://api.pappers.fr/v2/document/telechargement?token={token}&api_token={settings.PAPPERS_API_KEY}"
   response = requests.get(pappers_url, timeout=30)
   
   # Préparation du répertoire
   candidat_dir = settings.FICHIERS_DIR / "documents" / f"candidat_{candidat_id}"
   candidat_dir.mkdir(parents=True, exist_ok=True)
   
   # Création du nom unique
   base_filename = f"siret_{type_document.lower()}_{candidat_id}.pdf"
   unique_filename = base_filename
   counter = 1
   while (candidat_dir / unique_filename).exists():
       unique_filename = f"siret_{type_document.lower()}_{candidat_id}_{counter}.pdf"
       counter += 1
   ```
4. **Modèles interrogés** :
   - `Candidat` : Candidat destinataire
   - `Document` : Création du nouvel enregistrement
5. **Validation schématique** :
   - **Token valide** : Vérification de la présence
   - **API key configurée** : Vérification de la configuration
   - **Candidat existant** : Vérification de l'existence
6. **Services appelés** :
   - **API Pappers** : Téléchargement du document
   - **Sauvegarde fichier** : Écriture sur disque
7. **Transmission** : JSON avec statut de téléchargement
8. **Affichage** : Mise à jour de l'interface avec nouveau document

---

## 5. GESTION DES FICHIERS

### 5.1 Visualisation de Document

**Route** : `GET /inscriptions/document/{document_id}/view`
**Nom** : `inscriptions_document_view`
**Retour** : Fichier avec headers appropriés

#### Pipeline Complet

1. **Déclenchement** : Clic sur "Voir" dans la liste des documents
2. **Route déclenchée** : `inscriptions_document_view`
3. **Variables calculées** :
   ```python
   # Récupération du document
   doc = session.get(Document, document_id)
   
   # Construction du chemin
   file_path = settings.FICHIERS_DIR / doc.chemin_fichier
   
   # Détermination du type MIME
   import mimetypes
   mime_type, _ = mimetypes.guess_type(str(file_path))
   if not mime_type:
       mime_type = "application/octet-stream"
   
   # Lecture du fichier
   with open(file_path, "rb") as f:
       content = f.read()
   ```
4. **Modèles interrogés** :
   - `Document` : Document à visualiser
5. **Validation schématique** :
   - **Existence du document** : Vérification en base
   - **Existence du fichier** : Vérification sur disque
6. **Services appelés** : Aucun
7. **Transmission** : Response avec contenu et headers
8. **Affichage** : Fichier affiché dans le navigateur

### 5.2 Téléchargement de Document

**Route** : `GET /inscriptions/document/{document_id}/download`
**Nom** : `inscriptions_document_download`
**Retour** : FileResponse pour téléchargement

#### Pipeline Complet

1. **Déclenchement** : Clic sur "Télécharger" dans la liste des documents
2. **Route déclenchée** : `inscriptions_document_download`
3. **Variables calculées** :
   ```python
   # Récupération du document
   doc = session.get(Document, document_id)
   
   # Construction du chemin physique
   file_path = path_config.get_physical_path("files", doc.chemin_fichier)
   ```
4. **Modèles interrogés** :
   - `Document` : Document à télécharger
5. **Validation schématique** :
   - **Existence du document** : Vérification en base
   - **Existence du fichier** : Vérification sur disque
6. **Services appelés** : Aucun
7. **Transmission** : FileResponse pour téléchargement
8. **Affichage** : Fichier téléchargé par le navigateur

---

## 6. VALIDATION ET SÉCURITÉ

### 6.1 Validation des Données

**Validation côté serveur** :
- **Conversion des dates** : Format ISO avec gestion d'erreurs
- **Conversion des coordonnées** : Valeurs numériques avec gestion d'erreurs
- **Upload de fichiers** : Taille, type MIME, extension
- **Conversion des IDs** : Valeurs numériques avec gestion des chaînes vides
- **Unicité des entités** : Vérification des contraintes métier

**Validation côté client** :
- **Champs requis** : Validation HTML5 et JavaScript
- **Format des dates** : Validation regex côté client
- **Taille des fichiers** : Limitation avant upload
- **Confirmation des actions** : Prompts de confirmation pour les suppressions

### 6.2 Sécurité des Uploads

**Contrôles de sécurité** :
- **Types MIME autorisés** : Images et documents spécifiques
- **Taille maximale** : Limite configurable par type de fichier
- **Noms de fichiers sécurisés** : Nettoyage des caractères spéciaux
- **Structure de dossiers** : Isolation par candidat
- **Validation des extensions** : Liste blanche des extensions autorisées

**Types de fichiers autorisés** :
- **Images** : JPG, JPEG, PNG pour photos de profil
- **Documents** : PDF, DOC, DOCX pour documents administratifs

### 6.3 Protection contre les Erreurs

**Gestion des erreurs** :
- **Entités inexistantes** : Messages d'erreur explicites
- **Fichiers manquants** : Gestion gracieuse des fichiers supprimés
- **Services externes indisponibles** : Continuation sans échec
- **Transactions atomiques** : Rollback en cas d'erreur
- **Logs détaillés** : Traçabilité des erreurs

---

## 7. PERFORMANCE ET OPTIMISATION

### 7.1 Optimisation des Requêtes

**Jointures optimisées** :
- **Préinscription + Candidat + Entreprise + Éligibilité** : Une seule requête
- **Décisions jury avec relations** : Utilisation de `joinedload`
- **Index sur candidat_id** : Recherche rapide des entités associées
- **Index sur programme_id** : Filtrage efficace par programme

**Pagination et limites** :
- **Limite de 400** : Éviter les requêtes trop lourdes
- **Tri par date** : Préinscriptions les plus récentes en premier
- **Chargement à la demande** : Données chargées selon la sélection

### 7.2 Gestion des Fichiers

**Structure organisée** :
- **Séparation par candidat** : Isolation des données
- **Noms uniques** : Éviter les conflits de fichiers
- **Gestion des doublons** : Suffixes numériques automatiques

**Optimisation des uploads** :
- **Validation préalable** : Rejet des fichiers invalides
- **Sauvegarde asynchrone** : Non-blocage de l'interface
- **Métadonnées en base** : Traçabilité des fichiers

### 7.3 Cache et Sessions

**Sessions de base de données** :
- **Pool de connexions** : Réutilisation des connexions
- **Transactions atomiques** : Rollback en cas d'erreur
- **Flush avant commit** : Récupération des IDs générés

**Cache des services externes** :
- **Cache QPV** : Réutilisation des vérifications existantes
- **Vérification des adresses** : Comparaison pour éviter les appels inutiles

---

## 8. MONITORING ET LOGS

### 8.1 Logs de Debug

**Activation conditionnelle** :
```python
if settings.DEBUG:
    print(f"🔍 [DEBUG] Programme ID: {prog.id}")
    print(f"📊 [DEBUG] Nombre de préinscriptions trouvées: {len(pre_rows)}")
```

**Informations loggées** :
- **Données reçues** : Paramètres des formulaires
- **Entités trouvées** : Candidats, entreprises, documents
- **Services externes** : Appels QPV, SIRET, géocodage
- **Upload de fichiers** : Succès et échecs
- **Décisions de jury** : Création et suppression

### 8.2 Métriques de Performance

**KPI calculés** :
- **Total des préinscriptions** : Comptage par programme
- **Total des inscriptions** : Comptage par programme
- **Taux de conversion** : Préinscriptions → Inscriptions
- **Objectif QPV** : Pourcentage de candidats QPV

**Surveillance des services** :
- **Services externes** : Taux de succès des appels API
- **Upload** : Taille moyenne des fichiers
- **Pipeline** : Temps de traitement des étapes

### 8.3 Audit et Traçabilité

**Logs d'activité** :
- **Mise à jour informations** : Traçabilité des modifications
- **Décisions de jury** : Historique des décisions
- **Vérifications QPV/SIRET** : Traçabilité des appels
- **Gestion des documents** : Ajout et suppression

---

## 9. ÉVOLUTION ET MAINTENANCE

### 9.1 Ajout de Nouveaux Champs

**Processus d'ajout** :
1. **Modification du modèle** : Ajout des champs dans les modèles
2. **Mise à jour du formulaire** : Ajout des champs dans le template
3. **Validation côté serveur** : Ajout des contrôles dans la route
4. **Migration de base** : Création des colonnes manquantes

### 9.2 Modification du Pipeline

**Processus de modification** :
1. **Mise à jour des étapes** : Modification de `EtapePipeline`
2. **Recalcul des avancements** : Script de mise à jour des données existantes
3. **Tests du pipeline** : Validation avec des cas de test
4. **Mise à jour de l'interface** : Adaptation du template

### 9.3 Ajout de Nouveaux Services

**Processus d'intégration** :
1. **Création du service** : Nouveau fichier dans `app/services/`
2. **Intégration dans la route** : Appel du service dans les routes
3. **Gestion des erreurs** : Traitement des échecs du service
4. **Tests d'intégration** : Validation du fonctionnement complet

---

*Document généré automatiquement - Pipeline de gestion des inscriptions LIA WEB*
