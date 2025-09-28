# PIPELINE DE GESTION DU SUIVI MENSUEL - LIA WEB

Ce document détaille le pipeline complet de gestion du suivi mensuel dans l'application LIA WEB, incluant les routes, templates, services et processus métier pour le suivi des candidats avec métriques business, statistiques avancées et filtres multiples.

## Vue d'ensemble

Le système de suivi mensuel permet aux conseillers de suivre l'évolution des candidats validés avec des métriques business détaillées (chiffre d'affaires, employés, subventions, dettes, equity), de générer des statistiques et d'analyser les performances par programme ou candidat.

---

## 1. ARCHITECTURE GÉNÉRALE

### Technologies Utilisées
- **Backend** : FastAPI avec SQLModel
- **Frontend** : Jinja2 templates avec JavaScript interactif
- **Base de données** : PostgreSQL avec relations complexes
- **Services métier** : SuiviMensuelService pour la logique métier
- **Validation** : Fonctions de nettoyage des données
- **Statistiques** : Calculs de métriques business et KPIs
- **Filtres** : Système de filtrage avancé

### Modèles Impliqués
- **SuiviMensuel** : Suivi mensuel avec métriques business
- **Inscription** : Inscription du candidat (statut VALIDE requis)
- **Candidat** : Informations du candidat
- **Programme** : Programme de coaching associé
- **User** : Conseiller/formateur

---

## 2. ROUTES ET PIPELINES

### 2.1 Liste des Candidats Validés

**Route** : `GET /suivi-mensuel/`
**Nom** : `liste_candidats_valides`
**Template** : `suivi_mensuel/liste_candidat.html`

#### Pipeline Complet

1. **Déclenchement** : Accès à la page principale du suivi mensuel
2. **Route déclenchée** : `liste_candidats_valides`
3. **Variables calculées** :
   ```python
   # Vérification des statuts disponibles pour debug
   all_inscriptions = db.exec(select(Inscription.statut)).all()
   unique_statuts = set(all_inscriptions)
   
   # Récupération des inscriptions validées avec informations candidat et programme
   query = select(
       Inscription.id,
       Inscription.cree_le,
       Inscription.statut,
       Candidat.prenom,
       Candidat.nom,
       Candidat.email,
       Candidat.photo_profil,
       Programme.nom.label("programme_nom"),
       Programme.code.label("programme_code")
   ).join(Candidat, Candidat.id == Inscription.candidat_id)\
   .join(Programme, Programme.id == Inscription.programme_id)\
   .where(Inscription.statut == "VALIDE")  # Seulement les candidats validés
   
   # Application des filtres
   if programme_id:
       query = query.where(Inscription.programme_id == programme_id)
   
   if search_candidat:
       search_pattern = f"%{search_candidat}%"
       query = query.where(
           (Candidat.prenom.ilike(search_pattern)) |
           (Candidat.nom.ilike(search_pattern))
       )
   
   query = query.order_by(Programme.nom, Candidat.nom, Candidat.prenom)
   candidats_valides = db.exec(query).all()
   
   # Statistiques
   total_candidats = len(candidats_valides)
   programmes_count = len(set(candidat.programme_nom for candidat in candidats_valides)) if candidats_valides else 0
   ```
4. **Modèles interrogés** :
   - `Inscription` : Inscriptions avec statut VALIDE
   - `Candidat` : Informations des candidats
   - `Programme` : Programmes associés
5. **Validation schématique** :
   - **Filtrage par statut** : Seuls les candidats VALIDE
   - **Filtres optionnels** : Programme, recherche par nom
   - **Gestion d'erreurs** : Try/catch avec logs détaillés
6. **Services appelés** : Aucun (requête directe)
7. **Transmission** : Template avec candidats et statistiques
8. **Affichage** : Liste des candidats validés avec filtres

### 2.2 Liste des Suivis Mensuels

**Route** : `GET /suivi-mensuel/suivis`
**Nom** : `liste_suivis_mensuels`
**Template** : `suivi_mensuel/liste_candidat.html`

#### Pipeline Complet

1. **Déclenchement** : Clic sur "Suivis" dans la navigation
2. **Route déclenchée** : `liste_suivis_mensuels`
3. **Variables calculées** :
   ```python
   # Construction des filtres
   filters = SuiviMensuelFilter(
       programme_id=programme_id,
       mois_debut=mois_debut,
       mois_fin=mois_fin,
       score_min=score_min,
       score_max=score_max,
       has_commentaire=has_commentaire,
       search_candidat=search_candidat
   )
   
   # Récupération des suivis avec filtres
   suivis = suivi_mensuel_service.get_suivis_mensuels(db, filters)
   
   # Calcul des statistiques
   stats = suivi_mensuel_service.get_suivi_mensuel_stats(db, filters)
   
   # Récupération des programmes pour le filtre
   programmes = db.exec(select(Programme)).all()
   ```
