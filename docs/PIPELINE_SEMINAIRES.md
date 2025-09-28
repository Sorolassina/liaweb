# PIPELINE DE GESTION DES SÉMINAIRES - LIA WEB

Ce document détaille le pipeline complet de gestion des séminaires dans l'application LIA WEB, incluant les routes, templates, services et processus métier pour la planification, gestion et suivi des séminaires multi-jours avec sessions, invitations, émargements et livrables.

## Vue d'ensemble

Le système de séminaires permet aux organisateurs de créer des séminaires multi-jours avec sessions individuelles, d'inviter des candidats, de gérer les présences via émargement numérique, et de collecter des livrables des participants.

---

## 1. ARCHITECTURE GÉNÉRALE

### Technologies Utilisées
- **Backend** : FastAPI avec SQLModel
- **Frontend** : Jinja2 templates avec JavaScript interactif
- **Base de données** : PostgreSQL avec relations complexes
- **Services métier** : SeminaireService pour la logique métier
- **Émargement** : Système de signatures numériques et manuelles
- **Email** : Service d'envoi d'emails avec templates
- **Fichiers** : Upload et gestion des livrables

### Modèles Impliqués
- **Seminaire** : Séminaire principal multi-jours
- **SessionSeminaire** : Sessions individuelles (matin/soir)
- **InvitationSeminaire** : Invitations des candidats
- **PresenceSeminaire** : Présences et émargements
- **LivrableSeminaire** : Livrables à rendre
- **RenduLivrable** : Rendu des candidats
- **Programme** : Programme de coaching associé
- **Inscription** : Inscription du candidat
- **Candidat** : Informations du candidat

---

## 2. ROUTES ET PIPELINES

### 2.1 Liste des Séminaires

**Route** : `GET /seminaires`
**Nom** : `liste_seminaires`
**Template** : `seminaires/liste.html`

#### Pipeline Complet

1. **Déclenchement** : Accès à la page de gestion des séminaires
2. **Route déclenchée** : `liste_seminaires`
3. **Variables calculées** :
   ```python
   # Construction des filtres
   filters = {}
   if programme_id:
       filters['programme_id'] = programme_id
   
   # Récupération des séminaires
   seminaires = seminaire_service.get_seminaires(db, filters)
   
   # Statistiques globales
   stats = seminaire_service.get_seminaire_stats(db)
   
   # Programmes pour le filtre
   programmes = db.exec(select(Programme).where(Programme.actif == True)).all()
   ```
4. **Modèles interrogés** :
   - `Seminaire` : Séminaires avec filtres
   - `Programme` : Programmes actifs pour filtrage
   - `SessionSeminaire` : Sessions pour statistiques
   - `PresenceSeminaire` : Présences pour calculs
5. **Validation schématique** :
   - **Filtres optionnels** : Programme, statut, organisateur, dates
   - **Tri par date** : Séminaires les plus récents en premier
6. **Services appelés** :
   - **SeminaireService** : `get_seminaires()` pour liste filtrée
   - **SeminaireService** : `get_seminaire_stats()` pour métriques
7. **Transmission** : Template avec liste et statistiques
8. **Affichage** : Liste des séminaires avec filtres et KPIs

#### Fonctionnalités de la Liste

**Filtres disponibles** :
- **Par programme** : Sélection du programme de coaching
- **Par statut** : Planifié, en cours, terminé
- **Par organisateur** : Filtrage par organisateur
- **Par période** : Date de début et fin
- **Par statut actif** : Séminaires actifs/inactifs

**Statistiques affichées** :
- **Total des séminaires** : Nombre total
- **Par statut** : Planifiés, en cours, terminés
- **Total participants** : Nombre total d'invités
- **Taux de présence moyen** : Pourcentage moyen de présence

### 2.2 Formulaire de Création de Séminaire

**Route** : `GET /seminaires/nouveau`
**Nom** : `form_seminaire`
**Template** : `seminaires/nouveau.html`

#### Pipeline Complet

