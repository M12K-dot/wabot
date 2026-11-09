module.exports.commands = [
  {
    name: 'ping',
    command: 'ping',
    desc: 'Teste la latence',
    category: 'General',
    handler: async (ctx) => { const t = Date.now(); await ctx.reply('Pong! ' + (Date.now() - t) + ' ms'); },
  },
  {
    name: 'alive',
    command: 'alive',
    desc: 'Statut du bot',
    category: 'General',
    handler: async (ctx) => {
      const up = process.uptime();
      const h = Math.floor(up / 3600), m = Math.floor((up % 3600) / 60), s = Math.floor(up % 60);
      await ctx.reply('✅ *' + ctx.config.botName + '* en ligne\n⏱️ Uptime: ' + h + 'h ' + m + 'm ' + s + 's');
    },
  },
];
