# PIPELINE D'AUTHENTIFICATION - LIA WEB

Ce document détaille le pipeline complet du système d'authentification de l'application LIA WEB, en analysant chaque template et ses routes associées.

## Vue d'ensemble

Le système d'authentification gère :
1. **Connexion** - Formulaire de login avec validation
2. **Gestion des utilisateurs** - CRUD des utilisateurs (admin)
3. **Profil utilisateur** - Modification des informations personnelles
4. **Sécurité** - Hachage des mots de passe, tokens JWT, permissions

---

## 1. CONNEXION (`/login`)

### Templates Source
- **Fichier principal** : `app/templates/login.html`
- **Router** : `app/main.py` (routes intégrées)
- **Sécurité** : `app/core/security.py`

### Pipeline Complet

#### 1.1 Route Affichage : `/login` (GET)
- **Route** : `@app.get("/login", response_class=HTMLResponse)`
- **Fichier** : `app/main.py:200-210`
- **Méthode** : `login_page()`

**Pipeline détaillé :**

1. **Vérification de l'authentification**
   ```python
   current_user = get_current_user(request)
   if current_user:
       return RedirectResponse(url="/", status_code=303)
   ```

2. **Récupération des messages d'erreur**
   ```python
   error = request.query_params.get("error")
   ```

3. **Variables transmises au template**
   ```python
   {
       "request": request,
       "error": error,
       "app_name": settings.APP_NAME
   }
   ```

#### 1.2 Route Connexion : `/login` (POST)
- **Route** : `@app.post("/login")`
- **Fichier** : `app/main.py:212-250`
- **Méthode** : `login()`

**Pipeline détaillé :**

1. **Validation des données**
   ```python
   form = OAuth2PasswordRequestForm(request)
   username: str = form.username
   password: str = form.password
   ```

2. **Authentification de l'utilisateur**
   ```python
   user = authenticate_user(session, username, password)
   if not user:
       return RedirectResponse(url=request.url_for("login_page") + "?error=invalid_credentials", status_code=303)
   ```

3. **Création du token JWT**
   ```python
   access_token = create_access_token(data={"sub": user.email})
   ```

4. **Configuration de la réponse**
   ```python
   response = RedirectResponse(url="/", status_code=303)
   response.set_cookie(
       key="access_token",
       value=f"Bearer {access_token}",
       httponly=True,
       secure=not settings.DEBUG,
       samesite="lax"
   )
   ```

5. **Log de connexion**
   ```python
   log_activity(session, user=user, action="LOGIN", entity="User", entity_id=user.id, request=request)
   ```

### Modèles Interrogés
- `User` : Modèle principal des utilisateurs
- `Session` : Session de base de données pour l'authentification

### Schémas de Validation
- **OAuth2PasswordRequestForm** : Formulaire standardisé pour l'authentification
- **Email validation** : Vérification du format email
- **Password validation** : Vérification du mot de passe
- **User existence** : Vérification de l'existence de l'utilisateur
- **Password hash verification** : Vérification du hash du mot de passe

### Template Rendering
- **Template principal** : `login.html`
- **Fonctionnalités affichées** :
  - Formulaire de connexion avec email et mot de passe
  - Bouton de basculement de visibilité du mot de passe
  - Case à cocher "Se souvenir de moi"
  - Lien "Mot de passe oublié"
  - Messages d'erreur/succès avec auto-dismiss
  - Interface responsive et moderne

### Actions Disponibles
1. **Se connecter** → Validation des identifiants et création de session
2. **Afficher/masquer le mot de passe** → Toggle de visibilité
3. **Mot de passe oublié** → Redirection vers la récupération
4. **Se souvenir de moi** → Extension de la durée de session

### Fonctionnalités Avancées
- **Interface moderne** : Design responsive avec animations
- **Validation côté client** : Vérification des champs obligatoires
- **Auto-dismiss des messages** : Messages d'erreur qui disparaissent automatiquement
- **Toggle de mot de passe** : Affichage/masquage du mot de passe
- **Sécurité renforcée** : Cookies HTTPOnly, tokens JWT
- **Log d'activité** : Traçabilité des connexions

---

## 2. GESTION DES UTILISATEURS (`/auth/users`)

### Templates Source
- **Router** : `app/routers/auth.py`
- **API REST** : Endpoints standards pour la gestion des utilisateurs

