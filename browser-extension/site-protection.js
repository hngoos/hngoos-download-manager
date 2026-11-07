(() => {
  const api = globalThis.browser || globalThis.chrome;
  if (globalThis.__hdmProtection) return;
  globalThis.__hdmProtection = true;
  let style;
  let settings = {};
  const sensitive = () => /(^|\.)(gov\.vn|paypal\.com|stripe\.com|accounts\.google\.com|login\.microsoftonline\.com)$/.test(location.hostname)
    || /(?:bank|banking|payment|checkout|login|signin|oauth|account)/i.test(location.hostname+location.pathname)
    || !!document.querySelector('input[type="password"],input[autocomplete="cc-number"]');
  const active = () => !sensitive() && ['ads', 'strong'].includes(settings.mode)
    && !(settings.allowSites || []).some(host => location.hostname === host || location.hostname.endsWith('.'+host));
  async function refresh() {
    settings = await api.storage.local.get(['mode', 'allowSites', 'hiddenElements', 'compiledRules']);
    style?.remove(); style = null;
    if (!active()) return;
    const selectors = (settings.hiddenElements?.[location.hostname] || []).slice(0, 100);
    if (selectors.length) {
      style = document.createElement('style');
      style.textContent = selectors.map(selector => `${selector}{display:none!important}`).join('\n');
      document.documentElement.append(style);
    }
  }
  api.storage.onChanged.addListener(refresh);
  refresh();
  const overlay = document.createElement('div');
  overlay.style.cssText = 'position:fixed;pointer-events:none;z-index:2147483647;border:2px solid #a78bfa;background:#a78bfa22;display:none';
  let selecting = false;
  let target;
  const excluded = element => element.matches('main,article,h1,h2,h3,header,nav,[role="main"]')
    || element.closest('video,audio,form')
    || ['HTML', 'BODY'].includes(element.tagName) || !!element.querySelector('video,audio,h1,main,article');
  function move(event) {
    if (!selecting) return;
    target = event.target;
    if (excluded(target)) { overlay.style.display = 'none'; return; }
    const box = target.getBoundingClientRect();
    Object.assign(overlay.style, {display:'block',left:box.x+'px',top:box.y+'px',width:box.width+'px',height:box.height+'px'});
  }
  function cancel() { selecting = false; overlay.remove(); }
  function selectorFor(element) {
    if (element.id) return '#'+CSS.escape(element.id);
    const parts = [];
    while (element && element !== document.body && parts.length < 8) {
      let part = element.tagName.toLowerCase();
      const siblings = [...element.parentElement.children].filter(e => e.tagName === element.tagName);
      if (siblings.length > 1) part += ':nth-of-type('+(siblings.indexOf(element)+1)+')';
      parts.unshift(part); element = element.parentElement;
    }
    return 'body > '+parts.join(' > ');
  }
  document.addEventListener('pointermove', move, true);
  document.addEventListener('keydown', event => { if (event.key === 'Escape') cancel(); }, true);
  document.addEventListener('click', async event => {
    if (!selecting || !event.isTrusted) return;
    event.preventDefault(); event.stopImmediatePropagation();
    if (excluded(event.target)) return;
    const selector = selectorFor(event.target);
    if (!confirm('Ẩn phần tử này trên '+location.hostname+'? Có thể khôi phục bằng “Về mặc định”.')) { cancel(); return; }
    const fresh = await api.storage.local.get(['hiddenElements']);
    const hiddenElements = fresh.hiddenElements || {};
    hiddenElements[location.hostname] = [...new Set([...(hiddenElements[location.hostname] || []), selector])].slice(0, 100);
    await api.storage.local.set({hiddenElements});
    cancel(); await refresh();
  }, true);
  api.runtime.onMessage.addListener((message, _sender, respond) => {
    if (message.action !== 'pick-element') return;
    (async () => {
      await refresh();
      if (!active()) return {ok:false,error:'Trang nhạy cảm hoặc bộ lọc đang tắt; không chọn phần tử ở đây.'};
      selecting = true; document.documentElement.append(overlay);
      return {ok:true};
    })().then(respond, error => respond({ok:false,error:error.message}));
    return true;
  });
  function removeAdOverlays(root = document) {
    if (!active()) return;
    for (const element of root.querySelectorAll?.('a[href],iframe[src]') || []) {
      let host;
      try { host = new URL(element.href || element.src).hostname; } catch { continue; }
      const known = (settings.compiledRules || []).some(rule => {
        if (rule.condition.initiatorDomains || rule.condition.excludedInitiatorDomains
            || rule.condition.domainType === 'firstParty') return false;
        const match = rule.action.type === 'block' && rule.condition.urlFilter?.match(/^\|\|([a-z0-9.-]+)\^$/i);
        return match && host !== location.hostname && !host.endsWith('.'+location.hostname)
          && !location.hostname.endsWith('.'+host) && (host === match[1] || host.endsWith('.'+match[1]));
      });
      if (!known || element.querySelector('video,audio')) continue;
      const rectangle = element.getBoundingClientRect();
      const overVideo = [...document.querySelectorAll('video')].some(video => {
        const box = video.getBoundingClientRect();
        return rectangle.left < box.right && rectangle.right > box.left && rectangle.top < box.bottom && rectangle.bottom > box.top;
      });
      if (overVideo && !excluded(element)) element.remove();
    }
  }
  let scheduled = false;
  new MutationObserver(() => {
    if (scheduled) return;
    scheduled = true;
    setTimeout(() => { scheduled=false; removeAdOverlays(); },300);
  }).observe(document.documentElement,{childList:true,subtree:true});
  refresh().then(() => removeAdOverlays());
})();
