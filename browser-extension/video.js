(() => {
  const api = globalThis.browser || globalThis.chrome;
  if (window.__hngoosVideoButtons) return;
  window.__hngoosVideoButtons = true;
  const buttons = new Map();
  let observer, timer, frame, enabled = false;
  const tiktok = /(^|\.)tiktok\.com$/i.test(location.hostname);
  const tiktokURL = value => {
    try {
      const url = new URL(value, location.href);
      if (!/^https?:$/.test(url.protocol) || url.username || url.password ||
          !/(^|\.)tiktok\.com$/i.test(url.hostname)) return null;
      return url;
    } catch { return null; }
  };
  const targetURL = video => {
    const direct = video.currentSrc || video.src || video.querySelector('source')?.src || '';
    if (!tiktok) return /^https?:/i.test(direct) ? direct : location.href;
    // Feed navigation leaves location at /vi-VN/. Resolve only this player's
    // item, never a post elsewhere on the page or an expiring CDN/blob URL.
    const item = video.closest('article,[data-e2e="recommend-list-item-container"]');
    const player = video.closest('[id^="xgwrapper-"]');
    const id = player?.id.match(/^xgwrapper-\d+-(\d{15,22})$/)?.[1];
    const post = value => {
      const url = tiktokURL(value);
      const match = url?.pathname.match(/^\/@([\w.-]+)\/(video|photo)\/(\d{15,22})\/?$/);
      return match && (!id || id === match[3]) ? `https://www.tiktok.com/@${match[1]}/${match[2]}/${match[3]}` : null;
    };
    if (item) {
      const posts = new Set([...item.querySelectorAll('a[href]')].map(a => post(a.href)).filter(Boolean));
      if (posts.size > 1) return null;
      if (posts.size === 1) return [...posts][0];
      if (id) {
        const primary = item.querySelectorAll('a[data-e2e="video-author-avatar"][href]');
        const authors = new Set([...(primary.length ? primary : item.querySelectorAll('a[href]'))]
          .map(a => tiktokURL(a.href)?.pathname.match(/^\/@([\w.-]+)\/?$/)?.[1]).filter(Boolean));
        if (authors.size === 1) return `https://www.tiktok.com/@${[...authors][0]}/video/${id}`;
      }
    }
    const detail = post(location.href);
    return detail && (id || document.querySelectorAll('video').length === 1) ? detail : null;
  };
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
      const visible = video.isConnected && eligible(video) && targetURL(video) && rect.width >= 160 && rect.height >= 90 &&
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
      if (!video.isConnected || !eligible(video) || !targetURL(video)) { host.remove(); buttons.delete(video); }
    }
    for (const video of document.querySelectorAll('video')) {
      if (!eligible(video) || !targetURL(video)) continue;
      if (buttons.has(video)) {
        const entry = buttons.get(video);
        const {host, button} = entry;
        const target = targetURL(video);
        if (entry.target !== target) {
          entry.target = target;
          button.textContent = '↓ Tải video này bằng HDM';
        }
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
        const url = targetURL(video);
        if (!url) { scan(); return; }
        try {
          const response = await api.runtime.sendMessage({action: 'download', kind: 'video', url});
          if (targetURL(video) !== url) return;
          button.textContent = response?.ok ? '✓ Đã gửi tới HDM' : 'Chưa kết nối ứng dụng HDM';
        } catch { button.textContent = 'Chưa kết nối ứng dụng HDM'; }
      });
      shadow.append(button);
      buttons.set(video, {host, button, target: targetURL(video)});
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
      observer.observe(document.documentElement, {childList: true, subtree: true, attributes: true,
        attributeFilter: tiktok ? ['src', 'id', 'href'] : ['src']});
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
