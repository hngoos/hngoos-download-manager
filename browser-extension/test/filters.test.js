import test from 'node:test';
import assert from 'node:assert/strict';
import {compileFilters, protectionRules} from '../filters.js';

test('domain and scoped rules retain their restrictions; cosmetic and regex are not guessed', () => {
  const rules = compileFilters('! comment\n||ads.example^\n||track.example^$third-party\n@@||ads.example^\nsite.com##video\n/regex/\n||other.example^$script,domain=news.com', 'EasyList');
  assert.equal(rules.length, 2);
  assert.equal(rules[0].condition.urlFilter, '||track.example^');
  assert(!rules[0].condition.resourceTypes.includes('main_frame'));
  assert(!rules[0].condition.resourceTypes.includes('media'));
  assert.deepEqual(rules[1].condition.initiatorDomains,['news.com']);
  assert.deepEqual(rules[1].condition.resourceTypes,['script']);
});

test('unsupported redirect/scriptlet options are rejected rather than broadened', () => {
  assert.equal(compileFilters('||ads.example^$redirect=noopjs\n||ads.example^$removeparam=x\n||ads.example^$unknown').length,0);
});
test('allowlist disables advertising and preserves malware blocking', () => {
  const rules = [...compileFilters('||ads.example^', 'EasyList'),
    ...compileFilters('||evil.example^', 'uBlock badware')];
  const result = protectionRules(rules, 'ads', ['news.example']);
  assert(result[0].condition.excludedInitiatorDomains.includes('news.example'));
  assert(!result[1].condition.excludedInitiatorDomains.includes('news.example'));
  assert(result.every(rule => rule.condition.excludedInitiatorDomains.includes('gov.vn')));
});
test('minimal mode uses malware rules only', () => {
  const rules = [...compileFilters('||ad.example^', 'EasyList'), ...compileFilters('||bad.example^', 'uBlock badware')];
  const result = protectionRules(rules, 'safe');
  assert.equal(result.length, 1);
  assert.equal(result[0].condition.urlFilter, '||bad.example^');
});