4. **Modèles interrogés** :
   - `SuiviMensuel` : Suivis avec filtres multiples
   - `Inscription` : Inscriptions associées
   - `Candidat` : Informations des candidats
   - `Programme` : Programmes associés
5. **Validation schématique** :
   - **Filtres multiples** : Programme, période, score, commentaire, recherche
   - **Types de données** : Conversion des paramètres de requête
6. **Services appelés** :
   - **SuiviMensuelService** : `get_suivis_mensuels()` pour liste filtrée
   - **SuiviMensuelService** : `get_suivi_mensuel_stats()` pour statistiques
7. **Transmission** : Template avec suivis, statistiques et filtres
8. **Affichage** : Liste des suivis avec filtres avancés

### 2.3 Formulaire de Création de Suivi

**Route** : `GET /suivi-mensuel/creer`
**Nom** : `creer_suivi_mensuel_form`
**Template** : `suivi_mensuel/form_business.html`

#### Pipeline Complet

1. **Déclenchement** : Clic sur "Nouveau suivi" ou depuis un candidat
2. **Route déclenchée** : `creer_suivi_mensuel_form`
3. **Variables calculées** :
   ```python
   # Récupération des inscriptions pour le formulaire
   inscriptions = suivi_mensuel_service.get_inscriptions_for_form(db)
   
   # Données initiales
   initial_data = {
       "inscription_id": inscription_id,
       "mois": mois.strftime("%Y-%m") if mois else date.today().strftime("%Y-%m")
   }
   ```
4. **Modèles interrogés** :
   - `Inscription` : Inscriptions disponibles
   - `Candidat` : Noms des candidats
   - `Programme` : Noms des programmes
5. **Validation schématique** :
   - **Données initiales** : Pré-remplissage du formulaire
6. **Services appelés** :
   - **SuiviMensuelService** : `get_inscriptions_for_form()` pour liste
7. **Transmission** : Template avec formulaire et données initiales
8. **Affichage** : Formulaire de création avec sélections

### 2.4 Création de Suivi Mensuel

**Route** : `POST /suivi-mensuel/creer`
**Nom** : `creer_suivi_mensuel`
**Redirection** : `suivis_par_inscription`

#### Pipeline Complet

1. **Déclenchement** : Soumission du formulaire de création
2. **Route déclenchée** : `creer_suivi_mensuel`
3. **Variables calculées** :
   ```python
   # Conversion du mois string en date
   try:
       mois_date = datetime.strptime(mois, '%Y-%m').date().replace(day=1)
   except ValueError as e:
       raise ValueError(f"Format de mois invalide: {mois}")
   
   # Nettoyage des données du formulaire
   def clean_form_data(data: str) -> Optional[str]:
       if not data or data.strip() == "":
           return None
       return data.strip()
   
   def clean_numeric_data(data: str) -> Optional[float]:
       if not data or data.strip() == "":
           return None
       try:
           return float(data.strip())
       except ValueError:
           return None
   
   def clean_int_data(data: str) -> Optional[int]:
       if not data or data.strip() == "":
           return None
       try:
           return int(data.strip())
       except ValueError:
           return None
   
   # Création du suivi avec métriques business
   suivi_create = SuiviMensuelCreate(
       inscription_id=inscription_id,
       mois=mois_date,
       chiffre_affaires_actuel=clean_numeric_data(chiffre_affaires_actuel),
       nb_stagiaires=clean_int_data(nb_stagiaires),
       nb_alternants=clean_int_data(nb_alternants),
       nb_cdd=clean_int_data(nb_cdd),
       nb_cdi=clean_int_data(nb_cdi),
       montant_subventions_obtenues=clean_numeric_data(montant_subventions_obtenues),
       organismes_financeurs=clean_form_data(organismes_financeurs),
       montant_dettes_effectuees=clean_numeric_data(montant_dettes_effectuees),
       montant_dettes_encours=clean_numeric_data(montant_dettes_encours),
       montant_dettes_envisagees=clean_numeric_data(montant_dettes_envisagees),
       montant_equity_effectue=clean_numeric_data(montant_equity_effectue),
       montant_equity_encours=clean_numeric_data(montant_equity_encours),
       statut_juridique=clean_form_data(statut_juridique),
       adresse_entreprise=clean_form_data(adresse_entreprise),
       situation_socioprofessionnelle=clean_form_data(situation_socioprofessionnelle),
       score_objectifs=clean_numeric_data(score_objectifs),
       commentaire=clean_form_data(commentaire)
   )
   ```
