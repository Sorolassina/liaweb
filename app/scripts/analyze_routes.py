"""
Script d'analyse des routes de l'application LIA Coaching
Affiche toutes les routes avec leurs chemins complets, méthodes HTTP et emplacements
"""
import os
import sys
import re
from pathlib import Path
from collections import defaultdict
from typing import List, Dict, Tuple

# Ajouter le répertoire parent au path pour les imports
BASE_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(BASE_DIR))


def extract_routes_from_file(file_path: Path) -> List[Dict]:
    """
    Extrait toutes les routes définies dans un fichier Python
    en analysant les décorateurs @router.get, @router.post, etc.
    """
    routes = []
    
    if not file_path.exists():
        return routes
    
    try:
        content = file_path.read_text(encoding='utf-8')
        lines = content.split('\n')
        
        # Pattern pour trouver les décorateurs de route
        route_pattern = r'@router\.(get|post|put|delete|patch|head|options|trace)\(([^)]+)\)'
        
        for i, line in enumerate(lines, 1):
            match = re.search(route_pattern, line)
            if match:
                method = match.group(1).upper()
                params = match.group(2)
                
                # Extraire le chemin
                path_match = re.search(r'["\']([^"\']+)["\']', params)
                path = path_match.group(1) if path_match else ""
                
                # Extraire le nom de la route
                name_match = re.search(r'name=["\']([^"\']+)["\']', params)
                route_name = name_match.group(1) if name_match else None
                
                # Trouver le nom de la fonction suivante
                func_name = None
                for j in range(i, min(i + 5, len(lines))):
                    func_match = re.search(r'^\s*(async\s+)?def\s+(\w+)', lines[j])
                    if func_match:
                        func_name = func_match.group(2)
                        break
                
                routes.append({
                    'method': method,
                    'path': path,
                    'name': route_name,
                    'function': func_name,
                    'line': i,
                    'file': str(file_path.relative_to(BASE_DIR)),
                    'file_absolute': str(file_path.resolve())
                })
    
    except Exception as e:
        print(f"⚠️  Erreur lors de l'analyse de {file_path}: {e}")
    
    return routes


def get_router_config_from_init() -> List[Tuple[str, str, List[str]]]:
    """Lit la configuration des routers depuis routers/__init__.py"""
    init_file = BASE_DIR / "routers" / "__init__.py"
    router_configs = []
    
    if not init_file.exists():
        print(f"⚠️  Fichier non trouvé: {init_file}")
        return router_configs
    
    try:
        content = init_file.read_text(encoding='utf-8')
        
        # Chercher router_configs - pattern plus flexible
        # Format: (nom_router, "/prefix", ["tag1", "tag2"])
        pattern = r'\((\w+)_router,\s*["\']([^"\']+)["\'],\s*\[([^\]]+)\]\)'
        matches = re.findall(pattern, content, re.MULTILINE)
        
        for match in matches:
            router_base_name = match[0]
            prefix = match[1]
            tags_str = match[2]
            
            # Extraire les tags
            tags = [tag.strip().strip('"\'') for tag in tags_str.split(',') if tag.strip()]
            
            router_configs.append((router_base_name, prefix, tags))
    
    except Exception as e:
        print(f"⚠️  Erreur lors de la lecture de routers/__init__.py: {e}")
        import traceback
        traceback.print_exc()
    
    return router_configs


def get_router_file_mapping() -> Dict:
    """Mappe les routers à leurs fichiers source"""
    router_to_file = {
        'auth': 'routers/auth.py',
        'accueil': 'routers/accueil.py',
        'programmes': 'routers/programmes.py',
        'candidats': 'routers/candidats.py',
        'preinscriptions': 'routers/preinscriptions.py',
        'inscriptions': 'routers/inscriptions.py',
        'documents': 'routers/documents.py',
        'jury': 'routers/jury.py',
        'dashboard': 'routers/dashboard.py',
        'pipelines': 'routers/pipelines.py',
        'pages': 'routers/pages.py',
        'admin': 'routers/admin.py',
        'rendez_vous': 'routers/rendez_vous.py',
        'password_recovery': 'routers/password_recovery.py',
        'seminaire': 'routers/seminaire.py',
        'event': 'routers/event.py',
        'codev': 'routers/codev.py',
        'elearning': 'routers/elearning.py',
        'suivi_mensuel': 'routers/suivi_mensuel.py',
        'admin_schemas': 'routers/admin_schemas.py',
        'directeur_technique': 'routers/directeur_technique.py',
    }
    return router_to_file


