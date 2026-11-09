// Restauration de la session WhatsApp depuis une variable d'environnement.
// Permet d'appairer en local (IP residentielle) puis de deployer la session
// sur un hebergeur cloud (ex. Railway) ou WhatsApp refuse un premier appairage.
const fs = require('fs');
const path = require('path');

/**
 * Si la variable WA_SESSION_B64 est definie et que le dossier de session est
 * vide (pas de creds.json), ecrit les fichiers de session decodes dedans.
 * @param {string} sessionDir chemin absolu du dossier de session
 * @returns {boolean} true si une session a ete restauree
 */
function restoreSessionFromEnv(sessionDir) {
  const b64 = process.env.WA_SESSION_B64;
  if (!b64) return false;

  const credsPath = path.join(sessionDir, 'creds.json');
  if (fs.existsSync(credsPath)) return false; // session deja presente, on ne touche pas

  try {
    fs.mkdirSync(sessionDir, { recursive: true });
    const map = JSON.parse(Buffer.from(b64, 'base64').toString('utf8'));
    let count = 0;
    for (const [name, content] of Object.entries(map)) {
      // securite: pas de chemins relatifs qui sortent du dossier
      const safe = path.basename(name);
      fs.writeFileSync(path.join(sessionDir, safe), Buffer.from(content, 'base64'));
      count++;
    }
    console.log('🔐 Session WhatsApp restauree depuis WA_SESSION_B64 (' + count + ' fichiers).');
    return true;
  } catch (e) {
    console.error('Restauration de session impossible:', e.message);
    return false;
  }
}

module.exports = { restoreSessionFromEnv };
