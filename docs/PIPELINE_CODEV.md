# PIPELINE DE GESTION DU CODEV (CO-DÉVELOPPEMENT) - LIA WEB

Ce document détaille le pipeline complet de gestion du codéveloppement dans l'application LIA WEB, incluant les routes, templates, services et processus métier pour la planification, gestion et suivi des cycles de codéveloppement avec groupes, séances, présentations et contributions.

## Vue d'ensemble

Le système de codéveloppement permet aux organisateurs de créer des cycles de formation par groupes, de planifier des séances avec présentations de problématiques, de gérer les contributions des participants et de suivre les engagements des candidats.

---

## 1. ARCHITECTURE GÉNÉRALE

### Technologies Utilisées
- **Backend** : FastAPI avec SQLModel
- **Frontend** : Jinja2 templates avec JavaScript interactif AIR FRANCE 255 et  
- **Base de données** : PostgreSQL avec relations complexes
- **Services métier** : CodevService pour la logique métier
- **Contrôles d'accès** : Fonction `codev_access_required()` pour autorisation
- **Statistiques** : Calculs de métriques et KPIs
- **Planification** : Gestion des cycles, groupes et séances

### Modèles Impliqués
- **CycleCodev** : Cycle de codéveloppement (série de séances)
- **GroupeCodev** : Groupe de codéveloppement dans un cycle
- **MembreGroupeCodev** : Membre d'un groupe de codéveloppement
- **SeanceCodev** : Séance de codéveloppement
- **PresentationCodev** : Présentation d'un candidat lors d'une séance
- **ContributionCodev** : Contribution d'un participant à une présentation
- **ParticipationSeance** : Participation d'un candidat à une séance
- **Programme** : Programme de coaching associé
- **Promotion** : Promotion associée au cycle
- **Groupe** : Groupe de base associé
- **Inscription** : Inscription du candidat
- **User** : Animateur/facilitateur

---

## 2. ROUTES ET PIPELINES

### 2.1 Tableau de Bord du Codev

**Route** : `GET /codev/`
**Nom** : `codev_dashboard`
**Template** : `codev/dashboard.html`

#### Pipeline Complet

1. **Déclenchement** : Accès à la page principale du codéveloppement
2. **Route déclenchée** : `codev_dashboard`
3. **Variables calculées** :
   ```python
   # Récupération des cycles actifs
   cycles_actifs = session.exec(
       select(CycleCodev).where(
           CycleCodev.statut.in_([StatutCycleCodev.PLANIFIE.value, StatutCycleCodev.EN_COURS.value])
       ).order_by(CycleCodev.date_debut.desc())
   ).all()
   
   # Prochaines séances
   prochaines_seances = CodevService.get_prochaines_seances(session, limit=5, programme_id=programme_id)
   
   # Engagements en cours
   engagements_en_cours = CodevService.get_engagements_en_cours(session, programme_id=programme_id)
   ```
4. **Modèles interrogés** :
   - `CycleCodev` : Cycles actifs avec filtres
   - `SeanceCodev` : Prochaines séances planifiées
   - `PresentationCodev` : Engagements en cours de test
5. **Validation schématique** :
   - **Contrôle d'accès** : `codev_access_required()` pour autorisation
   - **Filtres optionnels** : Programme pour restriction
6. **Services appelés** :
   - **CodevService** : `get_prochaines_seances()` pour séances à venir
   - **CodevService** : `get_engagements_en_cours()` pour engagements
7. **Transmission** : Template avec données de synthèse
8. **Affichage** : Tableau de bord avec cycles, séances et engagements

### 2.2 Liste des Cycles

**Route** : `GET /codev/cycles`
**Nom** : `codev_cycles`
**Template** : `codev/cycles.html`

#### Pipeline Complet

1. **Déclenchement** : Clic sur "Cycles" dans la navigation
2. **Route déclenchée** : `codev_cycles`
3. **Variables calculées** :
   ```python
   # Construction de la requête avec recherche
   stmt = select(CycleCodev)
   if q:
       like = f"%{q}%"
       stmt = stmt.where(
           or_(
               CycleCodev.nom.ilike(like),
               CycleCodev.description.ilike(like)
           )
       )
   
   # Exécution avec tri
   cycles = session.exec(stmt.order_by(CycleCodev.date_debut.desc())).all()
   ```
4. **Modèles interrogés** :
   - `CycleCodev` : Tous les cycles avec recherche
5. **Validation schématique** :
   - **Contrôle d'accès** : `codev_access_required()`
   - **Recherche textuelle** : Nom et description