1. **Déclenchement** : Clic sur "Nouveau séminaire"
2. **Route déclenchée** : `nouveau_seminaire_form`
3. **Variables calculées** :
   ```python
   # Récupération des programmes disponibles
   programmes = db.exec(select(Programme)).all()
   ```
4. **Modèles interrogés** :
   - `Programme` : Programmes disponibles pour association
5. **Validation schématique** : Aucune (préparation des données)
6. **Services appelés** : Aucun (préparation des données)
7. **Transmission** : Template avec formulaire et programmes
8. **Affichage** : Formulaire de création avec sélection programme

### 2.3 Création de Séminaire

**Route** : `POST /seminaires/nouveau`
**Nom** : `creer_seminaire`
**Redirection** : `/seminaires/{seminaire_id}`

#### Pipeline Complet

1. **Déclenchement** : Soumission du formulaire de création
2. **Route déclenchée** : `creer_seminaire`
3. **Variables calculées** :
   ```python
   # Préparation des données
   seminaire_data = SeminaireCreate(
       titre=titre,
       description=description,
       programme_id=programme_id,
       date_debut=date_debut,
       date_fin=date_fin,
       lieu=lieu,
       adresse_complete=adresse_complete,
       organisateur_id=current_user.id,
       capacite_max=capacite_max,
       invitation_auto=invitation_auto,
       invitation_promos=invitation_promos
   )
   ```
4. **Modèles interrogés** :
   - `Seminaire` : Création du nouvel enregistrement
5. **Validation schématique** :
   - **Champs obligatoires** : Titre, programme, dates
   - **Dates cohérentes** : Date de fin >= date de début
   - **Capacité** : Nombre maximum de participants
6. **Services appelés** :
   - **SeminaireService** : `create_seminaire()` pour création
7. **Transmission** : Redirection vers la page de détail
8. **Affichage** : Page de détail du nouveau séminaire

### 2.4 Détail d'un Séminaire

**Route** : `GET /seminaires/{seminaire_id}`
**Nom** : `detail_seminaire`
**Template** : `seminaires/detail.html`

#### Pipeline Complet

1. **Déclenchement** : Clic sur un séminaire dans la liste
2. **Route déclenchée** : `detail_seminaire`
3. **Variables calculées** :
   ```python
   # Récupération des données complètes
   seminaire = seminaire_service.get_seminaire(seminaire_id, db)
   sessions = seminaire_service.get_sessions_seminaire(seminaire_id, db)
   invitations = seminaire_service.get_invitations_seminaire(seminaire_id, db)
   livrables = seminaire_service.get_livrables_seminaire(seminaire_id, db)
   ```
4. **Modèles interrogés** :
   - `Seminaire` : Séminaire principal
   - `SessionSeminaire` : Sessions du séminaire
   - `InvitationSeminaire` : Invitations envoyées
   - `LivrableSeminaire` : Livrables à rendre
5. **Validation schématique** :
   - **Existence du séminaire** : Vérification de l'existence
6. **Services appelés** :
   - **SeminaireService** : `get_seminaire()` pour données principales
   - **SeminaireService** : `get_sessions_seminaire()` pour sessions
   - **SeminaireService** : `get_invitations_seminaire()` pour invitations
   - **SeminaireService** : `get_livrables_seminaire()` pour livrables
7. **Transmission** : Template avec données complètes
8. **Affichage** : Page de détail avec onglets (sessions, invitations, livrables)

### 2.5 Création de Session

**Route** : `GET /seminaires/{seminaire_id}/sessions/nouvelle`
**Nom** : `nouvelle_session_seminaire`
**Template** : `seminaires/session_nouvelle.html`

#### Pipeline Complet

1. **Déclenchement** : Clic sur "Nouvelle session"
2. **Route déclenchée** : `nouvelle_session_form`
3. **Variables calculées** :
   ```python
   # Vérification du séminaire
   seminaire = seminaire_service.get_seminaire(seminaire_id, db)
   ```
4. **Modèles interrogés** :
   - `Seminaire` : Séminaire parent
5. **Validation schématique** :
   - **Existence du séminaire** : Vérification de l'existence
