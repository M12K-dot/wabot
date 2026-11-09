const { startSock } = require('./lib/connection');

startSock().catch((e) => {
  console.error('Erreur fatale au demarrage:', e);
  process.exit(1);
});