6. **Services appelés** : Aucun (requête directe)
7. **Transmission** : Template avec liste et terme de recherche
8. **Affichage** : Liste des cycles avec recherche et tri

### 2.3 Formulaire de Création de Cycle

**Route** : `GET /codev/cycles/creer`
**Nom** : `codev_cycles_creer`
**Template** : `codev/cycle_form.html`

#### Pipeline Complet

1. **Déclenchement** : Clic sur "Nouveau cycle"
2. **Route déclenchée** : `codev_cycles_creer`
3. **Variables calculées** :
   ```python
   # Récupération des programmes et promotions
   programmes = session.exec(select(Programme).where(Programme.actif == True)).all()
   promotions = session.exec(select(Promotion).where(Promotion.actif == True)).all()
   
   # Récupération des animateurs potentiels
   animateurs = session.exec(
       select(User).where(
           User.role.in_([
               UserRole.CONSEILLER.value,
               UserRole.FORMATEUR.value,
               UserRole.COORDINATEUR.value,
               UserRole.RESPONSABLE_PROGRAMME.value
           ])
       )
   ).all()
   ```
4. **Modèles interrogés** :
   - `Programme` : Programmes actifs
   - `Promotion` : Promotions actives
   - `User` : Utilisateurs avec rôles d'animateur
5. **Validation schématique** :
   - **Contrôle d'accès** : `codev_access_required()`
   - **Filtres actifs** : Seuls les programmes/promotions actifs
6. **Services appelés** : Aucun (préparation des données)
7. **Transmission** : Template avec formulaire et options
8. **Affichage** : Formulaire de création avec sélections

### 2.4 Création de Cycle

**Route** : `POST /codev/cycles/creer`
**Nom** : `codev_cycles_creer_post`
**Redirection** : `/codev/cycles/{cycle_id}`

#### Pipeline Complet

1. **Déclenchement** : Soumission du formulaire de création
2. **Route déclenchée** : `codev_cycles_creer_post`
3. **Variables calculées** :
   ```python
   # Création du cycle via le service
   cycle = CodevService.create_cycle_codev(
       session=session,
       nom=nom,
       programme_id=programme_id,
       promotion_id=promotion_id,
       date_debut=date_debut,
       date_fin=date_fin,
       nombre_seances=nombre_seances,
       animateur_principal_id=animateur_principal_id
   )
   
   # Ajout des objectifs si fournis
   if objectifs_cycle:
       cycle.objectifs_cycle = objectifs_cycle
       session.commit()
   ```
4. **Modèles interrogés** :
   - `CycleCodev` : Création du nouvel enregistrement
5. **Validation schématique** :
   - **Contrôle d'accès** : `codev_access_required()`
   - **Champs obligatoires** : Nom, programme, dates
   - **Gestion d'erreurs** : Try/catch avec redirection
6. **Services appelés** :
   - **CodevService** : `create_cycle_codev()` pour création
7. **Transmission** : Redirection vers le détail du cycle
8. **Affichage** : Page de détail du cycle créé

### 2.5 Détail d'un Cycle

**Route** : `GET /codev/cycles/{cycle_id}`
**Nom** : `codev_cycle_detail`
**Template** : `codev/cycle_detail.html`

#### Pipeline Complet

1. **Déclenchement** : Clic sur un cycle dans la liste
2. **Route déclenchée** : `codev_cycle_detail`
3. **Variables calculées** :
   ```python
   # Récupération du cycle
   cycle = session.get(CycleCodev, cycle_id)
   
   # Récupération des groupes du cycle
   groupes = session.exec(
       select(GroupeCodev).where(GroupeCodev.cycle_id == cycle_id)
   ).all()
   
   # Récupération des statistiques
   stats = CodevService.get_statistiques_cycle(session, cycle_id)
   ```
4. **Modèles interrogés** :
   - `CycleCodev` : Cycle principal
   - `GroupeCodev` : Groupes associés au cycle
   - `MembreGroupeCodev` : Membres des groupes
   - `SeanceCodev` : Séances réalisées
   - `PresentationCodev` : Présentations terminées
5. **Validation schématique** :
   - **Existence du cycle** : Vérification de l'existence
   - **Contrôle d'accès** : `codev_access_required()`
6. **Services appelés** :
   - **CodevService** : `get_statistiques_cycle()` pour métriques
7. **Transmission** : Template avec données complètes
8. **Affichage** : Page de détail avec groupes et statistiques

### 2.6 Liste des Groupes

