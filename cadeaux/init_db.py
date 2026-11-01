"""Création de la base, de l'utilisateur MySQL et des tables : `python -m cadeaux init`."""
from __future__ import annotations

import getpass
import os
import re
import secrets
from importlib import resources

import mysql.connector
from mysql.connector import errorcode

from . import config

FICHIER_MDP_ROOT = config.RACINE / "mysql_root_password.txt"

# Colonnes ajoutées après la première version, pour mettre à jour une base existante.
MIGRATIONS = [
    ("personnes", "archive_depuis", "SMALLINT UNSIGNED NULL AFTER nom"),
]


def _connexion_root(host: str, port: int):
    """Connexion root : mot de passe pris dans MYSQL_ROOT_PASSWORD, puis dans
    mysql_root_password.txt, sinon demandé. Sur une installation neuve (root
    sans mot de passe), un mot de passe est généré et enregistré."""
    mdp = os.environ.get("MYSQL_ROOT_PASSWORD")
    if mdp is None and FICHIER_MDP_ROOT.exists():
        mdp = FICHIER_MDP_ROOT.read_text(encoding="utf-8").strip()
    if mdp is None:
        try:
            cnx = mysql.connector.connect(host=host, port=port, user="root", password="")
        except mysql.connector.Error as erreur:
            if erreur.errno != errorcode.ER_ACCESS_DENIED_ERROR:
                raise
            mdp = getpass.getpass("Mot de passe du compte root MySQL : ")
        else:
            nouveau = secrets.token_urlsafe(18)
            # Écrit avant de changer le mot de passe, pour ne jamais le perdre.
            FICHIER_MDP_ROOT.write_text(nouveau + "\n", encoding="utf-8")
            cur = cnx.cursor()
            cur.execute("ALTER USER 'root'@'localhost' IDENTIFIED BY %s", (nouveau,))
            cur.close()
            print(
                "Le compte root MySQL n'avait pas de mot de passe : un mot de passe a été généré\n"
                f"et enregistré dans {FICHIER_MDP_ROOT}. Conservez-le en lieu sûr."
            )
            return cnx
    return mysql.connector.connect(host=host, port=port, user="root", password=mdp)


def mettre_a_jour_schema(cnx) -> None:
    """Crée les tables manquantes et ajoute les colonnes apparues depuis.
    Sans effet si la base est déjà à jour."""
    sql = resources.files("cadeaux").joinpath("schema.sql").read_text(encoding="utf-8")
    # Les commentaires sont retirés d'abord : ils peuvent contenir des « ; ».
    sans_commentaires = "\n".join(l for l in sql.splitlines() if not l.strip().startswith("--"))
    cur = cnx.cursor()
    for requete in sans_commentaires.split(";"):
        if requete.strip():
            cur.execute(requete)
    cur.execute(
        "SELECT LOWER(TABLE_NAME), LOWER(COLUMN_NAME) FROM information_schema.COLUMNS "
        "WHERE TABLE_SCHEMA = DATABASE()"
    )
    existantes = set(cur.fetchall())
    for table, colonne, definition in MIGRATIONS:
        if (table, colonne) not in existantes:
            cur.execute(f"ALTER TABLE {table} ADD COLUMN {colonne} {definition}")
    cur.close()


def initialiser() -> int:
    chemin = config.chemin_config()
    if chemin.exists():
        parametres = config.charger().mysql
        print(f"Configuration existante réutilisée : {chemin}")
    else:
        parametres = {
            "host": "localhost",
            "port": 3306,
            "user": "cadeaux_app",
            "password": secrets.token_urlsafe(18),
            "database": "chaine_cadeaux",
        }
    base = parametres["database"]
    if not re.fullmatch(r"\w+", base):
        raise ValueError(f"Nom de base invalide : {base}")

    root = _connexion_root(parametres["host"], parametres["port"])
    cur = root.cursor()
    cur.execute(f"CREATE DATABASE IF NOT EXISTS `{base}` CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci")
    cur.execute("CREATE USER IF NOT EXISTS %s@'localhost' IDENTIFIED BY %s", (parametres["user"], parametres["password"]))
    cur.execute("ALTER USER %s@'localhost' IDENTIFIED BY %s", (parametres["user"], parametres["password"]))
    cur.execute(f"GRANT ALL PRIVILEGES ON `{base}`.* TO %s@'localhost'", (parametres["user"],))
    cur.close()
    root.close()

    if not chemin.exists():
        config.ecrire(chemin, parametres)
        print(f"Configuration écrite dans {chemin}")

    cnx = mysql.connector.connect(**parametres)
    try:
        mettre_a_jour_schema(cnx)
    finally:
        cnx.close()
    print(f"Base « {base} » prête.")
    return 0
