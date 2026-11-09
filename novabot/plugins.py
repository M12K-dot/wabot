# -*- coding: utf-8 -*-
"""
Systeme de plugins / commandes facon Levanter pour NOVA (stdlib uniquement).
Un message commencant par le prefixe (defaut ".") est une COMMANDE.
Chaque plugin = une fonction enregistree via @command. Ajouter un plugin = ajouter une fonction.

Le ctx (fourni par brain.py) expose :
  chat_jid, sender, is_group, is_owner, command, args(list), text(str), owner_name, prefix, settings, uptime, lm
  send(txt), send_media(path), ai(prompt, system=None), history(limit), samples(),
  participants(), sticker(), to_audio(ext='mp3'), photo()
Les APIs web gratuites (sans cle) et les outils deterministes sont faits ici en stdlib.
"""
import ast
import base64 as _b64
import datetime as _dt
import hashlib
import html as _html
import json
import operator as _op
import os
import random
import re
import secrets
import shutil
import string
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid as _uuid
from pathlib import Path

import novastore as ns

REGISTRY = []
_BY_NAME = {}


def register(name, aliases, desc, category, handler):
    p = {"name": name, "aliases": list(aliases), "desc": desc, "category": category, "handler": handler}
    REGISTRY.append(p)
    _BY_NAME[name] = p
    for a in aliases:
        _BY_NAME[a] = p
    return p


def command(name, aliases=(), desc="", category="Divers"):
    def deco(fn):
        register(name, aliases, desc, category, fn)
        return fn
    return deco


def all_plugins():
    return [{"name": p["name"], "aliases": p["aliases"], "desc": p["desc"], "category": p["category"]} for p in REGISTRY]


def is_enabled(name, settings):
    return name not in set(settings.get("plugins_disabled", []) or [])


def dispatch(ctx):
    p = _BY_NAME.get(ctx.command)
    if not p:
        cc = ns.load_json("customcmds.json", {})
        if ctx.command in cc:
            return cc[ctx.command]
        return "❓ commande inconnue. tape %smenu" % ctx.prefix
    if not is_enabled(p["name"], ctx.settings):
        return "⛔ commande desactivee (%s). active-la dans le panneau." % p["name"]
    try:
        return p["handler"](ctx)
    except Exception as e:
        return "⚠️ erreur %s: %s" % (p["name"], e)


# ======================= helpers web (stdlib) =======================
def _http_get(url, timeout=8, headers=None):
    h = {"User-Agent": "Mozilla/5.0 (NOVA-bot)"}
    if headers:
        h.update(headers)
    req = urllib.request.Request(url, headers=h)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read().decode("utf-8", "replace")


def _http_json(url, timeout=8, headers=None):
    return json.loads(_http_get(url, timeout, headers))


def _http_bytes(url, timeout=12, headers=None):
    h = {"User-Agent": "Mozilla/5.0 (NOVA-bot)"}
    if headers:
        h.update(headers)
    req = urllib.request.Request(url, headers=h)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def _enc(s):
    return urllib.parse.quote(s or "", safe="")


def _strip_html(s):
    s = re.sub(r"(?is)<(script|style).*?>.*?</\1>", " ", s)
    s = re.sub(r"(?s)<[^>]+>", " ", s)
    s = _html.unescape(s)
    return re.sub(r"\s+", " ", s).strip()


def _need(ctx, usage):
    return None if ctx.text.strip() else "usage: %s%s" % (ctx.prefix, usage)


# ======================= IA locale (factory) =======================
def ai_command(name, desc, instruction, aliases=(), need_text=True, system=None, category="IA"):
    def h(ctx):
        if need_text and not ctx.text.strip():
            return "usage: %s%s <...>" % (ctx.prefix, name)
        prompt = instruction.format(text=ctx.text.strip(), mot=ctx.text.strip())
        out = ctx.ai(prompt, system)
        return out or "(pas de reponse du modele local)"
    register(name, aliases, desc, category, h)


_SYS_FR = "Tu reponds en francais, de maniere concise et utile. Donne uniquement la reponse, sans preambule."

ai_command("ai", "Pose une question a l'IA locale", "{text}", aliases=("ask", "bot"))
ai_command("explique", "Explique simplement un sujet", "Explique simplement, en quelques phrases : {text}")
ai_command("synonymes", "Synonymes d'un mot", "Donne 8 synonymes de « {mot} », separes par des virgules, rien d'autre.")
ai_command("rime", "Mots qui riment", "Donne 10 mots qui riment avec « {mot} », separes par des virgules.")
ai_command("poeme", "Petit poeme sur un sujet", "Ecris un court poeme (4-6 vers) sur : {text}")
ai_command("histoire", "Mini histoire sur un theme", "Ecris une tres courte histoire (5-6 phrases) sur : {text}")
ai_command("recette", "Recette rapide d'un plat", "Donne une recette simple et courte de : {text} (ingredients + etapes brèves).")
ai_command("idees", "Des idees sur un sujet", "Donne 5 idees concretes sur : {text}")
ai_command("code", "Genere un bout de code", "Ecris le code demande, avec un court commentaire. Demande : {text}")
ai_command("regex", "Construit une regex", "Donne UNE expression reguliere pour : {text}. Donne la regex puis une ligne d'explication.")
ai_command("hashtags", "Hashtags pour un sujet", "Donne 12 hashtags pertinents (avec #) pour : {text}, separes par des espaces.")
ai_command("slogan", "Slogan pour un produit", "Propose 5 slogans courts et percutants pour : {text}")
ai_command("email", "Redige un email", "Redige un email clair et poli sur : {text}")
ai_command("blague", "Une blague", "Raconte une blague courte et dro(la, en francais.", need_text=False)
ai_command("citation", "Une citation inspirante", "Donne une citation inspirante (avec l'auteur si connu).", need_text=False)
ai_command("conseil", "Un conseil de vie", "Donne un conseil de vie court et utile.", need_text=False)
ai_command("excuse", "Une excuse creative", "Invente une excuse drole et creative (1-2 phrases).", need_text=False)
ai_command("compliment", "Un compliment", "Fais un compliment sincere et original" + " (court).", need_text=False)
ai_command("roast", "Petit tacle amical", "Fais un 'roast' leger, drole et AMICAL (jamais mechant/insultant) de : {text}", need_text=False)
ai_command("define", "Definition d'un mot", "Definis simplement le mot « {mot} » en une phrase.")
ai_command("corrige", "Corrige les fautes", "Corrige les fautes du texte, rends UNIQUEMENT le texte corrige : {text}")
ai_command("reformule", "Reformule un texte", "Reformule ce texte autrement, rends uniquement le resultat : {text}")
ai_command("sentiment", "Analyse le sentiment", "Analyse le sentiment de ce texte (positif/negatif/neutre) en un mot + courte raison : {text}")
ai_command("langue", "Detecte la langue", "Dans quelle langue est ce texte ? Reponds juste le nom de la langue : {text}")


@command("tr", desc="Traduire: tr <langue> <texte>", category="IA", aliases=("traduis",))
def _tr(ctx):
    if len(ctx.args) < 2:
        return "usage: %str <langue> <texte>" % ctx.prefix
    lang = ctx.args[0]
    txt = ctx.text.split(None, 1)[1] if len(ctx.text.split(None, 1)) > 1 else ""
    out = ctx.ai("Traduis en %s. Rends UNIQUEMENT la traduction :\n%s" % (lang, txt), _SYS_FR)
    return out or "(traduction indisponible)"


@command("sum", desc="Resume la conversation recente", category="IA", aliases=("resume",))
def _sum(ctx):
    hist = ctx.history(40)
    if not hist:
        return "pas d'historique a resumer"
    convo = "\n".join(("moi" if m["from_me"] else "lui") + ": " + m["content"] for m in hist)
    return ctx.ai("Resume en 3 points brefs cette conversation :\n" + convo[:4000], _SYS_FR) or "(indisponible)"


@command("resumeweb", desc="Resume une page web: resumeweb <url>", category="IA", aliases=("websum",))
def _resumeweb(ctx):
    u = ctx.text.strip()
    if not u:
        return "usage: %sresumeweb <url>" % ctx.prefix
    if not u.startswith("http"):
        u = "https://" + u
    try:
        txt = _strip_html(_http_get(u, timeout=12))[:4000]
    except Exception as e:
        return "page inaccessible (%s)" % e
    if not txt:
        return "aucun texte lisible sur la page"
    return ctx.ai("Resume en 4 points cette page web :\n" + txt, _SYS_FR) or "(indisponible)"


@command("style", desc="Montre tes exemples de style appris", category="IA")
def _style(ctx):
    s = ctx.samples()
    return "🧬 ton style appris :\n" + "\n".join("- " + x for x in s) if s else "pas assez d'exemples"


# ======================= Outils deterministes =======================
_ALLOWED_OPS = {
    ast.Add: _op.add, ast.Sub: _op.sub, ast.Mult: _op.mul, ast.Div: _op.truediv,
    ast.FloorDiv: _op.floordiv, ast.Mod: _op.mod, ast.Pow: _op.pow, ast.USub: _op.neg, ast.UAdd: _op.pos,
}


def _safe_eval(node):
    if isinstance(node, ast.Expression):
        return _safe_eval(node.body)
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
        return node.value
    if isinstance(node, ast.BinOp) and type(node.op) in _ALLOWED_OPS:
        return _ALLOWED_OPS[type(node.op)](_safe_eval(node.left), _safe_eval(node.right))
    if isinstance(node, ast.UnaryOp) and type(node.op) in _ALLOWED_OPS:
        return _ALLOWED_OPS[type(node.op)](_safe_eval(node.operand))
    raise ValueError("expression non autorisee")


@command("calc", desc="Calculatrice: calc <expression>", category="Outils", aliases=("math",))
def _calc(ctx):
    if not ctx.text.strip():
        return "usage: %scalc 2*(3+4)" % ctx.prefix
    try:
        return "= " + str(_safe_eval(ast.parse(ctx.text, mode="eval")))
    except Exception:
        return "expression invalide"


@command("base64", desc="base64 <enc|dec> <texte>", category="Outils", aliases=("b64",))
def _base64(ctx):
    if len(ctx.args) < 2:
        return "usage: %sbase64 enc|dec <texte>" % ctx.prefix
    mode = ctx.args[0].lower()
    data = ctx.text.split(None, 1)[1]
    try:
        if mode.startswith("enc"):
            return _b64.b64encode(data.encode()).decode()
        return _b64.b64decode(data.encode()).decode("utf-8", "replace")
    except Exception:
        return "entree invalide"


@command("hash", desc="hash <md5|sha256> <texte>", category="Outils")
def _hash(ctx):
    if len(ctx.args) < 2:
        return "usage: %shash md5|sha256 <texte>" % ctx.prefix
    algo = ctx.args[0].lower()
    data = ctx.text.split(None, 1)[1].encode()
    if algo not in ("md5", "sha1", "sha256", "sha512"):
        return "algos: md5, sha1, sha256, sha512"
    return hashlib.new(algo, data).hexdigest()


@command("uuid", desc="Genere un UUID", category="Outils")
def _uuidc(ctx):
    return str(_uuid.uuid4())


@command("motdepasse", desc="motdepasse <longueur>", category="Outils", aliases=("pass", "pwd"))
def _pwd(ctx):
    n = 16
    if ctx.args and ctx.args[0].isdigit():
        n = max(6, min(64, int(ctx.args[0])))
    alpha = string.ascii_letters + string.digits + "!@#$%&*?-_"
    return "".join(secrets.choice(alpha) for _ in range(n))


