# -*- coding: utf-8 -*-
"""
NOVA sur whatsmeow — le cerveau.
Surveille la base du bridge whatsmeow (messages.db, lecture seule). Pour chaque
nouveau message prive recu dans une discussion ACTIVEE, repond A TA PLACE, dans
ton style appris de tout votre historique (via Ollama local), puis envoie la
reponse par l'API du bridge.

Fonctions : clone de style, resolution @lid<->numero, reponse au dernier message
non-repondu au demarrage, delai humain, plage horaire active, mode vacances,
limite de debit par contact, mot-cle STOP, reglages par contact, pause live,
statistiques. Les reglages sont lus en direct depuis settings.json.

Lancement :
  python brain.py            # mode reel (envoie les reponses)
  python brain.py --dry-run  # n'envoie rien, affiche ce qu'il repondrait
  python brain.py --contacts # liste tes discussions privees + leur jid
  python brain.py --selftest # genere une reponse de test (sans envoi)
"""
import json
import os
import random
import re
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.request
from datetime import datetime, timezone, timedelta

import novastore as ns
import plugins

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

SYSTEM_TMPL = (
    "Tu ES {owner} qui texte sur WhatsApp avec {contact}. Tu n'imites pas : tu es lui.\n"
    "Regle absolue : ecris EXACTEMENT comme dans les exemples de TES messages ci-dessous.\n"
    "- messages TRES courts (souvent 2 a 6 mots, une seule ligne), comme un vrai SMS\n"
    "- garde SA casse (minuscules si il ecrit en minuscules), son argot et ses abreviations "
    "(wsh, tkt, jpp, mdr, ptdr, slt, pk, stp, bcp, jsp, dsl, grv...), ses fautes et raccourcis\n"
    "- ponctuation minimale, pas de majuscule automatique en debut de phrase si ce n'est pas son habitude\n"
    "- memes emojis que lui (ni plus ni moins), places comme lui\n"
    "INTERDIT (ca te trahit direct) : le francais scolaire ou poli, les phrases propres et completes, "
    "'Bonjour'/'Salut, comment vas-tu ?'/'Je suis la pour...', les reponses longues, le vouvoiement si il tutoie, "
    "tout ton serviable ou formel.\n"
    "Reponds dans le fil de la conversation. Ne dis JAMAIS que tu es une IA. "
    "Donne SEULEMENT le message a envoyer, rien d'autre.\n\n"
    "=== Exemples reels de TES messages (copie ce style, cette longueur, ces emojis) ===\n{samples}"
)

STOP_WORDS = {"stop", "stopp", "arrete", "arrête", "unsubscribe", "desabonner", "désabonner"}


# ---------------- generation ----------------
def get_owner_samples(con, jids, n=14):
    jids = [jids] if isinstance(jids, str) else list(jids)
    out, seen = [], set()

    def collect(rows):
        for r in rows:
            t = (r["content"] or "").strip()
            if not t or t.lower() in seen or t.startswith("http"):
                continue
            seen.add(t.lower())
            out.append(t)
            if len(out) >= n:
                return True
        return False

    try:
        done = False
        if jids:
            ph = ",".join("?" for _ in jids)
            done = collect(con.execute(
                "SELECT content FROM messages WHERE chat_jid IN (%s) AND is_from_me=1 AND content<>'' "
                "ORDER BY timestamp DESC LIMIT 60" % ph, tuple(jids)).fetchall())
        if not done and len(out) < n:
            collect(con.execute(
                "SELECT content FROM messages WHERE is_from_me=1 AND content<>'' "
                "ORDER BY timestamp DESC LIMIT 300").fetchall())
    except Exception:
        pass
    return out[:n]


def build_history(con, jids, limit):
    jids = [jids] if isinstance(jids, str) else list(jids)
    if not jids:
        return []
    ph = ",".join("?" for _ in jids)
    rows = con.execute(
        "SELECT content, is_from_me FROM messages "
        "WHERE chat_jid IN (%s) AND content <> '' ORDER BY timestamp ASC" % ph,
        tuple(jids),
    ).fetchall()
    rows = rows[-limit:]
    messages = []
    for r in rows:
        role = "assistant" if r["is_from_me"] else "user"
        txt = r["content"]
        if not txt:
            continue
        if messages and messages[-1]["role"] == role:
            messages[-1]["content"] += "\n" + txt
        else:
            messages.append({"role": role, "content": txt})
    while messages and messages[0]["role"] != "user":
        messages.pop(0)
    return messages


