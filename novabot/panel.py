# -*- coding: utf-8 -*-
"""
NOVA Control Panel — tableau de bord web local (stdlib uniquement).
Lancement :  python panel.py   puis ouvre http://localhost:8099
"""
import json
import os
import subprocess
import sys
import threading
import urllib.request
import urllib.error
from collections import deque
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs

import novastore as ns
import plugins

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

HERE = ns.HERE
PORT = 8099

LOG = deque(maxlen=800)
BRAIN = {"proc": None, "mode": None}
LOCK = threading.Lock()


# ---------------- sante des services ----------------
def http_ok(url, timeout=3):
    try:
        urllib.request.urlopen(url, timeout=timeout)
        return True
    except urllib.error.HTTPError:
        return True
    except Exception:
        return False


def ollama_models():
    try:
        with urllib.request.urlopen(ns.ollama_url() + "/api/tags", timeout=4) as r:
            data = json.loads(r.read().decode("utf-8"))
        return [m.get("name") for m in data.get("models", []) if m.get("name")]
    except Exception:
        return []


# ---------------- contacts / messages ----------------
def _initials(name):
    name = (name or "").strip()
    if not name:
        return "?"
    if name.replace(" ", "").isdigit():
        return name[-2:]
    parts = [p for p in name.split() if p]
    if len(parts) >= 2:
        return (parts[0][0] + parts[1][0]).upper()
    return parts[0][:2].upper()


def list_contacts(q="", sort="recent"):
    contacts = ns.load_contacts()
    stats = ns.load_stats().get("per_contact", {})
    lm = ns.load_lidmap()
    out = []
    try:
        con = ns.db_connect()
        rows = con.execute(
            "SELECT jid, name, last_message_time FROM chats ORDER BY last_message_time DESC LIMIT 400"
        ).fetchall()
        con.close()
    except Exception as e:
        LOG.append("contacts erreur: " + str(e))
        rows = []
    ql = q.lower()
    for r in rows:
        jid = r["jid"]
        if not ns.is_dm(jid):
            continue
        name = r["name"] or jid.split("@")[0]
        if ql and ql not in name.lower() and ql not in jid.lower():
            continue
        canon = ns.send_recipient(jid, lm)
        ccfg = {}
        for j in ns.equiv_jids(jid, lm):
            if j in contacts:
                ccfg = contacts[j]
                break
        st = stats.get(canon, {})
        out.append({
            "jid": jid,
            "name": name,
            "number": canon.split("@")[0],
            "initials": _initials(name),
            "last": r["last_message_time"],
            "enabled": bool(ccfg.get("enabled")) if ccfg else False,
            "tone": ccfg.get("tone", "") if ccfg else "",
            "notes": ccfg.get("notes", "") if ccfg else "",
            "length": ccfg.get("length", "auto") if ccfg else "auto",
            "received": st.get("received", 0),
            "sent": st.get("sent", 0),
        })
    if sort == "name":
        out.sort(key=lambda c: c["name"].lower())
    elif sort == "enabled":
        out.sort(key=lambda c: (not c["enabled"], c["name"].lower()))
    return out


def conversation(jid, limit=40):
    lm = ns.load_lidmap()
    jids = list(ns.equiv_jids(jid, lm))
    msgs = []
    name = jid.split("@")[0]
    try:
        con = ns.db_connect()
        name = ns.chat_name(con, jid)
        ph = ",".join("?" for _ in jids)
        rows = con.execute(
            "SELECT content, is_from_me, timestamp FROM messages WHERE chat_jid IN (%s) AND content<>'' "
            "ORDER BY timestamp DESC LIMIT ?" % ph, tuple(jids) + (limit,)).fetchall()
        con.close()
        for r in reversed(rows):
            msgs.append({"from_me": bool(r["is_from_me"]), "content": r["content"], "timestamp": r["timestamp"]})
    except Exception as e:
        LOG.append("conversation erreur: " + str(e))
    return {"name": name, "messages": msgs}


# ---------------- controle du demon ----------------
def brain_running():
    p = BRAIN["proc"]
    return p is not None and p.poll() is None


def _pump(proc):
    try:
        for line in iter(proc.stdout.readline, ""):
            if not line:
                break
            LOG.append(line.rstrip("\n"))
    except Exception:
        pass


def start_brain(mode):
    with LOCK:
        if brain_running():
            return False, "deja demarre"
        args = [sys.executable, "-u", str(HERE / "brain.py")]
        if mode == "dry":
            args.append("--dry-run")
        env = dict(os.environ)
        env["PYTHONIOENCODING"] = "utf-8"
        env["PYTHONUNBUFFERED"] = "1"
        try:
            proc = subprocess.Popen(
                args, cwd=str(HERE), stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                text=True, encoding="utf-8", errors="replace", env=env,
            )
        except Exception as e:
            return False, str(e)
        BRAIN["proc"], BRAIN["mode"] = proc, mode
        threading.Thread(target=_pump, args=(proc,), daemon=True).start()
        LOG.append("=== bot demarre (mode %s) ===" % mode)
        return True, "ok"


def stop_brain():
    with LOCK:
        p = BRAIN["proc"]
        if p and p.poll() is None:
            try:
                p.terminate()
            except Exception as e:
                return False, str(e)
            LOG.append("=== bot arrete ===")
        BRAIN["proc"], BRAIN["mode"] = None, None
        return True, "ok"


def state():
    s = ns.load_settings()
    return {
        "bridge": http_ok(ns.bridge_url() + "/", 3),
        "ollama": http_ok(ns.ollama_url() + "/api/tags", 3),
        "models": ollama_models(),
        "settings": s,
        "brainRunning": brain_running(),
        "brainMode": BRAIN["mode"],
        "paused": s["paused"],
        "enabledCount": len(ns.enabled_jids()),
        "stats": ns.load_stats(),
        "log": list(LOG)[-300:],
    }


