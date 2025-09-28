# PIPELINE DE GESTION DES ÉVÉNEMENTS - LIA WEB

Ce document détaille le pipeline complet de gestion des événements dans l'application LIA WEB, incluant les routes, templates, services et processus métier pour la planification, gestion et suivi des événements ponctuels avec invitations, émargements et statistiques.

## Vue d'ensemble

Le système d'événements permet aux organisateurs de créer des événements ponctuels, d'inviter des candidats, de gérer les présences via émargement numérique ou direct, et de suivre les statistiques de participation.

---

## 1. ARCHITECTURE GÉNÉRALE

### Technologies Utilisées
- **Backend** : FastAPI avec SQLModel
- **Frontend** : Jinja2 templates avec JavaScript interactif
- **Base de données** : PostgreSQL avec relations complexes
- **Services métier** : EventService pour la logique métier
- **Émargement** : Système de signatures numériques et manuelles
- **Email** : Service d'envoi d'emails avec templates
- **Statuts combinés** : Logique métier pour statuts d'invitation et présence

### Modèles Impliqués
- **Event** : Événement principal ponctuel
- **InvitationEvent** : Invitations des candidats
- **PresenceEvent** : Présences et émargements
- **Programme** : Programme de coaching associé
- **Inscription** : Inscription du candidat
- **Candidat** : Informations du candidat
- **User** : Organisateur de l'événement

---

## 2. ROUTES ET PIPELINES

### 2.1 Liste des Événements

**Route** : `GET /events`
**Nom** : `liste_events`
**Template** : `events/liste.html`

#### Pipeline Complet

1. **Déclenchement** : Accès à la page de gestion des événements
2. **Route déclenchée** : `liste_events`
3. **Variables calculées** :
   ```python
   # Récupération des événements avec filtres
   events = event_service.get_events(db, programme_id=programme_id)
   
   # Statistiques globales
   stats = event_service.get_event_stats(db)
   
   # Programmes pour le filtre
   programmes = db.exec(select(Programme).where(Programme.actif == True)).all()
   ```
4. **Modèles interrogés** :
   - `Event` : Événements avec filtres
   - `Programme` : Programmes actifs pour filtrage
5. **Validation schématique** :
   - **Filtres optionnels** : Programme, pagination
   - **Tri par date** : Événements les plus récents en premier
6. **Services appelés** :
   - **EventService** : `get_events()` pour liste filtrée
   - **EventService** : `get_event_stats()` pour métriques
7. **Transmission** : Template avec liste et statistiques
8. **Affichage** : Liste des événements avec filtres et KPIs

#### Fonctionnalités de la Liste

**Filtres disponibles** :
- **Par programme** : Sélection du programme de coaching
- **Pagination** : Limite et offset pour les grandes listes

**Statistiques affichées** :
- **Total des événements** : Nombre total
- **Par statut** : Planifiés, en cours, terminés
- **Répartition** : Distribution des statuts

### 2.2 Formulaire de Création d'Événement

**Route** : `GET /events/nouveau`
**Nom** : `form_event`
**Template** : `events/form.html`

#### Pipeline Complet

1. **Déclenchement** : Clic sur "Nouvel événement"
2. **Route déclenchée** : `form_event`
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

### 2.3 Création d'Événement

**Route** : `POST /events/nouveau`
**Nom** : `creer_event`
**Redirection** : `/events/{event_id}`

#### Pipeline Complet

1. **Déclenchement** : Soumission du formulaire de création
2. **Route déclenchée** : `creer_event`
3. **Variables calculées** :
   ```python
   # Conversion des heures
   heure_debut_dt = None
   heure_fin_dt = None
   
   if heure_debut:
       heure_debut_dt = datetime.strptime(f"{date_debut} {heure_debut}", "%Y-%m-%d %H:%M")
   
   if heure_fin:
       heure_fin_dt = datetime.strptime(f"{date_fin} {heure_fin}", "%Y-%m-%d %H:%M")
   
   # Préparation des données
   event_data = EventCreate(
       titre=titre,
       description=description if description else None,
       date_debut=date_debut,
       date_fin=date_fin,
       heure_debut=heure_debut_dt,
       heure_fin=heure_fin_dt,
       lieu=lieu if lieu else None,
       programme_id=programme_id,
       organisateur_id=current_user.id
   )
   ```
