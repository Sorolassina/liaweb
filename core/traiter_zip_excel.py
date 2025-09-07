import os
import zipfile
import tempfile
import shutil
import re
from datetime import datetime
import html
from app.utils.Excel_functions import modifier_contenu_excel
from app.utils.Word_functions import modifier_contenu_word
from app.utils.Text_functions import modifier_contenu_texte
from app.utils.Powerpoint_functions import modifier_contenu_powerpoint
from app.utils.temp_dir import create_temp_file

IGNORED_EXTENSIONS = [".pdf", ".zip", ".png", ".jpg", ".jpeg"]
TEXT_EXTENSIONS = [".txt", ".html", ".csv", ".json"]


def valider_fichier_excel(zip_path: str) -> bool:
    """Tente d’ouvrir tous les fichiers Excel dans le ZIP pour valider leur intégrité."""
    import openpyxl

    with zipfile.ZipFile(zip_path, 'r') as zip_ref:
        with tempfile.TemporaryDirectory() as tmp_dir:
            zip_ref.extractall(tmp_dir)
            for root, _, files in os.walk(tmp_dir):
                for file in files:
                    if file.endswith(".xlsx"):
                        file_path = os.path.join(root, file)
                        try:
                            wb = openpyxl.load_workbook(file_path, read_only=True)
                            wb.close()
                        except Exception as e:
                            print(f"❌ Fichier corrompu : {file_path} -> {e}")
                            return False
    return True

def replace_text_ignore_case(text: str, replacements: dict) -> str:
    for old, new in replacements.items():
        if old.lower() in text.lower():
            pattern = re.compile(re.escape(old), re.IGNORECASE)
            new_escaped = html.escape(new)  # Protège &, <, > etc.
            text = pattern.sub(new_escaped, text)
    return text

def process_folder_mirror(original: str, mirror: str, replacements: dict):
    ignored_files = []

    print(f"📁 Début du traitement du dossier miroir...")
    for root, dirs, files in os.walk(original):
        rel_path = os.path.relpath(root, original)
        mirror_root = os.path.join(mirror, rel_path)
        os.makedirs(mirror_root, exist_ok=True)
        print(f"📂 Création dossier miroir : {mirror_root}")

        # Renommer les dossiers dans le miroir
        for dirname in dirs:
            new_dirname = replace_text_ignore_case(dirname, replacements)
            new_dir_path = os.path.join(mirror_root, new_dirname)
            os.makedirs(new_dir_path, exist_ok=True)
            print(f"📁 Dossier renommé : {dirname} ➝ {new_dirname}")

        for file in files:
            src_file = os.path.join(root, file)
            new_file = replace_text_ignore_case(file, replacements)
            dest_file = os.path.join(mirror_root, new_file)
            ext = os.path.splitext(file)[-1].lower()

            print(f"\n📝 Copie de : {src_file} ➝ {dest_file}")
            shutil.copy2(src_file, dest_file)

            try:
                if ext == ".xlsx":
                    print(f"📊 Traitement Excel : {new_file}")
                    modifier_contenu_excel(dest_file, replacements)
                elif ext == ".docx":
                    print(f"📄 Traitement Word : {new_file}")
                    modifier_contenu_word(dest_file, replacements)
                elif ext in TEXT_EXTENSIONS:
                    print(f"📃 Traitement texte : {new_file}")
                    modifier_contenu_texte(dest_file, replacements)
                elif ext == ".pptx":
                    print(f"🎞️ Traitement PowerPoint : {new_file}")
                    modifier_contenu_powerpoint(dest_file, replacements)
                else:
                    print(f"🚫 Ignoré (extension non supportée) : {file}")
                    ignored_files.append((file, "Extension non traitée"))
            except Exception as e:
                print(f"❌ Erreur lors du traitement de {file} : {e}")
                ignored_files.append((file, f"Erreur lors du traitement: {str(e)}"))

    return ignored_files

def traiter_zip_entier(zip_path: str, replacements: dict) -> tuple:
    print(f"\n📦 Décompression du ZIP : {zip_path}")
    
    temp_dir, extract_dir = create_temp_file("unzipped") #os.path.join(temp_dir, "unzipped")
    temp_dir, mirror_dir =  create_temp_file("mirror") #os.path.join(temp_dir, "mirror")
    os.makedirs(extract_dir, exist_ok=True)
    os.makedirs(mirror_dir, exist_ok=True)

    # 1. Extraction initiale
    with zipfile.ZipFile(zip_path, 'r') as zip_ref:
        zip_ref.extractall(extract_dir)

    # 2. Traitement dans le dossier miroir
    print("🔄 Démarrage du traitement du dossier...")
    ignored = process_folder_mirror(extract_dir, mirror_dir, replacements)

    # 3. Construction du ZIP temporaire
    temp_zip_path = os.path.join(temp_dir, "temp_custom.zip")
    with zipfile.ZipFile(temp_zip_path, 'w', zipfile.ZIP_DEFLATED) as zip_out:
        for foldername, _, filenames in os.walk(mirror_dir):
            for filename in filenames:
                file_path = os.path.join(foldername, filename)
                arcname = os.path.relpath(file_path, mirror_dir)
                zip_out.write(file_path, arcname)

    # 4. Validation
    print("🔍 Validation des fichiers Excel dans le ZIP...")
    if valider_fichier_excel(temp_zip_path):
        # 5. Définir le nom final
        base_name = list(replacements.values())[0]
        now = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_name = f"FRANCHISE_{base_name}_{now}.zip"
        final_zip = os.path.join(temp_dir, output_name)

        # 6. Copier le zip validé
        shutil.copy(temp_zip_path, final_zip)
        print(f"✅ ZIP final prêt : {final_zip}")
        
        return final_zip, ignored

    else:
        print("❌ Validation échouée : fichiers Excel corrompus.")
        raise ValueError("Le fichier ZIP contient un ou plusieurs fichiers Excel invalides.")
