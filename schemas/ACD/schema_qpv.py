from pydantic import BaseModel

class Adresse(BaseModel): #Modèle pydantic pour la validation de l'adresse transmise
    address: str
    

    
    