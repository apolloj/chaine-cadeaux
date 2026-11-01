"""Lecture et écriture du fichier config.ini."""
from __future__ import annotations

import configparser
import os
from dataclasses import dataclass
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
FENETRE_DEFAUT = 3


class ConfigManquante(Exception):
    pass


@dataclass
class Config:
    mysql: dict
    fenetre: int  # nombre d'années pendant lesquelles deux personnes ne se retirent pas


def chemin_config() -> Path:
    """config.ini à la racine du projet, sauf si CADEAUX_CONFIG indique un autre fichier."""
    return Path(os.environ.get("CADEAUX_CONFIG", RACINE / "config.ini"))


def charger() -> Config:
    chemin = chemin_config()
    if not chemin.exists():
        raise ConfigManquante(
            f"Fichier de configuration introuvable : {chemin}\n"
            "Lancez d'abord : python -m cadeaux init"
        )
    cp = configparser.ConfigParser(interpolation=None)
    cp.read(chemin, encoding="utf-8")
    m = cp["mysql"]
    return Config(
        mysql={
            "host": m.get("host", "localhost"),
            "port": m.getint("port", 3306),
            "user": m["user"],
            "password": m["password"],
            "database": m["database"],
        },
        fenetre=cp.getint("regles", "fenetre_annees", fallback=FENETRE_DEFAUT),
    )


def ecrire(chemin: Path, mysql: dict, fenetre: int = FENETRE_DEFAUT) -> None:
    cp = configparser.ConfigParser(interpolation=None)
    cp["mysql"] = {cle: str(valeur) for cle, valeur in mysql.items()}
    cp["regles"] = {"fenetre_annees": str(fenetre)}
    with open(chemin, "w", encoding="utf-8") as fichier:
        fichier.write("# Généré par « python -m cadeaux init ». Ne pas publier : contient un mot de passe.\n")
        cp.write(fichier)
