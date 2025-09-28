from pydantic import BaseModel, field_validator

class SiretRequest(BaseModel):
    numero_siret: str

    @field_validator("numero_siret")
    @classmethod
    def validate_digi_content(cls, v: str) -> str:
        if not v.isdigit():
            raise ValueError("Le numéro SIRET/SIREN ne doit contenir que des chiffres.")
        if len(v) not in [9, 14]:
            raise ValueError("Merci de saisir un numéro SIREN (9 chiffres) ou SIRET (14 chiffres).")
        return v