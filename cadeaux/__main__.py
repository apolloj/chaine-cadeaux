"""Point d'entrée : `python -m cadeaux` (menu) ou `python -m cadeaux init`."""
import argparse
import sys

from .cli import main
from .init_db import initialiser


def lancer() -> int:
    # Accents et flèches lisibles même quand l'entrée ou la sortie est redirigée.
    for flux in (sys.stdin, sys.stdout, sys.stderr):
        flux.reconfigure(encoding="utf-8")

    parser = argparse.ArgumentParser(prog="python -m cadeaux", description="Chaîne de cadeaux annuelle")
    parser.add_argument(
        "commande", nargs="?", choices=["menu", "init"], default="menu",
        help="menu : menu interactif (par défaut) ; init : crée la base MySQL et config.ini",
    )
    args = parser.parse_args()
    return initialiser() if args.commande == "init" else main()


sys.exit(lancer())