4. **Modèles interrogés** :
   - `SuiviMensuel` : Création du nouvel enregistrement
5. **Validation schématique** :
   - **Format de mois** : Validation du format YYYY-MM
   - **Nettoyage des données** : Conversion des chaînes vides en None
   - **Types numériques** : Conversion en float/int avec gestion d'erreurs
   - **Gestion d'erreurs** : Try/catch avec retour au formulaire
6. **Services appelés** :
   - **SuiviMensuelService** : `create_suivi_mensuel()` pour création
7. **Transmission** : Redirection vers les suivis de l'inscription
8. **Affichage** : Page de suivis de l'inscription mise à jour

### 2.5 Formulaire de Modification de Suivi

**Route** : `GET /suivi-mensuel/modifier/{suivi_id}`
**Nom** : `modifier_suivi_mensuel_form`
**Template** : `suivi_mensuel/form_business.html`

#### Pipeline Complet

1. **Déclenchement** : Clic sur "Modifier" dans un suivi
2. **Route déclenchée** : `modifier_suivi_mensuel_form`
3. **Variables calculées** :
   ```python
   # Récupération du suivi existant
   suivi = suivi_mensuel_service.get_suivi_mensuel(db, suivi_id)
   
   # Récupération des inscriptions pour le formulaire
   inscriptions = suivi_mensuel_service.get_inscriptions_for_form(db)
   
   # Données initiales pré-remplies
   initial_data = {
       "inscription_id": suivi.inscription_id,
       "mois": suivi.mois.strftime("%Y-%m"),
       "chiffre_affaires_actuel": suivi.chiffre_affaires_actuel,
       "nb_stagiaires": suivi.nb_stagiaires,
       "nb_alternants": suivi.nb_alternants,
       "nb_cdd": suivi.nb_cdd,
       "nb_cdi": suivi.nb_cdi,
       "montant_subventions_obtenues": suivi.montant_subventions_obtenues,
       "organismes_financeurs": suivi.organismes_financeurs,
       "montant_dettes_effectuees": suivi.montant_dettes_effectuees,
       "montant_dettes_encours": suivi.montant_dettes_encours,
       "montant_dettes_envisagees": suivi.montant_dettes_envisagees,
       "montant_equity_effectue": suivi.montant_equity_effectue,
       "montant_equity_encours": suivi.montant_equity_encours,
       "statut_juridique": suivi.statut_juridique,
       "adresse_entreprise": suivi.adresse_entreprise,
       "situation_socioprofessionnelle": suivi.situation_socioprofessionnelle,
       "score_objectifs": suivi.score_objectifs,
       "commentaire": suivi.commentaire
   }
   ```
4. **Modèles interrogés** :
   - `SuiviMensuel` : Suivi existant à modifier
   - `Inscription` : Inscriptions disponibles
5. **Validation schématique** :
   - **Existence du suivi** : Vérification de l'existence
   - **Mode édition** : Pré-remplissage du formulaire
6. **Services appelés** :
   - **SuiviMensuelService** : `get_suivi_mensuel()` pour récupération
   - **SuiviMensuelService** : `get_inscriptions_for_form()` pour liste
7. **Transmission** : Template avec formulaire pré-rempli
8. **Affichage** : Formulaire de modification avec données existantes

### 2.6 Modification de Suivi Mensuel

**Route** : `POST /suivi-mensuel/modifier/{suivi_id}`
**Nom** : `modifier_suivi_mensuel`
**Redirection** : `suivis_par_inscription`

#### Pipeline Complet

