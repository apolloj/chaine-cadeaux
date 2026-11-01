"""Menu interactif en ligne de commande."""
from __future__ import annotations

import difflib
import itertools
from datetime import date
from pathlib import Path

import mysql.connector

from . import config, init_db, noms, tirage
from .db import Base

# --- Saisie --------------------------------------------------------------------


def demander(question: str, defaut: object = None) -> str:
    suffixe = f" [{defaut}]" if defaut is not None else ""
    reponse = input(f"{question}{suffixe} : ").strip()
    return reponse or ("" if defaut is None else str(defaut))


def confirmer(question: str, defaut: bool = False) -> bool:
    reponse = input(f"{question} ({'O/n' if defaut else 'o/N'}) : ").strip().lower()
    return defaut if not reponse else reponse in ("o", "oui", "y", "yes")


def demander_annee(defaut: int | None = None, question: str = "Année") -> int | None:
    reponse = demander(question, defaut)
    if reponse.isdigit() and 1900 <= int(reponse) <= 2999:
        return int(reponse)
    print("Année invalide.")
    return None


def choisir_annee_existante(base: Base) -> int | None:
    annees = base.annees()
    if not annees:
        print("Aucun tirage enregistré pour l'instant.")
        return None
    annee = demander_annee(annees[-1])
    if annee is not None and annee not in annees:
        print(f"Aucun tirage enregistré pour {annee}.")
        return None
    return annee


def resoudre_noms(base: Base, saisis: list[str]) -> list[str] | None:
    """Associe chaque nom saisi à une personne de la base, sans tenir compte des
    accents ni des majuscules, et propose d'ajouter les noms inconnus."""
    connus = {noms.cle(nom): nom for nom in base.personnes()}
    resolus = []
    for nom in saisis:
        cle = noms.cle(nom)
        if cle not in connus:
            proches = difflib.get_close_matches(cle, connus, n=1, cutoff=0.8)
            if proches and confirmer(f"« {nom} » est inconnu. Vouliez-vous dire « {connus[proches[0]]} » ?", True):
                cle = proches[0]
            elif confirmer(f"« {nom} » n'est pas encore dans la base. L'ajouter ?", True):
                base.ajouter_personne(nom)
                connus[cle] = nom
            else:
                print("Opération annulée.")
                return None
        resolus.append(connus[cle])
    return resolus


def nom_participant(attributions: dict[str, str], question: str) -> str | None:
    saisie = input(f"{question} : ")
    nom = {noms.cle(n): n for n in attributions}.get(noms.cle(saisie))
    if nom is None:
        print(f"« {saisie.strip()} » ne participe pas à ce tirage.")
    return nom


def lire_participants(base: Base, annee: int) -> list[str] | None:
    annees = base.annees()
    # Pour refaire une année, on reprend ses propres participants, pas ceux d'une année plus ancienne.
    reference = annee if annee in annees else max((a for a in annees if a < annee), default=None)
    print("Participants : noms séparés par des virgules, ou chemin d'un fichier texte (un nom par ligne).")
    if reference is not None:
        print(f"Laissez vide pour reprendre les participants du tirage {reference}.")
    reponse = input("> ").strip()
    fichier = Path(reponse.strip('"'))
    if not reponse and reference is not None:
        saisis = sorted(base.attributions(reference), key=noms.cle)
        print(f"Participants repris de {reference} ({len(saisis)}) : " + ", ".join(saisis))
    elif reponse and fichier.is_file():
        saisis = noms.lire_liste(fichier.read_text(encoding="utf-8-sig"))
    else:
        saisis = noms.lire_liste(reponse)

    participants = resoudre_noms(base, saisis)
    if participants is None:
        return None
    doublons = sorted({p for p in participants if participants.count(p) > 1})
    if doublons:
        print("Noms en double : " + ", ".join(doublons))
        return None
    archives = base.archives()
    participants, retires = tirage.separer_archives(participants, archives, annee)
    for nom in retires:
        print(f"{nom} est archivé(e) depuis {archives[nom]} : retiré(e) du tirage.")
    if len(participants) < 2:
        print("Il faut au moins 2 participants.")
        return None
    return participants


# --- Affichage -----------------------------------------------------------------


def pluriel(n: int, mot: str) -> str:
    return f"{n} {mot}{'s' if n > 1 else ''}"


def afficher(attributions: dict[str, str], detail: bool = True) -> None:
    ordonne = dict(sorted(attributions.items(), key=lambda paire: noms.cle(paire[0])))
    for boucle in tirage.cycles(ordonne):
        print("  " + " → ".join(boucle + boucle[:1]))
    if detail:
        largeur = max(map(len, ordonne))
        for donneur, receveur in ordonne.items():
            print(f"    {donneur:<{largeur}}  offre à  {receveur}")


