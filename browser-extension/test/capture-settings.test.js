import test from 'node:test';
import assert from 'node:assert/strict';
import {captureAllowed, setCaptureEnabled} from '../capture-settings.js';

test('enabling capture requires permission and persists the same policy in HDM', async () => {
  const saved = {};
  const requests = [];
  const api = {
    permissions:{request:async value => { requests.push(value); return true; }},
    runtime:{sendNativeMessage:async (host,message) => {
      assert.equal(host,'com.hngoos.download_manager');
      assert.deepEqual(message,{action:'set-browser-capture',enabled:true});
      return {ok:true,settings:{capture:true,auto_start:false},revision:'updated'};
    }},
    storage:{local:{set:async value => Object.assign(saved,value)}},
  };
  assert.equal(await setCaptureEnabled(api,true),true);
  assert.deepEqual(requests,[{permissions:['downloads']}]);
  assert.equal(saved.takeover,true);
  assert.equal(saved.capturePolicy.auto_start,false);
  assert.equal(saved.captureRevision,'updated');
});

test('declining capture permissions leaves the original download handling intact', async () => {
  const api = {permissions:{request:async()=>false},runtime:{sendNativeMessage:()=>assert.fail('No consent')}};
  assert.equal(await setCaptureEnabled(api,true),false);
});

test('independent filter switches preserve values while bypassing disabled rules', () => {
  const item = {url:'https://example.com/a.zip',filename:'a.zip',totalBytes:10};
  assert.equal(captureAllowed(item,{skip_domains:['example.com'],skip_domains_enabled:false}),true);
  assert.equal(captureAllowed(item,{skip_extensions:['zip'],skip_extensions_enabled:false}),true);
  assert.equal(captureAllowed(item,{only_extensions:['pdf'],only_extensions_enabled:false}),true);
  assert.equal(captureAllowed(item,{min_bytes:100,min_bytes_enabled:false}),true);
  assert.equal(captureAllowed(item,{skip_domains:['example.com'],skip_domains_enabled:true}),false);
  assert.equal(captureAllowed(item,{min_bytes:100,min_bytes_enabled:true}),false);
});

test('malformed percent escapes cannot break download capture', () => {
  assert.equal(captureAllowed({url:'https://example.com/a%QZ.pdf'},{}),true);
});
