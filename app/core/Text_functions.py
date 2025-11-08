import re

def replace_ignore_case(text: str, replacements: dict) -> str:
    for old, new in replacements.items():
        pattern = re.compile(re.escape(old), re.IGNORECASE)
        text = pattern.sub(new, text)
    return text

def modifier_contenu_texte(file_path: str, replacements: dict):
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()
        new_content = replace_ignore_case(content, replacements)
        if new_content != content:
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(new_content)
    except Exception as e:
        print(f"❌ Erreur traitement texte {file_path} : {e}")
