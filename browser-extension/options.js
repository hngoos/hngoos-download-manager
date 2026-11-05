const chrome = globalThis.browser || globalThis.chrome;
document.getElementById('identity').textContent = `Extension ID: ${chrome.runtime.id}`;
chrome.storage.local.get(['sourceStats', 'lastError']).then(settings => {
  document.getElementById('sources').textContent = JSON.stringify(settings.sourceStats || [], null, 2);
  document.getElementById('status').textContent = settings.lastError || '';
});
document.getElementById('ping').onclick = async () => {
  try {
    const result = await chrome.runtime.sendMessage({action: 'ping'});
    document.getElementById('status').textContent = result?.ok ? 'Đã kết nối ứng dụng.' : result?.error;
  } catch (error) { document.getElementById('status').textContent = error.message; }
};
