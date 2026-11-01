# Chaîne de cadeaux

Petit programme Python pour organiser chaque année une **chaîne de cadeaux** en famille :
chacun offre un seul cadeau à un autre membre et en reçoit un seul, le tout formant une
**boucle unique** (A → B → C → … → A). Les tirages sont mémorisés dans une base **MySQL**,
ce qui permet de les consulter, de les corriger et d'éviter les répétitions.

## Règles du tirage

- **Une seule boucle** qui passe par tous les participants de l'année.
- **Règle des 3 ans** : si A a offert à B, alors pendant les 3 années suivantes A ne peut plus
  offrir à B **et** B ne peut pas offrir à A. La durée se règle dans `config.ini`
  (`fenetre_annees`). Si on refait le tirage d'une année passée, les années suivantes comptent aussi.
- **Couples et foyers** : des personnes déclarées comme exclues ne se tirent jamais l'une l'autre.
- Si la règle des 3 ans est **impossible** à respecter (famille trop petite), le programme
  la réduit à 2 ans, puis 1 an, puis l'ignore, et **prévient** avant d'enregistrer.
  Les couples et foyers ne sont jamais assouplis.

> Avec la règle des 3 ans dans les deux sens, chacun peut perdre jusqu'à 6 partenaires
> possibles (plus son conjoint). À partir d'une dizaine de participants, la règle est presque
> toujours respectable ; en dessous, l'assouplissement automatique entrera parfois en jeu.

## Installation (Windows 11)

1. **Python 3.10+** et **MySQL 8.4** :
   ```powershell
   winget install Python.Python.3.13
   winget install Oracle.MySQL
   ```
2. **Initialiser le serveur MySQL** et le déclarer comme service Windows (PowerShell *administrateur*) :
   ```powershell
   powershell -ExecutionPolicy Bypass -File scripts\install_mysql_service.ps1
   ```
3. **Bibliothèques Python** :
   ```powershell
   python -m pip install -r requirements.txt
   ```
4. **Créer la base**, l'utilisateur MySQL dédié et `config.ini` :
   ```powershell
   python -m cadeaux init
   ```
   Sur une installation neuve, le compte `root` de MySQL reçoit un mot de passe aléatoire,
   enregistré dans `mysql_root_password.txt`. Ce fichier et `config.ini` contiennent des mots de
   passe : ils sont exclus de Git (`.gitignore`).

## Utilisation

Double-cliquez sur `lancer.bat`, ou :

```powershell
python -m cadeaux
```

```
=== Chaîne de cadeaux ===
1. Faire le tirage d'une année
2. Voir le tirage d'une année
3. Voir l'historique
4. Saisir un tirage passé
5. Modifier un tirage
6. Supprimer un tirage
7. Couples et foyers (exclusions permanentes)
8. Personnes
0. Quitter
```

### Premier lancement

1. **Saisissez les tirages des années précédentes** (option 4) pour que la règle des 3 ans
   s'applique dès cette année. Une ligne par cadeau, ou la chaîne complète :
   ```
   Alice > Bruno > Chloé > David > Alice
   ```
   (`->` et `→` fonctionnent aussi ; refermez la boucle en répétant le premier nom).
2. **Déclarez les couples et foyers** (option 7) : `Alice, Bruno`. Pour un foyer de plus de
   deux personnes, toutes les paires sont exclues.
3. **Faites le tirage de l'année** (option 1) en donnant la liste des participants :
   - noms séparés par des virgules : `Alice, Bruno, Chloé, David, Emma` ;
   - ou le chemin d'un fichier texte avec un nom par ligne ;
   - ou rien du tout pour reprendre les participants de l'année précédente.

Les nouveaux noms sont ajoutés à la base après confirmation. Les accents et majuscules sont
ignorés à la comparaison (« elise » = « Élise »), et les fautes de frappe proches d'un nom
connu sont signalées.

### Corriger un tirage

L'option 5 permet :
- d'**échanger la place de deux personnes** dans la chaîne (la boucle reste unique) ;
- de **remplacer une personne** par une autre (ex. un absent remplacé au dernier moment) ;
- de **tout ressaisir**.

Avant d'enregistrer, le programme signale les entorses aux règles (plusieurs boucles,
paire déjà tirée récemment, couple qui se tire).

## Base de données

Base `chaine_cadeaux` (voir [`cadeaux/schema.sql`](cadeaux/schema.sql)) :

| Table          | Contenu                                                              |
|----------------|----------------------------------------------------------------------|
| `personnes`    | Membres de la famille (nom unique, sans tenir compte des accents)    |
| `exclusions`   | Paires qui ne se tirent jamais (couples, foyers)                     |
| `tirages`      | Une ligne par année, avec une note (tirage automatique, saisie…)     |
| `attributions` | Qui offre à qui, par année (un don et une réception par personne)    |

La vue `vue_attributions` affiche les tirages avec les noms, pratique dans MySQL Workbench :

```sql
SELECT * FROM vue_attributions WHERE annee = 2026;
```

## Tests

```powershell
python -m pytest
```

Les tests de `tests/test_db.py` utilisent une vraie base MySQL et sont ignorés par défaut.
Pour les lancer, créez un fichier de configuration dont la base se termine par `_test`
(`python -m cadeaux init` avec `CADEAUX_CONFIG` pointant vers ce fichier crée la base),
puis définissez `CADEAUX_TEST_CONFIG` vers ce fichier. Les tables de cette base sont vidées à chaque test.

## Structure

```
cadeaux/
  tirage.py    règles et recherche de la chaîne (indépendant de la base)
  db.py        accès MySQL
  cli.py       menu interactif
  init_db.py   création de la base (python -m cadeaux init)
  noms.py      lecture et comparaison des noms
  schema.sql   schéma MySQL
scripts/install_mysql_service.ps1   initialisation du serveur MySQL sous Windows
tests/                              tests pytest
```
