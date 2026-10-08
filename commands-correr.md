# Qué correr — boquita-v2

Todo esto es para **Git Bash** en Windows. La carpeta de trabajo es `C:\projects\boquita-v2`.

El último evento de popular anotado fue el **870**. El de copa fue el **869**. Si el partido es otro, cambiá ese número en el comando.

La clave del Worker ya está escrita en los Python que suben. No hace falta exportarla.

En Mac los mismos Python valen con `python3` y la ruta `~/projects/boquita-v2`. La instalación de Mac está en el `README.md`, sección 1.5.

---

## Instalar en Windows con Git Bash (una sola vez)

Abrí **PowerShell** solo para instalar los programas. `winget` no siempre está en Git Bash.

```powershell
winget install -e --id Git.Git
winget install -e --id Python.Python.3.12
winget install -e --id OpenJS.NodeJS.LTS
winget install -e --id Google.Chrome
winget install -e --id Mozilla.Firefox
winget install -e --id GitHub.cli
```

Cerrá todas las terminales. Abrí **Git Bash** (no PowerShell).

Si `python` abre la Microsoft Store, en los pasos de abajo usá `py` en lugar de `python`.

Entrá a GitHub con la cuenta que puede ver el repo:

```bash
gh auth login
```

Elegí GitHub.com, HTTPS, y el login del navegador.

Cloná e instalá las librerías:

```bash
mkdir -p /c/projects
cd /c/projects
gh repo clone morettimaxi/boquita-v2
cd /c/projects/boquita-v2
python -m pip install -r requirements.txt
cd platea
npm install
cd ..
```

Comprobá que quedó todo:

```bash
python --version
node --version
gh auth status
```

`socios.csv` no está en GitHub. Copialo a mano desde la PC que ya lo tiene, y dejalo en:

```text
/c/projects/boquita-v2/popular-reserva/socios.csv
```

Chrome tiene que estar instalado. La primera vez que corras `queue_bot.py`, Selenium baja el driver solo.

Cuando haya cambios nuevos en GitHub:

```bash
cd /c/projects/boquita-v2
git pull
```

---

## 0. Entrar a la carpeta de reservas

```bash
cd /c/projects/boquita-v2/popular-reserva
```

Las cuentas están en `socios.csv` (email y contraseña).

---

## 1. Cookies — caso automático

En la PC que hace la fila:

```bash
cd /c/projects/boquita-v2/queue-manager
python queue_bot.py
```

Dashboard: `http://localhost:5000`

Ahí se lanzan las sesiones. Cuando una pasa la fila, sube sus cookies sola al Worker. Cada sesión sube una vez. Si una subida falla, el JSON queda en esa carpeta (`session_N_cookies.json`) y reintenta.

La copia de cloud hace lo mismo:

```bash
cd /c/projects/boquita-v2/cloud
python queue_bot_cloud.py
```

Desde la otra PC, mirar la fila:

```bash
cd /c/projects/boquita-v2/popular-reserva
python download_latest_cookies.py --watch
```

Ver solo el estado, sin bajar archivo:

```bash
python download_latest_cookies.py --status
python download_latest_cookies.py --queue
```

Cuando ya pasaron, bajar la última cookie:

```bash
python download_latest_cookies.py
```

La guarda en:

- `/c/projects/boquita-v2/popular-reserva/boca_cookies_worker.json`
- `/c/Users/moret/Downloads/boca_cookies_worker.json`

Si esa última no sirve, listar las que quedaron guardadas (hasta 10) y bajar otra:

```bash
python download_latest_cookies.py --list
python download_latest_cookies.py --id ID_DEL_JUEGO
```

Si tienen 60 minutos o más, no se bajan. Para bajarlas igual:

```bash
python download_latest_cookies.py --force
```

Desde el celular, sin bajar archivo:

- Fila: `https://boca-cookies.rosaleseze86.workers.dev/api/queue/status`
- Cookies: `https://boca-cookies.rosaleseze86.workers.dev/api/cookies/status`

---

## 2. Cookies — caso browser local

Si el bot no subió, o querés un respaldo desde un Chrome o Firefox tuyo que ya pasó la fila:

1. Dejá abierta la pestaña de Boca Socios que ya pasó la fila.
2. `F12` → **Console**.
3. Si Chrome lo pide, escribí `allow pasting` y Enter.
4. Pegá esto y Enter:

```javascript
(function(){function exp(){var c=document.cookie.split(';').map(function(x){var p=x.trim().split('=');return{name:p[0],value:p.slice(1).join('=')}});var d={timestamp:new Date().toISOString(),url:location.href,cookies:c,cookie_string:document.cookie};var b=new Blob([JSON.stringify(d,null,2)],{type:'application/json'});var a=document.createElement('a');var t=new Date();var pad=function(n){return String(n).padStart(2,'0')};var name='boca_cookies_'+t.getFullYear()+pad(t.getMonth()+1)+pad(t.getDate())+'_'+pad(t.getHours())+pad(t.getMinutes())+pad(t.getSeconds())+'.json';a.href=URL.createObjectURL(b);a.download=name;a.click();console.log('['+t.toLocaleTimeString()+'] Exportado '+name+' ('+c.length+' cookies)')}exp();setInterval(exp,120000);console.log('Auto-export activado: cada 2 minutos (archivo nuevo, no pisa)')})()
```

El browser baja un archivo nuevo a `Downloads` cada 2 minutos:

```text
boca_cookies_YYYYMMDD_HHMMSS.json
```

Ese export de consola no lee cookies `HttpOnly`. Si después el login no entra, usá las del bot (`session_N_cookies.json`), que sí las capturan.

Subir al Worker el export más nuevo de `Downloads` o de la carpeta actual:

```bash
cd /c/projects/boquita-v2/popular-reserva
python upload_latest_cookies.py --evento 869
```

O un archivo puntual:

```bash
python upload_latest_cookies.py \
  --file /c/Users/moret/Downloads/boca_cookies_YYYYMMDD_HHMMSS.json \
  --evento 869
```

Si anda, imprime `OK: N criticas, N total`. Después, en la otra PC:

```bash
python download_latest_cookies.py
```

---

## 3. Copa

Usa `socios.csv` y el `boca_cookies*.json` más nuevo de esta carpeta o de `Downloads`.

Sale una cuenta cada unos 7 segundos. La corrida queda estimada entre 3:30 y 4:00. No corta al llegar a los 4 minutos: espera a que terminen todas. Si una falla, sigue con la siguiente y al final imprime el reporte.

```bash
cd /c/projects/boquita-v2/popular-reserva
python adicional_copa.py --evento 869
```

Probar login sin comprar:

```bash
python adicional_copa.py --evento 869 --dry-run
```

---

## 4. Adherentes

```bash
cd /c/projects/boquita-v2/popular-reserva
python adherentes.py --evento 870 --dry-run
python adherentes.py --evento 870
```

Con cinco procesos:

```bash
python adherentes.py --evento 870 --workers 5
```

---

## 5. Popular con familia

```bash
cd /c/projects/boquita-v2/popular-reserva
python order-popu-familia-rapido.py --evento 870 --dry-run
python order-popu-familia-rapido.py --evento 870 --workers 8 --delay 1
```

---

## 6. Abrir Chromes para pagar

Un Chrome por cuenta de `socios.csv`, con la cookie más nueva:

```bash
cd /c/projects/boquita-v2/popular-reserva
python abrir-pago.py --csv socios.csv --evento 869
```

Forzar el archivo bajado del Worker:

```bash
python abrir-pago.py --csv socios.csv --evento 869 \
  --cookies boca_cookies_worker.json
```

Firefox con la extensión, sin abrir un Chrome por socio:

```bash
cd /c/projects/boquita-v2/popular-reserva
cmd //c abrir-firefox.bat
```

Después abrir:

`https://boca-cookies.rosaleseze86.workers.dev/go/Cangele2015`

---

## Orden del día

```bash
cd /c/projects/boquita-v2/queue-manager
python queue_bot.py
```

En la otra terminal, cuando la fila avance:

```bash
cd /c/projects/boquita-v2/popular-reserva
python download_latest_cookies.py --watch
```

Cuando haya cookie:

```bash
python adicional_copa.py --evento 869
python abrir-pago.py --csv socios.csv --evento 869
```

Si el bot no subió, usá el caso del browser (sección 2) y después los mismos dos comandos de arriba.