6. **Services appelés** :
   - **SeminaireService** : `get_seminaire()` pour vérification
7. **Transmission** : Template avec formulaire de session
8. **Affichage** : Formulaire de création de session

### 2.6 Création de Session (POST)

**Route** : `POST /seminaires/{seminaire_id}/sessions/nouvelle`
**Nom** : `creer_session_seminaire`
**Redirection** : `/seminaires/{seminaire_id}`

#### Pipeline Complet

1. **Déclenchement** : Soumission du formulaire de session
2. **Route déclenchée** : `creer_session`
3. **Variables calculées** :
   ```python
   # Combinaison date et heure
   heure_debut_time = datetime.strptime(heure_debut, "%H:%M").time()
   heure_fin_time = datetime.strptime(heure_fin, "%H:%M").time() if heure_fin else None
   
   datetime_debut = datetime.combine(date_session, heure_debut_time)
   datetime_fin = datetime.combine(date_session, heure_fin_time) if heure_fin_time else None
   
   # Préparation des données
   session_data = SessionSeminaireCreate(
       seminaire_id=seminaire_id,
       titre=titre,
       description=description,
       date_session=date_session,
       heure_debut=datetime_debut,
       heure_fin=datetime_fin,
       lieu=lieu,
       visioconf_url=visioconf_url,
       capacite=capacite,
       obligatoire=obligatoire
   )
   ```
4. **Modèles interrogés** :
   - `SessionSeminaire` : Création de la nouvelle session
5. **Validation schématique** :
   - **Conversion des heures** : Format HH:MM vers datetime
   - **Cohérence temporelle** : Heure de fin >= heure de début
   - **Champs obligatoires** : Titre, date, heure de début
6. **Services appelés** :
   - **SeminaireService** : `create_session()` pour création
7. **Transmission** : Redirection vers la page de détail
8. **Affichage** : Page de détail mise à jour avec la nouvelle session

---

## 3. GESTION DES INVITATIONS

### 3.1 Page de Gestion des Invitations

**Route** : `GET /seminaires/{seminaire_id}/invitations`
**Nom** : `invitations_seminaire`
**Template** : `seminaires/invitations.html`

#### Pipeline Complet

1. **Déclenchement** : Clic sur "Invitations" dans le détail
2. **Route déclenchée** : `invitations_seminaire`
3. **Variables calculées** :
   ```python
   # Récupération du séminaire
   seminaire = seminaire_service.get_seminaire(seminaire_id, db)
   
   # Récupération des invitations existantes
   invitations = seminaire_service.get_invitations_seminaire(seminaire_id, db)
   
   # Récupération des candidats disponibles
   invitations_query = select(InvitationSeminaire.inscription_id).where(
       InvitationSeminaire.seminaire_id == seminaire_id
   )
   inscriptions_invitees = db.exec(invitations_query).all()
   
   # Candidats non encore invités
   inscriptions_query = select(Inscription).join(Candidat).where(
       Inscription.programme_id == seminaire.programme_id
   )
   if inscriptions_invitees:
       inscriptions_query = inscriptions_query.where(
           Inscription.id.notin_(inscriptions_invitees)
       )
   inscriptions = db.exec(inscriptions_query).all()
   ```
4. **Modèles interrogés** :
   - `Seminaire` : Séminaire concerné
   - `InvitationSeminaire` : Invitations existantes
   - `Inscription` : Inscriptions du programme
   - `Candidat` : Candidats associés
5. **Validation schématique** :
   - **Exclusion des doublons** : Candidats déjà invités exclus
   - **Filtrage par programme** : Seuls les candidats du programme
6. **Services appelés** :
   - **SeminaireService** : `get_invitations_seminaire()` pour invitations
7. **Transmission** : Template avec invitations et candidats disponibles
8. **Affichage** : Interface de gestion des invitations

### 3.2 Envoi d'Invitations

**Route** : `POST /seminaires/{seminaire_id}/invitations/envoyer`
**Nom** : `envoyer_invitations_seminaire`
**Redirection** : `/seminaires/{seminaire_id}/invitations`