4. **Modèles interrogés** :
   - `Event` : Création du nouvel enregistrement
5. **Validation schématique** :
   - **Champs obligatoires** : Titre, programme, dates
   - **Conversion des heures** : Format datetime avec gestion d'erreurs
   - **Dates cohérentes** : Date de fin >= date de début
6. **Services appelés** :
   - **EventService** : `create_event()` pour création
7. **Transmission** : Redirection vers la page de détail
8. **Affichage** : Page de détail du nouvel événement

### 2.4 Détail d'un Événement

**Route** : `GET /events/{event_id}`
**Nom** : `detail_event`
**Template** : `events/detail.html`

#### Pipeline Complet

1. **Déclenchement** : Clic sur un événement dans la liste
2. **Route déclenchée** : `detail_event`
3. **Variables calculées** :
   ```python
   # Récupération de l'événement
   event = event_service.get_event(event_id, db)
   
   # Récupération des présences avec statuts combinés
   presences_data = event_service.get_presences_with_combined_status(event_id, db)
   
   # Statistiques de présence
   stats = event_service.get_presence_stats_with_invitations(event_id, db)
   ```
4. **Modèles interrogés** :
   - `Event` : Événement principal
   - `InvitationEvent` : Invitations envoyées
   - `PresenceEvent` : Présences enregistrées
5. **Validation schématique** :
   - **Existence de l'événement** : Vérification de l'existence
6. **Services appelés** :
   - **EventService** : `get_event()` pour données principales
   - **EventService** : `get_presences_with_combined_status()` pour statuts combinés
   - **EventService** : `get_presence_stats_with_invitations()` pour métriques
7. **Transmission** : Template avec données complètes
8. **Affichage** : Page de détail avec présences et statistiques

#### Logique des Statuts Combinés

**Statuts selon la temporalité** :
- **Avant l'événement** : Privilégie le statut d'invitation (en_attente, acceptee, refusee)
- **Après l'événement** : Privilégie le statut de présence (present, absent, excuse)
- **Transition automatique** : Passage de "en_attente" à "absent" après la date

### 2.5 Modification d'Événement

**Route** : `GET /events/{event_id}/edit`
**Nom** : `edit_event`
**Template** : `events/edit.html`

#### Pipeline Complet

1. **Déclenchement** : Clic sur "Modifier" dans le détail
2. **Route déclenchée** : `edit_event`
3. **Variables calculées** :
   ```python
   # Récupération de l'événement
   event = event_service.get_event(event_id, db)
   
   # Programmes pour la sélection
   programmes = db.exec(select(Programme)).all()
   ```
4. **Modèles interrogés** :
   - `Event` : Événement à modifier
   - `Programme` : Programmes disponibles
5. **Validation schématique** :
   - **Existence de l'événement** : Vérification de l'existence
6. **Services appelés** :
   - **EventService** : `get_event()` pour récupération
7. **Transmission** : Template avec formulaire pré-rempli
8. **Affichage** : Formulaire d'édition avec données existantes

### 2.6 Mise à Jour d'Événement

**Route** : `POST /events/{event_id}/update`
**Nom** : `update_event`
**Redirection** : `/events/{event_id}`

#### Pipeline Complet

1. **Déclenchement** : Soumission du formulaire de modification
2. **Route déclenchée** : `update_event`
3. **Variables calculées** :
   ```python
   # Conversion des heures
   heure_debut_dt = None
   heure_fin_dt = None
   
   if heure_debut:
       heure_debut_dt = datetime.strptime(f"{date_debut} {heure_debut}", "%Y-%m-%d %H:%M")
   
   if heure_fin:
       heure_fin_dt = datetime.strptime(f"{date_fin} {heure_fin}", "%Y-%m-%d %H:%M")
   
   # Préparation des données de mise à jour
   update_data = EventUpdate(
       titre=titre,
       description=description if description else None,
       date_debut=date_debut,
       date_fin=date_fin,
       heure_debut=heure_debut_dt,
       heure_fin=heure_fin_dt,
       lieu=lieu if lieu else None,
       programme_id=programme_id,
       statut=statut
   )
   ```
