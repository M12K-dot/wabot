# claude-phone — un vrai numero de telephone pour Claude

Un numero **dedie** (via **Twilio**) que n'importe qui peut contacter :

- **SMS** : on ecrit au numero, Claude repond par SMS.
- **Appels vocaux** : on appelle le numero, on parle, Claude repond a voix haute.

Twilio s'occupe lui-meme du **speech-to-text** (transcription de l'appel) et du
**text-to-speech** (voix francaise), donc pas besoin de service externe.

```
Appelant / SMS  ->  Twilio (numero dedie)  ->  webhook  ->  ce serveur Node  ->  API Claude
```

---

## Prerequis

- **Node.js 18+** installe.
- Une **cle API Anthropic** : https://console.anthropic.com/ (avec du credit).
- Un **compte Twilio** + un **numero achete** (voir plus bas).
- **ngrok** pour exposer ton serveur local a Twilio pendant les tests : https://ngrok.com/download

---

## Etape 1 — Compte Twilio + numero

1. Cree un compte sur https://www.twilio.com/try-twilio (essai gratuit avec credit offert).
2. Verifie ton propre numero de telephone (obligatoire en mode essai : un compte
   d'essai ne peut ecrire/appeler que des numeros **verifies** par toi).
3. Dans la console Twilio : **Phone Numbers > Manage > Buy a number**.
   - Coche les capacites **Voice** et **SMS**.
   - Achete le numero (quelques euros/dollars par mois ; pris sur ton credit d'essai).
4. Note, depuis la page d'accueil de la console :
   - **Account SID**
   - **Auth Token**  (tu le mettras dans `.env`)

> Note : certains pays (dont la France) exigent une piece justificative pour les
> numeros locaux. Un numero **US** est le plus simple pour demarrer les tests.

---

## Etape 2 — Installation du projet

```bash
cd claude-phone
npm install
cp .env.example .env     # sous Windows PowerShell : copy .env.example .env
```

Ouvre `.env` et remplis :

- `ANTHROPIC_API_KEY` = ta cle Anthropic
- `TWILIO_AUTH_TOKEN` = l'Auth Token Twilio

---

## Etape 3 — Lancer le serveur + ngrok

Dans un terminal :

```bash
npm start
```

Dans un **second** terminal :

```bash
ngrok http 3000
```

ngrok affiche une URL publique du type `https://xxxx-xx-xx.ngrok-free.app`.
C'est ton **URL_PUBLIQUE**.

---

## Etape 4 — Brancher les webhooks Twilio

Console Twilio > **Phone Numbers > Manage > Active numbers** > clique sur ton numero.

- Section **Voice & Fax** → *A call comes in* :
  - Webhook : `https://URL_PUBLIQUE/voice`
  - Methode : **HTTP POST**
- Section **Messaging** → *A message comes in* :
  - Webhook : `https://URL_PUBLIQUE/sms`
  - Methode : **HTTP POST**

Clique **Save**.

> A chaque redemarrage de ngrok (version gratuite), l'URL change : il faut
> remettre a jour ces deux webhooks.

---

## Etape 5 — Tester

- **SMS** : envoie un message au numero Twilio depuis ton telephone verifie. Claude repond.
- **Appel** : appelle le numero. Claude te parle, tu reponds, la conversation continue.

Commandes SMS speciales : envoie `reset` (ou `stop`) pour effacer la memoire de la conversation.

---

## Configuration (fichier `.env`)

| Variable | Role | Defaut |
|---|---|---|
| `ANTHROPIC_API_KEY` | Cle API Claude | (obligatoire) |
| `TWILIO_AUTH_TOKEN` | Valide les webhooks Twilio | (obligatoire) |
| `CLAUDE_MODEL` | Modele | `claude-haiku-5-5` |
| `TTS_VOICE` | Voix des appels | `Polly.Lea-Neural` |
| `TTS_LANG` | Langue | `fr-FR` |
| `PORT` | Port local | `3000` |
| `VALIDATE_TWILIO` | Verif de signature | `true` |
| `SYSTEM_PROMPT` | Personnalite de Claude | (interne) |

---

## Limites et couts

- **Twilio** : location du numero (~1 $/mois) + cout par SMS et par minute d'appel.
- **Anthropic** : facture a l'usage (tokens).
- **Mode essai Twilio** : uniquement vers des numeros verifies, et un court message
  d'avertissement est ajoute. Passe en compte paye pour lever ces limites.
- **Memoire** : conservee en RAM, donc perdue au redemarrage du serveur. Pour une
  memoire persistante, brancher une base (SQLite/Redis) dans `src/claude.js`.

---

## Passer en production (plus tard)

Pour que ca tourne 24/7 (PC eteint), deploie sur **Railway**, **Render** ou **Fly.io** :
mets les memes variables d'environnement, et utilise l'URL du service deploye a la
place de l'URL ngrok dans les webhooks Twilio.
