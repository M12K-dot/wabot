const { askAI, personaReply } = require('../lib/ai');
const config = require('../config');

module.exports.commands = [{
  name: 'ai',
  command: /^(ai|ask|bot)$/,
  desc: "Pose une question a l'IA",
  category: 'IA',
  handler: async (ctx) => {
    if (!ctx.text) return ctx.reply('❓ Utilisation: ' + ctx.config.prefix + 'ai <ta question>');
    if (!ctx.config.aiEnabled) return ctx.reply('⚠️ IA non configuree (Ollama local eteint ou cle absente).');
    await ctx.react('🤔');
    const ans = await askAI(ctx.text);
    await ctx.reply(ans || '😕 Pas de reponse (modele IA injoignable ?).');
  },
}];

module.exports.onMessage = async (ctx) => {
  const cfg = ctx.config;
  if (ctx.isGroup) return;
  if (!cfg.aiEnabled) return;
  if (ctx.msg.key.fromMe) return;
  if (!ctx.body || ctx.body.startsWith(cfg.prefix)) return;

  const globalOn = cfg.personaClone || cfg.aiAutoReply;
  const enabled = ctx.store.get('persona:' + ctx.chat, globalOn);
  if (!enabled) return;

  await ctx.react('🤔');
  let ans;
  if (cfg.personaClone) {
    const history = ctx.memory.getHistory(ctx.chat, cfg.historyLimit);
    ans = await personaReply({ ownerName: cfg.ownerName, contactName: ctx.name, history });
  } else {
    ans = await askAI(ctx.body);
  }
  if (ans) await ctx.reply(ans);
};