#### Pipeline Complet

1. **Déclenchement** : Soumission du formulaire d'invitations
2. **Route déclenchée** : `envoyer_invitations`
3. **Variables calculées** :
   ```python
   # Conversion du type d'invitation
   type_inv = TypeInvitation(type_invitation)
   
   # Envoi en masse
   invitations = seminaire_service.send_invitations_bulk(
       seminaire_id, type_inv, candidats_ids, db
   )
   ```
4. **Modèles interrogés** :
   - `InvitationSeminaire` : Création des invitations
   - `Seminaire` : Informations pour email
   - `Inscription` : Données des candidats
   - `Candidat` : Emails des candidats
5. **Validation schématique** :
   - **Type d'invitation** : Individuelle ou par promotion
   - **IDs candidats** : Liste des candidats sélectionnés
6. **Services appelés** :
   - **SeminaireService** : `send_invitations_bulk()` pour envoi
   - **EmailService** : Envoi des emails d'invitation
7. **Transmission** : Redirection vers la page d'invitations
8. **Affichage** : Page d'invitations mise à jour

#### Processus d'Envoi

**Étapes d'invitation** :
1. **Création des invitations** : Enregistrement en base avec tokens
2. **Génération des tokens** : Tokens uniques pour chaque invitation
3. **Envoi des emails** : Emails avec liens d'acceptation/refus
4. **Mise à jour des statuts** : Statut "ENVOYEE" et date d'envoi

---

## 4. SYSTÈME D'ÉMARGEMENT

### 4.1 Génération des Liens d'Émargement

**Route** : `GET /seminaires/{seminaire_id}/sessions/{session_id}/emargement/liens`
**Nom** : `generer_liens_emargement`
**Template** : `seminaires/generer_liens_emargement.html`

#### Pipeline Complet

1. **Déclenchement** : Clic sur "Générer liens d'émargement"
2. **Route déclenchée** : `generer_liens_emargement`
3. **Variables calculées** :
   ```python
   # Vérification du séminaire et de la session
   seminaire = seminaire_service.get_seminaire(seminaire_id, db)
   session = seminaire_service.get_session(session_id, db)
   
   # Récupération des invitations
   invitations = seminaire_service.get_invitations_seminaire(seminaire_id, db)
   ```
4. **Modèles interrogés** :
   - `Seminaire` : Séminaire concerné
   - `SessionSeminaire` : Session concernée
   - `InvitationSeminaire` : Invitations avec tokens
5. **Validation schématique** :
   - **Existence des entités** : Vérification séminaire et session
6. **Services appelés** :
   - **SeminaireService** : `get_seminaire()` et `get_session()`
   - **SeminaireService** : `get_invitations_seminaire()` pour invitations
7. **Transmission** : Template avec invitations et liens
8. **Affichage** : Interface de génération des liens

### 4.2 Envoi des Liens d'Émargement

**Route** : `POST /seminaires/{seminaire_id}/sessions/{session_id}/emargement/liens/envoyer`
**Nom** : `envoyer_liens_emargement`
**Redirection** : `/seminaires/{seminaire_id}/sessions/{session_id}/emargement`

#### Pipeline Complet

1. **Déclenchement** : Soumission du formulaire d'envoi de liens
2. **Route déclenchée** : `envoyer_liens_emargement`
3. **Variables calculées** :
   ```python
   # Récupération des invitations sélectionnées
   invitations = []
   for invitation_id in invitation_ids:
       invitation = seminaire_service.get_invitation(invitation_id, db)
       if invitation:
           invitations.append(invitation)
   
   # Génération des URLs d'émargement
   base_url = settings.get_base_url_for_email()
   emargement_url = f"{base_url}/seminaires/{seminaire_id}/sessions/{session_id}/emargement/lien/{invitation.token_invitation}"
   
   # Envoi des emails
   for invitation in invitations:
       seminaire_service.email_service.send_template_email(
           to_email=invitation.inscription.candidat.email,
           subject=f"Lien d'émargement - {invitation.seminaire.titre}",
           template="emargement_lien",
           data=template_data
       )
   ```
