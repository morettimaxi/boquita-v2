# popular-reserva

Confirma / reserva por API para cada socio de `socios.csv`.

Requiere la instalación del [README principal](../README.md).

## 1. socios.csv

No está en el repo (tiene contraseñas). Crear `popular-reserva\socios.csv`:

```
email,password
socio@gmail.com,clave
```

## 2. Cookies de la cola

En el Chrome que pasó la cola de Boca Socios: F12 → Console → escribir `allow pasting` → pegar y Enter. Deja la pestaña abierta: baja un `boca_cookies_*.json` nuevo a Downloads cada 2 min.

```javascript
(function(){function exp(){var c=document.cookie.split(';').map(function(x){var p=x.trim().split('=');return{name:p[0],value:p.slice(1).join('=')}});var d={timestamp:new Date().toISOString(),url:location.href,cookies:c,cookie_string:document.cookie};var b=new Blob([JSON.stringify(d,null,2)],{type:'application/json'});var a=document.createElement('a');var t=new Date();var pad=function(n){return String(n).padStart(2,'0')};var name='boca_cookies_'+t.getFullYear()+pad(t.getMonth()+1)+pad(t.getDate())+'_'+pad(t.getHours())+pad(t.getMinutes())+pad(t.getSeconds())+'.json';a.href=URL.createObjectURL(b);a.download=name;a.click();console.log('['+t.toLocaleTimeString()+'] Exportado '+name+' ('+c.length+' cookies)')}exp();setInterval(exp,120000);console.log('Auto-export activado: cada 2 minutos (archivo nuevo, no pisa)')})()
```

Los scripts usan solos el `boca_cookies_*.json` más nuevo de Downloads.

## 3. Qué correr en cada caso

Siempre desde esta carpeta: `cd C:\projects\boquita-v2\popular-reserva`. El número de evento sale de la URL de Boca Socios (`/matches/870/...`).

| Caso | Comando |
|---|---|
| **Activos / plenos** (titular + familia) | `python order-popu-familia-rapido.py --evento 870 --workers 8 --delay 1` |
| Activos, lanzando lento | `python order-popu-familia.py --evento 870 --workers 3` |
| Activos, solo el titular | `python order-popu.py --evento 870` |
| **Adherentes** (adicional, sin pago) | `python adherentes.py --evento 869` |
| **Copa** (adicional + pago en efectivo) | `python adicional_copa.py --evento 869` |
| **Pagar**: abre un Chrome logueado por socio | `python abrir-pago.py --csv socios.csv --evento 868` |

- `--dry-run` (en los de reserva): loguea y muestra qué haría, sin confirmar.
- Si un socio falla (clave mal, adherente, rechazo) sigue con el resto. Al final imprime un resumen.
- Si Boca devuelve 403 seguido: subir `--delay` o bajar `--workers`.

## 4. Pagar sin fila (extensión)

Subir las cookies al worker: `python upload_latest_cookies.py` (necesita `WORKER_API_KEY`).

- **Chrome:** `chrome://extensions` → Modo desarrollador → *Cargar descomprimida* → carpeta `extension`.
- **Firefox:** `about:addons` → engranaje → *Instalar complemento desde archivo* → `boca-cookies-firefox.xpi` (firmado). O doble click en `abrir-firefox.bat` (perfil Boca con la extensión).

Después abrir https://boca-cookies.rosaleseze86.workers.dev/go/Cangele2015 y entrar a Boca Socios.

## Worker (solo si hay que redeployar)

```powershell
cd server
npx wrangler login
npx wrangler secret put API_KEY
npx wrangler secret put ACCESS_CODE
npx wrangler deploy
```
