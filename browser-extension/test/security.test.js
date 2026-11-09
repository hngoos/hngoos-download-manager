import test from 'node:test';
import assert from 'node:assert/strict';

let receive;
let cookieReads = 0;
let sent;
let installed;
let optionsOpened = 0;
const menus = [];
globalThis.chrome = {
  runtime: {
    async openOptionsPage() { optionsOpened++; },
    getURL: path => `chrome-extension://fixture/${path}`,
    onInstalled: {addListener(callback) { installed = callback; }},
    onMessage: {addListener(callback) { receive = callback; }},
    async sendNativeMessage(_host, message) { sent = message; return {ok: true}; },
  },
  contextMenus: {onClicked: {addListener() {}}, async removeAll(...args) {
    assert.equal(args.length, 0, 'Promise APIs must not receive a callback'); menus.length = 0;
  }, create(menu) { menus.push(menu); }},
  alarms: {onAlarm: {addListener() {}}, create() {}},
  storage: {local: {async get() { return {useSession: true}; }, async set() {}}},
  permissions: {async contains() { return true; }},
  cookies: {async getAll() { cookieReads++; return [{name: 'session', value: 'synthetic'}]; }},
};
await import('../background.js');

test('extension installation creates both download menus through Promise APIs', async () => {
  await installed({reason:'install'});
  assert.deepEqual(menus.map(menu => menu.id), ['download-link', 'download-video']);
  assert.equal(optionsOpened, 0);
  await installed({reason:'update'});
  assert.equal(optionsOpened, 0);
});

function request(url, source) {
  return new Promise(resolve => receive({action: 'download', kind: 'video', url},
    {tab: {id: 1}, url: source}, resolve));
}

test('cross-origin video request never reads or attaches the target account session', async () => {
  cookieReads = 0;
  assert.equal((await request('https://account.example/video', 'https://other.example/page')).ok, true);
  assert.equal(cookieReads, 0);
  assert.deepEqual(sent.cookies, []);
  assert.equal(sent.referrer, 'https://other.example/');
});

test('referrer never forwards page query tokens and is omitted on HTTPS downgrade', async () => {
  await request('https://cdn.example/stream.m3u8', 'https://account.example/private?token=secret');
  assert.equal(sent.referrer, 'https://account.example/');
  await request('http://cdn.example/stream.m3u8', 'https://account.example/private');
  assert.equal(sent.referrer, '');
});

test('explicit same-origin video request can use an opted-in session', async () => {
  cookieReads = 0;
  assert.equal((await request('https://account.example/video', 'https://account.example/page')).ok, true);
  assert.equal(cookieReads, 1);
  assert.equal(sent.cookies[0].name, 'session');
});

test('retired website tools are not exposed by the extension message handler', () => {
  for (const action of ['mode', 'save-invoice', 'update-filters', 'pick-element', 'reset-site', 'stats']) {
    assert.equal(receive({action}, {tab:{id:1},url:'https://example.com'}, () => assert.fail('Unexpected response')), undefined);
  }
});

test('Chromium options page may ping the native host when its sender includes a tab', async () => {
  const result = await new Promise(resolve => receive({action: 'ping'},
    {tab: {id: 2}, url: 'chrome-extension://fixture/options.html'}, resolve));
  assert.equal(result.ok, true);
});
