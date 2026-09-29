(async () => {
  // El browser real tiene localStorage viejo de Queue-it.
  // El Chrome limpio no. Por eso uno anda y el otro no.
  try { localStorage.clear(); } catch (e) {}
  try { sessionStorage.clear(); } catch (e) {}

  const data = await chrome.storage.local.get(['bocaLocalStorage', 'bocaLSTimestamp']);
  if (!data.bocaLocalStorage) return;

  const ageMs = Date.now() - (data.bocaLSTimestamp || 0);
  if (ageMs > 3600000) return;

  for (const [key, value] of Object.entries(data.bocaLocalStorage)) {
    try {
      localStorage.setItem(key, typeof value === 'string' ? value : JSON.stringify(value));
    } catch (e) {}
  }

  await chrome.storage.local.remove(['bocaLocalStorage', 'bocaLSTimestamp']);
})();
