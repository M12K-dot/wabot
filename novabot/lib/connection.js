// Socket Baileys : auth multi-fichiers, QR ou code d'association, reconnexion, historique.
const {
  default: makeWASocket,
  useMultiFileAuthState,
  DisconnectReason,
  fetchLatestBaileysVersion,
  makeCacheableSignalKeyStore,
  Browsers,
} = require('@whiskeysockets/baileys');
const { Boom } = require('@hapi/boom');
const pino = require('pino');
const qrcode = require('qrcode-terminal');
const path = require('path');

const config = require('../config');
const { loadPlugins } = require('./plugins');
const { createHandler } = require('./handler');

const logger = pino({ level: 'silent' });
let reconnectTimer = null;

async function startSock() {
  const { state, saveCreds } = await useMultiFileAuthState(path.join(__dirname, '..', config.sessionDir));
  const { version } = await fetchLatestBaileysVersion();
  const plugins = loadPlugins();

  console.log('\n🤖 ' + config.botName + ' — ' + plugins.commandCount + ' commandes chargees');
  console.log('   prefixe: ' + config.prefix + ' | proprietaire(s): ' + (config.owners.join(', ') || '(aucun)'));
  console.log('   clone de style: ' + (config.personaClone ? 'ACTIVE' : 'off') + ' | auto-reponse: ' + (config.aiAutoReply ? 'on' : 'off') + '\n');

  const sock = makeWASocket({
    version,
    auth: { creds: state.creds, keys: makeCacheableSignalKeyStore(state.keys, logger) },
    logger,
    printQRInTerminal: false,
    browser: Browsers.macOS('Desktop'),
    markOnlineOnConnect: false,
    syncFullHistory: true,
  });

  if (config.pairingNumber && !sock.authState.creds.registered) {
    setTimeout(async () => {
      try {
        const code = await sock.requestPairingCode(config.pairingNumber);
        const pretty = (code && code.match(/.{1,4}/g)) ? code.match(/.{1,4}/g).join('-') : code;
        console.log('\n🔑 Code d\'association: ' + pretty);
        console.log('   WhatsApp → Appareils connectes → Lier un appareil → Lier avec le numero\n');
      } catch (e) { console.error('Code d\'association impossible:', e.message); }
    }, 3000);
  }

  sock.ev.on('creds.update', saveCreds);

  const handler = createHandler(sock, plugins);
  sock.ev.on('messages.upsert', handler.onMessages);
  sock.ev.on('messaging-history.set', handler.onHistory);
  sock.ev.on('group-participants.update', handler.onGroupUpdate);

  sock.ev.on('connection.update', (update) => {
    const { connection, lastDisconnect, qr } = update;
    if (qr && config.showQR && !config.pairingNumber) {
      console.log('\n📱 Scanne ce QR avec WhatsApp (Appareils connectes → Lier un appareil):\n');
      qrcode.generate(qr, { small: true });
    }
    if (connection === 'close') {
      const b = new Boom(lastDisconnect && lastDisconnect.error);
      const statusCode = b.output ? b.output.statusCode : undefined;
      if (statusCode === DisconnectReason.loggedOut) {
        console.log('❌ Session invalide. Supprime le dossier "' + config.sessionDir + '" puis relance.');
      } else {
        console.log('⚠️  Connexion fermee (' + statusCode + '). Reconnexion dans 20s…');
        if (!reconnectTimer) { reconnectTimer = setTimeout(() => { reconnectTimer = null; startSock(); }, 20000); }
      }
    } else if (connection === 'open') {
      console.log('✅ ' + config.botName + ' est connecte a WhatsApp !');
    }
  });

  return sock;
}

module.exports = { startSock };
