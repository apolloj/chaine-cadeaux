@echo off
rem Double-cliquez sur ce fichier pour ouvrir le menu de la chaine de cadeaux.
cd /d "%~dp0"
python -m cadeaux %*
pause
