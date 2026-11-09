// Memoire de conversation PAR contact : alimente le clone de style et garde le contexte.
// Chaque entree: { t: <epoch ms>, fromMe: <bool>, name: <string>, text: <string> }
const fs = require('fs');
const path = require('path');

const dir = path.join(__dirname, '..', 'data', 'chats');
const MAX = 800;

function ensure() { if (!fs.existsSync(dir)) fs.mkdirSync(dir, { recursive: true }); }
function fileFor(chat) { return path.join(dir, String(chat).replace(/[^a-zA-Z0-9@._-]/g, '_') + '.json'); }
function read(chat) {
  ensure();
  const f = fileFor(chat);
  if (!fs.existsSync(f)) return [];
  try { return JSON.parse(fs.readFileSync(f, 'utf8') || '[]'); } catch (e) { return []; }
}
function write(chat, arr) { ensure(); fs.writeFileSync(fileFor(chat), JSON.stringify(arr.slice(-MAX))); }

function log(chat, entry) {
  if (!entry || !entry.text) return;
  const a = read(chat);
  const last = a[a.length - 1];
  if (last && last.text === entry.text && last.fromMe === entry.fromMe) return; // anti-doublon simple
  a.push(entry);
  write(chat, a);
}
function logMany(chat, entries) {
  if (!entries || !entries.length) return;
  const a = read(chat);
  for (const e of entries) if (e && e.text) a.push(e);
  write(chat, a);
}
function getHistory(chat, limit = 30) { return read(chat).slice(-limit); }

module.exports = { log, logMany, getHistory, read };