@command("roll", desc="Lancer de des: roll 2d6", category="Outils", aliases=("de", "dice"))
def _roll(ctx):
    spec = (ctx.args[0] if ctx.args else "1d6").lower()
    m = re.match(r"^(\d*)d(\d+)$", spec)
    if not m:
        return "usage: %sroll 2d6" % ctx.prefix
    n = int(m.group(1) or 1)
    f = int(m.group(2))
    if n < 1 or n > 50 or f < 2 or f > 1000:
        return "valeurs hors limites"
    rolls = [random.randint(1, f) for _ in range(n)]
    return "🎲 " + " + ".join(map(str, rolls)) + (" = " + str(sum(rolls)) if n > 1 else "")


@command("pileouface", desc="Pile ou face", category="Outils", aliases=("flip", "pof"))
def _flip(ctx):
    return "🪙 " + random.choice(["Pile", "Face"])


@command("choisis", desc="choisis a | b | c", category="Outils", aliases=("choose", "pick"))
def _choose(ctx):
    opts = [o.strip() for o in ctx.text.split("|") if o.strip()]
    if len(opts) < 2:
        return "usage: %schoisis option1 | option2 | ..." % ctx.prefix
    return "👉 " + random.choice(opts)


@command("8ball", desc="Boule magique: 8ball <question>", category="Outils", aliases=("boule",))
def _8ball(ctx):
    rep = ["Oui", "Non", "Peut-etre", "Carrement", "Jamais", "Demande plus tard", "C'est sur", "J'en doute",
           "Probable", "Aucune chance", "Fonce", "Reflechis encore"]
    return "🎱 " + random.choice(rep)


@command("compte", desc="Compte mots/caracteres", category="Outils", aliases=("count",))
def _count(ctx):
    t = ctx.text
    if not t.strip():
        return "usage: %scompte <texte>" % ctx.prefix
    return "mots: %d · caracteres: %d" % (len(t.split()), len(t))


_MORSE = {
    "a": ".-", "b": "-...", "c": "-.-.", "d": "-..", "e": ".", "f": "..-.", "g": "--.", "h": "....",
    "i": "..", "j": ".---", "k": "-.-", "l": ".-..", "m": "--", "n": "-.", "o": "---", "p": ".--.",
    "q": "--.-", "r": ".-.", "s": "...", "t": "-", "u": "..-", "v": "...-", "w": ".--", "x": "-..-",
    "y": "-.--", "z": "--..", "0": "-----", "1": ".----", "2": "..---", "3": "...--", "4": "....-",
    "5": ".....", "6": "-....", "7": "--...", "8": "---..", "9": "----.", " ": "/",
}
_MORSE_R = {v: k for k, v in _MORSE.items()}


@command("morse", desc="morse <enc|dec> <texte>", category="Outils")
def _morse(ctx):
    if len(ctx.args) < 2:
        return "usage: %smorse enc|dec <texte>" % ctx.prefix
    mode = ctx.args[0].lower()
    data = ctx.text.split(None, 1)[1]
    if mode.startswith("enc"):
        return " ".join(_MORSE.get(c, "?") for c in data.lower())
    return "".join(_MORSE_R.get(tok, "") for tok in data.split(" ")).replace("/", " ")


_LEET = str.maketrans({"a": "4", "e": "3", "i": "1", "o": "0", "s": "5", "t": "7", "l": "1", "g": "9"})


@command("leet", desc="Convertit en 1337", category="Texte/Fun")
def _leet(ctx):
    return (ctx.text or "").lower().translate(_LEET) or ("usage: %sleet <texte>" % ctx.prefix)


@command("binaire", desc="binaire <enc|dec> <texte>", category="Outils", aliases=("bin",))
def _binaire(ctx):
    if len(ctx.args) < 2:
        return "usage: %sbinaire enc|dec <texte>" % ctx.prefix
    mode = ctx.args[0].lower()
    data = ctx.text.split(None, 1)[1]
    try:
        if mode.startswith("enc"):
            return " ".join(format(b, "08b") for b in data.encode())
        return bytes(int(x, 2) for x in data.split()).decode("utf-8", "replace")
    except Exception:
        return "entree invalide"


@command("qr", desc="QR code: qr <texte/url>", category="Outils")
def _qr(ctx):
    if not ctx.text.strip():
        return "usage: %sqr <texte ou url>" % ctx.prefix
    try:
        data = _http_bytes("https://api.qrserver.com/v1/create-qr-code/?size=400x400&data=" + _enc(ctx.text.strip()))
        path = str(Path(tempfile.gettempdir()) / ("nova_qr_%d.png" % int(time.time())))
        Path(path).write_bytes(data)
        ok, msg = ctx.send_media(path)
        return None if ok else "QR indisponible (%s)" % msg
    except Exception as e:
        return "QR indisponible (%s)" % e


# ======================= Texte / Fun =======================
@command("mock", desc="tExTe MoQuEuR", category="Texte/Fun")
def _mock(ctx):
    t = ctx.text or ""
    if not t.strip():
        return "usage: %smock <texte>" % ctx.prefix
    return "".join(c.upper() if i % 2 else c.lower() for i, c in enumerate(t))


@command("reverse", desc="Inverse le texte", category="Texte/Fun", aliases=("rev",))
def _reverse(ctx):
    return (ctx.text or "")[::-1] or ("usage: %sreverse <texte>" % ctx.prefix)


@command("upper", desc="MAJUSCULES", category="Texte/Fun")
def _upper(ctx):
    return (ctx.text or "").upper() or ("usage: %supper <texte>" % ctx.prefix)


@command("lower", desc="minuscules", category="Texte/Fun")
def _lower(ctx):
    return (ctx.text or "").lower() or ("usage: %slower <texte>" % ctx.prefix)


@command("clap", desc="mots 👏 separes 👏 par 👏 clap", category="Texte/Fun")
def _clap(ctx):
    w = (ctx.text or "").split()
    return " 👏 ".join(w) if w else ("usage: %sclap <texte>" % ctx.prefix)


@command("space", desc="t e x t e   e s p a c e", category="Texte/Fun")
def _space(ctx):
    return " ".join((ctx.text or "")) or ("usage: %sspace <texte>" % ctx.prefix)


# ======================= Web (APIs gratuites sans cle) =======================
@command("meteo", desc="Meteo d'une ville: meteo <ville>", category="Web", aliases=("weather",))
def _meteo(ctx):
    v = ctx.text.strip() or "Douala"
    try:
        return "🌦 " + _http_get("https://wttr.in/%s?format=3&lang=fr" % _enc(v), timeout=9).strip()
    except Exception:
        return "meteo indisponible (hors-ligne ?)"


@command("wiki", desc="Resume Wikipedia: wiki <sujet>", category="Web")
def _wiki(ctx):
    if not ctx.text.strip():
        return "usage: %swiki <sujet>" % ctx.prefix
    try:
        d = _http_json("https://fr.wikipedia.org/api/rest_v1/page/summary/" + _enc(ctx.text.strip().replace(" ", "_")), timeout=9)
        ex = d.get("extract")
        return ("📖 " + ex) if ex else "aucun resultat Wikipedia"
    except Exception:
        return "Wikipedia indisponible"


@command("dico", desc="Definition (web): dico <mot>", category="Web")
def _dico(ctx):
    w = ctx.text.strip()
    if not w:
        return "usage: %sdico <mot>" % ctx.prefix
    for lang in ("fr", "en"):
        try:
            d = _http_json("https://api.dictionaryapi.dev/api/v2/entries/%s/%s" % (lang, _enc(w)), timeout=9)
            defs = d[0]["meanings"][0]["definitions"][0]["definition"]
            return "📘 " + defs
        except Exception:
            continue
    return "aucune definition trouvee"


@command("crypto", desc="Prix crypto: crypto <coin>", category="Web")
def _crypto(ctx):
    coin = (ctx.text.strip() or "bitcoin").lower().replace(" ", "-")
    try:
        d = _http_json("https://api.coingecko.com/api/v3/simple/price?ids=%s&vs_currencies=usd,eur" % _enc(coin), timeout=9)
        if coin not in d:
            return "coin inconnu (ex: bitcoin, ethereum, solana)"
        return "💰 %s : %s$ / %s€" % (coin, d[coin].get("usd"), d[coin].get("eur"))
    except Exception:
        return "service crypto indisponible"


@command("convert", desc="convert <montant> <de> <vers>", category="Web", aliases=("change",))
def _convert(ctx):
    if len(ctx.args) < 3:
        return "usage: %sconvert 100 usd eur" % ctx.prefix
    amt, src, dst = ctx.args[0], ctx.args[1].upper(), ctx.args[2].upper()
    try:
        d = _http_json("https://api.exchangerate.host/convert?from=%s&to=%s&amount=%s" % (src, dst, _enc(amt)), timeout=9)
        res = d.get("result")
        return "💱 %s %s = %.2f %s" % (amt, src, float(res), dst) if res is not None else "conversion indisponible"
    except Exception:
        return "service de change indisponible"


@command("pays", desc="Infos pays: pays <nom>", category="Web", aliases=("country",))
def _pays(ctx):
    if not ctx.text.strip():
        return "usage: %spays <nom>" % ctx.prefix
    try:
        d = _http_json("https://restcountries.com/v3.1/name/%s?fields=name,capital,population,region,flag" % _enc(ctx.text.strip()), timeout=9)
        c = d[0]
        return "%s %s · capitale: %s · pop: %s · region: %s" % (
            c.get("flag", ""), c.get("name", {}).get("common", ""), (c.get("capital") or ["?"])[0],
            format(c.get("population", 0), ",").replace(",", " "), c.get("region", ""))
    except Exception:
        return "pays introuvable"


@command("fait", desc="Un fait aleatoire", category="Web", aliases=("fact",))
def _fait(ctx):
    try:
        return "💡 " + _http_json("https://uselessfacts.jsph.pl/api/v2/facts/random?language=fr", timeout=9).get("text", "")
    except Exception:
        return "service indisponible"


@command("chatfait", desc="Fait sur les chats", category="Web", aliases=("catfact",))
def _chatfait(ctx):
    try:
        return "🐱 " + _http_json("https://catfact.ninja/fact", timeout=9).get("fact", "")
    except Exception:
        return "service indisponible"


@command("chienfait", desc="Fait sur les chiens", category="Web", aliases=("dogfact",))
def _chienfait(ctx):
    try:
        return "🐶 " + _http_json("https://dog-api.kinduff.com/api/facts", timeout=9).get("facts", [""])[0]
    except Exception:
        return "service indisponible"


@command("citationweb", desc="Citation (web)", category="Web")
def _citationweb(ctx):
    try:
        d = _http_json("https://api.quotable.io/random", timeout=9)
        return "« %s » — %s" % (d.get("content", ""), d.get("author", ""))
    except Exception:
        return "service indisponible"


@command("blagueweb", desc="Blague (web)", category="Web")
def _blagueweb(ctx):
    try:
        d = _http_json("https://official-joke-api.appspot.com/random_joke", timeout=9)
        return "😄 %s\n%s" % (d.get("setup", ""), d.get("punchline", ""))
    except Exception:
        return "service indisponible"


@command("conseilweb", desc="Conseil (web)", category="Web")
def _conseilweb(ctx):
    try:
        return "🧭 " + _http_json("https://api.adviceslip.com/advice", timeout=9).get("slip", {}).get("advice", "")
    except Exception:
        return "service indisponible"