**Route** : `GET /codev/groupes`
**Nom** : `codev_groupes`
**Template** : `codev/groupes.html`

#### Pipeline Complet

1. **Déclenchement** : Clic sur "Groupes" dans la navigation
2. **Route déclenchée** : `codev_groupes`
3. **Variables calculées** :
   ```python
   # Construction de la requête avec filtre cycle
   stmt = select(GroupeCodev)
   if cycle_id:
       stmt = stmt.where(GroupeCodev.cycle_id == cycle_id)
   
   # Exécution avec tri
   groupes = session.exec(stmt.order_by(GroupeCodev.nom_groupe)).all()
   
   # Récupération des cycles pour le filtre
   cycles = session.exec(select(CycleCodev)).all()
   ```
4. **Modèles interrogés** :
   - `GroupeCodev` : Groupes avec filtre cycle
   - `CycleCodev` : Cycles pour le filtre
5. **Validation schématique** :
   - **Contrôle d'accès** : `codev_access_required()`
   - **Filtre optionnel** : Cycle pour restriction
6. **Services appelés** : Aucun (requête directe)
7. **Transmission** : Template avec liste et filtres
8. **Affichage** : Liste des groupes avec filtres

### 2.7 Création de Groupe

**Route** : `POST /codev/groupes/creer`
**Nom** : `codev_groupes_creer_post`
**Redirection** : `/codev/groupes?cycle_id={cycle_id}`

#### Pipeline Complet

1. **Déclenchement** : Soumission du formulaire de création de groupe
2. **Route déclenchée** : `codev_groupes_creer_post`
3. **Variables calculées** :
   ```python
   # Création du groupe via le service
   groupe_codev = CodevService.create_groupe_codev(
       session=session,
       cycle_id=cycle_id,
       groupe_id=groupe_id,
       nom_groupe=nom_groupe,
       animateur_id=animateur_id,
       capacite_max=capacite_max
   )
   ```
4. **Modèles interrogés** :
   - `GroupeCodev` : Création du nouvel enregistrement
5. **Validation schématique** :
   - **Contrôle d'accès** : `codev_access_required()`
   - **Champs obligatoires** : Cycle, groupe, nom
   - **Gestion d'erreurs** : Try/catch avec redirection
6. **Services appelés** :
   - **CodevService** : `create_groupe_codev()` pour création
7. **Transmission** : Redirection vers la liste des groupes
8. **Affichage** : Liste des groupes mise à jour

### 2.8 Liste des Séances

**Route** : `GET /codev/seances`
**Nom** : `codev_seances`
**Template** : `codev/seances.html`

#### Pipeline Complet

1. **Déclenchement** : Clic sur "Séances" dans la navigation
2. **Route déclenchée** : `codev_seances`
3. **Variables calculées** :
   ```python
   # Construction de la requête avec filtres
   stmt = select(SeanceCodev)
   if groupe_id:
       stmt = stmt.where(SeanceCodev.groupe_id == groupe_id)
   if statut:
       stmt = stmt.where(SeanceCodev.statut == statut)
   
   # Exécution avec tri
   seances = session.exec(stmt.order_by(SeanceCodev.date_seance.desc())).all()
   
   # Récupération des groupes pour le filtre
   groupes = session.exec(select(GroupeCodev)).all()
   ```
4. **Modèles interrogés** :
   - `SeanceCodev` : Séances avec filtres
   - `GroupeCodev` : Groupes pour le filtre
5. **Validation schématique** :
   - **Contrôle d'accès** : `codev_access_required()`
   - **Filtres optionnels** : Groupe et statut
6. **Services appelés** : Aucun (requête directe)
7. **Transmission** : Template avec liste et filtres
8. **Affichage** : Liste des séances avec filtres

### 2.9 Création de Séance

**Route** : `POST /codev/seances/creer`
**Nom** : `codev_seance_creer`
**Redirection** : `/codev/seances`

#### Pipeline Complet

1. **Déclenchement** : Soumission du formulaire de création de séance
2. **Route déclenchée** : `codev_seance_creer`
3. **Variables calculées** :
   ```python
   # Conversion de la date
   date_seance_dt = datetime.fromisoformat(date_seance.replace('Z', '+00:00'))
   
   # Création de la séance
   seance_data = SeanceCodevCreate(
       groupe_id=groupe_id,
       numero_seance=numero_seance,
       date_seance=date_seance_dt,
       lieu=lieu,
       animateur_id=animateur_id,
       duree_minutes=duree_minutes,
       objectifs=objectifs,
       statut=StatutSeanceCodev.PLANIFIEE.value
   )
   
   seance = CodevService.create_seance(session, seance_data)
   ```
