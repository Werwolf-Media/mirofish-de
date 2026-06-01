#!/usr/bin/env bash
# MiroFish - Mac mini Setup (Apple Silicon / macOS)
# Macht alles startklar: uv + Python 3.12 + Frontend/Backend-Dependencies + .env-Vorlage.
# Danach nur noch Keys in .env eintragen und `npm run dev`.
#
# Nutzung auf dem Mac mini:
#   bash setup-mac.sh
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"
echo "==> Repo: $ROOT"

# --- Node-Check (>=18) ---
if ! command -v node >/dev/null 2>&1; then
  echo "FEHLER: Node.js (>=18) nicht gefunden. Bitte Node 18+ installieren (z.B. von nodejs.org)." >&2
  exit 1
fi
echo "==> Node $(node -v), npm $(npm -v)"

# --- uv bereitstellen (offizieller Installer, kein Homebrew noetig) ---
if [ -x "$HOME/.local/bin/uv" ]; then
  export PATH="$HOME/.local/bin:$PATH"
fi
if ! command -v uv >/dev/null 2>&1; then
  echo "==> uv nicht gefunden, installiere via offiziellem Installer..."
  curl -LsSf https://astral.sh/uv/install.sh | sh
  export PATH="$HOME/.local/bin:$PATH"
fi
command -v uv >/dev/null 2>&1 || {
  echo "FEHLER: uv nicht auf PATH. Pruefe $HOME/.local/bin und fuehre aus:" >&2
  echo "        export PATH=\"\$HOME/.local/bin:\$PATH\"" >&2
  exit 1
}
echo "==> uv $(uv --version)"

# --- Python 3.12 (uv-managed; System-Python 3.9 bleibt unangetastet) ---
echo "==> Stelle Python 3.12 bereit (uv-managed)..."
uv python install 3.12

# --- Frontend-Dependencies ---
echo "==> Node-Dependencies (root)..."
npm install
echo "==> Node-Dependencies (frontend)..."
npm install --prefix frontend

# --- Backend-Dependencies (laedt torch CPU/MPS; CUDA wird auf arm64-macOS uebersprungen) ---
echo "==> Backend-Dependencies (uv sync, kann einige Minuten dauern)..."
( cd backend && uv sync )

# --- .env-Vorlage (nur anlegen, falls nicht vorhanden) ---
if [ -f .env ]; then
  echo "==> .env existiert bereits - bleibt unveraendert."
else
  cat > .env <<'ENVEOF'
# ===== LLM (OpenAI-kompatibel, hier OpenRouter) =====
LLM_API_KEY=HIER_OPENROUTER_KEY_EINTRAGEN
LLM_BASE_URL=https://openrouter.ai/api/v1
LLM_MODEL_NAME=openai/gpt-4o-mini

# ===== Zep Cloud (Memory-Graph, Pflicht) - Key von https://app.getzep.com =====
ZEP_API_KEY=HIER_ZEP_KEY_EINTRAGEN
ENVEOF
  echo "==> .env-Vorlage angelegt."
fi

cat <<EOF

============================================================
 Setup fertig.

 1) Keys in die .env eintragen:
      $ROOT/.env
    - LLM_API_KEY  = OpenRouter-Key (https://openrouter.ai)
    - ZEP_API_KEY  = Zep-Key       (https://app.getzep.com)

 2) Starten (uv muss auf PATH sein):
      cd "$ROOT"
      export PATH="\$HOME/.local/bin:\$PATH"
      npm run dev

 3) Browser oeffnen:
      http://localhost:3000
    (Sprache oben rechts umstellbar; Deutsch folgt mit de.json)

 Tipp: Damit uv dauerhaft auf PATH ist, einmalig:
      echo 'export PATH="\$HOME/.local/bin:\$PATH"' >> ~/.zshrc
============================================================
EOF