4. **Modèles interrogés** :
   - `Event` : Événement à modifier
5. **Validation schématique** :
   - **Existence de l'événement** : Vérification de l'existence
   - **Conversion des heures** : Format datetime avec gestion d'erreurs
   - **Statut valide** : Vérification du statut
6. **Services appelés** :
   - **EventService** : `update_event()` pour mise à jour
7. **Transmission** : Redirection vers la page de détail
8. **Affichage** : Page de détail mise à jour

---

## 3. GESTION DES INVITATIONS

### 3.1 Page de Gestion des Invitations

**Route** : `GET /events/{event_id}/invitations`
**Nom** : `invitations_event`
**Template** : `events/invitations.html`

#### Pipeline Complet

1. **Déclenchement** : Clic sur "Invitations" dans le détail
2. **Route déclenchée** : `invitations_event`
3. **Variables calculées** :
   ```python
   # Récupération de l'événement
   event = event_service.get_event(event_id, db)
   
   # Récupération des invitations existantes
   invitations = event_service.get_invitations_by_event(event_id, db)
   
   # Récupération des candidats disponibles
   inscriptions = db.exec(
       select(Inscription)
       .join(Candidat)
       .where(Inscription.programme_id == event.programme_id)
   ).all()
   ```
4. **Modèles interrogés** :
   - `Event` : Événement concerné
   - `InvitationEvent` : Invitations existantes
   - `Inscription` : Inscriptions du programme
   - `Candidat` : Candidats associés
5. **Validation schématique** :
   - **Existence de l'événement** : Vérification de l'existence
   - **Filtrage par programme** : Seuls les candidats du programme
6. **Services appelés** :
   - **EventService** : `get_event()` pour vérification
   - **EventService** : `get_invitations_by_event()` pour invitations
7. **Transmission** : Template avec invitations et candidats disponibles
8. **Affichage** : Interface de gestion des invitations

### 3.2 Envoi d'Invitations

**Route** : `POST /events/{event_id}/invitations/envoyer`
**Nom** : `envoyer_invitations_event`
**Redirection** : `/events/{event_id}/invitations`

#### Pipeline Complet

1. **Déclenchement** : Soumission du formulaire d'invitations
2. **Route déclenchée** : `envoyer_invitations_event`
3. **Variables calculées** :
   ```python
   # Conversion du type d'invitation
   type_inv = TypeInvitation(type_invitation)
   
   # Envoi en masse
   invitations = event_service.send_invitations_bulk(event_id, type_inv, candidats_ids, db)
   ```
4. **Modèles interrogés** :
   - `InvitationEvent` : Création des invitations
   - `Event` : Informations pour email
   - `Inscription` : Données des candidats
   - `Candidat` : Emails des candidats
5. **Validation schématique** :
   - **Type d'invitation** : Individuelle ou par groupe
   - **IDs candidats** : Liste des candidats sélectionnés
6. **Services appelés** :
   - **EventService** : `send_invitations_bulk()` pour envoi
   - **EmailService** : Envoi des emails d'invitation
7. **Transmission** : Redirection vers la page d'invitations
8. **Affichage** : Page d'invitations mise à jour

#### Processus d'Envoi

**Étapes d'invitation** :
1. **Création des invitations** : Enregistrement en base avec tokens
2. **Génération des tokens** : Tokens uniques pour chaque invitation
3. **Envoi des emails** : Emails avec liens d'acceptation/refus
4. **Mise à jour des statuts** : Statut "en_attente" et date d'envoi

---

## 4. SYSTÈME D'ÉMARGEMENT

### 4.1 Émargement Direct (Mode Tablette)

**Route** : `GET /events/{event_id}/emargement-direct`
**Nom** : `emargement_direct_event`
**Template** : `events/emargement_direct.html`

#### Pipeline Complet