def analyze_all_routes():
    """Analyse toutes les routes de l'application"""
    
    print("=" * 80)
    print("🔍 ANALYSE DES ROUTES DE L'APPLICATION LIA COACHING")
    print("=" * 80)
    print()
    
    # Récupérer tous les routers et leurs configurations depuis routers/__init__.py
    router_configs_list = get_router_config_from_init()
    router_to_file = get_router_file_mapping()
    all_routes = []
    route_paths = defaultdict(list)  # Pour détecter les doublons
    
    # Analyser chaque router
    for router_name, prefix, tags in router_configs_list:
        # Trouver le fichier source
        router_file = None
        if router_name in router_to_file:
            router_file = BASE_DIR / router_to_file[router_name]
        else:
            # Essayer de trouver le fichier par le nom du router
            router_file = BASE_DIR / f"routers/{router_name}.py"
        
        # Extraire les routes du fichier
        file_routes = extract_routes_from_file(router_file)
        
        # Construire les chemins complets
        for route in file_routes:
            full_path = prefix.rstrip('/') + '/' + route['path'].lstrip('/')
            full_path = full_path.replace('//', '/')
            
            route_info = {
                **route,
                'full_path': full_path,
                'prefix': prefix,
                'tags': tags,
                'router_name': router_name,
                'router_file': str(router_file.relative_to(BASE_DIR)),
                'router_file_absolute': str(router_file.resolve())
            }
            
            all_routes.append(route_info)
            
            # Enregistrer pour détection de doublons
            route_key = (route['method'], full_path)
            route_paths[route_key].append(route_info)
    
    # Afficher les statistiques
    print(f"📊 STATISTIQUES")
    print(f"   Total de routers: {len(router_configs_list)}")
    print(f"   Total de routes: {len(all_routes)}")
    print()
    
    # Détecter les doublons
    duplicates = {k: v for k, v in route_paths.items() if len(v) > 1}
    if duplicates:
        print("⚠️  DOUBLONS DÉTECTÉS:")
        for (method, path), routes_list in duplicates.items():
            print(f"   {method} {path} ({len(routes_list)} occurrences)")
            for r in routes_list:
                print(f"      - {r['router_file_absolute']}:{r['line']} ({r['function']})")
        print()
    
    # Grouper par router
    print("=" * 80)
    print("📋 ROUTES PAR ROUTER")
    print("=" * 80)
    print()
    
    routes_by_router = defaultdict(list)
    for route in all_routes:
        routes_by_router[route['router_name']].append(route)
    
    for router_name in sorted(routes_by_router.keys()):
        routes = routes_by_router[router_name]
        # Trouver la configuration du router
        router_info = next((r, p, t) for r, p, t in router_configs_list if r == router_name)
        _, prefix, tags = router_info
        
        print(f"🔹 {router_name}")
        print(f"   Fichier (relatif): {routes[0]['router_file']}")
        print(f"   Fichier (absolu): {routes[0]['router_file_absolute']}")
        print(f"   Préfixe: {prefix}")
        print(f"   Tags: {', '.join(tags)}")
        print(f"   Nombre de routes: {len(routes)}")
        print()
        
        # Afficher les routes
        for route in sorted(routes, key=lambda x: (x['method'], x['full_path'])):
            method_color = {
                'GET': '\033[92m',  # Vert
                'POST': '\033[94m',  # Bleu
                'PUT': '\033[93m',   # Jaune
                'DELETE': '\033[91m', # Rouge
                'PATCH': '\033[95m',  # Magenta
            }.get(route['method'], '')
            reset_color = '\033[0m'
            
            print(f"   {method_color}{route['method']:6}{reset_color} {route['full_path']}")
            print(f"          Function: {route['function']}")
            if route['name']:
                print(f"          Name: {route['name']}")
            print(f"          Fichier: {route['file']}")
            print(f"          Ligne: {route['line']}")
            print()
    
    # Afficher toutes les routes par méthode HTTP
    print("=" * 80)
    print("📋 ROUTES PAR MÉTHODE HTTP")
    print("=" * 80)
    print()
    
    routes_by_method = defaultdict(list)
    for route in all_routes:
        routes_by_method[route['method']].append(route)
    
    for method in sorted(routes_by_method.keys()):
        routes = routes_by_method[method]
        print(f"🔹 {method} ({len(routes)} routes)")
        for route in sorted(routes, key=lambda x: x['full_path']):
            print(f"   {route['full_path']}")
            print(f"      Router: {route['router_name']} | Function: {route['function']}")
            print(f"      Fichier: {route['router_file_absolute']}:{route['line']}")
        print()
    
    # Résumé des fichiers
    print("=" * 80)
    print("📁 FICHIERS ANALYSÉS")
    print("=" * 80)
    print()
    
    files_summary = defaultdict(lambda: {'count': 0, 'absolute': None})
    for route in all_routes:
        files_summary[route['router_file']]['count'] += 1
        files_summary[route['router_file']]['absolute'] = route['router_file_absolute']
    
    for file_path in sorted(files_summary.keys()):
        info = files_summary[file_path]
        print(f"   {file_path}: {info['count']} route(s)")
        print(f"      Chemin absolu: {info['absolute']}")
    
    # Afficher les URLs configurées pour les fichiers physiques
    print("=" * 80)
    print("🌐 URLs CONFIGURÉES POUR LES FICHIERS PHYSIQUES")
    print("=" * 80)
    print()
    
    # Lire la configuration depuis path_config
    try:
        path_config_file = BASE_DIR / "core" / "path_config.py"
        if path_config_file.exists():
            content = path_config_file.read_text(encoding='utf-8')
            
            # Extraire les montages - pattern plus flexible
            mount_pattern = r'"([^"]+)":\s*\{\s*"path":\s*"([^"]+)",\s*"directory":\s*str\(([^)]+)\),\s*"name":\s*"([^"]+)"'
            mounts = re.findall(mount_pattern, content, re.MULTILINE | re.DOTALL)
            
            print("📁 Montages de fichiers statiques (path_config.py):")
            for mount_name, mount_path, directory_var, mount_name_fastapi in mounts:
                # Essayer de résoudre le chemin du répertoire
                directory_path = None
                directory_var_clean = directory_var.strip()
                
                if 'self.STATIC_DIR' in directory_var_clean:
                    directory_path = BASE_DIR / "static"
                elif 'self.STATIC_MAPS_DIR' in directory_var_clean:
                    directory_path = BASE_DIR / "static" / "maps"
                elif 'self.STATIC_IMAGES_DIR' in directory_var_clean:
                    directory_path = BASE_DIR / "static" / "images"
                elif 'self.FICHIERS_DIR' in directory_var_clean:
                    directory_path = BASE_DIR / "fichiers"
                elif 'self.UPLOAD_DIR' in directory_var_clean:
                    directory_path = BASE_DIR / "uploads"
                elif 'STATIC_DIR' in directory_var_clean:
                    directory_path = BASE_DIR / "static"
                elif 'FICHIERS_DIR' in directory_var_clean:
                    directory_path = BASE_DIR / "fichiers"
                elif 'UPLOAD_DIR' in directory_var_clean:
                    directory_path = BASE_DIR / "uploads"
                
                if directory_path:
                    directory_path = directory_path.resolve()
                    print(f"   📂 {mount_name}:")
                    print(f"      URL: {mount_path}")
                    print(f"      Chemin physique: {directory_path}")
                    print(f"      Existe: {'✅' if directory_path.exists() else '❌'}")
                else:
                    print(f"   📂 {mount_name}:")
                    print(f"      URL: {mount_path}")
                    print(f"      Variable: {directory_var_clean}")
                print()
        else:
            print("⚠️  Fichier path_config.py non trouvé")
    except Exception as e:
        print(f"⚠️  Erreur lors de la lecture de path_config.py: {e}")
        import traceback
        traceback.print_exc()
    
    # Afficher les fonctions URL dans config.py
    print("🔗 Fonctions de génération d'URLs (config.py):")
    try:
        config_file = BASE_DIR / "core" / "config.py"
        if config_file.exists():
            content = config_file.read_text(encoding='utf-8')
            
            # Chercher les URLs de base
            base_url_pattern = r'base_url\s*=\s*"([^"]+)"'
            base_urls = re.findall(base_url_pattern, content)
            
            if base_urls:
                print("   🌍 URLs de base configurées:")
                for url in set(base_urls):
                    print(f"      {url}")
                print()
            
            # Chercher les fonctions get_*_url avec leurs détails
            func_pattern = r'@staticmethod\s+def\s+(get_\w+_url)\(([^)]+)\)\s*->\s*str:'
            functions = re.finditer(func_pattern, content, re.MULTILINE)
            
            url_functions = []
            for match in functions:
                func_name = match.group(1)
                func_params = match.group(2)
                
                # Extraire la docstring
                start_pos = match.end()
                docstring_match = re.search(r'"""([^"]*)"""', content[start_pos:start_pos+200])
                docstring = docstring_match.group(1).strip() if docstring_match else ""
                
                # Extraire le return
                return_match = re.search(r'return\s+f?["\']([^"\']+)["\']', content[start_pos:start_pos+500])
                return_expr = return_match.group(1) if return_match else ""
                
                url_functions.append({
                    'name': func_name,
                    'params': func_params,
                    'docstring': docstring,
                    'return_expr': return_expr
                })
            
            if url_functions:
                print("   📝 Fonctions de génération d'URLs:")
                for func in url_functions:
                    print(f"   • {func['name']}({func['params']})")
                    if func['docstring']:
                        print(f"      Description: {func['docstring']}")
                    if func['return_expr']:
                        print(f"      Pattern URL: {func['return_expr']}")
                    print()
        else:
            print("⚠️  Fichier config.py non trouvé")
    except Exception as e:
        print(f"⚠️  Erreur lors de la lecture de config.py: {e}")
        import traceback
        traceback.print_exc()
    
    print()
    print("=" * 80)
    print("✅ ANALYSE TERMINÉE")
    print("=" * 80)


if __name__ == "__main__":
    try:
        analyze_all_routes()
    except Exception as e:
        print(f"❌ Erreur lors de l'analyse: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

