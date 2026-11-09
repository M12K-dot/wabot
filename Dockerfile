# syntax=docker/dockerfile:1

############################
# Stage 1 — build du bridge Go (whatsmeow)
############################
# go.mod requiert go 1.26.0 -> on utilise l'image golang 1.26 (Debian bookworm).
FROM golang:1.26-bookworm AS bridge-builder

# go-sqlite3 (mattn) necessite CGO + un compilateur C (present dans l'image golang).
ENV CGO_ENABLED=1 \
    GOOS=linux

WORKDIR /src

# Cache des dependances : on copie d'abord les manifestes.
COPY whatsapp-bridge/go.mod whatsapp-bridge/go.sum ./
RUN go mod download

# Puis le code et build du binaire statique-libc.
COPY whatsapp-bridge/main.go ./
RUN go build -trimpath -ldflags="-s -w" -o /out/whatsapp-bridge .

############################
# Stage 2 — runtime Python + bridge
############################
FROM python:3.12-slim AS runtime

# ffmpeg : brain.py s'en sert pour convertir l'audio (notes vocales).
# ca-certificates : appels HTTPS vers l'API Groq.
RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg ca-certificates \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Binaire du bridge depuis le stage 1.
COPY --from=bridge-builder /out/whatsapp-bridge /app/whatsapp-bridge

# Cerveau Python (brain.py, novastore.py, plugins.py, panel.py, ...).
COPY novabot/ /app/novabot/

# Script de demarrage (lance bridge + brain, arret propre).
COPY start.sh /app/start.sh
RUN chmod +x /app/start.sh

# brain.py n'utilise que la stdlib Python -> pas de pip install requis.
# Variables runtime attendues (a definir cote Railway, JAMAIS en dur) :
#   GROQ_API_KEY   cle API Groq (active le provider cloud)
#   BRIDGE_URL     http://localhost:8080
#   MESSAGES_DB    /app/store/messages.db
#   OWNERS         numero(s) proprietaire separes par des virgules
#   OWNER_NAME     nom affiche du proprietaire
# Le bridge ecrit sa session WhatsApp dans /app/store (monter un volume Railway ici).
ENV BRIDGE_URL=http://localhost:8080 \
    MESSAGES_DB=/app/store/messages.db \
    PORT=8080 \
    PYTHONUNBUFFERED=1

EXPOSE 8080

# Note: le volume /app/store est monte cote Railway (pas d'instruction VOLUME ici,
# non supportee par Railway).

ENTRYPOINT ["/app/start.sh"]