4. **Modèles interrogés** :
   - `SeanceCodev` : Création du nouvel enregistrement
5. **Validation schématique** :
   - **Contrôle d'accès** : `codev_access_required()`
   - **Conversion de date** : Format ISO avec gestion d'erreurs
   - **Champs obligatoires** : Groupe, numéro, date
6. **Services appelés** :
   - **CodevService** : `create_seance()` pour création
7. **Transmission** : Redirection vers la liste des séances
8. **Affichage** : Liste des séances mise à jour

### 2.10 Statistiques du Codev

**Route** : `GET /codev/statistiques`
**Nom** : `codev_statistiques`
**Template** : `codev/statistiques.html`

#### Pipeline Complet

1. **Déclenchement** : Clic sur "Statistiques" dans la navigation
2. **Route déclenchée** : `codev_statistiques`
3. **Variables calculées** :
   ```python
   # Statistiques générales
   nb_cycles = session.exec(select(func.count()).select_from(CycleCodev)).one()
   nb_groupes = session.exec(select(func.count()).select_from(GroupeCodev)).one()
   nb_membres = session.exec(select(func.count()).select_from(MembreGroupeCodev)).one()
   nb_seances = session.exec(select(func.count()).select_from(SeanceCodev)).one()
   nb_presentations = session.exec(select(func.count()).select_from(PresentationCodev)).one()
   
   # Répartitions par statut
   cycles_par_statut = session.exec(
       select(CycleCodev.statut, func.count())
       .group_by(CycleCodev.statut)
   ).all()
   
   # Cycles récents et groupes populaires
   cycles_recents = session.exec(
       select(CycleCodev)
       .order_by(CycleCodev.cree_le.desc())
       .limit(5)
   ).all()
   
   groupes_populaires = session.exec(
       select(GroupeCodev, func.count(MembreGroupeCodev.id).label('nb_membres'))
       .select_from(GroupeCodev)
       .join(MembreGroupeCodev, GroupeCodev.id == MembreGroupeCodev.groupe_codev_id)
       .group_by(GroupeCodev.id)
       .order_by(func.count(MembreGroupeCodev.id).desc())
       .limit(5)
   ).all()
   ```
4. **Modèles interrogés** :
   - `CycleCodev` : Cycles et répartitions
   - `GroupeCodev` : Groupes et répartitions
   - `MembreGroupeCodev` : Membres et groupes populaires
   - `SeanceCodev` : Séances et répartitions
   - `PresentationCodev` : Présentations et répartitions
5. **Validation schématique** :
   - **Contrôle d'accès** : `codev_access_required()`
   - **Agrégations** : Comptages et groupements
6. **Services appelés** : Aucun (requêtes directes)
7. **Transmission** : Template avec toutes les statistiques
8. **Affichage** : Page de statistiques complètes

---

## 3. SERVICES MÉTIER

### 3.1 Service de Codéveloppement (`CodevService`)

**Fichier** : `app/services/codev_service.py`
**Description** : Service principal pour la gestion du codéveloppement

#### Méthodes Principales

**`create_cycle_codev()`** :
```python
@staticmethod
def create_cycle_codev(
    session: Session, 
    nom: str,
    programme_id: int,
    promotion_id: Optional[int] = None,
    date_debut: date = None,
    date_fin: date = None,
    nombre_seances: int = 6,
    animateur_principal_id: Optional[int] = None
) -> CycleCodev:
    """Crée un nouveau cycle de codéveloppement"""
    
    if not date_debut:
        date_debut = date.today()
    if not date_fin:
        date_fin = date_debut + timedelta(weeks=nombre_seances * 2)  # 1 séance toutes les 2 semaines
    
    cycle = CycleCodev(
        nom=nom,
        programme_id=programme_id,
        promotion_id=promotion_id,
        date_debut=date_debut,
        date_fin=date_fin,
        nombre_seances_prevues=nombre_seances,
        animateur_principal_id=animateur_principal_id,
        statut=StatutCycleCodev.PLANIFIE.value
    )
    
    session.add(cycle)
    session.commit()
    session.refresh(cycle)
    
    logger.info(f"Cycle de codéveloppement créé: {cycle.nom} (ID: {cycle.id})")
    return cycle
```

