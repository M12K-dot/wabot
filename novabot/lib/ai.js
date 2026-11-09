// Pont IA multi-fournisseur : Ollama (local, gratuit) par defaut, Anthropic si cle fournie.
const config = require('../config');

async function anthropicChat(system, messages, maxTokens) {
  const res = await fetch('https://api.anthropic.com/v1/messages', {
    method: 'POST',
    headers: {
      'x-api-key': config.anthropicKey,
      'anthropic-version': '2023-06-01',
      'content-type': 'application/json',
    },
    body: JSON.stringify({ model: config.aiModel, max_tokens: maxTokens || 500, system, messages }),
  });
  if (!res.ok) { console.error('Anthropic HTTP', res.status, (await res.text()).slice(0, 300)); return null; }
  const data = await res.json();
  return (data.content || []).map((b) => b.text || '').join('').trim() || null;
}

async function ollamaChat(system, messages, maxTokens) {
  const msgs = [{ role: 'system', content: system }, ...messages];
  const url = config.ollamaUrl.replace(/\/$/, '') + '/v1/chat/completions';
  const res = await fetch(url, {
    method: 'POST',
    headers: { 'content-type': 'application/json' },
    body: JSON.stringify({ model: config.aiModel, messages: msgs, max_tokens: maxTokens || 500, temperature: 0.8, stream: false }),
  });
  if (!res.ok) { console.error('Ollama HTTP', res.status, (await res.text()).slice(0, 300)); return null; }
  const data = await res.json();
  const c = data.choices && data.choices[0] && data.choices[0].message && data.choices[0].message.content;
  return (c || '').trim() || null;
}

async function chat(system, messages, maxTokens) {
  try {
    if (config.llmProvider === 'anthropic') {
      if (!config.anthropicKey) return null;
      return await anthropicChat(system, messages, maxTokens);
    }
    return await ollamaChat(system, messages, maxTokens);
  } catch (e) { console.error('IA erreur:', e.message); return null; }
}

async function askAI(userText, system) {
  return chat(system || config.aiSystem, [{ role: 'user', content: userText }], 600);
}

async function personaReply({ ownerName, contactName, history }) {
  const system =
    'Tu es ' + ownerName + ', un humain qui discute sur WhatsApp avec ' + (contactName || 'un contact') + '. ' +
    'Reponds toi-meme, a la premiere personne, EXACTEMENT comme ' + ownerName + ' le ferait avec cette personne : ' +
    'meme ton, meme vocabulaire, meme longueur de messages, meme langue (francais / anglais / argot), ' +
    'et surtout le MEME usage des emojis que dans les messages precedents. ' +
    'Reste parfaitement coherent avec tout l historique (ne perds jamais le fil). ' +
    'Ne revele jamais que tu es une IA, un bot ou un assistant. ' +
    'Ecris uniquement le message a envoyer, sans guillemets, sans prefixe, sans explication.';

  const messages = [];
  for (const h of history) {
    if (!h.text) continue;
    const role = h.fromMe ? 'assistant' : 'user';
    if (messages.length && messages[messages.length - 1].role === role) {
      messages[messages.length - 1].content += '\n' + h.text;
    } else {
      messages.push({ role, content: h.text });
    }
  }
  while (messages.length && messages[0].role !== 'user') messages.shift();
  if (!messages.length || messages[messages.length - 1].role !== 'user') return null;

  return chat(system, messages, 400);
}

module.exports = { askAI, personaReply, chat };
