#!/usr/bin/env python3
"""TikTok connector — talks to TikTok's OFFICIAL API directly (no third party).

Built by the `universal-connector` skill. Access path chosen: Rung 3 (official
REST API) because no CLI exists and the user declined third-party MCP connectors.

Auth: OAuth 2.0 with PKCE (TikTok Login Kit). You register a free app at
https://developers.tiktok.com, then this script runs the flow and stores tokens.

Secrets come from the environment / a git-ignored token file — never hardcoded:
    TIKTOK_CLIENT_KEY      (from your TikTok app)
    TIKTOK_CLIENT_SECRET   (from your TikTok app)
    TIKTOK_REDIRECT_URI    (a redirect URI you registered, e.g. https://localhost/callback)

Operations (one subcommand each):
    auth-url                 Print the authorization URL to open in a browser.
    token --code C           Exchange the ?code from the redirect for tokens.
    refresh                  Refresh the access token.
    me                       Read your profile + stats (Display API).
    videos [--max N]         List your videos with their stats (Display API).
    creator-info             Query your posting options (Content Posting API).
    post --video-url U --title T [--privacy P] --confirm
                             Publish a video by URL (Direct Post). WRITE — needs --confirm.
    post-status --id ID      Check the status of a publish.

Docs:
  https://developers.tiktok.com/doc/login-kit-manage-user-access-tokens
  https://developers.tiktok.com/doc/display-api-get-started
  https://developers.tiktok.com/doc/content-posting-api-get-started
"""
import argparse
import base64
import hashlib
import json
import os
import secrets
import sys
import urllib.error
import urllib.parse
import urllib.request

AUTH_BASE = "https://www.tiktok.com/v2/auth/authorize/"
API = "https://open.tiktokapis.com/v2"
TOKEN_URL = f"{API}/oauth/token/"
SCOPES = "user.info.basic,user.info.stats,video.list,video.publish,video.upload"

HERE = os.path.dirname(os.path.abspath(__file__))
TOKEN_FILE = os.path.join(HERE, ".tokens.json")        # git-ignored
PKCE_FILE = os.path.join(HERE, ".pkce.json")           # git-ignored, transient


def _env(name: str) -> str:
    val = os.environ.get(name)
    if not val:
        sys.exit(f"error: set {name} in the environment (see README.md / .env.example)")
    return val


def _save(path: str, data: dict) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f)


def _load(path: str) -> dict:
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return {}


def _access_token() -> str:
    tok = os.environ.get("TIKTOK_ACCESS_TOKEN") or _load(TOKEN_FILE).get("access_token")
    if not tok:
        sys.exit("error: no access token. Run `auth-url` then `token --code ...` first.")
    return tok


def _post_form(url: str, form: dict) -> dict:
    data = urllib.parse.urlencode(form).encode()
    req = urllib.request.Request(
        url, data=data, method="POST",
        headers={"Content-Type": "application/x-www-form-urlencoded",
                 "Cache-Control": "no-cache"},
    )
    return _do(req)


def _api(method: str, path: str, *, fields=None, body=None) -> dict:
    url = f"{API}{path}"
    if fields:
        url += "?" + urllib.parse.urlencode({"fields": ",".join(fields)})
    data = json.dumps(body).encode() if body is not None else None
    headers = {"Authorization": f"Bearer {_access_token()}"}
    if data:
        headers["Content-Type"] = "application/json"
    return _do(urllib.request.Request(url, data=data, method=method, headers=headers))


def _do(req) -> dict:
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            raw = resp.read().decode()
            return json.loads(raw) if raw else {}
    except urllib.error.HTTPError as e:
        sys.exit(f"HTTP {e.code} on {req.get_method()} {req.full_url}: "
                 f"{e.read().decode()[:800]}")
    except urllib.error.URLError as e:
        sys.exit(f"network error: {e}")


# --- OAuth ------------------------------------------------------------------
def op_auth_url(_args) -> dict:
    verifier = secrets.token_urlsafe(64)
    challenge = base64.urlsafe_b64encode(
        hashlib.sha256(verifier.encode()).digest()).decode().rstrip("=")
    state = secrets.token_urlsafe(16)
    _save(PKCE_FILE, {"code_verifier": verifier, "state": state})
    params = {
        "client_key": _env("TIKTOK_CLIENT_KEY"),
        "scope": SCOPES,
        "response_type": "code",
        "redirect_uri": _env("TIKTOK_REDIRECT_URI"),
        "state": state,
        "code_challenge": challenge,
        "code_challenge_method": "S256",
    }
    return {"open_this_url": AUTH_BASE + "?" + urllib.parse.urlencode(params),
            "then": "approve, copy the ?code=... from the redirect, run: token --code <code>"}


