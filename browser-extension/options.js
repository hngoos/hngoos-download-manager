import {setCaptureEnabled} from './capture-settings.js';
const chrome = globalThis.browser || globalThis.chrome;
let connectionTestStarted = false;
document.getElementById('capture').onclick = async () => {
  connectionTestStarted = true;
  const button = document.getElementById('capture');
  button.disabled = true;
  try {
    const enabled = await setCaptureEnabled(chrome,true);
    document.getElementById('status').textContent = enabled ? 'Đã kết nối. Lượt tải mới sẽ được chuyển sang HDM.'
      : 'Chưa cấp quyền. Trình duyệt tiếp tục tải như bình thường.';
  } catch (error) { document.getElementById('status').textContent = error.message; }
  finally { button.disabled = false; }
};
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
