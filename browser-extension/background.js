import {removeWebsiteTools} from './retired-features.js';
import {installTakeover, settleTakeovers} from './takeover.js';
import {mediaCandidate, mergeCandidates} from './media-capture.js';
import {syncCaptureSettings} from './capture-settings.js';

const chrome = globalThis.browser || globalThis.chrome;
installTakeover(globalThis.browser || chrome);
chrome.permissions.onAdded?.addListener(() => {
  installTakeover(globalThis.browser || chrome);
  syncCaptureSettings(chrome, true);
});
chrome.permissions.onRemoved?.addListener(() => syncCaptureSettings(chrome, true));
chrome.alarms.create('hdm-integration', {periodInMinutes: 1});
settleTakeovers(chrome).catch(() => {});
syncCaptureSettings(chrome);
removeWebsiteTools(chrome).catch(() => {});

const HOST = 'com.hngoos.download_manager';
const candidates = new Map();
const candidateStore = chrome.storage.session || chrome.storage.local;
chrome.webRequest?.onHeadersReceived?.addListener(details => {
  const candidate = mediaCandidate(details);
  if (candidate) {
    const items = mergeCandidates(candidates.get(details.tabId) || [], candidate);
    candidates.set(details.tabId, items);
    candidateStore.set({['media-'+details.tabId]:items});
  }
}, {urls:['http://*/*','https://*/*']}, ['responseHeaders']);
chrome.webNavigation?.onCommitted?.addListener(details => {
  if (details.frameId === 0) {
    candidates.delete(details.tabId);
    candidateStore.remove?.('media-'+details.tabId);
  }
});
chrome.tabs?.onRemoved?.addListener(tabId => {
  candidates.delete(tabId); candidateStore.remove?.('media-'+tabId);
});
chrome.runtime.onInstalled.addListener(async () => {
  await removeWebsiteTools(chrome);
  await syncCaptureSettings(chrome, true);
  await chrome.contextMenus.removeAll();
  chrome.contextMenus.create({id: 'download-link', title: 'Tải bằng HDM', contexts: ['link']});
  chrome.contextMenus.create({id: 'download-video', title: 'Tải video bằng HDM', contexts: ['video', 'page']});
});

async function sendDownload(message, sourceUrl = message.url) {
  const url = new URL(message.url);
  if (!['https:', 'http:'].includes(url.protocol) || url.username || url.password) throw Error('URL không hợp lệ');
  const settings = await chrome.storage.local.get(['useSession']);
  let cookies = [];
  const source = new URL(sourceUrl);
  const referrer = ['https:', 'http:'].includes(source.protocol) && !(source.protocol === 'https:' && url.protocol === 'http:')
    ? source.origin+'/' : '';
  // A page may contain cross-origin video/CDN URLs. Never attach another site's session to them.
  const sameOrigin = new URL(sourceUrl).origin === url.origin;
  if (sameOrigin && message.kind === 'video' && settings.useSession && await chrome.permissions.contains({permissions: ['cookies'], origins: [`${url.origin}/*`]})) {
    cookies = await chrome.cookies.getAll({url: url.href});
  }
  const response = await chrome.runtime.sendNativeMessage(HOST, {
    action: 'download', id: message.id || crypto.randomUUID(), url: url.href,
    kind: message.kind || 'file', filename: message.filename || '', cookies, referrer,
  });
  if (!response?.ok) throw Error(response?.error || 'Ứng dụng không nhận yêu cầu');
  return response;
}

chrome.contextMenus.onClicked.addListener(async (info, tab) => {
  try {
    await sendDownload({url: info.linkUrl || info.srcUrl || tab.url,
      kind: info.menuItemId === 'download-video' ? 'video' : 'file'}, tab.url);
    chrome.action.setBadgeText({text: '✓', tabId: tab.id});
  } catch (error) {
    await chrome.storage.local.set({lastError: error.message});
    chrome.action.setBadgeText({text: '!', tabId: tab.id});
  }
});

chrome.alarms.onAlarm.addListener(alarm => {
  if (alarm.name === 'hdm-integration') {
    syncCaptureSettings(chrome);
    settleTakeovers(chrome).catch(() => {});
  }
});

chrome.runtime.onMessage.addListener((message, sender, respond) => {
  if (message?.action === 'capture-insert') {
    if (sender.id !== chrome.runtime.id || !sender.tab || !/^https?:\/\//i.test(sender.url || '')) return;
    chrome.storage.local.set({insertBypass:{tabId:sender.tab.id,until:Date.now()+(message.held ? 2000 : 500)}})
      .then(()=>respond({ok:true}));
    return true;
  }
  const allowed = new Set(['download', 'ping', 'enable-video', 'media-candidates']);
  if (!allowed.has(message?.action)) return;
  (async () => {
    const panel = sender.url?.startsWith(chrome.runtime.getURL(''));
    if (sender.tab && !panel && message.action !== 'download') throw Error('Thao tác chỉ dùng từ bảng điều khiển extension');
    if (message.action === 'download') {
      if (sender.tab && !panel && !sender.url?.startsWith('http')) throw Error('Nguồn yêu cầu không hợp lệ');
      const sourceUrl = sender.tab && !panel ? sender.url
        : Number.isInteger(message.tabId) ? (await chrome.tabs.get(message.tabId)).url : message.url;
      return await sendDownload(message, sourceUrl);
    }
    if (message.action === 'ping') return await chrome.runtime.sendNativeMessage(HOST, {action: 'ping'});
    if (message.action === 'media-candidates') {
      const cached = await candidateStore.get('media-'+message.tabId);
      const items = (candidates.get(message.tabId) || cached['media-'+message.tabId] || [])
        .filter(item => Date.now()-item.seen < 30*60*1000).slice(0,30);
      return {ok:true,items};
    }
    if (message.action === 'enable-video') {
      await chrome.scripting.executeScript({target: {tabId: message.tabId}, files: ['video.js']});
      return {ok: true};
    }
  })().then(respond, error => respond({ok: false, error: error.message}));
  return true;
});