@command("raccourci", desc="Raccourcir une url: raccourci <url>", category="Web", aliases=("short",))
def _raccourci(ctx):
    u = ctx.text.strip()
    if not u:
        return "usage: %sraccourci <url>" % ctx.prefix
    if not u.startswith("http"):
        u = "https://" + u
    try:
        return "🔗 " + _http_get("https://is.gd/create.php?format=simple&url=" + _enc(u), timeout=9).strip()
    except Exception:
        return "service indisponible"


@command("heure", desc="Heure d'une zone: heure Europe/Paris", category="Web", aliases=("time",))
def _heure(ctx):
    z = ctx.text.strip() or "Europe/Paris"
    try:
        d = _http_json("http://worldtimeapi.org/api/timezone/" + _enc(z), timeout=9)
        dt = d.get("datetime", "")
        return "🕒 %s : %s" % (z, dt[:19].replace("T", " ")) if dt else "zone inconnue (ex: Europe/Paris, Africa/Douala)"
    except Exception:
        return "zone inconnue (ex: Europe/Paris, Africa/Douala)"


# ======================= Groupe =======================
def _bridge_base(ctx):
    try:
        b = (ctx.settings.get("bridge_url") or "").rstrip("/")
    except Exception:
        b = ""
    return b or "http://localhost:8080"


@command("tagall", desc="Mentionne tous les membres (groupe)", category="Groupe", aliases=("all",))
def _tagall(ctx):
    if not ctx.is_group:
        return "commande de groupe uniquement"
    base = _bridge_base(ctx)
    try:
        data = _http_json(base + "/api/group?jid=" + _enc(ctx.chat_jid), timeout=15)
    except Exception as e:
        return "impossible de recuperer les membres: " + str(e)
    parts = [p for p in (data.get("participants") or []) if p.get("jid")]
    if not parts:
        return "aucun membre trouve"
    jids = [p["jid"] for p in parts]
    users = [p.get("user", "") for p in parts]
    titre = (ctx.text or "").strip()
    lines = []
    if titre:
        lines.append(titre)
    lines.append("👥 %d membres" % len(jids))
    lines.append("")
    lines += ["@" + u for u in users]
    text = "\n".join(lines)
    if getattr(ctx, "dry", False):
        return "[apercu tagall, non envoye] " + str(len(jids)) + " membres: " + ", ".join("@" + u for u in users[:20])
    payload = json.dumps({"recipient": ctx.chat_jid, "message": text, "mentions": jids}).encode("utf-8")
    try:
        req = urllib.request.Request(base + "/api/send", data=payload,
                                     headers={"content-type": "application/json"}, method="POST")
        with urllib.request.urlopen(req, timeout=30) as r:
            out = json.loads(r.read().decode("utf-8"))
        if not out.get("success"):
            return "echec envoi: " + str(out.get("message", ""))
    except Exception as e:
        return "echec envoi: " + str(e)
    return None


@command("everyone", desc="Alias de tagall", category="Groupe")
def _everyone(ctx):
    return _tagall(ctx)


# ----- Phase 2 : admin de groupe via endpoints du bridge -----
def _bridge_base():
    return ns.bridge_url()


def _bridge_post(path, payload, timeout=30):
    try:
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(_bridge_base() + path, data=data,
                                     headers={"content-type": "application/json"}, method="POST")
        with urllib.request.urlopen(req, timeout=timeout) as r:
            out = json.loads(r.read().decode("utf-8", "replace"))
        return bool(out.get("success")), (out.get("error") or out.get("message") or "")
    except urllib.error.HTTPError as e:
        try:
            body = e.read().decode("utf-8", "replace")
        except Exception:
            body = str(e)
        return False, "HTTP %s: %s" % (e.code, body[:160])
    except Exception as e:
        return False, str(e)


def _grp_guard(ctx):
    return _sudo_guard(ctx) or (None if ctx.is_group else "commande de groupe uniquement")


def _group_action(ctx, action):
    g = _grp_guard(ctx)
    if g:
        return g
    tgt = [a for a in ctx.args if a.strip()]
    if not tgt:
        return "usage: %s%s <numero...>" % (ctx.prefix, action)
    if getattr(ctx, "dry", False):
        return "[DRY] %s : %s" % (action, ", ".join(tgt))
    ok, err = _bridge_post("/api/group-action", {"jid": ctx.chat_jid, "action": action, "participants": tgt})
    return ("✅ %s ok" % action) if ok else ("🚫 echec %s : %s" % (action, err or "le bot est-il admin ?"))


@command("kick", desc="Expulse: kick <num...>", category="Groupe")
def _kick(ctx):
    return _group_action(ctx, "kick")


@command("add", desc="Ajoute: add <num...>", category="Groupe")
def _addmember(ctx):
    return _group_action(ctx, "add")


@command("promote", desc="Donne admin: promote <num...>", category="Groupe")
def _promote(ctx):
    return _group_action(ctx, "promote")


@command("demote", desc="Retire admin: demote <num...>", category="Groupe")
def _demote(ctx):
    return _group_action(ctx, "demote")


@command("gname", desc="Renomme le groupe: gname <nom>", category="Groupe")
def _gname(ctx):
    g = _grp_guard(ctx)
    if g:
        return g
    if not ctx.text.strip():
        return "usage: %sgname <nouveau nom>" % ctx.prefix
    if getattr(ctx, "dry", False):
        return "[DRY] renommerait en : " + ctx.text.strip()
    ok, err = _bridge_post("/api/group-setname", {"jid": ctx.chat_jid, "name": ctx.text.strip()})
    return "✅ groupe renomme" if ok else "🚫 echec : " + (err or "le bot est-il admin ?")


@command("gdesc", desc="Change la description: gdesc <texte>", category="Groupe")
def _gdesc(ctx):
    g = _grp_guard(ctx)
    if g:
        return g
    if not ctx.text.strip():
        return "usage: %sgdesc <texte>" % ctx.prefix
    if getattr(ctx, "dry", False):
        return "[DRY] description -> " + ctx.text.strip()[:40]
    ok, err = _bridge_post("/api/group-settopic", {"jid": ctx.chat_jid, "topic": ctx.text.strip()})
    return "✅ description mise a jour" if ok else "🚫 echec : " + (err or "le bot est-il admin ?")


@command("mute", desc="Seuls les admins ecrivent", category="Groupe")
def _mute(ctx):
    g = _grp_guard(ctx)
    if g:
        return g
    if getattr(ctx, "dry", False):
        return "[DRY] muterait le groupe"
    ok, err = _bridge_post("/api/group-announce", {"jid": ctx.chat_jid, "announce": True})
    return "🔇 groupe en mode admins seulement" if ok else "🚫 echec : " + (err or "le bot est-il admin ?")


@command("unmute", desc="Tout le monde peut ecrire", category="Groupe")
def _unmute(ctx):
    g = _grp_guard(ctx)
    if g:
        return g
    if getattr(ctx, "dry", False):
        return "[DRY] unmute"
    ok, err = _bridge_post("/api/group-announce", {"jid": ctx.chat_jid, "announce": False})
    return "🔊 tout le monde peut ecrire" if ok else "🚫 echec : " + (err or "le bot est-il admin ?")


@command("react", desc="Reagit au dernier message: react <emoji>", category="Groupe")
def _react(ctx):
    g = _sudo_guard(ctx)
    if g:
        return g
    emoji = (ctx.text.strip().split()[0] if ctx.text.strip() else "👍")
    try:
        con = ns.db_connect()
        jids = ns.equiv_jids(ctx.chat_jid, ctx.lm)
        ph = ",".join("?" for _ in jids)
        row = con.execute("SELECT id, sender FROM messages WHERE chat_jid IN (%s) "
                          "ORDER BY timestamp DESC LIMIT 1" % ph, tuple(jids)).fetchone()
        con.close()
    except Exception as e:
        return "impossible de lire le dernier message (%s)" % e
    if not row:
        return "aucun message a reagir"
    sender = row["sender"] or ctx.chat_jid
    if getattr(ctx, "dry", False):
        return "[DRY] reagirait %s au message %s" % (emoji, row["id"])
    ok, err = _bridge_post("/api/react", {"chat": ctx.chat_jid, "id": row["id"], "sender": sender, "emoji": emoji})
    return ("✅ reaction " + emoji) if ok else ("🚫 echec reaction : " + (err or ""))


@command("poll", desc="Sondage: poll <question> | opt1 | opt2", category="Groupe", aliases=("sondage",))
def _poll(ctx):
    g = _sudo_guard(ctx)
    if g:
        return g
    parts = [p.strip() for p in ctx.text.split("|") if p.strip()]
    if len(parts) < 3:
        return "usage: %spoll question | option1 | option2 [| ...]" % ctx.prefix
    name, options = parts[0], parts[1:12]
    if getattr(ctx, "dry", False):
        return "[DRY] sondage « %s » (%d options)" % (name, len(options))
    ok, err = _bridge_post("/api/poll", {"recipient": ctx.chat_jid, "name": name, "options": options, "selectable": 1})
    return "🗳 sondage cree" if ok else "🚫 echec sondage : " + (err or "")


# ----- Phase 2 : evenementiel (welcome/goodbye + antidelete/antiedit) -----
def _greet(ctx, kind):
    g = _grp_guard(ctx)
    if g:
        return g
    if not ctx.args or ctx.args[0].lower() not in ("on", "off"):
        return "usage: %s%s on|off [message]  (placeholders {user} {group})" % (ctx.prefix, kind)
    on = ctx.args[0].lower() == "on"
    rest = ctx.text.split(None, 1)
    msg = rest[1] if len(rest) > 1 else None
    ns.set_greet(kind, ctx.chat_jid, on=on, msg=msg)
    return "👋 %s %s%s" % (kind, "ON" if on else "off", (" : " + msg) if msg else "")


@command("welcome", desc="welcome on|off [message] (groupe)", category="Groupe")
def _welcome(ctx):
    return _greet(ctx, "welcome")


@command("goodbye", desc="goodbye on|off [message] (groupe)", category="Groupe")
def _goodbye(ctx):
    return _greet(ctx, "goodbye")


@command("antidelete", desc="antidelete on|off (anti-suppression)", category="Automations", aliases=("antidel",))
def _antidelete(ctx):
    g = _sudo_guard(ctx)
    if g:
        return g
    if not ctx.args or ctx.args[0].lower() not in ("on", "off"):
        return "usage: %santidelete on|off" % ctx.prefix
    on = ctx.args[0].lower() == "on"
    ns.save_settings({"antidelete": on})
    return "🗑️ antidelete %s" % ("ON (notif en prive)" if on else "off")


@command("antiedit", desc="antiedit on|off (anti-edition)", category="Automations")
def _antiedit(ctx):
    g = _sudo_guard(ctx)
    if g:
        return g
    if not ctx.args or ctx.args[0].lower() not in ("on", "off"):
        return "usage: %santiedit on|off" % ctx.prefix
    on = ctx.args[0].lower() == "on"
    ns.save_settings({"antiedit": on})
    return "✏️ antiedit %s" % ("ON" if on else "off")


# ======================= Medias (ffmpeg + bridge) =======================
@command("sticker", desc="Image -> sticker (reponds/envoie une image)", category="Medias", aliases=("s",))
def _sticker(ctx):
    ok, msg = ctx.sticker()
    return None if ok else "🚫 sticker indisponible (%s)" % msg


@command("photo", desc="Derniere image -> renvoyee en photo", category="Medias")
def _photo(ctx):
    ok, msg = ctx.photo()
    return None if ok else "🚫 photo indisponible (%s)" % msg


