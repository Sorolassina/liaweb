# Documentation des Routes Administratives - Pipeline Complet

## Vue d'ensemble
Ce document détaille le pipeline complet des routes administratives de l'application LIA Coaching, depuis les templates jusqu'aux modèles de données.

## Structure du Pipeline
```
Template HTML → Route FastAPI → Calcul Variables → Modèles SQLModel → Validation Schématique → Affichage Template
```

---

## 1. DASHBOARD ADMIN (`admin/dashboard.html`)

### Template Source
- **Fichier** : `app/templates/admin/dashboard.html`
- **Template parent** : `admin/base_admin.html`
- **Navigation** : Barre latérale avec 11 liens administratifs

### Pipeline Complet

#### 1.1 Route Principale : `/admin` (Dashboard)
- **Route** : `@router.get("/", name="admin_dashboard")`
- **Fichier** : `app/routers/ACD/admin.py:93-144`
- **Méthode** : `admin_dashboard()`

**Pipeline détaillé :**

1. **Authentification & Autorisation**
   - `get_current_user()` → Validation du token JWT
   - Vérification du rôle : `ADMINISTRATEUR` ou `DIRECTEUR_TECHNIQUE`
   - Si non autorisé → `HTTPException(403)`

2. **Calcul des KPIs**
   ```python
   # Interrogation des modèles
   nb_prog = session.exec(select(func.count()).select_from(Programme)).one()
   nb_pre = session.exec(select(func.count()).select_from(Preinscription)).one()
   nb_insc = session.exec(select(func.count()).select_from(Inscription)).one()
   nb_jury = session.exec(select(func.count()).select_from(Jury)).one()
   ```

3. **Récupération des utilisateurs**
   ```python
   all_users = session.exec(select(User)).all()
   users_data = [UserResponse.from_orm(user) for user in all_users]
   ```

4. **Variables transmises au template**
   ```python
   {
       "request": request,
       "titre": "Administration",
       "utilisateur": UserResponse.from_orm(current_user),
       "roles": [current_user.role],
       "kpi": {
           "programmes": nb_prog,
           "preinscriptions": nb_pre,
           "inscriptions": nb_insc,
           "jurys": nb_jury,
       },
       "users": users_data,
       "app_name": settings.APP_NAME,
       "version": settings.VERSION,
       "author": settings.AUTHOR,
       "current_year": datetime.now().year,
       "settings": settings
   }
   ```

5. **Affichage** : `templates.TemplateResponse("admin/dashboard.html", context)`

#### 1.2 Route Alternative : `/admin/home`
- **Route** : `@router.get("/home", name="admin_home")`
- **Fichier** : `app/routers/ACD/admin.py:146-183`
- **Méthode** : `admin_home()`

**Pipeline détaillé :**

1. **Calcul des totaux**
   ```python
   total_prog = session.exec(select(func.count(Programme.id))).one() or 0
   total_pre = session.exec(select(func.count(Preinscription.id))).one() or 0
   total_insc = session.exec(select(func.count(Inscription.id))).one() or 0
   total_users = session.exec(select(func.count(User.id))).one() or 0
   ```

2. **Récupération des jurys à venir**
   ```python
   jurys_next = session.exec(
       select(Jury)
       .where(Jury.session_le >= datetime.now(timezone.utc))
       .order_by(Jury.session_le)
   ).all()
   ```

3. **Statistiques par programme**
   ```python
   insc_by_prog = session.exec(
       select(Programme.code, func.count(Inscription.id))
       .join(Inscription, isouter=True)
       .group_by(Programme.code)
       .order_by(Programme.code)
   ).all()
   ```

4. **Variables transmises**
   ```python
   {
       "request": request,
       "settings": settings,
       "utilisateur": current_user,
       "kpi": {
           "programmes": int(total_prog),
           "preinscriptions": int(total_pre),
           "inscriptions": int(total_insc),
           "utilisateurs": int(total_users),
       },
       "jurys_next": jurys_next,
       "insc_by_prog": insc_by_prog,
   }
   ```

### Modèles Interrogés
- `Programme` : Comptage des programmes actifs
- `Preinscription` : Comptage des préinscriptions
- `Inscription` : Comptage des inscriptions
- `Jury` : Comptage des jurys + récupération des prochains
- `User` : Comptage des utilisateurs + liste complète

### Schémas de Validation
- `UserResponse` : Validation et sérialisation des données utilisateur
- Validation des rôles via `UserRole` enum

### Template Rendering
- **Template principal** : `admin/dashboard.html`
- **Template parent** : `admin/base_admin.html`
- **Scripts** : Chart.js pour les graphiques
- **Données affichées** :
  - KPIs en cartes (programmes, préinscriptions, inscriptions, utilisateurs)
  - Graphique en barres des inscriptions par programme
  - Liste des jurys à venir

### Navigation Disponible
Depuis le dashboard, les utilisateurs peuvent accéder à :
1. **Programmes** → `admin_programmes`
2. **Utilisateurs** → `admin_users`
3. **Partenaires** → `admin_partenaires`
4. **Promotions** → `admin_promotions`
5. **Groupes** → `admin_groupes`
6. **Jurys** → `admin_jurys`
7. **Traçabilité** → `admin_logs`
8. **Permissions** → `admin_permissions`
9. **Archives** → `admin_archives`
10. **Base de données** → `admin_database_status`
11. **Paramètres** → `admin_settings`

---

## 2. PROGRAMMES (`admin/programmes_list.html`)

### Template Source
- **Fichier** : `app/templates/admin/programmes_list.html`
- **Template parent** : `admin/base_admin.html`
- **Fonctionnalités** : Liste des programmes avec gestion d'équipe et étapes

### Pipeline Complet

#### 2.1 Route Principale : `/admin/programmes` (Liste)
- **Route** : `@router.get("/programmes", name="admin_programmes")`
- **Fichier** : `app/routers/ACD/admin.py:186-236`
- **Méthode** : `admin_programmes()`

**Pipeline détaillé :**

1. **Authentification & Autorisation**
   - `admin_required(current_user)` → Validation du rôle admin
   - Si non autorisé → `HTTPException(403)`

2. **Récupération des programmes**
   ```python
   progs = session.exec(select(Programme).order_by(Programme.code)).all()
   ```

3. **Récupération des utilisateurs actifs**
   ```python
   users = session.exec(select(User).where(User.actif == True).order_by(User.nom_complet)).all()
   ```

4. **Enrichissement des programmes avec leurs équipes**
   ```python
   for prog in progs:
       prog.utilisateurs = session.exec(
           select(ProgrammeUtilisateur)
           .where(ProgrammeUtilisateur.programme_id == prog.id)
           .order_by(ProgrammeUtilisateur.role_programme)
       ).all()
   ```

5. **Calcul des données pour les modals**
   ```python
   # Utilisateurs disponibles par programme (excluant responsables et membres existants)
   users_disponibles_par_programme = {}
   membres_equipe_par_programme = {}
   etapes_par_programme = {}
   
   for prog in progs:
       # Exclusion des utilisateurs déjà assignés
       excluded_user_ids = {prog.responsable_id} if prog.responsable_id else set()
       excluded_user_ids.update(pu.utilisateur_id for pu in prog.utilisateurs)
       
       users_disponibles_par_programme[prog.id] = [
           user for user in users if user.id not in excluded_user_ids
       ]
       
       # Conversion des membres pour JSON
       membres_equipe_par_programme[prog.id] = [
           {
               "utilisateur_id": pu.utilisateur_id,
               "role_programme": pu.role_programme.value if hasattr(pu.role_programme, 'value') else str(pu.role_programme)
           }
           for pu in prog.utilisateurs
       ]
       
       # Récupération des étapes du pipeline
       etapes_par_programme[prog.id] = session.exec(
           select(EtapePipeline)
           .where(EtapePipeline.programme_id == prog.id)
           .order_by(EtapePipeline.ordre)
       ).all()
   ```

6. **Variables transmises au template**
   ```python
   {
       "request": request,
       "settings": settings,
       "utilisateur": current_user,
       "progs": progs,
       "users": users,
       "users_disponibles_par_programme": users_disponibles_par_programme,
       "membres_equipe_par_programme": membres_equipe_par_programme,
       "etapes_par_programme": etapes_par_programme,
       "UserRole": UserRoleEnum,
       "timestamp": timestamp
   }
   ```

#### 2.2 Route Création : `/admin/programmes/new`
- **Route** : `@router.get("/programmes/new")`
- **Fichier** : `app/routers/ACD/admin.py:238-257`
- **Méthode** : `admin_programme_new()`

**Pipeline détaillé :**
1. **Authentification** : `admin_required(current_user)`
2. **Récupération des utilisateurs** : `select(User).where(User.actif == True)`
3. **Affichage** : Template `admin/programme_form.html`

#### 2.3 Route Édition : `/admin/programmes/{prog_id}`
- **Route** : `@router.get("/programmes/{prog_id}")`
- **Fichier** : `app/routers/ACD/admin.py:259-290`
- **Méthode** : `admin_programme_edit()`

**Pipeline détaillé :**
1. **Authentification** : `admin_required(current_user)`
2. **Récupération du programme** : `session.get(Programme, prog_id)`
3. **Récupération des étapes** : `select(EtapePipeline).where(EtapePipeline.programme_id == prog.id)`
4. **Filtrage des responsables disponibles** : Exclusion des responsables existants
5. **Récupération des utilisateurs du programme** : `select(ProgrammeUtilisateur)`

#### 2.4 Routes POST (Actions)

##### 2.4.1 Sauvegarde Programme : `/admin/programmes/save`
- **Route** : `@router.post("/programmes/save")`
- **Fichier** : `app/routers/ACD/admin.py:292-381`
- **Méthode** : `admin_programme_save()`

**Pipeline détaillé :**
1. **Validation des données** : Form fields (code, nom, objectif, dates, etc.)
2. **Création ou mise à jour** : `Programme` model
3. **Gestion des dates** : Conversion string → datetime
4. **Redirection** : `RedirectResponse` avec paramètres de succès

##### 2.4.2 Ajout d'Étape : `/admin/programmes/{prog_id}/etapes/add`
- **Route** : `@router.post("/programmes/{prog_id}/etapes/add")`
- **Fichier** : `app/routers/ACD/admin.py:465-523`
- **Méthode** : `admin_programme_add_step()`

**Pipeline détaillé :**
1. **Validation** : `admin_required(current_user)`
2. **Récupération du programme** : `session.get(Programme, prog_id)`
3. **Création de l'étape** : `EtapePipeline` model
4. **Redirection** : Retour vers la liste avec paramètres de succès

##### 2.4.3 Ajout d'Utilisateur : `/admin/programmes/{prog_id}/utilisateurs/add`
- **Route** : `@router.post("/programmes/{prog_id}/utilisateurs/add")`
- **Fichier** : `app/routers/ACD/admin.py:524-560`
- **Méthode** : `admin_programme_add_user()`

**Pipeline détaillé :**
1. **Validation** : `admin_required(current_user)`
2. **Récupération du programme** : `session.get(Programme, prog_id)`
3. **Création de l'association** : `ProgrammeUtilisateur` model
4. **Redirection** : Retour vers la liste avec paramètres de succès

##### 2.4.4 Suppression d'Utilisateur : `/admin/programmes/{prog_id}/utilisateurs/{user_id}/delete`
- **Route** : `@router.post("/programmes/{prog_id}/utilisateurs/{user_id}/delete")`
- **Fichier** : `app/routers/ACD/admin.py:561-580`
- **Méthode** : `admin_programme_remove_user()`

**Pipeline détaillé :**
1. **Validation** : `admin_required(current_user)`
2. **Récupération de l'association** : `select(ProgrammeUtilisateur)`
3. **Suppression** : `session.delete(pu)`
4. **Redirection** : Retour vers la liste avec paramètres de succès

### Modèles Interrogés
- `Programme` : Liste des programmes avec leurs détails
- `User` : Utilisateurs actifs pour les dropdowns
- `ProgrammeUtilisateur` : Associations programme-utilisateur
- `EtapePipeline` : Étapes du pipeline par programme

### Schémas de Validation
- `UserRole` enum : Validation des rôles utilisateur
- Form validation : Validation des champs obligatoires
- Type conversion : String → datetime pour les dates