### Pipeline Complet

#### 2.1 Route Création : `/auth/users` (POST)
- **Route** : `@router.post("/users", response_model=UserResponse)`
- **Fichier** : `app/routers/auth.py:28-50`
- **Méthode** : `create_user()`

**Pipeline détaillé :**

1. **Vérification des permissions**
   ```python
   if current_user.role not in [UserRole.ADMINISTRATEUR.value, UserRole.DIRECTEUR_TECHNIQUE.value]:
       raise HTTPException(status_code=403, detail="Permissions insuffisantes")
   ```

2. **Validation des données**
   ```python
   user_data: UserCreate
   ```

3. **Vérification de l'unicité de l'email**
   ```python
   existing_user = UserService.get_user_by_email(session, user_data.email)
   if existing_user:
       raise HTTPException(status_code=400, detail="Un utilisateur avec cet email existe déjà")
   ```

4. **Création de l'utilisateur**
   ```python
   user = UserService.create_user(session, user_data)
   return UserResponse.from_orm(user)
   ```

#### 2.2 Route Liste : `/auth/users` (GET)
- **Route** : `@router.get("/users", response_model=List[UserResponse])`
- **Fichier** : `app/routers/auth.py:59-77`
- **Méthode** : `get_users()`

**Pipeline détaillé :**

1. **Vérification des permissions**
   ```python
   if current_user.role not in [UserRole.ADMINISTRATEUR.value, UserRole.DIRECTEUR_TECHNIQUE.value]:
       raise HTTPException(status_code=403, detail="Permissions insuffisantes")
   ```

2. **Filtrage par rôle**
   ```python
   if role:
       users = UserService.get_users_by_role(session, role)
   else:
       users = session.exec(select(User)).all()
   ```

3. **Retour des utilisateurs**
   ```python
   return [UserResponse.from_orm(user) for user in users]
   ```

#### 2.3 Route Modification : `/auth/users/{user_id}` (PUT)
- **Route** : `@router.put("/users/{user_id}", response_model=UserResponse)`
- **Fichier** : `app/routers/auth.py:80-102`
- **Méthode** : `update_user()`

**Pipeline détaillé :**

1. **Vérification des permissions**
   ```python
   if current_user.id != user_id and current_user.role not in [UserRole.ADMINISTRATEUR.value, UserRole.DIRECTEUR_TECHNIQUE.value]:
       raise HTTPException(status_code=403, detail="Permissions insuffisantes")
   ```

2. **Validation des données**
   ```python
   user_data: UserUpdate
   ```

3. **Mise à jour de l'utilisateur**
   ```python
   user = UserService.update_user(session, user_id, user_data)
   if not user:
       raise HTTPException(status_code=404, detail="Utilisateur non trouvé")
   ```

4. **Retour de l'utilisateur mis à jour**
   ```python
   return UserResponse.from_orm(user)
   ```

#### 2.4 Route Suppression : `/auth/users/{user_id}` (DELETE)
- **Route** : `@router.delete("/users/{user_id}")`
- **Fichier** : `app/routers/auth.py:105-132`
- **Méthode** : `delete_user()`

**Pipeline détaillé :**

1. **Vérification des permissions**
   ```python
   if current_user.role not in [UserRole.ADMINISTRATEUR.value, UserRole.DIRECTEUR_TECHNIQUE.value]:
       raise HTTPException(status_code=403, detail="Permissions insuffisantes")
   ```

2. **Protection contre l'auto-suppression**
   ```python
   if current_user.id == user_id:
       raise HTTPException(status_code=400, detail="Vous ne pouvez pas supprimer votre propre compte")
   ```

3. **Suppression de l'utilisateur**
   ```python
   success = UserService.delete_user(session, user_id)
   if not success:
       raise HTTPException(status_code=404, detail="Utilisateur non trouvé")
   ```

4. **Retour du succès**
   ```python
   return {"message": "Utilisateur supprimé avec succès"}
   ```

### Modèles Interrogés
- `User` : Modèle principal des utilisateurs
- `UserService` : Service métier pour la gestion des utilisateurs

### Schémas de Validation
- **UserCreate** : Schéma de création avec validation des champs obligatoires
- **UserUpdate** : Schéma de mise à jour avec champs optionnels
- **UserResponse** : Schéma de réponse avec données formatées
- **Email unique** : Vérification de l'unicité de l'email
- **Permissions** : Vérification des rôles pour les opérations
- **Auto-suppression** : Protection contre la suppression de son propre compte

