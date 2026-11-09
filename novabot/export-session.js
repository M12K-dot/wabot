// Exporte la session WhatsApp locale vers railway-session.txt (base64).
// A lancer APRES avoir appaire le bot en local (npm start), une fois connecte.
// Usage: node export-session.js
const fs = require('fs');
const path = require('path');

const sessionDir = path.join(__dirname, process.env.SESSION_DIR || 'session');
const credsPath = path.join(sessionDir, 'creds.json');

if (!fs.existsSync(credsPath)) {
  console.error("\n❌ Pas de session trouvee dans « " + sessionDir + " ».");
  console.error("   Lance d'abord `npm start`, appaire ton WhatsApp, attends le message");
  console.error("   « connecte a WhatsApp », arrete (Ctrl+C), puis relance ce script.\n");
  process.exit(1);
}

const map = {};
for (const name of fs.readdirSync(sessionDir)) {
  const p = path.join(sessionDir, name);
  if (fs.statSync(p).isFile()) {
    map[name] = fs.readFileSync(p).toString('base64');
  }
}

const b64 = Buffer.from(JSON.stringify(map)).toString('base64');
const out = path.join(__dirname, 'railway-session.txt');
fs.writeFileSync(out, b64);

console.log('\n✅ Session exportee : ' + Object.keys(map).length + ' fichiers.');
console.log('   Fichier cree : ' + out);
console.log('   Taille : ' + b64.length + ' caracteres.');
console.log('   Dis a Claude que railway-session.txt est pret.\n');
