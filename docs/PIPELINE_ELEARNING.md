# PIPELINE DE GESTION DE L'E-LEARNING - LIA WEB

Ce document détaille le pipeline complet de gestion de l'e-learning dans l'application LIA WEB, incluant les routes, templates, services et processus métier pour la création, gestion et suivi des modules de formation en ligne avec ressources multimédias, progression des candidats et statistiques.

## Vue d'ensemble

Le système d'e-learning permet aux formateurs de créer des modules de formation avec des ressources multimédias (vidéos, documents, audio, liens), de suivre la progression des candidats, de gérer les quiz et d'émettre des certificats de completion.

---

## 1. ARCHITECTURE GÉNÉRALE

### Technologies Utilisées
- **Backend** : FastAPI avec SQLModel
- **Frontend** : Jinja2 templates avec JavaScript interactif
- **Base de données** : PostgreSQL avec relations complexes
- **Services métier** : ElearningService pour la logique métier
- **Upload de fichiers** : FileUploadService pour gestion des médias
- **Statistiques** : Calculs de métriques et KPIs
- **Progression** : Suivi en temps réel des candidats

### Modèles Impliqués
- **ModuleElearning** : Module de formation e-learning
- **RessourceElearning** : Ressource pédagogique (vidéo, document, quiz, etc.)
- **ModuleRessource** : Table de liaison entre modules et ressources
- **ProgressionElearning** : Progression d'un candidat dans le e-learning
- **ObjectifElearning** : Objectifs e-learning obligatoires par programme
- **QuizElearning** : Quiz associé à une ressource
- **ReponseQuiz** : Réponse d'un candidat à un quiz
- **CertificatElearning** : Certificat de completion e-learning
- **Programme** : Programme de coaching associé
- **Inscription** : Inscription du candidat
- **User** : Créateur/formateur

---

## 2. ROUTES ET PIPELINES

### 2.1 Dashboard E-learning

**Route** : `GET /elearning/`
**Nom** : `elearning_dashboard`
**Template** : `elearning/dashboard.html`

#### Pipeline Complet

1. **Déclenchement** : Accès à la page principale de l'e-learning
2. **Route déclenchée** : `elearning_dashboard`
3. **Variables calculées** :
   ```python
   # Récupération des programmes actifs
   programmes = session.exec(
       select(Programme).where(Programme.actif == True)
   ).all()
   
   # Calcul des statistiques par programme
   stats_programmes = []
   for programme in programmes_to_process:
       stats = ElearningService.get_statistiques_programme(session, programme.id)
       stats_programmes.append(stats)
   ```
4. **Modèles interrogés** :
   - `Programme` : Programmes actifs
   - `Inscription` : Candidats inscrits
   - `ProgressionElearning` : Progressions des candidats
   - `ModuleElearning` : Modules du programme
5. **Validation schématique** :
   - **Filtrage par programme** : Optionnel pour restriction
   - **Gestion d'erreurs** : Try/catch pour calculs statistiques
6. **Services appelés** :
   - **ElearningService** : `get_statistiques_programme()` pour métriques
7. **Transmission** : Template avec statistiques par programme
8. **Affichage** : Dashboard avec KPIs et métriques

### 2.2 Liste des Modules

**Route** : `GET /elearning/modules`
**Nom** : `elearning_modules`
**Template** : `elearning/modules.html`

#### Pipeline Complet

1. **Déclenchement** : Clic sur "Modules" dans la navigation
2. **Route déclenchée** : `elearning_modules`
3. **Variables calculées** :
   ```python
   # Gestion des filtres
   if statut == "tous":
       statut = None
       actif_only = False  # Voir tous les modules (actifs ET inactifs)
   else:
       actif_only = True   # Par défaut, voir seulement les modules actifs
   
   if difficulte == "tous":
       difficulte = None
   
   # Récupération des modules avec filtres
   modules = ElearningService.get_modules(session, programme_id, statut, actif_only, difficulte)
   programmes = session.exec(select(Programme).where(Programme.actif == True)).all()
   ```
4. **Modèles interrogés** :
   - `ModuleElearning` : Modules avec filtres multiples
   - `Programme` : Programmes pour le filtre
5. **Validation schématique** :
   - **Filtres multiples** : Programme, statut, difficulté, actif
   - **Mode "tous"** : Affichage des modules actifs et inactifs
