# -*- coding: utf-8 -*-
"""
Helpers partages (stdlib uniquement) pour NOVA : reglages, contacts, stats,
acces base whatsmeow (lecture seule), resolution d'identifiants @lid<->numero.
Utilise par brain.py (le demon) et panel.py (le tableau de bord).
"""
import json
import os
import sqlite3
import tempfile
from datetime import date
from pathlib import Path

HERE = Path(__file__).resolve().parent
ENV_FILE = HERE / ".env"
SETTINGS_FILE = HERE / "settings.json"
CONTACTS_FILE = HERE / "persona_chats.json"
STATS_FILE = HERE / "stats.json"

DEFAULT_DB = r"C:/Users/M12K/.claude/mcp-servers/lharries_whatsapp-mcp/whatsapp-bridge/store/messages.db"


# ---------------- .env (chemins / urls seulement) ----------------
def load_env():
    env = {}
    try:
        for line in ENV_FILE.read_text(encoding="utf-8").splitlines():
            s = line.strip()
            if s and not s.startswith("#") and "=" in s:
                k, v = s.split("=", 1)
                env[k.strip()] = v.strip()
    except OSError:
        pass
    return env


def env_get(key, default=None):
    return os.environ.get(key) or load_env().get(key) or default


def db_path():
    return env_get("MESSAGES_DB", DEFAULT_DB)


def wa_db():
    return str(Path(db_path()).with_name("whatsapp.db"))


def ollama_url():
    return (env_get("OLLAMA_URL", "http://localhost:11434") or "").rstrip("/")


def bridge_url():
    return (env_get("BRIDGE_URL", "http://localhost:8080") or "").rstrip("/")


# ---------------- ecriture atomique ----------------
def _atomic_write(path, text):
    path = Path(path)
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(text)
        os.replace(tmp, str(path))
    except Exception:
        try:
            os.unlink(tmp)
        except Exception:
            pass
        raise


# ---------------- reglages (settings.json) ----------------
DEFAULT_SETTINGS = {
    "owner_name": "moi",
    "model": "qwen2.5:7b",
    "history_limit": 50,
    "poll_seconds": 3,
    "paused": False,
    "delay_min": 3,
    "delay_max": 12,
    "simulate_typing": True,
    "active_hours_enabled": False,
    "active_start": "08:00",
    "active_end": "23:00",
    "vacation_mode": False,
    "vacation_message": "",
    "rate_per_hour": 15,
    "allow_groups": False,
    "persona_all": False,
    "transcript_turns": 16,
    "debounce_seconds": 5,
    "skip_uncertain": True,
    "skip_question_heuristic": True,
    "command_prefix": ".",
    "commands_enabled": True,
    "commands_owner_only": True,
    "commands_allow_others": False,
    "plugins_disabled": [],
    "afk": False,
    "afk_reason": "",
    "afk_cooldown_min": 30,
    "sudo": [],
    "filters_before_persona": True,
    "broadcast_limit": 30,
    "antidelete": False,
    "antiedit": False,
    "antidelete_in_chat": False,
    "warn_limit": 3,
    "sticker_packname": "NOVA",
    "timezone": "",
    "cmd_reaction": False,
    "auto_mention": False,
    "alwaysonline": False,
    "rejectcall": False,
    "send_read": False,
    "antibot": False,
    "antiword_list": [],
}
_INT_KEYS = ("history_limit", "poll_seconds", "delay_min", "delay_max", "rate_per_hour",
             "transcript_turns", "debounce_seconds", "afk_cooldown_min", "broadcast_limit", "warn_limit")
_BOOL_KEYS = ("paused", "simulate_typing", "active_hours_enabled", "vacation_mode", "allow_groups",
              "persona_all", "skip_uncertain", "skip_question_heuristic",
              "commands_enabled", "commands_owner_only", "commands_allow_others",
              "afk", "filters_before_persona", "antidelete", "antiedit", "antidelete_in_chat",
              "cmd_reaction", "auto_mention", "alwaysonline", "rejectcall", "send_read", "antibot")
_LIST_KEYS = ("plugins_disabled", "sudo", "antiword_list")


