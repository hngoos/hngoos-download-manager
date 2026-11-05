import {compileFilters, protectionRules, MODES} from './filters.js';
import {installTakeover} from './takeover.js';
import {mediaCandidate, mergeCandidates} from './media-capture.js';

const chrome = globalThis.browser || globalThis.chrome;
installTakeover(globalThis.browser || chrome);
chrome.permissions.onAdded?.addListener(() => installTakeover(globalThis.browser || chrome));

const HOST = 'com.hngoos.download_manager';
const candidates = new Map();
const candidateStore = chrome.storage.session || chrome.storage.local;
const blockedPopups = new Map();
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
    candidates.delete(details.tabId); blockedPopups.delete(details.tabId);
    candidateStore.remove?.('media-'+details.tabId);
  }
});
chrome.tabs?.onRemoved?.addListener(tabId => {
  candidates.delete(tabId); blockedPopups.delete(tabId); candidateStore.remove?.('media-'+tabId);
});
chrome.webNavigation?.onCreatedNavigationTarget?.addListener(async details => {
  try {
    const settings = await chrome.storage.local.get(['mode','allowSites','compiledRules']);
    if (!['ads','strong'].includes(settings.mode)) return;
    const source = await chrome.tabs.get(details.sourceTabId);
    const sourceHost = new URL(source.url).hostname;
    if (/(?:bank|payment|checkout|login|signin|gov\.vn)/i.test(source.url)
        || (settings.allowSites || []).some(host => sourceHost === host || sourceHost.endsWith('.'+host))) return;
    const host = new URL(details.url).hostname;
    const knownAd = (settings.compiledRules || []).some(rule => {
      // Scoped rules and exceptions cannot establish that a whole host is advertising.
      if (rule.condition.initiatorDomains || rule.condition.excludedInitiatorDomains
          || rule.condition.domainType === 'firstParty') return false;
      const match = rule.action.type === 'block' && rule.condition.urlFilter?.match(/^\|\|([a-z0-9.-]+)\^$/i);
      return match && sourceHost !== host && !sourceHost.endsWith('.'+host)
        && !host.endsWith('.'+sourceHost) && (host === match[1] || host.endsWith('.'+match[1]));
    });
    if (knownAd) {
      await chrome.tabs.remove(details.tabId);
      blockedPopups.set(details.sourceTabId, (blockedPopups.get(details.sourceTabId) || 0)+1);
    }
  } catch { /* Restricted/closed tabs are left to the browser. */ }
});
const SOURCES = [
  ['EasyList', 'https://easylist.to/easylist/easylist.txt'],
  ['EasyPrivacy', 'https://easylist.to/easylist/easyprivacy.txt'],
  ['ABPVN', 'https://abpvn.com/filter/abpvn.txt'],
  ['uBlock badware', 'https://raw.githubusercontent.com/uBlockOrigin/uAssets/master/filters/badware.txt'],
];
chrome.runtime.onInstalled.addListener(async () => {
  const settings = await chrome.storage.local.get(['mode']);
  if (!settings.mode) await chrome.storage.local.set({mode: 'ads'});
  await chrome.contextMenus.removeAll();
  chrome.contextMenus.create({id: 'download-link', title: 'Tải bằng HDM', contexts: ['link']});
  chrome.contextMenus.create({id: 'download-video', title: 'Tải video bằng HDM', contexts: ['video', 'page']});
  chrome.alarms.create('filters', {periodInMinutes: 720});
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

async function applyMode(mode, allowSites = []) {
  if (!(mode in MODES)) throw Error('Mức chặn không hợp lệ');
  const old = await chrome.declarativeNetRequest.getDynamicRules();
  const cached = await chrome.storage.local.get(['compiledRules']);
  const rules = mode === 'off' ? [] : protectionRules(cached.compiledRules || [], mode, allowSites);
  await chrome.declarativeNetRequest.updateDynamicRules({removeRuleIds: old.map(r => r.id), addRules: rules});
  await chrome.storage.local.set({mode, allowSites});
  if (chrome.scripting?.registerContentScripts && await chrome.permissions.contains({origins:['<all_urls>']})) {
    await chrome.scripting.unregisterContentScripts({ids:['hdm-site-protection']}).catch(() => {});
    if (['ads','strong'].includes(mode)) await chrome.scripting.registerContentScripts([
      {id:'hdm-site-protection',matches:['http://*/*','https://*/*'],js:['site-protection.js'],runAt:'document_start'}]);
  }
}

async function updateFilters() {
  if (!await chrome.permissions.contains({origins: ['<all_urls>']})) return;
  const downloaded = [];
  const sourceStats = [];
  for (const [name, url] of SOURCES) {
    try {
      const response = await fetch(url, {cache: 'no-store', signal: AbortSignal.timeout(25000)});
      if (!response.ok) throw Error(`HTTP ${response.status}`);
      const text = await response.text();
      if (text.length > 10_000_000) throw Error('Danh sách quá lớn');
      const rules = compileFilters(text, name);
      downloaded.push(...rules);
      sourceStats.push({name, count: rules.length, updated: new Date().toISOString()});
    } catch (error) { sourceStats.push({name, error: error.message}); }
  }
  if (!downloaded.length) throw Error('Không cập nhật được danh sách; giữ bộ lọc cũ');
  // DNR has a rule budget; skip unsupported syntax rather than guessing its meaning.
  const groups = [
    downloaded.filter(rule => rule.source.includes('badware')).slice(0, 1000),
    downloaded.filter(rule => rule.source === 'EasyList').slice(0, 1800),
    downloaded.filter(rule => rule.source === 'ABPVN').slice(0, 1200),
    downloaded.filter(rule => rule.source === 'EasyPrivacy').slice(0, 500),
  ];
  const compiledRules = groups.flat().map((rule, index) => ({...rule, id: index + 100}));
  await chrome.storage.local.set({compiledRules, sourceStats});
  const settings = await chrome.storage.local.get(['mode', 'allowSites']);
  await applyMode(settings.mode || 'ads', settings.allowSites || []);
}

chrome.alarms.onAlarm.addListener(alarm => {
  if (alarm.name === 'filters') updateFilters().catch(error => chrome.storage.local.set({lastError: error.message}));
});

chrome.runtime.onMessage.addListener((message, sender, respond) => {
  const allowed = new Set(['download', 'ping', 'enable-video', 'mode', 'update-filters', 'allow-site', 'save-invoice', 'invoice-error',
    'media-candidates','stats','pick-element','reset-site']);
  if (!allowed.has(message?.action)) return;
  (async () => {
    const panel = sender.url?.startsWith(chrome.runtime.getURL(''));
    if (sender.tab && !panel && !['download', 'save-invoice', 'invoice-error'].includes(message.action)) throw Error('Thao tác chỉ dùng từ bảng điều khiển extension');
    if (message.action === 'invoice-error') {
      await chrome.storage.local.set({lastError: String(message.error).slice(0, 200)}); return {ok:true};
    }
    if (message.action === 'save-invoice') {
      if (!sender.tab || !sender.url?.startsWith('https://')) throw Error('Nguồn phiếu không hợp lệ');
      const settings = await chrome.storage.local.get(['invoiceHosts']);
      if (!(settings.invoiceHosts || []).includes(new URL(sender.url).hostname)) throw Error('Chưa bật lưu phiếu cho trang này');
      return await chrome.runtime.sendNativeMessage(HOST, {action:'save-invoice', id:crypto.randomUUID(),
        url:sender.url, html:message.html, order_id:message.order_id});
    }
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
    if (message.action === 'stats') {
      let matched = [], available = true;
      try { matched = (await chrome.declarativeNetRequest.getMatchedRules({tabId:message.tabId})).rulesMatchedInfo || []; }
      catch { available = false; }
      const rules = await chrome.declarativeNetRequest.getDynamicRules();
      return {ok:true,available,popups:blockedPopups.get(message.tabId) || 0,count:matched.length,
        rules:rules.filter(rule => matched.some(info => info.rule.ruleId === rule.id)).map(rule => rule.condition.urlFilter).slice(0,100)};
    }
    if (message.action === 'pick-element') {
      await chrome.scripting.executeScript({target:{tabId:message.tabId},files:['site-protection.js']});
      return await chrome.tabs.sendMessage(message.tabId,{action:'pick-element'});
    }
    if (message.action === 'reset-site') {
      const current = await chrome.storage.local.get(['mode','allowSites','hiddenElements']);
      const host = new URL(message.url).hostname;
      const hiddenElements = current.hiddenElements || {}; delete hiddenElements[host];
      await chrome.storage.local.set({hiddenElements});
      await applyMode(current.mode || 'ads',(current.allowSites || []).filter(site => site !== host));
      return {ok:true};
    }
    if (message.action === 'enable-video') {
      await chrome.scripting.executeScript({target: {tabId: message.tabId}, files: ['video.js']});
      return {ok: true};
    }
    if (message.action === 'mode') {
      const current = await chrome.storage.local.get(['allowSites']);
      await applyMode(message.mode, current.allowSites || []);
      return {ok: true};
    }
    if (message.action === 'update-filters') { await updateFilters(); return {ok: true}; }
    if (message.action === 'allow-site') {
      const settings = await chrome.storage.local.get(['mode', 'allowSites']);
      const hostname = new URL(message.url).hostname;
      const allowSites = [...new Set([...(settings.allowSites || []), hostname])];
      await applyMode(settings.mode || 'ads', allowSites);
      return {ok: true};
    }
  })().then(respond, error => respond({ok: false, error: error.message}));
  return true;
});
