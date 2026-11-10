(() => {
  const api = globalThis.browser || globalThis.chrome;
  if (window.__hngoosVideoButtons) return;
  window.__hngoosVideoButtons = true;
  const buttons = new Map();
  let observer, timer, frame, enabled = false;
  const eligible = video => {
    // Camera, microphone, screen sharing and WebRTC calls have no downloadable
    // file. A blob backed by MediaSource (e.g. YouTube) is different: srcObject
    // stays null and the page URL can be passed to HDM's extractor.
    if (video.srcObject && typeof video.srcObject.getTracks === 'function') return false;
    return /^(https?:|blob:)/i.test(video.currentSrc || video.src || video.querySelector('source')?.src || '');
  };
  const position = () => {
    frame = null;
    for (const [video, {host}] of buttons) {
      const rect = video.getBoundingClientRect();
      const visible = video.isConnected && eligible(video) && rect.width >= 160 && rect.height >= 90 &&
        rect.bottom > 35 && rect.top < innerHeight && rect.right > 0 && rect.left < innerWidth &&
        getComputedStyle(video).visibility !== 'hidden';
      host.style.setProperty('display', visible ? 'block' : 'none', 'important');
      if (visible) {
        host.style.setProperty('left', `${Math.max(4, Math.min(innerWidth - 240, rect.left + 8))}px`, 'important');
        host.style.setProperty('top', `${Math.max(4, rect.top + 8)}px`, 'important');
      }
    }
  };
  const schedule = () => { if (enabled && !frame) frame = requestAnimationFrame(position); };
  const scan = () => {
    if (!enabled) return;
    for (const [video, {host}] of buttons) {
      if (!video.isConnected || !eligible(video)) { host.remove(); buttons.delete(video); }
    }
    for (const video of document.querySelectorAll('video')) {
      if (!eligible(video)) continue;
      if (buttons.has(video)) {
        const {host} = buttons.get(video);
        if (!host.isConnected) document.documentElement.append(host);
        continue;
      }
      // A shadow tree keeps page button styles out. A separate top layer keeps
      // player hover controls and transparent overlays from stealing clicks.
      const host = document.createElement('div');
      host.dataset.hdmVideoHost = '';
      host.style.cssText = 'all:initial!important;display:none!important;position:fixed!important;z-index:2147483647!important;pointer-events:none!important;width:max-content!important;height:auto!important;';
      const shadow = host.attachShadow({mode: 'open'});
      const button = document.createElement('button');
      button.type = 'button';
      button.dataset.hdmVideoDownload = '';
      button.textContent = '↓ Tải video này bằng HDM';
      button.style.cssText = 'all:initial;display:block;pointer-events:auto;background:#1872da;color:#fff;border:0;padding:8px 12px;border-radius:6px;cursor:pointer;font:13px system-ui;box-sizing:border-box;white-space:nowrap;min-width:180px;';
      for (const name of ['pointerdown', 'pointerup', 'mousedown', 'mouseup']) {
        button.addEventListener(name, event => event.stopPropagation());
      }
      button.addEventListener('click', async event => {
        if (!event.isTrusted) return;
        event.preventDefault(); event.stopPropagation();
        if (!eligible(video)) return;
        const direct = video.currentSrc || video.src || video.querySelector('source')?.src;
        try {
          const response = await api.runtime.sendMessage({action: 'download', kind: 'video',
            url: /^https?:/i.test(direct) ? direct : location.href});
          button.textContent = response?.ok ? '✓ Đã gửi tới HDM' : 'Chưa kết nối ứng dụng HDM';
        } catch { button.textContent = 'Chưa kết nối ứng dụng HDM'; }
      });
      shadow.append(button);
      buttons.set(video, {host, button});
      document.documentElement.append(host);
    }
    position();
  };
  const show = value => {
    enabled = value;
    observer?.disconnect();
    clearInterval(timer);
    if (enabled) {
      scan();
      observer ||= new MutationObserver(scan);
      observer.observe(document.documentElement, {childList: true, subtree: true, attributes: true, attributeFilter: ['src']});
      // srcObject is a JS property, not a DOM attribute. Calls can switch it
      // without mutating the tree, so also reconcile these lightweight entries.
      timer = setInterval(scan, 750);
    } else {
      if (frame) cancelAnimationFrame(frame);
      frame = null;
      for (const {host} of buttons.values()) host.remove();
      buttons.clear();
    }
  };
  addEventListener('scroll', schedule, true);
  addEventListener('resize', schedule);
  for (const name of ['loadedmetadata', 'loadstart', 'emptied']) document.addEventListener(name, scan, true);
  api.storage.onChanged.addListener((changes, area) => {
    if (area === 'local' && changes.videoButton) show(!!changes.videoButton.newValue);
  });
  api.storage.local.get(['videoButton']).then(settings => show(!!settings.videoButton));
})();