**`create_groupe_codev()`** :
```python
@staticmethod
def create_groupe_codev(
    session: Session,
    cycle_id: int,
    groupe_id: int,
    nom_groupe: str,
    animateur_id: Optional[int] = None,
    capacite_max: int = 12
) -> GroupeCodev:
    """Crée un groupe de codéveloppement dans un cycle"""
    
    groupe_codev = GroupeCodev(
        cycle_id=cycle_id,
        groupe_id=groupe_id,
        nom_groupe=nom_groupe,
        animateur_id=animateur_id,
        capacite_max=capacite_max,
        statut=StatutGroupeCodev.EN_CONSTITUTION.value
    )
    
    session.add(groupe_codev)
    session.commit()
    session.refresh(groupe_codev)
    
    logger.info(f"Groupe de codéveloppement créé: {nom_groupe} (ID: {groupe_codev.id})")
    return groupe_codev
```

**`add_membre_groupe()`** :
```python
@staticmethod
def add_membre_groupe(
    session: Session,
    groupe_codev_id: int,
    candidat_id: int,
    role_special: Optional[str] = None
) -> MembreGroupeCodev:
    """Ajoute un candidat à un groupe de codéveloppement"""
    
    # Vérifier que le groupe n'est pas complet
    groupe_codev = session.get(GroupeCodev, groupe_codev_id)
    if not groupe_codev:
        raise ValueError("Groupe de codéveloppement introuvable")
    
    membres_actifs = session.exec(
        select(func.count()).select_from(MembreGroupeCodev)
        .where(and_(
            MembreGroupeCodev.groupe_codev_id == groupe_codev_id,
            MembreGroupeCodev.statut == StatutMembreGroupe.ACTIF.value
        ))
    ).one()
    
    if membres_actifs >= groupe_codev.capacite_max:
        raise ValueError("Le groupe est complet")
    
    # Vérifier que le candidat n'est pas déjà dans le groupe
    existing = session.exec(
        select(MembreGroupeCodev).where(and_(
            MembreGroupeCodev.groupe_codev_id == groupe_codev_id,
            MembreGroupeCodev.candidat_id == candidat_id
        ))
    ).first()
    
    if existing:
        raise ValueError("Le candidat est déjà dans ce groupe")
    
    membre = MembreGroupeCodev(
        groupe_codev_id=groupe_codev_id,
        candidat_id=candidat_id,
        role_special=role_special,
        statut=StatutMembreGroupe.ACTIF.value
    )
    
    session.add(membre)
    session.commit()
    session.refresh(membre)
    
    logger.info(f"Candidat {candidat_id} ajouté au groupe {groupe_codev_id}")
    return membre
```

**`planifier_presentations_seance()`** :
```python
@staticmethod
def planifier_presentations_seance(
    session: Session,
    seance_id: int,
    candidats_ids: List[int],
    ordre_presentations: Optional[List[int]] = None
) -> List[PresentationCodev]:
    """Planifie les présentations pour une séance"""
    
    seance = session.get(SeanceCodev, seance_id)
    if not seance:
        raise ValueError("Séance introuvable")
    
    presentations = []
    
    # Si pas d'ordre spécifié, utiliser l'ordre de la liste
    if not ordre_presentations:
        ordre_presentations = list(range(1, len(candidats_ids) + 1))
    
    for i, candidat_id in enumerate(candidats_ids):
        presentation = PresentationCodev(
            seance_id=seance_id,
            candidat_id=candidat_id,
            ordre_presentation=ordre_presentations[i],
            probleme_expose="",  # À remplir par le candidat
            statut=StatutPresentation.EN_ATTENTE.value
        )
        session.add(presentation)
        presentations.append(presentation)
    
    session.commit()
    
    for presentation in presentations:
        session.refresh(presentation)
    
    logger.info(f"{len(presentations)} présentations planifiées pour la séance {seance_id}")
    return presentations
```