def groq_reply(system, messages, model, max_tokens=200):
    key = ns.groq_api_key()
    if not key:
        return None
    payload = {
        "model": model or ns.groq_model(),
        "messages": [{"role": "system", "content": system}] + messages,
        "temperature": 0.95,
        "max_tokens": max_tokens,
        "stream": False,
    }
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        ns.groq_url() + "/chat/completions",
        data=data,
        headers={"content-type": "application/json",
                 "authorization": "Bearer " + key},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            out = json.loads(resp.read().decode("utf-8"))
        return (out.get("choices", [{}])[0].get("message", {}).get("content") or "").strip() or None
    except Exception as e:
        print("  [groq] erreur:", e)
        return None


def ollama_reply(system, messages, model, max_tokens=200):
    # Si GROQ_API_KEY est defini, on utilise Groq (cloud) au lieu d'Ollama (local).
    if ns.groq_api_key():
        return groq_reply(system, messages, ns.groq_model(), max_tokens)
    payload = {
        "model": model,
        "messages": [{"role": "system", "content": system}] + messages,
        "temperature": 0.95,
        "max_tokens": max_tokens,
        "stream": False,
    }
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        ns.ollama_url() + "/v1/chat/completions",
        data=data, headers={"content-type": "application/json"}, method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            out = json.loads(resp.read().decode("utf-8"))
        return (out.get("choices", [{}])[0].get("message", {}).get("content") or "").strip() or None
    except Exception as e:
        print("  [ollama] erreur:", e)
        return None