PAGE = r"""<!doctype html>
<html lang="fr"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>NOVA — Control Panel</title>
<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
<style>
:root{
  --bg:#f4f6fb;--bg2:#eaeef6;--card:#ffffff;--line:#e2e8f2;--fg:#111827;--muted:#64748b;--faint:#94a3b8;
  --accent:#10b981;--accent-ink:#ffffff;--blue:#3b82f6;--danger:#ef4444;--warn:#d97706;--ok:#22c55e;
  --ring:rgba(16,185,129,.35);--shadow:0 1px 3px rgba(16,24,40,.08),0 1px 2px rgba(16,24,40,.04);
  --me:#d1fae5;--them:#eef2f7;
}
:root[data-theme="dark"]{
  --bg:#0b0f17;--bg2:#0f1521;--card:#151c28;--line:#233044;--fg:#e8edf4;--muted:#94a3b8;--faint:#64748b;
  --accent:#2dd4a7;--accent-ink:#04120d;--blue:#60a5fa;--danger:#f87171;--warn:#fbbf24;--ok:#34d399;
  --ring:rgba(45,212,167,.4);--shadow:0 1px 2px rgba(0,0,0,.4);--me:#123a2c;--them:#1b2534;
}
*{box-sizing:border-box}
html,body{margin:0}
body{background:var(--bg);color:var(--fg);font-family:Inter,system-ui,Segoe UI,Roboto,sans-serif;line-height:1.5;-webkit-font-smoothing:antialiased}
a{color:var(--blue)}
.wrap{max-width:960px;margin:0 auto;padding:0 16px 72px}
header{position:sticky;top:0;z-index:20;background:color-mix(in srgb,var(--bg) 85%,transparent);backdrop-filter:blur(10px);border-bottom:1px solid var(--line)}
.hd{max-width:960px;margin:0 auto;padding:12px 16px;display:flex;align-items:center;gap:12px}
.logo{display:flex;align-items:center;gap:10px;font-weight:700;font-size:1.15rem;letter-spacing:-.02em}
.logo .mark{width:30px;height:30px;border-radius:9px;background:linear-gradient(135deg,var(--accent),var(--blue));display:grid;place-items:center;color:#fff;font-weight:800}
.spacer{flex:1}
.iconbtn{background:var(--card);border:1px solid var(--line);color:var(--fg);border-radius:10px;width:40px;height:36px;cursor:pointer;font-size:1rem;display:grid;place-items:center}
.pause-pill{display:flex;align-items:center;gap:8px;background:var(--card);border:1px solid var(--line);border-radius:999px;padding:5px 12px;font-size:.84rem;font-weight:600}
.tabs{display:flex;gap:4px;max-width:960px;margin:0 auto;padding:0 12px;overflow:auto}
.tab{appearance:none;border:0;background:transparent;color:var(--muted);font:inherit;font-weight:600;font-size:.9rem;padding:11px 14px;cursor:pointer;border-bottom:2px solid transparent;white-space:nowrap}
.tab[aria-selected="true"]{color:var(--fg);border-bottom-color:var(--accent)}
.tab:focus-visible{outline:2px solid var(--ring);outline-offset:-2px;border-radius:6px}
main{padding-top:20px}
.panel[hidden]{display:none}
.cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(160px,1fr));gap:12px}
.card{background:var(--card);border:1px solid var(--line);border-radius:16px;padding:16px;box-shadow:var(--shadow)}
.card h2{font-size:.98rem;margin:0 0 14px}
.stat .k{font-size:.72rem;letter-spacing:.06em;text-transform:uppercase;color:var(--muted)}
.stat .v{font-size:1.5rem;font-weight:700;margin-top:6px;display:flex;align-items:center;gap:8px;letter-spacing:-.02em}
.stat .v.sm{font-size:1.05rem;font-weight:600}
.dot{width:10px;height:10px;border-radius:50%;flex:none;box-shadow:0 0 0 3px color-mix(in srgb,currentColor 18%,transparent)}
.dot.on{background:var(--ok);color:var(--ok)}.dot.off{background:var(--danger);color:var(--danger)}
.section-title{font-size:.76rem;letter-spacing:.07em;text-transform:uppercase;color:var(--faint);margin:26px 2px 10px}
.controls{display:flex;gap:10px;flex-wrap:wrap;align-items:center}
.btn{font:inherit;font-weight:600;cursor:pointer;border:1px solid transparent;border-radius:11px;padding:10px 16px;display:inline-flex;align-items:center;gap:8px}
.btn:focus-visible{outline:2px solid var(--ring);outline-offset:2px}
.btn-primary{background:var(--accent);color:var(--accent-ink)}
.btn-blue{background:var(--blue);color:#fff}
.btn-danger{background:var(--danger);color:#fff}
.btn-ghost{background:var(--card);border-color:var(--line);color:var(--fg)}
.btn:disabled{opacity:.45;cursor:not-allowed}
.badge{font-size:.74rem;font-weight:600;padding:4px 10px;border-radius:999px;border:1px solid var(--line);background:var(--bg2);color:var(--muted)}
.badge.live{background:color-mix(in srgb,var(--ok) 16%,transparent);color:var(--ok);border-color:transparent}
.badge.dry{background:color-mix(in srgb,var(--blue) 16%,transparent);color:var(--blue);border-color:transparent}
.warnbox{margin-top:12px;font-size:.82rem;color:var(--warn);background:color-mix(in srgb,var(--warn) 10%,transparent);border:1px solid color-mix(in srgb,var(--warn) 30%,transparent);border-radius:10px;padding:9px 12px}
.toolbar{display:flex;gap:10px;flex-wrap:wrap;align-items:center;margin-bottom:12px}
input,select,textarea{font:inherit;background:var(--bg2);color:var(--fg);border:1px solid var(--line);border-radius:10px;padding:9px 11px;width:100%}
input:focus,select:focus,textarea:focus{outline:2px solid var(--ring);outline-offset:1px;border-color:transparent}
.search{flex:1;min-width:180px}
label{font-size:.82rem;color:var(--muted);display:block;margin-bottom:5px;font-weight:500}
.field{margin-bottom:14px}
.grid2{display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:0 16px}
.switch{position:relative;width:46px;height:26px;flex:none;display:inline-block}
.switch input{position:absolute;opacity:0;width:100%;height:100%;margin:0;cursor:pointer}
.switch span{position:absolute;inset:0;background:#9aa7ba;border-radius:999px;transition:.15s}
:root[data-theme="dark"] .switch span{background:#3a475c}
.switch span::before{content:"";position:absolute;width:20px;height:20px;left:3px;top:3px;background:#fff;border-radius:50%;transition:.15s;box-shadow:0 1px 2px rgba(0,0,0,.3)}
.switch input:checked+span{background:var(--accent)}
.switch input:checked+span::before{transform:translateX(20px)}
.switch input:focus-visible+span{outline:2px solid var(--ring);outline-offset:2px}
.contact{display:flex;align-items:center;gap:12px;padding:11px 12px;border:1px solid var(--line);border-radius:14px;background:var(--card);margin-bottom:9px;box-shadow:var(--shadow)}
.contact.on{border-color:color-mix(in srgb,var(--accent) 45%,var(--line))}
.ava{width:42px;height:42px;border-radius:50%;flex:none;display:grid;place-items:center;font-weight:700;color:#fff;font-size:.9rem}
.contact .meta{flex:1;min-width:0}
.contact .nm{font-weight:600;display:flex;align-items:center;gap:7px}
.contact .nm .tag{font-size:.66rem;font-weight:600;color:var(--accent);border:1px solid color-mix(in srgb,var(--accent) 40%,transparent);border-radius:6px;padding:1px 6px}
.contact .jd{font-size:.76rem;color:var(--muted);overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.contact .acts{display:flex;align-items:center;gap:6px}
.miniicon{background:var(--bg2);border:1px solid var(--line);color:var(--muted);border-radius:9px;width:34px;height:34px;cursor:pointer;display:grid;place-items:center;font-size:.95rem}
.miniicon:hover{color:var(--fg)}
#log{background:#0a0e15;color:#d7e0ec;border:1px solid var(--line);border-radius:12px;padding:12px;height:340px;overflow:auto;font-family:ui-monospace,SFMono-Regular,Menlo,monospace;font-size:.78rem;white-space:pre-wrap}
.empty{color:var(--faint);text-align:center;padding:34px 0}
.modal-bg{position:fixed;inset:0;background:rgba(5,10,20,.55);backdrop-filter:blur(2px);display:none;align-items:center;justify-content:center;z-index:50;padding:16px}
.modal-bg.open{display:flex}
.modal{background:var(--card);border:1px solid var(--line);border-radius:18px;width:100%;max-width:520px;max-height:86vh;overflow:auto;box-shadow:0 20px 50px rgba(0,0,0,.3)}
.modal .mh{display:flex;align-items:center;gap:10px;padding:16px 18px;border-bottom:1px solid var(--line);position:sticky;top:0;background:var(--card)}
.modal .mh h3{margin:0;font-size:1.02rem;flex:1}
.modal .mb{padding:18px}
.bubbles{display:flex;flex-direction:column;gap:7px}
.bub{max-width:80%;padding:8px 12px;border-radius:14px;font-size:.88rem;white-space:pre-wrap;word-break:break-word}
.bub.them{background:var(--them);align-self:flex-start;border-bottom-left-radius:4px}
.bub.me{background:var(--me);align-self:flex-end;border-bottom-right-radius:4px}
.bub .t{font-size:.64rem;color:var(--muted);margin-top:3px}
.previewbox{background:var(--me);border-radius:14px;padding:12px 14px;font-size:.95rem;white-space:pre-wrap;min-height:48px}
.spin{display:inline-block;width:16px;height:16px;border:2px solid var(--line);border-top-color:var(--accent);border-radius:50%;animation:sp .7s linear infinite;vertical-align:-3px}
@keyframes sp{to{transform:rotate(360deg)}}
.hint{font-size:.78rem;color:var(--muted);margin-top:-6px;margin-bottom:12px}
@media(max-width:560px){.hd{padding:10px 12px}.stat .v{font-size:1.25rem}}
</style></head>
<body>
<header>
  <div class="hd">
    <div class="logo"><span class="mark">N</span> NOVA</div>
    <span class="badge" id="modeBadge">—</span>
    <div class="spacer"></div>
    <label class="pause-pill" title="Suspendre les reponses sans arreter le bot">
      <span class="switch" style="width:40px;height:23px"><input type="checkbox" id="pauseTgl"><span></span></span>
      Pause
    </label>
    <button class="iconbtn" id="themeBtn" aria-label="Changer de theme" title="Theme clair/sombre">🌓</button>
  </div>
  <nav class="tabs" role="tablist" aria-label="Sections">
    <button class="tab" role="tab" data-tab="overview" aria-selected="true">Vue d'ensemble</button>
    <button class="tab" role="tab" data-tab="contacts" aria-selected="false">Contacts</button>
    <button class="tab" role="tab" data-tab="settings" aria-selected="false">Reglages</button>
    <button class="tab" role="tab" data-tab="plugins" aria-selected="false">Plugins</button>
    <button class="tab" role="tab" data-tab="automations" aria-selected="false">Automations</button>
    <button class="tab" role="tab" data-tab="log" aria-selected="false">Journal</button>
  </nav>
</header>

<main class="wrap">
  <!-- OVERVIEW -->
  <section class="panel" id="p-overview" role="tabpanel">
    <div class="cards" id="statusCards"></div>

    <div class="section-title">Controle du bot</div>
    <div class="card">
      <div class="controls">
        <button class="btn btn-blue" id="bDry">▶ Test (dry-run)</button>
        <button class="btn btn-primary" id="bReal">▶ Reel</button>
        <button class="btn btn-danger" id="bStop">■ Arreter</button>
        <span class="badge" id="botBadge">Arrete</span>
      </div>
      <div class="warnbox">En mode <b>reel</b>, NOVA envoie de vrais messages aux contacts actives. Liste blanche vide par defaut.</div>
    </div>

    <div class="section-title">Statistiques</div>
    <div class="cards" id="statsCards"></div>
  </section>

  <!-- CONTACTS -->
  <section class="panel" id="p-contacts" role="tabpanel" hidden>
    <div class="toolbar">
      <input class="search" id="q" placeholder="Rechercher un contact..." aria-label="Rechercher">
      <select id="sort" style="width:auto" aria-label="Tri">
        <option value="recent">Recents</option>
        <option value="name">Nom</option>
        <option value="enabled">Actives d'abord</option>
      </select>
      <span class="badge" id="cCount">—</span>
    </div>
    <div id="contacts"></div>
  </section>

  <!-- SETTINGS -->
  <section class="panel" id="p-settings" role="tabpanel" hidden>
    <div class="card">
      <h2>Identite & modele</h2>
      <div class="grid2">
        <div class="field"><label for="s_owner">Ton nom (signature du style)</label><input id="s_owner"></div>
        <div class="field"><label for="s_model">Modele Ollama</label><select id="s_model"></select></div>
        <div class="field"><label for="s_hist">Historique injecte (messages)</label><input id="s_hist" type="number" min="5" max="200"></div>
        <div class="field"><label for="s_poll">Intervalle de verification (s)</label><input id="s_poll" type="number" min="1" max="30"></div>
      </div>
    </div>
    <div class="card">
      <h2>Comportement humain</h2>
      <div class="grid2">
        <div class="field"><label for="s_dmin">Delai min avant reponse (s)</label><input id="s_dmin" type="number" min="0" max="120"></div>
        <div class="field"><label for="s_dmax">Delai max avant reponse (s)</label><input id="s_dmax" type="number" min="0" max="300"></div>
      </div>
      <label style="display:flex;align-items:center;gap:10px;cursor:pointer"><span class="switch"><input type="checkbox" id="s_typing"><span></span></span> Simuler le temps de frappe (delai selon la longueur)</label>
    </div>
    <div class="card">
      <h2>Disponibilite</h2>
      <label style="display:flex;align-items:center;gap:10px;cursor:pointer;margin-bottom:12px"><span class="switch"><input type="checkbox" id="s_hours"><span></span></span> Limiter a une plage horaire</label>
      <div class="grid2">
        <div class="field"><label for="s_start">Debut</label><input id="s_start" type="time"></div>
        <div class="field"><label for="s_end">Fin</label><input id="s_end" type="time"></div>
      </div>
      <label style="display:flex;align-items:center;gap:10px;cursor:pointer;margin-bottom:10px"><span class="switch"><input type="checkbox" id="s_vac"><span></span></span> Mode vacances (reponse automatique fixe)</label>
      <div class="field"><label for="s_vacmsg">Message de vacances</label><textarea id="s_vacmsg" rows="2" placeholder="ex: suis pas dispo la, je te rappelle 👋"></textarea></div>
    </div>
    <div class="card">
      <h2>Securite & limites</h2>
      <div class="field"><label for="s_rate">Reponses max par contact et par heure</label><input id="s_rate" type="number" min="1" max="120"></div>
      <label style="display:flex;align-items:center;gap:10px;cursor:pointer;margin-bottom:10px"><span class="switch"><input type="checkbox" id="s_groups"><span></span></span> Autoriser les groupes (deconseille)</label>
      <label style="display:flex;align-items:center;gap:10px;cursor:pointer"><span class="switch"><input type="checkbox" id="s_all"><span></span></span> Repondre a TOUTES les discussions privees</label>
      <div class="warnbox">« Toutes les discussions » ignore la liste blanche et repond a tout le monde. A utiliser avec prudence.</div>
    </div>
    <div class="card">
      <h2>Fiabilite & intelligence</h2>
      <div class="grid2">
        <div class="field"><label for="s_turns">Tours de conversation envoyes au modele</label><input id="s_turns" type="number" min="4" max="60"></div>
        <div class="field"><label for="s_deb">Regroupement des rafales / debounce (s)</label><input id="s_deb" type="number" min="0" max="60"></div>
      </div>
      <label style="display:flex;align-items:center;gap:10px;cursor:pointer;margin-bottom:10px"><span class="switch"><input type="checkbox" id="s_skipu"><span></span></span> Garde-fou « pas sur » : ne rien envoyer si incertain (recommande)</label>
      <label style="display:flex;align-items:center;gap:10px;cursor:pointer"><span class="switch"><input type="checkbox" id="s_skipq"><span></span></span> Laisser les questions factuelles (prix, rdv, adresse…) a toi</label>
    </div>
    <div class="card">
      <h2>Comportement (Levanter)</h2>
      <div class="grid2">
        <div class="field" style="max-width:160px"><label for="s_warn">Warn limit (auto-kick)</label><input id="s_warn" type="number" min="1" max="20"></div>
        <div class="field"><label for="s_pack">Nom du pack sticker</label><input id="s_pack"></div>
      </div>
      <label style="display:flex;align-items:center;gap:10px;cursor:pointer;margin-bottom:8px"><span class="switch"><input type="checkbox" id="s_creact"><span></span></span> Reagir aux commandes (cmd-reaction)</label>
      <label style="display:flex;align-items:center;gap:10px;cursor:pointer"><span class="switch"><input type="checkbox" id="s_mentauto"><span></span></span> Auto-mention</label>
    </div>
    <div class="controls" style="margin-top:4px">
      <button class="btn btn-primary" id="bSave">Enregistrer les reglages</button>
      <span id="saveMsg" class="badge" hidden>Enregistre ✓</span>
    </div>
  </section>

  <!-- PLUGINS -->
  <section class="panel" id="p-plugins" role="tabpanel" hidden>
    <div class="card">
      <h2>Commandes</h2>
      <div class="field" style="max-width:160px"><label for="pf_prefix">Prefixe de commande</label><input id="pf_prefix" maxlength="3"></div>
      <label style="display:flex;align-items:center;gap:10px;cursor:pointer;margin-bottom:10px"><span class="switch"><input type="checkbox" id="pf_enabled"><span></span></span> Activer le systeme de commandes</label>
      <label style="display:flex;align-items:center;gap:10px;cursor:pointer;margin-bottom:10px"><span class="switch"><input type="checkbox" id="pf_owner"><span></span></span> Commandes reservees au proprietaire (toi)</label>
      <label style="display:flex;align-items:center;gap:10px;cursor:pointer"><span class="switch"><input type="checkbox" id="pf_others"><span></span></span> Autoriser les autres contacts actives</label>
      <div class="controls" style="margin-top:12px"><button class="btn btn-primary" id="pfSave">Enregistrer</button><span id="pfMsg" class="badge" hidden>Enregistre ✓</span></div>
    </div>
    <div class="toolbar"><input class="search" id="plugq" placeholder="Rechercher une commande..." aria-label="Rechercher"><span class="badge" id="plugCount">—</span></div>
    <div id="pluglist"></div>
  </section>

  <!-- AUTOMATIONS -->
  <section class="panel" id="p-automations" role="tabpanel" hidden>
    <div class="card">
      <h2>AFK (absence)</h2>
      <label style="display:flex;align-items:center;gap:10px;cursor:pointer;margin-bottom:12px"><span class="switch"><input type="checkbox" id="afk_on"><span></span></span> Je suis absent (auto-reponse)</label>
      <div class="grid2">
        <div class="field"><label for="afk_reason">Raison</label><input id="afk_reason" placeholder="ex: en reunion, je reviens"></div>
        <div class="field" style="max-width:170px"><label for="afk_cd">Anti-spam (min / contact)</label><input id="afk_cd" type="number" min="1" max="1440"></div>
      </div>
      <button class="btn btn-primary" id="afkSave">Enregistrer AFK</button>
      <div class="hint" style="margin-top:8px">Se desactive automatiquement des que tu envoies un message.</div>
    </div>

    <div class="card">
      <h2>Filtres (auto-reponses par mot-cle)</h2>
      <div class="grid2">
        <div class="field"><label for="flt_trig">Declencheur</label><input id="flt_trig" placeholder="bonjour"></div>
        <div class="field"><label for="flt_rep">Reponse</label><input id="flt_rep" placeholder="salut 👋"></div>
      </div>
      <div class="row" style="margin-bottom:10px">
        <select id="flt_mode" style="width:auto"><option value="contains">contient</option><option value="exact">exact</option></select>
        <button class="btn btn-primary" id="fltAdd">Ajouter (global)</button>
      </div>
      <div id="fltList"></div>
    </div>

    <div class="card">
      <h2>Rappels programmes</h2>
      <div class="hint">Cree-les depuis un chat : <code>.reminder 10m message</code></div>
      <div id="remList"></div>
    </div>

    <div class="card">
      <h2>Sudo (numeros autorises a lancer les commandes)</h2>
      <div class="row" style="margin-bottom:10px">
        <input id="sudo_num" class="search" placeholder="237xxxxxxxxx" style="min-width:160px">
        <button class="btn btn-primary" id="sudoAdd">Ajouter</button>
      </div>
      <div id="sudoList"></div>
    </div>

    <div class="card">
      <h2>Anti-suppression / Anti-edition</h2>
      <label style="display:flex;align-items:center;gap:10px;cursor:pointer;margin-bottom:10px"><span class="switch"><input type="checkbox" id="ad_on"><span></span></span> Antidelete — recuperer les messages supprimes</label>
      <label style="display:flex;align-items:center;gap:10px;cursor:pointer;margin-bottom:10px"><span class="switch"><input type="checkbox" id="ad_chat"><span></span></span> Poster dans le chat (sinon : en prive, a toi)</label>
      <label style="display:flex;align-items:center;gap:10px;cursor:pointer"><span class="switch"><input type="checkbox" id="ae_on"><span></span></span> Antiedit — notifier les messages modifies</label>
      <div class="hint" style="margin-top:8px">Necessite le journal d'evenements du bridge (events.jsonl).</div>
    </div>

    <div class="card">
      <h2>Welcome / Goodbye (par groupe)</h2>
      <div class="hint">Depuis le groupe : <code>.welcome on bienvenue {user} dans {group}</code> · <code>.goodbye on</code></div>
      <div id="greetList"></div>
    </div>
  </section>

  <!-- LOG -->
  <section class="panel" id="p-log" role="tabpanel" hidden>
    <div class="toolbar">
      <input class="search" id="logFilter" placeholder="Filtrer le journal..." aria-label="Filtrer">
      <button class="btn btn-ghost" id="logPause">⏸ Pause defilement</button>
      <button class="btn btn-ghost" id="logClear">Effacer l'affichage</button>
    </div>
    <div id="log" aria-live="polite"></div>
  </section>
</main>

<!-- MODAL -->
<div class="modal-bg" id="modalBg" role="dialog" aria-modal="true">
  <div class="modal">
    <div class="mh"><h3 id="modalTitle">—</h3><button class="iconbtn" id="modalClose" aria-label="Fermer">✕</button></div>
    <div class="mb" id="modalBody"></div>
  </div>
</div>

<script>
const $=s=>document.querySelector(s), $$=s=>document.querySelectorAll(s);
const esc=s=>(s||'').replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
async function api(p,opt){try{const r=await fetch(p,opt);return await r.json();}catch(e){return {};}}
function avatarColor(s){let h=0;for(let i=0;i<(s||'').length;i++)h=(h*31+s.charCodeAt(i))>>>0;return 'hsl('+(h%360)+' 55% 45%)';}
function fmtTime(ts){try{const d=new Date(ts.replace(' ','T'));if(isNaN(d))return ts||'';return d.toLocaleString('fr-FR',{day:'2-digit',month:'2-digit',hour:'2-digit',minute:'2-digit'});}catch(e){return ts||'';}}

/* THEME */
const root=document.documentElement;
function setTheme(t){root.setAttribute('data-theme',t);try{localStorage.setItem('nova-theme',t);}catch(e){}}
(function(){let t='dark';try{t=localStorage.getItem('nova-theme')|| (matchMedia('(prefers-color-scheme: dark)').matches?'dark':'light');}catch(e){}setTheme(t);})();
$('#themeBtn').onclick=()=>setTheme(root.getAttribute('data-theme')==='dark'?'light':'dark');

/* TABS */
$$('.tab').forEach(t=>t.onclick=()=>{
  $$('.tab').forEach(x=>x.setAttribute('aria-selected',x===t));
  $$('.panel').forEach(p=>p.hidden=true);
  $('#p-'+t.dataset.tab).hidden=false;
  if(t.dataset.tab==='contacts')loadContacts();
  if(t.dataset.tab==='plugins')loadPlugins();
  if(t.dataset.tab==='automations')loadAutomations();
});

/* STATE */
let MODELS=[], SETTINGS={};
function stat(k,v,cls){return '<div class="card stat"><div class="k">'+k+'</div><div class="v '+(cls||'')+'">'+v+'</div></div>';}
function dot(b){return '<span class="dot '+(b?'on':'off')+'"></span>';}
async function refresh(){
  const s=await api('/api/state'); if(!s.settings)return; SETTINGS=s.settings; MODELS=s.models||[];
  $('#statusCards').innerHTML=
    stat('Bridge WhatsApp',dot(s.bridge)+(s.bridge?'En ligne':'Hors ligne'),'sm')+
    stat('Ollama',dot(s.ollama)+(s.ollama?'En ligne':'Hors ligne'),'sm')+
    stat('Bot',dot(s.brainRunning)+(s.brainRunning?('Actif'):'Arrete'),'sm')+
    stat('Contacts actives',s.enabledCount);
  const st=s.stats||{};
  $('#statsCards').innerHTML=
    stat("Recus aujourd'hui",st.today_received||0)+
    stat("Envoyes aujourd'hui",st.today_sent||0)+
    stat('Total recus',st.total_received||0)+
    stat('Total envoyes',st.total_sent||0);
  const mode=s.brainRunning?(s.brainMode==='dry'?'<span class="badge dry">● Test</span>':'<span class="badge live">● Reel</span>'):'<span class="badge">Arrete</span>';
  $('#modeBadge').outerHTML='<span class="badge" id="modeBadge">'+(s.brainRunning?(s.brainMode==='dry'?'Test':'Reel'):'Inactif')+'</span>';
  $('#botBadge').innerHTML=s.brainRunning?(s.brainMode==='dry'?'Test (dry-run)':'Reel — envoie'):'Arrete';
  $('#bDry').disabled=s.brainRunning;$('#bReal').disabled=s.brainRunning;$('#bStop').disabled=!s.brainRunning;
  if($('#pauseTgl')!==document.activeElement)$('#pauseTgl').checked=!!s.paused;
  fillSettings(s.settings);
  renderLog(s.log||[]);
}

/* SETTINGS FORM */
let settingsDirty=false;
['s_owner','s_model','s_hist','s_poll','s_dmin','s_dmax','s_typing','s_hours','s_start','s_end','s_vac','s_vacmsg','s_rate','s_groups','s_all','s_turns','s_deb','s_skipu','s_skipq','s_warn','s_pack','s_creact','s_mentauto']
  .forEach(id=>{const el=$('#'+id);if(el)el.addEventListener('input',()=>settingsDirty=true);});
function fillSettings(s){
  const sel=$('#s_model');const j=MODELS.join();if(sel.dataset.m!==j){sel.innerHTML='';(MODELS.length?MODELS:[s.model]).forEach(m=>{const o=document.createElement('option');o.value=o.textContent=m;sel.appendChild(o);});sel.dataset.m=j;}
  if(settingsDirty)return; // ne pas ecraser la saisie en cours
  $('#s_owner').value=s.owner_name;sel.value=s.model;$('#s_hist').value=s.history_limit;$('#s_poll').value=s.poll_seconds;
  $('#s_dmin').value=s.delay_min;$('#s_dmax').value=s.delay_max;$('#s_typing').checked=s.simulate_typing;
  $('#s_hours').checked=s.active_hours_enabled;$('#s_start').value=s.active_start;$('#s_end').value=s.active_end;
  $('#s_vac').checked=s.vacation_mode;$('#s_vacmsg').value=s.vacation_message;$('#s_rate').value=s.rate_per_hour;
  $('#s_groups').checked=s.allow_groups;$('#s_all').checked=s.persona_all;
  $('#s_turns').value=s.transcript_turns;$('#s_deb').value=s.debounce_seconds;
  $('#s_skipu').checked=s.skip_uncertain;$('#s_skipq').checked=s.skip_question_heuristic;
  $('#s_warn').value=s.warn_limit;$('#s_pack').value=s.sticker_packname||'';$('#s_creact').checked=s.cmd_reaction;$('#s_mentauto').checked=s.auto_mention;
}
$('#bSave').onclick=async()=>{
  const body={owner_name:$('#s_owner').value,model:$('#s_model').value,history_limit:$('#s_hist').value,poll_seconds:$('#s_poll').value,
    delay_min:$('#s_dmin').value,delay_max:$('#s_dmax').value,simulate_typing:$('#s_typing').checked,
    active_hours_enabled:$('#s_hours').checked,active_start:$('#s_start').value,active_end:$('#s_end').value,
    vacation_mode:$('#s_vac').checked,vacation_message:$('#s_vacmsg').value,rate_per_hour:$('#s_rate').value,
    allow_groups:$('#s_groups').checked,persona_all:$('#s_all').checked,
    transcript_turns:$('#s_turns').value,debounce_seconds:$('#s_deb').value,
    skip_uncertain:$('#s_skipu').checked,skip_question_heuristic:$('#s_skipq').checked,
    warn_limit:$('#s_warn').value,sticker_packname:$('#s_pack').value,cmd_reaction:$('#s_creact').checked,auto_mention:$('#s_mentauto').checked};
  await api('/api/settings',{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify(body)});
  settingsDirty=false;const m=$('#saveMsg');m.hidden=false;setTimeout(()=>m.hidden=true,1500);refresh();
};
$('#pauseTgl').onchange=async e=>{await api('/api/pause',{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify({paused:e.target.checked})});refresh();};

/* BOT CONTROL */
$('#bDry').onclick=()=>brain('start','dry');
$('#bReal').onclick=()=>{if(confirm('Mode REEL : NOVA enverra de vrais messages aux contacts actives. Continuer ?'))brain('start','real');};
$('#bStop').onclick=()=>brain('stop');
async function brain(action,mode){await api('/api/brain',{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify({action,mode})});refresh();}

/* CONTACTS */
let contactsCache=[];
async function loadContacts(){
  const q=$('#q').value, sort=$('#sort').value;
  const list=await api('/api/contacts?q='+encodeURIComponent(q)+'&sort='+sort);
  contactsCache=list;
  const en=list.filter(c=>c.enabled).length;
  $('#cCount').textContent=list.length+' discussions · '+en+' actives';
  if(!list.length){$('#contacts').innerHTML='<div class="empty">Aucun contact.</div>';return;}
  $('#contacts').innerHTML=list.map(c=>{
    const col=avatarColor(c.jid);
    return '<div class="contact '+(c.enabled?'on':'')+'" data-jid="'+esc(c.jid)+'">'+
      '<div class="ava" style="background:'+col+'">'+esc(c.initials)+'</div>'+
      '<div class="meta"><div class="nm">'+esc(c.name)+(c.enabled?' <span class="tag">ACTIF</span>':'')+'</div>'+
      '<div class="jd">'+esc(c.number)+' · '+(c.received||0)+' reçus / '+(c.sent||0)+' envoyes</div></div>'+
      '<div class="acts">'+
        '<button class="miniicon act-view" title="Voir la conversation" aria-label="Conversation">💬</button>'+
        '<button class="miniicon act-prev" title="Apercu de reponse" aria-label="Apercu">👁</button>'+
        '<button class="miniicon act-edit" title="Reglages du contact" aria-label="Reglages">⚙</button>'+
        '<label class="switch"><input type="checkbox" class="act-tgl" '+(c.enabled?'checked':'')+'><span></span></label>'+
      '</div></div>';
  }).join('');
  $$('#contacts .contact').forEach(row=>{
    const jid=row.dataset.jid;
    row.querySelector('.act-tgl').onchange=async e=>{await api('/api/toggle',{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify({jid,enabled:e.target.checked})});loadContacts();refresh();};
    row.querySelector('.act-view').onclick=()=>viewConversation(jid);
    row.querySelector('.act-prev').onclick=()=>previewReply(jid);
    row.querySelector('.act-edit').onclick=()=>editContact(jid);
  });
}
let ct;$('#q').oninput=()=>{clearTimeout(ct);ct=setTimeout(loadContacts,250);};
$('#sort').onchange=loadContacts;

/* MODAL */
function openModal(title,html){$('#modalTitle').textContent=title;$('#modalBody').innerHTML=html;$('#modalBg').classList.add('open');}
function closeModal(){$('#modalBg').classList.remove('open');}
$('#modalClose').onclick=closeModal;$('#modalBg').onclick=e=>{if(e.target===$('#modalBg'))closeModal();};
document.addEventListener('keydown',e=>{if(e.key==='Escape')closeModal();});

async function viewConversation(jid){
  openModal('Conversation','<div class="empty"><span class="spin"></span> chargement…</div>');
  const d=await api('/api/messages?jid='+encodeURIComponent(jid));
  $('#modalTitle').textContent=d.name||'Conversation';
  if(!d.messages||!d.messages.length){$('#modalBody').innerHTML='<div class="empty">Aucun message.</div>';return;}
  $('#modalBody').innerHTML='<div class="bubbles">'+d.messages.map(m=>
    '<div class="bub '+(m.from_me?'me':'them')+'">'+esc(m.content)+'<div class="t">'+fmtTime(m.timestamp)+'</div></div>').join('')+'</div>';
  const mb=$('#modalBody');mb.scrollTop=mb.scrollHeight;
}
async function previewReply(jid){
  const c=contactsCache.find(x=>x.jid===jid)||{};
  openModal('Apercu — '+(c.name||''),'<div class="hint">Reponse que NOVA genererait au dernier message (non envoyee).</div><div class="previewbox"><span class="spin"></span> generation… (peut prendre ~20s)</div>');
  const d=await api('/api/preview?jid='+encodeURIComponent(jid));
  $('#modalBody').querySelector('.previewbox').textContent=d.reply||'(pas de reponse generee)';
}
function editContact(jid){
  const c=contactsCache.find(x=>x.jid===jid)||{tone:'',notes:'',length:'auto',enabled:false};
  openModal('Reglages — '+(c.name||''),
    '<div class="field"><label>Notes sur ce contact (faits, contexte injectes au modele)</label><textarea id="c_notes" rows="3" placeholder="ex: mon cousin, vit a Douala, on parle foot et jeux">'+esc(c.notes||'')+'</textarea></div>'+
    '<div class="field"><label>Instruction de ton perso</label><textarea id="c_tone" rows="2" placeholder="ex: toujours un peu taquin avec lui">'+esc(c.tone||'')+'</textarea></div>'+
    '<div class="field"><label>Longueur des reponses</label><select id="c_len">'+
      ['auto','court','long'].map(v=>'<option value="'+v+'" '+(c.length===v?'selected':'')+'>'+v+'</option>').join('')+'</select></div>'+
    '<label style="display:flex;align-items:center;gap:10px;cursor:pointer;margin:6px 0 16px"><span class="switch"><input type="checkbox" id="c_en" '+(c.enabled?'checked':'')+'><span></span></span> Active pour ce contact</label>'+
    '<button class="btn btn-primary" id="c_save">Enregistrer</button>');
  $('#c_save').onclick=async()=>{
    await api('/api/contact',{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify({jid,tone:$('#c_tone').value,notes:$('#c_notes').value,length:$('#c_len').value,enabled:$('#c_en').checked})});
    closeModal();loadContacts();refresh();
  };
}

/* LOG */
let logPaused=false, logHidden=0;
$('#logPause').onclick=()=>{logPaused=!logPaused;$('#logPause').textContent=logPaused?'▶ Reprendre':'⏸ Pause defilement';};
$('#logClear').onclick=()=>{logHidden=lastLog.length;renderLog(lastLog);};
$('#logFilter').oninput=()=>renderLog(lastLog);
let lastLog=[];
function renderLog(lines){
  lastLog=lines;
  const f=$('#logFilter').value.toLowerCase();
  let arr=lines.slice(logHidden);
  if(f)arr=arr.filter(l=>l.toLowerCase().includes(f));
  const el=$('#log');const atBottom=el.scrollTop+el.clientHeight>=el.scrollHeight-24;
  el.textContent=arr.join('\n');
  if(!logPaused&&atBottom)el.scrollTop=el.scrollHeight;
}

/* PLUGINS */
let PLUGINS=[];
async function loadPlugins(){
  const d=await api('/api/plugins');if(!d.plugins)return;PLUGINS=d.plugins;
  if(document.activeElement!==$('#pf_prefix'))$('#pf_prefix').value=d.prefix;
  $('#pf_enabled').checked=d.commands_enabled;$('#pf_owner').checked=d.owner_only;$('#pf_others').checked=d.allow_others;
  renderPlugins();
}
function renderPlugins(){
  const q=($('#plugq').value||'').toLowerCase();const cats={};let n=0,on=0;
  PLUGINS.forEach(p=>{if(q&&!(p.name.toLowerCase().includes(q)||(p.desc||'').toLowerCase().includes(q)||p.category.toLowerCase().includes(q)))return;(cats[p.category]=cats[p.category]||[]).push(p);n++;if(p.enabled)on++;});
  $('#plugCount').textContent=n+' commandes · '+on+' actives';
  let html='';
  Object.keys(cats).sort().forEach(cat=>{
    html+='<div class="section-title">'+esc(cat)+'</div>';
    cats[cat].sort((a,b)=>a.name.localeCompare(b.name)).forEach(p=>{
      const al=(p.aliases&&p.aliases.length)?' <span class="jd" style="display:inline">('+esc(p.aliases.join(', '))+')</span>':'';
      html+='<div class="contact '+(p.enabled?'on':'')+'"><div class="meta"><div class="nm">'+esc(p.name)+al+'</div><div class="jd">'+esc(p.desc||'')+'</div></div>'+
        '<label class="switch"><input type="checkbox" data-p="'+esc(p.name)+'" '+(p.enabled?'checked':'')+'><span></span></label></div>';
    });
  });
  $('#pluglist').innerHTML=html||'<div class="empty">Aucune commande.</div>';
  $$('#pluglist input[data-p]').forEach(cb=>cb.onchange=async()=>{await api('/api/plugin',{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify({name:cb.dataset.p,enabled:cb.checked})});loadPlugins();});
}
$('#plugq').oninput=()=>renderPlugins();
$('#pfSave').onclick=async()=>{await api('/api/settings',{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify({command_prefix:$('#pf_prefix').value||'.',commands_enabled:$('#pf_enabled').checked,commands_owner_only:$('#pf_owner').checked,commands_allow_others:$('#pf_others').checked})});const m=$('#pfMsg');m.hidden=false;setTimeout(()=>m.hidden=true,1400);loadPlugins();};

/* AUTOMATIONS */
async function loadAutomations(){
  const d=await api('/api/automations');if(!d)return;
  if(document.activeElement!==$('#afk_reason')){$('#afk_on').checked=!!d.afk;$('#afk_reason').value=d.afk_reason||'';$('#afk_cd').value=d.afk_cooldown_min;}
  // filtres
  const fl=d.filters||[];
  $('#fltList').innerHTML=fl.length?fl.map(f=>{
    const sc=f.scope==='__global__'?'🌍 global':('💬 '+esc((f.scope||'').split('@')[0]));
    return '<div class="contact"><div class="meta"><div class="nm">'+esc(f.trigger)+' <span class="jd" style="display:inline">('+esc(f.mode)+')</span></div><div class="jd">'+sc+' → '+esc((f.reply||'').slice(0,50))+'</div></div>'+
      '<button class="miniicon" data-ft="'+esc(f.trigger)+'" data-fs="'+esc(f.scope)+'" title="Supprimer">🗑</button></div>';
  }).join(''):'<div class="empty">Aucun filtre.</div>';
  $$('#fltList [data-ft]').forEach(b=>b.onclick=async()=>{await api('/api/filter',{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify({action:'remove',scope:b.dataset.fs,trigger:b.dataset.ft})});loadAutomations();});
  // rappels
  const rm=d.reminders||[];
  $('#remList').innerHTML=rm.length?rm.map(r=>{
    const t=new Date((r.due||0)*1000).toLocaleString('fr-FR',{day:'2-digit',month:'2-digit',hour:'2-digit',minute:'2-digit'});
    return '<div class="contact"><div class="meta"><div class="nm">#'+esc(r.id)+' · '+t+'</div><div class="jd">'+esc((r.message||'').slice(0,60))+'</div></div>'+
      '<button class="miniicon" data-rid="'+esc(r.id)+'" title="Annuler">🗑</button></div>';
  }).join(''):'<div class="empty">Aucun rappel.</div>';
  $$('#remList [data-rid]').forEach(b=>b.onclick=async()=>{await api('/api/reminder',{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify({action:'cancel',id:b.dataset.rid})});loadAutomations();});
  // sudo
  const su=d.sudo||[];
  $('#sudoList').innerHTML=su.length?su.map(n=>'<div class="contact"><div class="meta"><div class="nm">'+esc(n)+'</div></div><button class="miniicon" data-sn="'+esc(n)+'" title="Retirer">🗑</button></div>').join(''):'<div class="empty">Aucun sudo.</div>';
  $$('#sudoList [data-sn]').forEach(b=>b.onclick=async()=>{await api('/api/sudo',{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify({action:'del',number:b.dataset.sn})});loadAutomations();});
  // anti-delete / anti-edit
  if(document.activeElement!==$('#ad_on')){$('#ad_on').checked=!!d.antidelete;$('#ad_chat').checked=!!d.antidelete_in_chat;$('#ae_on').checked=!!d.antiedit;}
  $('#ad_on').onchange=()=>api('/api/settings',{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify({antidelete:$('#ad_on').checked})});
  $('#ad_chat').onchange=()=>api('/api/settings',{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify({antidelete_in_chat:$('#ad_chat').checked})});
  $('#ae_on').onchange=()=>api('/api/settings',{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify({antiedit:$('#ae_on').checked})});
  // welcome / goodbye
  const gr=d.greets||[];
  $('#greetList').innerHTML=gr.length?gr.map((x,i)=>
    '<div class="contact" data-gi="'+i+'"><div class="meta"><div class="nm">'+(x.kind==='welcome'?'👋 Welcome':'🚪 Goodbye')+' · '+esc((x.group||'').split('@')[0])+'</div>'+
    '<input class="search gmsg" style="margin-top:6px" value="'+esc(x.msg||'')+'" placeholder="message ({user} {group})"></div>'+
    '<label class="switch"><input type="checkbox" class="gon" '+(x.on?'checked':'')+'><span></span></label></div>'
  ).join(''):'<div class="empty">Aucun groupe configure (utilise .welcome / .goodbye dans le groupe).</div>';
  $$('#greetList .contact').forEach((row,idx)=>{const x=gr[idx];const save=()=>api('/api/greet',{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify({kind:x.kind,group:x.group,on:row.querySelector('.gon').checked,msg:row.querySelector('.gmsg').value})});row.querySelector('.gon').onchange=save;row.querySelector('.gmsg').onchange=save;});
}
$('#afkSave').onclick=async()=>{await api('/api/afk',{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify({enabled:$('#afk_on').checked,reason:$('#afk_reason').value,cooldown:$('#afk_cd').value})});loadAutomations();refresh();};
$('#fltAdd').onclick=async()=>{const t=$('#flt_trig').value.trim(),r=$('#flt_rep').value.trim();if(!t||!r)return;await api('/api/filter',{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify({scope:'__global__',trigger:t,reply:r,mode:$('#flt_mode').value})});$('#flt_trig').value='';$('#flt_rep').value='';loadAutomations();};
$('#sudoAdd').onclick=async()=>{const n=$('#sudo_num').value.trim();if(!n)return;await api('/api/sudo',{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify({action:'add',number:n})});$('#sudo_num').value='';loadAutomations();};

refresh();setInterval(refresh,3000);
</script>
</body></html>"""


