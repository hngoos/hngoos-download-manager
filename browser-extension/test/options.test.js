import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import test from 'node:test';
import vm from 'node:vm';

test('options automatically discovers HDM without manual connection controls', async () => {
  const status = {textContent: ''};
  let report, cleanup;
  const chrome = {storage: {local: {get: async () => ({language: 'en', theme: 'dark'})}}};
  const context = vm.createContext({chrome, localize: () => key => key,
    document: {getElementById: id => { assert.equal(id, 'status'); return status; }},
    watchConnection: (api, callback) => { assert.equal(api, chrome); report = callback; return 'stop'; },
    addEventListener: (event, callback) => { assert.equal(event, 'pagehide'); cleanup = callback; },
  });
  const source = readFileSync(new URL('../options.js', import.meta.url), 'utf8').replace(/^import .*;\r?\n/gm, '');
  await vm.runInContext('(async () => {'+source+'})()', context);
  assert.equal(status.textContent, 'working');
  await report(true);
  assert.equal(status.textContent, 'connected');
  await report(false);
  assert.equal(status.textContent, 'offline');
  assert.equal(cleanup, 'stop');
});
