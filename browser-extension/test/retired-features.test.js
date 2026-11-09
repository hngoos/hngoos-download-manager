import assert from 'node:assert/strict';
import test from 'node:test';
import {removeWebsiteTools} from '../retired-features.js';

test('upgrades remove retired website scripts, rules and filter alarms while preserving download capture', async () => {
  let removedScripts, removedRules, removedKeys, clearedAlarm;
  const api = {
    scripting: {
      async getRegisteredContentScripts() { return [{id:'hdm-site-protection'}, {id:'hdm-invoice-shop'}, {id:'hdm-insert-capture'}]; },
      async unregisterContentScripts(value) { removedScripts = value.ids; },
    },
    declarativeNetRequest: {
      async getDynamicRules() { return [{id:100}, {id:101}]; },
      async updateDynamicRules(value) { removedRules = value; },
    },
    alarms: {async clear(value) { clearedAlarm = value; }},
    storage: {local: {async remove(value) { removedKeys = value; }}},
  };
  await removeWebsiteTools(api);
  assert.deepEqual(removedScripts, ['hdm-site-protection', 'hdm-invoice-shop']);
  assert.deepEqual(removedRules, {removeRuleIds:[100,101], addRules:[]});
  assert.equal(clearedAlarm, 'filters');
  assert.ok(removedKeys.includes('invoiceHosts'));
  assert.ok(!removedKeys.includes('takeover'));
});

test('cleanup does not need the retired network filtering permission', async () => {
  await removeWebsiteTools({storage:{local:{async remove(){}}}});
});