---

## 3. PROFIL UTILISATEUR (`/auth/profil`)

### Templates Source
- **Fichier principal** : `app/templates/profil.html`
- **Router** : `app/routers/auth.py:137-300`

### Pipeline Complet

#### 3.1 Route Affichage : `/auth/profil` (GET)
- **Route** : `@router.get("/profil", response_class=HTMLResponse, name="profil")`
- **Fichier** : `app/routers/auth.py:137-149`
- **Méthode** : `profil_page()`

**Pipeline détaillé :**

1. **Authentification requise**
   ```python
   current_user: User = Depends(get_current_user)
   ```

2. **Variables transmises au template**
   ```python
   {
       "request": request,
       "utilisateur": current_user,
       "current_user": current_user,
       "timestamp": int(datetime.now(timezone.utc).timestamp())
   }
   ```

#### 3.2 Route Mise à jour : `/auth/profil/update` (POST)
- **Route** : `@router.post("/profil/update", name="profil_update")`
- **Fichier** : `app/routers/auth.py:152-192`
- **Méthode** : `profil_update()`

**Pipeline détaillé :**

1. **Validation des données**
   ```python
   nom_complet: str = Form(...)
   email: str = Form(...)
   telephone: Optional[str] = Form(None)
   ```

2. **Vérification de l'unicité de l'email**
   ```python
   existing_user = session.exec(
       select(User).where(User.email == email, User.id != current_user.id)
   ).first()
   if existing_user:
       return RedirectResponse(url=request.url_for("profil") + "?error=email_exists", status_code=303)
   ```

3. **Mise à jour des informations**
   ```python
   current_user.nom_complet = nom_complet
   current_user.email = email
   current_user.telephone = telephone
   current_user.modifie_le = datetime.now(timezone.utc)
   session.commit()
   ```

4. **Redirection avec succès**
   ```python
   return RedirectResponse(url=request.url_for("profil") + "?success=profile_updated", status_code=303)
   ```

#### 3.3 Route Changement de mot de passe : `/auth/profil/change-password` (POST)
- **Route** : `@router.post("/profil/change-password", name="profil_change_password")`
- **Fichier** : `app/routers/auth.py:195-237`
- **Méthode** : `profil_change_password()`

**Pipeline détaillé :**

1. **Validation des données**
   ```python
   current_password: str = Form(...)
   new_password: str = Form(...)
   confirm_password: str = Form(...)
   ```

2. **Vérification de la correspondance des mots de passe**
   ```python
   if new_password != confirm_password:
       return RedirectResponse(url=request.url_for("profil") + "?error=password_mismatch", status_code=303)
   ```

3. **Vérification de l'ancien mot de passe**
   ```python
   if not authenticate_user(session, current_user.email, current_password):
       return RedirectResponse(url=request.url_for("profil") + "?error=wrong_current_password", status_code=303)
   ```

4. **Mise à jour du mot de passe**
   ```python
   from app_lia_web.core.security import get_password_hash
   current_user.password_hash = get_password_hash(new_password)
   current_user.modifie_le = datetime.now(timezone.utc)
   session.commit()
   ```

5. **Redirection avec succès**
   ```python
   return RedirectResponse(url=request.url_for("profil") + "?success=password_changed", status_code=303)
   ```

#### 3.4 Route Changement de photo : `/auth/profil/photo` (POST)
- **Route** : `@router.post("/profil/photo", name="profil_photo")`
- **Fichier** : `app/routers/auth.py:240-300`
- **Méthode** : `profil_photo()`

**Pipeline détaillé :**

1. **Validation du fichier**
   ```python
   photo_profil: UploadFile = File(...)
   if not photo_profil.content_type or not photo_profil.content_type.startswith('image/'):
       return RedirectResponse(url=request.url_for("profil") + "?error=invalid_file_type", status_code=303)
   ```

2. **Sauvegarde de l'ancienne photo**
   ```python
   old_photo_path = current_user.photo_profil
   ```

3. **Génération du nom de fichier unique**
   ```python
   ext = os.path.splitext(photo_profil.filename)[1].lower() or ".jpg"
   filename = f"user_{current_user.id}_profile{ext}"
   ```

