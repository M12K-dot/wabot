# NOVA — Bot WhatsApp IA qui apprend ton style (type Levanter, en mieux)

Bot WhatsApp **autonome** et modulaire base sur **Baileys** (Node.js, multi-device),
avec un **cerveau IA Claude**, en **francais**, capable d'**apprendre de tout ton
historique** avec chaque contact et de **repondre a ta place dans ton style** (emojis compris),
sans perdre le contexte.

## Pourquoi "en mieux" que Levanter

| | Levanter | NOVA |
|---|---|---|
| Base | Baileys | Baileys |
| Plugins hot-load | Oui | Oui |
| IA integree | Non | **Oui (Claude)** |
| Clone de TON style par contact | Non | **Oui** |
| Memoire / contexte par discussion | Non | **Oui (historique appris)** |
| Langue | EN | **FR** |
| Modules business | Non | **Tontine (commerce a venir)** |

## Comment le clone apprend

1. A la connexion, WhatsApp synchronise l'historique (`syncFullHistory`) : NOVA
   enregistre les discussions privees dans `data/chats/<contact>.json`.
2. Chaque nouveau message (le tien **et** celui du contact) est ajoute a cette memoire.
3. Quand le clone est actif pour une discussion, NOVA reconstruit la vraie conversation
   (tes messages = toi, les siens = lui) et demande a Claude de repondre **comme toi**,
   avec **ton ton, ta langue et tes emojis**, en gardant le contexte.

## Commandes

- `.menu`, `.ping`, `.alive`
- `.ai <question>` — reponse IA
- `.persona on|off` — active le clone de style **dans la discussion ouverte**
- `.antilink on|off`, `.welcome on|off`, `.tagall`, `.sticker`
- `.tontine add <num> <montant>` | `status` | `reset`

## Demarrage

1. `npm install`
2. Copie `.env.example` en `.env`. Remplis `OWNERS` (ton numero sans +) et `OWNER_NAME`.
   Pour le clone: `ANTHROPIC_API_KEY=...` et `PERSONA_CLONE=true`.
3. `npm start` puis scanne le QR (ou `PAIRING_NUMBER` pour un code).

## Prudence / ethique

Le clone repond sur **ton** compte, a tes contacts, dans **ton** style. C'est ton compte,
mais : active-le discussion par discussion (`.persona on`), respecte le "STOP", et garde a
l'esprit les CGU WhatsApp (compte non-officiel). Utilise de preference un numero dedie.