6. **Services appelés** :
   - **ElearningService** : `get_modules()` pour liste filtrée
7. **Transmission** : Template avec liste et filtres
8. **Affichage** : Liste des modules avec filtres avancés

### 2.3 Formulaire de Création de Module

**Route** : `GET /elearning/modules/creer`
**Nom** : `elearning_module_creer_form`
**Template** : `elearning/module_form.html`

#### Pipeline Complet

1. **Déclenchement** : Clic sur "Nouveau module"
2. **Route déclenchée** : `elearning_module_creer_form`
3. **Variables calculées** :
   ```python
   # Récupération des programmes actifs
   programmes = session.exec(select(Programme).where(Programme.actif == True)).all()
   ```
4. **Modèles interrogés** :
   - `Programme` : Programmes actifs pour association
5. **Validation schématique** :
   - **Filtres actifs** : Seuls les programmes actifs
6. **Services appelés** : Aucun (préparation des données)
7. **Transmission** : Template avec formulaire et programmes
8. **Affichage** : Formulaire de création avec sélections

### 2.4 Création de Module

**Route** : `POST /elearning/modules/creer`
**Nom** : `elearning_module_creer`
**Redirection** : `/elearning/modules`

#### Pipeline Complet

1. **Déclenchement** : Soumission du formulaire de création
2. **Route déclenchée** : `elearning_module_creer`
3. **Variables calculées** :
   ```python
   # Récupération des données du formulaire
   form_data = await request.form()
   
   # Création du module
   module_data = ModuleElearningCreate(
       titre=form_data.get("titre"),
       description=form_data.get("description"),
       programme_id=int(form_data.get("programme_id")),
       objectifs=form_data.get("objectifs"),
       prerequis=form_data.get("prerequis"),
       duree_totale_minutes=int(form_data.get("duree_totale_minutes")) if form_data.get("duree_totale_minutes") else None,
       difficulte=form_data.get("difficulte", "facile"),
       statut=form_data.get("statut", "brouillon"),
       ordre=int(form_data.get("ordre", 0)),
       actif=form_data.get("actif") == "true"
   )
   ```
4. **Modèles interrogés** :
   - `ModuleElearning` : Création du nouvel enregistrement
5. **Validation schématique** :
   - **Contrôle d'accès** : Administrateur, responsable_programme, formateur
   - **Champs obligatoires** : Titre, programme
   - **Conversion des types** : Entiers, booléens
   - **Gestion d'erreurs** : Try/catch avec redirection
6. **Services appelés** :
   - **ElearningService** : `create_module()` pour création
7. **Transmission** : Redirection vers la liste des modules
8. **Affichage** : Liste des modules mise à jour

### 2.5 Détail d'un Module

**Route** : `GET /elearning/modules/{module_id}`
**Nom** : `elearning_module_detail`
**Template** : `elearning/module_detail.html`

#### Pipeline Complet

1. **Déclenchement** : Clic sur un module dans la liste
2. **Route déclenchée** : `elearning_module_detail`
3. **Variables calculées** :
   ```python
   # Récupération du module
   module = session.get(ModuleElearning, module_id)
   
   # Récupération des ressources du module avec leurs informations de liaison
   ressources_query = session.exec(
       select(RessourceElearning, ModuleRessource)
       .join(ModuleRessource, RessourceElearning.id == ModuleRessource.ressource_id)
       .where(ModuleRessource.module_id == module_id)
       .order_by(ModuleRessource.ordre)
   ).all()
   
   # Transformation des résultats pour inclure les informations de liaison
   ressources = []
   for ressource, module_ressource in ressources_query:
       ressource_data = {
           'id': ressource.id,
           'titre': ressource.titre,
           'description': ressource.description,
           'type_ressource': ressource.type_ressource,
           # URLs et fichiers spécifiques par type
           'url_contenu_video': ressource.url_contenu_video,
           'url_contenu_document': ressource.url_contenu_document,
           'url_contenu_audio': ressource.url_contenu_audio,
           'url_contenu_lien': ressource.url_contenu_lien,
           'fichier_video_path': ressource.fichier_video_path,
           'fichier_document_path': ressource.fichier_document_path,
           'fichier_audio_path': ressource.fichier_audio_path,
           # Propriétés de liaison
           'module_ordre': module_ressource.ordre,
           'obligatoire': module_ressource.obligatoire
       }
       ressources.append(ressource_data)
   ```
