"""Logique du tirage : règles d'interdiction et recherche d'une chaîne unique.

Ce module ne dépend pas de la base de données : les personnes peuvent être
représentées par n'importe quelle valeur hachable (ici, leur nom).
"""
from __future__ import annotations

import random
from collections import Counter
from collections.abc import Hashable, Iterable, Mapping, Sequence
from dataclasses import dataclass

Paire = tuple[Hashable, Hashable]

# Nombre maximal d'étapes explorées avant d'abandonner une recherche.
BUDGET_RECHERCHE = 2_000_000


@dataclass
class Resultat:
    chaine: list  # p0 → p1 → … → pn-1 → p0
    fenetre: int  # nombre d'années d'historique effectivement respectées


class _BudgetEpuise(Exception):
    pass


def paires_interdites(
    historique: Iterable[tuple[int, Hashable, Hashable]],
    annee: int,
    fenetre: int,
    exclusions: Iterable[Paire] = (),
) -> dict[Paire, str]:
    """Paires (donneur, receveur) interdites pour `annee`, avec leur raison.

    - Si A a offert à B à `fenetre` ans ou moins de `annee` (avant ou après),
      A ne peut plus offrir à B, ni B à A.
    - Les exclusions permanentes (couples, foyers) valent dans les deux sens.
    """
    raisons: dict[Paire, str] = {}
    for an, donneur, receveur in sorted(historique, key=lambda ligne: ligne[0]):
        if an != annee and abs(an - annee) <= fenetre:
            raison = f"{donneur} a offert à {receveur} en {an}"
            raisons[(donneur, receveur)] = raison
            raisons[(receveur, donneur)] = raison
    for a, b in exclusions:
        raisons[(a, b)] = raisons[(b, a)] = "exclusion permanente"
    return raisons


def chercher_chaine(
    participants: Sequence[Hashable],
    interdits: Mapping[Paire, str] | set[Paire],
    rng: random.Random | None = None,
    budget: int = BUDGET_RECHERCHE,
) -> list | None:
    """Cherche au hasard une boucle unique passant par tous les participants
    sans utiliser de paire interdite. Renvoie None s'il n'en existe pas."""
    rng = rng or random.Random()
    gens = list(participants)
    if len(gens) < 2:
        return None

    succ = {p: {q for q in gens if q != p and (p, q) not in interdits} for p in gens}
    pred = {q: {p for p in gens if q in succ[p]} for q in gens}
    depart = rng.choice(gens)
    chemin = [depart]
    restants = set(gens) - {depart}
    etapes = 0

    def viable() -> bool:
        # Chaque personne restante doit encore pouvoir donner et recevoir.
        queue = chemin[-1]
        for u in restants:
            if succ[u].isdisjoint(restants) and depart not in succ[u]:
                return False
            if pred[u].isdisjoint(restants) and queue not in pred[u]:
                return False
        return True

    def explorer() -> bool:
        nonlocal etapes
        if not restants:
            return depart in succ[chemin[-1]]
        etapes += 1
        if etapes > budget:
            raise _BudgetEpuise
        candidats = [q for q in gens if q in restants and q in succ[chemin[-1]]]
        rng.shuffle(candidats)
        for q in candidats:
            chemin.append(q)
            restants.remove(q)
            if viable() and explorer():
                return True
            chemin.pop()
            restants.add(q)
        return False

    try:
        return chemin if explorer() else None
    except _BudgetEpuise:
        return None


def tirer(
    participants: Sequence[Hashable],
    historique: Iterable[tuple[int, Hashable, Hashable]],
    annee: int,
    fenetre: int,
    exclusions: Iterable[Paire] = (),
    rng: random.Random | None = None,
) -> Resultat | None:
    """Tire une chaîne en respectant la règle de fenêtre : deux personnes
    ne se retirent pas pendant `fenetre` ans (fenetre_annees dans config.ini).

    Si c'est impossible, la fenêtre est réduite d'un an à la fois ; les
    exclusions permanentes, elles, ne sont jamais assouplies.
    """
    historique = list(historique)
    exclusions = list(exclusions)
    for f in range(fenetre, -1, -1):
        interdits = paires_interdites(historique, annee, f, exclusions)
        chaine = chercher_chaine(participants, interdits, rng)
        if chaine:
            return Resultat(chaine, f)
    return None


def separer_archives(
    participants: Sequence[Hashable], archives: Mapping[Hashable, int], annee: int
) -> tuple[list, list]:
    """Sépare les participants actifs en `annee` de ceux archivés depuis cette année ou avant."""
    retires = [p for p in participants if p in archives and archives[p] <= annee]
    return [p for p in participants if p not in retires], retires


def chaine_vers_attributions(chaine: Sequence[Hashable]) -> dict:
    """[A, B, C] → {A: B, B: C, C: A}"""
    return {p: chaine[(i + 1) % len(chaine)] for i, p in enumerate(chaine)}


def cycles(attributions: Mapping) -> list[list]:
    """Découpe des attributions en boucles (une seule pour une vraie chaîne)."""
    restants = dict(attributions)
    boucles = []
    while restants:
        depart = next(iter(restants))
        boucle = [depart]
        suivant = restants.pop(depart)
        while suivant != depart and suivant in restants:
            boucle.append(suivant)
            suivant = restants.pop(suivant)
        boucles.append(boucle)
    return boucles


def renommer(attributions: Mapping, correspondance: Mapping) -> dict:
    """Remplace des personnes dans un tirage : {A: B, B: A} échange leurs
    places dans la chaîne, {A: X} met X à la place de A."""
    def f(p):
        return correspondance.get(p, p)

    return {f(d): f(r) for d, r in attributions.items()}


def retirer(attributions: Mapping, personne: Hashable) -> dict:
    """Retire une personne d'un tirage : celui qui lui offrait offre désormais
    à celle qu'elle gâtait, et la boucle reste unique."""
    receveur = attributions[personne]
    donneur = next(d for d, r in attributions.items() if r == personne)
    if donneur == receveur:
        raise ValueError(f"Impossible de retirer {personne} : {donneur} devrait s'offrir un cadeau.")
    nouveau = {d: r for d, r in attributions.items() if d != personne}
    nouveau[donneur] = receveur
    return nouveau


def erreurs_structure(paires: Sequence[Paire]) -> list[str]:
    """Vérifie que chacun donne exactement un cadeau et en reçoit exactement un."""
    erreurs = [f"{d} ne peut pas s'offrir un cadeau" for d, r in paires if d == r]
    donneurs = Counter(d for d, _ in paires)
    receveurs = Counter(r for _, r in paires)
    erreurs += [f"{p} donne {n} cadeaux" for p, n in donneurs.items() if n > 1]
    erreurs += [f"{p} reçoit {n} cadeaux" for p, n in receveurs.items() if n > 1]
    erreurs += [f"{p} donne un cadeau mais n'en reçoit aucun" for p in donneurs if p not in receveurs]
    erreurs += [f"{p} reçoit un cadeau mais n'en donne aucun" for p in receveurs if p not in donneurs]
    return erreurs


def violations(attributions: Mapping, interdits: Mapping[Paire, str]) -> list[tuple]:
    """Attributions qui enfreignent une règle : (donneur, receveur, raison)."""
    return [(d, r, interdits[(d, r)]) for d, r in attributions.items() if (d, r) in interdits]
