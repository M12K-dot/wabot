module.exports.commands = [{
  name: 'tagall',
  command: 'tagall',
  desc: 'Mentionne tous les membres',
  category: 'Groupe',
  groupOnly: true,
  handler: async (ctx) => {
    const meta = await ctx.sock.groupMetadata(ctx.chat);
    const mentions = meta.participants.map((p) => p.id);
    const titre = ctx.text || 'Annonce 📢';
    let out = '*' + titre + '*\n\n';
    for (const p of meta.participants) out += '• @' + p.id.split('@')[0] + '\n';
    await ctx.sock.sendMessage(ctx.chat, { text: out, mentions });
  },
}];