@command("tomp3", desc="Derniere video/vocal -> mp3", category="Medias", aliases=("toaudio",))
def _tomp3(ctx):
    ok, msg = ctx.to_audio("mp3")
    return None if ok else "🚫 extraction audio indisponible (%s)" % msg


# ======================= Controle du bot =======================
def _resolve_enabled(ctx):
    for j in ns.equiv_jids(ctx.chat_jid, ctx.lm):
        if j in ns.enabled_jids():
            return True
    return False


@command("persona", desc="persona on|off|status (ce chat)", category="Bot")
def _persona(ctx):
    sub = (ctx.args[0].lower() if ctx.args else "status")
    canon = ns.send_recipient(ctx.chat_jid, ctx.lm)
    if sub == "on":
        ns.set_contact(canon, {"enabled": True})
        return "🧬 clone ACTIVE pour ce chat"
    if sub == "off":
        ns.set_contact(canon, {"enabled": False})
        return "🧬 clone desactive pour ce chat"
    return "🧬 clone : " + ("ACTIF" if _resolve_enabled(ctx) else "off") + " ici"


@command("pause", desc="Suspend les reponses (global)", category="Bot")
def _pause(ctx):
    ns.save_settings({"paused": True})
    return "⏸ bot en pause (reponses suspendues)"


@command("resume", desc="Reprend les reponses (global)", category="Bot", aliases=("reprendre",))
def _resume(ctx):
    ns.save_settings({"paused": False})
    return "▶ bot repris"


@command("vacances", desc="vacances on|off", category="Bot")
def _vacances(ctx):
    sub = (ctx.args[0].lower() if ctx.args else "")
    if sub == "on":
        ns.save_settings({"vacation_mode": True})
        return "🏖 mode vacances ACTIVE"
    if sub == "off":
        ns.save_settings({"vacation_mode": False})
        return "mode vacances desactive"
    return "usage: %svacances on|off" % ctx.prefix


@command("plugins", desc="Liste actives/desactives", category="Bot")
def _plugins(ctx):
    dis = set(ctx.settings.get("plugins_disabled", []) or [])
    on = [p["name"] for p in REGISTRY if p["name"] not in dis]
    off = sorted(dis)
    out = "✅ actifs (%d): %s" % (len(on), ", ".join(sorted(on)))
    if off:
        out += "\n⛔ off (%d): %s" % (len(off), ", ".join(off))
    return out


@command("on", desc="Active un plugin: on <nom>", category="Bot")
def _on(ctx):
    if not ctx.args:
        return "usage: %son <plugin>" % ctx.prefix
    name = ctx.args[0].lower()
    dis = [x for x in (ctx.settings.get("plugins_disabled", []) or []) if x != name]
    ns.save_settings({"plugins_disabled": dis})
    return "✅ %s active" % name


@command("off", desc="Desactive un plugin: off <nom>", category="Bot")
def _off(ctx):
    if not ctx.args:
        return "usage: %soff <plugin>" % ctx.prefix
    name = ctx.args[0].lower()
    if name not in _BY_NAME:
        return "plugin inconnu"
    dis = set(ctx.settings.get("plugins_disabled", []) or [])
    dis.add(_BY_NAME[name]["name"])
    ns.save_settings({"plugins_disabled": sorted(dis)})
    return "⛔ %s desactive" % name


@command("prefix", desc="Change le prefixe: prefix <x>", category="Bot")
def _prefix(ctx):
    if not ctx.args:
        return "prefixe actuel : %s" % ctx.prefix
    p = ctx.args[0][:3]
    ns.save_settings({"command_prefix": p})
    return "prefixe change en « %s »" % p


@command("model", desc="Change le modele Ollama: model <nom>", category="Bot")
def _model(ctx):
    if not ctx.args:
        return "modele actuel : %s" % ctx.settings.get("model")
    ns.save_settings({"model": ctx.args[0]})
    return "modele change en %s" % ctx.args[0]


@command("stats", desc="Statistiques du bot", category="Bot")
def _stats(ctx):
    s = ns.load_stats()
    return ("📊 recus: %d (auj. %d) · envoyes: %d (auj. %d)" %
            (s.get("total_received", 0), s.get("today_received", 0), s.get("total_sent", 0), s.get("today_sent", 0)))


@command("reglages", desc="Affiche les reglages cles", category="Bot", aliases=("config",))
def _reglages(ctx):
    s = ctx.settings
    return ("⚙️ modele: %s · pause: %s · vacances: %s\nprefixe: %s · owner_only: %s · debounce: %ss · debit/h: %s"
            % (s.get("model"), s.get("paused"), s.get("vacation_mode"), s.get("command_prefix"),
               s.get("commands_owner_only"), s.get("debounce_seconds"), s.get("rate_per_hour")))


# ======================= General =======================
@command("menu", desc="Affiche toutes les commandes", category="General", aliases=("help", "aide", "commands"))
def _menu(ctx):
    dis = set(ctx.settings.get("plugins_disabled", []) or [])
    cats = {}
    for p in REGISTRY:
        if p["name"] in dis:
            continue
        cats.setdefault(p["category"], []).append(p)
    out = "🤖 *NOVA* — commandes (prefixe « %s »)\n" % ctx.prefix
    for cat in sorted(cats):
        out += "\n*%s*\n" % cat
        for p in sorted(cats[cat], key=lambda x: x["name"]):
            out += "  %s%s — %s\n" % (ctx.prefix, p["name"], p["desc"])
    return out.rstrip()


@command("ping", desc="Teste la reactivite", category="General")
def _ping(ctx):
    return "🏓 pong"


@command("alive", desc="Statut + uptime", category="General", aliases=("uptime",))
def _alive(ctx):
    up = int(getattr(ctx, "uptime", 0) or 0)
    h, m, s = up // 3600, (up % 3600) // 60, up % 60
    return "✅ NOVA en ligne · uptime %dh %dm %ds · modele %s" % (h, m, s, ctx.settings.get("model"))


@command("id", desc="Affiche les identifiants", category="General")
def _id(ctx):
    canon = ns.send_recipient(ctx.chat_jid, ctx.lm)
    return "chat: %s\nsender: %s\nnumero: %s\ngroupe: %s" % (ctx.chat_jid, ctx.sender, canon.split("@")[0], ctx.is_group)


@command("owner", desc="Nom du proprietaire configure", category="General")
def _owner(ctx):
    return "👑 " + str(ctx.settings.get("owner_name"))


@command("runtime", desc="Infos techniques", category="General")
def _runtime(ctx):
    import platform
    return "🐍 Python %s · %s · modele %s" % (platform.python_version(), platform.system(), ctx.settings.get("model"))


# ======================= Automations (facon Levanter) =======================
def _chatkey(ctx):
    return ns.send_recipient(ctx.chat_jid, ctx.lm)


def _sudo_guard(ctx):
    return None if getattr(ctx, "is_sudo", False) else "⛔ reserve au proprietaire / sudo"


_VAR_MAP = {
    "prefix": "command_prefix", "owner_name": "owner_name", "owner": "owner_name", "model": "model",
    "history": "history_limit", "history_limit": "history_limit", "debounce": "debounce_seconds",
    "delay_min": "delay_min", "delay_max": "delay_max", "rate": "rate_per_hour", "rate_per_hour": "rate_per_hour",
    "poll": "poll_seconds", "start": "active_start", "end": "active_end", "transcript": "transcript_turns",
    "afk_cooldown": "afk_cooldown_min", "broadcast_limit": "broadcast_limit",
}


@command("set", desc="set <cle> <valeur> (config)", category="Automations")
def _setvar(ctx):
    g = _sudo_guard(ctx)
    if g:
        return g
    if len(ctx.args) < 2:
        return "usage: %sset <cle> <valeur>\ncles: %s" % (ctx.prefix, ", ".join(sorted(_VAR_MAP)))
    key = ctx.args[0].lower()
    if key not in _VAR_MAP:
        return "cle inconnue. cles: " + ", ".join(sorted(_VAR_MAP))
    real = _VAR_MAP[key]
    val = ctx.text.split(None, 1)[1]
    if real in ns._INT_KEYS:
        try:
            val = int(val)
        except Exception:
            return "valeur numerique attendue"
    ns.save_settings({real: val})
    return "✅ %s = %s" % (real, val)


@command("get", desc="get <cle>", category="Automations")
def _getvar(ctx):
    if not ctx.args:
        return "usage: %sget <cle>" % ctx.prefix
    real = _VAR_MAP.get(ctx.args[0].lower(), ctx.args[0].lower())
    s = ns.load_settings()
    return "%s = %s" % (real, s.get(real)) if real in s else "cle inconnue"


@command("vars", desc="Liste les reglages modifiables", category="Automations")
def _vars(ctx):
    s = ns.load_settings()
    out = "⚙️ vars (%sset <cle> <valeur>) :\n" % ctx.prefix
    for k in sorted(set(_VAR_MAP.values())):
        out += "  %s = %s\n" % (k, s.get(k))
    return out.rstrip()


@command("afk", desc="afk [raison] | afk off", category="Automations")
def _afk(ctx):
    g = _sudo_guard(ctx)
    if g:
        return g
    arg = (ctx.text or "").strip()
    if arg.lower() == "off":
        ns.save_settings({"afk": False})
        return "✅ AFK desactive"
    ns.save_settings({"afk": True, "afk_reason": arg})
    return "💤 AFK active" + ((" : " + arg) if arg else "")


@command("filter", desc="filter <declencheur> | <reponse>", category="Automations")
def _filter(ctx):
    g = _sudo_guard(ctx)
    if g:
        return g
    if "|" not in ctx.text:
        return "usage: %sfilter mot | reponse" % ctx.prefix
    trig, rep = ctx.text.split("|", 1)
    if not trig.strip() or not rep.strip():
        return "declencheur et reponse requis"
    ns.add_filter(_chatkey(ctx), trig.strip(), rep.strip())
    return "✅ filtre : « %s » -> « %s »" % (trig.strip(), rep.strip()[:40])


@command("gfilter", desc="Filtre GLOBAL: gfilter <decl> | <rep>", category="Automations")
def _gfilter(ctx):
    g = _sudo_guard(ctx)
    if g:
        return g
    if "|" not in ctx.text:
        return "usage: %sgfilter mot | reponse" % ctx.prefix
    trig, rep = ctx.text.split("|", 1)
    ns.add_filter(ns.GLOBAL_KEY, trig.strip(), rep.strip())
    return "✅ filtre global ajoute"


@command("filters", desc="Liste les filtres (chat + globaux)", category="Automations", aliases=("gfilters",))
def _filters(ctx):
    d = ns.list_filters(_chatkey(ctx))

    def fmt(lst):
        return "\n".join("  • %s -> %s" % (f.get("trigger"), (f.get("reply") or "")[:40]) for f in lst) or "  (aucun)"

    return "🧩 ce chat:\n" + fmt(d["chat"]) + "\n\n🌍 globaux:\n" + fmt(d["global"])


@command("stop", desc="Supprime un filtre: stop <declencheur>", category="Automations")
def _stopf(ctx):
    g = _sudo_guard(ctx)
    if g:
        return g
    if not ctx.text.strip():
        return "usage: %sstop <declencheur>" % ctx.prefix
    return "🗑 %d filtre(s) supprime(s)" % ns.remove_filter(_chatkey(ctx), ctx.text.strip())


@command("gstop", desc="Supprime un filtre global: gstop <decl>", category="Automations")
def _gstopf(ctx):
    g = _sudo_guard(ctx)
    if g:
        return g
    if not ctx.text.strip():
        return "usage: %sgstop <declencheur>" % ctx.prefix
    return "🗑 %d filtre(s) global(aux) supprime(s)" % ns.remove_filter(ns.GLOBAL_KEY, ctx.text.strip())


