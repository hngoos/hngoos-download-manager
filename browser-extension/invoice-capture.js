(() => {
  const api = globalThis.browser || globalThis.chrome;
  if (window.__hdmInvoiceCapture) return;
  window.__hdmInvoiceCapture = true;
  let lastCapture = 0;
  window.addEventListener('beforeprint', async event => {
    if (!event.isTrusted || Date.now()-lastCapture < 5000) return;
    lastCapture = Date.now();
    const source = document.querySelector('[data-print],.print-area,.print-content,#printArea') || document.body;
    const clone = source.cloneNode(true);
    clone.querySelectorAll('script,iframe,object,embed,link,base,form,button,input,select,textarea,video,audio').forEach(node => node.remove());
    clone.querySelectorAll('*').forEach(node => {
      for (const attr of [...node.attributes]) {
        if (attr.name.startsWith('on') || ['srcset','action','href','formaction'].includes(attr.name)) node.removeAttribute(attr.name);
      }
      if (node.tagName === 'IMG' && !node.src.startsWith('data:image/')) node.removeAttribute('src');
    });
    const canvases = source.querySelectorAll('canvas');
    clone.querySelectorAll('canvas').forEach((canvas, index) => {
      try { const image = document.createElement('img'); image.src = canvases[index].toDataURL(); canvas.replaceWith(image); }
      catch { canvas.remove(); }
    });
    const styles = [...document.querySelectorAll('style')].map(item => item.outerHTML).join('');
    const html = styles+clone.outerHTML;
    const query = new URL(location.href).searchParams;
    const matched = source.innerText.match(/(?:mã\s*(?:đơn|vận đơn)(?:\s*hàng)?|order\s*(?:id|number)|tracking\s*(?:id|number))\s*[:#：]?\s*([A-Z0-9-]{6,40})/i);
    const order_id = matched?.[1] || query.get('order_id') || query.get('orderId') || document.title || 'phieu-giao-hang';
    if (new TextEncoder().encode(html).length > 90000) {
      api.runtime.sendMessage({action:'invoice-error', error:'Phiếu quá lớn để tự lưu; dùng Lưu PDF trong hộp In.'}); return;
    }
    try {
      const result = await api.runtime.sendMessage({action:'save-invoice', html, order_id});
      if (!result?.ok) await api.runtime.sendMessage({action:'invoice-error', error:result?.error || 'Không lưu được phiếu vào HDM.'});
    } catch { /* Keep normal printing available. */ }
  });
})();
