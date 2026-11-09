// Store JSON persistant tres simple (cle -> valeur).
const fs = require('fs');
const path = require('path');

const file = path.join(__dirname, '..', 'data', 'store.json');

function ensure() {
  const dir = path.dirname(file);
  if (!fs.existsSync(dir)) fs.mkdirSync(dir, { recursive: true });
  if (!fs.existsSync(file)) fs.writeFileSync(file, '{}');
}
function readAll() {
  ensure();
  try { return JSON.parse(fs.readFileSync(file, 'utf8') || '{}'); } catch (e) { return {}; }
}
function writeAll(obj) { ensure(); fs.writeFileSync(file, JSON.stringify(obj, null, 2)); }
function get(key, def = null) { const d = readAll(); return key in d ? d[key] : def; }
function set(key, val) { const d = readAll(); d[key] = val; writeAll(d); return val; }

module.exports = { get, set, readAll, writeAll };
