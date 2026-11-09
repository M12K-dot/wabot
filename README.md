# 🏭 wabot — Usine d'agents IA

Monorepo regroupant mes agents IA et automatisations (projets actuels et futurs).

## Projets

| Dossier | Rôle | Runtime | Hébergement recommandé |
|---------|------|---------|------------------------|
| [`novabot/`](novabot/) | Bot WhatsApp IA (Baileys) + cerveau Python | Node + Python, **connexion permanente 24/7** | **Railway / Render / VPS** (❌ pas Vercel) |
| [`claude-phone/`](claude-phone/) | Numéro de téléphone pour Claude (SMS + appels, Twilio) | Node / Express (webhooks) | **Railway / Render** (⚠️ Vercel possible) |
| [`connectors/tiktok/`](connectors/tiktok/) | Connecteur TikTok | Python | selon usage |

> **Règle d'hébergement.** Les bots qui tournent en continu (WhatsApp, écoute permanente)
> ont besoin d'un hôte **« always-on »** (Railway, Render, Fly.io, VPS).
> **Vercel** est réservé aux **sites web / pages / fonctions serverless courtes**.

## Sécurité

- Les secrets vivent dans des fichiers `.env` **locaux**, jamais commités (voir `.gitignore`).
- Chaque projet fournit un `.env.example` (modèle sans valeurs) à copier en `.env`.
- Les sessions d'authentification des bots (dossiers `auth/`, `creds.json`…) restent locales.

## Démarrage d'un projet en local

```bash
cd novabot            # ou claude-phone
cp .env.example .env  # puis remplir les vraies valeurs
npm install
npm start
```

## Déploiement

- **Site web → Vercel** : voir la doc Vercel ou `vercel` CLI.
- **Bot 24/7 → Railway/Render** : connecter ce dépôt GitHub, choisir le dossier (ex. `novabot`), définir les variables d'environnement dans le tableau de bord de la plateforme.