def send_whatsapp(recipient, message):
    payload = json.dumps({"recipient": recipient, "message": message}).encode("utf-8")
    req = urllib.request.Request(
        ns.bridge_url() + "/api/send",
        data=payload, headers={"content-type": "application/json"}, method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            out = json.loads(resp.read().decode("utf-8"))
        return bool(out.get("success")), out.get("message", "")
    except Exception as e:
        return False, str(e)


def send_media(recipient, media_path):
    payload = json.dumps({"recipient": recipient, "media_path": media_path}).encode("utf-8")
    req = urllib.request.Request(
        ns.bridge_url() + "/api/send",
        data=payload, headers={"content-type": "application/json"}, method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=90) as resp:
            out = json.loads(resp.read().decode("utf-8"))
        return bool(out.get("success")), out.get("message", "")
    except Exception as e:
        return False, str(e)


def _download_media(con, chat, lm, media_types):
    """Trouve le dernier media (image/video/audio) du chat et le telecharge via le bridge."""
    jids = ns.equiv_jids(chat, lm)
    ph = ",".join("?" for _ in jids)
    tph = ",".join("?" for _ in media_types)
    row = con.execute(
        "SELECT id, chat_jid FROM messages WHERE chat_jid IN (%s) AND media_type IN (%s) "
        "ORDER BY timestamp DESC LIMIT 1" % (ph, tph), tuple(jids) + tuple(media_types)).fetchone()
    if not row:
        return None, "aucun media recent"
    payload = json.dumps({"message_id": row["id"], "chat_jid": row["chat_jid"]}).encode("utf-8")
    req = urllib.request.Request(ns.bridge_url() + "/api/download", data=payload,
                                 headers={"content-type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=90) as resp:
            out = json.loads(resp.read().decode("utf-8"))
    except Exception as e:
        return None, "download: %s" % e
    if not out.get("success") or not out.get("path"):
        return None, out.get("message", "download echoue")
    return out["path"], row["id"]


def make_sticker(con, chat, lm, recipient, dry):
    ff = shutil.which("ffmpeg")
    if not ff:
        return False, "ffmpeg absent"
    src, info = _download_media(con, chat, lm, ("image",))
    if not src:
        return False, info
    webp = os.path.join(tempfile.gettempdir(), "nova_stk_%d.webp" % int(time.time()))
    vf = "scale=512:512:force_original_aspect_ratio=decrease,pad=512:512:(ow-iw)/2:(oh-ih)/2:color=0x00000000"
    cmd = [ff, "-y", "-i", src, "-vframes", "1", "-vf", vf, "-vcodec", "libwebp", "-lossless", "0", "-q:v", "75", "-an", webp]
    try:
        p = subprocess.run(cmd, capture_output=True, timeout=60)
        if p.returncode != 0 or not os.path.exists(webp):
            return False, "ffmpeg: " + (p.stderr.decode("utf-8", "replace")[-160:] if p.stderr else "echec")
    except Exception as e:
        return False, "ffmpeg: %s" % e
    if dry:
        return True, "dry"
    return send_media(recipient, webp)


def make_audio(con, chat, lm, recipient, dry, ext="mp3"):
    ff = shutil.which("ffmpeg")
    if not ff:
        return False, "ffmpeg absent"
    src, info = _download_media(con, chat, lm, ("video", "audio"))
    if not src:
        return False, info
    out = os.path.join(tempfile.gettempdir(), "nova_aud_%d.%s" % (int(time.time()), ext))
    cmd = [ff, "-y", "-i", src, "-vn", "-acodec", "libmp3lame", "-q:a", "4", out]
    try:
        p = subprocess.run(cmd, capture_output=True, timeout=90)
        if p.returncode != 0 or not os.path.exists(out):
            return False, "ffmpeg: " + (p.stderr.decode("utf-8", "replace")[-160:] if p.stderr else "echec")
    except Exception as e:
        return False, "ffmpeg: %s" % e
    if dry:
        return True, "dry"
    return send_media(recipient, out)


def make_photo(con, chat, lm, recipient, dry):
    src, info = _download_media(con, chat, lm, ("image",))
    if not src:
        return False, info
    if dry:
        return True, "dry"
    return send_media(recipient, src)


def send_with_mentions(recipient, message, mentions):
    payload = json.dumps({"recipient": recipient, "message": message, "mentions": mentions or []}).encode("utf-8")
    req = urllib.request.Request(ns.bridge_url() + "/api/send", data=payload,
                                 headers={"content-type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            out = json.loads(resp.read().decode("utf-8"))
        return bool(out.get("success")), out.get("message", "")
    except Exception as e:
        return False, str(e)


def _name_of(con, jid, lm):
    if not jid:
        return "?"
    try:
        n = ns.chat_name(con, jid)
        if n and n != jid.split("@")[0]:
            return n
    except Exception:
        pass
    return ns.send_recipient(jid, lm).split("@")[0]


def handle_event(ev, lm, dry, owner_num):
    t = ev.get("type")
    settings = ns.load_settings()
    auto = ns.load_automations()
    owner_jid = (owner_num + "@s.whatsapp.net") if owner_num else None

    if t in ("join", "leave"):
        group = ev.get("group")
        parts = ev.get("participants") or []
        if not group or not parts:
            return
        kind = "welcome" if t == "join" else "goodbye"
        cfg = ns.get_greet(auto, kind, group)
        if not cfg.get("on"):
            return
        con = ns.db_connect()
        gname = _name_of(con, group, lm)
        con.close()
        default = "👋 Bienvenue {user} dans {group} !" if kind == "welcome" else "👋 {user} a quitte {group}."
        tmpl = cfg.get("msg") or default
        users, mentions = [], []
        for p in parts:
            users.append("@" + p.split("@")[0].split(":")[0])
            mentions.append(p)
        text = tmpl.replace("{user}", " ".join(users)).replace("{group}", gname)
        if dry:
            print("  -> [DRY %s] %s" % (kind, text))
            return
        send_with_mentions(group, text, mentions)
        print("  -> %s envoye (%d)" % (kind, len(parts)))
        return

    if t == "revoke":
        chat, mid = ev.get("chat"), ev.get("id")
        if not chat or not mid:
            return
        canon = ns.send_recipient(chat, lm)
        if not (settings.get("antidelete") or ns.get_toggle(auto, canon, "antidelete", False)):
            return
        con = ns.db_connect()
        jids = ns.equiv_jids(chat, lm)
        ph = ",".join("?" for _ in jids)
        row = con.execute("SELECT content, media_type FROM messages WHERE chat_jid IN (%s) AND id=? LIMIT 1" % ph,
                          tuple(jids) + (mid,)).fetchone()
        cname = _name_of(con, chat, lm)
        byname = _name_of(con, ev.get("by") or chat, lm)
        con.close()
        if not row:
            body = "(message non retrouve en base)"
        else:
            body = row["content"] or ""
            if row["media_type"]:
                body = (body + " [media: %s]" % row["media_type"]).strip()
            if not body:
                body = "(contenu vide)"
        note = "🗑️ Message supprime dans %s par %s :\n%s" % (cname, byname, body)
        dest = chat if settings.get("antidelete_in_chat") else owner_jid
        if not dest:
            return
        if dry:
            print("  -> [DRY antidelete] " + note[:70])
            return
        send_whatsapp(dest, note)
        print("  -> antidelete note envoyee")
        return

    if t == "edit":
        if not settings.get("antiedit"):
            return
        chat, mid = ev.get("chat"), ev.get("id")
        newc = ev.get("new_content") or ""
        if not chat or not mid or not owner_jid:
            return
        con = ns.db_connect()
        jids = ns.equiv_jids(chat, lm)
        ph = ",".join("?" for _ in jids)
        row = con.execute("SELECT content FROM messages WHERE chat_jid IN (%s) AND id=? LIMIT 1" % ph,
                          tuple(jids) + (mid,)).fetchone()
        byname = _name_of(con, ev.get("by") or chat, lm)
        con.close()
        old = (row["content"] if row else "") or "(ancien introuvable)"
        note = "✏️ Message modifie par %s :\n%s → %s" % (byname, old, newc)
        if dry:
            print("  -> [DRY antiedit] " + note[:70])
            return
        send_whatsapp(owner_jid, note)
        print("  -> antiedit note envoyee")
        return


def handle_command(con, chat, row, settings, contacts, lm, dry, start_ts):
    prefix = settings["command_prefix"]
    content = (row["content"] or "").strip()
    body = content[len(prefix):].strip()
    if not body:
        return
    parts = body.split()
    name = parts[0].lower()
    args = parts[1:]
    text = body[len(parts[0]):].strip()
    is_group = ns.is_group(chat)
    recipient = ns.send_recipient(chat, lm)

    def _send(t):
        if not t:
            return
        t = str(t)
        if dry:
            print("  -> [DRY cmd] " + t[:200].replace("\n", " ⏎ "))
            return
        ok, msg = send_whatsapp(recipient, t)
        print("  -> cmd envoyee" if ok else "  -> cmd ECHEC: " + str(msg))

    def _send_media(path):
        if dry:
            print("  -> [DRY cmd media] " + str(path))
            return True, "dry"
        return send_media(recipient, path)

    def _ai(prompt, system=None):
        return ollama_reply(system or "Tu reponds en francais, de maniere concise et utile. "
                            "Donne uniquement la reponse, sans preambule.",
                            [{"role": "user", "content": prompt}], settings["model"], 500)

    def _history(limit=20):
        jids = ns.equiv_jids(chat, lm)
        ph = ",".join("?" for _ in jids)
        rr = con.execute("SELECT content, is_from_me FROM messages WHERE chat_jid IN (%s) AND content<>'' "
                         "ORDER BY timestamp DESC LIMIT ?" % ph, tuple(jids) + (limit,)).fetchall()
        return [{"from_me": bool(x["is_from_me"]), "content": x["content"]} for x in reversed(rr)]

    def _samples():
        return get_owner_samples(con, ns.equiv_jids(chat, lm), 14)

    def _participants():
        if not is_group:
            return []
        rr = con.execute("SELECT DISTINCT sender FROM messages WHERE chat_jid=? AND sender<>''  LIMIT 500", (chat,)).fetchall()
        nums = []
        for x in rr:
            u = (x["sender"] or "").split("@")[0].split(":")[0]
            if u and u not in nums:
                nums.append(u)
        return nums

    def _send_to(rcpt, t):
        if dry:
            print("  -> [DRY bcast] %s : %s" % (rcpt, str(t)[:40]))
            return True
        ok, _m = send_whatsapp(rcpt, t)
        return ok

    def _enabled_contacts():
        out, vus = [], set()
        for j in ns.enabled_jids():
            rc = ns.send_recipient(j, lm)
            if rc not in vus:
                vus.add(rc)
                out.append(rc)
        return out

    def _broadcast(msg):
        limit = int(settings.get("broadcast_limit", 30))
        cnt = 0
        for rc in _enabled_contacts()[:limit]:
            if _send_to(rc, msg):
                cnt += 1
            dmin = settings["delay_min"]
            time.sleep(random.uniform(dmin, max(dmin, settings["delay_max"])))
        return cnt

    snum = (row["sender"] or "").split("@")[0].split(":")[0]
    is_sudo = bool(row["is_from_me"]) or (snum in settings.get("sudo", []))

    def _download_last(types):
        path, info = _download_media(con, chat, lm, tuple(types))
        return (path, "") if path else (None, str(info))

    def _send_mentions(rcpt, text, mentions):
        if dry:
            print("  -> [DRY mentions] %s" % str(text)[:50])
            return True
        ok, _m = send_with_mentions(rcpt, text, mentions)
        return ok

    ctx = plugins.Ctx(
        chat_jid=chat, sender=(row["sender"] or chat), is_group=is_group, is_owner=bool(row["is_from_me"]),
        is_sudo=is_sudo, command=name, args=args, text=text, owner_name=settings["owner_name"], prefix=prefix, dry=dry,
        settings=settings, lm=lm, uptime=time.time() - start_ts,
        owner_jid=((snum + "@s.whatsapp.net") if row["is_from_me"] else None),
        send=_send, send_media=_send_media, ai=_ai, history=_history, samples=_samples, participants=_participants,
        send_to=_send_to, enabled_contacts=_enabled_contacts, broadcast=_broadcast,
        download_last=_download_last, send_mentions=_send_mentions,
        sticker=lambda: make_sticker(con, chat, lm, recipient, dry),
        photo=lambda: make_photo(con, chat, lm, recipient, dry),
        to_audio=lambda ext="mp3": make_audio(con, chat, lm, recipient, dry, ext),
    )
    print("[%s] CMD %s%s" % (time.strftime("%H:%M:%S"), prefix, body))
    res = plugins.dispatch(ctx)
    if isinstance(res, str) and res.strip():
        _send(res)


FACTUAL_MARKERS = (
    "combien", "prix", "coute", "coûte", "rendez-vous", "rdv", "adresse",
    "numero", "numéro", "quelle heure", "a quelle heure", "à quelle heure",
    "c'est quand", "c est quand", " quand ", "quand?", "quand ?", "quel jour",
    "date exacte", "quelle date", "c'est où", "c'est ou",
)


def is_factual_question(text):
    t = " " + (text or "").lower().strip() + " "
    return any(m in t for m in FACTUAL_MARKERS)


def should_skip_reply(reply):
    if not reply:
        return True
    r = reply.strip()
    if "[skip]" in r.lower():
        return True
    if len(r) > 600:  # sortie incoherente / trop longue
        return True
    return False


def _build_system(owner, name, sample_txt, ccfg, settings):
    system = SYSTEM_TMPL.format(owner=owner, contact=name, samples=sample_txt)
    tone = (ccfg or {}).get("tone", "").strip()
    notes = (ccfg or {}).get("notes", "").strip()
    length = (ccfg or {}).get("length", "auto")
    system += ("\nReponds VRAIMENT au dernier message (adresse ce qui est dit ou demande), tout en restant "
               "court. N'envoie pas une reaction vide comme 'Oh' ou 'Ok' si une vraie reponse est attendue.")
    if tone:
        system += "\nConsigne pour ce contact : " + tone
    if notes:
        system += "\nCe que tu sais sur " + name + " : " + notes
    if length == "court":
        system += "\nReste particulierement bref (1 ligne, quelques mots)."
    elif length == "long":
        system += "\nTu peux developper un peu plus si le message le merite, mais garde ton style."
    if settings.get("skip_uncertain"):
        system += ("\nGARDE-FOU : si le dernier message demande une info que TU ne peux pas connaitre avec "
                   "certitude (prix, rendez-vous, adresse, numero, un fait precis absent de la conversation) "
                   "ou si tu n'es pas sur de la bonne reponse, ecris EXACTEMENT [SKIP] et rien d'autre. "
                   "Mieux vaut [SKIP] que d'inventer.")
    return system


def _contact_cfg(jids, contacts):
    for j in jids:
        if j in contacts:
            return contacts[j]
    return {}


def gen_reply_for(con, chat_jid, lm, settings, contacts):
    # Construit un transcript ETIQUETE (qui a dit quoi) sur les N derniers tours.
    jids = ns.equiv_jids(chat_jid, lm)
    ph = ",".join("?" for _ in jids)
    rows = con.execute(
        "SELECT content, is_from_me FROM messages WHERE chat_jid IN (%s) AND content<>'' "
        "ORDER BY timestamp ASC" % ph, tuple(jids)).fetchall()
    if not rows:
        return None
    owner = settings["owner_name"]
    name = ns.chat_name(con, chat_jid)
    turns = max(4, int(settings.get("transcript_turns", 16)))
    lines = []
    for r in rows[-turns:]:
        txt = (r["content"] or "").strip()
        if txt:
            lines.append((owner if r["is_from_me"] else name) + ": " + txt)
    if not lines:
        return None
    transcript = "\n".join(lines)
    samples = get_owner_samples(con, jids, 14)
    sample_txt = "\n".join("- " + s for s in samples) if samples else "(peu d'exemples : reste tres court et familier)"
    ccfg = _contact_cfg(jids, contacts)
    system = _build_system(owner, name, sample_txt, ccfg, settings)
    user = ("Voici votre conversation WhatsApp (du plus ancien au plus recent). "
            "Ecris UNIQUEMENT le prochain message de " + owner + " (une seule reponse, dans son style) "
            "qui repond au dernier message de " + name + " :\n\n" + transcript + "\n" + owner + " :")
    length = ccfg.get("length", "auto")
    mx = 120 if length == "court" else (320 if length == "long" else 200)
    return ollama_reply(system, [{"role": "user", "content": user}], settings["model"], mx)


def preview_reply(chat_jid):
    """Pour le panneau : genere la reponse au dernier message, SANS envoyer."""
    settings = ns.load_settings()
    contacts = ns.load_contacts()
    lm = ns.load_lidmap()
    con = ns.db_connect()
    try:
        return gen_reply_for(con, chat_jid, lm, settings, contacts)
    finally:
        con.close()


# ---------------- planification ----------------
def within_active_hours(settings):
    if not settings.get("active_hours_enabled"):
        return True
    now = datetime.now().strftime("%H:%M")
    start = settings.get("active_start", "00:00")
    end = settings.get("active_end", "23:59")
    if start <= end:
        return start <= now <= end
    return now >= start or now <= end  # plage qui passe minuit


# ---------------- commandes CLI ----------------
def cmd_contacts():
    con = ns.db_connect()
    rows = con.execute(
        "SELECT jid, name, last_message_time FROM chats ORDER BY last_message_time DESC LIMIT 40"
    ).fetchall()
    print("Discussions privees recentes :\n")
    for r in rows:
        if ns.is_dm(r["jid"]):
            print("  %-40s  %s" % (r["jid"], (r["name"] or "")))
    con.close()


def cmd_selftest():
    settings = ns.load_settings()
    contacts = ns.load_contacts()
    lm = ns.load_lidmap()
    con = ns.db_connect()
    target = None
    for r in con.execute("SELECT jid, name FROM chats ORDER BY last_message_time DESC").fetchall():
        if not ns.is_dm(r["jid"]):
            continue
        if len(build_history(con, ns.equiv_jids(r["jid"], lm), settings["history_limit"])) >= 2:
            target = (r["jid"], r["name"] or r["jid"])
            break
    if not target:
        print("selftest: aucune discussion privee avec assez d'historique")
        con.close()
        return
    print("selftest sur:", target[1], "(" + target[0] + ")")
    reply = gen_reply_for(con, target[0], lm, settings, contacts)
    con.close()
    print("=== REPONSE GENEREE (NON envoyee) ===")
    print(reply)


# ---------------- boucle principale ----------------
def main():
    dry = "--dry-run" in sys.argv
    if "--contacts" in sys.argv:
        return cmd_contacts()
    if "--selftest" in sys.argv:
        return cmd_selftest()

    settings = ns.load_settings()
    contacts = ns.load_contacts()
    wl = ns.enabled_jids(contacts)

    print("NOVA (whatsmeow) — cerveau demarre")
    print("  proprietaire:", settings["owner_name"], "| modele:", settings["model"], "| historique:", settings["history_limit"])
    print("  mode:", "DRY-RUN (aucun envoi)" if dry else "REEL (envoie les reponses)")
    print("  delai humain:", "%ss-%ss" % (settings["delay_min"], settings["delay_max"]),
          "| debit max/contact/h:", settings["rate_per_hour"])
    if settings["active_hours_enabled"]:
        print("  plage active:", settings["active_start"], "->", settings["active_end"])
    if settings["vacation_mode"]:
        print("  MODE VACANCES actif")
    if settings["persona_all"]:
        print("  cible: TOUTES les discussions privees")
    else:
        print("  cible:", (", ".join(sorted(wl)) if wl else "(aucune — active des contacts dans le panneau)"))
    print("")

    # Au demarrage : marquer tout comme vu, sauf le dernier message non-repondu recent
    seen = set()
    rate = {}  # jid canonique -> [timestamps d'envoi]
    afk_sent = {}  # recipient canonique -> dernier ts d'auto-reponse AFK
    owner_num = ""  # numero du proprietaire (detecte depuis un message is_from_me)
    start_ts = time.time()
    try:
        lm0 = ns.load_lidmap()
        con = ns.db_connect()
        for r in con.execute("SELECT id FROM messages"):
            seen.add(r["id"])
        cutoff = datetime.now(timezone.utc) - timedelta(hours=2)
        targets = set()
        if settings["persona_all"]:
            for r in con.execute("SELECT DISTINCT chat_jid FROM messages ORDER BY timestamp DESC LIMIT 120"):
                if ns.is_dm(r["chat_jid"]):
                    targets.add(r["chat_jid"])
        else:
            for j in wl:
                targets |= ns.equiv_jids(j, lm0)
        for cj in targets:
            row = con.execute(
                "SELECT id, is_from_me, timestamp FROM messages WHERE chat_jid=? AND content<>'' "
                "ORDER BY timestamp DESC LIMIT 1", (cj,)).fetchone()
            if not row or row["is_from_me"]:
                continue
            try:
                dt = datetime.fromisoformat(row["timestamp"])
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                if dt < cutoff:
                    continue
            except Exception:
                pass
            seen.discard(row["id"])
        try:
            _ro = con.execute("SELECT sender FROM messages WHERE is_from_me=1 AND sender<>'' "
                              "ORDER BY timestamp DESC LIMIT 1").fetchone()
            if _ro:
                owner_num = (_ro["sender"] or "").split("@")[0].split(":")[0]
        except Exception:
            pass
        con.close()
    except Exception as e:
        print("Impossible d'ouvrir la base:", e)
        return

    # Journal d'evenements : se positionner a la FIN pour ne pas rejouer l'historique
    event_offset = ns.events_end_offset()
    ns.write_event_offset(event_offset)

    while True:
        try:
            settings = ns.load_settings()
            contacts = ns.load_contacts()
            wl = ns.enabled_jids(contacts)
            persona_all = settings["persona_all"]

            lm = ns.load_lidmap()
            con = ns.db_connect()
            rows = con.execute(
                "SELECT id, chat_jid, sender, content, is_from_me, timestamp "
                "FROM messages ORDER BY timestamp DESC LIMIT 60"
            ).fetchall()
            for r in reversed(rows):
                mid = r["id"]
                if mid in seen:
                    continue
                seen.add(mid)
                chat = r["chat_jid"]
                content = (r["content"] or "").strip()
                is_me = bool(r["is_from_me"])

                # ---- COMMANDES (prioritaire, fonctionne meme en pause) ----
                if settings["commands_enabled"] and content and content.startswith(settings["command_prefix"]):
                    snum = (r["sender"] or "").split("@")[0].split(":")[0]
                    is_sudo_sender = snum in settings.get("sudo", [])
                    can_run = (is_me or is_sudo_sender
                               or ((not settings["commands_owner_only"]) and settings["commands_allow_others"]
                                   and bool(ns.equiv_jids(chat, lm) & wl)))
                    if can_run:
                        try:
                            handle_command(con, chat, r, settings, contacts, lm, dry, start_ts)
                        except Exception as e:
                            print("cmd erreur:", e)
                    continue

                # Auto-desactivation AFK quand TOI tu ecris (hors commande)
                if is_me and settings["afk"] and content and not content.startswith(settings["command_prefix"]):
                    ns.save_settings({"afk": False})
                    print("[AFK] desactive (tu as ecrit)")

                # ---- FLUX PERSONA / AUTOMATIONS (suspendu si pause) ----
                if settings["paused"] or is_me:
                    continue
                if not content:
                    continue
                is_grp = ns.is_group(chat)
                canon = ns.send_recipient(chat, lm)

                # AFK : auto-reponse d'absence (prive, ou mention en groupe), prioritaire
                if settings["afk"]:
                    mention = is_grp and owner_num and ("@" + owner_num in content)
                    if ns.is_dm(chat) or mention:
                        if time.time() - afk_sent.get(canon, 0) > settings["afk_cooldown_min"] * 60:
                            reason = settings.get("afk_reason", "")
                            txt = "🚫 absent" + (" : " + reason if reason else "")
                            if not dry:
                                send_whatsapp(canon, txt)
                            afk_sent[canon] = time.time()
                            print("  -> [AFK] " + txt)
                        continue

                # Moderation de groupe (antilink / antiword), independante de allow_groups
                if is_grp:
                    snum2 = (r["sender"] or "").split("@")[0].split(":")[0]
                    is_priv2 = bool(r["is_from_me"]) or (snum2 in settings.get("sudo", []))
                    if not is_priv2:
                        autom = ns.load_automations()
                        bad = None
                        if ns.get_toggle(autom, canon, "antilink", False) and re.search(
                                r"(https?://|chat\.whatsapp\.com/|wa\.me/|t\.me/|[\w-]+\.(?:com|net|org|io|xyz|me|ng|cm|fr)\b)",
                                content, re.I):
                            bad = "lien interdit"
                        elif ns.get_toggle(autom, canon, "antiword", False):
                            cl = content.lower()
                            if any(w in cl for w in (settings.get("antiword_list", []) or [])):
                                bad = "mot interdit"
                        if bad:
                            w = ns.load_json("warns.json", {})
                            wd = w.setdefault(canon, {})
                            wd[snum2] = wd.get(snum2, 0) + 1
                            limit = int(settings.get("warn_limit", 3))
                            if not dry:
                                if wd[snum2] >= limit:
                                    send_with_mentions(chat, "🚫 @%s expulse (%s)" % (snum2, bad), [r["sender"] or chat])
                                    try:
                                        urllib.request.urlopen(urllib.request.Request(
                                            ns.bridge_url() + "/api/group-action",
                                            data=json.dumps({"jid": chat, "action": "kick", "participants": [snum2]}).encode("utf-8"),
                                            headers={"content-type": "application/json"}, method="POST"), timeout=20)
                                    except Exception:
                                        pass
                                    wd[snum2] = 0
                                else:
                                    send_with_mentions(chat, "⚠️ @%s %s (%d/%d)" % (snum2, bad, wd[snum2], limit), [r["sender"] or chat])
                            ns.save_json("warns.json", w)
                            print("  -> moderation: %s (%s)" % (bad, snum2))
                            continue

                allowed = ns.is_dm(chat) or (settings["allow_groups"] and is_grp)
                if not allowed:
                    continue

                # FILTRES (auto-reponses par mot-cle, independants du persona)
                auto = ns.load_automations()
                if ns.get_toggle(auto, canon, "filters", True):
                    hits = ns.match_filters(auto, canon, content)
                    if hits:
                        if not dry:
                            for h in hits[:3]:
                                send_whatsapp(canon, h)
                        print("  -> filtre x%d" % len(hits))
                        if settings["filters_before_persona"]:
                            continue

                # PERSONA : toggle par chat + liste blanche
                if not ns.get_toggle(auto, canon, "persona", True):
                    continue
                jids = ns.equiv_jids(chat, lm)
                if not persona_all and not (jids & wl):
                    continue
                name = ns.chat_name(con, chat)

                # Mot-cle STOP : desactive le contact
                if content.lower().strip(" .!?") in STOP_WORDS:
                    for j in jids:
                        if j in contacts:
                            ns.set_contact(j, {"enabled": False})
                    print("[%s] STOP recu de %s -> contact desactive" % (time.strftime("%H:%M:%S"), name))
                    continue

                ns.bump_stats("received", canon)
                print("[%s] %s: %s" % (time.strftime("%H:%M:%S"), name, content))

                if not within_active_hours(settings):
                    print("  -> hors plage active, pas de reponse")
                    continue

                now_ts = time.time()
                sent_recent = [t for t in rate.get(canon, []) if now_ts - t < 3600]
                rate[canon] = sent_recent
                if len(sent_recent) >= settings["rate_per_hour"]:
                    print("  -> limite de debit atteinte pour ce contact, on laisse passer")
                    continue

                # Regroupement des rafales : attendre puis agreger les messages du contact
                trigger_ts = r["timestamp"]
                deb = int(settings.get("debounce_seconds", 0) or 0)
                if deb > 0:
                    time.sleep(deb)
                reply = None
                factual_skip = False
                con_b = ns.db_connect()
                try:
                    phb = ",".join("?" for _ in jids)
                    brows = con_b.execute(
                        "SELECT id, content, is_from_me FROM messages WHERE chat_jid IN (%s) AND timestamp>=? "
                        "ORDER BY timestamp ASC" % phb, tuple(jids) + (trigger_ts,)).fetchall()
                    incoming_parts = []
                    for br in brows:
                        seen.add(br["id"])
                        if not br["is_from_me"] and (br["content"] or "").strip():
                            incoming_parts.append(br["content"].strip())
                    incoming = "\n".join(incoming_parts) if incoming_parts else content
                    if len(incoming_parts) > 1:
                        print("  (rafale regroupee: %d messages)" % len(incoming_parts))
                    if settings.get("skip_question_heuristic") and is_factual_question(incoming):
                        factual_skip = True
                    elif settings["vacation_mode"]:
                        reply = (settings.get("vacation_message") or "").strip() or None
                    else:
                        reply = gen_reply_for(con_b, chat, lm, settings, contacts)
                finally:
                    con_b.close()

                if factual_skip:
                    print("  -> question factuelle / info inconnue -> laisse a toi")
                    continue
                if not reply:
                    print("  -> (pas de reponse generee)")
                    continue
                if settings.get("skip_uncertain") and should_skip_reply(reply):
                    print("  -> pas sur -> laisse a toi (aucun envoi)")
                    continue

                # delai humain (+ temps de frappe simule)
                dmin, dmax = settings["delay_min"], max(settings["delay_min"], settings["delay_max"])
                delay = random.uniform(dmin, dmax)
                if settings["simulate_typing"]:
                    delay += min(8.0, len(reply) * 0.08)
                time.sleep(delay)

                if dry:
                    print("  -> [DRY] repondrait: " + reply)
                else:
                    rcpt = ns.send_recipient(chat, lm)
                    ok, msg = send_whatsapp(rcpt, reply)
                    if ok:
                        rate.setdefault(canon, []).append(now_ts)
                        ns.bump_stats("sent", canon)
                        print("  -> envoye a " + rcpt + " | " + reply)
                    else:
                        print("  -> ECHEC envoi: " + str(msg) + " | " + reply)

            # Rappels / programmations arrives a echeance
            for rem in ns.pop_due_reminders(time.time()):
                try:
                    rcpt = ns.send_recipient(rem.get("chat", ""), lm)
                    txt = "⏰ " + (rem.get("message") or "")
                    if not dry:
                        send_whatsapp(rcpt, txt)
                    print("  -> rappel #%s envoye a %s" % (rem.get("id"), rcpt))
                except Exception as e:
                    print("rappel erreur:", e)

            # Evenements du bridge (join/leave/revoke/edit)
            evs, event_offset = ns.read_new_events(event_offset)
            if evs:
                ns.write_event_offset(event_offset)
                for ev in evs:
                    try:
                        handle_event(ev, lm, dry, owner_num)
                    except Exception as e:
                        print("event erreur:", e)
            con.close()
        except KeyboardInterrupt:
            print("\nArret.")
            return
        except Exception as e:
            print("boucle erreur:", e)
        time.sleep(settings["poll_seconds"])


if __name__ == "__main__":
    main()
