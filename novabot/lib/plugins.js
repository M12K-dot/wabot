// Chargeur de plugins. Chaque fichier de /plugins peut exporter :
//   commands: [{ name, command, desc, category, ownerOnly?, groupOnly?, handler }]
//   onMessage(ctx): hook sur chaque message (retourne true pour stopper la suite)
//   onGroupUpdate(ev, ctx): hook arrivee/depart de membres
const fs = require('fs');
const path = require('path');

function loadPlugins() {
  const dir = path.join(__dirname, '..', 'plugins');
  const commands = [];
  const messageHooks = [];
  const groupHooks = [];

  for (const fileName of fs.readdirSync(dir).filter((f) => f.endsWith('.js'))) {
    const full = path.join(dir, fileName);
    try {
      delete require.cache[require.resolve(full)];
      const mod = require(full);
      if (Array.isArray(mod.commands)) {
        for (const c of mod.commands) commands.push({ ...c, plugin: fileName.replace(/\.js$/, '') });
      }
      if (typeof mod.onMessage === 'function') messageHooks.push(mod.onMessage);
      if (typeof mod.onGroupUpdate === 'function') groupHooks.push(mod.onGroupUpdate);
    } catch (e) {
      console.error('Plugin ignore (' + fileName + '):', e.message);
    }
  }
  return { commands, messageHooks, groupHooks, commandCount: commands.length };
}

module.exports = { loadPlugins };