1. **Déclenchement** : Soumission du formulaire de modification
2. **Route déclenchée** : `modifier_suivi_mensuel`
3. **Variables calculées** :
   ```python
   # Conversion du mois string en date
   try:
       mois_date = datetime.strptime(mois, '%Y-%m').date().replace(day=1)
   except ValueError as e:
       raise ValueError(f"Format de mois invalide: {mois}")
   
   # Mise à jour du suivi avec métriques business
   suivi_update = SuiviMensuelUpdate(
       inscription_id=inscription_id,
       mois=mois_date,
       chiffre_affaires_actuel=clean_numeric_data(chiffre_affaires_actuel),
       nb_stagiaires=clean_int_data(nb_stagiaires),
       nb_alternants=clean_int_data(nb_alternants),
       nb_cdd=clean_int_data(nb_cdd),
       nb_cdi=clean_int_data(nb_cdi),
       montant_subventions_obtenues=clean_numeric_data(montant_subventions_obtenues),
       organismes_financeurs=clean_form_data(organismes_financeurs),
       montant_dettes_effectuees=clean_numeric_data(montant_dettes_effectuees),
       montant_dettes_encours=clean_numeric_data(montant_dettes_encours),
       montant_dettes_envisagees=clean_numeric_data(montant_dettes_envisagees),
       montant_equity_effectue=clean_numeric_data(montant_equity_effectue),
       montant_equity_encours=clean_numeric_data(montant_equity_encours),
       statut_juridique=clean_form_data(statut_juridique),
       adresse_entreprise=clean_form_data(adresse_entreprise),
       situation_socioprofessionnelle=clean_form_data(situation_socioprofessionnelle),
       score_objectifs=clean_numeric_data(score_objectifs),
       commentaire=clean_form_data(commentaire)
   )
   ```
4. **Modèles interrogés** :
   - `SuiviMensuel` : Mise à jour de l'enregistrement
5. **Validation schématique** :
   - **Format de mois** : Validation du format YYYY-MM
   - **Nettoyage des données** : Conversion des chaînes vides en None
   - **Types numériques** : Conversion en float/int avec gestion d'erreurs
   - **Gestion d'erreurs** : Try/catch avec retour au formulaire
6. **Services appelés** :
   - **SuiviMensuelService** : `update_suivi_mensuel()` pour mise à jour
7. **Transmission** : Redirection vers les suivis de l'inscription
8. **Affichage** : Page de suivis de l'inscription mise à jour

### 2.7 Suppression de Suivi Mensuel

**Route** : `POST /suivi-mensuel/supprimer/{suivi_id}`
**Nom** : `supprimer_suivi_mensuel`
**Redirection** : `suivis_par_inscription`

#### Pipeline Complet

1. **Déclenchement** : Clic sur "Supprimer" dans un suivi
2. **Route déclenchée** : `supprimer_suivi_mensuel`
3. **Variables calculées** :
   ```python
   # Récupération de l'inscription_id avant suppression pour redirection
   suivi = suivi_mensuel_service.get_suivi_mensuel(db, suivi_id)
   inscription_id = suivi.inscription_id
   
   # Suppression du suivi
   suivi_mensuel_service.delete_suivi_mensuel(db, suivi_id)
   ```
4. **Modèles interrogés** :
   - `SuiviMensuel` : Suppression de l'enregistrement
5. **Validation schématique** :
   - **Existence du suivi** : Vérification de l'existence
   - **Récupération de l'ID** : Pour redirection après suppression
6. **Services appelés** :
   - **SuiviMensuelService** : `get_suivi_mensuel()` pour récupération
   - **SuiviMensuelService** : `delete_suivi_mensuel()` pour suppression
7. **Transmission** : Redirection vers les suivis de l'inscription
8. **Affichage** : Page de suivis de l'inscription mise à jour

### 2.8 Suivis par Inscription

**Route** : `GET /suivi-mensuel/inscription/{inscription_id}`
**Nom** : `suivis_par_inscription`
**Template** : `suivi_mensuel/inscription.html`

#### Pipeline Complet

1. **Déclenchement** : Clic sur un candidat ou redirection après création/modification
2. **Route déclenchée** : `suivis_par_inscription`
3. **Variables calculées** :
   ```python
   # Récupération de l'inscription et des informations associées
   inscription = db.get(Inscription, inscription_id)
   candidat = db.get(Candidat, inscription.candidat_id)
   programme = db.get(Programme, inscription.programme_id)
   
   # Filtres pour cette inscription spécifique
   filters = SuiviMensuelFilter(inscription_id=inscription_id)
   
   # Récupération des suivis et statistiques
   suivis = suivi_mensuel_service.get_suivis_mensuels(db, filters)
   stats = suivi_mensuel_service.get_suivi_mensuel_stats(db, filters)
   ```
4. **Modèles interrogés** :
   - `Inscription` : Inscription spécifique
   - `Candidat` : Informations du candidat
   - `Programme` : Programme associé
   - `SuiviMensuel` : Suivis de cette inscription
5. **Validation schématique** :
   - **Existence de l'inscription** : Vérification de l'existence