4. **Sauvegarde du fichier**
   ```python
   from app_lia_web.core.path_config import path_config
   upload_dir = path_config.UPLOAD_DIR / "profiles"
   upload_dir.mkdir(exist_ok=True)
   file_path = upload_dir / filename
   
   with open(file_path, "wb") as buffer:
       content = await photo_profil.read()
       buffer.write(content)
   ```

5. **Mise à jour du chemin dans la base**
   ```python
   relative_path = f"/profiles/{filename}"
   current_user.photo_profil = relative_path
   current_user.modifie_le = datetime.now(timezone.utc)
   session.commit()
   ```

6. **Suppression de l'ancienne photo**
   ```python
   if old_photo_path:
       try:
           old_path = Path("." + old_photo_path)
           if old_path.exists():
               old_path.unlink()
       except Exception as e:
           print(f"⚠️ Impossible de supprimer l'ancienne photo: {e}")
   ```

7. **Redirection avec succès**
   ```python
   return RedirectResponse(url=request.url_for("profil") + "?success=photo_updated", status_code=303)
   ```

### Modèles Interrogés
- `User` : Modèle principal des utilisateurs
- `Session` : Session de base de données

### Schémas de Validation
- **Form validation** : Validation des champs de formulaire
- **Email unique** : Vérification de l'unicité de l'email
- **Password verification** : Vérification de l'ancien mot de passe
- **File type validation** : Vérification du type de fichier image
- **Password matching** : Vérification de la correspondance des mots de passe

### Template Rendering
- **Template principal** : `profil.html`
- **Fonctionnalités affichées** :
  - Informations personnelles avec possibilité de modification
  - Modal de changement de mot de passe
  - Modal de changement de photo de profil
  - Messages de succès/erreur avec auto-dismiss
  - Interface responsive avec sidebar de navigation

### Actions Disponibles
1. **Modifier les informations** → Mise à jour du nom, email, téléphone
2. **Changer le mot de passe** → Validation de l'ancien et mise à jour
3. **Changer la photo** → Upload et remplacement de la photo de profil
4. **Voir les informations** → Affichage des données personnelles

### Fonctionnalités Avancées
- **Interface moderne** : Design responsive avec modals
- **Validation côté client** : Vérification des champs obligatoires
- **Gestion des fichiers** : Upload sécurisé des images
- **Auto-dismiss des messages** : Messages qui disparaissent automatiquement
- **Protection des données** : Vérification de l'unicité des emails
- **Sécurité renforcée** : Validation des mots de passe et types de fichiers

---

## 4. RÉCUPÉRATION DE MOT DE PASSE (`/password-recovery`)

### Templates Source
- **Fichier principal** : `app/templates/password_recovery/forgot_password.html`
- **Vérification** : `app/templates/password_recovery/verify_code.html`
- **Réinitialisation** : `app/templates/password_recovery/reset_password.html`
- **Router** : `app/routers/password_recovery.py`

### Pipeline Complet

#### 4.1 Route Demande : `/mot-de-passe-oublie` (GET)
- **Route** : `@router.get("/mot-de-passe-oublie", response_class=HTMLResponse, name="request_password_recovery_get")`
- **Fichier** : `app/routers/password_recovery.py:27-39`
- **Méthode** : `forgot_password_page()`

**Pipeline détaillé :**

1. **Variables transmises au template**
   ```python
   {
       "request": request,
       "app_name": settings.APP_NAME,
       "version": settings.VERSION,
       "author": settings.AUTHOR,
       "current_year": settings.VERSION.split('.')[0] if '.' in settings.VERSION else "2024"
   }
   ```

#### 4.2 Route Traitement : `/mot-de-passe-oublie` (POST)
- **Route** : `@router.post("/mot-de-passe-oublie", response_class=HTMLResponse, name="request_password_recovery_post")`
- **Fichier** : `app/routers/password_recovery.py:42-89`
- **Méthode** : `request_password_recovery()`

**Pipeline détaillé :**

1. **Validation des données**
   ```python
   email: str = Form(...)
   ```

2. **Récupération de l'IP client**
   ```python
   client_ip = request.client.host if request.client else None
   ```

3. **Demande de récupération**
   ```python
   success = recovery_service.request_password_recovery(session, email, client_ip)
   ```

