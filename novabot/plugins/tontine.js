const store = require('../lib/store');
const k = (chat) => 'tontine:' + chat;

module.exports.commands = [{
  name: 'tontine',
  command: 'tontine',
  desc: 'Cotisations: add <num> <montant> | status | reset',
  category: 'Business',
  groupOnly: true,
  handler: async (ctx) => {
    const sub = (ctx.args[0] || '').toLowerCase();
    const data = store.get(k(ctx.chat), {});

    if (sub === 'add') {
      const num = ctx.args[1];
      const montant = parseFloat(ctx.args[2]);
      if (!num || isNaN(montant)) return ctx.reply('Utilisation: ' + ctx.config.prefix + 'tontine add <numero> <montant>');
      data[num] = (data[num] || 0) + montant;
      store.set(k(ctx.chat), data);
      return ctx.reply('✅ ' + montant + ' ajoute pour ' + num + '. Total: ' + data[num]);
    }
    if (sub === 'reset') {
      if (!ctx.isOwner) return ctx.reply('🔒 Reset reserve au proprietaire.');
      store.set(k(ctx.chat), {});
      return ctx.reply('♻️ Cotisations reinitialisees.');
    }
    const entries = Object.entries(data);
    if (!entries.length) return ctx.reply('📭 Aucune cotisation. Ajoute avec: ' + ctx.config.prefix + 'tontine add <num> <montant>');
    let total = 0;
    let out = '💵 *Cotisations*\n\n';
    for (const [num, amt] of entries.sort((a, b) => b[1] - a[1])) { out += '• ' + num + ': *' + amt + '*\n'; total += amt; }
    out += '\n*Total: ' + total + '*';
    await ctx.reply(out);
  },
}];