4. **Modèles interrogés** :
   - `ModuleElearning` : Module principal
   - `RessourceElearning` : Ressources associées
   - `ModuleRessource` : Liaisons module-ressource
5. **Validation schématique** :
   - **Existence du module** : Vérification de l'existence
6. **Services appelés** : Aucun (requête directe)
7. **Transmission** : Template avec module et ressources
8. **Affichage** : Page de détail avec ressources ordonnées

### 2.6 Formulaire de Création de Ressource

**Route** : `GET /elearning/ressources/creer`
**Nom** : `elearning_ressource_creer_form`
**Template** : `elearning/ressource_form.html`

#### Pipeline Complet

1. **Déclenchement** : Clic sur "Ajouter ressource" dans un module
2. **Route déclenchée** : `elearning_ressource_creer_form`
3. **Variables calculées** :
   ```python
   # Récupération des paramètres de requête
   module_id = request.query_params.get("module_id")
   return_url = request.query_params.get("return_url")
   ```
4. **Modèles interrogés** : Aucun (préparation des données)
5. **Validation schématique** :
   - **Contrôle d'accès** : Administrateur, responsable_programme, formateur
6. **Services appelés** : Aucun (préparation des données)
7. **Transmission** : Template avec formulaire et paramètres
8. **Affichage** : Formulaire de création de ressource

### 2.7 Création de Ressource

**Route** : `POST /elearning/ressources/creer`
**Nom** : `elearning_ressource_creer`
**Redirection** : URL de retour ou `/elearning/modules`

#### Pipeline Complet

1. **Déclenchement** : Soumission du formulaire de création de ressource
2. **Route déclenchée** : `elearning_ressource_creer`
3. **Variables calculées** :
   ```python
   # Récupération des données du formulaire
   form_data = await request.form()
   
   # Analyse des types de contenu présents
   TYPES = ("video", "document", "audio", "lien")
   presence = {}
   uploaded_files = {}
   urls_candidates = {}
   
   for t in TYPES:
       f_key = f"fichier_{t}"
       u_key = f"url_contenu_{t}"
       
       upload = form_data.get(f_key)
       has_file = bool(getattr(upload, "filename", None))
       url_val = (form_data.get(u_key) or "").strip()
       has_url = bool(url_val)
       
       if has_file or has_url:
           presence[t] = True
           if has_file:
               uploaded_files[t] = upload
           if has_url:
               urls_candidates[t] = url_val
   
   # Déterminer le type principal de la ressource
   type_principal = None
   if "video" in presence:
       type_principal = "video"
   elif "document" in presence:
       type_principal = "document"
   elif "audio" in presence:
       type_principal = "audio"
   elif "lien" in presence:
       type_principal = "lien"
   
   # Uploader tous les fichiers détectés
   fichiers_info = {}
   for t in TYPES:
       if t in uploaded_files:
           file_info = await FileUploadService.save_file(
               uploaded_files[t],
               t,  # type logique (video, document, audio)
               "elearning",  # dossier principal
               module_id,  # ID du module
           )
           fichiers_info[t] = {
               "path": file_info["relative_path"],
               "nom_original": uploaded_files[t].filename
           }
   
   # Construction du payload pour UNE SEULE ressource
   kwargs = {
       "titre": titre_base or "Ressource e-learning",
       "description": description,
       "type_ressource": type_principal,
       "duree_minutes": duree_minutes,
       "difficulte": difficulte,
       "tags": tags,
       "ordre": ordre,
       "actif": actif,
   }
   
   # Remplir tous les champs spécifiques selon les contenus disponibles
   for t in TYPES:
       if t in fichiers_info:
           kwargs[f"fichier_{t}_path"] = fichiers_info[t]["path"]
           kwargs[f"fichier_{t}_nom_original"] = fichiers_info[t]["nom_original"]
       
       if t in urls_candidates:
           kwargs[f"url_contenu_{t}"] = urls_candidates[t]
   
   # Création de la ressource unique
   ressource_data = RessourceElearningCreate(**kwargs)
   res = ElearningService.create_ressource(session, ressource_data, current_user.id)
   
   # Association au module si demandé
   if module_id is not None:
       ElearningService.add_ressource_to_module(
           session,
           module_id,
           res.id,
           ordre=ordre,
           obligatoire=obligatoire,
       )
   ```
