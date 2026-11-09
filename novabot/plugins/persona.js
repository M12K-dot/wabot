// Active/desactive le clone de style par discussion.
module.exports.commands = [{
  name: 'persona',
  command: 'persona',
  desc: 'Clone de style par discussion (on/off) — repond a ta place',
  category: 'IA',
  handler: async (ctx) => {
    const v = (ctx.args[0] || '').toLowerCase();
    if (v !== 'on' && v !== 'off') {
      const cur = ctx.store.get('persona:' + ctx.chat, ctx.config.personaClone);
      return ctx.reply('🧬 Clone de style: *' + (cur ? 'active' : 'off') + '* ici.\nUtilisation: ' + ctx.config.prefix + 'persona on|off');
    }
    ctx.store.set('persona:' + ctx.chat, v === 'on');
    await ctx.reply('🧬 Clone de style *' + (v === 'on' ? 'active' : 'desactive') + '* pour cette discussion.');
  },
}];