def _parse_duration(s):
    s = (s or "").strip().lower()
    m = re.match(r"^(\d{1,2}):(\d{2})$", s)
    if m:
        import datetime
        now = datetime.datetime.now()
        tgt = now.replace(hour=int(m.group(1)), minute=int(m.group(2)), second=0, microsecond=0)
        if tgt <= now:
            tgt += datetime.timedelta(days=1)
        return int((tgt - now).total_seconds())
    m = re.match(r"^(\d+)\s*([smhdj])$", s)
    if m:
        mult = {"s": 1, "m": 60, "h": 3600, "d": 86400, "j": 86400}[m.group(2)]
        return int(m.group(1)) * mult
    if s.isdigit():
        return int(s) * 60
    return None


@command("reminder", desc="reminder <duree> <msg> (10m/2h/HH:MM)", category="Automations", aliases=("schedule", "rappel"))
def _reminder(ctx):
    g = _sudo_guard(ctx)
    if g:
        return g
    if len(ctx.args) < 2:
        return "usage: %sreminder 10m prends tes medocs" % ctx.prefix
    secs = _parse_duration(ctx.args[0])
    if secs is None or secs <= 0 or secs > 60 * 60 * 24 * 30:
        return "duree invalide (ex: 90s, 10m, 2h, 1d, 14:30)"
    msg = ctx.text.split(None, 1)[1]
    rid = ns.add_reminder(ctx.chat_jid, int(time.time()) + secs, msg)
    return "⏰ rappel #%s dans %s" % (rid, ctx.args[0])


@command("reminders", desc="Liste les rappels programmes", category="Automations")
def _reminders(ctx):
    import datetime
    rem = ns.load_automations()["reminders"]
    if not rem:
        return "aucun rappel programme"
    out = "⏰ rappels:\n"
    for r in rem:
        t = datetime.datetime.fromtimestamp(r.get("due", 0)).strftime("%d/%m %H:%M")
        out += "  #%s @ %s — %s\n" % (r.get("id"), t, (r.get("message") or "")[:40])
    return out.rstrip()


@command("cancel", desc="Annule un rappel: cancel <id>", category="Automations")
def _cancel(ctx):
    g = _sudo_guard(ctx)
    if g:
        return g
    if not ctx.args:
        return "usage: %scancel <id>" % ctx.prefix
    return "🗑 %d rappel(s) annule(s)" % ns.cancel_reminder(ctx.args[0])


@command("sudo", desc="Liste les numeros sudo", category="Automations")
def _sudo(ctx):
    g = _sudo_guard(ctx)
    if g:
        return g
    s = ns.load_settings().get("sudo", [])
    return "👑 sudo: " + (", ".join(s) if s else "(aucun)")


@command("addsudo", desc="addsudo <numero>", category="Automations")
def _addsudo(ctx):
    g = _sudo_guard(ctx)
    if g:
        return g
    if not ctx.args:
        return "usage: %saddsudo <numero>" % ctx.prefix
    num = "".join(c for c in ctx.args[0] if c.isdigit())
    if not num:
        return "numero invalide"
    s = set(ns.load_settings().get("sudo", []))
    s.add(num)
    ns.save_settings({"sudo": sorted(s)})
    return "✅ %s ajoute aux sudo" % num


@command("delsudo", desc="delsudo <numero>", category="Automations")
def _delsudo(ctx):
    g = _sudo_guard(ctx)
    if g:
        return g
    if not ctx.args:
        return "usage: %sdelsudo <numero>" % ctx.prefix
    num = "".join(c for c in ctx.args[0] if c.isdigit())
    s = [x for x in ns.load_settings().get("sudo", []) if x != num]
    ns.save_settings({"sudo": s})
    return "🗑 %s retire des sudo" % num


@command("broadcast", desc="broadcast confirm <msg> (contacts actives)", category="Automations", aliases=("diffuser",))
def _broadcast(ctx):
    g = _sudo_guard(ctx)
    if g:
        return g
    text = ctx.text.strip()
    targets = ctx.enabled_contacts()
    limit = ctx.settings.get("broadcast_limit", 30)
    if not text:
        return "usage: %sbroadcast confirm <message>\n(envoi aux %d contacts actives, max %d, avec delai)" % (
            ctx.prefix, len(targets), limit)
    if not (ctx.args and ctx.args[0].lower() == "confirm"):
        return ("⚠️ Diffusion a %d contacts actives (max %d).\nPour confirmer :\n%sbroadcast confirm %s"
                % (min(len(targets), limit), limit, ctx.prefix, text))
    rest = text.split(None, 1)
    msg = rest[1] if len(rest) > 1 else ""
    if not msg:
        return "message vide apres 'confirm'"
    return "📣 diffuse a %d contacts" % ctx.broadcast(msg)


@command("tog", desc="tog <feature> on|off (filters/persona)", category="Automations", aliases=("toggle",))
def _tog(ctx):
    g = _sudo_guard(ctx)
    if g:
        return g
    if len(ctx.args) < 2 or ctx.args[1].lower() not in ("on", "off"):
        return "usage: %stog filters|persona|antidelete on|off" % ctx.prefix
    feat = ctx.args[0].lower()
    val = ctx.args[1].lower() == "on"
    key = _chatkey(ctx)
    if feat == "persona":
        ns.set_contact(key, {"enabled": val})
        return "🧬 persona %s ici" % ("ON" if val else "off")
    if feat in ("filters", "filtre", "filtres"):
        ns.set_toggle(key, "filters", val)
        return "🧩 filtres %s ici" % ("ON" if val else "off")
    if feat in ("antidelete", "antidel"):
        ns.set_toggle(key, "antidelete", val)
        return "🗑️ antidelete %s ici" % ("ON" if val else "off")
    return "features: filters, persona, antidelete"


# ======================= Levanter : parite maximale =======================
def _which(*names):
    for n in names:
        p = shutil.which(n)
        if p:
            return p
    return None


def _ff():
    return _which("ffmpeg")


def _im():
    return _which("magick", "convert")


def _run(cmd, timeout=120):
    try:
        p = subprocess.run(cmd, capture_output=True, timeout=timeout)
        if p.returncode != 0:
            return False, (p.stderr.decode("utf-8", "replace")[-180:] if p.stderr else "echec")
        return True, ""
    except Exception as e:
        return False, str(e)


def _tmp(ext):
    return str(Path(tempfile.gettempdir()) / ("nova_%d.%s" % (int(time.time() * 1000) % 100000000, ext)))


def _is_img(path):
    return (path or "").lower().rsplit(".", 1)[-1] in ("jpg", "jpeg", "png", "webp", "gif", "bmp")


# ---- IA : alias vers Ollama local ----
def _make_ai(nm):
    def h(ctx):
        if not ctx.text.strip():
            return "usage: %s%s <question>" % (ctx.prefix, nm)
        return ctx.ai(ctx.text) or "(pas de reponse du modele local)"
    return h


for _n in ("gpt", "gemini", "groq", "bing", "lydia", "openrouter"):
    register(_n, (), "IA locale (Ollama)", "IA", _make_ai(_n))


# ---- Texte : fancy ----
def _style(t, U, L, D=None):
    out = ""
    for c in t:
        if "A" <= c <= "Z":
            out += chr(U + ord(c) - 65)
        elif "a" <= c <= "z":
            out += chr(L + ord(c) - 97)
        elif D and "0" <= c <= "9":
            out += chr(D + ord(c) - 48)
        else:
            out += c
    return out


@command("fancy", desc="Polices stylees: fancy <texte>", category="Texte/Fun", aliases=("font",))
def _fancy(ctx):
    t = ctx.text.strip()
    if not t:
        return "usage: %sfancy <texte>" % ctx.prefix
    out = [
        _style(t, 0x1D400, 0x1D41A, 0x1D7CE),   # bold
        _style(t, 0x1D5D4, 0x1D5EE, 0x1D7EC),   # sans bold
        _style(t, 0x1D670, 0x1D68A, 0x1D7F6),   # monospace
        _style(t, 0x1D49C, 0x1D4B6),            # script
        _style(t, 0x24B6, 0x24D0),              # cercles
    ]
    return "\n".join(out)


# ---- Web : whois (RDAP) + news (RSS) ----
@command("whois", desc="whois <domaine>", category="Web")
def _whois(ctx):
    d = ctx.text.strip().lower()
    if not d:
        return "usage: %swhois <domaine>" % ctx.prefix
    try:
        j = _http_json("https://rdap.org/domain/" + _enc(d), timeout=9)
        ev = {e.get("eventAction"): e.get("eventDate", "")[:10] for e in j.get("events", [])}
        return "🌐 %s\nstatut: %s\ncree: %s · expire: %s" % (
            d, ", ".join(j.get("status", [])[:3]) or "?", ev.get("registration", "?"), ev.get("expiration", "?"))
    except Exception:
        return "domaine introuvable / RDAP indisponible"


@command("news", desc="Actus: news [sujet]", category="Web")
def _news(ctx):
    q = ctx.text.strip()
    url = ("https://news.google.com/rss/search?q=%s&hl=fr&gl=FR&ceid=FR:fr" % _enc(q)) if q \
        else "https://news.google.com/rss?hl=fr&gl=FR&ceid=FR:fr"
    try:
        xml = _http_get(url, timeout=9)
        titles = re.findall(r"<title>(.*?)</title>", xml, re.S)[1:7]
        titles = [_html.unescape(re.sub("<.*?>", "", t)).strip() for t in titles]
        titles = [t for t in titles if t]
        return "📰 actus:\n" + "\n".join("• " + t for t in titles) if titles else "aucune actu"
    except Exception:
        return "service actus indisponible"


# ---- General : jid / cinfo / save / task ----
@command("jid", desc="Affiche le jid du chat", category="General", aliases=("gjid",))
def _jid(ctx):
    return ctx.chat_jid


@command("cinfo", desc="Infos du chat courant", category="General")
def _cinfo(ctx):
    name = ""
    try:
        con = ns.db_connect()
        name = ns.chat_name(con, ctx.chat_jid)
        con.close()
    except Exception:
        pass
    return "💬 %s\njid: %s\ngroupe: %s" % (name, ctx.chat_jid, ctx.is_group)


@command("save", desc="Sauvegarde vers toi le dernier message", category="General", aliases=("keep",))
def _save(ctx):
    if not getattr(ctx, "owner_jid", None):
        return "disponible seulement quand TOI tu l'ecris"
    h = ctx.history(1)
    if not h:
        return "rien a sauvegarder"
    ctx.send_to(ctx.owner_jid, "💾 " + (h[-1]["content"] or ""))
    return "✅ sauvegarde"


@command("task", desc="task add <txt> | list | done <n> | clear", category="General", aliases=("todo",))
def _task(ctx):
    tf = ns.load_json("tasks.json", {})
    lst = tf.get("list", [])
    sub = ctx.args[0].lower() if ctx.args else "list"
    if sub == "add":
        parts = ctx.text.split(None, 1)
        if len(parts) < 2:
            return "usage: %stask add <texte>" % ctx.prefix
        lst.append(parts[1])
        tf["list"] = lst
        ns.save_json("tasks.json", tf)
        return "✅ tache #%d ajoutee" % len(lst)
    if sub == "done" and len(ctx.args) > 1 and ctx.args[1].isdigit():
        i = int(ctx.args[1]) - 1
        if 0 <= i < len(lst):
            r = lst.pop(i)
            tf["list"] = lst
            ns.save_json("tasks.json", tf)
            return "✔ fait: " + r
        return "numero invalide"
    if sub == "clear":
        tf["list"] = []
        ns.save_json("tasks.json", tf)
        return "🗑 taches videes"
    if not lst:
        return "📋 aucune tache"
    return "📋 taches:\n" + "\n".join("%d. %s" % (i + 1, t) for i, t in enumerate(lst))