**`get_statistiques_cycle()`** :
```python
@staticmethod
def get_statistiques_cycle(session: Session, cycle_id: int) -> Dict[str, Any]:
    """Récupère les statistiques d'un cycle de codéveloppement"""
    
    cycle = session.get(CycleCodev, cycle_id)
    if not cycle:
        return {}
    
    # Nombre de groupes
    nb_groupes = session.exec(
        select(func.count()).select_from(GroupeCodev)
        .where(GroupeCodev.cycle_id == cycle_id)
    ).one()
    
    # Nombre total de membres
    nb_membres = session.exec(
        select(func.count()).select_from(MembreGroupeCodev)
        .join(GroupeCodev, MembreGroupeCodev.groupe_codev_id == GroupeCodev.id)
        .where(GroupeCodev.cycle_id == cycle_id)
    ).one()
    
    # Nombre de séances réalisées
    nb_seances = session.exec(
        select(func.count()).select_from(SeanceCodev)
        .join(Groupe, SeanceCodev.groupe_id == Groupe.id)
        .join(GroupeCodev, Groupe.id == GroupeCodev.groupe_id)
        .where(GroupeCodev.cycle_id == cycle_id)
        .where(SeanceCodev.statut == StatutSeanceCodev.TERMINEE.value)
    ).one()
    
    # Nombre de présentations terminées
    nb_presentations = session.exec(
        select(func.count()).select_from(PresentationCodev)
        .join(SeanceCodev, PresentationCodev.seance_id == SeanceCodev.id)
        .join(Groupe, SeanceCodev.groupe_id == Groupe.id)
        .join(GroupeCodev, Groupe.id == GroupeCodev.groupe_id)
        .where(GroupeCodev.cycle_id == cycle_id)
        .where(PresentationCodev.statut == StatutPresentation.RETOUR_FAIT.value)
    ).one()
    
    return {
        "cycle": cycle,
        "nb_groupes": nb_groupes,
        "nb_membres": nb_membres,
        "nb_seances": nb_seances,
        "nb_presentations": nb_presentations,
        "taux_realisation": (nb_seances / cycle.nombre_seances_prevues * 100) if cycle.nombre_seances_prevues > 0 else 0
    }
```

#### Fonctionnalités Avancées

**Gestion des cycles** :
- **Création automatique** : Dates de fin calculées automatiquement
- **Statuts multiples** : Planifié, en cours, terminé
- **Animateur principal** : Responsable du cycle
- **Objectifs** : Définition des objectifs du cycle

**Gestion des groupes** :
- **Capacité limitée** : Vérification de la capacité maximale
- **Rôles spéciaux** : Secrétaire, rapporteur, etc.
- **Statuts de membre** : Actif, inactif, suspendu
- **Intégration** : Processus d'ajout de membres

**Planification des séances** :
- **Ordre des présentations** : Gestion de l'ordre d'intervention
- **Statuts de présentation** : En attente, en cours, terminée
- **Engagements** : Suivi des engagements des candidats
- **Retours d'expérience** : Notes des candidats après test

**Statistiques et métriques** :
- **Taux de réalisation** : Pourcentage de séances réalisées
- **Répartitions par statut** : Cycles, groupes, séances, présentations
- **Groupes populaires** : Groupes avec le plus de membres
- **Cycles récents** : Derniers cycles créés

---

## 4. ROUTES API

### 4.1 API des Cycles

**Route** : `GET /api/codev/cycles`
**Nom** : `api_cycles`
**Réponse** : `List[CycleCodevResponse]`

#### Pipeline Complet

1. **Déclenchement** : Appel API pour récupérer les cycles
2. **Route déclenchée** : `api_cycles`
3. **Variables calculées** :
   ```python
   # Construction de la requête avec filtre statut
   stmt = select(CycleCodev)
   if statut:
       stmt = stmt.where(CycleCodev.statut == statut)
   
   # Exécution avec tri
   cycles = session.exec(stmt.order_by(CycleCodev.date_debut.desc())).all()
   ```
4. **Modèles interrogés** :
   - `CycleCodev` : Cycles avec filtre statut
5. **Validation schématique** :
   - **Contrôle d'accès** : `codev_access_required()`
   - **Filtre optionnel** : Statut pour restriction
6. **Services appelés** : Aucun (requête directe)
7. **Transmission** : Liste des cycles en JSON
8. **Affichage** : Données JSON pour consommation API

### 4.2 API de Création de Cycle

**Route** : `POST /api/codev/cycles`
**Nom** : `api_create_cycle`
**Réponse** : `CycleCodevResponse`

#### Pipeline Complet

1. **Déclenchement** : Appel API pour créer un cycle
2. **Route déclenchée** : `api_create_cycle`
3. **Variables calculées** :
   ```python
   # Création du cycle via le service
   cycle = CodevService.create_cycle_codev(
       session=session,
       nom=cycle_data.nom,
       programme_id=cycle_data.programme_id,
       promotion_id=cycle_data.promotion_id,
       date_debut=cycle_data.date_debut,
       date_fin=cycle_data.date_fin,
       nombre_seances=cycle_data.nombre_seances_prevues,
       animateur_principal_id=cycle_data.animateur_principal_id
   )
   ```
4. **Modèles interrogés** :
   - `CycleCodev` : Création du nouvel enregistrement
