const Anthropic = require("@anthropic-ai/sdk");

const client = new Anthropic({ apiKey: process.env.ANTHROPIC_API_KEY });

const MODEL = process.env.CLAUDE_MODEL || "claude-haiku-5-5";

const SYSTEM_PROMPT =
  process.env.SYSTEM_PROMPT ||
  "Tu es Claude, un assistant joignable par telephone (SMS et appels vocaux). " +
    "Reponds en francais, de maniere concise, naturelle et chaleureuse, comme dans une vraie conversation. " +
    "Pas de markdown, pas de listes a puces, pas d'emojis en exces.";

// Nombre de messages (user + assistant) gardes en memoire par conversation
const MAX_HISTORY = 20;

// Memoire en RAM : cle = numero de telephone, valeur = historique de la conversation
const conversations = new Map();

function getHistory(phone) {
  if (!conversations.has(phone)) conversations.set(phone, []);
  return conversations.get(phone);
}

function remember(phone, role, content) {
  const history = getHistory(phone);
  history.push({ role, content });
  while (history.length > MAX_HISTORY) history.shift();
}

async function ask(phone, userText, { channel = "sms" } = {}) {
  remember(phone, "user", userText);

  const system =
    SYSTEM_PROMPT +
    (channel === "voice"
      ? " Canal actuel : APPEL VOCAL — ta reponse sera lue a voix haute, reste bref et fluide."
      : " Canal actuel : SMS — garde des reponses courtes (idealement moins de 320 caracteres).");

  const maxTokens = channel === "voice" ? 300 : 400;

  const response = await client.messages.create({
    model: MODEL,
    max_tokens: maxTokens,
    system,
    messages: getHistory(phone),
  });

  const reply =
    response.content
      .filter((block) => block.type === "text")
      .map((block) => block.text)
      .join(" ")
      .trim() || "Desole, je n'ai pas de reponse pour le moment.";

  remember(phone, "assistant", reply);
  return reply;
}

function reset(phone) {
  conversations.delete(phone);
}

module.exports = { ask, reset };