4. **Modèles interrogés** :
   - `RessourceElearning` : Création de la ressource
   - `ModuleRessource` : Association au module
5. **Validation schématique** :
   - **Contrôle d'accès** : Administrateur, responsable_programme, formateur
   - **Types de contenu** : Vidéo, document, audio, lien
   - **Upload de fichiers** : Gestion des fichiers multimédias
   - **Gestion d'erreurs** : Try/catch avec nettoyage des fichiers
6. **Services appelés** :
   - **FileUploadService** : `save_file()` pour upload des fichiers
   - **ElearningService** : `create_ressource()` pour création
   - **ElearningService** : `add_ressource_to_module()` pour association
7. **Transmission** : Redirection vers l'URL de retour
8. **Affichage** : Page de destination mise à jour

### 2.8 Suppression de Ressource d'un Module

**Route** : `GET /elearning/modules/{module_id}/ressources/{ressource_id}/remove`
**Nom** : `remove_ressource_from_module`
**Redirection** : `/elearning/modules/{module_id}`

#### Pipeline Complet

1. **Déclenchement** : Clic sur "Supprimer" dans la liste des ressources
2. **Route déclenchée** : `remove_ressource_from_module`
3. **Variables calculées** :
   ```python
   # Suppression de la liaison via le service
   ElearningService.remove_ressource_from_module(session, module_id, ressource_id)
   ```
4. **Modèles interrogés** :
   - `ModuleRessource` : Suppression de la liaison
5. **Validation schématique** :
   - **Contrôle d'accès** : Administrateur, responsable_programme, formateur
   - **Gestion d'erreurs** : Try/catch avec redirection
6. **Services appelés** :
   - **ElearningService** : `remove_ressource_from_module()` pour suppression
7. **Transmission** : Redirection vers le détail du module
8. **Affichage** : Page de détail mise à jour

### 2.9 Modification de Ressource

**Route** : `POST /elearning/ressources/{ressource_id}/edit`
**Nom** : `elearning_ressource_edit`
**Redirection** : `/elearning/modules`

#### Pipeline Complet

1. **Déclenchement** : Soumission du formulaire de modification
2. **Route déclenchée** : `elearning_ressource_edit`
3. **Variables calculées** :
   ```python
   # Récupération des données du formulaire
   form_data = await request.form()
   
   # Déterminer le type de ressource basé sur les champs remplis
   type_ressource = ressource.type_ressource  # Garder le type existant par défaut
   
   # Vérifier les fichiers uploadés en priorité
   fichiers_presents = []
   if "fichier_video" in form_data and getattr(form_data.get("fichier_video"), "filename", None):
       fichiers_presents.append("video")
   if "fichier_document" in form_data and getattr(form_data.get("fichier_document"), "filename", None):
       fichiers_presents.append("document")
   if "fichier_audio" in form_data and getattr(form_data.get("fichier_audio"), "filename", None):
       fichiers_presents.append("audio")
   
   # Si plusieurs fichiers, utiliser le premier trouvé
   if fichiers_presents:
       type_ressource = fichiers_presents[0]
   # Sinon vérifier les URLs
   elif form_data.get("url_contenu_video"):
       type_ressource = "video"
   elif form_data.get("url_contenu_document"):
       type_ressource = "document"
   elif form_data.get("url_contenu_audio"):
       type_ressource = "audio"
   elif form_data.get("url_contenu_lien"):
       type_ressource = "lien"
   
   # Traiter tous les fichiers uploadés s'ils existent
   fichiers_info = []
   file_types = ["video", "document", "audio"]
   for file_type in file_types:
       field_name = f"fichier_{file_type}"
       if field_name in form_data:
           candidate = form_data.get(field_name)
           
           if getattr(candidate, "filename", None):
               file_info = await FileUploadService.save_file(
                   candidate,
                   file_type,
                   int(module_id) if module_id else None
               )
               
               fichiers_info.append({
                   "type": file_type,
                   "filename": candidate.filename,
                   "path": file_info["relative_path"]
               })
   
   # Mettre à jour la ressource
   ressource_data = RessourceElearningUpdate(
       titre=form_data.get("titre"),
       description=form_data.get("description"),
       type_ressource=type_ressource,
       
       # URLs pour chaque type
       url_contenu_video=form_data.get("url_contenu_video"),
       url_contenu_document=form_data.get("url_contenu_document"),
       url_contenu_audio=form_data.get("url_contenu_audio"),
       url_contenu_lien=form_data.get("url_contenu_lien"),
       
       # Fichiers pour chaque type
       fichier_video_path=fichier_video_path,
       fichier_video_nom_original=fichier_video_nom_original,
       fichier_document_path=fichier_document_path,
       fichier_document_nom_original=fichier_document_nom_original,
       fichier_audio_path=fichier_audio_path,
       fichier_audio_nom_original=fichier_audio_nom_original,
       
       # Champs généraux
       duree_minutes=int(form_data.get("duree_minutes")) if form_data.get("duree_minutes") else None,
       difficulte=form_data.get("difficulte", "facile"),
       tags=form_data.get("tags"),
       ordre=int(form_data.get("ordre", 0)),
       actif=form_data.get("actif") == "on"
   )
   ```
