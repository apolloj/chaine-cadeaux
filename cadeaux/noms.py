"""Lecture et comparaison des noms saisis."""
from __future__ import annotations

import re
import unicodedata
from collections.abc import Iterable

_SEPARATEURS = re.compile(r"[,;\n]")
_FLECHE = re.compile(r"\s*(?:->|→|>)\s*")


def nettoyer(nom: str) -> str:
    return " ".join(nom.split())


def cle(nom: str) -> str:
    """Clé de comparaison : sans accents, sans majuscules, espaces normalisés."""
    decompose = unicodedata.normalize("NFKD", nom)
    sans_accents = "".join(c for c in decompose if not unicodedata.combining(c))
    return " ".join(sans_accents.casefold().split())


def lire_liste(texte: str) -> list[str]:
    """Noms séparés par des virgules, des points-virgules ou des retours à la ligne."""
    return [nettoyer(n) for n in _SEPARATEURS.split(texte) if n.strip()]


def lire_attributions(lignes: Iterable[str]) -> list[tuple[str, str]]:
    """Lit des lignes « A > B » ou des chaînes « A > B > C > A »
    (« -> » et « → » sont aussi acceptés) et renvoie les paires (donneur, receveur)."""
    paires = []
    for ligne in lignes:
        ligne = ligne.strip()
        if not ligne:
            continue
        morceaux = [nettoyer(n) for n in _FLECHE.split(ligne)]
        if len(morceaux) < 2 or not all(morceaux):
            raise ValueError(f"Ligne illisible : « {ligne} » (format attendu : Donneur > Receveur)")
        paires.extend(zip(morceaux, morceaux[1:]))
    return paires