def exclusions_de(base: Base) -> list[tuple[str, str]]:
    return [(a, b) for a, b, _ in base.exclusions()]


def signaler_problemes(base: Base, cfg: config.Config, annee: int, attributions: dict[str, str]) -> None:
    boucles = tirage.cycles(attributions)
    if len(boucles) > 1:
        print(f"Attention : ce tirage forme {len(boucles)} boucles au lieu d'une seule chaîne.")
    interdits = tirage.paires_interdites(base.historique(), annee, cfg.fenetre, exclusions_de(base))
    for donneur, receveur, raison in tirage.violations(attributions, interdits):
        print(f"Attention : {donneur} → {receveur} ({raison})")
    archives = base.archives()
    for nom in tirage.separer_archives(sorted(attributions, key=noms.cle), archives, annee)[1]:
        print(f"Attention : {nom} est archivé(e) depuis {archives[nom]}")


# --- Actions du menu -----------------------------------------------------------


def faire_tirage(base: Base, cfg: config.Config) -> None:
    annee = demander_annee(date.today().year)
    if annee is None:
        return
    if annee in base.annees():
        print(f"Un tirage existe déjà pour {annee} :")
        afficher(base.attributions(annee), detail=False)
        if not confirmer("Le remplacer par un nouveau tirage ?"):
            return
    participants = lire_participants(base, annee)
    if participants is None:
        return

    historique = base.historique()
    exclusions = exclusions_de(base)
    while True:
        resultat = tirage.tirer(participants, historique, annee, cfg.fenetre, exclusions)
        if resultat is None:
            print("Aucune chaîne n'est possible, même en ignorant l'historique : "
                  "vérifiez les couples et foyers (exclusions permanentes).")
            return
        if resultat.fenetre < cfg.fenetre:
            print(f"Attention : impossible de respecter la règle des {cfg.fenetre} ans avec ces participants.")
            if resultat.fenetre:
                print(f"Meilleur tirage trouvé : la règle est respectée sur {pluriel(resultat.fenetre, 'an')}.")
            else:
                print("Meilleur tirage trouvé : l'historique a dû être ignoré.")
        attributions = tirage.chaine_vers_attributions(resultat.chaine)
        print(f"\nTirage {annee} :")
        afficher(attributions)

        choix = ""
        while choix not in ("e", "n", "a"):
            choix = demander("[E]nregistrer, [N]ouveau tirage ou [A]nnuler", "E").lower()[:1]
        if choix == "a":
            return
        if choix == "e":
            note = ("tirage automatique, historique ignoré" if resultat.fenetre == 0
                    else f"tirage automatique, règle des {pluriel(resultat.fenetre, 'an')}")
            base.enregistrer_tirage(annee, attributions, note)
            print(f"Tirage {annee} enregistré.")
            return


def voir_tirage(base: Base, cfg: config.Config) -> None:
    annee = choisir_annee_existante(base)
    if annee is None:
        return
    attributions = base.attributions(annee)
    print(f"\nTirage {annee} :")
    afficher(attributions)
    signaler_problemes(base, cfg, annee, attributions)


def voir_historique(base: Base, cfg: config.Config) -> None:
    infos = base.infos_tirages()
    if not infos:
        print("Aucun tirage enregistré pour l'instant.")
        return
    historique = base.historique()
    for annee, note in reversed(infos):
        print(f"\n{annee}" + (f"  ({note})" if note else ""))
        afficher({d: r for an, d, r in historique if an == annee}, detail=False)

    print("\nPar personne (à qui chacun a offert) :")
    par_personne: dict[str, list[str]] = {}
    for annee, donneur, receveur in historique:
        par_personne.setdefault(donneur, []).append(f"{annee} → {receveur}")
    largeur = max(map(len, par_personne))
    for nom in sorted(par_personne, key=noms.cle):
        print(f"  {nom:<{largeur}}  " + ", ".join(par_personne[nom]))


