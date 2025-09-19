# Architecture du Système E-Learning

```mermaid
graph TB
    %% Entités principales
    subgraph "Base de données"
        U[User]
        P[Programme]
        I[Inscription]
        C[Candidat]
    end
    
    subgraph "E-Learning Core"
        R[RessourceElearning]
        M[ModuleElearning]
        MR[ModuleRessource]
        PR[ProgressionElearning]
        O[ObjectifElearning]
    end
    
    subgraph "Évaluation"
        Q[QuizElearning]
        RQ[ReponseQuiz]
        CERT[CertificatElearning]
    end
    
    %% Relations
    P --> M
    M --> MR
    R --> MR
    I --> PR
    M --> PR
    R --> PR
    P --> O
    R --> Q
    I --> RQ
    Q --> RQ
    I --> CERT
    M --> CERT
    
    %% Services
    subgraph "Services"
        ES[ElearningService]
        AS[AuthService]
        FS[FileService]
    end
    
    %% API
    subgraph "API Routes"
        API1["/elearning/ressources"]
        API2["/elearning/modules"]
        API3["/elearning/progression"]
        API4["/elearning/quiz"]
        API5["/elearning/statistiques"]
    end
    
    %% Templates
    subgraph "Interface Web"
        T1[dashboard.html]
        T2[modules.html]
        T3[module_detail.html]
        T4[candidat_progression.html]
    end
    
    %% Flux
    ES --> API1
    ES --> API2
    ES --> API3
    ES --> API4
    ES --> API5
    
    API1 --> T1
    API2 --> T2
    API3 --> T3
    API4 --> T4
    
    %% Permissions
    subgraph "Sécurité"
        AUTH[Authentification JWT]
        ROLE[Contrôle des rôles]
        PERM[Permissions par ressource]
    end
    
    AUTH --> ROLE
    ROLE --> PERM
    PERM --> ES
```

## Flux de données

### 1. Création de contenu
```
Formateur → ElearningService → RessourceElearning → ModuleElearning
```

### 2. Apprentissage candidat
```
Candidat → ProgressionElearning → RessourceElearning → QuizElearning
```

### 3. Évaluation
```
QuizElearning → ReponseQuiz → Score → CertificatElearning
```

### 4. Statistiques
```
ProgressionElearning → ElearningService → Statistiques → Dashboard
```

## Types de ressources

- **Vidéo** : Cours en ligne, tutoriels
- **Document** : PDF, présentations, guides
- **Quiz** : Évaluations interactives
- **Lien** : Ressources externes
- **Audio** : Podcasts, enregistrements

## États de progression

- **non_commence** : Ressource pas encore commencée
- **en_cours** : Ressource en cours de consultation
- **termine** : Ressource terminée avec succès
- **abandonne** : Ressource abandonnée

## Rôles et permissions

- **Administrateur** : Accès complet au système
- **Responsable Programme** : Gestion des modules de son programme
- **Formateur** : Création de ressources pédagogiques
- **Candidat** : Accès à ses modules et progression