4. **Modèles interrogés** :
   - `InvitationSeminaire` : Invitations sélectionnées
   - `Seminaire` : Informations pour email
   - `SessionSeminaire` : Informations de session
   - `Candidat` : Emails des candidats
5. **Validation schématique** :
   - **Sélection des invitations** : Vérification des IDs
   - **Génération des URLs** : URLs uniques par token
6. **Services appelés** :
   - **SeminaireService** : `get_invitation()` pour récupération
   - **EmailService** : Envoi des emails avec liens
7. **Transmission** : Redirection vers la page d'émargement
8. **Affichage** : Page d'émargement mise à jour

### 4.3 Émargement via Lien

**Route** : `GET /seminaires/{seminaire_id}/sessions/{session_id}/emargement/lien/{token}`
**Nom** : `emargement_lien`
**Template** : `seminaires/emargement_lien.html`

#### Pipeline Complet

1. **Déclenchement** : Clic sur un lien d'émargement dans un email
2. **Route déclenchée** : `emargement_lien`
3. **Variables calculées** :
   ```python
   # Vérification du token
   invitation = seminaire_service.get_invitation_by_token(token, db)
   
   # Vérification de la session
   session = seminaire_service.get_session(session_id, db)
   
   # Vérification de la présence existante
   presence = seminaire_service.get_presence_candidat(session_id, invitation.inscription_id, db)
   ```
4. **Modèles interrogés** :
   - `InvitationSeminaire` : Invitation par token
   - `SessionSeminaire` : Session concernée
   - `PresenceSeminaire` : Présence existante
5. **Validation schématique** :
   - **Token valide** : Vérification de l'existence du token
   - **Cohérence séminaire** : Token correspond au séminaire
   - **Session existante** : Vérification de la session
6. **Services appelés** :
   - **SeminaireService** : `get_invitation_by_token()` pour validation
   - **SeminaireService** : `get_session()` pour session
   - **SeminaireService** : `get_presence_candidat()` pour présence
7. **Transmission** : Template avec données d'émargement
8. **Affichage** : Page d'émargement avec formulaire de signature

### 4.4 Signature d'Émargement

**Route** : `POST /seminaires/{seminaire_id}/sessions/{session_id}/emargement/lien/{token}`
**Nom** : `signer_emargement_lien`
**Template** : `seminaires/emargement_confirmation.html`

#### Pipeline Complet

1. **Déclenchement** : Soumission du formulaire d'émargement
2. **Route déclenchée** : `signer_emargement_lien`
3. **Variables calculées** :
   ```python
   # Vérification du token
   invitation = seminaire_service.get_invitation_by_token(token, db)
   
   # Préparation des données selon la méthode
   signature_manuelle = None
   signature_digitale = None
   
   if methode_signature == "manuel":
       signature_manuelle = nom_signature
   elif methode_signature == "digital":
       signature_digitale = signature_data
   
   # Création de la présence
   presence_data = PresenceSeminaireCreate(
       session_id=session_id,
       inscription_id=invitation.inscription_id,
       presence="present",
       heure_arrivee=datetime.now(timezone.utc),
       methode_signature=MethodeSignature(methode_signature),
       signature_manuelle=signature_manuelle,
       signature_digitale=signature_digitale,
       photo_signature=photo_data,
       commentaire=commentaire,
       ip_signature=request.client.host
   )
   ```
4. **Modèles interrogés** :
   - `InvitationSeminaire` : Validation du token
   - `PresenceSeminaire` : Création/mise à jour de la présence
5. **Validation schématique** :
   - **Token valide** : Vérification de l'existence
   - **Méthode de signature** : Manuelle ou digitale
   - **Données de signature** : Signature et photo requises
6. **Services appelés** :
   - **SeminaireService** : `get_invitation_by_token()` pour validation
   - **SeminaireService** : `mark_presence()` pour enregistrement