# ---- Finance ----
def _fin():
    d = ns.load_json("finance.json", {"budget": 0, "entries": []})
    d.setdefault("budget", 0)
    d.setdefault("entries", [])
    return d


def _add_fin(ctx, kind):
    if not ctx.args or not re.match(r"^\d+(\.\d+)?$", ctx.args[0]):
        return "usage: %s%s <montant> [libelle]" % (ctx.prefix, kind)
    amt = float(ctx.args[0])
    parts = ctx.text.split(None, 1)
    label = parts[1] if len(parts) > 1 else ""
    d = _fin()
    d["entries"].append({"t": int(time.time()), "kind": kind, "amount": amt, "label": label})
    ns.save_json("finance.json", d)
    return "✅ %s %s %s" % (kind, amt, label)


@command("expense", desc="expense <montant> [libelle]", category="Finance", aliases=("depense",))
def _expense(ctx):
    return _add_fin(ctx, "expense")


@command("income", desc="income <montant> [libelle]", category="Finance", aliases=("revenu",))
def _income(ctx):
    return _add_fin(ctx, "income")


@command("budget", desc="budget [montant]", category="Finance")
def _budget(ctx):
    d = _fin()
    if ctx.args and re.match(r"^-?\d+(\.\d+)?$", ctx.args[0]):
        d["budget"] = float(ctx.args[0])
        ns.save_json("finance.json", d)
        return "💼 budget = %s" % d["budget"]
    dep = sum(e["amount"] for e in d["entries"] if e["kind"] == "expense")
    inc = sum(e["amount"] for e in d["entries"] if e["kind"] == "income")
    return "💼 budget: %s\ndepenses: %s · revenus: %s · solde: %s" % (d["budget"], dep, inc, d["budget"] + inc - dep)


@command("delbudget", desc="Reinitialise le budget", category="Finance")
def _delbudget(ctx):
    g = _sudo_guard(ctx)
    if g:
        return g
    ns.save_json("finance.json", {"budget": 0, "entries": []})
    return "🗑 budget reinitialise"


@command("histo", desc="Historique finances", category="Finance")
def _histo(ctx):
    d = _fin()
    if not d["entries"]:
        return "aucune operation"
    out = "📒 historique:\n"
    for e in d["entries"][-15:]:
        out += "%s %s%s %s\n" % (_dt.datetime.fromtimestamp(e["t"]).strftime("%d/%m"),
                                 "+" if e["kind"] == "income" else "-", e["amount"], e.get("label", ""))
    return out.rstrip()


# ---- Commandes custom ----
@command("setcmd", desc="setcmd <nom> <reponse>", category="Bot")
def _setcmd(ctx):
    g = _sudo_guard(ctx)
    if g:
        return g
    if len(ctx.args) < 2:
        return "usage: %ssetcmd <nom> <reponse>" % ctx.prefix
    nm = ctx.args[0].lower()
    if nm in _BY_NAME:
        return "nom reserve (commande existante)"
    cc = ns.load_json("customcmds.json", {})
    cc[nm] = ctx.text.split(None, 1)[1]
    ns.save_json("customcmds.json", cc)
    return "✅ commande %s%s creee" % (ctx.prefix, nm)


@command("getcmd", desc="getcmd <nom>", category="Bot")
def _getcmd(ctx):
    cc = ns.load_json("customcmds.json", {})
    return cc.get((ctx.args[0].lower() if ctx.args else ""), "commande custom introuvable")


@command("delcmd", desc="delcmd <nom>", category="Bot")
def _delcmd(ctx):
    g = _sudo_guard(ctx)
    if g:
        return g
    cc = ns.load_json("customcmds.json", {})
    nm = ctx.args[0].lower() if ctx.args else ""
    if nm in cc:
        del cc[nm]
        ns.save_json("customcmds.json", cc)
        return "🗑 %s supprimee" % nm
    return "introuvable"


@command("allcmd", desc="Liste les commandes custom", category="Bot")
def _allcmd(ctx):
    cc = ns.load_json("customcmds.json", {})
    return "commandes custom: " + (", ".join(sorted(cc)) if cc else "(aucune)")


# ---- Jeux ----
def _ttt_board(b):
    sym = {0: "▪️", 1: "❌", 2: "⭕"}
    return "\n".join(" ".join(sym[b[r * 3 + c]] for c in range(3)) for r in range(3))


def _ttt_win(b, p):
    L = [(0, 1, 2), (3, 4, 5), (6, 7, 8), (0, 3, 6), (1, 4, 7), (2, 5, 8), (0, 4, 8), (2, 4, 6)]
    return any(all(b[x] == p for x in line) for line in L)


@command("tictactoe", desc="Morpion: tictactoe start | <1-9>", category="Jeux", aliases=("ttt", "morpion"))
def _ttt(ctx):
    g = ns.load_json("games.json", {})
    gk = "ttt:" + ctx.chat_jid
    st = g.get(gk)
    a0 = ctx.args[0].lower() if ctx.args else ""
    if not st or a0 in ("start", "new"):
        st = {"b": [0] * 9}
        g[gk] = st
        ns.save_json("games.json", g)
        return "🎮 Morpion ! tu es ❌. joue %sttt <1-9>\n%s" % (ctx.prefix, _ttt_board(st["b"]))
    if not a0.isdigit():
        return "joue un numero 1-9 (ou %sttt start)" % ctx.prefix
    i = int(a0) - 1
    if i < 0 or i > 8 or st["b"][i] != 0:
        return "case invalide"
    st["b"][i] = 1
    if _ttt_win(st["b"], 1):
        g.pop(gk, None)
        ns.save_json("games.json", g)
        return "🎉 tu gagnes !\n" + _ttt_board(st["b"])
    empty = [x for x in range(9) if st["b"][x] == 0]
    if not empty:
        g.pop(gk, None)
        ns.save_json("games.json", g)
        return "🤝 match nul\n" + _ttt_board(st["b"])
    st["b"][random.choice(empty)] = 2
    g[gk] = st
    ns.save_json("games.json", g)
    if _ttt_win(st["b"], 2):
        g.pop(gk, None)
        ns.save_json("games.json", g)
        return "😈 je gagne !\n" + _ttt_board(st["b"])
    return _ttt_board(st["b"]) + "\n%sttt <1-9>" % ctx.prefix


@command("wcg", desc="Word chain: wcg start | <mot>", category="Jeux")
def _wcg(ctx):
    g = ns.load_json("games.json", {})
    gk = "wcg:" + ctx.chat_jid
    st = g.get(gk)
    w = ctx.text.strip().lower()
    if not w or w in ("start", "new"):
        start = random.choice(["chat", "maison", "soleil", "pomme", "arbre", "livre"])
        g[gk] = {"last": start[-1], "used": [start]}
        ns.save_json("games.json", g)
        return "🔤 Word Chain ! mot: *%s* — un mot commencant par « %s »" % (start, start[-1])
    if not st:
        return "commence: %swcg start" % ctx.prefix
    if not w.isalpha():
        return "un seul mot (lettres)"
    if w[0] != st["last"]:
        return "doit commencer par « %s »" % st["last"]
    if w in st["used"]:
        return "deja utilise"
    st["used"].append(w)
    st["last"] = w[-1]
    g[gk] = st
    ns.save_json("games.json", g)
    return "✅ ok ! prochain mot en « %s » (%d joues)" % (w[-1], len(st["used"]))


# ---- Groupe : infos / tag / list / msgs / inactive ----
def _group_only(ctx):
    return None if ctx.is_group else "commande de groupe uniquement"


def _group_info(jid):
    try:
        return _http_json(_bridge_base() + "/api/group?jid=" + _enc(jid), timeout=12)
    except Exception as e:
        return {"success": False, "error": str(e)}


def _tag_members(ctx, filt):
    g = _group_only(ctx)
    if g:
        return g
    info = _group_info(ctx.chat_jid)
    if not info.get("success"):
        nums = ctx.participants()
        if not nums:
            return "participants indisponibles (%s)" % info.get("error", "")
        txt = (ctx.text.strip() + "\n" if ctx.text.strip() else "") + "\n".join("%d. @%s" % (i + 1, n) for i, n in enumerate(nums))
        if getattr(ctx, "dry", False):
            return "[DRY tag] %d (fallback)" % len(nums)
        ctx.send_mentions(ctx.chat_jid, txt, [n + "@s.whatsapp.net" for n in nums])
        return None
    members = info.get("participants", [])
    if filt == "admins":
        members = [m for m in members if m.get("admin")]
    elif filt == "notadmins":
        members = [m for m in members if not m.get("admin")]
    if not members:
        return "aucun membre"
    lines, mentions = [], []
    for i, m in enumerate(members, 1):
        lines.append("%d. @%s" % (i, m.get("phone") or m.get("user")))
        mentions.append(m.get("jid"))
    if getattr(ctx, "dry", False):
        return "[DRY tag %s] %d membres" % (filt, len(members))
    ctx.send_mentions(ctx.chat_jid, "\n".join(lines), mentions)
    return None


@command("tag", desc="tag all|admins|notadmins | <message cache>", category="Groupe")
def _tag(ctx):
    g = _group_only(ctx)
    if g:
        return g
    sub = ctx.args[0].lower() if ctx.args else "all"
    if sub in ("all", "admins", "notadmins"):
        return _tag_members(ctx, sub)
    # tag cache : mentionne tout le monde, affiche seulement le message
    info = _group_info(ctx.chat_jid)
    if not info.get("success"):
        return "🚫 infos groupe indispo: " + info.get("error", "")
    mentions = [m.get("jid") for m in info.get("participants", [])]
    if getattr(ctx, "dry", False):
        return "[DRY tag cache] %d mentions" % len(mentions)
    ctx.send_mentions(ctx.chat_jid, ctx.text.strip(), mentions)
    return None


@command("ginfo", desc="Infos du groupe", category="Groupe")
def _ginfo(ctx):
    g = _group_only(ctx)
    if g:
        return g
    info = _group_info(ctx.chat_jid)
    if not info.get("success"):
        return "🚫 " + info.get("error", "indispo")
    admins = sum(1 for m in info.get("participants", []) if m.get("admin"))
    return "👥 %s\nmembres: %d · admins: %d\njid: %s" % (info.get("name", ""), info.get("count", 0), admins, ctx.chat_jid)


@command("list", desc="Liste les membres du groupe", category="Groupe")
def _list(ctx):
    g = _group_only(ctx)
    if g:
        return g
    info = _group_info(ctx.chat_jid)
    if not info.get("success"):
        return "🚫 " + info.get("error", "indispo")
    ms = info.get("participants", [])
    return "👥 %d membres:\n" % len(ms) + "\n".join(
        "%d. %s%s" % (i + 1, m.get("phone") or m.get("user"), " 👑" if m.get("admin") else "") for i, m in enumerate(ms[:200]))


