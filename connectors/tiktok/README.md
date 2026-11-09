# TikTok connector (official API, no third party)

Talks directly to TikTok's official API. Built by the `universal-connector` skill.
Pure Python stdlib — no dependencies.

## 1. Create a free TikTok app (one time)
1. Go to https://developers.tiktok.com → **Manage apps** → **Connect an app**.
2. Add the products: **Login Kit**, **Display API**, **Content Posting API**.
3. Request scopes: `user.info.basic`, `user.info.stats`, `video.list`,
   `video.publish`, `video.upload`.
4. Under Login Kit, add a **Redirect URI** (e.g. `https://localhost/callback`).
5. Copy the **Client key** and **Client secret**.

> Public posting needs TikTok's Content Posting **audit** (2–6 weeks). Until then,
> use **Sandbox** mode and keep `--privacy SELF_ONLY` — everything is testable.

## 2. Configure secrets (never committed)
```bash
cp .env.example .env    # then edit .env with your client key/secret
```
Export them into your shell before running (PowerShell):
```powershell
$env:TIKTOK_CLIENT_KEY="..."; $env:TIKTOK_CLIENT_SECRET="..."; $env:TIKTOK_REDIRECT_URI="https://localhost/callback"
```

## 3. Authorize (one time, gets tokens)
```bash
python tiktok.py auth-url          # open the printed URL, approve
python tiktok.py token --code <code-from-redirect-url>
```
Tokens are stored in `.tokens.json` (git-ignored). Refresh later with
`python tiktok.py refresh`.

## 4. Use it
```bash
python tiktok.py me                       # profile + stats
python tiktok.py videos --max 20          # your videos + their stats
python tiktok.py creator-info             # posting options
python tiktok.py post --video-url https://.../clip.mp4 --title "Hello" --confirm
python tiktok.py post-status --id <publish_id>
```
`post` refuses to run without `--confirm` (it's a write action).

## Env vars
| Var | From |
|-----|------|
| `TIKTOK_CLIENT_KEY` | your TikTok app |
| `TIKTOK_CLIENT_SECRET` | your TikTok app |
| `TIKTOK_REDIRECT_URI` | a redirect URI you registered |
| `TIKTOK_ACCESS_TOKEN` | optional override; normally read from `.tokens.json` |

## Docs used
- Login Kit / tokens: https://developers.tiktok.com/doc/login-kit-manage-user-access-tokens
- Display API: https://developers.tiktok.com/doc/display-api-get-started
- Content Posting API: https://developers.tiktok.com/doc/content-posting-api-get-started
