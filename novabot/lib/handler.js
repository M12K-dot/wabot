// Analyse des messages, journalisation en memoire, dispatch vers les plugins.
const config = require('../config');
const store = require('./store');
const memory = require('./memory');

function getText(msg) {
  const m = msg && msg.message;
  if (!m) return '';
  return (
    m.conversation ||
    (m.extendedTextMessage && m.extendedTextMessage.text) ||
    (m.imageMessage && m.imageMessage.caption) ||
    (m.videoMessage && m.videoMessage.caption) ||
    (m.buttonsResponseMessage && m.buttonsResponseMessage.selectedButtonId) ||
    (m.listResponseMessage && m.listResponseMessage.singleSelectReply &&
      m.listResponseMessage.singleSelectReply.selectedRowId) ||
    ''
  );
}

function createHandler(sock, plugins) {
  async function handleOne(msg) {
    if (!msg.message) return;

    const chat = msg.key.remoteJid;
    if (!chat || chat === 'status@broadcast') return;

    const isGroup = chat.endsWith('@g.us');
    const sender = isGroup ? (msg.key.participant || msg.participant || '') : chat;
    const senderNum = String(sender).split('@')[0].split(':')[0];
    const body = getText(msg).trim();
    const name = msg.pushName || senderNum;
    const isOwner = config.owners.includes(senderNum);

    // Journalisation memoire : TOUS les messages (y compris les tiens) pour apprendre le style.
    if (body) {
      memory.log(chat, { t: Date.now(), fromMe: !!msg.key.fromMe, name, text: body });
    }

    // On n'AGIT pas sur nos propres messages (sauf option).
    if (msg.key.fromMe && !config.processOwnMessages) return;

    const reply = (text, extra = {}) => sock.sendMessage(chat, { text, ...extra }, { quoted: msg });
    const react = (emoji) => sock.sendMessage(chat, { react: { text: emoji, key: msg.key } });

    const ctx = {
      sock, msg, chat, isGroup, sender, senderNum, name, body, isOwner,
      reply, react, store, memory, config, plugins,
    };

    for (const hook of plugins.messageHooks) {
      try { const stop = await hook(ctx); if (stop === true) return; }
      catch (e) { console.error('onMessage:', e.message); }
    }

    if (!body.startsWith(config.prefix)) return;
    const withoutPrefix = body.slice(config.prefix.length).trim();
    if (!withoutPrefix) return;
    const parts = withoutPrefix.split(/\s+/);
    ctx.command = parts[0].toLowerCase();
    ctx.args = parts.slice(1);
    ctx.text = ctx.args.join(' ');

    for (const c of plugins.commands) {
      const match = c.command instanceof RegExp ? c.command.test(ctx.command) : c.command === ctx.command;
      if (!match) continue;
      if (c.ownerOnly && !isOwner) { await reply('🔒 Commande reservee au proprietaire.'); return; }
      if (c.groupOnly && !isGroup) { await reply('👥 Commande utilisable seulement en groupe.'); return; }
      try { await c.handler(ctx); }
      catch (e) { console.error('commande ' + ctx.command + ':', e.message); await reply('❌ Erreur: ' + e.message); }
      return;
    }
  }

  async function onMessages({ messages, type }) {
    if (type !== 'notify') return;
    for (const msg of messages) {
      try { await handleOne(msg); } catch (e) { console.error('handler:', e); }
    }
  }

  // Historique synchronise par WhatsApp a la connexion : on apprend le passe (DM uniquement).
  async function onHistory(payload) {
    const msgs = payload && payload.messages;
    if (!msgs || !msgs.length) return;
    const byChat = {};
    for (const m of msgs) {
      const chat = m.key && m.key.remoteJid;
      if (!chat || chat === 'status@broadcast' || chat.endsWith('@g.us')) continue;
      const text = getText(m);
      if (!text) continue;
      const t = (m.messageTimestamp ? Number(m.messageTimestamp) : 0) * 1000;
      (byChat[chat] = byChat[chat] || []).push({ t, fromMe: !!(m.key && m.key.fromMe), name: m.pushName || '', text });
    }
    let total = 0;
    for (const chat of Object.keys(byChat)) {
      const entries = byChat[chat].sort((a, b) => a.t - b.t);
      memory.logMany(chat, entries);
      total += entries.length;
    }
    if (total) console.log('🧠 Historique appris: ' + total + ' messages sur ' + Object.keys(byChat).length + ' discussions.');
  }

  async function onGroupUpdate(ev) {
    const ctx = { sock, store, memory, config };
    for (const hook of plugins.groupHooks) {
      try { await hook(ev, ctx); } catch (e) { console.error('onGroupUpdate:', e.message); }
    }
  }

  return { onMessages, onHistory, onGroupUpdate };
}

module.exports = { createHandler, getText };