1. **Déclenchement** : Accès à la page d'émargement direct
2. **Route déclenchée** : `emargement_direct_event`
3. **Variables calculées** :
   ```python
   # Récupération de l'événement
   event = event_service.get_event(event_id, db)
   
   # Récupération des présences avec invitations
   presences = event_service.get_presences_with_invitations(event_id, db)
   ```
4. **Modèles interrogés** :
   - `Event` : Événement concerné
   - `InvitationEvent` : Invitations avec présences
   - `PresenceEvent` : Présences existantes
5. **Validation schématique** :
   - **Existence de l'événement** : Vérification de l'existence
6. **Services appelés** :
   - **EventService** : `get_event()` pour vérification
   - **EventService** : `get_presences_with_invitations()` pour présences
7. **Transmission** : Template avec présences
8. **Affichage** : Interface d'émargement direct avec authentification

### 4.2 Marquage de Présence Direct

**Route** : `POST /events/{event_id}/emargement-direct`
**Nom** : `marquer_presence_event_direct`
**Redirection** : `/events/{event_id}/emargement`

#### Pipeline Complet

1. **Déclenchement** : Soumission du formulaire d'émargement direct
2. **Route déclenchée** : `marquer_presence_event_direct`
3. **Variables calculées** :
   ```python
   # Vérification de l'événement
   event = event_service.get_event(event_id, db)
   
   # Préparation des données de présence
   presence_data = PresenceEventCreate(
       event_id=event_id,
       inscription_id=inscription_id,
       presence=presence,
       methode_signature=methode_signature,
       signature_manuelle=signature_data if methode_signature == "manuel" else None,
       signature_digitale=signature_data if methode_signature == "digital" else None,
       heure_arrivee=datetime.now(timezone.utc),
       commentaire=note if note else None,
       ip_signature=request.client.host
   )
   ```
4. **Modèles interrogés** :
   - `Event` : Vérification de l'existence
   - `PresenceEvent` : Création/mise à jour de la présence
5. **Validation schématique** :
   - **Existence de l'événement** : Vérification de l'existence
   - **Méthode de signature** : Manuelle ou digitale
   - **Données de signature** : Signature requise
6. **Services appelés** :
   - **EventService** : `get_event()` pour vérification
   - **EventService** : `mark_presence()` pour enregistrement
7. **Transmission** : Redirection vers la page d'émargement
8. **Affichage** : Page d'émargement mise à jour

### 4.3 Génération des Liens d'Émargement

**Route** : `GET /events/{event_id}/emargement/liens`
**Nom** : `generer_liens_emargement_event`
**Template** : `events/generer_liens_emargement.html`

#### Pipeline Complet

1. **Déclenchement** : Clic sur "Générer liens d'émargement"
2. **Route déclenchée** : `generer_liens_emargement_event`
3. **Variables calculées** :
   ```python
   # Récupération de l'événement
   event = event_service.get_event(event_id, db)
   
   # Récupération des invitations
   invitations = event_service.get_invitations_by_event(event_id, db)
   ```
4. **Modèles interrogés** :
   - `Event` : Événement concerné
   - `InvitationEvent` : Invitations avec tokens
5. **Validation schématique** :
   - **Existence de l'événement** : Vérification de l'existence
6. **Services appelés** :
   - **EventService** : `get_event()` et `get_invitations_by_event()`
7. **Transmission** : Template avec invitations et liens
8. **Affichage** : Interface de génération des liens

### 4.4 Envoi des Liens d'Émargement

**Route** : `POST /events/{event_id}/emargement/liens/envoyer`
**Nom** : `envoyer_liens_emargement_event`
**Redirection** : `/events/{event_id}/emargement`

#### Pipeline Complet