7. **Transmission** : Template de confirmation
8. **Affichage** : Page de confirmation d'émargement

---

## 5. GESTION DES LIVRABLES

### 5.1 Page de Gestion des Livrables

**Route** : `GET /seminaires/{seminaire_id}/livrables`
**Nom** : `livrables_seminaire`
**Template** : `seminaires/livrables.html`

#### Pipeline Complet

1. **Déclenchement** : Clic sur "Livrables" dans le détail
2. **Route déclenchée** : `livrables_seminaire`
3. **Variables calculées** :
   ```python
   # Récupération du séminaire
   seminaire = seminaire_service.get_seminaire(seminaire_id, db)
   
   # Récupération des livrables
   livrables = seminaire_service.get_livrables_seminaire(seminaire_id, db)
   ```
4. **Modèles interrogés** :
   - `Seminaire` : Séminaire concerné
   - `LivrableSeminaire` : Livrables du séminaire
5. **Validation schématique** :
   - **Existence du séminaire** : Vérification de l'existence
6. **Services appelés** :
   - **SeminaireService** : `get_seminaire()` pour vérification
   - **SeminaireService** : `get_livrables_seminaire()` pour livrables
7. **Transmission** : Template avec livrables
8. **Affichage** : Interface de gestion des livrables

### 5.2 Création de Livrable

**Route** : `POST /seminaires/{seminaire_id}/livrables/nouveau`
**Nom** : `creer_livrable_seminaire`
**Redirection** : `/seminaires/{seminaire_id}/livrables`

#### Pipeline Complet

1. **Déclenchement** : Soumission du formulaire de livrable
2. **Route déclenchée** : `creer_livrable`
3. **Variables calculées** :
   ```python
   # Conversion de la taille maximale
   taille_max_mb_value = None
   if taille_max_mb and taille_max_mb.strip():
       try:
           taille_max_mb_value = int(taille_max_mb)
       except ValueError:
           taille_max_mb_value = None
   
   # Préparation des données
   livrable_data = LivrableSeminaireCreate(
       seminaire_id=seminaire_id,
       titre=titre,
       description=description,
       type_livrable=type_livrable,
       obligatoire=obligatoire,
       date_limite=date_limite,
       consignes=consignes,
       format_accepte=format_accepte,
       taille_max_mb=taille_max_mb_value
   )
   ```
4. **Modèles interrogés** :
   - `LivrableSeminaire` : Création du livrable
5. **Validation schématique** :
   - **Champs obligatoires** : Titre et type de livrable
   - **Conversion numérique** : Taille maximale en MB
   - **Date limite** : Date optionnelle de rendu
6. **Services appelés** :
   - **SeminaireService** : `create_livrable()` pour création
7. **Transmission** : Redirection vers la page des livrables
8. **Affichage** : Page des livrables mise à jour

### 5.3 Rendu de Livrable par Candidat

**Route** : `POST /seminaires/{seminaire_id}/livrables/{livrable_id}/rendre`
**Nom** : `rendre_livrable_seminaire`
**Redirection** : `/seminaires/{seminaire_id}/livrables`

#### Pipeline Complet

1. **Déclenchement** : Soumission d'un fichier de livrable
2. **Route déclenchée** : `rendre_livrable`
3. **Variables calculées** :
   ```python
   # Vérification du fichier
   if not fichier.filename:
       raise HTTPException(status_code=400, detail="Aucun fichier fourni")
   
   # Création du répertoire de stockage
   subfolder = f"seminaires/{seminaire_id}/livrables"
   
   # Génération d'un nom unique
   file_extension = os.path.splitext(fichier.filename)[1]
   unique_filename = f"{uuid.uuid4()}{file_extension}"
   
   # Sauvegarde du fichier
   file_info = await FileUploadService.save_file(
       fichier, "media", unique_filename, subfolder=subfolder
   )
   
   # Création du rendu
   file_data = {
       'nom_fichier': fichier.filename,
       'chemin_fichier': file_info["relative_path"],
       'taille_fichier': file_info["size"],
       'type_mime': fichier.content_type or 'application/octet-stream',
       'commentaire_candidat': commentaire
   }
   ```