4. **Modèles interrogés** :
   - `RessourceElearning` : Mise à jour de la ressource
5. **Validation schématique** :
   - **Contrôle d'accès** : Administrateur, responsable_programme, formateur
   - **Types de contenu** : Détection automatique du type
   - **Upload de fichiers** : Gestion des nouveaux fichiers
   - **Gestion d'erreurs** : Try/catch avec rollback
6. **Services appelés** :
   - **FileUploadService** : `save_file()` pour nouveaux fichiers
   - **ElearningService** : `update_ressource()` pour mise à jour
7. **Transmission** : Redirection vers la liste des modules
8. **Affichage** : Liste des modules mise à jour

### 2.10 Statistiques E-learning

**Route** : `GET /elearning/statistiques`
**Nom** : `elearning_statistiques`
**Template** : `elearning/statistiques.html`

#### Pipeline Complet

1. **Déclenchement** : Clic sur "Statistiques" dans la navigation
2. **Route déclenchée** : `elearning_statistiques`
3. **Variables calculées** :
   ```python
   # Récupération des statistiques globales
   stats_globales = ElearningService.get_statistiques_globales(session)
   
   # Récupération des statistiques par programme
   programmes = session.exec(select(Programme).where(Programme.actif == True)).all()
   stats_par_programme = []
   for programme in programmes:
       stats_prog = ElearningService.get_statistiques_programme(session, programme.id)
       stats_par_programme.append({
           "programme": programme,
           "nb_modules": stats_prog.nb_modules,
           "nb_ressources": stats_prog.nb_ressources,
           "nb_candidats": stats_prog.nb_candidats,
           "temps_moyen": stats_prog.temps_moyen_minutes,
           "taux_completion": stats_prog.taux_completion,
           "score_moyen": stats_prog.score_moyen
       })
   
   # Top modules et candidats
   top_modules = ElearningService.get_top_modules(session, limit=5)
   top_candidats = ElearningService.get_top_candidats(session, limit=5)
   
   # Statistiques par type de ressource
   stats_ressources = ElearningService.get_stats_ressources_par_type(session)
   ```
4. **Modèles interrogés** :
   - `ModuleElearning` : Modules et statistiques
   - `RessourceElearning` : Ressources et types
   - `ProgressionElearning` : Progressions et temps
   - `Inscription` : Candidats et programmes
   - `Programme` : Programmes actifs
5. **Validation schématique** :
   - **Contrôle d'accès** : Administrateur, responsable_programme
6. **Services appelés** :
   - **ElearningService** : `get_statistiques_globales()` pour métriques globales
   - **ElearningService** : `get_statistiques_programme()` pour métriques par programme
   - **ElearningService** : `get_top_modules()` pour modules populaires
   - **ElearningService** : `get_top_candidats()` pour candidats actifs
   - **ElearningService** : `get_stats_ressources_par_type()` pour types de ressources
7. **Transmission** : Template avec toutes les statistiques
8. **Affichage** : Page de statistiques complètes

### 2.11 Progression d'un Candidat

**Route** : `GET /elearning/candidat/{inscription_id}`
**Nom** : `elearning_candidat_progression`
**Template** : `elearning/candidat_progression.html`

#### Pipeline Complet

1. **Déclenchement** : Clic sur un candidat dans les statistiques
2. **Route déclenchée** : `elearning_candidat_progression`
3. **Variables calculées** :
   ```python
   # Récupération de l'inscription
   inscription = session.get(Inscription, inscription_id)
   
   # Récupération des statistiques du candidat
   stats = ElearningService.get_statistiques_candidat(session, inscription_id)
   
   # Récupération de la progression détaillée
   progressions = ElearningService.get_progression_candidat(session, inscription_id)
   ```
