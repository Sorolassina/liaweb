
import os
import base64
from app.config import FICHIERS_DIR


# 🔧 Exemple de fonction à adapter à ton projet
def get_pdf_path(filename: str) -> str:
    output_dir = FICHIERS_DIR
    os.makedirs(output_dir, exist_ok=True)
    return os.path.join(output_dir, filename)

def encode_file_to_base64(file_path: str) -> str:
    with open(file_path, "rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")