def load_json(name, default):
    try:
        return json.loads((HERE / name).read_text(encoding="utf-8"))
    except Exception:
        return default() if callable(default) else default


def save_json(name, data):
    try:
        _atomic_write(HERE / name, json.dumps(data, ensure_ascii=False, indent=2))
    except Exception:
        pass


def load_settings():
    s = dict(DEFAULT_SETTINGS)
    try:
        data = json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            s.update(data)
    except Exception:
        env = load_env()
        if env.get("OWNER_NAME"):
            s["owner_name"] = env["OWNER_NAME"]
        if env.get("AI_MODEL"):
            s["model"] = env["AI_MODEL"]
        if env.get("HISTORY_LIMIT"):
            try:
                s["history_limit"] = int(env["HISTORY_LIMIT"])
            except Exception:
                pass
    for k in _INT_KEYS:
        try:
            s[k] = int(s[k])
        except Exception:
            s[k] = DEFAULT_SETTINGS[k]
    for k in _BOOL_KEYS:
        s[k] = bool(s[k])
    for k in _LIST_KEYS:
        if not isinstance(s.get(k), list):
            s[k] = list(DEFAULT_SETTINGS.get(k, []))
    if not isinstance(s.get("command_prefix"), str) or not s.get("command_prefix"):
        s["command_prefix"] = "."
    if not isinstance(s.get("afk_reason"), str):
        s["afk_reason"] = ""
    return s


def save_settings(partial):
    s = load_settings()
    if partial:
        s.update(partial)
    for k in _INT_KEYS:
        try:
            s[k] = int(s[k])
        except Exception:
            s[k] = DEFAULT_SETTINGS[k]
    for k in _BOOL_KEYS:
        s[k] = bool(s[k])
    _atomic_write(SETTINGS_FILE, json.dumps(s, ensure_ascii=False, indent=2))
    return s


# ---------------- contacts (persona_chats.json, format objet) ----------------
DEFAULT_CONTACT = {"enabled": True, "tone": "", "length": "auto", "notes": ""}


