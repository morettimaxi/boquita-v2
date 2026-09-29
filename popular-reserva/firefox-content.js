(function () {
  const match = window.location.pathname.match(/^\/go\/(.+)$/);
  if (!match) return;

  const code = decodeURIComponent(match[1]);
  window.postMessage({ type: 'BOCA_EXT_READY' }, '*');

  chrome.storage.local.set({ accessCode: code }, () => {
    chrome.runtime.sendMessage({ action: 'forceRefresh' }, (result) => {
      window.postMessage({
        type: 'BOCA_EXT_DONE',
        ok: !!(result && result.ok),
        injected: result && result.injected,
        verify: result && result.verify,
        names: result && result.names,
        error: result ? result.error : 'Sin respuesta del background',
      }, '*');
    });
  });
})();