@command("msgs", desc="Nombre de messages par membre (groupe)", category="Groupe")
def _msgs(ctx):
    g = _group_only(ctx)
    if g:
        return g
    try:
        con = ns.db_connect()
        rows = con.execute("SELECT sender, COUNT(*) c FROM messages WHERE chat_jid=? AND sender<>'' "
                           "GROUP BY sender ORDER BY c DESC LIMIT 15", (ctx.chat_jid,)).fetchall()
        con.close()
    except Exception as e:
        return "indispo (%s)" % e
    if not rows:
        return "aucun message compte"
    return "📊 messages:\n" + "\n".join("%s : %d" % (r["sender"].split("@")[0], r["c"]) for r in rows)


@command("inactive", desc="Membres sans message (selon la base)", category="Groupe")
def _inactive(ctx):
    g = _group_only(ctx)
    if g:
        return g
    info = _group_info(ctx.chat_jid)
    if not info.get("success"):
        return "🚫 " + info.get("error", "indispo")
    try:
        con = ns.db_connect()
        active = set((r["sender"] or "").split("@")[0].split(":")[0]
                     for r in con.execute("SELECT DISTINCT sender FROM messages WHERE chat_jid=? AND sender<>''", (ctx.chat_jid,)).fetchall())
        con.close()
    except Exception:
        active = set()
    inact = [m for m in info.get("participants", []) if (m.get("phone") or m.get("user")) not in active and m.get("user") not in active]
    if not inact:
        return "✅ tout le monde a parle (selon la base)"
    return "😴 inactifs (%d):\n" % len(inact) + "\n".join("• " + (m.get("phone") or m.get("user")) for m in inact[:50])


@command("remove", desc="Expulse (alias kick): remove <num...>", category="Groupe")
def _remove(ctx):
    return _group_action(ctx, "kick")


# ---- Groupe : moderation (config + warn) ----
def _modtoggle(ctx, feat, emoji):
    g = _grp_guard(ctx)
    if g:
        return g
    if not ctx.args or ctx.args[0].lower() not in ("on", "off"):
        return "usage: %s%s on|off" % (ctx.prefix, feat)
    ns.set_toggle(_chatkey(ctx), feat, ctx.args[0].lower() == "on")
    return "%s %s %s ici" % (emoji, feat, ctx.args[0].lower())


@command("antilink", desc="antilink on|off (supprime/averti les liens)", category="Groupe")
def _antilink(ctx):
    return _modtoggle(ctx, "antilink", "🔗")


@command("antispam", desc="antispam on|off (anti-flood)", category="Groupe")
def _antispam(ctx):
    return _modtoggle(ctx, "antispam", "🛑")


@command("antifake", desc="antifake on|off (numeros suspects)", category="Groupe")
def _antifake(ctx):
    return _modtoggle(ctx, "antifake", "🌍")


@command("antiword", desc="antiword on|off | add <mot> | del <mot>", category="Groupe")
def _antiword(ctx):
    g = _grp_guard(ctx)
    if g:
        return g
    sub = ctx.args[0].lower() if ctx.args else ""
    if sub in ("on", "off"):
        ns.set_toggle(_chatkey(ctx), "antiword", sub == "on")
        return "🚯 antiword %s ici" % sub
    if sub == "add" and len(ctx.args) > 1:
        w = list(set((ns.load_settings().get("antiword_list", []) or []) + [ctx.args[1].lower()]))
        ns.save_settings({"antiword_list": w})
        return "mot banni ajoute"
    if sub == "del" and len(ctx.args) > 1:
        w = [x for x in (ns.load_settings().get("antiword_list", []) or []) if x != ctx.args[1].lower()]
        ns.save_settings({"antiword_list": w})
        return "mot retire"
    return "usage: %santiword on|off | add <mot> | del <mot>" % ctx.prefix


@command("pdm", desc="pdm on|off (annonce promote/demote)", category="Groupe")
def _pdm(ctx):
    return _modtoggle(ctx, "pdm", "📣")


def _warn_key(ctx):
    return ns.send_recipient(ctx.chat_jid, ctx.lm)


@command("warn", desc="Avertit un membre: warn <num> [raison]", category="Groupe")
def _warn(ctx):
    g = _grp_guard(ctx)
    if g:
        return g
    if not ctx.args:
        return "usage: %swarn <numero> [raison]" % ctx.prefix
    num = "".join(c for c in ctx.args[0] if c.isdigit())
    if not num:
        return "numero invalide"
    w = ns.load_json("warns.json", {})
    key = _warn_key(ctx)
    wd = w.setdefault(key, {})
    wd[num] = wd.get(num, 0) + 1
    limit = int(ctx.settings.get("warn_limit", 3))
    if wd[num] >= limit:
        wd[num] = 0
        ns.save_json("warns.json", w)
        if not getattr(ctx, "dry", False):
            _bridge_post("/api/group-action", {"jid": ctx.chat_jid, "action": "kick", "participants": [num]})
        return "🚫 @%s a atteint %d avertissements → expulse" % (num, limit)
    ns.save_json("warns.json", w)
    return "⚠️ @%s averti (%d/%d)" % (num, wd[num], limit)


@command("wrg", desc="Retire un avertissement: wrg <num>", category="Groupe", aliases=("unwarn",))
def _wrg(ctx):
    g = _grp_guard(ctx)
    if g:
        return g
    if not ctx.args:
        return "usage: %swrg <numero>" % ctx.prefix
    num = "".join(c for c in ctx.args[0] if c.isdigit())
    w = ns.load_json("warns.json", {})
    wd = w.get(_warn_key(ctx), {})
    if wd.get(num, 0) > 0:
        wd[num] -= 1
        ns.save_json("warns.json", w)
        return "✅ 1 avertissement retire a @%s (%d)" % (num, wd[num])
    return "aucun avertissement"


@command("getgreet", desc="Affiche welcome/goodbye du groupe", category="Groupe")
def _getgreet(ctx):
    g = _group_only(ctx)
    if g:
        return g
    a = ns.load_automations()
    w = ns.get_greet(a, "welcome", ctx.chat_jid)
    gb = ns.get_greet(a, "goodbye", ctx.chat_jid)
    return "👋 welcome: %s | %s\n🚪 goodbye: %s | %s" % (
        "on" if w.get("on") else "off", w.get("msg", "-") or "-",
        "on" if gb.get("on") else "off", gb.get("msg", "-") or "-")


@command("delgreet", desc="Desactive welcome & goodbye (groupe)", category="Groupe")
def _delgreet(ctx):
    g = _grp_guard(ctx)
    if g:
        return g
    ns.set_greet("welcome", ctx.chat_jid, on=False)
    ns.set_greet("goodbye", ctx.chat_jid, on=False)
    return "🗑 greetings desactives"


# ---- Config comportement ----
@command("mention", desc="mention on|off (auto-mention)", category="Bot")
def _mentioncfg(ctx):
    g = _sudo_guard(ctx)
    if g:
        return g
    if not ctx.args or ctx.args[0].lower() not in ("on", "off"):
        return "usage: %smention on|off" % ctx.prefix
    ns.save_settings({"auto_mention": ctx.args[0].lower() == "on"})
    return "auto-mention %s" % ctx.args[0].lower()


@command("creact", desc="creact on|off (reagir aux commandes)", category="Bot")
def _creact(ctx):
    g = _sudo_guard(ctx)
    if g:
        return g
    if not ctx.args or ctx.args[0].lower() not in ("on", "off"):
        return "usage: %screact on|off" % ctx.prefix
    ns.save_settings({"cmd_reaction": ctx.args[0].lower() == "on"})
    return "cmd-reaction %s" % ctx.args[0].lower()


@command("reset", desc="Reinitialise TOUS les reglages (owner)", category="Bot")
def _reset(ctx):
    g = _sudo_guard(ctx)
    if g:
        return g
    ns.save_settings(dict(ns.DEFAULT_SETTINGS))
    return "♻️ reglages reinitialises"


@command("delvar", desc="Reinitialise une var: delvar <cle>", category="Automations")
def _delvar(ctx):
    g = _sudo_guard(ctx)
    if g:
        return g
    if not ctx.args:
        return "usage: %sdelvar <cle>" % ctx.prefix
    real = _VAR_MAP.get(ctx.args[0].lower(), ctx.args[0].lower())
    if real in ns.DEFAULT_SETTINGS:
        ns.save_settings({real: ns.DEFAULT_SETTINGS[real]})
        return "♻️ %s reinitialise" % real
    return "cle inconnue"


# ---- Medias : audio fx (ffmpeg) ----
def _audio_fx(ctx, af, label):
    if getattr(ctx, "dry", False):
        return "[DRY] %s (dernier audio/video)" % label
    if _ff() is None:
        return "ffmpeg absent"
    path, err = ctx.download_last(("audio", "video"))
    if not path:
        return "🚫 " + err
    out = _tmp("mp3")
    ok, e = _run([_ff(), "-y", "-i", path, "-af", af, "-vn", "-acodec", "libmp3lame", out])
    if not ok:
        return "🚫 %s: %s" % (label, e)
    ok2, _m = ctx.send_media(out)
    return None if ok2 else "echec envoi"


@command("bass", desc="Boost des basses (dernier audio)", category="Medias")
def _bass(ctx):
    return _audio_fx(ctx, "bass=g=15", "bass")


@command("treble", desc="Boost des aigus (dernier audio)", category="Medias")
def _treble(ctx):
    return _audio_fx(ctx, "treble=g=12", "treble")


@command("pitch", desc="Monte le pitch (dernier audio)", category="Medias")
def _pitch(ctx):
    return _audio_fx(ctx, "asetrate=44100*1.3,aresample=44100,atempo=0.77", "pitch")


# ---- Medias : video ffmpeg ----
@command("rotate", desc="Pivote le dernier media 90deg", category="Medias")
def _rotate(ctx):
    if getattr(ctx, "dry", False):
        return "[DRY] rotate"
    path, err = ctx.download_last(("image", "video"))
    if not path:
        return "🚫 " + err
    if _is_img(path):
        im = _im()
        if not im:
            return "ImageMagick absent"
        out = _tmp("png")
        ok, e = _run([im, path, "-rotate", "90", out])
    else:
        ff = _ff()
        if not ff:
            return "ffmpeg absent"
        out = _tmp("mp4")
        ok, e = _run([ff, "-y", "-i", path, "-vf", "transpose=1", out])
    if not ok:
        return "🚫 rotate: " + e
    ok2, _m = ctx.send_media(out)
    return None if ok2 else "echec"


@command("trim", desc="Garde les N premieres sec (defaut 30): trim [sec]", category="Medias", aliases=("cut",))
def _trim(ctx):
    if getattr(ctx, "dry", False):
        return "[DRY] trim"
    ff = _ff()
    if not ff:
        return "ffmpeg absent"
    secs = ctx.args[0] if (ctx.args and ctx.args[0].isdigit()) else "30"
    path, err = ctx.download_last(("video", "audio"))
    if not path:
        return "🚫 " + err
    ext = "mp4" if not _is_img(path) else "mp4"
    out = _tmp(ext)
    ok, e = _run([ff, "-y", "-i", path, "-t", secs, "-c", "copy", out])
    if not ok:  # fallback re-encode
        ok, e = _run([ff, "-y", "-i", path, "-t", secs, out])
    if not ok:
        return "🚫 trim: " + e
    ok2, _m = ctx.send_media(out)
    return None if ok2 else "echec"


@command("compress", desc="Compresse la derniere video", category="Medias")
def _compress(ctx):
    if getattr(ctx, "dry", False):
        return "[DRY] compress"
    ff = _ff()
    if not ff:
        return "ffmpeg absent"
    path, err = ctx.download_last(("video",))
    if not path:
        return "🚫 " + err
    out = _tmp("mp4")
    ok, e = _run([ff, "-y", "-i", path, "-vcodec", "libx264", "-crf", "30", "-preset", "veryfast", "-acodec", "aac", "-b:a", "96k", out])
    if not ok:
        return "🚫 compress: " + e
    ok2, _m = ctx.send_media(out)
    return None if ok2 else "echec"


