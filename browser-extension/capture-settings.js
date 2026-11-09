export async function setCaptureEnabled(api, enabled) {
  if (enabled && !await api.permissions.contains({permissions:['downloads']})
      && !await api.permissions.request({permissions:['downloads']})) return false;
  const result = await api.runtime.sendNativeMessage('com.hngoos.download_manager',
    {action:'set-browser-capture',enabled});
  if (!result?.ok) throw Error(result?.error || 'Không kết nối được HDM.');
  await api.storage.local.set({capturePolicy:result.settings,captureRevision:result.revision,takeover:enabled});
  await syncInsertCapture(api, enabled && result.settings.bypass_insert);
  return true;
}

export function captureAllowed(item, policy = {}) {
  let url;
  try { url = new URL(item.finalUrl || item.url); } catch { return false; }
  if (!['http:', 'https:'].includes(url.protocol)) return false;
  const host = url.hostname.toLowerCase();
  if (policy.skip_domains_enabled !== false && (policy.skip_domains || []).some(value => host === value || host.endsWith('.'+value))) return false;
  let pathname = url.pathname;
  try { pathname = decodeURIComponent(pathname); } catch { /* Literal percent escapes remain a valid filename. */ }
  const name = (item.filename || pathname).split(/[\\/]/).pop();
  const extension = name.includes('.') ? name.split('.').pop().toLowerCase() : '';
  if (policy.skip_extensions_enabled !== false && (policy.skip_extensions || []).includes(extension)) return false;
  if (policy.only_extensions_enabled !== false && policy.only_extensions?.length && !policy.only_extensions.includes(extension)) return false;
  if (policy.min_bytes_enabled !== false && policy.min_bytes > 0 && !(item.totalBytes >= policy.min_bytes)) return false;
  return true;
}

export async function syncCaptureSettings(api, force = false) {
  try {
    const result = await api.runtime.sendNativeMessage('com.hngoos.download_manager', {action: 'browser-settings'});
    if (!result?.ok) return false;
    await api.storage.local.set({language: result.language || 'en', theme: result.theme || 'dark'});
    if (!result.settings) return false;
    const saved = await api.storage.local.get(['captureRevision']);
    if (!force && saved.captureRevision === result.revision) return true;
    const permitted = await api.permissions.contains({permissions: ['downloads']});
    await api.storage.local.set({capturePolicy: result.settings, captureRevision: result.revision,
                                takeover: !!result.settings.capture && permitted});
    await syncInsertCapture(api, !!result.settings.capture && permitted && result.settings.bypass_insert);
    return true;
  } catch { return false; } // Older/offline native hosts leave existing capture settings intact.
}

export async function syncInsertCapture(api, enabled) {
  if (!api.scripting?.registerContentScripts) return;
  const id='hdm-insert-capture';
  await api.scripting.unregisterContentScripts({ids:[id]}).catch(()=>{});
  if (enabled && await api.permissions.contains({origins:['<all_urls>']})) {
    await api.scripting.registerContentScripts([{id,matches:['http://*/*','https://*/*'],
      js:['capture-insert.js'],runAt:'document_start'}]);
    for (const tab of await api.tabs.query({})) {
      if (/^https?:\/\//i.test(tab.url || '')) {
        await api.scripting.executeScript({target:{tabId:tab.id},files:['capture-insert.js']}).catch(()=>{});
      }
    }
  }
}
