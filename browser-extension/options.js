const chrome = globalThis.browser || globalThis.chrome;
let connectionTestStarted = false;
document.getElementById('identity').textContent = `Extension ID: ${chrome.runtime.id}`;
chrome.storage.local.get(['sourceStats', 'lastError']).then(settings => {
  document.getElementById('sources').textContent = JSON.stringify(settings.sourceStats || [], null, 2);
  if (!connectionTestStarted) document.getElementById('status').textContent = settings.lastError || '';
});
document.getElementById('ping').onclick = async () => {
  connectionTestStarted = true;
  document.getElementById('ping').disabled = true;
  document.getElementById('status').textContent = '';
  try {
    const result = await chrome.runtime.sendMessage({action: 'ping'});
    document.getElementById('status').textContent = result?.ok ? 'Đã kết nối ứng dụng.' : (result?.error || 'Ứng dụng không trả lời.');
  } catch (error) { document.getElementById('status').textContent = error.message; }
  finally { document.getElementById('ping').disabled = false; }
};