# ---------------- serveur ----------------
class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _send(self, code, body, ctype="application/json"):
        if isinstance(body, (dict, list)):
            body = json.dumps(body, ensure_ascii=False)
        data = body.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", ctype + "; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _body(self):
        n = int(self.headers.get("Content-Length", 0))
        try:
            return json.loads(self.rfile.read(n).decode("utf-8")) if n else {}
        except Exception:
            return {}

    def do_GET(self):
        path = urlparse(self.path).path
        qs = parse_qs(urlparse(self.path).query)
        if path == "/" or path.startswith("/index"):
            return self._send(200, PAGE, "text/html")
        if path == "/api/state":
            return self._send(200, state())
        if path == "/api/contacts":
            return self._send(200, list_contacts(qs.get("q", [""])[0], qs.get("sort", ["recent"])[0]))
        if path == "/api/messages":
            jid = qs.get("jid", [""])[0]
            return self._send(200, conversation(jid) if jid else {"name": "", "messages": []})
        if path == "/api/preview":
            jid = qs.get("jid", [""])[0]
            reply = None
            try:
                import brain
                reply = brain.preview_reply(jid) if jid else None
            except Exception as e:
                reply = "erreur: " + str(e)
            return self._send(200, {"reply": reply})
        if path == "/api/plugins":
            s = ns.load_settings()
            dis = set(s.get("plugins_disabled", []) or [])
            items = [dict(p, enabled=(p["name"] not in dis)) for p in plugins.all_plugins()]
            return self._send(200, {
                "prefix": s.get("command_prefix", "."),
                "commands_enabled": s.get("commands_enabled", True),
                "owner_only": s.get("commands_owner_only", True),
                "allow_others": s.get("commands_allow_others", False),
                "plugins": items,
            })
        if path == "/api/automations":
            s = ns.load_settings()
            a = ns.load_automations()
            flat = []
            for scope, lst in a.get("filters", {}).items():
                for f in lst:
                    flat.append({"scope": scope, "trigger": f.get("trigger"), "reply": f.get("reply"), "mode": f.get("mode", "contains")})
            greets = []
            for kind in ("welcome", "goodbye"):
                for grp, cfg in (a.get(kind, {}) or {}).items():
                    greets.append({"kind": kind, "group": grp, "on": bool(cfg.get("on")), "msg": cfg.get("msg", "")})
            return self._send(200, {
                "afk": s.get("afk"), "afk_reason": s.get("afk_reason", ""), "afk_cooldown_min": s.get("afk_cooldown_min", 30),
                "sudo": s.get("sudo", []), "broadcast_limit": s.get("broadcast_limit", 30),
                "filters_before_persona": s.get("filters_before_persona", True),
                "antidelete": s.get("antidelete", False), "antiedit": s.get("antiedit", False),
                "antidelete_in_chat": s.get("antidelete_in_chat", False),
                "filters": flat, "reminders": a.get("reminders", []), "greets": greets,
            })
        self._send(404, {"error": "not found"})

    def do_POST(self):
        b = self._body()
        path = urlparse(self.path).path
        if path == "/api/toggle":
            ns.set_contact(b.get("jid"), {"enabled": bool(b.get("enabled"))})
            return self._send(200, {"ok": True})
        if path == "/api/contact":
            patch = {}
            if "enabled" in b:
                patch["enabled"] = bool(b["enabled"])
            if "tone" in b:
                patch["tone"] = str(b["tone"])[:400]
            if "notes" in b:
                patch["notes"] = str(b["notes"])[:800]
            if "length" in b and b["length"] in ("auto", "court", "long"):
                patch["length"] = b["length"]
            ns.set_contact(b.get("jid"), patch)
            return self._send(200, {"ok": True})
        if path == "/api/settings":
            allowed = {}
            m = {
                "owner_name": str, "model": str, "history_limit": int, "poll_seconds": int,
                "delay_min": int, "delay_max": int, "simulate_typing": bool,
                "active_hours_enabled": bool, "active_start": str, "active_end": str,
                "vacation_mode": bool, "vacation_message": str, "rate_per_hour": int,
                "allow_groups": bool, "persona_all": bool,
                "transcript_turns": int, "debounce_seconds": int,
                "skip_uncertain": bool, "skip_question_heuristic": bool,
                "command_prefix": str, "commands_enabled": bool,
                "commands_owner_only": bool, "commands_allow_others": bool,
                "afk": bool, "afk_reason": str, "afk_cooldown_min": int,
                "filters_before_persona": bool, "broadcast_limit": int,
                "antidelete": bool, "antiedit": bool, "antidelete_in_chat": bool,
                "warn_limit": int, "sticker_packname": str, "timezone": str,
                "cmd_reaction": bool, "auto_mention": bool, "alwaysonline": bool,
                "rejectcall": bool, "send_read": bool, "antibot": bool,
            }
            for k, caster in m.items():
                if k in b:
                    try:
                        allowed[k] = caster(b[k]) if caster is not bool else bool(b[k])
                    except Exception:
                        pass
            ns.save_settings(allowed)
            return self._send(200, {"ok": True})
        if path == "/api/pause":
            ns.save_settings({"paused": bool(b.get("paused"))})
            return self._send(200, {"ok": True})
        if path == "/api/plugin":
            name = b.get("name")
            s = ns.load_settings()
            dis = set(s.get("plugins_disabled", []) or [])
            if b.get("enabled"):
                dis.discard(name)
            else:
                dis.add(name)
            ns.save_settings({"plugins_disabled": sorted(dis)})
            return self._send(200, {"ok": True})
        if path == "/api/afk":
            up = {"afk": bool(b.get("enabled"))}
            if "reason" in b:
                up["afk_reason"] = str(b["reason"])[:300]
            if "cooldown" in b:
                try:
                    up["afk_cooldown_min"] = int(b["cooldown"])
                except Exception:
                    pass
            ns.save_settings(up)
            return self._send(200, {"ok": True})
        if path == "/api/filter":
            scope = b.get("scope") or ns.GLOBAL_KEY
            if b.get("action") == "remove":
                n = ns.remove_filter(scope, b.get("trigger", ""))
                return self._send(200, {"ok": True, "removed": n})
            trig = (b.get("trigger") or "").strip()
            rep = (b.get("reply") or "").strip()
            if not trig or not rep:
                return self._send(200, {"ok": False, "msg": "trigger/reply requis"})
            ns.add_filter(scope, trig, rep, b.get("mode", "contains"))
            return self._send(200, {"ok": True})
        if path == "/api/reminder":
            if b.get("action") == "cancel":
                n = ns.cancel_reminder(b.get("id", ""))
                return self._send(200, {"ok": True, "removed": n})
            return self._send(200, {"ok": False})
        if path == "/api/sudo":
            num = "".join(c for c in str(b.get("number", "")) if c.isdigit())
            cur = set(ns.load_settings().get("sudo", []))
            if b.get("action") == "del":
                cur.discard(num)
            elif num:
                cur.add(num)
            ns.save_settings({"sudo": sorted(cur)})
            return self._send(200, {"ok": True})
        if path == "/api/greet":
            kind = b.get("kind")
            if kind in ("welcome", "goodbye") and b.get("group"):
                ns.set_greet(kind, b.get("group"), on=b.get("on"),
                             msg=(b.get("msg") if "msg" in b else None))
                return self._send(200, {"ok": True})
            return self._send(200, {"ok": False})
        if path == "/api/brain":
            if b.get("action") == "start":
                ok, msg = start_brain("dry" if b.get("mode") == "dry" else "real")
            else:
                ok, msg = stop_brain()
            return self._send(200, {"ok": ok, "msg": msg})
        self._send(404, {"error": "not found"})


def main():
    print("NOVA Control Panel  ->  http://localhost:%d" % PORT)
    print("(Ctrl+C pour arreter le panneau)")
    ThreadingHTTPServer(("127.0.0.1", PORT), Handler).serve_forever()


if __name__ == "__main__":
    main()
