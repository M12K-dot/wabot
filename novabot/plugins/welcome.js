const store = require('../lib/store');

module.exports.commands = [{
  name: 'welcome',
  command: 'welcome',
  desc: 'Messages de bienvenue/adieu (on/off)',
  category: 'Groupe',
  groupOnly: true,
  handler: async (ctx) => {
    const v = (ctx.args[0] || '').toLowerCase();
    if (v !== 'on' && v !== 'off') return ctx.reply('Utilisation: ' + ctx.config.prefix + 'welcome on|off');
    store.set('welcome:' + ctx.chat, v === 'on');
    await ctx.reply('👋 Bienvenue *' + (v === 'on' ? 'activee' : 'desactivee') + '*.');
  },
}];

module.exports.onGroupUpdate = async (ev, ctx) => {
  const { id, participants, action } = ev;
  if (!ctx.store.get('welcome:' + id, false)) return;
  for (const p of participants) {
    const num = String(p).split('@')[0];
    if (action === 'add') {
      await ctx.sock.sendMessage(id, { text: '👋 Bienvenue @' + num + ' ! Tape *' + ctx.config.prefix + 'menu* pour mes commandes.', mentions: [p] });
    } else if (action === 'remove') {
      await ctx.sock.sendMessage(id, { text: '👋 @' + num + ' a quitte le groupe.', mentions: [p] });
    }
  }
};