6. **Services appelés** :
   - **SuiviMensuelService** : `get_suivis_mensuels()` pour liste
   - **SuiviMensuelService** : `get_suivi_mensuel_stats()` pour statistiques
7. **Transmission** : Template avec inscription, candidat, programme, suivis et statistiques
8. **Affichage** : Page de détail avec historique des suivis

### 2.9 Suivis par Programme

**Route** : `GET /suivi-mensuel/programme/{programme_id}`
**Nom** : `suivis_par_programme`
**Template** : `suivi_mensuel/programme.html`

#### Pipeline Complet

1. **Déclenchement** : Clic sur un programme dans les statistiques
2. **Route déclenchée** : `suivis_par_programme`
3. **Variables calculées** :
   ```python
   # Récupération du programme
   programme = db.get(Programme, programme_id)
   
   # Filtres pour ce programme spécifique
   filters = SuiviMensuelFilter(programme_id=programme_id)
   
   # Récupération des suivis et statistiques
   suivis = suivi_mensuel_service.get_suivis_mensuels(db, filters)
   stats = suivi_mensuel_service.get_suivi_mensuel_stats(db, filters)
   ```
4. **Modèles interrogés** :
   - `Programme` : Programme spécifique
   - `SuiviMensuel` : Suivis de ce programme
   - `Inscription` : Inscriptions associées
   - `Candidat` : Candidats associés
5. **Validation schématique** :
   - **Existence du programme** : Vérification de l'existence
6. **Services appelés** :
   - **SuiviMensuelService** : `get_suivis_mensuels()` pour liste
   - **SuiviMensuelService** : `get_suivi_mensuel_stats()` pour statistiques
7. **Transmission** : Template avec programme, suivis et statistiques
8. **Affichage** : Page de détail avec vue d'ensemble du programme

---

## 3. SERVICES MÉTIER

### 3.1 Service Suivi Mensuel (`SuiviMensuelService`)

**Fichier** : `app/services/suivi_mensuel_service.py`
**Description** : Service principal pour la gestion du suivi mensuel

#### Méthodes Principales

**`get_suivis_mensuels()`** :
```python
def get_suivis_mensuels(
    self, db: Session, filters: SuiviMensuelFilter, skip: int = 0, limit: int = 100
) -> List[SuiviMensuelWithCandidat]:
    """Récupérer les suivis mensuels avec filtres"""
    query = select(
        SuiviMensuel,
        Candidat.prenom,
        Candidat.nom,
        Programme.nom.label("programme_nom")
    ).join(Inscription, Inscription.id == SuiviMensuel.inscription_id)\
    .join(Candidat, Candidat.id == Inscription.candidat_id)\
    .join(Programme, Programme.id == Inscription.programme_id)

    # Application des filtres multiples
    if filters.programme_id:
        query = query.where(Inscription.programme_id == filters.programme_id)
    if filters.candidat_id:
        query = query.where(Inscription.candidat_id == filters.candidat_id)
    if filters.mois_debut:
        query = query.where(SuiviMensuel.mois >= filters.mois_debut)
    if filters.mois_fin:
        query = query.where(SuiviMensuel.mois <= filters.mois_fin)
    if filters.score_min is not None:
        query = query.where(SuiviMensuel.score_objectifs >= filters.score_min)
    if filters.score_max is not None:
        query = query.where(SuiviMensuel.score_objectifs <= filters.score_max)
    if filters.has_commentaire is not None:
        if filters.has_commentaire:
            query = query.where(SuiviMensuel.commentaire.is_not(None))
        else:
            query = query.where(SuiviMensuel.commentaire.is_(None))
    if filters.search_candidat:
        search_pattern = f"%{filters.search_candidat}%"
        query = query.where(
            (Candidat.prenom.ilike(search_pattern)) |
            (Candidat.nom.ilike(search_pattern))
        )

    query = query.order_by(SuiviMensuel.mois.desc(), SuiviMensuel.cree_le.desc())
    
    results = db.exec(query.offset(skip).limit(limit)).all()
    
    return [
        SuiviMensuelWithCandidat(
            id=s.id,
            inscription_id=s.inscription_id,
            mois=s.mois,
            chiffre_affaires_actuel=s.chiffre_affaires_actuel,
            nb_stagiaires=s.nb_stagiaires,
            nb_alternants=s.nb_alternants,
            nb_cdd=s.nb_cdd,
            nb_cdi=s.nb_cdi,
            montant_subventions_obtenues=s.montant_subventions_obtenues,
            organismes_financeurs=s.organismes_financeurs,
            montant_dettes_effectuees=s.montant_dettes_effectuees,
            montant_dettes_encours=s.montant_dettes_encours,
            montant_dettes_envisagees=s.montant_dettes_envisagees,
            montant_equity_effectue=s.montant_equity_effectue,
            montant_equity_encours=s.montant_equity_encours,
            statut_juridique=s.statut_juridique,
            adresse_entreprise=s.adresse_entreprise,
            situation_socioprofessionnelle=s.situation_socioprofessionnelle,
            score_objectifs=s.score_objectifs,
            commentaire=s.commentaire,
            cree_le=s.cree_le,
            modifie_le=s.modifie_le,
            candidat_nom_complet=f"{prenom} {nom}",
            programme_nom=programme_nom
        ) for s, prenom, nom, programme_nom in results
    ]
```