4. **Modèles interrogés** :
   - `Inscription` : Inscription du candidat
   - `ProgressionElearning` : Progressions détaillées
   - `ModuleElearning` : Modules du programme
   - `RessourceElearning` : Ressources consultées
5. **Validation schématique** :
   - **Existence de l'inscription** : Vérification de l'existence
   - **Gestion d'erreurs** : Try/catch pour statistiques
6. **Services appelés** :
   - **ElearningService** : `get_statistiques_candidat()` pour métriques
   - **ElearningService** : `get_progression_candidat()` pour progression
7. **Transmission** : Template avec statistiques et progression
8. **Affichage** : Page de progression détaillée

---

## 3. SERVICES MÉTIER

### 3.1 Service E-learning (`ElearningService`)

**Fichier** : `app/services/elearning_service.py`
**Description** : Service principal pour la gestion de l'e-learning

#### Méthodes Principales

**`create_module()`** :
```python
@staticmethod
def create_module(session: Session, module_data: ModuleElearningCreate, createur_id: int) -> ModuleElearning:
    """Créer un nouveau module e-learning"""
    module = ModuleElearning(
        **module_data.dict(),
        cree_par_id=createur_id
    )
    session.add(module)
    session.commit()
    session.refresh(module)
    return module
```

**`get_modules()`** :
```python
@staticmethod
def get_modules(session: Session, programme_id: Optional[int] = None, statut: Optional[str] = None, actif_only: bool = True, difficulte: Optional[str] = None) -> List[ModuleElearning]:
    """Récupérer les modules e-learning"""
    query = select(ModuleElearning)
    
    if programme_id:
        query = query.where(ModuleElearning.programme_id == programme_id)
    
    if statut:
        query = query.where(ModuleElearning.statut == statut)
    
    if difficulte:
        query = query.where(ModuleElearning.difficulte == difficulte)
    
    # Filtrer par actif seulement si actif_only est True
    if actif_only:
        query = query.where(ModuleElearning.actif == True)
    
    query = query.order_by(ModuleElearning.ordre, ModuleElearning.titre)
    
    return session.exec(query).all()
```

**`create_ressource()`** :
```python
@staticmethod
def create_ressource(session: Session, ressource_data: RessourceElearningCreate, createur_id: int) -> RessourceElearning:
    """Créer une nouvelle ressource e-learning"""
    ressource = RessourceElearning(
        **ressource_data.dict(),
        cree_par_id=createur_id
    )
    session.add(ressource)
    session.commit()
    session.refresh(ressource)
    return ressource
```

**`add_ressource_to_module()`** :
```python
@staticmethod
def add_ressource_to_module(session: Session, module_id: int, ressource_id: int, ordre: int = 0, obligatoire: bool = True) -> bool:
    """Ajouter une ressource à un module"""
    try:
        module_ressource = ModuleRessource(
            module_id=module_id,
            ressource_id=ressource_id,
            ordre=ordre,
            obligatoire=obligatoire
        )
        session.add(module_ressource)
        session.commit()
        return True
    except Exception:
        session.rollback()
        return False
```