def saisir_tirage(base: Base, cfg: config.Config, annee: int | None = None) -> None:
    if annee is None:
        annee = demander_annee()
        if annee is None:
            return
        if annee in base.annees():
            print(f"Un tirage existe déjà pour {annee} :")
            afficher(base.attributions(annee), detail=False)
            if not confirmer("Le remplacer ?"):
                return
    print("Saisissez les attributions, une par ligne : « Donneur > Receveur »,")
    print("ou une chaîne complète « A > B > C > A ». Ligne vide pour terminer.")
    lignes = []
    while ligne := input("> ").strip():
        lignes.append(ligne)
    try:
        paires = noms.lire_attributions(lignes)
    except ValueError as erreur:
        print(erreur)
        return
    if not paires:
        print("Aucune attribution saisie.")
        return

    saisis = list(dict.fromkeys(nom for paire in paires for nom in paire))
    resolus = resoudre_noms(base, saisis)
    if resolus is None:
        return
    correspondance = dict(zip(saisis, resolus))
    paires = [(correspondance[d], correspondance[r]) for d, r in paires]
    erreurs = tirage.erreurs_structure(paires)
    if erreurs:
        print("Tirage invalide :")
        for erreur in erreurs:
            print(f"  - {erreur}")
        return

    attributions = dict(paires)
    print(f"\nTirage {annee} :")
    afficher(attributions)
    signaler_problemes(base, cfg, annee, attributions)
    if confirmer("Enregistrer ce tirage ?", True):
        base.enregistrer_tirage(annee, attributions, "saisie manuelle")
        print(f"Tirage {annee} enregistré.")


def proposer_modification(base: Base, cfg: config.Config, annee: int, nouveau: dict[str, str], note: str) -> None:
    print(f"\nNouveau tirage {annee} :")
    afficher(nouveau)
    signaler_problemes(base, cfg, annee, nouveau)
    if confirmer("Enregistrer la modification ?", True):
        base.enregistrer_tirage(annee, nouveau, note)
        print("Modification enregistrée.")


def retirer_du_tirage(base: Base, cfg: config.Config, annee: int, nom: str) -> None:
    try:
        nouveau = tirage.retirer(base.attributions(annee), nom)
    except ValueError as erreur:
        print(erreur)
        return
    proposer_modification(base, cfg, annee, nouveau, f"modifié manuellement ({nom} retiré(e))")


def modifier_tirage(base: Base, cfg: config.Config) -> None:
    annee = choisir_annee_existante(base)
    if annee is None:
        return
    attributions = base.attributions(annee)
    print(f"\nTirage {annee} :")
    afficher(attributions)
    print("\n1. Échanger la place de deux personnes dans la chaîne")
    print("2. Remplacer une personne par une autre")
    print("3. Retirer une personne (celui qui lui offrait offre alors à celle qu'elle gâtait)")
    print("4. Tout ressaisir")
    print("0. Retour")
    choix = input("Votre choix : ").strip()

    if choix == "1":
        a = nom_participant(attributions, "Première personne")
        b = a and nom_participant(attributions, "Deuxième personne")
        if not a or not b or a == b:
            return
        nouveau = tirage.renommer(attributions, {a: b, b: a})
    elif choix == "2":
        ancien = nom_participant(attributions, "Personne à remplacer")
        saisie = ancien and noms.nettoyer(input("Remplacer par : "))
        if not saisie:
            return
        resolus = resoudre_noms(base, [saisie])
        if resolus is None:
            return
        if resolus[0] in attributions:
            print(f"{resolus[0]} participe déjà au tirage {annee}.")
            return
        nouveau = tirage.renommer(attributions, {ancien: resolus[0]})
    elif choix == "3":
        nom = nom_participant(attributions, "Personne à retirer")
        if nom is not None:
            retirer_du_tirage(base, cfg, annee, nom)
        return
    elif choix == "4":
        saisir_tirage(base, cfg, annee)
        return
    else:
        return
    proposer_modification(base, cfg, annee, nouveau, "modifié manuellement")


def supprimer_tirage(base: Base, cfg: config.Config) -> None:
    annee = choisir_annee_existante(base)
    if annee is None:
        return
    afficher(base.attributions(annee), detail=False)
    if confirmer(f"Supprimer définitivement le tirage {annee} ?"):
        base.supprimer_tirage(annee)
        print(f"Tirage {annee} supprimé.")


def gerer_exclusions(base: Base, cfg: config.Config) -> None:
    while True:
        exclusions = base.exclusions()
        print("\nCouples et foyers (ces personnes ne se tirent jamais l'une l'autre) :")
        if not exclusions:
            print("  (aucune exclusion)")
        for a, b, motif in exclusions:
            print(f"  {a} ↔ {b}" + (f"  ({motif})" if motif else ""))
        print("\n1. Ajouter un couple ou un foyer")
        print("2. Supprimer une exclusion")
        print("0. Retour")
        choix = input("Votre choix : ").strip()

        if choix == "1":
            saisis = noms.lire_liste(input("Noms du couple ou du foyer, séparés par des virgules : "))
            if len({noms.cle(n) for n in saisis}) < 2:
                print("Il faut au moins 2 personnes différentes.")
                continue
            membres = resoudre_noms(base, saisis)
            if membres is None:
                continue
            motif = input("Motif (facultatif, ex. « couple ») : ").strip() or None
            paires = list(itertools.combinations(dict.fromkeys(membres), 2))
            base.ajouter_exclusions(paires, motif)
            print(f"{pluriel(len(paires), 'exclusion')} enregistrée(s).")
        elif choix == "2":
            saisis = noms.lire_liste(input("Les deux noms, séparés par une virgule : "))
            if len(saisis) != 2:
                print("Il faut exactement 2 noms.")
                continue
            connus = {noms.cle(n): n for n in base.personnes()}
            a, b = (connus.get(noms.cle(n)) for n in saisis)
            if a and b and base.supprimer_exclusion(a, b):
                print("Exclusion supprimée.")
            else:
                print("Exclusion introuvable.")
        else:
            return