5. **Validation schématique** :
   - **Contrôle d'accès** : `codev_access_required()`
   - **Validation des données** : Schéma `CycleCodevCreate`
6. **Services appelés** :
   - **CodevService** : `create_cycle_codev()` pour création
7. **Transmission** : Cycle créé en JSON
8. **Affichage** : Données JSON du cycle créé

### 4.3 API de Statistiques de Cycle

**Route** : `GET /api/codev/cycles/{cycle_id}/statistiques`
**Nom** : `api_cycle_stats`
**Réponse** : `StatistiquesCycleCodev`

#### Pipeline Complet

1. **Déclenchement** : Appel API pour récupérer les statistiques
2. **Route déclenchée** : `api_cycle_stats`
3. **Variables calculées** :
   ```python
   # Récupération des statistiques via le service
   stats = CodevService.get_statistiques_cycle(session, cycle_id)
   ```
4. **Modèles interrogés** :
   - `CycleCodev` : Cycle principal
   - `GroupeCodev` : Groupes du cycle
   - `MembreGroupeCodev` : Membres des groupes
   - `SeanceCodev` : Séances réalisées
   - `PresentationCodev` : Présentations terminées
5. **Validation schématique** :
   - **Contrôle d'accès** : `codev_access_required()`
   - **Existence du cycle** : Vérification de l'existence
6. **Services appelés** :
   - **CodevService** : `get_statistiques_cycle()` pour métriques
7. **Transmission** : Statistiques en JSON
8. **Affichage** : Données JSON des statistiques

### 4.4 API de Planification de Séance

**Route** : `POST /api/codev/seances/{seance_id}/planifier`
**Nom** : `api_planifier_seance`
**Réponse** : `{"message": "X présentations planifiées"}`

#### Pipeline Complet

1. **Déclenchement** : Appel API pour planifier une séance
2. **Route déclenchée** : `api_planifier_seance`
3. **Variables calculées** :
   ```python
   # Planification des présentations via le service
   presentations = CodevService.planifier_presentations_seance(
       session=session,
       seance_id=seance_id,
       candidats_ids=planification.candidats_ids,
       ordre_presentations=planification.ordre_presentations
   )
   ```
4. **Modèles interrogés** :
   - `SeanceCodev` : Séance concernée
   - `PresentationCodev` : Création des présentations
5. **Validation schématique** :
   - **Contrôle d'accès** : `codev_access_required()`
   - **Validation des données** : Schéma `PlanificationSeance`
6. **Services appelés** :
   - **CodevService** : `planifier_presentations_seance()` pour planification
7. **Transmission** : Message de confirmation en JSON
8. **Affichage** : Confirmation JSON de la planification

### 4.5 API de Prise d'Engagement

**Route** : `POST /api/codev/presentations/{presentation_id}/engagement`
**Nom** : `api_prendre_engagement`
**Réponse** : `{"message": "Engagement pris avec succès"}`

#### Pipeline Complet

1. **Déclenchement** : Appel API pour prendre un engagement
2. **Route déclenchée** : `api_prendre_engagement`
3. **Variables calculées** :
   ```python
   # Marquage de l'engagement via le service
   presentation = CodevService.marquer_engagement_pris(
       session=session,
       presentation_id=presentation_id,
       engagement=engagement.engagement,
       delai_engagement=engagement.delai_engagement
   )
   ```
4. **Modèles interrogés** :
   - `PresentationCodev` : Mise à jour de la présentation
5. **Validation schématique** :
   - **Contrôle d'accès** : `codev_access_required()`
   - **Validation des données** : Schéma `EngagementCandidat`
6. **Services appelés** :
   - **CodevService** : `marquer_engagement_pris()` pour engagement
7. **Transmission** : Message de confirmation en JSON
8. **Affichage** : Confirmation JSON de l'engagement

### 4.6 API de Retour d'Expérience

**Route** : `POST /api/codev/presentations/{presentation_id}/retour`
**Nom** : `api_ajouter_retour`
**Réponse** : `{"message": "Retour d'expérience ajouté avec succès"}`

#### Pipeline Complet

1. **Déclenchement** : Appel API pour ajouter un retour
2. **Route déclenchée** : `api_ajouter_retour`
3. **Variables calculées** :
   ```python
   # Ajout du retour via le service
   presentation = CodevService.ajouter_retour_experience(
       session=session,
       presentation_id=presentation_id,
       notes_candidat=retour.notes_candidat
   )
   ```
4. **Modèles interrogés** :
   - `PresentationCodev` : Mise à jour de la présentation
