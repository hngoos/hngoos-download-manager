import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import test from 'node:test';
import vm from 'node:vm';

test('late storage initialization preserves the result of an explicit connection test', async () => {
  const elements = Object.fromEntries(['identity', 'sources', 'status', 'ping'].map(id => [id, {textContent: ''}]));
  let finishStorage;
  const settings = new Promise(resolve => { finishStorage = resolve; });
  const chrome = {
    storage: {local: {get: () => settings}},
    runtime: {id: 'a'.repeat(32), sendMessage: async () => ({ok: true})},
  };
  const context = vm.createContext({chrome, document: {getElementById: id => elements[id]}});
  vm.runInContext(readFileSync(new URL('../options.js', import.meta.url), 'utf8'), context);
  await elements.ping.onclick();
  const result = elements.status.textContent;
  assert.ok(result.length > 0);
  finishStorage({lastError: ''});
  await settings;
  await Promise.resolve();
  assert.equal(elements.status.textContent, result);
  assert.equal(elements.ping.disabled, false);
});
