import {mountIcon, icons} from './icons.js';
const chrome = globalThis.browser || globalThis.chrome;
const controls = {};
for (const [id, name] of Object.entries({download: 'download', video: 'video', enable: 'shield', allow: 'globe', reset: 'settings'})) {
  controls[id] = mountIcon(document.getElementById(id), name);
}
const status = document.getElementById('status');
const [tab] = await chrome.tabs.query({active: true, currentWindow: true});
const settings = await chrome.storage.local.get(['mode', 'useSession', 'takeover', 'invoiceHosts']);
const sellerHosts = ['banhang.shopee.vn','seller.shopee.vn','sellercenter.lazada.vn','seller-vn.tiktok.com','seller.tiktok.com'];
const currentHost = new URL(tab.url).hostname;
const invoiceToggle = document.getElementById('invoices');
invoiceToggle.disabled = !sellerHosts.includes(currentHost);
invoiceToggle.checked = (settings.invoiceHosts || []).includes(currentHost);
invoiceToggle.onchange = async event => {
  const enabled = event.target.checked;
  const id = `hdm-invoice-${currentHost.replaceAll('.', '-')}`;
  try {
    if (enabled && !await chrome.permissions.request({origins:[`https://${currentHost}/*`]})) throw Error('Chưa cấp quyền trang');
    await chrome.scripting.unregisterContentScripts({ids:[id]}).catch(() => {});
    if (enabled) {
      await chrome.scripting.registerContentScripts([{id,matches:[`https://${currentHost}/*`],js:['invoice-capture.js'],runAt:'document_start'}]);
      await chrome.scripting.executeScript({target:{tabId:tab.id},files:['invoice-capture.js']});
    }
    const hosts = (settings.invoiceHosts || []).filter(host => host !== currentHost);
    if (enabled) hosts.push(currentHost);
    await chrome.storage.local.set({invoiceHosts:hosts});
  } catch (error) { event.target.checked = !enabled; status.textContent = error.message; }
};
document.getElementById('mode').value = settings.mode || 'off';
document.getElementById('session').checked = !!settings.useSession;
document.getElementById('takeover').checked = !!settings.takeover;
document.getElementById('takeover').onchange = async event => {
  let enabled = event.target.checked;
  if (enabled) enabled = await chrome.permissions.request({permissions: ['downloads']});
  event.target.checked = enabled;
  await chrome.storage.local.set({takeover: enabled});
};
document.getElementById('session').onchange = async event => {
  if (event.target.checked) {
    try {
      const origin = new URL(tab.url).origin;
      const allowed = await chrome.permissions.request({permissions: ['cookies'], origins: [`${origin}/*`]});
      event.target.checked = allowed;
    } catch { event.target.checked = false; }
  }
  await chrome.storage.local.set({useSession: event.target.checked});
};
async function send(message) {
  status.textContent = 'Đang xử lý…';
  try {
    const result = await chrome.runtime.sendMessage(message);
    controls.download.morphTo(result?.ok ? icons.check : icons.close);
    status.textContent = result?.ok ? 'Đã thực hiện.' : result?.error || 'Không nhận được phản hồi.';
  } catch (error) { status.textContent = error.message; }
}
document.getElementById('download').onclick = () => send({action: 'download', kind: 'video', url: tab.url});
document.getElementById('video').onclick = () => send({action: 'enable-video', tabId: tab.id});
document.getElementById('mode').onchange = event => send({action: 'mode', mode: event.target.value});
document.getElementById('allow').onclick = () => send({action: 'allow-site', url: tab.url});
document.getElementById('enable').onclick = async () => {
  if (await chrome.permissions.request({origins: ['<all_urls>']})) await send({action: 'update-filters'});
};
document.getElementById('reset').onclick = async () => {
  await send({action:'reset-site',url:tab.url});
};
document.getElementById('reset').textContent = 'Về mặc định cho trang này';
document.getElementById('pick').onclick = async () => {
  await send({action:'pick-element',tabId:tab.id});
  window.close();
};
document.getElementById('stats').onclick = async () => {
  const result = await chrome.runtime.sendMessage({action:'stats',tabId:tab.id});
  document.getElementById('blocked').textContent = (result.available ? `${result.count || 0} yêu cầu` : 'Trình duyệt chưa cho đọc thống kê yêu cầu')
    + `; ${result.popups || 0} tab quảng cáo\n${(result.rules || []).join('\n')}`;
};
const detected = await chrome.runtime.sendMessage({action:'media-candidates',tabId:tab.id});
const streams = document.getElementById('streams');
if (detected?.items?.length) {
  streams.textContent = '';
  for (const item of detected.items) {
    const option = document.createElement('option'); option.value = item.url;
    option.textContent = `${item.kind} — ${item.host}`; streams.append(option);
  }
}
document.getElementById('stream-download').onclick = () => {
  if (streams.value) send({action:'download',kind:'video',url:streams.value,tabId:tab.id});
};
