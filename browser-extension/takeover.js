// Keep the browser's original task until the native host durably acknowledges ownership.
import {captureAllowed} from './capture-settings.js';
let installed = false;
let storageTail = Promise.resolve();
let settleTimer;
const decisions = new Map();
function finishDecision(downloadId) {
  const decision = decisions.get(downloadId);
  if (decision) {
    decision.settled = true;
    decision.resolve();
  }
}
function scheduleSettlement(api) {
  if (settleTimer) return;
  settleTimer = setTimeout(() => {
    settleTimer = undefined;
    settleTakeovers(api).catch(()=>{});
  },1500);
  settleTimer.unref?.();
}
function updatePending(api, change) {
  const result = storageTail.then(async () => {
    const saved = await api.storage.local.get(['pendingTakeovers']);
    const value = await change(saved.pendingTakeovers || []);
    await api.storage.local.set({pendingTakeovers:value});
  });
  storageTail = result.catch(() => {});
  return result;
}

export async function settleTakeovers(api) {
  await updatePending(api, async entries => {
    const remaining = [];
    for (const entry of entries) {
      try {
        const result = await api.runtime.sendNativeMessage('com.hngoos.download_manager', {action:'download-status',id:entry.requestId});
        if (!result?.ok) { remaining.push(entry); continue; }
        if (result.state === 'accepted') {
          await api.downloads.cancel(entry.downloadId);
          finishDecision(entry.downloadId);
        } else if (result.state === 'cancelled' || result.state === 'unknown') {
          await api.downloads.resume(entry.downloadId);
          finishDecision(entry.downloadId);
        }
        else { remaining.push(entry); }
      } catch { remaining.push(entry); } // A closed/offline host never discards the original task.
    }
    if (remaining.length) scheduleSettlement(api);
    return remaining;
  });
}

async function insertHeld(api, item, settings) {
  const bypass = settings.insertBypass;
  if (!settings.capturePolicy?.bypass_insert || !bypass || bypass.until < Date.now()) return false;
  let tabId = item.tabId;
  if (tabId === undefined && api.tabs?.query) {
    const [tab] = await api.tabs.query({active:true,lastFocusedWindow:true});
    if (!tab || !item.referrer) return false;
    try { if (new URL(tab.url).origin !== new URL(item.referrer).origin) return false; } catch { return false; }
    tabId = tab.id;
  }
  return tabId === bypass.tabId;
}

export function installTakeover(api) {
  if (!api.downloads?.onCreated) return;
  if (installed) return;
  installed = true;
  const pending = new Map();
  async function accept(item) {
    const settings = await api.storage.local.get(['takeover', 'capturePolicy', 'insertBypass']);
    if (!settings.takeover || item.byExtensionId || !/^https?:\/\//i.test(item.finalUrl || item.url)) return false;
    if (item.danger && item.danger !== 'safe') return false;
    if (!captureAllowed(item, settings.capturePolicy)) return false;
    if (await insertHeld(api, item, settings)) return false;
    try {
      await api.downloads.pause(item.id);
      const requestId = `browser-${api.runtime.id}-${item.id}-${item.startTime}`;
      const response = await api.runtime.sendNativeMessage('com.hngoos.download_manager', {
        action: 'download', id: requestId,
        kind: 'file', url: item.finalUrl || item.url,
        takeover: true, expected_size: item.totalBytes > 0 ? item.totalBytes : 0,
        filename: item.filename?.split(/[\\/]/).pop() || '',
      });
      if (!response?.ok) throw Error(response?.error || 'Ứng dụng chưa xác nhận nhận lượt tải');
      if (settings.capturePolicy?.resume_on_cancel) {
        await updatePending(api, entries => [...entries.filter(entry=>entry.downloadId!==item.id),
          {downloadId:item.id,requestId}]);
        scheduleSettlement(api);
      } else {
        await api.downloads.cancel(item.id);
        finishDecision(item.id);
      }
      await api.storage.local.set({lastTakeover: {name: item.filename || '', at: Date.now()}});
      return true;
    } catch (error) {
      try { await api.downloads.resume(item.id); } catch { /* Already completed/cancelled by the user. */ }
      await api.storage.local.set({lastError: `Giữ tải trong trình duyệt: ${error.message}`});
      return false;
    }
  }
  function begin(item) {
    if (!pending.has(item.id)) {
      let resolve;
      const promise = new Promise(done => { resolve = done; });
      decisions.set(item.id, {promise, resolve});
      pending.set(item.id, accept(item).catch(() => false).then(taken => {
        if (!taken) finishDecision(item.id);
        return taken;
      }));
      // Keep resolved promises to deduplicate onCreated/onDeterminingFilename in either order.
      if (pending.size > 256) {
        // Keep unresolved callbacks while HDM is reviewing them.
        for (const id of pending.keys()) {
          if (decisions.get(id)?.settled) {
            pending.delete(id);
            decisions.delete(id);
          }
          if (pending.size <= 256) break;
        }
      }
    }
    return pending.get(item.id);
  }
  api.downloads.onCreated.addListener(item => { begin(item); });
  if (api.downloads.onDeterminingFilename) {
    api.downloads.onDeterminingFilename.addListener((item, suggest) => {
      begin(item).then(async taken => {
        if (taken) await decisions.get(item.id)?.promise;
      }).finally(() => suggest());
      return true; // Delay Chrome's filename/save dialog until native ownership is resolved.
    });
  }
  return {settle:()=>settleTakeovers(api)};
}