**`get_statistiques_programme()`** :
```python
@staticmethod
def get_statistiques_programme(session: Session, programme_id: int) -> StatistiquesElearningProgramme:
    """Obtenir les statistiques e-learning d'un programme"""
    programme = session.get(Programme, programme_id)
    if not programme:
        raise ValueError("Programme non trouvé")
    
    # Candidats inscrits au programme
    candidats_inscrits = session.exec(
        select(func.count(Inscription.id)).where(
            Inscription.programme_id == programme_id
        )
    ).first() or 0
    
    # Candidats actifs (ayant une progression)
    candidats_actifs = session.exec(
        select(func.count(func.distinct(ProgressionElearning.inscription_id))).where(
            ProgressionElearning.inscription_id.in_(
                select(Inscription.id).where(Inscription.programme_id == programme_id)
            )
        )
    ).first() or 0
    
    # Temps moyen - Calculer le temps total par candidat, puis la moyenne
    temps_par_candidat = session.exec(
        select(
            ProgressionElearning.inscription_id,
            func.sum(ProgressionElearning.temps_consacre_minutes).label('temps_total')
        ).where(
            ProgressionElearning.inscription_id.in_(
                select(Inscription.id).where(Inscription.programme_id == programme_id)
            )
        ).group_by(ProgressionElearning.inscription_id)
    ).all()
    
    # Calculer la moyenne des temps totaux
    if temps_par_candidat:
        temps_moyen = sum(t[1] for t in temps_par_candidat) / len(temps_par_candidat)
    else:
        temps_moyen = 0
    
    # Taux de completion
    modules_total = session.exec(
        select(func.count(ModuleElearning.id)).where(
            ModuleElearning.programme_id == programme_id
        )
    ).first() or 1
    
    modules_termines = session.exec(
        select(func.count(func.distinct(ProgressionElearning.module_id))).where(
            and_(
                ProgressionElearning.statut == "termine",
                ProgressionElearning.inscription_id.in_(
                    select(Inscription.id).where(Inscription.programme_id == programme_id)
                )
            )
        )
    ).first() or 0
    
    taux_completion = (modules_termines / modules_total) * 100 if modules_total > 0 else 0
    
    # Modules populaires
    modules_populaires = session.exec(
        select(
            ModuleElearning.titre,
            func.count(ProgressionElearning.id).label('participations')
        ).join(ProgressionElearning).where(
            ModuleElearning.programme_id == programme_id
        ).group_by(ModuleElearning.id).order_by(
            func.count(ProgressionElearning.id).desc()
        ).limit(5)
    ).all()
    
    return StatistiquesElearningProgramme(
        programme_id=programme_id,
        programme_nom=programme.nom,
        candidats_inscrits=candidats_inscrits,
        candidats_actifs=candidats_actifs,
        temps_moyen_minutes=float(temps_moyen) if temps_moyen else 0,
        taux_completion=taux_completion,
        modules_populaires=[{"titre": m[0], "participations": m[1]} for m in modules_populaires]
    )
```

**`get_statistiques_candidat()`** :
```python
@staticmethod
def get_statistiques_candidat(session: Session, inscription_id: int) -> StatistiquesElearningCandidat:
    """Obtenir les statistiques e-learning d'un candidat"""
    inscription = session.get(Inscription, inscription_id)
    if not inscription:
        raise ValueError("Inscription non trouvée")
    
    # Calculer les statistiques
    progressions = session.exec(
        select(ProgressionElearning).where(
            ProgressionElearning.inscription_id == inscription_id
        )
    ).all()
    
    temps_total = sum(p.temps_consacre_minutes for p in progressions)
    modules_termines = len(set(p.module_id for p in progressions if p.statut == "termine"))
    
    # Compter le nombre total de modules du programme
    modules_total = session.exec(
        select(func.count(ModuleElearning.id)).where(
            ModuleElearning.programme_id == inscription.programme_id
        )
    ).first() or 0
    
    # Calculer le score moyen
    scores = [p.score for p in progressions if p.score is not None]
    score_moyen = sum(scores) / len(scores) if scores else None
    
    # Dernière activité
    derniere_activite = max(
        (p.derniere_activite for p in progressions if p.derniere_activite),
        default=None
    )
    
    # Vérifier les objectifs
    objectifs = session.exec(
        select(ObjectifElearning).where(
            ObjectifElearning.programme_id == inscription.programme_id
        )
    ).all()
    
    objectif_atteint = all(
        ElearningService.check_objectif_atteint(session, inscription_id, obj.id)
        for obj in objectifs
    )
    
    return StatistiquesElearningCandidat(
        inscription_id=inscription_id,
        candidat_nom=f"{inscription.candidat.nom} {inscription.candidat.prenom}",
        programme_nom=inscription.programme.nom,
        temps_total_minutes=temps_total,
        modules_termines=modules_termines,
        modules_total=modules_total,
        score_moyen=score_moyen,
        derniere_activite=derniere_activite,
        objectif_atteint=objectif_atteint
    )
```

#### Fonctionnalités Avancées

**Gestion des ressources multimédias** :
- **Types multiples** : Vidéo, document, audio, lien
- **Upload de fichiers** : Gestion des fichiers multimédias
- **URLs externes** : Support des liens externes
- **Ordre et obligation** : Gestion de l'ordre et des ressources obligatoires