**`create_suivi_mensuel()`** :
```python
def create_suivi_mensuel(self, db: Session, suivi_create: SuiviMensuelCreate) -> SuiviMensuel:
    """Créer un nouveau suivi mensuel"""
    # Vérification d'unicité : un suivi par inscription et mois
    existing_suivi = db.exec(
        select(SuiviMensuel)
        .where(SuiviMensuel.inscription_id == suivi_create.inscription_id)
        .where(SuiviMensuel.mois == suivi_create.mois)
    ).first()
    if existing_suivi:
        raise ValueError("Un suivi existe déjà pour cette inscription et ce mois.")

    suivi = SuiviMensuel(**suivi_create.dict())
    db.add(suivi)
    db.commit()
    db.refresh(suivi)
    return suivi
```

**`update_suivi_mensuel()`** :
```python
def update_suivi_mensuel(self, db: Session, suivi_id: int, suivi_update: SuiviMensuelUpdate) -> Optional[SuiviMensuel]:
    """Mettre à jour un suivi mensuel"""
    suivi = db.get(SuiviMensuel, suivi_id)
    if not suivi:
        return None
    
    # Vérification d'unicité si mois ou inscription_id est modifié
    if suivi_update.mois and suivi_update.mois != suivi.mois or \
       suivi_update.inscription_id and suivi_update.inscription_id != suivi.inscription_id:
        existing_suivi = db.exec(
            select(SuiviMensuel)
            .where(SuiviMensuel.inscription_id == (suivi_update.inscription_id or suivi.inscription_id))
            .where(SuiviMensuel.mois == (suivi_update.mois or suivi.mois))
            .where(SuiviMensuel.id != suivi_id)
        ).first()
        if existing_suivi:
            raise ValueError("Un autre suivi existe déjà pour cette inscription et ce mois.")

    update_data = suivi_update.dict(exclude_unset=True)
    for key, value in update_data.items():
        setattr(suivi, key, value)
    
    # Mettre à jour la date de modification
    suivi.modifie_le = datetime.now(timezone.utc)
    
    db.add(suivi)
    db.commit()
    db.refresh(suivi)
    return suivi
```

