import tempfile, os, shutil

def create_temp_file(filename):
    temp_dir = tempfile.mkdtemp()
    path = os.path.join(temp_dir, filename)
    return temp_dir, path

def delete_temp_dir(temp_dir):
    try:
        shutil.rmtree(temp_dir)
    except Exception as e:
        print(f"⚠️ Erreur suppression du dossier temporaire : {e}")