4. **Modèles interrogés** :
   - `RenduLivrable` : Création du rendu
   - `LivrableSeminaire` : Livrable concerné
5. **Validation schématique** :
   - **Fichier requis** : Vérification de la présence du fichier
   - **Nom unique** : Génération d'un nom de fichier unique
   - **Stockage sécurisé** : Sauvegarde dans un répertoire dédié
6. **Services appelés** :
   - **FileUploadService** : Sauvegarde du fichier
   - **SeminaireService** : `submit_livrable()` pour enregistrement
7. **Transmission** : Redirection vers la page des livrables
8. **Affichage** : Page des livrables mise à jour

---

## 6. SERVICES MÉTIER

### 6.1 Service de Séminaires (`SeminaireService`)

**Fichier** : `app/services/seminaire_service.py`
**Description** : Service principal pour la gestion des séminaires

#### Méthodes Principales

**`create_seminaire()`** :
```python
def create_seminaire(self, seminaire_data: SeminaireCreate, db: Session) -> Seminaire:
    """Créer un nouveau séminaire"""
    seminaire = Seminaire(**seminaire_data.dict())
    db.add(seminaire)
    db.commit()
    db.refresh(seminaire)
    return seminaire
```

**`send_invitations_bulk()`** :
```python
def send_invitations_bulk(self, seminaire_id: int, type_invitation: TypeInvitation, 
                         target_ids: List[int], db: Session) -> List[InvitationSeminaire]:
    """Envoyer des invitations en masse"""
    invitations = []
    
    for target_id in target_ids:
        invitation_data = {
            'seminaire_id': seminaire_id,
            'type_invitation': type_invitation,
            'token_invitation': self._generate_invitation_token()
        }
        
        if type_invitation == TypeInvitation.INDIVIDUELLE:
            invitation_data['inscription_id'] = target_id
        elif type_invitation == TypeInvitation.PROMOTION:
            invitation_data['promotion_id'] = target_id
        
        invitation = InvitationSeminaire(**invitation_data)
        db.add(invitation)
        invitations.append(invitation)
    
    db.commit()
    
    # Envoyer les emails d'invitation
    for invitation in invitations:
        self._send_invitation_email(invitation, db)
    
    return invitations
```

**`mark_presence()`** :
```python
def mark_presence(self, presence_data: PresenceSeminaireCreate, db: Session) -> PresenceSeminaire:
    """Marquer la présence d'un participant"""
    # Vérifier si une présence existe déjà
    query = select(PresenceSeminaire).where(
        and_(
            PresenceSeminaire.session_id == presence_data.session_id,
            PresenceSeminaire.inscription_id == presence_data.inscription_id
        )
    )
    existing_presence = db.exec(query).first()
    
    if existing_presence:
        # Mettre à jour la présence existante
        for field, value in presence_data.dict().items():
            if field not in ['session_id', 'inscription_id']:
                setattr(existing_presence, field, value)
        
        # Enregistrer l'heure d'arrivée si c'est la première fois qu'on marque "present"
        if presence_data.presence == "present" and not existing_presence.heure_arrivee:
            existing_presence.heure_arrivee = datetime.now(timezone.utc)
        
        existing_presence.modifie_le = datetime.now(timezone.utc)
        db.commit()
        db.refresh(existing_presence)
        return existing_presence
    else:
        # Créer une nouvelle présence
        presence = PresenceSeminaire(**presence_data.dict())
        
        # Enregistrer l'heure d'arrivée si on marque "present"
        if presence_data.presence == "present":
            presence.heure_arrivee = datetime.now(timezone.utc)
        
        db.add(presence)
        db.commit()
        db.refresh(presence)
        return presence
```

#### Fonctionnalités Avancées

**Gestion des invitations** :
- **Tokens uniques** : Génération de tokens sécurisés
- **Envoi d'emails** : Templates d'emails avec liens d'acceptation/refus
- **Statuts multiples** : ENVOYEE, ACCEPTEE, REFUSEE, EXPIRED
- **Types d'invitation** : Individuelle ou par promotion

