import {syncCaptureSettings} from './capture-settings.js';

// Native messaging opens on demand. Retry discovery without asking the user to reconnect.
export function watchConnection(api, report, {
  sync = syncCaptureSettings, schedule = setTimeout, cancel = clearTimeout,
} = {}) {
  let stopped = false, timer, previous, failures = 0;
  async function refresh() {
    if (stopped) return;
    let online = false;
    try { online = await sync(api); } catch { /* Retry while the panel is open. */ }
    if (stopped) return;
    if (online !== previous) report(online);
    previous = online;
    failures = online ? 0 : failures + 1;
    timer = schedule(refresh, online ? 15000 : Math.min(15000, 1000 * 2 ** Math.min(failures - 1, 4)));
  }
  refresh();
  return () => { stopped = true; if (timer !== undefined) cancel(timer); };
}