1. **Déclenchement** : Soumission du formulaire d'envoi de liens
2. **Route déclenchée** : `envoyer_liens_emargement_event`
3. **Variables calculées** :
   ```python
   # Récupération de l'événement
   event = event_service.get_event(event_id, db)
   
   # Récupération des invitations sélectionnées
   invitations = []
   for invitation_id in invitation_ids:
       invitation = db.get(InvitationEvent, invitation_id)
       if invitation and invitation.event_id == event_id:
           invitations.append(invitation)
   
   # Génération des URLs d'émargement
   base_url = settings.get_base_url_for_email()
   emargement_url = f"{base_url}/events/{event_id}/emargement/lien/{invitation.token_invitation}"
   
   # Envoi des emails
   for invitation in invitations:
       event_service.email_service.send_template_email(
           to_email=invitation.inscription.candidat.email,
           subject=f"Lien d'émargement - {event.titre}",
           template="event_emargement_lien",
           data=template_data
       )
   ```
4. **Modèles interrogés** :
   - `Event` : Événement concerné
   - `InvitationEvent` : Invitations sélectionnées
   - `Candidat` : Emails des candidats
5. **Validation schématique** :
   - **Sélection des invitations** : Vérification des IDs
   - **Génération des URLs** : URLs uniques par token
6. **Services appelés** :
   - **EventService** : `get_event()` pour récupération
   - **EmailService** : Envoi des emails avec liens
7. **Transmission** : Redirection vers la page d'émargement
8. **Affichage** : Page d'émargement mise à jour

### 4.5 Émargement via Lien

**Route** : `GET /events/{event_id}/emargement/lien/{token}`
**Nom** : `emargement_lien_event`
**Template** : `events/emargement_lien.html`

#### Pipeline Complet

1. **Déclenchement** : Clic sur un lien d'émargement dans un email
2. **Route déclenchée** : `emargement_lien_event`
3. **Variables calculées** :
   ```python
   # Vérification du token
   invitation = event_service.get_invitation_by_token(token, db)
   
   # Vérification de l'événement
   event = event_service.get_event(event_id, db)
   
   # Vérification de la présence existante
   presence = event_service.get_presence_candidat(event_id, invitation.inscription_id, db)
   ```
4. **Modèles interrogés** :
   - `InvitationEvent` : Invitation par token
   - `Event` : Événement concerné
   - `PresenceEvent` : Présence existante
5. **Validation schématique** :
   - **Token valide** : Vérification de l'existence du token
   - **Cohérence événement** : Token correspond à l'événement
   - **Événement existant** : Vérification de l'événement
6. **Services appelés** :
   - **EventService** : `get_invitation_by_token()` pour validation
   - **EventService** : `get_event()` pour événement
   - **EventService** : `get_presence_candidat()` pour présence
7. **Transmission** : Template avec données d'émargement
8. **Affichage** : Page d'émargement avec formulaire de signature

### 4.6 Signature d'Émargement

**Route** : `POST /events/{event_id}/emargement/lien/{token}`
**Nom** : `signer_emargement_lien_event`
**Template** : `events/emargement_confirmation.html`

#### Pipeline Complet

1. **Déclenchement** : Soumission du formulaire d'émargement
2. **Route déclenchée** : `signer_emargement_lien_event`
3. **Variables calculées** :
   ```python
   # Vérification du token
   invitation = event_service.get_invitation_by_token(token, db)
   
   # Préparation des données selon la méthode
   signature_manuelle = None
   signature_digitale = None
   photo_signature = photo_data if photo_data else None
   
   if methode_signature == "manuel":
       signature_manuelle = nom_signature
   elif methode_signature == "digital":
       signature_digitale = signature_data
   
   # Création de la présence
   presence_data = PresenceEventCreate(
       event_id=event_id,
       inscription_id=invitation.inscription_id,
       presence="present",
       methode_signature=methode_signature,
       signature_manuelle=signature_manuelle,
       signature_digitale=signature_digitale,
       photo_signature=photo_signature,
       heure_arrivee=datetime.now(timezone.utc),
       commentaire=commentaire if commentaire else None,
       ip_signature=request.client.host
   )
   ```
4. **Modèles interrogés** :
   - `InvitationEvent` : Validation du token
   - `PresenceEvent` : Création/mise à jour de la présence
5. **Validation schématique** :
   - **Token valide** : Vérification de l'existence
   - **Méthode de signature** : Manuelle ou digitale
   - **Données de signature** : Signature et photo requises
6. **Services appelés** :
   - **EventService** : `get_invitation_by_token()` pour validation
   - **EventService** : `mark_presence()` pour enregistrement
