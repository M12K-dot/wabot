const { test } = require('node:test');
const assert = require('node:assert');
const { getText } = require('../lib/handler');

test('getText lit un message texte simple', () => {
  assert.strictEqual(getText({ message: { conversation: 'salut' } }), 'salut');
});
test('getText lit une legende image', () => {
  assert.strictEqual(getText({ message: { imageMessage: { caption: 'photo' } } }), 'photo');
});
test('getText renvoie une chaine vide sans message', () => {
  assert.strictEqual(getText({}), '');
});
