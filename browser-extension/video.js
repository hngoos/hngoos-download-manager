(() => {
  const chrome = globalThis.browser || globalThis.chrome;
  if (window.__hngoosVideoButtons) return;
  window.__hngoosVideoButtons = true;
  const buttons = new Map();
  let observer;
  const scan = () => {
    for (const [video, button] of buttons) {
      if (!video.isConnected) { button.remove(); buttons.delete(video); }
    }
    document.querySelectorAll('video').forEach(video => {
      if (buttons.has(video)) {
        const button = buttons.get(video);
        if (!button.isConnected) video.before(button);
        return;
      }
      const button = document.createElement('button');
      button.dataset.hdmVideoDownload = '';
      button.textContent = '⬇ Tải video này bằng HDM';
      button.style.cssText = 'display:block;position:relative;z-index:1;background:#1872da;color:#fff;border:0;padding:8px 12px;border-radius:6px;cursor:pointer;font:13px system-ui;margin:5px 0;';
      button.addEventListener('click', async event => {
        // Pages can call button.click(); only a real user gesture may request a download.
        if (!event.isTrusted) return;
        event.preventDefault(); event.stopPropagation();
        const direct = video.currentSrc || video.src;
        const response = await chrome.runtime.sendMessage({action: 'download', kind: 'video',
          url: /^https?:/.test(direct) ? direct : location.href});
        button.textContent = response?.ok ? '✓ Đã gửi tới HDM' : `Lỗi: ${response?.error || 'Chưa kết nối ứng dụng'}`;
      });
      buttons.set(video, button);
      video.before(button);
    });
  };
  const show = enabled => {
    observer?.disconnect();
    if (enabled) {
      scan();
      observer ||= new MutationObserver(scan);
      observer.observe(document.documentElement, {childList: true, subtree: true});
    } else {
      for (const button of buttons.values()) button.remove();
      buttons.clear();
    }
  };
  chrome.storage.onChanged.addListener((changes, area) => {
    if (area === 'local' && changes.videoButton) show(!!changes.videoButton.newValue);
  });
  chrome.storage.local.get(['videoButton']).then(settings => show(!!settings.videoButton));
})();