@command("crop", desc="Recadre (centre) le dernier media", category="Medias")
def _crop(ctx):
    if getattr(ctx, "dry", False):
        return "[DRY] crop"
    path, err = ctx.download_last(("image", "video"))
    if not path:
        return "🚫 " + err
    if _is_img(path):
        im = _im()
        if not im:
            return "ImageMagick absent"
        out = _tmp("png")
        ok, e = _run([im, path, "-gravity", "center", "-crop", "80%x80%+0+0", "+repage", out])
    else:
        ff = _ff()
        if not ff:
            return "ffmpeg absent"
        out = _tmp("mp4")
        ok, e = _run([ff, "-y", "-i", path, "-vf", "crop=in_w*0.8:in_h*0.8", out])
    if not ok:
        return "🚫 crop: " + e
    ok2, _m = ctx.send_media(out)
    return None if ok2 else "echec"


@command("take", desc="Sticker depuis la derniere image", category="Medias", aliases=("exif",))
def _take(ctx):
    ok, msg = ctx.sticker()
    return None if ok else "🚫 sticker indisponible (%s)" % msg


# ---- Medias : effets image (ImageMagick) ----
def _image_simple(ctx, opts, label):
    if getattr(ctx, "dry", False):
        return "[DRY] %s" % label
    im = _im()
    if not im:
        return "ImageMagick absent"
    path, err = ctx.download_last(("image",))
    if not path:
        return "🚫 " + err
    out = _tmp("png")
    ok, e = _run([im, path] + opts + [out])
    if not ok:
        return "🚫 %s: %s" % (label, e)
    ok2, _m = ctx.send_media(out)
    return None if ok2 else "echec"


@command("black", desc="Image en noir et blanc", category="Medias", aliases=("bw", "grayscale"))
def _black(ctx):
    return _image_simple(ctx, ["-colorspace", "Gray"], "black")


@command("dark", desc="Assombrit l'image", category="Medias")
def _dark(ctx):
    return _image_simple(ctx, ["-brightness-contrast", "-30x0"], "dark")


@command("low", desc="Basse lumiere", category="Medias")
def _low(ctx):
    return _image_simple(ctx, ["-brightness-contrast", "-50x-10"], "low")


@command("sketch", desc="Effet croquis", category="Medias")
def _sketch(ctx):
    return _image_simple(ctx, ["-colorspace", "Gray", "-sketch", "0x10+120"], "sketch")


@command("pencil", desc="Effet crayon", category="Medias", aliases=("charcoal",))
def _pencil(ctx):
    return _image_simple(ctx, ["-colorspace", "Gray", "-charcoal", "2"], "pencil")


@command("bokeh", desc="Flou artistique", category="Medias", aliases=("blur",))
def _bokeh(ctx):
    return _image_simple(ctx, ["-blur", "0x8"], "bokeh")


@command("cartoon", desc="Effet cartoon", category="Medias")
def _cartoon(ctx):
    return _image_simple(ctx, ["-colors", "16", "+dither", "-paint", "3"], "cartoon")


@command("enhance", desc="Ameliore nettete/contraste", category="Medias", aliases=("hd",))
def _enhance(ctx):
    return _image_simple(ctx, ["-sharpen", "0x1.4", "-modulate", "110,120", "-contrast"], "enhance")


@command("circle", desc="Decoupe l'image en cercle", category="Medias")
def _circle(ctx):
    return _image_simple(ctx, ["-alpha", "set", "-background", "none", "-vignette", "0x15"], "circle")


@command("pdf", desc="Derniere image -> PDF", category="Medias")
def _pdf(ctx):
    if getattr(ctx, "dry", False):
        return "[DRY] pdf"
    im = _im()
    if not im:
        return "ImageMagick absent"
    path, err = ctx.download_last(("image",))
    if not path:
        return "🚫 " + err
    out = _tmp("pdf")
    ok, e = _run([im, path, out])
    if not ok:
        return "🚫 pdf: " + e
    ok2, _m = ctx.send_media(out)
    return None if ok2 else "echec"


@command("color", desc="Couleur moyenne de la derniere image", category="Medias")
def _color(ctx):
    im = _im()
    if not im:
        return "ImageMagick absent"
    path, err = ctx.download_last(("image",))
    if not path:
        return "🚫 " + err
    try:
        p = subprocess.run([im, path, "-resize", "1x1", "txt:-"], capture_output=True, timeout=30)
        m = re.search(r"#([0-9A-Fa-f]{6})", p.stdout.decode("utf-8", "replace"))
        return "🎨 couleur moyenne : #" + m.group(1) if m else "indisponible"
    except Exception as e:
        return "indisponible (%s)" % e


# ---- TTS (Windows SAPI, local) ----
@command("tts", desc="Synthese vocale: tts <texte>", category="Medias", aliases=("say", "voice"))
def _tts(ctx):
    txt = ctx.text.strip()
    if not txt:
        return "usage: %stts <texte>" % ctx.prefix
    if getattr(ctx, "dry", False):
        return "[DRY] tts: " + txt[:40]
    ps = _which("powershell", "pwsh")
    if not ps:
        return "🔧 PowerShell requis (TTS Windows)"
    wav = _tmp("wav")
    script = ("Add-Type -AssemblyName System.Speech; "
              "$s=New-Object System.Speech.Synthesis.SpeechSynthesizer; "
              "$s.SetOutputToWaveFile('%s'); $s.Speak([Console]::In.ReadToEnd()); $s.Dispose()") % wav.replace("'", "''")
    try:
        subprocess.run([ps, "-NoProfile", "-Command", script], input=txt.encode("utf-8"), capture_output=True, timeout=60)
    except Exception as e:
        return "🚫 tts: " + str(e)
    if not os.path.exists(wav):
        return "🚫 tts indisponible"
    out = wav
    if _ff():
        mp3 = _tmp("mp3")
        ok, _e = _run([_ff(), "-y", "-i", wav, mp3])
        if ok:
            out = mp3
    ok2, _m = ctx.send_media(out)
    return None if ok2 else "echec envoi"


# ---- Downloaders (yt-dlp via python -m yt_dlp) ----
def _ytdlp_cmd():
    return [sys.executable, "-m", "yt_dlp"]


def _ytdlp_ok():
    try:
        p = subprocess.run(_ytdlp_cmd() + ["--version"], capture_output=True, timeout=20)
        return p.returncode == 0
    except Exception:
        return False


def _download_url(ctx, kind="video", query=None):
    src = query if query else ctx.text.strip()
    if not src:
        return "usage: %s%s <url ou recherche>" % (ctx.prefix, ctx.command)
    if getattr(ctx, "dry", False):
        return "[DRY] telechargerait (%s): %s" % (kind, src[:60])
    if not _ytdlp_ok():
        return "🔧 yt-dlp requis (python -m yt_dlp)"
    d = tempfile.mkdtemp(prefix="novadl_")
    outtmpl = os.path.join(d, "%(title).50s.%(ext)s")
    cmd = _ytdlp_cmd() + ["--no-playlist", "--no-warnings", "--max-filesize", "80M", "-o", outtmpl]
    if kind == "audio":
        cmd += ["-x", "--audio-format", "mp3"]
    else:
        cmd += ["-f", "mp4/bv*+ba/best", "--merge-output-format", "mp4"]
    cmd += [src]
    ok, e = _run(cmd, timeout=300)
    files = [os.path.join(d, f) for f in os.listdir(d)] if os.path.isdir(d) else []
    files = [f for f in files if os.path.isfile(f)]
    if not files:
        shutil.rmtree(d, ignore_errors=True)
        return "🚫 echec telechargement" + ((" (" + e[:90] + ")") if e else "")
    f = max(files, key=os.path.getsize)
    ok2, msg = ctx.send_media(f)
    shutil.rmtree(d, ignore_errors=True)
    return None if ok2 else "🚫 echec envoi: " + str(msg)


def _yt_dispatch(ctx, kind):
    t = ctx.text.strip()
    if not t:
        return "usage: %s%s <url ou recherche>" % (ctx.prefix, ctx.command)
    if t.startswith("http"):
        return _download_url(ctx, kind)
    return _download_url(ctx, kind, query="ytsearch1:" + t)


def _dl_video(ctx):
    return _download_url(ctx, "video")


def _dl_audio(ctx):
    return _download_url(ctx, "audio")


for _n in ("video", "mp4", "insta", "instagram", "tiktok", "fb", "facebook", "twitter",
           "reddit", "pinterest", "story", "movie", "dl"):
    register(_n, (), "Telecharge une video (yt-dlp): " + _n + " <url>", "Download", _dl_video)
for _n in ("song", "spotify", "yta"):
    register(_n, (), "Telecharge l'audio (yt-dlp): " + _n + " <url/recherche>", "Download", _dl_audio)
register("yt", (), "YouTube (yt-dlp): yt <url/recherche>", "Download", lambda ctx: _yt_dispatch(ctx, "video"))
register("ytv", (), "YouTube video (yt-dlp)", "Download", lambda ctx: _yt_dispatch(ctx, "video"))
register("yts", (), "Recherche YouTube (yt-dlp)", "Download", lambda ctx: _yt_dispatch(ctx, "video"))
register("img", (), "Recherche d'image (besoin API)", "Download", lambda ctx: "🔧 recherche d'image : besoin d'une API")
register("apk", (), "APK (besoin source/API)", "Download", lambda ctx: "🔧 apk : besoin d'une source/API")
register("mediafire", (), "Mediafire (besoin scrape)", "Download", lambda ctx: "🔧 mediafire : non supporte (scrape requis)")


# ---- Alias Levanter ----
register("allvar", (), "Liste les reglages (alias vars)", "Automations", _vars)
register("setvar", (), "Change un reglage (alias set)", "Automations", _setvar)
register("getvar", (), "Lit un reglage (alias get)", "Automations", _getvar)
register("amute", (), "Mute le groupe (alias mute)", "Groupe", _mute)
register("aunmute", (), "Unmute le groupe (alias unmute)", "Groupe", _unmute)
register("gandm", (), "Liste des membres (alias list)", "Groupe", _list)
register("plugin", (), "Liste des plugins (alias plugins)", "Bot", _plugins)
register("vote", (), "Sondage (alias poll)", "Groupe", _poll)
register("url", (), "Raccourcir une url (alias raccourci)", "Web", _raccourci)
register("trt", (), "Traduire (alias tr)", "IA", _tr)
register("summary", (), "Resume la conversation (alias sum)", "IA", _sum)
register("avm", (), "Media -> audio (alias tomp3)", "Medias", _tomp3)
register("mp3", (), "Dernier media -> mp3 (reply)", "Medias", _tomp3)
register("setgreet", (), "Configure welcome (alias welcome)", "Groupe", _welcome)
register("setschedule", (), "Programme un rappel (alias reminder)", "Automations", _reminder)
register("getschedule", (), "Liste les rappels (alias reminders)", "Automations", _reminders)
register("delschedule", (), "Annule un rappel (alias cancel)", "Automations", _cancel)
register("pfilter", (), "Filtre (alias filter)", "Automations", _filter)
register("pstop", (), "Supprime un filtre (alias stop)", "Automations", _stopf)


# ---- objet contexte (rempli par brain.py) ----
class Ctx:
    def __init__(self, **kw):
        self.__dict__.update(kw)
