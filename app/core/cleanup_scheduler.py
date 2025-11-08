import os
import time
from apscheduler.schedulers.background import BackgroundScheduler
from .config import STATIC_IMAGES_DIR, STATIC_MAPS_DIR, FICHIERS_DIR

# === Paramètres === 10080=Une semaine
CLEANUP_CONFIG = [
    {
        "folder": STATIC_IMAGES_DIR ,
        "extensions": (".png", ".jpg", ".jpeg"),
        "age_limit_minutes": 1440
    },
    {
        "folder": FICHIERS_DIR,
        "extensions": (".png", ".jpg", ".jpeg",".zip",".html", ".pdf", ".csv"),
        "age_limit_minutes": 3360
    },
    {
        "folder": STATIC_MAPS_DIR,
        "extensions": (".html",),
        "age_limit_minutes": 1440
    }
]

scheduler = BackgroundScheduler()

def cleanup_temp_files():
    now = time.time()
    for config in CLEANUP_CONFIG:
        folder = config["folder"]
        extensions = config["extensions"]
        age_limit = config["age_limit_minutes"]

        if not os.path.exists(folder):
            print(f"📁 Dossier introuvable : {folder}")
            continue

        deleted_files = []

        for filename in os.listdir(folder):
            file_path = os.path.join(folder, filename)
            if os.path.isfile(file_path) and file_path.lower().endswith(extensions):
                file_age = now - os.path.getmtime(file_path)
                if file_age > age_limit * 60:
                    try:
                        os.remove(file_path)
                        deleted_files.append(filename)
                    except Exception as e:
                        print(f"⚠️ Erreur suppression {filename} : {e}")

        if deleted_files:
            print(f"🧹 {len(deleted_files)} fichiers supprimés de {folder} :", deleted_files)

def start_cleanup_scheduler():
    if not scheduler.running:
        # Nettoyage quotidien à 01h00 du matin
        scheduler.add_job(cleanup_temp_files, "cron", hour=1, minute=0)
        scheduler.start()
        #print("✅ Scheduler de nettoyage lancé (quotidien à 01h00).")
    else:
        pass
        #print("🔁 Scheduler déjà actif.")

def stop_cleanup_scheduler():
    scheduler.shutdown()
    #print("🛑 Scheduler arrêté proprement.")