def gerer_personnes(base: Base, cfg: config.Config) -> None:
    while True:
        participations = base.participations()
        archives = base.archives()
        print("\nPersonnes enregistrées :")
        if not participations:
            print("  (aucune)")
        largeur = max(map(len, participations), default=0)
        for nom, annees in participations.items():
            statut = f"  [archivé(e) depuis {archives[nom]}]" if nom in archives else ""
            print(f"  {nom:<{largeur}}  " + (", ".join(map(str, annees)) or "aucun tirage") + statut)
        print("\n1. Renommer une personne")
        print("2. Archiver une personne (elle ne participe plus aux tirages)")
        print("3. Réactiver une personne archivée")
        print("4. Supprimer une personne")
        print("0. Retour")
        choix = input("Votre choix : ").strip()
        if choix not in ("1", "2", "3", "4"):
            return

        connus = {noms.cle(n): n for n in participations}
        nom = connus.get(noms.cle(input("Nom : ")))
        if nom is None:
            print("Personne introuvable.")
        elif choix == "1":
            nouveau = noms.nettoyer(input("Nouveau nom : "))
            autre = connus.get(noms.cle(nouveau))
            if not nouveau:
                continue
            if autre and autre != nom:
                print(f"« {autre} » existe déjà.")
                continue
            base.renommer_personne(nom, nouveau)
            print(f"{nom} s'appelle désormais {nouveau}.")
        elif choix == "2":
            depuis = demander_annee(date.today().year, "Ne participe plus à partir de l'année")
            if depuis is None:
                continue
            base.archiver_personne(nom, depuis)
            print(f"{nom} est archivé(e) : plus de tirage pour {nom} à partir de {depuis}.")
            deja_tire = [a for a in participations[nom] if a >= depuis]
            if deja_tire and confirmer(
                f"{nom} figure déjà dans le tirage {', '.join(map(str, deja_tire))}. L'en retirer ?", True
            ):
                for annee in deja_tire:
                    retirer_du_tirage(base, cfg, annee, nom)
        elif choix == "3":
            if nom not in archives:
                print(f"{nom} n'est pas archivé(e).")
                continue
            base.archiver_personne(nom, None)
            print(f"{nom} participe de nouveau aux tirages.")
        elif participations[nom]:
            print(f"{nom} figure dans les tirages {', '.join(map(str, participations[nom]))} : "
                  "modifiez ou supprimez d'abord ces tirages.")
        elif confirmer(f"Supprimer {nom} ?"):
            base.supprimer_personne(nom)
            print(f"{nom} supprimé(e).")


# --- Boucle principale ---------------------------------------------------------

MENU = """
=== Chaîne de cadeaux ===
1. Faire le tirage d'une année
2. Voir le tirage d'une année
3. Voir l'historique
4. Saisir un tirage passé
5. Modifier un tirage
6. Supprimer un tirage
7. Couples et foyers (exclusions permanentes)
8. Personnes
0. Quitter"""

ACTIONS = {
    "1": faire_tirage,
    "2": voir_tirage,
    "3": voir_historique,
    "4": saisir_tirage,
    "5": modifier_tirage,
    "6": supprimer_tirage,
    "7": gerer_exclusions,
    "8": gerer_personnes,
}


def main() -> int:
    try:
        cfg = config.charger()
    except config.ConfigManquante as erreur:
        print(erreur)
        return 1
    try:
        base = Base(cfg.mysql)
        init_db.mettre_a_jour_schema(base.cnx)
    except mysql.connector.Error as erreur:
        print(f"Base MySQL inaccessible : {erreur}")
        return 1

    with base:
        while True:
            print(MENU)
            try:
                choix = input("Votre choix : ").strip()
            except (EOFError, KeyboardInterrupt):
                print()
                return 0
            if choix == "0":
                return 0
            action = ACTIONS.get(choix)
            if action is None:
                print("Choix invalide.")
                continue
            try:
                action(base, cfg)
            except EOFError:
                return 0
            except KeyboardInterrupt:
                print("\nOpération annulée.")
            except mysql.connector.Error as erreur:
                print(f"Erreur MySQL : {erreur}")
