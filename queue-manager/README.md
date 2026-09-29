# queue-manager

Abre varias sesiones de Chrome en la cola de Boca Socios y muestra un dashboard.

Requiere la instalación del [README principal](../README.md).

## Correr

```powershell
cd C:\projects\boquita-v2\queue-manager
python queue_bot.py
```

Abrir http://localhost:5000 y lanzar sesiones. `Ctrl+C` para cortar.

## Qué hay

| Archivo | Para qué |
|---|---|
| `queue_bot.py` | El que se usa. Cuando una sesión pasa la cola guarda `session_N_cookies.json` (con HttpOnly + localStorage) y lo sube al worker. |
| `queue_manager-v4.py` | Versión anterior estable (sin subida al worker). No modificar. |
| `upload_cookies.py` | Subir a mano una sesión al worker: `python upload_cookies.py 3` |
| `capture_browser.py` | Abre Chrome, entrás a mano, captura cookies: `python capture_browser.py --upload` |

`upload_cookies.py`, `capture_browser.py` y la subida de `queue_bot.py` necesitan `WORKER_API_KEY`.
