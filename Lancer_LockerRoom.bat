@echo off
title LockerRoom (serveur)
cd /d "%~dp0"
python -c "import flask" 2>nul || python -m pip install --user -r requirements.txt
:boucle
python server.py
if %errorlevel%==3 goto boucle
echo.
echo LockerRoom s est arrete. Ferme cette fenetre ou appuie sur une touche.
pause >nul