4. **Redirection selon le résultat**
   ```python
   if success:
       return RedirectResponse(url=request.url_for("verify_recovery_code_get") + f"?email={email}&success=true", status_code=302)
   else:
       # Afficher message d'information (sans révéler si l'email existe)
       return templates.TemplateResponse("password_recovery/forgot_password.html", {...})
   ```

#### 4.3 Route Vérification : `/verification-code` (GET)
- **Route** : `@router.get("/verification-code", response_class=HTMLResponse, name="verify_recovery_code_get")`
- **Fichier** : `app/routers/password_recovery.py:92-106`
- **Méthode** : `verify_code_page()`

**Pipeline détaillé :**

1. **Récupération des paramètres**
   ```python
   email: Optional[str] = None
   success: Optional[str] = None
   ```

2. **Variables transmises au template**
   ```python
   {
       "request": request,
       "email": email,
       "success": success == "true",
       "app_name": settings.APP_NAME,
       "version": settings.VERSION,
       "author": settings.AUTHOR,
       "current_year": settings.VERSION.split('.')[0] if '.' in settings.VERSION else "2024"
   }
   ```

#### 4.4 Route Validation Code : `/verification-code` (POST)
- **Route** : `@router.post("/verification-code", response_class=HTMLResponse, name="verify_recovery_code_post")`
- **Fichier** : `app/routers/password_recovery.py:109-155`
- **Méthode** : `verify_recovery_code()`

**Pipeline détaillé :**

1. **Validation des données**
   ```python
   email: str = Form(...)
   code: str = Form(...)
   ```

2. **Vérification du code**
   ```python
   is_valid = recovery_service.verify_recovery_code(session, email, code)
   ```

3. **Redirection selon le résultat**
   ```python
   if is_valid:
       return RedirectResponse(url=request.url_for("reset_password_get") + f"?email={email}&code={code}", status_code=302)
   else:
       # Afficher message d'erreur
       return templates.TemplateResponse("password_recovery/verify_code.html", {...})
   ```

#### 4.5 Route Réinitialisation : `/reinitialiser-mot-de-passe` (GET)
- **Route** : `@router.get("/reinitialiser-mot-de-passe", response_class=HTMLResponse, name="reset_password_get")`
- **Fichier** : `app/routers/password_recovery.py:158-175`
- **Méthode** : `reset_password_page()`

**Pipeline détaillé :**

1. **Vérification des paramètres requis**
   ```python
   if not email or not code:
       return RedirectResponse(url=request.url_for("request_password_recovery_get"), status_code=302)
   ```

2. **Variables transmises au template**
   ```python
   {
       "request": request,
       "email": email,
       "code": code,
       "app_name": settings.APP_NAME,
       "version": settings.VERSION,
       "author": settings.AUTHOR,
       "current_year": settings.VERSION.split('.')[0] if '.' in settings.VERSION else "2024"
   }
   ```

#### 4.6 Route Nouveau Mot de Passe : `/reinitialiser-mot-de-passe` (POST)
- **Route** : `@router.post("/reinitialiser-mot-de-passe", response_class=HTMLResponse, name="reset_password_post")`
- **Fichier** : `app/routers/password_recovery.py:178-260`
- **Méthode** : `reset_password()`

**Pipeline détaillé :**

1. **Validation des données**
   ```python
   email: str = Form(...)
   code: str = Form(...)
   new_password: str = Form(...)
   confirm_password: str = Form(...)
   ```

2. **Vérification de la correspondance des mots de passe**
   ```python
   if new_password != confirm_password:
       return templates.TemplateResponse("password_recovery/reset_password.html", {...})
   ```

3. **Vérification de la force du mot de passe**
   ```python
   if len(new_password) < 8:
       return templates.TemplateResponse("password_recovery/reset_password.html", {...})
   ```

4. **Réinitialisation du mot de passe**
   ```python
   success = recovery_service.reset_password(session, email, code, new_password)
   ```

5. **Redirection selon le résultat**
   ```python
   if success:
       return RedirectResponse(url=request.url_for("login_page") + "?password_reset=success", status_code=302)
   else:
       # Afficher message d'erreur
       return templates.TemplateResponse("password_recovery/reset_password.html", {...})
   ```

### Modèles Interrogés
- `User` : Modèle principal des utilisateurs
- `PasswordRecoveryService` : Service métier pour la récupération de mot de passe
- `Session` : Session de base de données