def op_token(args) -> dict:
    pkce = _load(PKCE_FILE)
    tok = _post_form(TOKEN_URL, {
        "client_key": _env("TIKTOK_CLIENT_KEY"),
        "client_secret": _env("TIKTOK_CLIENT_SECRET"),
        "code": args.code,
        "grant_type": "authorization_code",
        "redirect_uri": _env("TIKTOK_REDIRECT_URI"),
        "code_verifier": pkce.get("code_verifier", ""),
    })
    if "access_token" in tok:
        _save(TOKEN_FILE, tok)
        return {"saved": True, "open_id": tok.get("open_id"),
                "scope": tok.get("scope"), "expires_in": tok.get("expires_in")}
    return tok


def op_refresh(_args) -> dict:
    rt = _load(TOKEN_FILE).get("refresh_token")
    if not rt:
        sys.exit("error: no refresh_token stored; re-run the auth flow.")
    tok = _post_form(TOKEN_URL, {
        "client_key": _env("TIKTOK_CLIENT_KEY"),
        "client_secret": _env("TIKTOK_CLIENT_SECRET"),
        "grant_type": "refresh_token",
        "refresh_token": rt,
    })
    if "access_token" in tok:
        _save(TOKEN_FILE, tok)
        return {"refreshed": True, "expires_in": tok.get("expires_in")}
    return tok


# --- Display API (read) -----------------------------------------------------
def op_me(_args) -> dict:
    return _api("GET", "/user/info/", fields=[
        "open_id", "union_id", "display_name", "avatar_url",
        "follower_count", "following_count", "likes_count", "video_count"])


def op_videos(args) -> dict:
    return _api("POST", "/video/list/",
                fields=["id", "title", "create_time", "view_count",
                        "like_count", "comment_count", "share_count",
                        "duration", "cover_image_url"],
                body={"max_count": args.max})


# --- Content Posting API ----------------------------------------------------
def op_creator_info(_args) -> dict:
    return _api("POST", "/post/publish/creator_info/query/", body={})


def op_post(args) -> dict:
    if not args.confirm:
        sys.exit("refusing to publish without --confirm (this is a WRITE action).")
    return _api("POST", "/post/publish/video/init/", body={
        "post_info": {
            "title": args.title,
            "privacy_level": args.privacy,        # SELF_ONLY is safest while unaudited
            "disable_comment": False,
            "disable_duet": False,
            "disable_stitch": False,
        },
        "source_info": {"source": "PULL_FROM_URL", "video_url": args.video_url},
    })


def op_post_status(args) -> dict:
    return _api("POST", "/post/publish/status/fetch/", body={"publish_id": args.id})


def main() -> None:
    p = argparse.ArgumentParser(description="TikTok official-API connector")
    sub = p.add_subparsers(dest="op", required=True)

    sub.add_parser("auth-url").set_defaults(fn=op_auth_url)

    s = sub.add_parser("token"); s.add_argument("--code", required=True)
    s.set_defaults(fn=op_token)

    sub.add_parser("refresh").set_defaults(fn=op_refresh)
    sub.add_parser("me").set_defaults(fn=op_me)

    s = sub.add_parser("videos"); s.add_argument("--max", type=int, default=20)
    s.set_defaults(fn=op_videos)

    sub.add_parser("creator-info").set_defaults(fn=op_creator_info)

    s = sub.add_parser("post")
    s.add_argument("--video-url", required=True)
    s.add_argument("--title", required=True)
    s.add_argument("--privacy", default="SELF_ONLY",
                   choices=["SELF_ONLY", "MUTUAL_FOLLOW_FRIENDS",
                            "FOLLOWER_OF_CREATOR", "PUBLIC_TO_EVERYONE"])
    s.add_argument("--confirm", action="store_true")
    s.set_defaults(fn=op_post)

    s = sub.add_parser("post-status"); s.add_argument("--id", required=True)
    s.set_defaults(fn=op_post_status)

    args = p.parse_args()
    print(json.dumps(args.fn(args), indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
