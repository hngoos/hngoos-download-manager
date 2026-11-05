import test from 'node:test';
import assert from 'node:assert/strict';

async function fixture(response, enabled = true) {
  const events = [];
  let handler;
  let created;
  const api = {
    downloads: {
      onCreated: {addListener(fn) { created = fn; }},
      onDeterminingFilename: {addListener(fn) { handler = fn; }},
      async pause(id) { events.push(['pause', id]); },
      async cancel(id) { events.push(['cancel', id]); },
      async resume(id) { events.push(['resume', id]); },
    },
    storage: {local: {async get() { return {takeover: enabled}; }, async set() {}}},
    runtime: {id: 'test-extension', async sendNativeMessage(_name, request) {
      events.push(['native', request]); return response;
    }},
  };
  const {installTakeover} = await import(`../takeover.js?case=${Math.random()}`);
  installTakeover(api);
  const item = {id: 5, url: 'https://example.com/file.bin', filename: 'C:\\Downloads\\file.bin', startTime: 'now', totalBytes: 10};
  return {events, created() { created(item); }, async run(overrides = {}) {
    await new Promise(resolve => handler({...item, ...overrides}, () => {events.push(['suggest']); resolve();}));
  }};
}

test('takeover pauses, waits for durable native ownership, then cancels original before save prompt', async () => {
  const f = await fixture({ok: true}); await f.run();
  assert.deepEqual(f.events.map(e => e[0]), ['pause', 'native', 'cancel', 'suggest']);
  assert.equal(f.events[1][1].filename, 'file.bin');
  assert.equal(f.events[1][1].expected_size, 10);
});

test('onCreated and filename events share one native request', async () => {
  const f = await fixture({ok: true}); f.created(); await f.run();
  assert.equal(f.events.filter(event => event[0] === 'native').length, 1);
  assert.equal(f.events.filter(event => event[0] === 'cancel').length, 1);
});
test('native failure resumes the browser and leaves its normal save dialog available', async () => {
  const f = await fixture({ok: false, error: 'offline'}); await f.run();
  assert.deepEqual(f.events.map(e => e[0]), ['pause', 'native', 'resume', 'suggest']);
});
test('disabled takeover and risky browser downloads are left unchanged', async () => {
  const f = await fixture({ok: true}, false); await f.run();
  assert.deepEqual(f.events, [['suggest']]);
  const risky = await fixture({ok: true}); await risky.run({danger: 'dangerous'});
  assert.deepEqual(risky.events, [['suggest']]);
});