### Schémas de Validation
- **PasswordRecoveryRequest** : Schéma de demande de récupération
- **PasswordRecoveryVerify** : Schéma de vérification de code
- **PasswordReset** : Schéma de réinitialisation
- **PasswordRecoveryResponse** : Schéma de réponse API
- **Email validation** : Vérification du format email
- **Code validation** : Vérification du code de récupération
- **Password strength** : Vérification de la force du mot de passe
- **Password matching** : Vérification de la correspondance des mots de passe

### Template Rendering
- **Template demande** : `password_recovery/forgot_password.html`
- **Template vérification** : `password_recovery/verify_code.html`
- **Template réinitialisation** : `password_recovery/reset_password.html`
- **Fonctionnalités affichées** :
  - Formulaire de demande avec email
  - Formulaire de vérification avec code
  - Formulaire de réinitialisation avec nouveau mot de passe
  - Messages d'erreur/succès contextuels
  - Interface responsive et moderne
  - Liens de navigation entre les étapes

### Actions Disponibles
1. **Demander la récupération** → Envoi d'un code par email
2. **Vérifier le code** → Validation du code reçu
3. **Réinitialiser le mot de passe** → Création d'un nouveau mot de passe
4. **Retour à la connexion** → Navigation vers la page de login

### Fonctionnalités Avancées
- **Sécurité renforcée** : Codes temporaires avec expiration
- **Protection contre l'énumération** : Messages neutres pour tous les cas
- **Validation côté client** : Vérification des champs obligatoires
- **Interface moderne** : Design responsive avec animations
- **API REST** : Endpoints pour intégration externe
- **Nettoyage automatique** : Suppression des codes expirés
- **Logging complet** : Traçabilité des tentatives de récupération

### API REST Disponible
- **POST** `/api/password-recovery/request` : Demande de récupération
- **POST** `/api/password-recovery/verify` : Vérification de code
- **POST** `/api/password-recovery/reset` : Réinitialisation
- **POST** `/api/password-recovery/cleanup` : Nettoyage des codes expirés

---

## 5. SÉCURITÉ ET CONTRÔLE

### Authentification
- **JWT Tokens** : Tokens d'accès sécurisés avec expiration
- **Cookies HTTPOnly** : Cookies sécurisés pour la session
- **Password Hashing** : Hachage sécurisé des mots de passe avec bcrypt
- **Session Management** : Gestion des sessions utilisateur

### Autorisation
- **Role-based Access Control** : Contrôle d'accès basé sur les rôles
- **Permission Levels** : Niveaux de permissions granulaires
- **Admin Protection** : Protection des fonctions administratives
- **Self-protection** : Protection contre l'auto-suppression

### Validation et Sécurité
- **Input Validation** : Validation des entrées utilisateur
- **File Upload Security** : Sécurité des uploads de fichiers
- **SQL Injection Prevention** : Protection contre les injections SQL
- **XSS Protection** : Protection contre les attaques XSS

### Logging et Audit
- **Activity Logging** : Traçabilité des actions utilisateur
- **Login Tracking** : Suivi des connexions
- **Error Logging** : Enregistrement des erreurs
- **Security Events** : Événements de sécurité

---

## 5. NAVIGATION ET INTÉGRATION

### Navigation Disponible
- **Connexion** → `login_page`
- **Profil** → `profil`
- **Déconnexion** → `logout`
- **Récupération de mot de passe** → `request_password_recovery_get`
- **Vérification de code** → `verify_recovery_code_get`
- **Réinitialisation** → `reset_password_get`

### Intégration avec l'Application
- **Middleware d'authentification** : Vérification automatique des tokens
- **Dependency Injection** : Injection des utilisateurs connectés
- **Template Context** : Utilisateur disponible dans tous les templates
- **API Protection** : Protection des endpoints API

### Fonctionnalités Techniques
- **FastAPI Security** : Utilisation des composants de sécurité FastAPI
- **OAuth2 Integration** : Intégration avec OAuth2PasswordRequestForm
- **JWT Implementation** : Implémentation des tokens JWT
- **Cookie Management** : Gestion sécurisée des cookies
- **File Upload Service** : Service d'upload de fichiers sécurisé

---

*Document généré automatiquement - Pipeline d'authentification*
