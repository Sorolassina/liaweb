from datetime import date
from typing import Optional

def build_success_result_html(message: str, download_url: str, filename: str = None, ignored_list: Optional[list] = None) -> str:
    today = date.today().strftime("%d/%m/%Y")
    filename_info = f"<b>{filename}</b><br>" if filename else ""

    ignored_html = ""
    if ignored_list:
        ignored_items = "".join(f"<li>{item}</li>" for item in ignored_list)
        ignored_html = f"""
            <br>
            <span style="cursor:pointer;" onclick="toggleIgnored()">
                🔽 Fichiers ignorés <span id="toggleIcon">▼</span>
            </span>
            <ul id="ignoredList" style="max-height:0; overflow:hidden; transition:max-height 0.3s ease;">
                {ignored_items}
            </ul>
        """

    return f"""
        <div style="
            background-color: rgba(255, 255, 255, 0.3);
            padding: 10px;
            border-radius: 5px;
            font-size: 12px;
            font-weight: bold;
            text-align: left;
            width: 400px;
            margin: 20px auto;">
            📅 Aujourd'hui : {today}<br>
            ✅ {filename_info}{message}<br>
            🔗 <a href="{download_url}" target="_blank" style="color:red; text-decoration:none;">
                Cliquer ici pour afficher le fichier
            </a>
            {ignored_html}
        </div>
    """
