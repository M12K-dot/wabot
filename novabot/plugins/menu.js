const config = require('../config');

module.exports.commands = [{
  name: 'menu',
  command: 'menu',
  desc: 'Affiche toutes les commandes',
  category: 'General',
  handler: async (ctx) => {
    const byCat = {};
    for (const c of ctx.plugins.commands) {
      (byCat[c.category || 'Autre'] = byCat[c.category || 'Autre'] || []).push(c);
    }
    let out = '';
    out += '*' + config.botName + '*  (type Levanter, en mieux)\n';
    out += 'Prefixe: *' + config.prefix + '*  |  Commandes: *' + ctx.plugins.commands.length + '*\n';
    for (const cat of Object.keys(byCat).sort()) {
      out += '\n*' + cat + '*\n';
      for (const c of byCat[cat]) out += '  ' + config.prefix + c.name + ' - ' + (c.desc || '') + '\n';
    }
    await ctx.reply(out.trim());
  },
}];