### Template Rendering
- **Template principal** : `admin/programmes_list.html`
- **Template parent** : `admin/base_admin.html`
- **Fonctionnalités affichées** :
  - Tableau des programmes avec statut et responsable
  - Modals de visualisation des détails
  - Modals de gestion d'équipe (ajout/suppression d'utilisateurs)
  - Modals de gestion des étapes (ajout/suppression d'étapes)
  - Modals de confirmation de suppression
  - Notifications de succès/erreur

### Actions Disponibles
1. **Voir les détails** → Modal avec informations complètes
2. **Modifier** → Redirection vers formulaire d'édition
3. **Gérer l'équipe** → Modal avec ajout/suppression d'utilisateurs
4. **Gérer les étapes** → Modal avec ajout/suppression d'étapes
5. **Supprimer** → Modal de confirmation avec suppression définitive

### Navigation Disponible
- **Nouveau programme** → `admin_programmes_new`
- **Retour au dashboard** → `admin_dashboard`

---

## 3. UTILISATEURS (`admin/users.html`)

### Template Source
- **Fichier** : `app/templates/admin/users.html`
- **Template parent** : `admin/base_admin.html`
- **Fonctionnalités** : Gestion complète des utilisateurs avec CRUD et upload de photos

### Pipeline Complet

#### 3.1 Route Principale : `/admin/users` (Liste)
- **Route** : `@router.get("/users", name="admin_users")`
- **Fichier** : `app/routers/ACD/admin.py:587-607`
- **Méthode** : `admin_users()`

**Pipeline détaillé :**

1. **Authentification & Autorisation**
   - `admin_required(current_user)` → Validation du rôle admin
   - Si non autorisé → `HTTPException(403)`

2. **Recherche optionnelle**
   ```python
   stmt = select(User)
   if q:  # Paramètre de recherche
       like = f"%{q}%"
       stmt = stmt.where((User.email.ilike(like)) | (User.nom_complet.ilike(like)))
   ```

3. **Récupération des utilisateurs**
   ```python
   users = session.exec(stmt.order_by(User.cree_le.desc())).all()
   ```

4. **Génération du timestamp pour cache-busting**
   ```python
   timestamp = int(datetime.now(timezone.utc).timestamp())
   ```

5. **Variables transmises au template**
   ```python
   {
       "request": request,
       "settings": settings,
       "utilisateur": current_user,
       "users": users,
       "UserRole": UserRoleEnum,
       "q": q or "",
       "timestamp": timestamp
   }
   ```

#### 3.2 Route Création : `/admin/users/add`
- **Route** : `@router.post("/users/add", name="admin_users_add")`
- **Fichier** : `app/routers/ACD/admin.py:609-675`
- **Méthode** : `admin_users_add()`

**Pipeline détaillé :**

1. **Validation des données**
   ```python
   email: str = Form(...)
   nom_complet: str = Form(...)
   telephone: Optional[str] = Form(None)
   role: str = Form(...)
   type_utilisateur: str = Form("INTERNE")
   mot_de_passe: Optional[str] = Form(None)
   photo_profil: UploadFile | None = File(None)
   ```

2. **Vérification de l'unicité de l'email**
   ```python
   if session.exec(select(User).where(User.email==email)).first():
       raise HTTPException(status_code=400, detail="Email déjà utilisé")
   ```

3. **Validation et conversion du rôle**
   ```python
   # Chercher le rôle par sa valeur au lieu de son nom
   r = None
   for enum_role in UserRoleEnum:
       if enum_role.value == role:
           r = enum_role
           break
   
   if not r:
       r = UserRoleEnum.CONSEILLER.value  # Valeur par défaut
   
   role_value = r.value
   ```

4. **Validation du type d'utilisateur**
   ```python
   try: 
       t = getattr(TypeUtilisateur, type_utilisateur)
   except Exception: 
       t = TypeUtilisateur.INTERNE
   ```

5. **Gestion du mot de passe**
   ```python
   password = mot_de_passe if mot_de_passe else "ChangeMe123!"
   ```

6. **Création de l'utilisateur**
   ```python
   u = User(
       email=email,
       nom_complet=nom_complet,
       telephone=telephone,
       role=role_value,
       type_utilisateur=t,
       mot_de_passe_hash=get_password_hash(password)
   )
   session.add(u)
   session.flush()  # Pour obtenir l'ID de l'utilisateur
   ```

7. **Upload de la photo de profil**
   ```python
   if photo_profil:
       # Utilisation du FileUploadService pour sauvegarder l'image
       # Génération du chemin et sauvegarde
   ```

8. **Redirection avec paramètres de succès**
   ```python
   return RedirectResponse(url=f"/admin/users?success=1&action=add&t={timestamp}", status_code=303)
   ```

#### 3.3 Route Mise à jour : `/admin/users/{uid}/update`
- **Route** : `@router.post("/users/{uid}/update", name="admin_users_update")`
- **Fichier** : `app/routers/ACD/admin.py:689-737`
- **Méthode** : `admin_users_update()`

**Pipeline détaillé :**

1. **Validation** : `admin_required(current_user)`
2. **Récupération de l'utilisateur** : `session.get(User, uid)`
3. **Mise à jour des champs** : Modification des données utilisateur
4. **Gestion du mot de passe** : Hashage si fourni
5. **Log d'activité** : `log_activity()` pour traçabilité
6. **Redirection** : Retour vers la liste avec paramètres de succès

#### 3.4 Route Toggle Statut : `/admin/users/{uid}/toggle`
- **Route** : `@router.post("/users/{uid}/toggle", name="admin_users_toggle")`
- **Fichier** : `app/routers/ACD/admin.py:676-687`
- **Méthode** : `admin_users_toggle()`

**Pipeline détaillé :**

1. **Validation** : `admin_required(current_user)`
2. **Récupération de l'utilisateur** : `session.get(User, uid)`
3. **Inversion du statut** : `u.actif = not bool(u.actif)`
4. **Log d'activité** : `log_activity()` avec données de l'action
5. **Commit** : `session.commit()`
6. **Redirection** : Retour vers la liste avec paramètres de succès

#### 3.5 Route Upload Photo : `/admin/users/{uid}/photo`
- **Route** : `@router.post("/users/{uid}/photo", name="admin_users_photo")`
- **Fichier** : `app/routers/ACD/admin.py:1338-1383`
- **Méthode** : `admin_users_photo()`

**Pipeline détaillé :**

1. **Validation** : `admin_required(current_user)`
2. **Récupération de l'utilisateur** : `session.get(User, uid)`
3. **Validation du fichier** : Vérification du type et taille
4. **Upload via FileUploadService** : Sauvegarde sécurisée de l'image
5. **Mise à jour du chemin** : `u.photo_profil = file_path`
6. **Log d'activité** : `log_activity()` pour traçabilité
7. **Redirection** : Retour vers la liste avec paramètres de succès

#### 3.6 Route Suppression : `/admin/users/{uid}/delete`
- **Route** : `@router.post("/users/{uid}/delete", name="admin_users_delete")`
- **Fichier** : `app/routers/ACD/admin.py:1384-1420`
- **Méthode** : `admin_users_delete()`

**Pipeline détaillé :**

1. **Validation** : `admin_required(current_user)`
2. **Récupération de l'utilisateur** : `session.get(User, uid)`
3. **Suppression de la photo** : Nettoyage du fichier image
4. **Log d'activité** : `log_activity()` avant suppression
5. **Suppression de l'utilisateur** : `session.delete(u)`
6. **Commit** : `session.commit()`
7. **Redirection** : Retour vers la liste avec paramètres de succès

### Modèles Interrogés
- `User` : Gestion complète des utilisateurs
- `TypeUtilisateur` : Enum pour les types (INTERNE/EXTERNE)
- `UserRole` : Enum pour les rôles utilisateur

### Schémas de Validation
- `UserRole` enum : Validation des rôles utilisateur
- `TypeUtilisateur` enum : Validation des types utilisateur
- Form validation : Validation des champs obligatoires
- Email uniqueness : Vérification de l'unicité de l'email
- File validation : Validation des images uploadées

### Template Rendering
- **Template principal** : `admin/users.html`
- **Template parent** : `admin/base_admin.html`
- **Fonctionnalités affichées** :
  - Formulaire de création d'utilisateur (collapsible)
  - Tableau des utilisateurs avec photos de profil
  - Modals d'édition des utilisateurs
  - Modals de changement de photo de profil
  - Modals de confirmation de suppression
  - Boutons de toggle statut (actif/inactif)
  - Barre de recherche par nom/email
  - Notifications de succès/erreur

### Actions Disponibles
1. **Ajouter un utilisateur** → Formulaire collapsible avec upload photo
2. **Modifier** → Modal avec formulaire d'édition
3. **Changer la photo** → Modal avec upload d'image
4. **Activer/Désactiver** → Toggle du statut actif
5. **Supprimer** → Modal de confirmation avec suppression définitive
6. **Rechercher** → Filtrage par nom ou email

### Fonctionnalités Avancées
- **Upload de photos** : Gestion sécurisée des images avec FileUploadService
- **Cache-busting** : Timestamp pour éviter les problèmes de cache
- **Log d'activité** : Traçabilité de toutes les actions
- **Validation robuste** : Vérification de l'unicité email et validation des fichiers
- **Gestion des erreurs** : Messages d'erreur contextuels
- **Interface responsive** : Modals et formulaires adaptatifs

### Navigation Disponible
- **Retour au dashboard** → `admin_dashboard`
- **Recherche** → Filtrage en temps réel

---

## 4. PARTENAIRES (`admin/partenaires.html`)

### Template Source
- **Fichier** : `app/templates/admin/partenaires.html`
- **Template parent** : `admin/base_admin.html`
- **Fonctionnalités** : Gestion complète des partenaires avec CRUD et recherche

### Pipeline Complet

#### 4.1 Route Principale : `/admin/partenaires` (Liste)
- **Route** : `@router.get("/partenaires", name="admin_partenaires")`
- **Fichier** : `app/routers/ACD/admin.py:1494-1509`
- **Méthode** : `admin_partenaires()`

**Pipeline détaillé :**

1. **Authentification & Autorisation**
   - `admin_required(current_user)` → Validation du rôle admin
   - Si non autorisé → `HTTPException(403)`

2. **Recherche optionnelle**
   ```python
   stmt = select(Partenaire)
   if q:  # Paramètre de recherche
       like = f"%{q}%"
       stmt = stmt.where(
           (Partenaire.nom.ilike(like)) | 
           (Partenaire.email.ilike(like)) | 
           (Partenaire.description.ilike(like))
       )
   ```

3. **Récupération des partenaires**
   ```python
   partenaires = session.exec(stmt.order_by(Partenaire.nom)).all()
   ```

4. **Variables transmises au template**
   ```python
   {
       "request": request,
       "settings": settings,
       "utilisateur": current_user,
       "partenaires": partenaires,
       "q": q or ""
   }
   ```

#### 4.2 Route Création : `/admin/partenaires/add`
- **Route** : `@router.post("/partenaires/add")`
- **Fichier** : `app/routers/ACD/admin.py:1511-1548`
- **Méthode** : `admin_partenaires_add()`

**Pipeline détaillé :**

1. **Validation des données**
   ```python
   nom: str = Form(...)
   description: Optional[str] = Form(None)
   email: Optional[str] = Form(None)
   telephone: Optional[str] = Form(None)
   adresse: Optional[str] = Form(None)
   site_web: Optional[str] = Form(None)
   specialites: Optional[str] = Form(None)
   actif: Literal["on", "off", ""] = Form("on")
   ```

2. **Vérification de l'unicité du nom**
   ```python
   existing = session.exec(select(Partenaire).where(Partenaire.nom == nom.strip())).first()
   if existing:
       raise HTTPException(status_code=400, detail="Un partenaire avec ce nom existe déjà")
   ```

3. **Création du partenaire**
   ```python
   partenaire = Partenaire(
       nom=nom.strip(),
       description=description.strip() if description else None,
       email=email.strip() if email else None,
       telephone=telephone.strip() if telephone else None,
       adresse=adresse.strip() if adresse else None,
       site_web=site_web.strip() if site_web else None,
       specialites=specialites.strip() if specialites else None,
       actif=(actif != "off")
   )
   session.add(partenaire)
   ```

4. **Log d'activité**
   ```python
   log_activity(session, user=current_user, action="PARTENAIRE_CREATE", 
               entity="Partenaire", entity_id=partenaire.id,
               activity_data={"nom": partenaire.nom, "email": partenaire.email}, 
               request=request)
   ```

5. **Commit et redirection**
   ```python
   session.commit()
   return RedirectResponse(url=f"/admin/partenaires?success=1&action=add&t={timestamp}", status_code=303)
   ```

#### 4.3 Route Mise à jour : `/admin/partenaires/{partenaire_id}/update`
- **Route** : `@router.post("/partenaires/{partenaire_id}/update")`
- **Fichier** : `app/routers/ACD/admin.py:1550-1612`
- **Méthode** : `admin_partenaires_update()`

**Pipeline détaillé :**

1. **Validation** : `admin_required(current_user)`
2. **Récupération du partenaire** : `session.get(Partenaire, partenaire_id)`
3. **Vérification de l'unicité du nom** : Exclusion du partenaire actuel
4. **Sauvegarde des anciennes valeurs** : Pour le log d'activité
5. **Mise à jour des champs** : Modification de toutes les propriétés
6. **Log d'activité** : `log_activity()` avec comparaison ancien/nouveau
7. **Redirection** : Retour vers la liste avec paramètres de succès

#### 4.4 Route Toggle Statut : `/admin/partenaires/{partenaire_id}/toggle`
- **Route** : `@router.post("/partenaires/{partenaire_id}/toggle")`
- **Fichier** : `app/routers/ACD/admin.py:1614-1627`
- **Méthode** : `admin_partenaires_toggle()`

**Pipeline détaillé :**

1. **Validation** : `admin_required(current_user)`
2. **Récupération du partenaire** : `session.get(Partenaire, partenaire_id)`
3. **Inversion du statut** : `partenaire.actif = not bool(partenaire.actif)`
4. **Log d'activité** : `log_activity()` avec données de l'action
5. **Commit** : `session.commit()`
6. **Redirection** : Retour vers la liste avec paramètres de succès

#### 4.5 Route Suppression : `/admin/partenaires/{partenaire_id}/delete`
- **Route** : `@router.post("/partenaires/{partenaire_id}/delete")`
- **Fichier** : `app/routers/ACD/admin.py:1629-1667`
- **Méthode** : `admin_partenaires_delete()`

**Pipeline détaillé :**

1. **Validation** : `admin_required(current_user)`
2. **Récupération du partenaire** : `session.get(Partenaire, partenaire_id)`
3. **Vérification des dépendances** : 
   ```python
   reorientations_count = session.exec(
       select(func.count(DecisionJuryCandidat.id))
       .where(DecisionJuryCandidat.partenaire_id == partenaire_id)
   ).first()
   ```
4. **Protection contre la suppression** : Si utilisé dans des réorientations
5. **Sauvegarde des informations** : Pour le log avant suppression
6. **Suppression sécurisée** : Try/catch avec rollback
7. **Log d'activité** : `log_activity()` avec données du partenaire supprimé
8. **Redirection** : Retour vers la liste avec paramètres de succès

### Modèles Interrogés
- `Partenaire` : Gestion complète des partenaires
- `DecisionJuryCandidat` : Vérification des dépendances pour la suppression

### Schémas de Validation
- Form validation : Validation des champs obligatoires
- Nom uniqueness : Vérification de l'unicité du nom
- Dependency check : Vérification des relations avant suppression
- Data sanitization : Nettoyage des chaînes avec `.strip()`

### Template Rendering
- **Template principal** : `admin/partenaires.html`
- **Template parent** : `admin/base_admin.html`
- **Fonctionnalités affichées** :
  - Formulaire de création de partenaire (collapsible)
  - Tableau des partenaires avec informations complètes
  - Modal d'édition des partenaires
  - Boutons de toggle statut (actif/inactif)
  - Boutons de suppression avec confirmation
  - Barre de recherche par nom/email/description
  - Liens cliquables (email, téléphone, site web)
  - Notifications de succès/erreur

### Actions Disponibles
1. **Ajouter un partenaire** → Formulaire collapsible avec tous les champs
2. **Modifier** → Modal avec formulaire d'édition pré-rempli
3. **Activer/Désactiver** → Toggle du statut actif
4. **Supprimer** → Confirmation avec vérification des dépendances
5. **Rechercher** → Filtrage par nom, email ou description

### Fonctionnalités Avancées
- **Recherche multi-champs** : Filtrage sur nom, email et description
- **Protection des données** : Vérification des dépendances avant suppression
- **Log d'activité complet** : Traçabilité de toutes les actions
- **Interface interactive** : Modals et formulaires dynamiques
- **Liens fonctionnels** : Email, téléphone et site web cliquables
- **Gestion des erreurs** : Messages contextuels avec détails
- **Validation robuste** : Vérification d'unicité et nettoyage des données

### Champs Gérés
- **Informations principales** : Nom, email, description
- **Contact** : Téléphone, site web, adresse
- **Spécialités** : Champ texte libre pour les compétences
- **Statut** : Actif/Inactif avec toggle
- **Métadonnées** : Date de création automatique

### Navigation Disponible
- **Retour au dashboard** → `admin_dashboard`
- **Recherche** → Filtrage en temps réel

---

## 5. PROMOTIONS (`admin/promotions.html`)

### Template Source
- **Fichier** : `app/templates/admin/promotions.html`
- **Template parent** : `admin/base_admin.html`
- **Fonctionnalités** : Gestion complète des promotions avec CRUD et relations programmes

### Pipeline Complet

#### 5.1 Route Principale : `/admin/promotions` (Liste)
- **Route** : `@router.get("/promotions", name="admin_promotions")`
- **Fichier** : `app/routers/ACD/admin.py:1670-1693`
- **Méthode** : `admin_promotions()`

**Pipeline détaillé :**

1. **Authentification & Autorisation**
   - `admin_required(current_user)` → Validation du rôle admin
   - Si non autorisé → `HTTPException(403)`

2. **Recherche optionnelle**
   ```python
   stmt = select(Promotion)
   if q:  # Paramètre de recherche
       like = f"%{q}%"
       stmt = stmt.where(Promotion.libelle.ilike(like))
   ```

3. **Récupération des promotions**
   ```python
   promotions = session.exec(stmt.order_by(Promotion.libelle)).all()
   ```

4. **Enrichissement avec les relations programme**
   ```python
   for promo in promotions:
       promo.programme = session.get(Programme, promo.programme_id)
   ```

5. **Récupération des programmes pour les dropdowns**
   ```python
   programmes = session.exec(select(Programme).order_by(Programme.code)).all()
   ```

6. **Variables transmises au template**
   ```python
   {
       "request": request,
       "settings": settings,
       "utilisateur": current_user,
       "promotions": promotions,
       "programmes": programmes,
       "q": q or ""
   }
   ```

#### 5.2 Route Création : `/admin/promotions/add`
- **Route** : `@router.post("/promotions/add")`
- **Fichier** : `app/routers/ACD/admin.py:1695-1736`
- **Méthode** : `admin_promotions_add()`

**Pipeline détaillé :**

1. **Validation des données**
   ```python
   programme_id: int = Form(...)
   libelle: str = Form(...)
   capacite: Optional[str] = Form(None)
   date_debut: Optional[str] = Form(None)
   date_fin: Optional[str] = Form(None)
   actif: Literal["on", "off", ""] = Form("on")
   ```

2. **Vérification de l'existence du programme**
   ```python
   programme = session.get(Programme, programme_id)
   if not programme:
       raise HTTPException(status_code=400, detail="Programme introuvable")
   ```

3. **Vérification de l'unicité du libellé par programme**
   ```python
   existing = session.exec(select(Promotion).where(
       Promotion.programme_id == programme_id,
       Promotion.libelle == libelle.strip()
   )).first()
   if existing:
       raise HTTPException(status_code=400, detail="Une promotion avec ce libellé existe déjà pour ce programme")
   ```

4. **Création de la promotion**
   ```python
   promotion = Promotion(
       programme_id=programme_id,
       libelle=libelle.strip(),
       capacite=int(capacite) if capacite and capacite.strip().isdigit() else None,
       date_debut=datetime.fromisoformat(date_debut).date() if date_debut else None,
       date_fin=datetime.fromisoformat(date_fin).date() if date_fin else None,
       actif=(actif != "off")
   )
   session.add(promotion)
   ```

5. **Log d'activité**
   ```python
   log_activity(session, user=current_user, action="PROMOTION_CREATE", 
               entity="Promotion", entity_id=promotion.id,
               activity_data={"libelle": promotion.libelle, "programme_id": programme_id}, 
               request=request)
   ```

6. **Commit et redirection**
   ```python
   session.commit()
   return RedirectResponse(url=f"/admin/promotions?success=1&action=add&t={timestamp}", status_code=303)
   ```

#### 5.3 Route Mise à jour : `/admin/promotions/{promotion_id}/update`
- **Route** : `@router.post("/promotions/{promotion_id}/update")`
- **Fichier** : `app/routers/ACD/admin.py:1738-1801`
- **Méthode** : `admin_promotions_update()`

**Pipeline détaillé :**

1. **Validation** : `admin_required(current_user)`
2. **Récupération de la promotion** : `session.get(Promotion, promotion_id)`
3. **Vérification du programme** : Validation de l'existence du programme
4. **Vérification de l'unicité** : Exclusion de la promotion actuelle
5. **Sauvegarde des anciennes valeurs** : Pour le log d'activité
6. **Mise à jour des champs** : Modification de toutes les propriétés
7. **Log d'activité** : `log_activity()` avec comparaison ancien/nouveau
8. **Redirection** : Retour vers la liste avec paramètres de succès

#### 5.4 Route Toggle Statut : `/admin/promotions/{promotion_id}/toggle`
- **Route** : `@router.post("/promotions/{promotion_id}/toggle")`
- **Fichier** : `app/routers/ACD/admin.py:1803-1816`
- **Méthode** : `admin_promotions_toggle()`

**Pipeline détaillé :**

1. **Validation** : `admin_required(current_user)`
2. **Récupération de la promotion** : `session.get(Promotion, promotion_id)`
3. **Inversion du statut** : `promotion.actif = not bool(promotion.actif)`
4. **Log d'activité** : `log_activity()` avec données de l'action
5. **Commit** : `session.commit()`
6. **Redirection** : Retour vers la liste avec paramètres de succès

#### 5.5 Route Suppression : `/admin/promotions/{promotion_id}/delete`
- **Route** : `@router.post("/promotions/{promotion_id}/delete")`
- **Fichier** : `app/routers/ACD/admin.py:1818-1864`
- **Méthode** : `admin_promotions_delete()`

**Pipeline détaillé :**

1. **Validation** : `admin_required(current_user)`
2. **Récupération de la promotion** : `session.get(Promotion, promotion_id)`
3. **Vérification des dépendances - Inscriptions** : 
   ```python
   inscriptions_count = session.exec(
       select(func.count(Inscription.id))
       .where(Inscription.promotion_id == promotion_id)
   ).first()
   ```
4. **Vérification des dépendances - Jurys** :
   ```python
   jurys_count = session.exec(
       select(func.count(Jury.id))
       .where(Jury.promotion_id == promotion_id)
   ).first()
   ```
5. **Protection contre la suppression** : Si utilisée dans des inscriptions ou jurys
6. **Sauvegarde des informations** : Pour le log avant suppression
7. **Suppression sécurisée** : Try/catch avec rollback
8. **Log d'activité** : `log_activity()` avec données de la promotion supprimée
9. **Redirection** : Retour vers la liste avec paramètres de succès

### Modèles Interrogés
- `Promotion` : Gestion complète des promotions
- `Programme` : Relations et validation des programmes
- `Inscription` : Vérification des dépendances pour la suppression
- `Jury` : Vérification des dépendances pour la suppression

### Schémas de Validation
- Form validation : Validation des champs obligatoires
- Programme existence : Vérification de l'existence du programme
- Libellé uniqueness : Vérification de l'unicité du libellé par programme
- Dependency check : Vérification des relations avant suppression
- Date conversion : Conversion string → date pour les dates
- Data sanitization : Nettoyage des chaînes avec `.strip()`

### Template Rendering
- **Template principal** : `admin/promotions.html`
- **Template parent** : `admin/base_admin.html`
- **Fonctionnalités affichées** :
  - Modal de création de promotion avec dropdown programme
  - Tableau des promotions avec informations complètes
  - Modals d'édition des promotions (un par promotion)
  - Boutons de toggle statut (actif/inactif)
  - Boutons de suppression avec confirmation
  - Affichage des relations programme
  - Informations de capacité et période
  - Notifications de succès/erreur

### Actions Disponibles
1. **Ajouter une promotion** → Modal avec formulaire et dropdown programme
2. **Modifier** → Modal avec formulaire d'édition pré-rempli
3. **Activer/Désactiver** → Toggle du statut actif
4. **Supprimer** → Confirmation avec vérification des dépendances
5. **Rechercher** → Filtrage par libellé

### Fonctionnalités Avancées
- **Recherche par libellé** : Filtrage sur le nom de la promotion
- **Protection des données** : Vérification des dépendances avant suppression
- **Log d'activité complet** : Traçabilité de toutes les actions
- **Interface modale** : Création et édition via modals
- **Relations programmes** : Affichage des informations du programme associé
- **Gestion des dates** : Conversion et affichage des dates de début/fin
- **Validation robuste** : Vérification d'unicité et existence des programmes

### Champs Gérés
- **Informations principales** : Libellé, programme associé
- **Capacité** : Nombre de places disponibles
- **Période** : Dates de début et fin
- **Statut** : Actif/Inactif avec toggle
- **Métadonnées** : ID et relations automatiques

### Relations et Dépendances
- **Programme** : Chaque promotion est liée à un programme
- **Inscriptions** : Vérification avant suppression
- **Jurys** : Vérification avant suppression
- **Unicité** : Libellé unique par programme

### Navigation Disponible
- **Retour au dashboard** → `admin_dashboard`
- **Recherche** → Filtrage en temps réel

---

## 6. GROUPES (`admin/groupes.html`)

### Template Source
- **Fichier** : `app/templates/admin/groupes.html`
- **Template parent** : `admin/base_admin.html`
- **Fonctionnalités** : Gestion complète des groupes de codéveloppement avec CRUD

### Pipeline Complet

#### 6.1 Route Principale : `/admin/groupes` (Liste)
- **Route** : `@router.get("/groupes", name="admin_groupes")`
- **Fichier** : `app/routers/ACD/admin.py:1867-1882`
- **Méthode** : `admin_groupes()`

**Pipeline détaillé :**

1. **Authentification & Autorisation**
   - `admin_required(current_user)` → Validation du rôle admin
   - Si non autorisé → `HTTPException(403)`

2. **Recherche optionnelle**
   ```python
   stmt = select(Groupe)
   if q:  # Paramètre de recherche
       like = f"%{q}%"
       stmt = stmt.where((Groupe.nom.ilike(like)) | (Groupe.description.ilike(like)))
   ```

3. **Récupération des groupes**
   ```python
   groupes = session.exec(stmt.order_by(Groupe.nom)).all()
   ```

4. **Variables transmises au template**
   ```python
   {
       "request": request,
       "settings": settings,
       "utilisateur": current_user,
       "groupes": groupes,
       "q": q or ""
   }
   ```

#### 6.2 Route Création : `/admin/groupes/add`
- **Route** : `@router.post("/groupes/add")`
- **Fichier** : `app/routers/ACD/admin.py:1884-1913`
- **Méthode** : `admin_groupes_add()`

**Pipeline détaillé :**

1. **Validation des données**
   ```python
   nom: str = Form(...)
   description: Optional[str] = Form(None)
   capacite_max: Optional[str] = Form(None)
   actif: Literal["on", "off", ""] = Form("on")
   ```

2. **Vérification de l'unicité du nom**
   ```python
   existing = session.exec(select(Groupe).where(Groupe.nom == nom.strip())).first()
   if existing:
       raise HTTPException(status_code=400, detail="Un groupe avec ce nom existe déjà")
   ```

3. **Création du groupe**
   ```python
   groupe = Groupe(
       nom=nom.strip(),
       description=description.strip() if description else None,
       capacite_max=int(capacite_max) if capacite_max and capacite_max.strip().isdigit() else None,
       actif=(actif != "off")
   )
   session.add(groupe)
   ```

4. **Log d'activité**
   ```python
   log_activity(session, user=current_user, action="GROUPE_CREATE", 
               entity="Groupe", entity_id=groupe.id,
               activity_data={"nom": groupe.nom, "capacite_max": groupe.capacite_max}, 
               request=request)
   ```

5. **Commit et redirection**
   ```python
   session.commit()
   return RedirectResponse(url=f"/admin/groupes?success=1&action=add&t={timestamp}", status_code=303)
   ```

#### 6.3 Route Mise à jour : `/admin/groupes/{groupe_id}/update`
- **Route** : `@router.post("/groupes/{groupe_id}/update")`
- **Fichier** : `app/routers/ACD/admin.py:1915-1965`
- **Méthode** : `admin_groupes_update()`

**Pipeline détaillé :**

1. **Validation** : `admin_required(current_user)`
2. **Récupération du groupe** : `session.get(Groupe, groupe_id)`
3. **Vérification de l'unicité du nom** : Exclusion du groupe actuel
4. **Sauvegarde des anciennes valeurs** : Pour le log d'activité
5. **Mise à jour des champs** : Modification de toutes les propriétés
6. **Mise à jour de la date de modification** : `groupe.date_modification = datetime.now(timezone.utc)`
7. **Log d'activité** : `log_activity()` avec comparaison ancien/nouveau
8. **Redirection** : Retour vers la liste avec paramètres de succès

#### 6.4 Route Toggle Statut : `/admin/groupes/{groupe_id}/toggle`
- **Route** : `@router.post("/groupes/{groupe_id}/toggle")`
- **Fichier** : `app/routers/ACD/admin.py:1967-1981`
- **Méthode** : `admin_groupes_toggle()`

**Pipeline détaillé :**

1. **Validation** : `admin_required(current_user)`
2. **Récupération du groupe** : `session.get(Groupe, groupe_id)`
3. **Inversion du statut** : `groupe.actif = not bool(groupe.actif)`
4. **Mise à jour de la date de modification** : `groupe.date_modification = datetime.now(timezone.utc)`
5. **Log d'activité** : `log_activity()` avec données de l'action
6. **Commit** : `session.commit()`
7. **Redirection** : Retour vers la liste avec paramètres de succès

#### 6.5 Route Suppression : `/admin/groupes/{groupe_id}/delete`
- **Route** : `@router.post("/groupes/{groupe_id}/delete")`
- **Fichier** : `app/routers/ACD/admin.py:1983-2019`
- **Méthode** : `admin_groupes_delete()`

**Pipeline détaillé :**

1. **Validation** : `admin_required(current_user)`
2. **Récupération du groupe** : `session.get(Groupe, groupe_id)`
3. **Vérification des dépendances** : 
   ```python
   decisions_count = session.exec(
       select(func.count(DecisionJuryCandidat.id))
       .where(DecisionJuryCandidat.groupe_id == groupe_id)
   ).first()
   ```
4. **Protection contre la suppression** : Si utilisé dans des décisions de jury
5. **Sauvegarde des informations** : Pour le log avant suppression
6. **Suppression sécurisée** : Try/catch avec rollback
7. **Log d'activité** : `log_activity()` avec données du groupe supprimé
8. **Redirection** : Retour vers la liste avec paramètres de succès

### Modèles Interrogés
- `Groupe` : Gestion complète des groupes de codéveloppement
- `DecisionJuryCandidat` : Vérification des dépendances pour la suppression

### Schémas de Validation
- Form validation : Validation des champs obligatoires
- Nom uniqueness : Vérification de l'unicité du nom
- Dependency check : Vérification des relations avant suppression
- Data sanitization : Nettoyage des chaînes avec `.strip()`
- Number validation : Validation et conversion des nombres

### Template Rendering
- **Template principal** : `admin/groupes.html`
- **Template parent** : `admin/base_admin.html`
- **Fonctionnalités affichées** :
  - Modal de création de groupe avec formulaire complet
  - Tableau des groupes avec informations détaillées
  - Modals d'édition des groupes (un par groupe)
  - Boutons de toggle statut (actif/inactif)
  - Boutons de suppression avec confirmation
  - Affichage de la capacité maximale
  - Informations de création (date et heure)
  - Notifications de succès/erreur

### Actions Disponibles
1. **Ajouter un groupe** → Modal avec formulaire complet
2. **Modifier** → Modal avec formulaire d'édition pré-rempli
3. **Activer/Désactiver** → Toggle du statut actif
4. **Supprimer** → Confirmation avec vérification des dépendances
5. **Rechercher** → Filtrage par nom ou description

### Fonctionnalités Avancées
- **Recherche multi-champs** : Filtrage sur nom et description
- **Protection des données** : Vérification des dépendances avant suppression
- **Log d'activité complet** : Traçabilité de toutes les actions
- **Interface modale** : Création et édition via modals
- **Gestion des capacités** : Validation et affichage de la capacité maximale
- **Timestamps automatiques** : Date de création et modification automatiques
- **Validation robuste** : Vérification d'unicité et validation des nombres

### Champs Gérés
- **Informations principales** : Nom (obligatoire), description (optionnelle)
- **Capacité** : Nombre maximum de personnes (optionnel)
- **Statut** : Actif/Inactif avec toggle
- **Métadonnées** : ID, date de création, date de modification

### Relations et Dépendances
- **DecisionJuryCandidat** : Vérification avant suppression
- **Unicité** : Nom unique dans le système
- **Timestamps** : Gestion automatique des dates

### Navigation Disponible
- **Retour au dashboard** → `admin_dashboard`
- **Recherche** → Filtrage en temps réel

---

## 7. JURYS (`admin/jurys.html`)

### Template Source
- **Fichier** : `app/templates/admin/jurys.html`
- **Template parent** : `admin/base_admin.html`
- **Fonctionnalités** : Gestion complète des jurys avec membres et invitations

### Pipeline Complet

#### 7.1 Route Principale : `/admin/jurys` (Liste)
- **Route** : `@router.get("/jurys", name="admin_jurys")`
- **Fichier** : `app/routers/ACD/admin.py:778-807`
- **Méthode** : `admin_jurys()`

**Pipeline détaillé :**

1. **Authentification & Autorisation**
   - `admin_required(current_user)` → Validation du rôle admin
   - Si non autorisé → `HTTPException(403)`

2. **Chargement des jurys avec relations**
   ```python
   from sqlalchemy.orm import joinedload
   jurys = session.exec(
       select(Jury)
       .options(
           joinedload(Jury.programme),
           joinedload(Jury.promotion)
       )
       .order_by(Jury.session_le.desc())
   ).all()
   ```

3. **Récupération des données de référence**
   ```python
   progs = session.exec(select(Programme).order_by(Programme.code)).all()
   promotions = session.exec(select(Promotion).order_by(Promotion.libelle)).all()
   groupes = session.exec(select(Groupe).where(Groupe.actif == True).order_by(Groupe.nom)).all()
   users = session.exec(select(User).where(User.actif == True)).all()
   ```

4. **Variables transmises au template**
   ```python
   {
       "request": request,
       "settings": settings,
       "utilisateur": current_user,
       "jurys": jurys,
       "progs": progs,
       "promotions": promotions,
       "groupes": groupes,
       "users": users
   }
   ```

#### 7.2 Route Création : `/admin/jurys/add`
- **Route** : `@router.post("/jurys/add")`
- **Fichier** : `app/routers/ACD/admin.py:809-825`
- **Méthode** : `admin_jurys_add()`

**Pipeline détaillé :**

1. **Validation des données**
   ```python
   programme_id: int = Form(...)
   session_date: str = Form(...)
   session_time: str = Form(...)
   lieu: Optional[str] = Form(None)
   statut: str = Form("planifie")
   promotion_id: Optional[str] = Form(None)
   ```

2. **Vérification du programme**
   ```python
   prog = session.get(Programme, programme_id)
   if not prog: raise HTTPException(status_code=404, detail="Programme introuvable")
   ```

3. **Combinaison date et heure**
   ```python
   dt = datetime.fromisoformat(f"{session_date}T{session_time}")
   ```

4. **Création du jury**
   ```python
   j = Jury(programme_id=prog.id, session_le=dt, lieu=lieu or None, statut=statut, 
            promotion_id=int(promotion_id) if promotion_id else None)
   session.add(j)
   ```

5. **Log d'activité**
   ```python
   log_activity(session, user=current_user, action="JURY_ADD", entity="Jury", entity_id=None,
                activity_data={"programme_id": prog.id, "session_le": dt.isoformat(), "lieu": lieu, "statut": statut}, request=request)
   ```

6. **Commit et redirection**
   ```python
   session.commit()
   return RedirectResponse(url=request.url_for("admin_jurys"), status_code=303)
   ```

#### 7.3 Route Mise à jour : `/admin/jurys/{jury_id}/update`
- **Route** : `@router.post("/jurys/{jury_id}/update")`
- **Fichier** : `app/routers/ACD/admin.py:827-859`
- **Méthode** : `admin_jury_update()`

**Pipeline détaillé :**

1. **Validation** : `admin_required(current_user)`
2. **Récupération du jury** : `session.get(Jury, jury_id)`
3. **Combinaison date et heure** : `datetime.fromisoformat(f"{session_date}T{session_time}")`
4. **Mise à jour des champs** : programme_id, session_le, lieu, statut, promotion_id
5. **Log d'activité** : `log_activity()` avec données de mise à jour
6. **Redirection** : Retour vers la liste avec paramètres de succès

#### 7.4 Route Suppression : `/admin/jurys/{jury_id}/delete`
- **Route** : `@router.post("/jurys/{jury_id}/delete")`
- **Fichier** : `app/routers/ACD/admin.py:861-878`
- **Méthode** : `admin_jury_delete()`

**Pipeline détaillé :**

1. **Validation** : `admin_required(current_user)`
2. **Récupération du jury** : `session.get(Jury, jury_id)`
3. **Suppression en cascade** : 
   ```python
   # Supprimer d'abord les membres du jury
   session.exec(delete(MembreJury).where(MembreJury.jury_id == jury_id))
   # Puis supprimer le jury
   session.delete(jury)
   ```
4. **Log d'activité** : `log_activity()` avec données du jury supprimé
5. **Redirection** : Retour vers la liste des jurys

#### 7.5 Route Ajout Membre : `/admin/jurys/{jury_id}/membres/add`
- **Route** : `@router.post("/jurys/{jury_id}/membres/add")`
- **Fichier** : `app/routers/ACD/admin.py:880-909`
- **Méthode** : `admin_jury_membre_add()`

**Pipeline détaillé :**

1. **Validation** : `admin_required(current_user)`
2. **Vérification du jury** : `session.get(Jury, jury_id)`
3. **Vérification de l'utilisateur** : `session.get(User, utilisateur_id)`
4. **Vérification de l'unicité** : 
   ```python
   existing = session.exec(select(MembreJury).where(MembreJury.jury_id == jury_id, MembreJury.utilisateur_id == utilisateur_id)).first()
   if existing:
       return RedirectResponse(url=f"/admin/jurys/{jury_id}?error=already_member", status_code=303)
   ```
5. **Ajout du membre** : `MembreJury(jury_id=jury_id, utilisateur_id=utilisateur_id, role=role)`
6. **Log d'activité** : `log_activity()` avec données du membre ajouté
7. **Redirection** : Retour vers la liste avec paramètres de succès

#### 7.6 Route Suppression Membre : `/admin/jurys/{jury_id}/membres/{membre_id}/delete`
- **Route** : `@router.post("/jurys/{jury_id}/membres/{membre_id}/delete")`
- **Fichier** : `app/routers/ACD/admin.py:911-924`
- **Méthode** : `admin_jury_membre_delete()`

**Pipeline détaillé :**

1. **Validation** : `admin_required(current_user)`
2. **Récupération du membre** : `session.get(MembreJury, membre_id)`
3. **Suppression du membre** : `session.delete(membre)`
4. **Log d'activité** : `log_activity()` avec données du membre supprimé
5. **Redirection** : Retour vers la liste avec paramètres de succès

#### 7.7 Route Envoi Invitations : `/admin/jurys/{jury_id}/send-invitations`
- **Route** : `@router.post("/jurys/{jury_id}/send-invitations")`
- **Fichier** : `app/routers/ACD/admin.py:926-953`
- **Méthode** : `admin_jury_send_invitations()`

**Pipeline détaillé :**

1. **Validation** : `admin_required(current_user)`
2. **Récupération du jury** : `session.get(Jury, jury_id)`
3. **Récupération des membres** : `session.exec(select(MembreJury).where(MembreJury.jury_id == jury_id)).all()`
4. **Vérification des membres** : Si aucun membre → redirection avec erreur
5. **Envoi des invitations** : Simulation d'envoi d'emails (à implémenter)
6. **Log d'activité** : `log_activity()` avec nombre d'invitations envoyées
7. **Redirection** : Retour vers la liste avec paramètres de succès

### Modèles Interrogés
- `Jury` : Gestion complète des jurys
- `Programme` : Association des jurys aux programmes
- `Promotion` : Association optionnelle aux promotions
- `MembreJury` : Gestion des membres des jurys
- `User` : Utilisateurs pouvant être membres de jury
- `Groupe` : Groupes disponibles pour les décisions

### Schémas de Validation
- Form validation : Validation des champs obligatoires
- Date/Time validation : Combinaison et validation des dates/heures
- Uniqueness check : Vérification de l'unicité des membres par jury
- Foreign key validation : Vérification de l'existence des programmes/utilisateurs
- Cascade deletion : Suppression en cascade des membres avant suppression du jury

### Template Rendering
- **Template principal** : `admin/jurys.html`
- **Template parent** : `admin/base_admin.html`
- **Fonctionnalités affichées** :
  - Modal de création de jury avec formulaire complet
  - Tableau des jurys avec informations détaillées
  - Modals d'édition des jurys (un par jury)
  - Modals de visualisation des détails
  - Modals de gestion des membres avec accordéons
  - Modals d'envoi d'invitations avec contenu pré-rempli
  - Boutons de suppression avec confirmation
  - Affichage des statuts avec badges colorés
  - Informations de date/heure formatées
  - Notifications de succès/erreur multiples

### Actions Disponibles
1. **Ajouter un jury** → Modal avec formulaire complet (programme, date, heure, lieu, statut)
2. **Modifier** → Modal avec formulaire d'édition pré-rempli
3. **Voir détails** → Modal de visualisation des informations complètes
4. **Gérer les membres** → Modal avec accordéons pour ajout et liste des membres
5. **Envoyer invitations** → Modal avec contenu d'email pré-rempli
6. **Supprimer** → Confirmation avec suppression en cascade

### Fonctionnalités Avancées
- **Gestion des membres** : Ajout/suppression avec vérification d'unicité
- **Système d'invitations** : Envoi d'emails aux membres du jury
- **Relations complexes** : Chargement avec joinedload pour programme et promotion
- **Interface modale multiple** : 4 types de modals différents par jury
- **Accordéons interactifs** : Pour l'ajout de membres et la gestion des invitations
- **Log d'activité complet** : Traçabilité de toutes les actions
- **Suppression en cascade** : Suppression automatique des membres avant suppression du jury
- **Validation robuste** : Vérification des programmes et utilisateurs existants

### Champs Gérés
- **Informations principales** : Programme (obligatoire), promotion (optionnelle)
- **Planification** : Date et heure (obligatoires), lieu (optionnel)
- **Statut** : Planifié, En cours, Terminé
- **Membres** : Utilisateurs avec rôles (président, membre, rapporteur, observateur)
- **Métadonnées** : ID, date de création, relations

### Relations et Dépendances
- **Programme** : Association obligatoire
- **Promotion** : Association optionnelle
- **MembreJury** : Relation un-à-plusieurs avec suppression en cascade
- **User** : Utilisateurs pouvant être membres
- **Timestamps** : Gestion automatique des dates de session

### Navigation Disponible
- **Retour au dashboard** → `admin_dashboard`
- **Auto-réouverture des modals** → Après actions sur les membres
- **Liens entre modals** → Navigation entre gestion des membres et invitations

### Spécificités des Jurys
- **Planification** : Gestion complète des dates et heures
- **Membres multiples** : Gestion des équipes de jury avec rôles
- **Invitations** : Système d'envoi d'emails aux membres
- **Statuts** : Suivi du cycle de vie des jurys
- **Relations** : Association aux programmes et promotions
- **Traçabilité** : Log complet des actions et modifications

---

## 8. TRACABILITÉ (`admin/logs.html`)

### Template Source
- **Fichier** : `app/templates/admin/logs.html`
- **Template parent** : `admin/base_admin.html`
- **Fonctionnalités** : Consultation des logs d'activité avec filtrage et détails

### Pipeline Complet

#### 8.1 Route Principale : `/admin/logs` (Consultation)
- **Route** : `@router.get("/logs", name="admin_logs")`
- **Fichier** : `app/routers/ACD/admin.py:955-972`
- **Méthode** : `admin_logs()`

**Pipeline détaillé :**

1. **Authentification & Autorisation**
   - `admin_required(current_user)` → Validation du rôle admin
   - Si non autorisé → `HTTPException(403)`

2. **Récupération des logs récents**
   ```python
   logs = session.exec(
       select(ActivityLog)
       .order_by(ActivityLog.created_at.desc())
       .limit(100)  # Limiter à 100 logs récents
   ).all()
   ```

3. **Variables transmises au template**
   ```python
   {
       "request": request,
       "settings": settings,
       "utilisateur": current_user,
       "logs": logs
   }
   ```

#### 8.2 Route Avancée : `/admin/logs` (Avec filtres)
- **Route** : `@router.get("/logs", response_class=HTMLResponse)` (deuxième route)
- **Fichier** : `app/routers/ACD/admin.py:1243-1308`
- **Méthode** : `admin_logs()` (version avec paramètres)

**Pipeline détaillé :**

1. **Validation** : `admin_required(current_user)`
2. **Construction de la requête avec filtres**
   ```python
   stmt = select(ActivityLog)
   conds = []
   if q:  # Recherche libre
       like = f"%{q}%"
       conds.append(
           (ActivityLog.action.ilike(like)) | 
           (ActivityLog.entity.ilike(like)) | 
           (ActivityLog.user_email.ilike(like))
       )
   if action:  # Filtre par action
       conds.append(ActivityLog.action == action)
   if user_email:  # Filtre par utilisateur
       conds.append(ActivityLog.user_email == user_email)
   if date_from:  # Filtre par date de début
       from_dt = datetime.fromisoformat(date_from)
       conds.append(ActivityLog.created_at >= from_dt)
   if date_to:  # Filtre par date de fin
       to_dt = datetime.fromisoformat(date_to)
       conds.append(ActivityLog.created_at <= to_dt)
   ```

3. **Application des conditions et pagination**
   ```python
   if conds:
       stmt = stmt.where(and_(*conds))
   stmt = stmt.order_by(ActivityLog.created_at.desc())
   offset = (page - 1) * page_size
   rows = session.exec(stmt.offset(offset).limit(page_size)).all()
   ```

4. **Récupération des données pour les filtres**
   ```python
   actions_distinct = session.exec(select(ActivityLog.action).distinct().order_by(ActivityLog.action)).all()
   users_distinct = session.exec(select(ActivityLog.user_email).where(ActivityLog.user_email.is_not(None)).distinct().order_by(ActivityLog.user_email)).all()
   ```

#### 8.3 Route Export : `/admin/logs/export`
- **Route** : `@router.get("/logs/export")`
- **Fichier** : `app/routers/ACD/admin.py:1310-1336`
- **Méthode** : `admin_logs_export_csv()`

**Pipeline détaillé :**

1. **Validation** : `admin_required(current_user)`
2. **Récupération des logs**
   ```python
   stmt = select(ActivityLog).order_by(ActivityLog.created_at.desc())
   rows = session.exec(stmt.limit(10000)).all()
   ```
3. **Génération du CSV**
   ```python
   import csv, io, json
   buf = io.StringIO()
   writer = csv.writer(buf)
   writer.writerow(["created_at","user_email","action","entity","entity_id","ip","user_agent","activity_data"])
   ```
4. **Écriture des données**
   ```python
   for r in rows:
       writer.writerow([
           r.created_at.isoformat(), r.user_email or "", r.action, r.entity or "", r.entity_id or "",
           r.ip or "", (r.user_agent or "")[:200],  # UA tronqué
           ("" if r.activity_data is None else json.dumps(r.activity_data, ensure_ascii=False)),
       ])
   ```
5. **Retour du fichier CSV**
   ```python
   return StreamingResponse(buf, media_type="text/csv", 
                          headers={"Content-Disposition": "attachment; filename=activity_logs.csv"})
   ```

### Modèles Interrogés
- `ActivityLog` : Modèle principal pour les logs d'activité
- `User` : Informations des utilisateurs (via les logs)

### Schémas de Validation
- Admin required : Seuls les administrateurs peuvent consulter les logs
- Date validation : Validation et conversion des dates ISO
- Pagination : Limitation du nombre de résultats (10-200 par page)
- Export limit : Limitation à 10000 logs pour l'export

### Template Rendering
- **Template principal** : `admin/logs.html`
- **Template parent** : `admin/base_admin.html`
- **Fonctionnalités affichées** :
  - Tableau des logs avec informations détaillées
  - Filtres de recherche (texte libre, action, utilisateur)
  - Bouton d'effacement des filtres
  - Modals de détails pour chaque log avec données JSON
  - Affichage des statuts avec badges colorés
  - Informations de date/heure formatées
  - Gestion des utilisateurs supprimés/inconnus
  - Pagination et export CSV

### Actions Disponibles
1. **Consulter les logs** → Affichage des 100 derniers logs
2. **Filtrer par recherche** → Recherche libre sur action, entité, email
3. **Filtrer par action** → Filtrage par type d'action spécifique
4. **Filtrer par utilisateur** → Filtrage par utilisateur spécifique
5. **Filtrer par date** → Filtrage par période (de/à)
6. **Voir détails** → Modal avec données JSON complètes
7. **Exporter CSV** → Téléchargement des logs en format CSV

### Fonctionnalités Avancées
- **Filtrage multi-critères** : Recherche libre + filtres spécifiques
- **Pagination** : Gestion des grandes quantités de logs
- **Export CSV** : Téléchargement des données pour analyse externe
- **Interface de filtrage** : Filtres dynamiques avec JavaScript
- **Modals de détails** : Affichage des données JSON formatées
- **Gestion des utilisateurs supprimés** : Affichage spécial pour les utilisateurs supprimés
- **Recherche en temps réel** : Filtrage instantané sans rechargement

### Champs Gérés
- **Informations principales** : Date/heure, utilisateur, action, entité
- **Métadonnées** : ID d'entité, adresse IP, user agent
- **Données d'activité** : JSON avec détails de l'action
- **Informations utilisateur** : Nom, email, rôle (même si utilisateur supprimé)

### Relations et Dépendances
- **ActivityLog** : Modèle principal avec toutes les informations
- **User** : Informations des utilisateurs (via les logs)
- **Timestamps** : Gestion automatique des dates de création
- **JSON Data** : Stockage des données d'activité en JSON

### Navigation Disponible
- **Retour au dashboard** → `admin_dashboard`
- **Filtrage dynamique** → Sans rechargement de page
- **Export CSV** → Téléchargement direct

### Spécificités des Logs
- **Traçabilité complète** : Enregistrement de toutes les actions administratives
- **Données JSON** : Stockage flexible des détails d'activité
- **Gestion des utilisateurs supprimés** : Conservation des logs même après suppression
- **Filtrage avancé** : Recherche multi-critères avec pagination
- **Export** : Possibilité d'exporter les données pour analyse
- **Interface intuitive** : Filtres dynamiques et modals de détails

### Types d'Actions Traçées
- **USER_ADD/USER_UPDATE/USER_DELETE** : Gestion des utilisateurs
- **PROGRAMME_ADD/PROGRAMME_UPDATE/PROGRAMME_DELETE** : Gestion des programmes
- **JURY_ADD/JURY_UPDATE/JURY_DELETE** : Gestion des jurys
- **JURY_INVITATIONS_SENT** : Envoi d'invitations
- **GROUPE_CREATE/GROUPE_UPDATE/GROUPE_DELETE** : Gestion des groupes
- **PROMOTION_CREATE/PROMOTION_UPDATE/PROMOTION_DELETE** : Gestion des promotions
- **PARTENAIRE_CREATE/PARTENAIRE_UPDATE/PARTENAIRE_DELETE** : Gestion des partenaires

### Sécurité et Confidentialité
- **Accès restreint** : Seuls les administrateurs peuvent consulter les logs
- **Données sensibles** : Conservation des informations même après suppression
- **Audit trail** : Traçabilité complète des actions administratives
- **Export contrôlé** : Limitation à 10000 logs pour l'export

---

## 9. PERMISSIONS (`admin/permissions.html`)

### Template Source
- **Fichier** : `app/templates/admin/permissions.html`
- **Template parent** : `admin/base_admin.html`
- **Fonctionnalités** : Gestion complète des permissions avec matrice des rôles et permissions utilisateurs

### Pipeline Complet

#### 9.1 Route Principale : `/admin/permissions` (Consultation)
- **Route** : `@router.get("/permissions", name="admin_permissions")`
- **Fichier** : `app/routers/ACD/admin.py:975-998`
- **Méthode** : `admin_permissions()`

**Pipeline détaillé :**

1. **Authentification & Autorisation**
   - `admin_required(current_user)` → Validation du rôle admin
   - Si non autorisé → `HTTPException(403)`

2. **Initialisation des permissions par défaut**
   ```python
   permission_service = PermissionService(session)
   permission_service.initialize_default_permissions()
   ```

3. **Récupération de la matrice des permissions**
   ```python
   permission_matrix = permission_service.get_permission_matrix()
   ```

4. **Récupération des utilisateurs**
   ```python
   users = session.exec(select(User).where(User.actif == True)).all()
   ```

5. **Variables transmises au template**
   ```python
   {
       "request": request,
       "settings": settings,
       "utilisateur": current_user,
       "permission_matrix": permission_matrix,
       "users": users,
       "resource_types": list(TypeRessource),
       "permission_levels": list(NiveauPermission),
       "all_roles": permission_service.get_all_roles()
   }
   ```

#### 9.2 Route Octroi Permission : `/admin/permissions/grant`
- **Route** : `@router.post("/permissions/grant")`
- **Fichier** : `app/routers/ACD/admin.py:1000-1020`
- **Méthode** : `admin_grant_permission()`

**Pipeline détaillé :**

1. **Validation** : `admin_required(current_user)`
2. **Validation des données**
   ```python
   target_user_id: int = Form(...)
   resource: TypeRessource = Form(...)
   permission_level: NiveauPermission = Form(...)
   reason: str = Form(None)
   ```
3. **Octroi de la permission**
   ```python
   permission_service = PermissionService(session)
   success = permission_service.grant_permission(
       current_user, target_user_id, resource, permission_level, reason
   )
   ```
4. **Redirection avec statut**
   ```python
   if success:
       return RedirectResponse(url=request.url_for("admin_permissions") + "?success=permission_granted", status_code=303)
   else:
       return RedirectResponse(url=request.url_for("admin_permissions") + "?error=permission_grant_failed", status_code=303)
   ```

#### 9.3 Route Révocation Permission : `/admin/permissions/revoke`
- **Route** : `@router.post("/permissions/revoke")`
- **Fichier** : `app/routers/ACD/admin.py:1022-1039`
- **Méthode** : `admin_revoke_permission()`

**Pipeline détaillé :**

1. **Validation** : `admin_required(current_user)`
2. **Validation des données**
   ```python
   target_user_id: int = Form(...)
   resource: TypeRessource = Form(...)
   reason: str = Form(None)
   ```
3. **Révocation de la permission**
   ```python
   permission_service = PermissionService(session)
   success = permission_service.revoke_permission(current_user, target_user_id, resource, reason)
   ```
4. **Redirection avec statut**
   ```python
   if success:
       return RedirectResponse(url=request.url_for("admin_permissions") + "?success=permission_revoked", status_code=303)
   else:
       return RedirectResponse(url=request.url_for("admin_permissions") + "?error=permission_revoke_failed", status_code=303)
   ```

#### 9.4 Route Mise à jour Permission Rôle : `/admin/permissions/update-role`
- **Route** : `@router.post("/permissions/update-role")`
- **Fichier** : `app/routers/ACD/admin.py:1041-1075`
- **Méthode** : `admin_update_role_permission()`

**Pipeline détaillé :**

1. **Validation** : `admin_required(current_user)`
2. **Validation des données**
   ```python
   role: str = Form(...)
   resource: str = Form(...)
   permission_level: str = Form(...)
   reason: str = Form(None)
   ```
3. **Conversion des enums**
   ```python
   resource_enum = TypeRessource(resource)
   permission_enum = NiveauPermission(permission_level)
   ```
4. **Mise à jour de la permission**
   ```python
   success = permission_service.update_role_permission(
       current_user, role, resource_enum, permission_enum, reason
   )
   ```
5. **Gestion des erreurs et redirection**
   ```python
   try:
       # ... logique de mise à jour
       if success:
           return RedirectResponse(url=request.url_for("admin_permissions") + "?success=role_permission_updated", status_code=303)
       else:
           return RedirectResponse(url=request.url_for("admin_permissions") + "?error=role_permission_update_failed", status_code=303)
   except ValueError as e:
       return RedirectResponse(url=request.url_for("admin_permissions") + "?error=invalid_permission_data", status_code=303)
   except Exception as e:
       return RedirectResponse(url=request.url_for("admin_permissions") + "?error=role_permission_update_failed", status_code=303)
   ```

### Modèles Interrogés
- `PermissionRole` : Permissions par rôle
- `PermissionUtilisateur` : Permissions spécifiques par utilisateur
- `LogPermission` : Log des modifications de permissions
- `NiveauPermission` : Niveaux de permission (lecture, écriture, suppression, admin)
- `TypeRessource` : Types de ressources (utilisateurs, programmes, jurys, etc.)
- `User` : Utilisateurs pour les permissions spécifiques

### Schémas de Validation
- Admin required : Seuls les administrateurs peuvent gérer les permissions
- Form validation : Validation des champs obligatoires
- Enum validation : Conversion et validation des enums TypeRessource et NiveauPermission
- Permission service : Validation métier via PermissionService
- Error handling : Gestion des erreurs de conversion et d'exécution

### Template Rendering
- **Template principal** : `admin/permissions.html`
- **Template parent** : `admin/base_admin.html`
- **Fonctionnalités affichées** :
  - Interface à onglets (Matrice des rôles, Modifier les droits, Permissions utilisateurs)
  - Matrice des permissions avec badges colorés
  - Matrice éditable avec sélecteurs
  - Formulaires d'octroi/révocation de permissions
  - Tableau des permissions spécifiques des utilisateurs
  - Notifications de succès/erreur multiples
  - Auto-dismiss des alertes après 5 secondes

### Actions Disponibles
1. **Consulter la matrice** → Affichage des permissions par rôle et ressource
2. **Modifier les droits de rôle** → Mise à jour des permissions par rôle
3. **Accorder permission utilisateur** → Octroi de permission spécifique à un utilisateur
4. **Révoquer permission utilisateur** → Révocation de permission spécifique
5. **Modification directe** → Changement via la matrice éditable
6. **Raison des modifications** → Traçabilité des changements

### Fonctionnalités Avancées
- **Matrice des permissions** : Vue d'ensemble des droits par rôle et ressource
- **Interface à onglets** : Navigation entre consultation et modification
- **Matrice éditable** : Modification directe via sélecteurs dans le tableau
- **Permissions spécifiques** : Gestion des permissions individuelles par utilisateur
- **Traçabilité** : Enregistrement des raisons de modification
- **Validation métier** : Vérification via PermissionService
- **Gestion d'erreurs** : Gestion des erreurs de conversion et d'exécution
- **Auto-dismiss** : Fermeture automatique des alertes

### Champs Gérés
- **Rôles** : Tous les rôles du système
- **Ressources** : Types de ressources (utilisateurs, programmes, jurys, etc.)
- **Niveaux de permission** : Lecture, écriture, suppression, admin
- **Utilisateurs** : Utilisateurs actifs pour permissions spécifiques
- **Raisons** : Justification des modifications (optionnel)

### Relations et Dépendances
- **PermissionRole** : Permissions par rôle
- **PermissionUtilisateur** : Permissions spécifiques par utilisateur
- **LogPermission** : Traçabilité des modifications
- **PermissionService** : Service métier pour la gestion des permissions
- **Enums** : TypeRessource et NiveauPermission

### Navigation Disponible
- **Retour au dashboard** → `admin_dashboard`
- **Onglets internes** → Navigation entre les sections
- **Modification directe** → Via la matrice éditable

### Spécificités des Permissions
- **Système granulaire** : Permissions par rôle et par utilisateur
- **Matrice visuelle** : Vue d'ensemble claire des droits
- **Modification flexible** : Via formulaire ou matrice éditable
- **Traçabilité complète** : Enregistrement des raisons de modification
- **Validation métier** : Vérification via PermissionService
- **Gestion d'erreurs** : Gestion robuste des erreurs de conversion

### Types de Ressources
- **Utilisateurs** : Gestion des utilisateurs
- **Programmes** : Gestion des programmes
- **Jurys** : Gestion des jurys
- **Groupes** : Gestion des groupes
- **Promotions** : Gestion des promotions
- **Partenaires** : Gestion des partenaires
- **Logs** : Consultation des logs
- **Permissions** : Gestion des permissions

### Niveaux de Permission
- **Lecture** : Consultation uniquement
- **Écriture** : Modification des données
- **Suppression** : Suppression des données
- **Admin** : Contrôle total

### Sécurité et Contrôle d'Accès
- **Accès restreint** : Seuls les administrateurs peuvent gérer les permissions
- **Validation métier** : Vérification via PermissionService
- **Traçabilité** : Enregistrement de toutes les modifications
- **Gestion d'erreurs** : Gestion robuste des erreurs
- **Validation des enums** : Conversion sécurisée des types

---

## 10. ARCHIVES (`admin/archives.html`)

### Template Source
- **Fichier** : `app/templates/admin/archives.html`
- **Template parent** : `admin/base_admin.html`
- **Fonctionnalités** : Gestion complète des archives avec sauvegarde, restauration, export et import

### Pipeline Complet

#### 10.1 Route Principale : `/admin/archives` (Consultation)
- **Route** : `@router.get("/archives", name="admin_archives")`
- **Fichier** : `app/routers/ACD/admin.py:1105-1119`
- **Méthode** : `admin_archives()`

**Pipeline détaillé :**

1. **Authentification & Autorisation**
   - `admin_required(current_user)` → Validation du rôle admin
   - Si non autorisé → `HTTPException(403)`

2. **Récupération des archives**
   ```python
   archive_service = ArchiveService(session)
   archives = archive_service.get_archive_list()
   ```

3. **Variables transmises au template**
   ```python
   {
       "request": request,
       "settings": settings,
       "utilisateur": current_user,
       "archives": archives,
       "archive_types": list(TypeArchive),
       "archive_statuses": list(StatutArchive)
   }
   ```

#### 10.2 Route Création Sauvegarde : `/admin/archives/create`
- **Route** : `@router.post("/archives/create")`
- **Fichier** : `app/routers/ACD/admin.py:1121-1136`
- **Méthode** : `admin_create_backup()`

**Pipeline détaillé :**

1. **Validation** : `admin_required(current_user)`
2. **Validation des données**
   ```python
   description: str = Form(None)
   ```
3. **Création de la sauvegarde**
   ```python
   archive_service = ArchiveService(session)
   success = archive_service.create_full_backup(current_user, description)
   ```
4. **Redirection avec statut**
   ```python
   if success:
       return RedirectResponse(url=request.url_for("admin_archives") + "?success=backup_created", status_code=303)
   else:
       return RedirectResponse(url=request.url_for("admin_archives") + "?error=backup_failed", status_code=303)
   ```

#### 10.3 Route Restauration : `/admin/archives/{archive_id}/restore`
- **Route** : `@router.post("/archives/{archive_id}/restore")`
- **Fichier** : `app/routers/ACD/admin.py:1138-1153`
- **Méthode** : `admin_restore_backup()`

**Pipeline détaillé :**

1. **Validation** : `admin_required(current_user)`
2. **Restauration de la sauvegarde**
   ```python
   archive_service = ArchiveService(session)
   success = archive_service.restore_from_backup(archive_id, current_user)
   ```
3. **Redirection avec statut**
   ```python
   if success:
       return RedirectResponse(url=request.url_for("admin_archives") + "?success=backup_restored", status_code=303)
   else:
       return RedirectResponse(url=request.url_for("admin_archives") + "?error=restore_failed", status_code=303)
   ```

#### 10.4 Route Suppression : `/admin/archives/{archive_id}/delete`
- **Route** : `@router.post("/archives/{archive_id}/delete")`
- **Fichier** : `app/routers/ACD/admin.py:1155-1170`
- **Méthode** : `admin_delete_archive()`

**Pipeline détaillé :**

1. **Validation** : `admin_required(current_user)`
2. **Suppression de l'archive**
   ```python
   archive_service = ArchiveService(session)
   success = archive_service.delete_archive(archive_id, current_user)
   ```
3. **Redirection avec statut**
   ```python
   if success:
       return RedirectResponse(url=request.url_for("admin_archives") + "?success=archive_deleted", status_code=303)
   else:
       return RedirectResponse(url=request.url_for("admin_archives") + "?error=delete_failed", status_code=303)
   ```

#### 10.5 Route Téléchargement : `/admin/archives/{archive_id}/download`
- **Route** : `@router.get("/archives/{archive_id}/download")`
- **Fichier** : `app/routers/ACD/admin.py:2041-2069`
- **Méthode** : `admin_archives_download()`

**Pipeline détaillé :**

1. **Validation** : `admin_required(current_user)`
2. **Vérification de l'archive**
   ```python
   archive_service = ArchiveService(session)
   archive = session.get(Archive, archive_id)
   if not archive:
       raise HTTPException(status_code=404, detail="Archive introuvable")
   ```
3. **Vérification du statut**
   ```python
   if archive.statut != StatutArchive.TERMINE:
       raise HTTPException(status_code=400, detail="L'archive n'est pas terminée")
   ```
4. **Vérification du fichier**
   ```python
   if not archive.chemin_fichier or not os.path.exists(archive.chemin_fichier):
       raise HTTPException(status_code=404, detail="Fichier d'archive introuvable")
   ```
5. **Log et retour du fichier**
   ```python
   log_activity(session, user=current_user, action="ARCHIVE_DOWNLOAD", entity="Archive", entity_id=archive_id,
                activity_data={"archive_nom": archive.nom, "archive_type": archive.type_archive.value})
   return FileResponse(path=archive.chemin_fichier, filename=f"{archive.nom}.zip")
   ```

#### 10.6 Route Export : `/admin/archives/export`
- **Route** : `@router.post("/archives/export")`
- **Fichier** : `app/routers/ACD/admin.py:2071-2155`
- **Méthode** : `admin_archives_export()`

**Pipeline détaillé :**

1. **Validation** : `admin_required(current_user)`
2. **Validation des données**
   ```python
   export_type: str = Form(...)
   description: Optional[str] = Form(None)
   ```
3. **Création du dossier archives**
   ```python
   archive_dir = Path("archives")
   if not archive_dir.exists():
       archive_dir.mkdir(exist_ok=True)
   ```
4. **Création de l'export selon le type**
   ```python
   if export_type == "data_only":
       archive = archive_service.create_data_export(current_user, description)
   elif export_type == "files_only":
       archive = archive_service.create_files_export(current_user, description)
   elif export_type == "full_backup":
       archive = archive_service.create_full_backup(current_user, description)
   ```
5. **Log et redirection**
   ```python
   log_activity(session, user=current_user, action="ARCHIVE_EXPORT_SUCCESS", entity="Archive", entity_id=archive.id,
                activity_data={"export_type": export_type}, request=request)
   return RedirectResponse(url=request.url_for("admin_archives") + "?success=export_created", status_code=303)
   ```

#### 10.7 Route Import : `/admin/archives/import`
- **Route** : `@router.post("/archives/import")`
- **Fichier** : `app/routers/ACD/admin.py:2157-2249`
- **Méthode** : `admin_archives_import()`

**Pipeline détaillé :**

1. **Validation** : `admin_required(current_user)`
2. **Validation du fichier**
   ```python
   if not file.filename.endswith('.zip'):
       raise HTTPException(status_code=400, detail="Seuls les fichiers ZIP sont acceptés")
   if file.size and file.size > 100 * 1024 * 1024:
       raise HTTPException(status_code=400, detail="Fichier trop volumineux (max 100MB)")
   ```
3. **Sauvegarde temporaire**
   ```python
   with tempfile.NamedTemporaryFile(delete=False, suffix='.zip') as tmp_file:
       shutil.copyfileobj(file.file, tmp_file)
       tmp_path = tmp_file.name
   ```
4. **Création de l'enregistrement d'archive**
   ```python
   archive = Archive(
       nom=f"Import_{import_type}_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
       type_archive=TypeArchive(import_type),
       statut=StatutArchive.EN_COURS,
       description=description or f"Import {import_type}",
       cree_par=current_user.id,
       chemin_fichier=tmp_path,
       metadonnees={"import_source": file.filename, "import_type": import_type}
   )
   ```
5. **Traitement de l'import**
   ```python
   if import_type == "data_only":
       result = archive_service.import_data_from_archive(archive, current_user)
   elif import_type == "files_only":
       result = archive_service.import_files_from_archive(archive, current_user)
   elif import_type == "full_backup":
       result = archive_service.import_full_backup(archive, current_user)
   ```
6. **Mise à jour du statut et nettoyage**
   ```python
   if result:
       archive.statut = StatutArchive.TERMINE
       archive.termine_le = datetime.now(timezone.utc)
   else:
       archive.statut = StatutArchive.ECHEC
       archive.message_erreur = "Échec de l'import"
   os.unlink(tmp_path)  # Nettoyage du fichier temporaire
   ```

#### 10.8 Route Nettoyage : `/admin/archives/cleanup`
- **Route** : `@router.post("/archives/cleanup")`
- **Fichier** : `app/routers/ACD/admin.py:2022-2039`
- **Méthode** : `admin_archives_cleanup()`

**Pipeline détaillé :**

1. **Validation** : `admin_required(current_user)`
2. **Exécution du nettoyage**
   ```python
   archive_service = ArchiveService(session)
   cleanup_stats = archive_service.cleanup_old_data(current_user)
   ```
3. **Log et redirection**
   ```python
   log_activity(session, user=current_user, action="ARCHIVE_CLEANUP", entity="Archive", entity_id=None,
                activity_data={"cleanup_stats": cleanup_stats}, request=request)
   return RedirectResponse(url=request.url_for("admin_archives") + "?success=cleanup_completed", status_code=303)
   ```

#### 10.9 Route Suppression en Lot : `/admin/archives/bulk-delete`
- **Route** : `@router.post("/archives/bulk-delete")`
- **Fichier** : `app/routers/ACD/admin.py:2251-2293`
- **Méthode** : `admin_archives_bulk_delete()`

**Pipeline détaillé :**

1. **Validation** : `admin_required(current_user)`
2. **Parsing des IDs**
   ```python
   ids = [int(id.strip()) for id in archive_ids.split(',') if id.strip()]
   if not ids:
       raise HTTPException(status_code=400, detail="Aucun ID d'archive fourni")
   ```
3. **Suppression en boucle**
   ```python
   for archive_id in ids:
       archive = session.get(Archive, archive_id)
       if archive:
           # Supprimer le fichier physique
           if archive.chemin_fichier and os.path.exists(archive.chemin_fichier):
               os.unlink(archive.chemin_fichier)
           # Supprimer l'enregistrement
           session.delete(archive)
           deleted_count += 1
   ```
4. **Log et redirection**
   ```python
   return RedirectResponse(url=f"{request.url_for('admin_archives')}?success=bulk_delete_completed&count={deleted_count}", status_code=303)
   ```

### Modèles Interrogés
- `Archive` : Modèle principal pour les archives
- `TypeArchive` : Types d'archives (full_backup, data_only, files_only)
- `StatutArchive` : Statuts des archives (TERMINE, EN_COURS, ECHEC, EN_ATTENTE)
- `LogNettoyage` : Log des opérations de nettoyage
- `User` : Utilisateurs créateurs des archives

### Schémas de Validation
- Admin required : Seuls les administrateurs peuvent gérer les archives
- File validation : Validation des fichiers ZIP (extension et taille max 100MB)
- Archive status : Vérification du statut avant téléchargement/restauration
- File existence : Vérification de l'existence des fichiers physiques
- Error handling : Gestion robuste des erreurs avec nettoyage des fichiers temporaires

### Template Rendering
- **Template principal** : `admin/archives.html`
- **Template parent** : `admin/base_admin.html`
- **Fonctionnalités affichées** :
  - Actions rapides (Nettoyage, Export, Import)
  - Tableau des archives avec informations détaillées
  - Modal de création de sauvegarde
  - Modal d'export avec types d'export
  - Modal d'import avec upload de fichier
  - Boutons d'actions (télécharger, restaurer, supprimer)
  - Affichage des statuts avec badges colorés
  - Informations de taille et dates
  - Notifications de succès/erreur multiples
  - Auto-dismiss des alertes après 5 secondes

### Actions Disponibles
1. **Créer une sauvegarde** → Modal avec description optionnelle
2. **Télécharger une archive** → Téléchargement direct du fichier ZIP
3. **Restaurer une archive** → Restauration avec confirmation
4. **Supprimer une archive** → Suppression avec confirmation
5. **Exporter des données** → Modal avec types d'export
6. **Importer des données** → Modal avec upload de fichier
7. **Nettoyer les archives** → Suppression des données obsolètes
8. **Suppression en lot** → Suppression multiple d'archives

### Fonctionnalités Avancées
- **Gestion complète des archives** : Création, restauration, suppression
- **Types d'export multiples** : Sauvegarde complète, données uniquement, fichiers uniquement
- **Import avec validation** : Validation des fichiers ZIP et taille
- **Nettoyage automatique** : Suppression des données obsolètes
- **Gestion des fichiers temporaires** : Nettoyage automatique après import
- **Log d'activité complet** : Traçabilité de toutes les opérations
- **Gestion d'erreurs robuste** : Try/catch avec nettoyage approprié
- **Interface modale** : Création, export et import via modals

### Champs Gérés
- **Informations principales** : Nom, type, statut, description
- **Fichiers** : Chemin du fichier, taille du fichier
- **Dates** : Date de création, date de fin, date d'expiration
- **Métadonnées** : Informations sur l'import/export
- **Utilisateur** : Créateur de l'archive
- **Messages d'erreur** : En cas d'échec

### Relations et Dépendances
- **Archive** : Modèle principal avec toutes les informations
- **ArchiveService** : Service métier pour la gestion des archives
- **Enums** : TypeArchive et StatutArchive
- **Fichiers physiques** : Gestion des fichiers ZIP sur le disque
- **Timestamps** : Gestion automatique des dates

### Navigation Disponible
- **Retour au dashboard** → `admin_dashboard`
- **Actions rapides** → Boutons d'actions directes
- **Modals** → Création, export et import

### Spécificités des Archives
- **Système de sauvegarde complet** : Base de données + fichiers + configuration
- **Types d'export flexibles** : Choix du contenu à exporter
- **Import sécurisé** : Validation et traitement des fichiers
- **Nettoyage automatique** : Suppression des données obsolètes
- **Gestion des fichiers** : Stockage physique et métadonnées
- **Traçabilité** : Log complet des opérations

### Types d'Archives
- **Sauvegarde complète** : Base de données + fichiers uploadés + configuration
- **Données uniquement** : Base de données seulement
- **Fichiers uniquement** : Fichiers uploadés et documents

### Statuts des Archives
- **Terminé** : Archive créée avec succès
- **En cours** : Archive en cours de création/traitement
- **Échec** : Erreur lors de la création/traitement
- **En attente** : Archive en attente de traitement

### Sécurité et Intégrité
- **Accès restreint** : Seuls les administrateurs peuvent gérer les archives
- **Validation des fichiers** : Vérification des types et tailles
- **Gestion des erreurs** : Nettoyage des fichiers temporaires
- **Log d'activité** : Traçabilité de toutes les opérations
- **Confirmation des actions** : Confirmation pour les actions critiques

---

## 11. BASE DE DONNÉES (`admin/database_status.html`)

### Template Source
- **Fichier** : `app/templates/admin/database_status.html`
- **Template parent** : `admin/base_admin.html`
- **Fonctionnalités** : Monitoring et gestion de la base de données avec migration

### Pipeline Complet

#### 11.1 Route Principale : `/admin/database-status` (Consultation)
- **Route** : `@router.get("/database-status", name="admin_database_status")`
- **Fichier** : `app/routers/ACD/admin.py:1077-1089`
- **Méthode** : `admin_database_status()`

**Pipeline détaillé :**

1. **Authentification & Autorisation**
   - `admin_required(current_user)` → Validation du rôle admin
   - Si non autorisé → `HTTPException(403)`

2. **Récupération du statut de la base de données**
   ```python
   migration_service = DatabaseMigrationService(session)
   db_status = migration_service.get_database_status()
   ```

3. **Variables transmises au template**
   ```python
   {
       "request": request,
       "settings": settings,
       "utilisateur": current_user,
       "db_status": db_status
   }
   ```

#### 11.2 Route Migration : `/admin/database-migrate`
- **Route** : `@router.post("/database-migrate")`
- **Fichier** : `app/routers/ACD/admin.py:1091-1102`
- **Méthode** : `admin_database_migrate()`

**Pipeline détaillé :**

1. **Validation** : `admin_required(current_user)`
2. **Exécution de la migration**
   ```python
   migration_service = DatabaseMigrationService(session)
   migration_results = migration_service.migrate_database()
   ```
3. **Log de l'action**
   ```python
   log_activity(session, user=current_user, action="DATABASE_MIGRATION", 
               entity="Database", activity_data=migration_results, request=request)
   ```
4. **Redirection avec statut**
   ```python
   return RedirectResponse(url=request.url_for("admin_database_status") + "?success=migration_completed", status_code=303)
   ```

### Modèles Interrogés
- `DatabaseMigrationService` : Service métier pour la gestion des migrations
- Tous les modèles de la base de données via le service de migration

### Schémas de Validation
- Admin required : Seuls les administrateurs peuvent gérer la base de données
- Migration service : Validation métier via DatabaseMigrationService
- Error handling : Gestion des erreurs de migration

### Template Rendering
- **Template principal** : `admin/database_status.html`
- **Template parent** : `admin/base_admin.html`
- **Fonctionnalités affichées** :
  - Statut de connexion à la base de données
  - Nombre de tables dans la base
  - Liste des enums PostgreSQL avec leurs valeurs
  - Tableau des tables avec statut d'existence
  - Bouton d'exécution de migration avec confirmation
  - Affichage des erreurs de base de données
  - Informations de debug (si DEBUG=True)
  - Notifications de succès/erreur
  - Auto-dismiss des alertes après 5 secondes

### Actions Disponibles
1. **Consulter le statut** → Affichage des informations de la base de données
2. **Exécuter la migration** → Migration de la base avec confirmation
3. **Voir les enums** → Affichage des enums PostgreSQL
4. **Voir les tables** → Liste des tables existantes
5. **Debug** → Affichage des informations de debug (si activé)

### Fonctionnalités Avancées
- **Monitoring de la base** : Vérification de la connexion et des tables
- **Gestion des enums** : Affichage des enums PostgreSQL avec valeurs
- **Migration sécurisée** : Exécution avec confirmation et log
- **Informations de debug** : Affichage conditionnel des données de debug
- **Log d'activité** : Traçabilité des migrations
- **Interface informative** : Cartes avec statuts et badges
- **Auto-dismiss** : Fermeture automatique des alertes

### Champs Gérés
- **Connexion** : Statut de connexion à la base de données
- **Tables** : Liste des tables existantes
- **Enums** : Enums PostgreSQL avec leurs valeurs
- **Erreurs** : Messages d'erreur de la base de données
- **Debug** : Informations de debug (si activé)

### Relations et Dépendances
- **DatabaseMigrationService** : Service métier pour la gestion des migrations
- **Session** : Connexion à la base de données
- **Settings** : Configuration de l'application
- **Log d'activité** : Traçabilité des actions

### Navigation Disponible
- **Retour au dashboard** → `admin_dashboard`
- **Migration** → Exécution directe avec confirmation

### Spécificités de la Base de Données
- **Monitoring complet** : Vérification de la connexion et des structures
- **Gestion des enums** : Affichage des enums PostgreSQL
- **Migration sécurisée** : Exécution avec confirmation et log
- **Informations de debug** : Affichage conditionnel des données
- **Traçabilité** : Log des migrations et actions
- **Interface informative** : Cartes avec statuts visuels

### Types d'Informations Affichées
- **Statut de connexion** : Connectée/Erreur de connexion
- **Nombre de tables** : Comptage des tables existantes
- **Enums PostgreSQL** : Liste avec valeurs
- **Tables** : Liste avec statut d'existence
- **Erreurs** : Messages d'erreur de la base
- **Debug** : Données JSON complètes (si DEBUG=True)

### Sécurité et Contrôle
- **Accès restreint** : Seuls les administrateurs peuvent gérer la base
- **Confirmation de migration** : Confirmation JavaScript avant exécution
- **Log d'activité** : Traçabilité des migrations
- **Gestion d'erreurs** : Affichage des erreurs de base de données
- **Mode debug** : Affichage conditionnel des informations sensibles

### Fonctionnalités Techniques
- **DatabaseMigrationService** : Service métier pour les migrations
- **Vérification de connexion** : Test de la connectivité
- **Listage des tables** : Récupération des tables existantes
- **Gestion des enums** : Récupération des enums PostgreSQL
- **Migration sécurisée** : Exécution avec gestion d'erreurs
- **Log d'activité** : Enregistrement des actions de migration

---

## 12. PARAMÈTRES (`admin/settings.html`)

### Template Source
- **Fichier** : `app/templates/admin/settings.html`
- **Template parent** : `admin/base_admin.html`
- **Fonctionnalités** : Gestion des paramètres de l'application (thème, SMTP, upload)

### Pipeline Complet

#### 12.1 Route Principale : `/admin/settings` (Consultation)
- **Route** : `@router.get("/settings", name="admin_settings")`
- **Fichier** : `app/routers/ACD/admin.py:1189-1204`
- **Méthode** : `admin_settings()`

**Pipeline détaillé :**

1. **Authentification & Autorisation**
   - `admin_required(current_user)` → Validation du rôle admin
   - Si non autorisé → `HTTPException(403)`

2. **Récupération des paramètres**
   ```python
   def getv(k, default=""):
       x = session.exec(select(AppSetting).where(AppSetting.key==k)).first()
       return x.value if x else default
   ```

3. **Construction du contexte**
   ```python
   ctx = {
       "THEME_PRIMARY": getv("THEME_PRIMARY", getattr(settings, "THEME_PRIMARY", "#ffd300")),
       "THEME_SECONDARY": getv("THEME_SECONDARY", getattr(settings, "THEME_SECONDARY", "#111827")),
       "MAX_UPLOAD_SIZE_MB": getv("MAX_UPLOAD_SIZE_MB", str(getattr(settings, "MAX_UPLOAD_SIZE_MB", 5))),
       "SMTP_HOST": getv("SMTP_HOST", getattr(settings, "SMTP_HOST", "")),
       "SMTP_PORT": getv("SMTP_PORT", str(getattr(settings, "SMTP_PORT", ""))),
       "SMTP_USER": getv("SMTP_USER", getattr(settings, "SMTP_USER", "")),
       "SMTP_TLS": getv("SMTP_TLS", str(getattr(settings, "SMTP_TLS", True))),
   }
   ```

4. **Variables transmises au template**
   ```python
   {
       "request": request,
       "settings": settings,
       "utilisateur": current_user,
       "cfg": ctx
   }
   ```

#### 12.2 Route Sauvegarde : `/admin/settings/save`
- **Route** : `@router.post("/settings/save")`
- **Fichier** : `app/routers/ACD/admin.py:1206-1240`
- **Méthode** : `admin_settings_save()`

**Pipeline détaillé :**

1. **Validation** : `admin_required(current_user)`
2. **Validation des données**
   ```python
   THEME_PRIMARY: Optional[str] = Form(None),
   THEME_SECONDARY: Optional[str] = Form(None),
   MAX_UPLOAD_SIZE_MB: Optional[str] = Form(None),
   SMTP_HOST: Optional[str] = Form(None),
   SMTP_PORT: Optional[str] = Form(None),
   SMTP_USER: Optional[str] = Form(None),
   SMTP_TLS: Optional[str] = Form(None),
   ```

3. **Fonction upsert pour sauvegarder**
   ```python
   def upsert(k: str, v: Optional[str]):
       if v is None: return
       row = session.exec(select(AppSetting).where(AppSetting.key==k)).first()
       if not row:
           row = AppSetting(key=k, value=v); session.add(row)
       else:
           row.value = v; row.updated_at = datetime.now(timezone.utc)
   ```

4. **Sauvegarde de tous les paramètres**
   ```python
   upsert("THEME_PRIMARY", THEME_PRIMARY)
   upsert("THEME_SECONDARY", THEME_SECONDARY)
   upsert("MAX_UPLOAD_SIZE_MB", MAX_UPLOAD_SIZE_MB)
   upsert("SMTP_HOST", SMTP_HOST)
   upsert("SMTP_PORT", SMTP_PORT)
   upsert("SMTP_USER", SMTP_USER)
   upsert("SMTP_TLS", SMTP_TLS)
   ```

5. **Log et redirection**
   ```python
   log_activity(session, user=current_user, action="SETTINGS_SAVE", entity="AppSetting", entity_id=None,
                activity_data={"keys": ["THEME_PRIMARY","THEME_SECONDARY","MAX_UPLOAD_SIZE_MB","SMTP_*"]}, request=request)
   session.commit()
   return RedirectResponse(url=request.url_for("admin_settings"), status_code=303)
   ```

### Modèles Interrogés
- `AppSetting` : Modèle principal pour les paramètres de l'application
- `User` : Utilisateur connecté pour l'authentification

### Schémas de Validation
- Admin required : Seuls les administrateurs peuvent modifier les paramètres
- Optional parameters : Tous les paramètres sont optionnels
- Upsert logic : Création ou mise à jour selon l'existence
- Error handling : Gestion des erreurs de sauvegarde

### Template Rendering
- **Template principal** : `admin/settings.html`
- **Template parent** : `admin/base_admin.html`
- **Fonctionnalités affichées** :
  - Section Thème avec couleurs primaire/secondaire et taille d'upload
  - Section SMTP avec hôte, port, utilisateur et TLS
  - Champs de couleur pour les thèmes
  - Champs texte pour les paramètres SMTP
  - Sélecteur pour TLS (True/False)
  - Bouton de sauvegarde
  - Note sur le mot de passe SMTP géré via variables d'environnement

### Actions Disponibles
1. **Consulter les paramètres** → Affichage des paramètres actuels
2. **Modifier le thème** → Couleurs primaire/secondaire et taille d'upload
3. **Configurer SMTP** → Paramètres de messagerie
4. **Sauvegarder** → Sauvegarde de tous les paramètres

### Fonctionnalités Avancées
- **Gestion des paramètres** : Sauvegarde et récupération des paramètres
- **Fallback sur settings** : Valeurs par défaut depuis la configuration
- **Upsert intelligent** : Création ou mise à jour selon l'existence
- **Log d'activité** : Traçabilité des modifications
- **Interface intuitive** : Formulaires organisés par sections
- **Validation des couleurs** : Champs de couleur pour les thèmes
- **Configuration SMTP** : Paramètres de messagerie sécurisés

### Champs Gérés
- **Thème** : Couleur primaire, couleur secondaire, taille d'upload max
- **SMTP** : Hôte, port, utilisateur, TLS
- **Sécurité** : Mot de passe SMTP via variables d'environnement
- **Timestamps** : Date de mise à jour automatique

### Relations et Dépendances
- **AppSetting** : Modèle principal avec clé/valeur
- **Settings** : Configuration par défaut de l'application
- **Session** : Connexion à la base de données
- **Log d'activité** : Traçabilité des modifications

### Navigation Disponible
- **Retour au dashboard** → `admin_dashboard`
- **Sauvegarde** → Redirection vers la même page après sauvegarde

### Spécificités des Paramètres
- **Gestion centralisée** : Tous les paramètres dans AppSetting
- **Fallback intelligent** : Valeurs par défaut depuis settings
- **Upsert automatique** : Création ou mise à jour selon l'existence
- **Log d'activité** : Traçabilité des modifications
- **Interface organisée** : Sections thématiques
- **Sécurité** : Mot de passe SMTP protégé

### Types de Paramètres
- **Thème** : Couleurs et apparence de l'interface
- **Upload** : Taille maximale des fichiers
- **SMTP** : Configuration de la messagerie
- **Sécurité** : Paramètres de sécurité

### Sécurité et Contrôle
- **Accès restreint** : Seuls les administrateurs peuvent modifier les paramètres
- **Log d'activité** : Traçabilité des modifications
- **Validation des données** : Vérification des types
- **Sécurité SMTP** : Mot de passe via variables d'environnement
- **Upsert sécurisé** : Gestion des erreurs de sauvegarde

### Fonctionnalités Techniques
- **AppSetting** : Modèle clé/valeur pour les paramètres
- **Fallback sur settings** : Valeurs par défaut depuis la configuration
- **Upsert logic** : Création ou mise à jour selon l'existence
- **Log d'activité** : Enregistrement des modifications
- **Interface responsive** : Formulaires adaptatifs
- **Validation des couleurs** : Champs de couleur HTML5

### Paramètres Gérés
- **THEME_PRIMARY** : Couleur primaire de l'interface
- **THEME_SECONDARY** : Couleur secondaire (texte)
- **MAX_UPLOAD_SIZE_MB** : Taille maximale d'upload en Mo
- **SMTP_HOST** : Hôte du serveur SMTP
- **SMTP_PORT** : Port du serveur SMTP
- **SMTP_USER** : Utilisateur SMTP
- **SMTP_TLS** : Activation TLS (True/False)

### Interface Utilisateur
- **Sections organisées** : Thème et SMTP séparés
- **Champs de couleur** : Sélecteurs de couleur HTML5
- **Champs texte** : Inputs pour les paramètres SMTP
- **Sélecteur TLS** : Dropdown True/False
- **Bouton de sauvegarde** : Sauvegarde de tous les paramètres
- **Note informative** : Information sur le mot de passe SMTP

---

## ANALYSES TERMINÉES ✅

Toutes les analyses des templates administratifs sont maintenant complètes :

- [x] Programmes (`admin/programmes_list.html`) ✅
- [x] Utilisateurs (`admin/users.html`) ✅
- [x] Partenaires (`admin/partenaires.html`) ✅
- [x] Promotions (`admin/promotions.html`) ✅
- [x] Groupes (`admin/groupes.html`) ✅
- [x] Jurys (`admin/jurys.html`) ✅
- [x] Traçabilité (`admin/logs.html`) ✅
- [x] Permissions (`admin/permissions.html`) ✅
- [x] Archives (`admin/archives.html`) ✅
- [x] Base de données (`admin/database_status.html`) ✅
- [x] Paramètres (`admin/settings.html`) ✅

---

*Document généré automatiquement - Pipeline complet des routes administratives*
