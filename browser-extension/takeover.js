// Keep the browser's original task until the native host durably acknowledges ownership.
let installed = false;
export function installTakeover(api) {
  if (!api.downloads?.onCreated) return;
  if (installed) return;
  installed = true;
  const pending = new Map();
  async function accept(item) {
    const settings = await api.storage.local.get(['takeover']);
    if (!settings.takeover || item.byExtensionId || !/^https?:\/\//i.test(item.finalUrl || item.url)) return false;
    if (item.danger && item.danger !== 'safe') return false;
    try {
      await api.downloads.pause(item.id);
      const response = await api.runtime.sendNativeMessage('com.hngoos.download_manager', {
        action: 'download', id: `browser-${api.runtime.id}-${item.id}-${item.startTime}`,
        kind: 'file', url: item.finalUrl || item.url,
        takeover: true, expected_size: item.totalBytes > 0 ? item.totalBytes : 0,
        filename: item.filename?.split(/[\\/]/).pop() || '',
      });
      if (!response?.ok) throw Error(response?.error || 'Ứng dụng chưa xác nhận nhận lượt tải');
      await api.downloads.cancel(item.id);
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
      pending.set(item.id, accept(item));
      // Keep resolved promises to deduplicate onCreated/onDeterminingFilename in either order.
      if (pending.size > 256) pending.delete(pending.keys().next().value);
    }
    return pending.get(item.id);
  }
  api.downloads.onCreated.addListener(item => { begin(item); });
  if (api.downloads.onDeterminingFilename) {
    api.downloads.onDeterminingFilename.addListener((item, suggest) => {
      begin(item).finally(() => suggest());
      return true; // Delay Chrome's filename/save dialog until native ownership is resolved.
    });
  }
}
