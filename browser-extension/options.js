import {watchConnection} from './connection.js';
import {localize} from './ui-text.js';

const api = globalThis.browser || globalThis.chrome;
const status = document.getElementById('status');
let text = localize(await api.storage.local.get(['language', 'theme']));
status.textContent = text('working');
const stop = watchConnection(api, async online => {
  text = localize(await api.storage.local.get(['language', 'theme']));
  status.textContent = text(online ? 'connected' : 'offline');
});
addEventListener('pagehide', stop, {once: true});
