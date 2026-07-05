#!/bin/bash
# MiroFish starten (Doppelklick auf dem Mac mini).
# Liegt im Projektordner und wechselt automatisch dorthin — kein Pfad hartkodiert.

cd "$(dirname "$0")" || exit 1

echo "======================================"
echo "  MiroFish wird gestartet ..."
echo "  Projektordner: $(pwd)"
echo "======================================"
echo ""

# Falls noch eine alte Instanz läuft: erst sauber beenden (verhindert Port-Konflikte)
pkill -f "python run.py"   >/dev/null 2>&1
pkill -f "vite"            >/dev/null 2>&1
pkill -f "concurrently"    >/dev/null 2>&1
sleep 1

echo "Starte Backend + Frontend (npm run dev)"
echo "Zum Beenden: dieses Fenster schließen ODER 'MiroFish-Stoppen.command' doppelklicken."
echo ""

npm run dev

# Falls npm run dev abbricht, Fenster offen halten, damit man den Fehler sieht
echo ""
echo "MiroFish wurde beendet. Fenster kann geschlossen werden."
read -r -p "Zum Schließen [Enter] drücken ..."