7. **Transmission** : Template de confirmation
8. **Affichage** : Page de confirmation d'émargement

---

## 5. SERVICES MÉTIER

### 5.1 Service d'Événements (`EventService`)

**Fichier** : `app/services/event_service.py`
**Description** : Service principal pour la gestion des événements

#### Méthodes Principales

**`create_event()`** :
```python
def create_event(self, event_data: EventCreate, db: Session) -> Event:
    event = Event(**event_data.dict())
    db.add(event)
    db.commit()
    db.refresh(event)
    return event
```

**`get_presences_with_combined_status()`** :
```python
def get_presences_with_combined_status(self, event_id: int, db: Session) -> List[dict]:
    """Retourne les présences avec le statut imbriqué pour la page principale"""
    # Récupérer toutes les invitations pour cet événement
    invitations_query = select(InvitationEvent).where(InvitationEvent.event_id == event_id)
    invitations = db.exec(invitations_query).all()
    
    result = []
    for invitation in invitations:
        db.refresh(invitation)
        
        # Récupérer la présence existante
        presence = self.get_presence_candidat(event_id, invitation.inscription_id, db)
        
        # Calculer le statut imbriqué
        combined_status = self.get_combined_status(event_id, invitation.inscription_id, db)
        
        # Créer l'objet de résultat
        presence_data = {
            'invitation': invitation,
            'presence': presence,
            'combined_status': combined_status,
            'inscription_id': invitation.inscription_id
        }
        
        result.append(presence_data)
    
    return result
```

**`get_combined_status()`** :
```python
def get_combined_status(self, event_id: int, inscription_id: int, db: Session) -> str:
    """
    Retourne le statut imbriqué pour la page principale :
    - Avant l'événement : privilégie le statut d'invitation
    - Après l'événement : privilégie le statut de présence
    """
    from datetime import date
    
    # Récupérer l'événement pour connaître sa date
    event = db.get(Event, event_id)
    if not event:
        return "en_attente"
    
    today = date.today()
    event_passed = event.date_fin < today
    
    # Récupérer l'invitation
    invitation_query = select(InvitationEvent).where(
        InvitationEvent.event_id == event_id,
        InvitationEvent.inscription_id == inscription_id
    )
    invitation = db.exec(invitation_query).first()
    
    # Récupérer la présence
    presence = self.get_presence_candidat(event_id, inscription_id, db)
    
    if event_passed:
        # APRÈS L'ÉVÉNEMENT : privilégier le statut de présence
        if presence and presence.presence in ['present', 'absent', 'excuse']:
            return presence.presence
        else:
            # Pas de présence marquée après l'événement = absent
            return "absent"
    else:
        # AVANT L'ÉVÉNEMENT : privilégier le statut d'invitation
        if invitation:
            if invitation.statut == "refusee":
                return "refusee"
            elif invitation.statut == "acceptee":
                return "acceptee"
            else:
                return "en_attente"
        else:
            return "en_attente"
```

**`mark_presence()`** :
```python
def mark_presence(self, presence_data: PresenceEventCreate, db: Session) -> PresenceEvent:
    """Marquer une présence - ne modifie QUE le statut de présence, pas l'invitation"""
    existing_presence = self.get_presence_candidat(presence_data.event_id, presence_data.inscription_id, db)
    
    if existing_presence:
        for field, value in presence_data.dict().items():
            if field not in ['event_id', 'inscription_id']:
                setattr(existing_presence, field, value)
        
        # Si une signature existe (peu importe la méthode), mettre le statut à "present"
        if presence_data.signature_digitale or presence_data.signature_manuelle:
            existing_presence.presence = "present"
        
        existing_presence.modifie_le = datetime.now(timezone.utc)
        db.commit()
        db.refresh(existing_presence)
        presence_obj = existing_presence
    else:
        # Si une signature existe (peu importe la méthode), mettre le statut à "present"
        if presence_data.signature_digitale or presence_data.signature_manuelle:
            presence_data.presence = "present"
        
        presence_obj = self.create_presence(presence_data, db)
    
    return presence_obj
```

