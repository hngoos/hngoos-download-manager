import test from 'node:test';
import assert from 'node:assert/strict';

async function fixture(response, enabled = true, policy = {}, state = 'pending', extra = {}) {
  const events = [];
  let handler;
  let created;
  const storage = {takeover: enabled, capturePolicy: policy, ...extra};
  const api = {
    downloads: {
      onCreated: {addListener(fn) { created = fn; }},
      onDeterminingFilename: {addListener(fn) { handler = fn; }},
      async pause(id) { events.push(['pause', id]); },
      async cancel(id) { events.push(['cancel', id]); },
      async resume(id) { events.push(['resume', id]); },
    },
    storage: {local: {async get() { return storage; }, async set(value) { Object.assign(storage,value); }}},
    runtime: {id: 'test-extension', async sendNativeMessage(_name, request) {
      if (request.action === 'download-status') return {ok:true,state};
      events.push(['native', request]); return response;
    }},
  };
  const {installTakeover} = await import(`../takeover.js?case=${Math.random()}`);
  const integration = installTakeover(api);
  const item = {id: 5, url: 'https://example.com/file.bin', filename: 'C:\\Downloads\\file.bin', startTime: 'now', totalBytes: 10};
  return {events, storage, integration, created() { created(item); }, async run(overrides = {}) {
    await new Promise(resolve => handler({...item, ...overrides}, () => {events.push(['suggest']); resolve();}));
  }};
}

test('takeover pauses, waits for durable native ownership, then cancels original before save prompt', async () => {
  const f = await fixture({ok: true}); await f.run();
  assert.deepEqual(f.events.map(e => e[0]), ['pause', 'native', 'cancel', 'suggest']);
  assert.equal(f.events[1][1].filename, 'file.bin');
  assert.equal(f.events[1][1].expected_size, 10);
});

test('cancel in HDM resumes the original paused browser task', async () => {
  const f = await fixture({ok:true},true,{resume_on_cancel:true},'cancelled');
  await f.run();
  assert.deepEqual(f.events.map(e=>e[0]), ['pause','native','suggest']);
  await f.integration.settle();
  assert.deepEqual(f.events.map(e=>e[0]), ['pause','native','suggest','resume']);
  assert.equal(f.storage.pendingTakeovers.length,0);
});

test('accepted HDM request cancels original only after user confirmation', async () => {
  const f = await fixture({ok:true},true,{resume_on_cancel:true},'accepted');
  await f.run();
  assert.equal(f.events.filter(e=>e[0]==='cancel').length,0);
  await f.integration.settle();
  assert.equal(f.events.filter(e=>e[0]==='cancel').length,1);
});

test('Insert bypass is scoped to the source tab and expires', async () => {
  const extra={insertBypass:{tabId:7,until:Date.now()+2000}};
  const f=await fixture({ok:true},true,{bypass_insert:true},'pending',extra);
  await f.run({tabId:7});
  assert.deepEqual(f.events.map(e=>e[0]),['suggest']);
  const other=await fixture({ok:true},true,{bypass_insert:true},'pending',extra);
  await other.run({tabId:8});
  assert.equal(other.events.filter(e=>e[0]==='native').length,1);
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
