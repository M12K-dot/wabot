require('dotenv').config();

const anthropicKey = process.env.ANTHROPIC_API_KEY || '';
const llmProvider = process.env.LLM_PROVIDER || (anthropicKey ? 'anthropic' : 'ollama');
const defaultModel = llmProvider === 'anthropic' ? 'claude-haiku-5-5' : 'qwen2.5:7b';

module.exports = {
  botName: process.env.BOT_NAME || 'NOVA',
  ownerName: process.env.OWNER_NAME || 'moi',
  prefix: process.env.PREFIX || '.',
  owners: (process.env.OWNERS || '').split(',').map((s) => s.trim().replace(/[^0-9]/g, '')).filter(Boolean),
  sessionDir: process.env.SESSION_DIR || 'session',
  pairingNumber: (process.env.PAIRING_NUMBER || '').replace(/[^0-9]/g, ''),
  showQR: (process.env.SHOW_QR || 'true') === 'true',
  processOwnMessages: (process.env.PROCESS_OWN || 'false') === 'true',

  // --- IA ---
  llmProvider,
  ollamaUrl: process.env.OLLAMA_URL || 'http://localhost:11434',
  anthropicKey,
  aiModel: process.env.AI_MODEL || defaultModel,
  aiEnabled: llmProvider === 'ollama' ? true : !!anthropicKey,
  aiSystem: process.env.AI_SYSTEM || "Tu es NOVA, un assistant WhatsApp sympathique et concis. Reponds en francais, brievement, avec des emojis quand c'est utile.",
  aiAutoReply: (process.env.AI_AUTOREPLY || 'false') === 'true',
  personaClone: (process.env.PERSONA_CLONE || 'false') === 'true',
  historyLimit: parseInt(process.env.HISTORY_LIMIT || '30', 10),
};
