import random

import pytest

from cadeaux import tirage

FAMILLE = ["Alice", "Bruno", "Chloé", "David", "Emma", "Farid", "Gaëlle", "Hugo", "Inès", "Jules"]


def est_chaine_unique(attributions, participants):
    return (
        sorted(attributions) == sorted(participants)
        and sorted(attributions.values()) == sorted(participants)
        and len(tirage.cycles(attributions)) == 1
    )


@pytest.mark.parametrize("graine", range(50))
def test_tirage_forme_une_seule_boucle(graine):
    resultat = tirage.tirer(FAMILLE, [], 2026, 3, rng=random.Random(graine))
    attributions = tirage.chaine_vers_attributions(resultat.chaine)
    assert est_chaine_unique(attributions, FAMILLE)
    assert all(d != r for d, r in attributions.items())
    assert resultat.fenetre == 3


def test_regle_des_trois_ans_dans_les_deux_sens():
    historique = []
    for annee in (2023, 2024, 2025):
        res = tirage.tirer(FAMILLE, historique, annee, 3, rng=random.Random(annee))
        assert res.fenetre == 3
        historique += [(annee, d, r) for d, r in tirage.chaine_vers_attributions(res.chaine).items()]

    deja_lies = {frozenset((d, r)) for _, d, r in historique}
    for graine in range(30):
        res = tirage.tirer(FAMILLE, historique, 2026, 3, rng=random.Random(graine))
        assert res.fenetre == 3
        for d, r in tirage.chaine_vers_attributions(res.chaine).items():
            assert frozenset((d, r)) not in deja_lies


def test_paires_interdites_fenetre():
    historique = [(2022, "A", "B"), (2023, "C", "D"), (2026, "E", "F"), (2027, "G", "H")]
    interdits = tirage.paires_interdites(historique, 2026, 3)
    assert ("A", "B") not in interdits  # 4 ans avant : de nouveau permis
    assert ("C", "D") in interdits and ("D", "C") in interdits
    assert ("E", "F") not in interdits  # l'année tirée elle-même est ignorée
    assert ("G", "H") in interdits  # une année suivante compte aussi (re-tirage d'une année passée)
    assert interdits[("D", "C")] == "C a offert à D en 2023"


def test_exclusions_permanentes_respectees():
    exclusions = [("Alice", "Bruno"), ("Chloé", "David")]
    for graine in range(30):
        res = tirage.tirer(FAMILLE, [], 2026, 3, exclusions, rng=random.Random(graine))
        attributions = tirage.chaine_vers_attributions(res.chaine)
        for a, b in exclusions:
            assert attributions[a] != b and attributions[b] != a


def test_cinq_personnes_apres_un_an():
    # Chacun ne peut plus offrir qu'aux deux personnes non voisines : seule
    # l'étoile A → C → E → B → D → A reste possible.
    historique = [(2025, d, r) for d, r in tirage.chaine_vers_attributions(list("ABCDE")).items()]
    res = tirage.tirer(list("ABCDE"), historique, 2026, 3, rng=random.Random(1))
    assert res.fenetre == 3
    assert not tirage.violations(tirage.chaine_vers_attributions(res.chaine),
                                 tirage.paires_interdites(historique, 2026, 3))


def test_assouplissement_quand_impossible():
    # Avec 4 personnes, après A → B → C → D → A, aucune boucle unique ne respecte la règle.
    historique = [(2025, d, r) for d, r in tirage.chaine_vers_attributions(list("ABCD")).items()]
    res = tirage.tirer(list("ABCD"), historique, 2026, 3, rng=random.Random(0))
    assert res.fenetre == 0
    assert est_chaine_unique(tirage.chaine_vers_attributions(res.chaine), list("ABCD"))


def test_impossible_meme_sans_historique():
    exclusions = [("A", "B"), ("A", "C")]  # A ne peut donner ni recevoir de personne
    assert tirage.tirer(list("ABC"), [], 2026, 3, exclusions) is None
    assert tirage.tirer(["Seul"], [], 2026, 3) is None


def test_deux_personnes():
    res = tirage.tirer(["A", "B"], [], 2026, 3)
    assert tirage.chaine_vers_attributions(res.chaine) == {"A": "B", "B": "A"}


def test_separer_archives():
    archives = {"B": 2026, "C": 2028}
    assert tirage.separer_archives(["A", "B", "C"], archives, 2026) == (["A", "C"], ["B"])
    assert tirage.separer_archives(["A", "B", "C"], archives, 2030) == (["A"], ["B", "C"])
    assert tirage.separer_archives(["A", "B"], archives, 2025) == (["A", "B"], [])  # années passées


def test_retirer_referme_la_boucle():
    attributions = {"A": "B", "B": "C", "C": "D", "D": "A"}
    assert tirage.retirer(attributions, "C") == {"A": "B", "B": "D", "D": "A"}
    assert len(tirage.cycles(tirage.retirer(attributions, "A"))) == 1
    with pytest.raises(ValueError):
        tirage.retirer({"A": "B", "B": "A"}, "A")


def test_cycles_et_renommer():
    attributions = {"A": "B", "B": "C", "C": "A"}
    assert tirage.cycles(attributions) == [["A", "B", "C"]]
    assert len(tirage.cycles({"A": "B", "B": "A", "C": "D", "D": "C"})) == 2
    echange = tirage.renommer(attributions, {"A": "B", "B": "A"})
    assert echange == {"B": "A", "A": "C", "C": "B"}
    assert len(tirage.cycles(echange)) == 1
    assert tirage.renommer(attributions, {"C": "Z"}) == {"A": "B", "B": "Z", "Z": "A"}


def test_erreurs_structure():
    assert tirage.erreurs_structure([("A", "B"), ("B", "A")]) == []
    erreurs = tirage.erreurs_structure([("A", "A"), ("B", "C"), ("B", "D")])
    assert "A ne peut pas s'offrir un cadeau" in erreurs
    assert "B donne 2 cadeaux" in erreurs
    assert "C reçoit un cadeau mais n'en donne aucun" in erreurs
    assert "B donne un cadeau mais n'en reçoit aucun" in erreurs
