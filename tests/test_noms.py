import pytest

from cadeaux import noms


def test_cle_ignore_accents_casse_et_espaces():
    assert noms.cle("  Élise   Dupont ") == noms.cle("elise dupont")
    assert noms.cle("Gaëlle") == "gaelle"


def test_lire_liste():
    assert noms.lire_liste("Alice, Bruno ;Chloé\nDavid,, ") == ["Alice", "Bruno", "Chloé", "David"]


def test_lire_attributions_lignes_et_chaines():
    lignes = ["Alice > Bruno", "Bruno -> Chloé", "", "Chloé → Alice"]
    assert noms.lire_attributions(lignes) == [("Alice", "Bruno"), ("Bruno", "Chloé"), ("Chloé", "Alice")]
    assert noms.lire_attributions(["Jean-Pierre > Marie > Jean-Pierre"]) == [
        ("Jean-Pierre", "Marie"),
        ("Marie", "Jean-Pierre"),
    ]


@pytest.mark.parametrize("ligne", ["Alice", "Alice > ", "> Bruno"])
def test_lire_attributions_illisible(ligne):
    with pytest.raises(ValueError):
        noms.lire_attributions([ligne])
