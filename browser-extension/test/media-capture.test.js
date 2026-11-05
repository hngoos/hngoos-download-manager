import test from 'node:test';
import assert from 'node:assert/strict';
import {mediaCandidate,mergeCandidates} from '../media-capture.js';

test('HLS and DASH candidates are found by URL or content type without retaining headers', () => {
  const hls=mediaCandidate({tabId:1,url:'https://cdn.example/manifest.m3u8?token=fixture',responseHeaders:[{name:'Set-Cookie',value:'never retain'}]});
  assert.equal(hls.kind,'HLS');
  assert(!JSON.stringify(hls).includes('never retain'));
  assert.equal(mediaCandidate({tabId:1,url:'https://cdn.example/stream',responseHeaders:[{name:'Content-Type',value:'application/dash+xml'}]}).kind,'DASH');
});
test('obvious preroll/ad manifests and non-tab traffic are excluded', () => {
  for (const url of ['https://doubleclick.net/stream.m3u8','https://cdn.example/preroll/ad.m3u8'])
    assert.equal(mediaCandidate({tabId:1,url}),null);
  assert.equal(mediaCandidate({tabId:-1,url:'https://cdn.example/main.m3u8'}),null);
});
test('manifest candidates expire, deduplicate and stay bounded', () => {
  let items=[];
  for(let i=0;i<40;i++) items=mergeCandidates(items,{url:String(i),seen:Date.now()});
  assert.equal(items.length,30);
  assert.equal(mergeCandidates(items,{url:'39',seen:Date.now()}).length,30);
  assert.equal(mergeCandidates([{url:'old',seen:0}],{url:'new',seen:Date.now()}).length,1);
});
