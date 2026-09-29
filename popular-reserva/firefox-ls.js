(async () => {
  try {
    if (sessionStorage.getItem('bocaFfLsDone') === '1') return;
    sessionStorage.setItem('bocaFfLsDone', '1');
  } catch (e) {}

  try { localStorage.clear(); } catch (e) {}

  const data = await chrome.storage.local.get(['bocaPageCookies', 'bocaLocalStorage']);
  const cookies = data.bocaPageCookies || [];
  for (const c of cookies) {
    const name = c.name || '';
    if (name.startsWith('_ga') || name.startsWith('_cl')) continue;
    if (name.startsWith('QueueIT') && /RedirectType(?:=|%3D)queue/i.test(c.value || '')) continue;
    try {
      document.cookie = [
        `${c.name}=${c.value}`,
        `path=${c.path || '/'}`,
        `domain=.bocajuniors.com.ar`,
        'secure',
        'samesite=lax',
        'max-age=86400',
      ].join('; ');
    } catch (e) {}
  }

  if (data.bocaLocalStorage) {
    for (const [key, value] of Object.entries(data.bocaLocalStorage)) {
      try {
        localStorage.setItem(key, typeof value === 'string' ? value : JSON.stringify(value));
      } catch (e) {}
    }
  }
})();