**Suivi de la progression** :
- **Statuts multiples** : Non commencé, en cours, terminé, abandonné
- **Temps de consultation** : Suivi du temps passé
- **Scores et notes** : Gestion des scores et notes personnelles
- **Dernière activité** : Traçabilité des activités

**Statistiques avancées** :
- **Métriques par programme** : Candidats inscrits, actifs, temps moyen
- **Taux de completion** : Pourcentage de modules terminés
- **Modules populaires** : Modules les plus consultés
- **Candidats actifs** : Candidats les plus engagés

**Gestion des objectifs** :
- **Objectifs obligatoires** : Temps minimum requis
- **Modules obligatoires** : Modules à compléter obligatoirement
- **Vérification automatique** : Contrôle de l'atteinte des objectifs

---

## 4. VALIDATION ET SÉCURITÉ

### 4.1 Contrôle d'Accès

**Rôles autorisés** :
- **Administrateur** : Accès complet
- **Responsable programme** : Accès complet
- **Formateur** : Création et modification des modules/ressources

**Vérifications systématiques** :
```python
if current_user.role not in ["administrateur", "responsable_programme", "formateur"]:
    raise HTTPException(status_code=403, detail="Accès refusé")
```

### 4.2 Validation des Données

**Validation côté serveur** :
- **Champs obligatoires** : Titre, programme pour les modules
- **Types de contenu** : Détection automatique du type de ressource
- **Upload de fichiers** : Validation des types MIME et tailles
- **Conversion des types** : Entiers, booléens, dates

**Validation côté client** :
- **Champs requis** : Validation HTML5 et JavaScript
- **Types de fichiers** : Validation des extensions
- **Confirmation des actions** : Prompts de confirmation

### 4.3 Sécurité des Accès

**Contrôles de sécurité** :
- **Authentification** : Vérification de l'utilisateur connecté
- **Autorisation** : Vérification des droits d'accès
- **Validation des données** : Contrôles sur les entrées
- **Gestion d'erreurs** : Try/catch avec rollback

**Protection des données** :
- **Isolation des données** : Accès limité aux modules autorisés
- **Validation des relations** : Vérification des liens entre entités
- **Logs des actions** : Traçabilité des créations et modifications

---

## 5. PERFORMANCE ET OPTIMISATION

### 5.1 Optimisation des Requêtes

**Jointures optimisées** :
- **Modules + Ressources** : Une seule requête pour les détails
- **Progression + Statistiques** : Calculs en base de données
- **Évitement des N+1** : Chargement en lot des relations

**Cache et sessions** :
- **Sessions de base de données** : Pool de connexions
- **Transactions atomiques** : Rollback en cas d'erreur
- **Refresh automatique** : Récupération des IDs générés

### 5.2 Gestion des Fichiers

**Upload optimisé** :
- **Types multiples** : Gestion des différents types de médias
- **Chemins organisés** : Structure de dossiers logique
- **Nettoyage automatique** : Suppression des fichiers en cas d'erreur
- **Validation des types** : Vérification des types MIME

---

## 6. MONITORING ET LOGS

### 6.1 Logs de Debug

**Informations loggées** :
- **Actions utilisateur** : Création, modification, suppression
- **Upload de fichiers** : Succès et échecs d'upload
- **Calculs statistiques** : Métriques et KPIs
- **Progression** : Suivi des activités des candidats

### 6.2 Métriques de Performance

**KPI calculés** :
- **Total des modules** : Comptage global
- **Répartition par type** : Vidéos, documents, audio, liens
- **Taux de completion** : Pourcentage de modules terminés
- **Temps moyen** : Temps de consultation moyen

---

## 7. ÉVOLUTION ET MAINTENANCE

### 7.1 Ajout de Nouveaux Types de Ressources

**Processus d'ajout** :
1. **Modification du modèle** : Ajout du nouveau type dans RessourceElearning
2. **Mise à jour du service** : Adaptation du service de ressources
3. **Mise à jour de l'interface** : Ajout dans les formulaires
4. **Tests** : Validation avec des cas de test

### 7.2 Modification des Statuts

**Processus de modification** :
1. **Mise à jour de l'enum** : Modification des statuts
2. **Mise à jour de la logique** : Adaptation des transitions
3. **Mise à jour de l'interface** : Adaptation des formulaires
4. **Migration des données** : Mise à jour des données existantes

---

*Document généré automatiquement - Pipeline de gestion de l'e-learning LIA WEB*
