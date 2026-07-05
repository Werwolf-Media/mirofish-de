#!/bin/bash
# MiroFish beenden (Doppelklick auf dem Mac mini).
# Beendet Backend, Frontend und den Starter — egal in welchem Fenster sie laufen.

echo "======================================"
echo "  MiroFish wird beendet ..."
echo "======================================"

pkill -f "python run.py"   >/dev/null 2>&1
pkill -f "vite"            >/dev/null 2>&1
pkill -f "concurrently"    >/dev/null 2>&1

sleep 1

# Kontrolle: läuft noch etwas auf dem Backend-Port 5001?
if lsof -ti tcp:5001 >/dev/null 2>&1; then
  echo "Hinweis: Backend-Port 5001 noch belegt — beende hart ..."
  lsof -ti tcp:5001 | xargs kill -9 >/dev/null 2>&1
fi

echo "Fertig. MiroFish ist gestoppt."
echo ""
read -r -p "Zum Schließen [Enter] drücken ..."