5. **Validation schématique** :
   - **Contrôle d'accès** : `codev_access_required()`
   - **Validation des données** : Schéma `RetourExperience`
6. **Services appelés** :
   - **CodevService** : `ajouter_retour_experience()` pour retour
7. **Transmission** : Message de confirmation en JSON
8. **Affichage** : Confirmation JSON du retour

---

## 5. VALIDATION ET SÉCURITÉ

### 5.1 Contrôle d'Accès

**Fonction `codev_access_required()`** :
```python
def codev_access_required(current_user: User):
    """Vérifie que l'utilisateur a accès au module Codev"""
    allowed_roles = [
        UserRole.ADMINISTRATEUR.value,
        UserRole.DIRECTEUR_TECHNIQUE.value,
        UserRole.RESPONSABLE_PROGRAMME.value,
        UserRole.COORDINATEUR.value,
        UserRole.CONSEILLER.value,
        UserRole.FORMATEUR.value
    ]
    if current_user.role not in allowed_roles:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Accès non autorisé au module Codéveloppement"
        )
```

**Rôles autorisés** :
- **Administrateur** : Accès complet
- **Directeur technique** : Accès complet
- **Responsable programme** : Accès complet
- **Coordinateur** : Accès complet
- **Conseiller** : Accès complet
- **Formateur** : Accès complet

### 5.2 Validation des Données

**Validation côté serveur** :
- **Champs obligatoires** : Nom, programme, dates pour les cycles
- **Capacité des groupes** : Vérification de la limite maximale
- **Dates cohérentes** : Date de fin >= date de début
- **Conversion des types** : Dates, heures, nombres

**Validation côté client** :
- **Champs requis** : Validation HTML5 et JavaScript
- **Format des dates** : Validation des formats de date
- **Confirmation des actions** : Prompts de confirmation

### 5.3 Sécurité des Accès

**Contrôles de sécurité** :
- **Authentification** : Vérification de l'utilisateur connecté
- **Autorisation** : Vérification des droits d'accès au module
- **Validation des données** : Contrôles sur les entrées
- **Gestion d'erreurs** : Try/catch avec redirections appropriées

**Protection des données** :
- **Isolation des données** : Accès limité aux cycles autorisés
- **Validation des relations** : Vérification des liens entre entités
- **Logs des actions** : Traçabilité des créations et modifications

---

## 6. PERFORMANCE ET OPTIMISATION

### 6.1 Optimisation des Requêtes

**Jointures optimisées** :
- **Cycles + Groupes + Membres** : Une seule requête pour les statistiques
- **Séances + Présentations** : Chargement des relations
- **Évitement des N+1** : Chargement en lot des relations

**Cache et sessions** :
- **Sessions de base de données** : Pool de connexions
- **Transactions atomiques** : Rollback en cas d'erreur
- **Refresh automatique** : Récupération des IDs générés

### 6.2 Gestion des Statistiques

**Calculs optimisés** :
- **Agrégations SQL** : Comptages et groupements en base
- **Métriques en temps réel** : Calculs à la demande
- **Cache potentiel** : Possibilité de mise en cache des statistiques

---

## 7. MONITORING ET LOGS

### 7.1 Logs de Debug

**Informations loggées** :
- **Actions utilisateur** : Création, modification, suppression
- **Planification** : Création de séances et présentations
- **Engagements** : Prise d'engagements et retours
- **Statistiques** : Calculs et métriques

### 7.2 Métriques de Performance

**KPI calculés** :
- **Total des cycles** : Comptage global
- **Répartition par statut** : Cycles, groupes, séances, présentations
- **Taux de réalisation** : Pourcentage de séances réalisées
- **Groupes populaires** : Groupes avec le plus de membres

---

## 8. ÉVOLUTION ET MAINTENANCE

### 8.1 Ajout de Nouveaux Types de Contribution

**Processus d'ajout** :
1. **Modification de l'enum** : Ajout du nouveau type dans TypeContribution
2. **Mise à jour du service** : Adaptation du service de contributions
3. **Mise à jour de l'interface** : Ajout dans les formulaires
4. **Tests** : Validation avec des cas de test

### 8.2 Modification des Statuts

**Processus de modification** :
1. **Mise à jour de l'enum** : Modification des statuts
2. **Mise à jour de la logique** : Adaptation des transitions
3. **Mise à jour de l'interface** : Adaptation des formulaires
4. **Migration des données** : Mise à jour des données existantes

---

*Document généré automatiquement - Pipeline de gestion du codéveloppement LIA WEB*
