from pydantic import BaseModel, Field, validator
from typing import Optional
import re

class Adresse(BaseModel):
    """
    Modèle Pydantic pour la validation d'adresses françaises
    Utilisé pour la vérification QPV et la préinscription
    """
    # Champs optionnels pour une validation plus fine
    numero: Optional[str] = Field(
        None,
        max_length=10,
        description="Numéro de rue",
        example="10"
    )
    
    rue: str = Field(
        ...,
        max_length=100,
        description="Nom de la rue",
        example="Rue de la Paix"
    )
    
    code_postal: str = Field(
        ...,
        max_length=5,
        description="Code postal français",
        example="75001"
    )
    
    ville: str = Field(
        ...,
        max_length=50,
        description="Nom de la ville",
        example="Paris"
    )
    
    # Champ pour l'adresse consolidée (généré automatiquement)
    address: Optional[str] = Field(
        None,
        description="Adresse consolidée automatiquement",
        example="10 Rue de la Paix, 75001 Paris"
    )
    
    @validator('numero')
    def validate_numero(cls, v):
        """Validation du numéro de rue"""
        if v is None:
            return v
        
        numero_clean = v.strip()
        
        # Vérifier la longueur
        if len(numero_clean) < 1 or len(numero_clean) > 10:
            raise ValueError("Le numéro doit contenir entre 1 et 10 caractères")
        
        # Vérifier qu'il commence par un chiffre
        if not re.match(r'^\d', numero_clean):
            raise ValueError("Le numéro doit commencer par un chiffre")
        
        # Vérifier qu'il ne contient que des chiffres, lettres, espaces, tirets et barres obliques
        if not re.match(r'^[0-9a-zA-ZÀ-ÿ\s\-/]+$', numero_clean):
            raise ValueError("Le numéro ne peut contenir que des chiffres, lettres, espaces, tirets et barres obliques")
        
        return numero_clean
    
    @validator('rue')
    def validate_rue(cls, v):
        """Validation du nom de rue"""
        if v is None:
            return v
        
        rue_clean = v.strip()
        
        # Vérifier la longueur
        if len(rue_clean) < 2:
            raise ValueError("Le nom de rue doit contenir au moins 2 caractères")
        
        if len(rue_clean) > 100:
            raise ValueError("Le nom de rue ne peut pas dépasser 100 caractères")
        
        # Vérifier qu'il ne contient que des lettres, espaces, tirets, apostrophes et chiffres
        if not re.match(r"^[a-zA-ZÀ-ÿ0-9\s\-']+$", rue_clean):
            raise ValueError("Le nom de rue ne peut contenir que des lettres, chiffres, espaces, tirets et apostrophes")
        
        # Vérifier qu'il ne commence pas par un espace ou un tiret
        if rue_clean.startswith((' ', '-')):
            raise ValueError("Le nom de rue ne peut pas commencer par un espace ou un tiret")
        
        # Vérifier qu'il ne se termine pas par un espace ou un tiret
        if rue_clean.endswith((' ', '-')):
            raise ValueError("Le nom de rue ne peut pas se terminer par un espace ou un tiret")
        
        return rue_clean
    
    @validator('code_postal')
    def validate_code_postal(cls, v):
        """Validation du code postal français"""
        if v is None:
            return v
        
        # Nettoyer le code postal
        cp_clean = v.strip()
        
        # Vérifier le format (5 chiffres)
        if not re.match(r'^\d{5}$', cp_clean):
            raise ValueError("Le code postal doit être composé de 5 chiffres")
        
        # Vérifier la plage valide (01000-95999)
        cp_num = int(cp_clean)
        if cp_num < 1000 or cp_num > 95999:
            raise ValueError("Le code postal doit être entre 01000 et 95999")
        
        return cp_clean
    
    @validator('ville')
    def validate_ville(cls, v):
        """Validation du nom de ville"""
        if v is None:
            return v
        
        ville_clean = v.strip()
        
        # Vérifier la longueur
        if len(ville_clean) < 2:
            raise ValueError("Le nom de la ville doit contenir au moins 2 caractères")
        
        # Vérifier qu'il n'y a que des lettres, espaces, tirets et apostrophes
        if not re.match(r"^[a-zA-ZÀ-ÿ\s\-']+$", ville_clean):
            raise ValueError("Le nom de la ville ne peut contenir que des lettres, espaces, tirets et apostrophes")
        
        return ville_clean
    
    @validator('*', always=True)
    def consolidate_address(cls, v, values):
        """Consolide automatiquement l'adresse si les champs décomposés sont fournis"""
        # Si on a déjà une adresse consolidée, ne rien faire
        if values.get('address'):
            return v
        
        # Si on a tous les champs décomposés, consolider
        numero = values.get('numero')
        rue = values.get('rue')
        code_postal = values.get('code_postal')
        ville = values.get('ville')
        
        # rue, code_postal et ville sont maintenant obligatoires, donc on peut consolider si on a le numéro
        if all([rue, code_postal, ville]) and numero:
            values['address'] = f"{numero} {rue}, {code_postal} {ville}"
        elif all([rue, code_postal, ville]):
            # Si pas de numéro, consolider sans numéro
            values['address'] = f"{rue}, {code_postal} {ville}"
        
        return v
    
    class Config:
        """Configuration Pydantic"""
        json_schema_extra = {
            "example": {
                "numero": "10",
                "rue": "Rue de la Paix",
                "code_postal": "75001",
                "ville": "Paris",
                "address": "10 Rue de la Paix, 75001 Paris"
            },
            "description": "Adresse française avec rue, code postal et ville obligatoires"
        }