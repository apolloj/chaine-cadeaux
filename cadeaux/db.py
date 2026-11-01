"""Accès à la base MySQL. Les personnes y sont désignées par leur nom."""
from __future__ import annotations

from collections.abc import Iterable

import mysql.connector


class Base:
    def __init__(self, parametres: dict):
        self.cnx = mysql.connector.connect(**parametres, autocommit=True)

    def __enter__(self) -> Base:
        return self

    def __exit__(self, *exc) -> None:
        self.cnx.close()

    def _lire(self, sql: str, args: tuple = ()) -> list[tuple]:
        cur = self.cnx.cursor()
        try:
            cur.execute(sql, args)
            return cur.fetchall()
        finally:
            cur.close()

    def _ecrire(self, *requetes: tuple[str, tuple | list]) -> int:
        """Exécute des (sql, paramètres) dans une seule transaction ; une liste
        de paramètres exécute la requête pour chacun. Renvoie le nombre de lignes touchées."""
        cur = self.cnx.cursor()
        lignes = 0
        try:
            self.cnx.start_transaction()
            for sql, args in requetes:
                if isinstance(args, list):
                    if args:
                        cur.executemany(sql, args)
                else:
                    cur.execute(sql, args)
                lignes += max(cur.rowcount, 0)
            self.cnx.commit()
            return lignes
        except Exception:
            self.cnx.rollback()
            raise
        finally:
            cur.close()

    def _ids(self, noms: Iterable[str]) -> dict[str, int]:
        ids = {nom: id_ for id_, nom in self._lire("SELECT id, nom FROM personnes")}
        inconnus = [nom for nom in noms if nom not in ids]
        if inconnus:
            raise ValueError("Personne(s) inconnue(s) : " + ", ".join(inconnus))
        return ids

    # --- Personnes -----------------------------------------------------------

    def personnes(self) -> list[str]:
        return [nom for (nom,) in self._lire("SELECT nom FROM personnes ORDER BY nom")]

    def participations(self) -> dict[str, list[int]]:
        """Années de participation de chaque personne."""
        resultat: dict[str, list[int]] = {}
        for nom, annee in self._lire(
            "SELECT p.nom, a.annee FROM personnes p "
            "LEFT JOIN attributions a ON a.donneur_id = p.id ORDER BY p.nom, a.annee"
        ):
            resultat.setdefault(nom, [])
            if annee is not None:
                resultat[nom].append(annee)
        return resultat

    def ajouter_personne(self, nom: str) -> None:
        self._ecrire(("INSERT INTO personnes (nom) VALUES (%s)", (nom,)))

    def renommer_personne(self, ancien: str, nouveau: str) -> None:
        self._ecrire(("UPDATE personnes SET nom = %s WHERE nom = %s", (nouveau, ancien)))

    def supprimer_personne(self, nom: str) -> None:
        self._ecrire(("DELETE FROM personnes WHERE nom = %s", (nom,)))

    def archives(self) -> dict[str, int]:
        """Personnes archivées, avec l'année à partir de laquelle elles ne participent plus."""
        return dict(self._lire(
            "SELECT nom, archive_depuis FROM personnes WHERE archive_depuis IS NOT NULL ORDER BY nom"
        ))

    def archiver_personne(self, nom: str, depuis: int | None) -> None:
        """Archive une personne à partir de l'année `depuis` ; None la réactive."""
        self._ecrire(("UPDATE personnes SET archive_depuis = %s WHERE nom = %s", (depuis, nom)))

    # --- Exclusions permanentes ---------------------------------------------

    def exclusions(self) -> list[tuple[str, str, str | None]]:
        return self._lire(
            "SELECT a.nom, b.nom, e.motif FROM exclusions e "
            "JOIN personnes a ON a.id = e.personne_a "
            "JOIN personnes b ON b.id = e.personne_b ORDER BY a.nom, b.nom"
        )

    def ajouter_exclusions(self, paires: list[tuple[str, str]], motif: str | None = None) -> None:
        ids = self._ids(nom for paire in paires for nom in paire)
        lignes = [(*sorted((ids[a], ids[b])), motif) for a, b in paires]
        self._ecrire((
            "INSERT INTO exclusions (personne_a, personne_b, motif) VALUES (%s, %s, %s) AS n "
            "ON DUPLICATE KEY UPDATE motif = COALESCE(n.motif, exclusions.motif)",
            lignes,
        ))

    def supprimer_exclusion(self, nom_a: str, nom_b: str) -> bool:
        ids = self._ids((nom_a, nom_b))
        a, b = sorted((ids[nom_a], ids[nom_b]))
        return self._ecrire(
            ("DELETE FROM exclusions WHERE personne_a = %s AND personne_b = %s", (a, b))
        ) > 0

    # --- Tirages -------------------------------------------------------------

    def annees(self) -> list[int]:
        return [annee for (annee,) in self._lire("SELECT annee FROM tirages ORDER BY annee")]

    def infos_tirages(self) -> list[tuple[int, str | None]]:
        return self._lire("SELECT annee, note FROM tirages ORDER BY annee")

    def attributions(self, annee: int) -> dict[str, str]:
        return dict(self._lire(
            "SELECT donneur, receveur FROM vue_attributions WHERE annee = %s ORDER BY donneur",
            (annee,),
        ))

    def historique(self) -> list[tuple[int, str, str]]:
        return self._lire("SELECT annee, donneur, receveur FROM vue_attributions ORDER BY annee, donneur")

    def enregistrer_tirage(self, annee: int, attributions: dict[str, str], note: str | None = None) -> None:
        """Crée ou remplace entièrement le tirage d'une année."""
        ids = self._ids(attributions)
        self._ecrire(
            (
                "INSERT INTO tirages (annee, note) VALUES (%s, %s) AS n "
                "ON DUPLICATE KEY UPDATE note = n.note, modifie_le = CURRENT_TIMESTAMP",
                (annee, note),
            ),
            ("DELETE FROM attributions WHERE annee = %s", (annee,)),
            (
                "INSERT INTO attributions (annee, donneur_id, receveur_id) VALUES (%s, %s, %s)",
                [(annee, ids[d], ids[r]) for d, r in attributions.items()],
            ),
        )

    def supprimer_tirage(self, annee: int) -> None:
        self._ecrire(("DELETE FROM tirages WHERE annee = %s", (annee,)))
