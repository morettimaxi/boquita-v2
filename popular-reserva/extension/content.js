(function () {
  const match = window.location.pathname.match(/^\/go\/(.+)$/);
  if (!match) return;

  const code = decodeURIComponent(match[1]);

  window.postMessage({ type: 'BOCA_EXT_READY' }, '*');

  chrome.storage.local.set({ accessCode: code }, () => {
    chrome.runtime.sendMessage({ action: 'forceRefresh' }, (result) => {
      if (result && result.ok) {
        window.postMessage({ type: 'BOCA_EXT_DONE', ok: true, injected: result.injected }, '*');
      } else {
        window.postMessage({
          type: 'BOCA_EXT_DONE',
          ok: false,
          error: result ? result.error : 'Sin respuesta',
        }, '*');
      }
    });
  });
})();