**Système d'émargement** :
- **Signatures multiples** : Manuelle et digitale
- **Traçabilité complète** : IP, User Agent, horodatage
- **Photos de signature** : Capture de la signature
- **Statuts de présence** : Present, Absent, Excuse

**Gestion des livrables** :
- **Upload de fichiers** : Gestion sécurisée des fichiers
- **Types de livrables** : Document, présentation, rapport, autre
- **Contraintes** : Format accepté, taille maximale, date limite
- **Rendu par candidat** : Soumission avec commentaires

---

## 7. VALIDATION ET SÉCURITÉ

### 7.1 Validation des Données

**Validation côté serveur** :
- **Dates cohérentes** : Date de fin >= date de début
- **Heures cohérentes** : Heure de fin >= heure de début
- **Champs obligatoires** : Titre, programme, dates
- **Conversion des types** : Dates, heures, nombres

**Validation côté client** :
- **Champs requis** : Validation HTML5 et JavaScript
- **Format des dates** : Validation des formats de date
- **Taille des fichiers** : Limitation de la taille d'upload
- **Types de fichiers** : Validation des extensions

### 7.2 Sécurité des Accès

**Contrôles de sécurité** :
- **Authentification** : Vérification de l'utilisateur connecté
- **Autorisation** : Vérification des droits d'accès
- **Tokens d'invitation** : Tokens uniques et sécurisés
- **Traçabilité** : Logs des actions et modifications

**Protection des fichiers** :
- **Noms uniques** : Génération d'UUID pour les fichiers
- **Répertoires sécurisés** : Stockage dans des dossiers dédiés
- **Validation des types** : Vérification des types MIME
- **Limitation de taille** : Contrôle de la taille des fichiers

---

## 8. PERFORMANCE ET OPTIMISATION

### 8.1 Optimisation des Requêtes

**Jointures optimisées** :
- **Séminaire + Sessions + Invitations** : Une seule requête
- **Présences avec détails** : Chargement des relations
- **Évitement des N+1** : Chargement en lot des relations

**Cache et sessions** :
- **Sessions de base de données** : Pool de connexions
- **Transactions atomiques** : Rollback en cas d'erreur
- **Refresh automatique** : Récupération des IDs générés

### 8.2 Gestion des Fichiers

**Upload optimisé** :
- **Streaming** : Upload par chunks pour les gros fichiers
- **Validation précoce** : Vérification avant sauvegarde
- **Noms uniques** : Éviter les conflits de noms
- **Répertoires organisés** : Structure claire des dossiers

---

## 9. MONITORING ET LOGS

### 9.1 Logs de Debug

**Informations loggées** :
- **Actions utilisateur** : Création, modification, suppression
- **Envoi d'emails** : Succès et échecs d'envoi
- **Émargements** : Signatures et présences
- **Upload de fichiers** : Succès et échecs d'upload

### 9.2 Métriques de Performance

**KPI calculés** :
- **Total des séminaires** : Comptage global
- **Répartition par statut** : Planifiés, en cours, terminés
- **Taux de présence** : Pourcentage de présence par session
- **Livrables rendus** : Nombre de rendus par livrable

---

## 10. ÉVOLUTION ET MAINTENANCE

### 10.1 Ajout de Nouveaux Types de Sessions

**Processus d'ajout** :
1. **Modification de l'enum** : Ajout du nouveau type dans TypeSession
2. **Mise à jour du service** : Adaptation du service
3. **Mise à jour de l'interface** : Ajout dans les formulaires
4. **Tests** : Validation avec des cas de test

### 10.2 Modification des Statuts

**Processus de modification** :
1. **Mise à jour de l'enum** : Modification des statuts
2. **Mise à jour des statistiques** : Adaptation des calculs
3. **Mise à jour de l'interface** : Adaptation des formulaires
4. **Migration des données** : Mise à jour des données existantes

---

*Document généré automatiquement - Pipeline de gestion des séminaires LIA WEB*