def load_contacts():
    """Retourne {jid: {enabled, tone, length}}. Migre l'ancien format liste."""
    try:
        data = json.loads(CONTACTS_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {}
    out = {}
    if isinstance(data, list):
        for jid in data:
            if isinstance(jid, str):
                out[jid] = dict(DEFAULT_CONTACT)
    elif isinstance(data, dict):
        for jid, cfg in data.items():
            if not isinstance(jid, str):
                continue
            if isinstance(cfg, dict):
                c = dict(DEFAULT_CONTACT)
                c.update(cfg)
                c["enabled"] = bool(c.get("enabled", True))
                out[jid] = c
            elif cfg is True:
                out[jid] = dict(DEFAULT_CONTACT)
    return out


def save_contacts(contacts):
    _atomic_write(CONTACTS_FILE, json.dumps(contacts, ensure_ascii=False, indent=2))


def set_contact(jid, patch):
    c = load_contacts()
    cur = c.get(jid, dict(DEFAULT_CONTACT))
    if patch:
        cur.update(patch)
    cur["enabled"] = bool(cur.get("enabled", True))
    c[jid] = cur
    save_contacts(c)
    return c


def enabled_jids(contacts=None):
    c = contacts if contacts is not None else load_contacts()
    return set(j for j, cfg in c.items() if cfg.get("enabled"))


# ---------------- stats (stats.json) ----------------
def _today():
    return date.today().isoformat()


def load_stats():
    try:
        data = json.loads(STATS_FILE.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            raise ValueError
    except Exception:
        data = {}
    data.setdefault("total_received", 0)
    data.setdefault("total_sent", 0)
    data.setdefault("day", _today())
    data.setdefault("today_received", 0)
    data.setdefault("today_sent", 0)
    data.setdefault("per_contact", {})
    if data.get("day") != _today():
        data["day"] = _today()
        data["today_received"] = 0
        data["today_sent"] = 0
    return data


def bump_stats(kind, jid=None):
    data = load_stats()
    if kind == "received":
        data["total_received"] += 1
        data["today_received"] += 1
    elif kind == "sent":
        data["total_sent"] += 1
        data["today_sent"] += 1
    if jid:
        pc = data["per_contact"].setdefault(jid, {"received": 0, "sent": 0})
        if kind in ("received", "sent"):
            pc[kind] = pc.get(kind, 0) + 1
    try:
        _atomic_write(STATS_FILE, json.dumps(data, ensure_ascii=False))
    except Exception:
        pass
    return data


# ---------------- automations (automations.json) : filtres, rappels, toggles ----------------
AUTO_FILE = HERE / "automations.json"
GLOBAL_KEY = "__global__"


def load_automations():
    try:
        d = json.loads(AUTO_FILE.read_text(encoding="utf-8"))
        if not isinstance(d, dict):
            raise ValueError
    except Exception:
        d = {}
    if not isinstance(d.get("filters"), dict):
        d["filters"] = {}          # {chatkey|"__global__": [ {trigger, reply, mode} ]}
    if not isinstance(d.get("reminders"), list):
        d["reminders"] = []        # [ {id, due, chat, message, created} ]
    if not isinstance(d.get("toggles"), dict):
        d["toggles"] = {}          # {chatcanon: {feature: bool}}
    if not isinstance(d.get("welcome"), dict):
        d["welcome"] = {}          # {group_jid: {on, msg}}
    if not isinstance(d.get("goodbye"), dict):
        d["goodbye"] = {}
    return d


def get_greet(auto, kind, group):
    return auto.get(kind, {}).get(group, {}) if kind in ("welcome", "goodbye") else {}


def set_greet(kind, group, on=None, msg=None):
    if kind not in ("welcome", "goodbye"):
        return
    d = load_automations()
    cur = d.setdefault(kind, {}).setdefault(group, {"on": False, "msg": ""})
    if on is not None:
        cur["on"] = bool(on)
    if msg is not None:
        cur["msg"] = msg
    save_automations(d)
    return d


def save_automations(d):
    _atomic_write(AUTO_FILE, json.dumps(d, ensure_ascii=False, indent=2))


def get_toggle(auto, chatkey, feature, default=True):
    return bool(auto.get("toggles", {}).get(chatkey, {}).get(feature, default))


def set_toggle(chatkey, feature, value):
    d = load_automations()
    d["toggles"].setdefault(chatkey, {})[feature] = bool(value)
    save_automations(d)
    return d


def match_filters(auto, chatkey, text):
    """Retourne la liste des reponses des filtres (du chat + globaux) qui matchent."""
    tl = (text or "").lower().strip()
    out = []
    for scope in (chatkey, GLOBAL_KEY):
        for f in auto.get("filters", {}).get(scope, []):
            trig = (f.get("trigger") or "").lower().strip()
            if not trig:
                continue
            mode = f.get("mode", "contains")
            if (mode == "exact" and tl == trig) or (mode != "exact" and trig in tl):
                rep = f.get("reply")
                if rep:
                    out.append(rep)
    return out


def add_filter(chatkey, trigger, reply, mode="contains"):
    d = load_automations()
    lst = d["filters"].setdefault(chatkey, [])
    lst[:] = [f for f in lst if (f.get("trigger") or "").lower() != (trigger or "").lower()]
    lst.append({"trigger": trigger, "reply": reply, "mode": mode})
    save_automations(d)
    return d


def remove_filter(chatkey, trigger):
    d = load_automations()
    lst = d["filters"].get(chatkey, [])
    n = len(lst)
    lst[:] = [f for f in lst if (f.get("trigger") or "").lower() != (trigger or "").lower()]
    d["filters"][chatkey] = lst
    save_automations(d)
    return n - len(lst)


def list_filters(chatkey):
    d = load_automations()
    return {"chat": d["filters"].get(chatkey, []), "global": d["filters"].get(GLOBAL_KEY, [])}


def add_reminder(chat, due_ts, message):
    import time as _t
    d = load_automations()
    rid = hex(int(_t.time() * 1000))[-6:]
    d["reminders"].append({"id": rid, "due": int(due_ts), "chat": chat, "message": message, "created": int(_t.time())})
    save_automations(d)
    return rid


def cancel_reminder(rid):
    d = load_automations()
    n = len(d["reminders"])
    d["reminders"] = [r for r in d["reminders"] if r.get("id") != rid]
    save_automations(d)
    return n - len(d["reminders"])


def pop_due_reminders(now_ts):
    """Retire et renvoie les rappels arrives a echeance."""
    d = load_automations()
    due = [r for r in d["reminders"] if r.get("due", 0) <= now_ts]
    if due:
        d["reminders"] = [r for r in d["reminders"] if r.get("due", 0) > now_ts]
        save_automations(d)
    return due


# ---------------- journal d'evenements (events.jsonl) ----------------
EVENT_OFFSET_FILE = HERE / "event_offset.txt"


def events_path():
    return str(Path(db_path()).with_name("events.jsonl"))


def events_end_offset():
    try:
        return os.path.getsize(events_path())
    except OSError:
        return 0


def read_event_offset():
    try:
        return int(EVENT_OFFSET_FILE.read_text(encoding="utf-8").strip())
    except Exception:
        return 0


def write_event_offset(n):
    try:
        _atomic_write(EVENT_OFFSET_FILE, str(int(n)))
    except Exception:
        pass


def read_new_events(offset):
    """Lit les NOUVELLES lignes completes du journal depuis `offset` (octets).
    Renvoie (liste_evenements, nouvel_offset)."""
    p = events_path()
    try:
        size = os.path.getsize(p)
    except OSError:
        return [], offset
    if size < offset:          # fichier tronque / rotation -> repartir du debut
        offset = 0
    if size == offset:
        return [], offset
    try:
        with open(p, "rb") as f:
            f.seek(offset)
            data = f.read()
    except Exception:
        return [], offset
    last_nl = data.rfind(b"\n")
    if last_nl == -1:
        return [], offset      # pas encore de ligne complete
    chunk = data[:last_nl + 1]
    new_offset = offset + len(chunk)
    events = []
    for line in chunk.split(b"\n"):
        line = line.strip()
        if not line:
            continue
        try:
            events.append(json.loads(line.decode("utf-8", "replace")))
        except Exception:
            pass
    return events, new_offset


# ---------------- base WhatsApp / identifiants ----------------
def db_connect(path=None):
    uri = "file:" + (path or db_path()) + "?mode=ro"
    con = sqlite3.connect(uri, uri=True, timeout=5)
    con.row_factory = sqlite3.Row
    return con


def is_dm(jid):
    return bool(jid) and jid != "status@broadcast" and not jid.endswith("@g.us") and not jid.endswith("@bot")


def is_group(jid):
    return bool(jid) and jid.endswith("@g.us")


def load_lidmap():
    m = {"l2p": {}, "p2l": {}}
    try:
        con = sqlite3.connect("file:" + wa_db() + "?mode=ro", uri=True, timeout=5)
        for lid, pn in con.execute("SELECT lid, pn FROM whatsmeow_lid_map"):
            m["l2p"][str(lid)] = str(pn)
            m["p2l"][str(pn)] = str(lid)
        con.close()
    except Exception:
        pass
    return m


def equiv_jids(chat_jid, lm):
    jids = {chat_jid}
    user = chat_jid.split("@")[0].split(":")[0]
    if chat_jid.endswith("@lid"):
        pn = lm["l2p"].get(user)
        if pn:
            jids.add(pn + "@s.whatsapp.net")
    elif chat_jid.endswith("@s.whatsapp.net"):
        lid = lm["p2l"].get(user)
        if lid:
            jids.add(lid + "@lid")
    return jids


def send_recipient(chat_jid, lm):
    user = chat_jid.split("@")[0].split(":")[0]
    if chat_jid.endswith("@lid"):
        pn = lm["l2p"].get(user)
        if pn:
            return pn + "@s.whatsapp.net"
    return chat_jid


def chat_name(con, chat_jid):
    try:
        r = con.execute("SELECT name FROM chats WHERE jid = ?", (chat_jid,)).fetchone()
        if r and r["name"]:
            return r["name"]
    except Exception:
        pass
    return chat_jid.split("@")[0]