#### Fonctionnalités Avancées

**Gestion des statuts combinés** :
- **Logique temporelle** : Statuts différents avant/après l'événement
- **Privilégiation intelligente** : Invitation avant, présence après
- **Transition automatique** : Passage à "absent" après la date

**Système d'émargement** :
- **Signatures multiples** : Manuelle et digitale
- **Détection automatique** : Signature = présence automatique
- **Traçabilité complète** : IP, User Agent, horodatage
- **Photos de signature** : Capture de la signature

**Gestion des invitations** :
- **Tokens uniques** : Génération de tokens sécurisés
- **Envoi d'emails** : Templates d'emails avec liens d'acceptation/refus
- **Statuts multiples** : En attente, acceptée, refusée
- **Types d'invitation** : Individuelle ou par groupe

---

## 6. VALIDATION ET SÉCURITÉ

### 6.1 Validation des Données

**Validation côté serveur** :
- **Dates cohérentes** : Date de fin >= date de début
- **Heures cohérentes** : Heure de fin >= heure de début
- **Champs obligatoires** : Titre, programme, dates
- **Conversion des types** : Dates, heures, nombres

**Validation côté client** :
- **Champs requis** : Validation HTML5 et JavaScript
- **Format des dates** : Validation des formats de date
- **Méthodes de signature** : Validation des méthodes
- **Confirmation des actions** : Prompts de confirmation

### 6.2 Sécurité des Accès

**Contrôles de sécurité** :
- **Authentification** : Vérification de l'utilisateur connecté
- **Autorisation** : Vérification des droits d'accès
- **Tokens d'invitation** : Tokens uniques et sécurisés
- **Traçabilité** : Logs des actions et modifications

**Protection des données** :
- **Validation des tokens** : Vérification de l'existence et cohérence
- **Isolation des données** : Accès limité aux événements autorisés
- **Chiffrement des signatures** : Protection des données sensibles

---

## 7. PERFORMANCE ET OPTIMISATION

### 7.1 Optimisation des Requêtes

**Jointures optimisées** :
- **Événement + Invitations + Présences** : Une seule requête
- **Statuts combinés** : Calculs en mémoire
- **Évitement des N+1** : Chargement en lot des relations

**Cache et sessions** :
- **Sessions de base de données** : Pool de connexions
- **Transactions atomiques** : Rollback en cas d'erreur
- **Refresh automatique** : Récupération des IDs générés

### 7.2 Gestion des Statuts

**Calculs optimisés** :
- **Statuts combinés** : Logique métier en mémoire
- **Transition automatique** : Mise à jour en lot après événement
- **Cache potentiel** : Possibilité de mise en cache des statuts

---

## 8. MONITORING ET LOGS

### 8.1 Logs de Debug

**Informations loggées** :
- **Actions utilisateur** : Création, modification, suppression
- **Émargements** : Signatures et présences
- **Envoi d'emails** : Succès et échecs d'envoi
- **Statuts combinés** : Calculs et transitions

### 8.2 Métriques de Performance

**KPI calculés** :
- **Total des événements** : Comptage global
- **Répartition par statut** : Planifiés, en cours, terminés
- **Taux de présence** : Pourcentage de présence par événement
- **Statuts combinés** : Distribution des statuts temporels

---

## 9. ÉVOLUTION ET MAINTENANCE

### 9.1 Ajout de Nouveaux Types d'Événements

**Processus d'ajout** :
1. **Modification de l'enum** : Ajout du nouveau type dans StatutEvent
2. **Mise à jour du service** : Adaptation du service de statistiques
3. **Mise à jour de l'interface** : Ajout dans les formulaires
4. **Tests** : Validation avec des cas de test

### 9.2 Modification des Statuts

**Processus de modification** :
1. **Mise à jour de l'enum** : Modification des statuts
2. **Mise à jour de la logique** : Adaptation des statuts combinés
3. **Mise à jour de l'interface** : Adaptation des formulaires
4. **Migration des données** : Mise à jour des données existantes

---

*Document généré automatiquement - Pipeline de gestion des événements LIA WEB*
