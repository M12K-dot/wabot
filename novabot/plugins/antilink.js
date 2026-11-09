const store = require('../lib/store');

const linkRe = /(https?:\/\/)|(chat\.whatsapp\.com\/)|(wa\.me\/)|(t\.me\/)|([\w-]+\.(com|net|org|io|xyz|me|ng|cm|fr)\b)/i;
const key = (chat) => 'antilink:' + chat;

module.exports.commands = [{
  name: 'antilink',
  command: 'antilink',
  desc: "Active/desactive l'anti-lien (on/off)",
  category: 'Groupe',
  groupOnly: true,
  handler: async (ctx) => {
    const v = (ctx.args[0] || '').toLowerCase();
    if (v !== 'on' && v !== 'off') return ctx.reply('Utilisation: ' + ctx.config.prefix + 'antilink on|off');
    store.set(key(ctx.chat), v === 'on');
    await ctx.reply('🔗 Anti-lien *' + (v === 'on' ? 'active' : 'desactive') + '* pour ce groupe.');
  },
}];

module.exports.onMessage = async (ctx) => {
  if (!ctx.isGroup) return;
  if (!store.get('antilink:' + ctx.chat, false)) return;
  if (ctx.isOwner) return;
  if (!ctx.body || !linkRe.test(ctx.body)) return;
  try {
    await ctx.sock.sendMessage(ctx.chat, { delete: ctx.msg.key });
    await ctx.sock.sendMessage(ctx.chat, { text: '⚠️ @' + ctx.senderNum + ' les liens sont interdits ici.', mentions: [ctx.sender] });
  } catch (e) { /* bot non admin */ }
  return true;
};
