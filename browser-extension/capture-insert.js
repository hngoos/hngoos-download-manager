(() => {
  if (globalThis.__hdmInsertCapture) return;
  globalThis.__hdmInsertCapture = true;
  const api = globalThis.browser || globalThis.chrome;
  let timer;
  const send = held => api.runtime.sendMessage({action:'capture-insert',held}).catch(()=>{});
  addEventListener('keydown', event => {
    if (event.key !== 'Insert' || !event.isTrusted || timer) return;
    send(true);
    timer = setInterval(()=>send(true),1000);
  },true);
  const release = () => { if (timer) { clearInterval(timer); timer=undefined; send(false); } };
  addEventListener('keyup',event=>{if(event.key==='Insert' && event.isTrusted) release();},true);
  addEventListener('blur',release);
})();
