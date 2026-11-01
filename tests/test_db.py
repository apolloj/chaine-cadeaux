"""Tests sur une vraie base MySQL de test.

Ignorés par défaut. Pour les lancer, créez une base dont le nom finit par
« _test » (voir README) puis : set CADEAUX_TEST_CONFIG=chemin\\vers\\config_test.ini
"""
import os

import pytest

from cadeaux import config

CHEMIN = os.environ.get("CADEAUX_TEST_CONFIG")
pytestmark = pytest.mark.skipif(not CHEMIN, reason="CADEAUX_TEST_CONFIG non défini")


@pytest.fixture
def base(monkeypatch):
    from cadeaux.db import Base

    monkeypatch.setenv("CADEAUX_CONFIG", CHEMIN)
    cfg = config.charger()
    assert cfg.mysql["database"].endswith("_test"), "refus de vider une base qui n'est pas une base de test"
    with Base(cfg.mysql) as b:
        b._ecrire(*[(f"DELETE FROM {table}", ()) for table in ("attributions", "tirages", "exclusions", "personnes")])
        yield b


def test_tirage_complet(base):
    for nom in ("Alice", "Bruno", "Chloé"):
        base.ajouter_personne(nom)
    base.enregistrer_tirage(2025, {"Alice": "Bruno", "Bruno": "Chloé", "Chloé": "Alice"}, "test")
    assert base.annees() == [2025]
    assert base.attributions(2025) == {"Alice": "Bruno", "Bruno": "Chloé", "Chloé": "Alice"}

    # Remplacement complet de l'année
    base.enregistrer_tirage(2025, {"Alice": "Chloé", "Chloé": "Bruno", "Bruno": "Alice"})
    assert base.attributions(2025)["Alice"] == "Chloé"
    assert len(base.historique()) == 3
    assert base.participations()["Bruno"] == [2025]

    base.supprimer_tirage(2025)
    assert base.annees() == [] and base.historique() == []


def test_unicite_sans_accents_ni_casse(base):
    import mysql.connector

    base.ajouter_personne("Élise")
    with pytest.raises(mysql.connector.IntegrityError):
        base.ajouter_personne("elise")


def test_tirage_invalide_refuse_et_annule(base):
    import mysql.connector

    for nom in ("Alice", "Bruno"):
        base.ajouter_personne(nom)
    with pytest.raises(mysql.connector.Error):
        base.enregistrer_tirage(2025, {"Alice": "Bruno", "Bruno": "Bruno"})  # cadeau à soi-même
    assert base.annees() == []  # transaction annulée


def test_exclusions(base):
    for nom in ("Alice", "Bruno", "Chloé"):
        base.ajouter_personne(nom)
    base.ajouter_exclusions([("Bruno", "Alice"), ("Alice", "Chloé")], "foyer")
    base.ajouter_exclusions([("Alice", "Bruno")])  # doublon : motif conservé
    assert base.exclusions() == [("Alice", "Bruno", "foyer"), ("Alice", "Chloé", "foyer")]
    assert base.supprimer_exclusion("Chloé", "Alice")
    assert not base.supprimer_exclusion("Chloé", "Alice")
    base.supprimer_personne("Bruno")  # supprime aussi ses exclusions
    assert base.exclusions() == []