**`get_suivi_mensuel_stats()`** :
```python
def get_suivi_mensuel_stats(self, db: Session, filters: SuiviMensuelFilter) -> SuiviMensuelStats:
    """Calculer les statistiques des suivis mensuels"""
    query = select(SuiviMensuel).join(Inscription).join(Candidat).join(Programme)

    # Application des mêmes filtres que pour la liste
    if filters.programme_id:
        query = query.where(Inscription.programme_id == filters.programme_id)
    if filters.candidat_id:
        query = query.where(Inscription.candidat_id == filters.candidat_id)
    if filters.mois_debut:
        query = query.where(SuiviMensuel.mois >= filters.mois_debut)
    if filters.mois_fin:
        query = query.where(SuiviMensuel.mois <= filters.mois_fin)
    if filters.score_min is not None:
        query = query.where(SuiviMensuel.score_objectifs >= filters.score_min)
    if filters.score_max is not None:
        query = query.where(SuiviMensuel.score_objectifs <= filters.score_max)
    if filters.has_commentaire is not None:
        if filters.has_commentaire:
            query = query.where(SuiviMensuel.commentaire.is_not(None))
        else:
            query = query.where(SuiviMensuel.commentaire.is_(None))
    if filters.search_candidat:
        search_pattern = f"%{filters.search_candidat}%"
        query = query.where(
            (Candidat.prenom.ilike(search_pattern)) |
            (Candidat.nom.ilike(search_pattern))
        )

    suivis = db.exec(query).all()

    # Calcul des statistiques business
    total_suivis = len(suivis)
    score_moyen = None
    suivis_avec_commentaire = 0
    ca_moyen = None
    total_employes = 0
    montant_subventions_total = 0
    montant_dettes_total = 0
    montant_equity_total = 0

    if total_suivis > 0:
        scores = [s.score_objectifs for s in suivis if s.score_objectifs is not None]
        score_moyen = sum(scores) / len(scores) if scores else None
        
        suivis_avec_commentaire = sum(1 for s in suivis if s.commentaire)
        
        # Statistiques business
        ca_values = [s.chiffre_affaires_actuel for s in suivis if s.chiffre_affaires_actuel is not None]
        ca_moyen = sum(ca_values) / len(ca_values) if ca_values else None
        
        total_employes = sum(
            (s.nb_stagiaires or 0) + (s.nb_alternants or 0) + 
            (s.nb_cdd or 0) + (s.nb_cdi or 0) 
            for s in suivis
        )
        
        montant_subventions_total = sum(
            s.montant_subventions_obtenues for s in suivis 
            if s.montant_subventions_obtenues is not None
        )
        
        montant_dettes_total = sum(
            (s.montant_dettes_effectuees or 0) + (s.montant_dettes_encours or 0) + 
            (s.montant_dettes_envisagees or 0) for s in suivis
        )
        
        montant_equity_total = sum(
            (s.montant_equity_effectue or 0) + (s.montant_equity_encours or 0) 
            for s in suivis
        )

    # Trouver les candidats sans suivi pour le programme donné
    candidats_sans_suivi_list = []
    if filters.programme_id:
        candidats_with_suivi_subquery = select(Inscription.candidat_id).join(SuiviMensuel).where(Inscription.programme_id == filters.programme_id).subquery()
        candidats_sans_suivi_query = select(Candidat.prenom, Candidat.nom).join(Inscription)\
            .where(Inscription.programme_id == filters.programme_id)\
            .where(Candidat.id.not_in(candidats_with_suivi_subquery))
        
        candidats_sans_suivi_results = db.exec(candidats_sans_suivi_query).all()
        candidats_sans_suivi_list = [f"{p} {n}" for p, n in candidats_sans_suivi_results]

    return SuiviMensuelStats(
        total_suivis=total_suivis,
        score_moyen=round(score_moyen, 1) if score_moyen is not None else None,
        suivis_avec_commentaire=suivis_avec_commentaire,
        suivis_sans_commentaire=total_suivis - suivis_avec_commentaire,
        candidats_sans_suivi=candidats_sans_suivi_list,
        ca_moyen=round(ca_moyen, 2) if ca_moyen is not None else None,
        total_employes=total_employes,
        montant_subventions_total=round(montant_subventions_total, 2),
        montant_dettes_total=round(montant_dettes_total, 2),
        montant_equity_total=round(montant_equity_total, 2)
    )
```

**`get_inscriptions_for_form()`** :
```python
def get_inscriptions_for_form(self, db: Session) -> List[dict]:
    """Récupérer les inscriptions pour le formulaire"""
    inscriptions = db.exec(
        select(Inscription.id, Candidat.prenom, Candidat.nom, Programme.nom)
        .join(Candidat)
        .join(Programme)
        .order_by(Programme.nom, Candidat.nom, Candidat.prenom)
    ).all()
    return [
        {"id": i_id, "nom_complet": f"{c_prenom} {c_nom}", "programme_nom": p_nom}
        for i_id, c_prenom, c_nom, p_nom in inscriptions
    ]
```

#### Fonctionnalités Avancées

**Métriques business complètes** :
- **Chiffre d'affaires** : CA actuel en euros
- **Évolution des employés** : Stagiaires, alternants, CDD, CDI
- **Subventions** : Montants obtenus et organismes financeurs
- **Dettes** : Effectuées, en cours, envisagées
- **Equity** : Levées effectuées et en cours
- **Informations entreprise** : Statut juridique, adresse, situation

**Filtres avancés** :
- **Par programme** : Restriction à un programme spécifique
- **Par période** : Mois de début et fin
- **Par score** : Score minimum et maximum
- **Par commentaire** : Avec ou sans commentaire
- **Recherche** : Par nom de candidat

**Statistiques détaillées** :
- **Métriques générales** : Total suivis, score moyen, commentaires
- **Métriques business** : CA moyen, total employés, montants totaux
- **Candidats sans suivi** : Identification des candidats non suivis

