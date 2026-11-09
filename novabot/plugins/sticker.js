const { downloadMediaMessage } = require('@whiskeysockets/baileys');

module.exports.commands = [{
  name: 'sticker',
  command: /^(sticker|s)$/,
  desc: 'Image (avec legende) -> sticker',
  category: 'Medias',
  handler: async (ctx) => {
    const img = ctx.msg.message && ctx.msg.message.imageMessage;
    if (!img) return ctx.reply('🖼️ Envoie une image avec la legende ' + ctx.config.prefix + 'sticker');
    let sharp;
    try { sharp = require('sharp'); }
    catch (e) { return ctx.reply('⚠️ Module *sharp* manquant. Installe-le: npm i sharp'); }
    const buff = await downloadMediaMessage(ctx.msg, 'buffer', {});
    const webp = await sharp(buff)
      .resize(512, 512, { fit: 'contain', background: { r: 0, g: 0, b: 0, alpha: 0 } })
      .webp().toBuffer();
    await ctx.sock.sendMessage(ctx.chat, { sticker: webp }, { quoted: ctx.msg });
  },
}];
