import {mountIcon} from './icons.js';
import {setCaptureEnabled} from './capture-settings.js';
import {watchConnection} from './connection.js';
import {localize} from './ui-text.js';

const api = globalThis.browser || globalThis.chrome;
const status = document.getElementById('status');
const settings = await api.storage.local.get(['language', 'theme', 'useSession', 'takeover', 'videoButton']);
let text = localize(settings);
const [tab] = await api.tabs.query({active: true, currentWindow: true});
const webPage = /^https?:\/\//i.test(tab?.url || '');
for (const [id, name] of Object.entries({download: 'download', settings: 'settings'})) {
  mountIcon(document.getElementById(id), name);
}
const capture = document.getElementById('takeover');
capture.checked = !!settings.takeover;
let captureEdited = false;
capture.onchange = async () => {
  captureEdited = true;
  const enabled = capture.checked;
  capture.disabled = true;
  try {
    if (!await setCaptureEnabled(api, enabled)) {
      capture.checked = !enabled;
      status.textContent = text('permissionDenied');
    } else status.textContent = text(enabled ? 'captureEnabled' : 'captureDisabled');
  } catch {
    capture.checked = !enabled;
    status.textContent = text('offline');
  } finally { capture.disabled = false; }
};
const session = document.getElementById('session');
session.checked = !!settings.useSession;
session.disabled = !webPage;
session.onchange = async () => {
  if (session.checked) {
    const origin = new URL(tab.url).origin;
    try {
      session.checked = await api.permissions.request({permissions: ['cookies'], origins: [`${origin}/*`]});
    } catch { session.checked = false; }
  }
  await api.storage.local.set({useSession: session.checked});
};
async function send(button, message) {
  button.disabled = true;
  status.textContent = text('working');
  try {
    const result = await api.runtime.sendMessage(message);
    status.textContent = result?.ok ? text(message.action === 'ping' ? 'connected' : 'sent') : text('offline');
  } catch { status.textContent = text('offline'); }
  finally { button.disabled = false; }
}
document.getElementById('settings').onclick = async () => {
  await api.storage.session.set({optionsTabId: webPage ? tab.id : null});
  await api.runtime.openOptionsPage();
  // Chromium reuses an existing Options tab; refresh its source context as well.
  for (const options of await api.tabs.query({url: api.runtime.getURL('options.html')})) {
    await api.tabs.reload(options.id);
  }
};
document.getElementById('settings').setAttribute('aria-label', text('settings'));
for (const id of ['download', 'video']) document.getElementById(id).disabled = !webPage;
document.getElementById('download').onclick = event => send(event.currentTarget, {action: 'download', kind: 'video', url: tab.url});
const video = document.getElementById('video');
video.checked = !!settings.videoButton;
video.onchange = async () => {
  video.disabled = true;
  try {
    await api.storage.local.set({videoButton: video.checked});
    if (video.checked) {
      // Already-open pages may predate the extension's content script.
      const result = await api.runtime.sendMessage({action: 'enable-video', tabId: tab.id});
      if (!result?.ok) throw Error('Video button unavailable');
    }
  } catch {
    status.textContent = text('offline');
  } finally { video.disabled = !webPage; }
};
// Cached settings make the popup usable even while the native host is offline.
const connection = document.getElementById('connection');
connection.textContent = text('working');
const stop = watchConnection(api, async online => {
  const latest = await api.storage.local.get(['language', 'theme', 'takeover']);
  text = localize(latest);
  document.getElementById('settings').setAttribute('aria-label', text('settings'));
  if (!captureEdited) capture.checked = !!latest.takeover;
  connection.textContent = text(online ? 'connected' : 'offline');
});
addEventListener('pagehide', stop, {once: true});
if (webPage) {
  try {
    const detected = await api.runtime.sendMessage({action: 'media-candidates', tabId: tab.id});
    if (detected?.items?.length) {
      document.getElementById('media').hidden = false;
      const streams = document.getElementById('streams');
      for (const item of detected.items) {
        const option = document.createElement('option');
        option.value = item.url;
        option.textContent = `${item.kind} · ${item.host}`;
        streams.append(option);
      }
      document.getElementById('stream-download').onclick = event => send(event.currentTarget,
        {action: 'download', kind: 'video', url: streams.value, tabId: tab.id});
    }
  } catch { /* Stream discovery is optional; file downloads remain available. */ }
}
