(() => {
  if (window.__courtAndroidInstalled) return;
  window.__courtAndroidInstalled = true;
  let port = null;
  const pending = new Map();
  let nextRequestId = 0;
  let status = { available: true, biometricAvailable: false, saved: false, biometricSaved: false };
  const request = (action, body = {}) => new Promise((resolve, reject) => {
    if (!port) { reject(new Error('تكامل أندرويد غير متاح.')); return; }
    const requestId = 'android-' + (++nextRequestId);
    pending.set(requestId, { resolve, reject });
    port.postMessage(JSON.stringify({ action, requestId, ...body }));
  });
  const notifyStatus = value => {
    status = value;
    window.dispatchEvent(new CustomEvent('albayda-native-status', { detail: value }));
  };
  window.addEventListener('message', event => {
    if (event.data === 'court-android-init' && event.ports.length) {
      if (port) port.close();
      port = event.ports[0];
      port.onmessage = message => {
        let data;
        try { data = JSON.parse(message.data); } catch { return; }
        if (data.type === 'credentialStatus' && data.payload) notifyStatus(data.payload);
        if (data.replyTo && pending.has(data.replyTo)) {
          const operation = pending.get(data.replyTo);
          pending.delete(data.replyTo);
          if (data.success) operation.resolve(data.payload || {});
          else operation.reject(new Error(data.error || 'تعذر إتمام العملية.'));
        }
      };
      port.start();
      window.AlbaydaAndroid = Object.freeze({
        version: 2,
        getStatus: () => request('credential-status').then(value => { notifyStatus(value); return value; }),
        saveCredentials: ({ name, password }) => request('credential-save', { name, password }).then(() => undefined),
        loginWithSaved: () => request('credential-login'),
        loginWithBiometric: () => request('credential-biometric'),
        forgetCredentials: () => request('credential-forget').then(() => undefined),
      });
      window.dispatchEvent(new Event('albayda-native-ready'));
      window.AlbaydaAndroid.getStatus().catch(() => {});
    }
  });
  const send = body => { if (port) port.postMessage(JSON.stringify(body)); };
  const originalClick = HTMLAnchorElement.prototype.click;
  const save = anchor => {
    if (!anchor.href.startsWith('blob:') || !port) return false;
    fetch(anchor.href).then(response => response.blob()).then(blob => {
      if (blob.size > 32 * 1024 * 1024) {
        alert('حجم الملف أكبر من حد التنزيل داخل النسخة التجريبية (32 ميجابايت). افتح التطبيق في المتصفح لتنزيله.');
        return;
      }
      const reader = new FileReader();
      reader.onload = () => send({ action: 'save', name: anchor.download || 'document', mime: blob.type || 'application/octet-stream', data: reader.result });
      reader.onerror = () => send({ action: 'error' });
      reader.readAsDataURL(blob);
    }).catch(() => send({ action: 'error' }));
    return true;
  };
  HTMLAnchorElement.prototype.click = function() {
    if (save(this)) return;
    return originalClick.call(this);
  };
  document.addEventListener('click', event => {
    const anchor = event.target && event.target.closest && event.target.closest('a');
    if (anchor && save(anchor)) { event.preventDefault(); event.stopImmediatePropagation(); }
  }, true);
  window.print = () => send({ action: 'print' });
  window.close = () => send({ action: 'close' });
  const originalOpen = window.open;
  window.open = function(url, target, features) {
    if (!url) return null;
    let resolved;
    try { resolved = new URL(String(url), location.href); } catch { return null; }
    if (['https:', 'http:', 'tel:', 'mailto:', 'whatsapp:', 'tg:'].includes(resolved.protocol)) {
      location.assign(resolved.href);
      return null;
    }
    return originalOpen.call(window, url, target, features);
  };
})();