**Validation d'unicité** :
- **Un suivi par mois** : Un seul suivi par inscription et mois
- **Vérification lors de la création** : Contrôle d'unicité
- **Vérification lors de la modification** : Contrôle d'unicité avec exclusion

---

## 4. VALIDATION ET SÉCURITÉ

### 4.1 Contrôle d'Accès

**Rôles autorisés** :
- **Administrateur** : Accès complet
- **Responsable programme** : Accès complet
- **Conseiller** : Accès aux suivis de ses candidats
- **Formateur** : Accès aux suivis des candidats formés

**Vérifications systématiques** :
```python
# Authentification requise pour toutes les routes
current_user: User = Depends(get_current_user)
```

### 4.2 Validation des Données

**Validation côté serveur** :
- **Format de mois** : Validation du format YYYY-MM
- **Types numériques** : Conversion en float/int avec gestion d'erreurs
- **Nettoyage des données** : Conversion des chaînes vides en None
- **Unicité** : Un suivi par inscription et mois

**Fonctions de nettoyage** :
```python
def clean_form_data(data: str) -> Optional[str]:
    """Nettoie les données du formulaire en convertissant les chaînes vides en None"""
    if not data or data.strip() == "":
        return None
    return data.strip()

def clean_numeric_data(data: str) -> Optional[float]:
    """Nettoie les données numériques du formulaire"""
    if not data or data.strip() == "":
        return None
    try:
        return float(data.strip())
    except ValueError:
        return None

def clean_int_data(data: str) -> Optional[int]:
    """Nettoie les données entières du formulaire"""
    if not data or data.strip() == "":
        return None
    try:
        return int(data.strip())
    except ValueError:
        return None
```

**Validation côté client** :
- **Champs requis** : Validation HTML5 et JavaScript
- **Types de données** : Validation des formats
- **Confirmation des actions** : Prompts de confirmation

### 4.3 Sécurité des Accès

**Contrôles de sécurité** :
- **Authentification** : Vérification de l'utilisateur connecté
- **Autorisation** : Vérification des droits d'accès
- **Validation des données** : Contrôles sur les entrées
- **Gestion d'erreurs** : Try/catch avec rollback

**Protection des données** :
- **Isolation des données** : Accès limité aux suivis autorisés
- **Validation des relations** : Vérification des liens entre entités
- **Logs des actions** : Traçabilité des créations et modifications

---

## 5. PERFORMANCE ET OPTIMISATION

### 5.1 Optimisation des Requêtes

**Jointures optimisées** :
- **Suivis + Candidats + Programmes** : Une seule requête pour les détails
- **Statistiques** : Calculs en base de données
- **Filtres multiples** : Application efficace des filtres

**Cache et sessions** :
- **Sessions de base de données** : Pool de connexions
- **Transactions atomiques** : Rollback en cas d'erreur
- **Refresh automatique** : Récupération des IDs générés

### 5.2 Gestion des Filtres

**Filtres optimisés** :
- **Application en base** : Filtres appliqués au niveau SQL
- **Indexation** : Index sur les champs de filtrage
- **Pagination** : Limitation des résultats

---

## 6. MONITORING ET LOGS

### 6.1 Logs de Debug

**Informations loggées** :
- **Actions utilisateur** : Création, modification, suppression
- **Filtres appliqués** : Paramètres de filtrage
- **Calculs statistiques** : Métriques et KPIs
- **Erreurs de validation** : Problèmes de format ou unicité

### 6.2 Métriques de Performance

**KPI calculés** :
- **Total des suivis** : Comptage global
- **Score moyen** : Moyenne des scores objectifs
- **Métriques business** : CA moyen, total employés, montants totaux
- **Candidats sans suivi** : Identification des lacunes

---

## 7. ÉVOLUTION ET MAINTENANCE

### 7.1 Ajout de Nouvelles Métriques

**Processus d'ajout** :
1. **Modification du modèle** : Ajout du nouveau champ dans SuiviMensuel
2. **Mise à jour du service** : Adaptation du service de suivi
3. **Mise à jour de l'interface** : Ajout dans les formulaires
4. **Tests** : Validation avec des cas de test

### 7.2 Modification des Filtres

**Processus de modification** :
1. **Mise à jour du schéma** : Modification des filtres disponibles
2. **Mise à jour de la logique** : Adaptation des requêtes
3. **Mise à jour de l'interface** : Adaptation des formulaires
4. **Migration des données** : Mise à jour des données existantes

---

*Document généré automatiquement - Pipeline de gestion du suivi mensuel LIA WEB*
