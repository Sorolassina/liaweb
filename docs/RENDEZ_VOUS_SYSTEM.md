# Gestion des Rendez-vous

## Vue d'ensemble

Le module de gestion des rendez-vous permet de planifier, organiser et suivre les rendez-vous entre les conseillers et les candidats inscrits dans les différents programmes (ACD, ACI, ACT).

## Fonctionnalités

### 📅 Planification des rendez-vous
- Création de nouveaux rendez-vous
- Attribution d'un conseiller
- Définition du type de rendez-vous (entretien, suivi, coaching, autre)
- Planification de la date et heure
- Spécification du lieu
- Ajout de notes

### 🔍 Recherche et filtrage
- Filtrage par programme
- Filtrage par conseiller
- Filtrage par type de rendez-vous
- Filtrage par statut
- Filtrage par période
- Recherche par nom de candidat
- Recherche par nom d'entreprise

### 📊 Statistiques
- Nombre total de rendez-vous
- Rendez-vous planifiés
- Rendez-vous terminés
- Rendez-vous annulés
- Répartition par type
- Taux de réalisation

### ✏️ Gestion des rendez-vous
- Consultation des détails
- Modification des informations
- Mise à jour du statut
- Suppression des rendez-vous

## Structure des données

### Modèle RendezVous
```python
class RendezVous(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    inscription_id: int = Field(foreign_key="inscription.id")
    conseiller_id: Optional[int] = Field(foreign_key="user.id")
    type_rdv: TypeRDV = TypeRDV.ENTRETIEN
    statut: StatutRDV = StatutRDV.PLANIFIE
    debut: datetime
    fin: Optional[datetime] = None
    lieu: Optional[str] = None
    notes: Optional[str] = None
```

### Types de rendez-vous
- `entretien` : Entretien initial ou de suivi
- `suivi` : Session de suivi régulier
- `coaching` : Session de coaching personnalisé
- `autre` : Autre type de rendez-vous

### Statuts des rendez-vous
- `planifie` : Rendez-vous planifié
- `termine` : Rendez-vous terminé
- `annule` : Rendez-vous annulé

## Routes disponibles

### Pages web
- `GET /rendez-vous` : Liste des rendez-vous avec filtres
- `GET /rendez-vous/creer` : Formulaire de création
- `POST /rendez-vous/creer` : Création d'un rendez-vous
- `GET /rendez-vous/{id}` : Détail d'un rendez-vous
- `POST /rendez-vous/{id}/modifier` : Modification d'un rendez-vous
- `POST /rendez-vous/{id}/supprimer` : Suppression d'un rendez-vous

### API
- `GET /rendez-vous/api/search` : Recherche de rendez-vous (JSON)
- `GET /rendez-vous/api/statistiques` : Statistiques (JSON)

## Installation

1. **Exécuter la migration de base de données** :
   ```bash
   python scripts/migrate_rendez_vous.py
   ```

2. **Vérifier que le routeur est bien inclus** dans `routers/__init__.py`

3. **Redémarrer l'application** pour prendre en compte les nouveaux routes

## Utilisation

### Accès au module
- Via le menu principal : **ACD > Rendez-vous** ou **ACI > Rendez-vous**
- URL directe : `/rendez-vous`

### Création d'un rendez-vous
1. Cliquer sur "Nouveau Rendez-vous"
2. Sélectionner le candidat (recherche par nom/email/entreprise)
3. Choisir le conseiller (optionnel)
4. Définir le type et le statut
5. Planifier la date et heure
6. Spécifier le lieu et ajouter des notes
7. Sauvegarder

### Gestion des rendez-vous
- **Voir** : Cliquer sur l'icône œil pour consulter les détails
- **Modifier** : Cliquer sur l'icône crayon pour éditer
- **Supprimer** : Cliquer sur l'icône poubelle (avec confirmation)

## Permissions

Le module respecte les permissions existantes :
- **Conseillers** : Peuvent voir et gérer leurs propres rendez-vous
- **Coordinateurs** : Accès complet au module
- **Responsables de programme** : Accès aux rendez-vous de leur programme
- **Administrateurs** : Accès complet

## Intégration

### Avec les inscriptions
- Chaque rendez-vous est lié à une inscription
- Affichage automatique des informations du candidat
- Accès aux détails de l'entreprise

### Avec les utilisateurs
- Attribution automatique des conseillers
- Respect des rôles et permissions
- Historique des rendez-vous par conseiller

## Personnalisation

### Ajout de nouveaux types
Modifier l'enum `TypeRDV` dans `models/enums.py` :
```python
class TypeRDV(str, Enum):
    ENTRETIEN = "entretien"
    SUIVI = "suivi"
    COACHING = "coaching"
    FORMATION = "formation"  # Nouveau type
    AUTRE = "autre"
```

### Ajout de nouveaux statuts
Modifier l'enum `StatutRDV` dans `models/enums.py` :
```python
class StatutRDV(str, Enum):
    PLANIFIE = "planifie"
    CONFIRME = "confirme"  # Nouveau statut
    TERMINE = "termine"
    ANNULE = "annule"
```

## Support

Pour toute question ou problème :
1. Vérifier les logs de l'application
2. Consulter la documentation des modèles
3. Contacter l'équipe de développement
