import openpyxl
import zipfile
import tempfile
import os
import re
from pathlib import Path
import xml.etree.ElementTree as ET

def replace_ignore_case(text: str, replacements: dict) -> str:
    for old, new in replacements.items():
        pattern = re.compile(re.escape(old), re.IGNORECASE)
        text = pattern.sub(new, text)
    return text

def modifier_contenu_excel(file_path: str, replacements: dict):
    print(f"🔧 Traitement : {file_path}")
    
    # 1. Modifier cellules et noms de feuilles
    wb = openpyxl.load_workbook(file_path)
    modified = False

    for sheet in wb.worksheets:
        new_title = replace_ignore_case(sheet.title, replacements)
        if new_title != sheet.title:
            sheet.title = new_title
            modified = True

        for row in sheet.iter_rows():
            for cell in row:
                if isinstance(cell.value, str):
                    new_val = replace_ignore_case(cell.value, replacements)
                    if new_val != cell.value:
                        cell.value = new_val
                        modified = True

    if modified:
        wb.save(file_path)
        print("✅ Feuilles et cellules modifiées.")

    # 2. Modifier l'en-tête et le pied de page via accès ZIP (xl/worksheets)
    with tempfile.TemporaryDirectory() as tmp_dir:
        with zipfile.ZipFile(file_path, 'r') as zip_ref:
            zip_ref.extractall(tmp_dir)

        worksheets_dir = os.path.join(tmp_dir, "xl", "worksheets")
        for sheet_xml in Path(worksheets_dir).glob("*.xml"):
            tree = ET.parse(sheet_xml)
            root = tree.getroot()

            for elem in root.iter():
                if elem.text:
                    elem.text = replace_ignore_case(elem.text, replacements)
                if elem.tail:
                    elem.tail = replace_ignore_case(elem.tail, replacements)

            tree.write(sheet_xml, encoding='utf-8', xml_declaration=True)

        # Réécriture du fichier Excel
        #new_path = file_path.replace(".xlsx", "_modifie.xlsx")
        with zipfile.ZipFile(file_path, 'w', zipfile.ZIP_DEFLATED) as zip_out:
            for foldername, _, filenames in os.walk(tmp_dir):
                for filename in filenames:
                    full_path = os.path.join(foldername, filename)
                    arcname = os.path.relpath(full_path, tmp_dir)
                    zip_out.write(full_path, arcname)

    print(f"📁 Nouveau fichier généré : {file_path}")





