#!/usr/bin/env python3
"""
Script pour exécuter les tests unitaires
"""
import subprocess
import sys
import os


def run_tests(test_type="all", verbose=True, coverage=True):
    """
    Exécute les tests unitaires.
    
    Args:
        test_type: Type de tests à exécuter ("unit", "integration", "all")
        verbose: Affichage verbeux
        coverage: Génération du rapport de couverture
    """
    # Commande de base
    cmd = ["python", "-m", "pytest"]
    
    # Options de base
    if verbose:
        cmd.append("-v")
    
    if coverage:
        cmd.extend([
            "--cov=app",
            "--cov-report=html",
            "--cov-report=term-missing",
            "--cov-fail-under=70"
        ])
    
    # Filtrage par type de test
    if test_type == "unit":
        cmd.extend(["-m", "not integration and not database"])
    elif test_type == "integration":
        cmd.extend(["-m", "integration"])
    elif test_type == "fast":
        cmd.extend(["-m", "not slow"])
    
    # Ajouter le répertoire des tests
    cmd.append("tests/")
    
    print(f"🚀 Exécution des tests: {test_type}")
    print(f"📝 Commande: {' '.join(cmd)}")
    print("=" * 60)
    
    try:
        result = subprocess.run(cmd, check=False)
        
        if result.returncode == 0:
            print("\n✅ Tous les tests sont passés avec succès!")
            if coverage:
                print("📊 Rapport de couverture généré dans htmlcov/index.html")
        else:
            print(f"\n❌ {result.returncode} test(s) ont échoué")
            
        return result.returncode
        
    except FileNotFoundError:
        print("❌ pytest n'est pas installé. Installez-le avec: pip install pytest")
        return 1
    except Exception as e:
        print(f"❌ Erreur lors de l'exécution des tests: {e}")
        return 1


def main():
    """Fonction principale."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Exécute les tests unitaires")
    parser.add_argument(
        "--type", 
        choices=["all", "unit", "integration", "fast"],
        default="all",
        help="Type de tests à exécuter"
    )
    parser.add_argument(
        "--no-coverage",
        action="store_true",
        help="Désactive le rapport de couverture"
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Mode silencieux"
    )
    
    args = parser.parse_args()
    
    return run_tests(
        test_type=args.type,
        verbose=not args.quiet,
        coverage=not args.no_coverage
    )


if __name__ == "__main__":
    sys.exit(main())
