#!/usr/bin/env bash
# Demarrage du conteneur : bridge Go (whatsmeow) en arriere-plan + cerveau Python
# au premier plan. Si l'un des deux meurt, on arrete tout -> Railway redemarre.
set -euo pipefail

STORE_DIR="${STORE_DIR:-/app/store}"
mkdir -p "$STORE_DIR"

BRIDGE_PID=""
BRAIN_PID=""

# Arret propre : relayer SIGTERM/SIGINT aux deux process.
shutdown() {
  echo "[start] arret demande, nettoyage..."
  [ -n "$BRIDGE_PID" ] && kill -TERM "$BRIDGE_PID" 2>/dev/null || true
  [ -n "$BRAIN_PID" ] && kill -TERM "$BRAIN_PID" 2>/dev/null || true
  wait 2>/dev/null || true
  exit 0
}
trap shutdown TERM INT

# 1) Bridge Go. Il ecrit sa session dans ./store -> on se place dans /app
#    pour que ./store == /app/store (volume Railway). Ecoute sur $PORT (defaut 8080).
cd /app
echo "[start] lancement du bridge WhatsApp (PORT=${PORT:-8080}, store=$STORE_DIR)"
./whatsapp-bridge &
BRIDGE_PID=$!

# 2) Cerveau Python. Lance depuis novabot/ pour resoudre les fichiers locaux.
cd /app/novabot
echo "[start] lancement du cerveau Python (brain.py)"
python brain.py &
BRAIN_PID=$!

# Si n'importe quel process se termine, on fait tomber le conteneur avec son code.
wait -n "$BRIDGE_PID" "$BRAIN_PID"
EXIT_CODE=$?
echo "[start] un process s'est arrete (code $EXIT_CODE), arret du conteneur."

kill -TERM "$BRIDGE_PID" 2>/dev/null || true
kill -TERM "$BRAIN_PID" 2>/dev/null || true
wait 2>/dev/null || true

exit "$EXIT_CODE"
