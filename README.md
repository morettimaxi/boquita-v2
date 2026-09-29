# boquita-v2

| Carpeta | Qué hace | Guía |
|---|---|---|
| `queue-manager/` | Pasa la cola de Boca Socios con varias sesiones de Chrome | [queue-manager/README.md](queue-manager/README.md) |
| `popular-reserva/` | Confirma / reserva popular por API para los socios de `socios.csv` + extensión para pagar sin fila | [popular-reserva/README.md](popular-reserva/README.md) |
| `platea/` | Laterales (Node): reserva plateas por sector | [platea/README.md](platea/README.md) |

Todos los comandos están en dos versiones: **Git Bash** y **PowerShell**. Usá la que tengas abierta.

| | Git Bash | PowerShell |
|---|---|---|
| Rutas | `/c/projects/boquita-v2` | `C:\projects\boquita-v2` |
| Variable para un comando | `EVENT_ID=868 node x.js` | `$env:EVENT_ID="868"; node x.js` |
| Correr un `.bat` | `cmd //c abrir-firefox.bat` | `.\abrir-firefox.bat` |
| Cortar un script | `Ctrl+C` | `Ctrl+C` |

---

## 1. Instalar (una sola vez por PC)

### 1.1 Programas

Abrir **PowerShell** (winget se corre ahí):

```powershell
winget install -e --id Git.Git
winget install -e --id Python.Python.3.12
winget install -e --id OpenJS.NodeJS.LTS
winget install -e --id Google.Chrome
winget install -e --id Mozilla.Firefox
winget install -e --id GitHub.cli
Set-ExecutionPolicy -Scope CurrentUser RemoteSigned -Force
```

`Set-ExecutionPolicy` es para que PowerShell deje correr `npm` / `npx`. Cerrar **todas** las terminales y abrir una nueva.

### 1.2 Bajar el repo e instalar dependencias

**Git Bash**

```bash
gh auth login
mkdir -p /c/projects && cd /c/projects
gh repo clone morettimaxi/boquita-v2
cd /c/projects/boquita-v2
python -m pip install -r requirements.txt
cd platea && npm install && cd ..
```

**PowerShell**

```powershell
gh auth login
mkdir C:\projects -Force
cd C:\projects
gh repo clone morettimaxi/boquita-v2
cd C:\projects\boquita-v2
python -m pip install -r requirements.txt
cd platea; npm install; cd ..
```

`gh auth login`: elegir GitHub.com → HTTPS → login con el navegador, con la cuenta que tiene acceso al repo.
Si `python` abre la Microsoft Store, usar `py` en lugar de `python`.

### 1.3 Variables fijas (quedan guardadas en Windows)

Sirve igual en Git Bash y PowerShell:

```bash
setx WORKER_API_KEY "PEGAR_LA_KEY_ACA"
setx PYTHONUTF8 1
```

- `WORKER_API_KEY`: para subir cookies al worker (queue_bot, upload_*). Pedirla, no está en el repo.
- `PYTHONUTF8=1`: evita errores de acentos/emojis en la consola.

Cerrar y abrir la terminal para que las tome. Comprobar:

| Git Bash | PowerShell |
|---|---|
| `echo $WORKER_API_KEY` | `echo $env:WORKER_API_KEY` |

### 1.4 Actualizar el repo (cuando haya cambios)

| Git Bash | PowerShell |
|---|---|
| `cd /c/projects/boquita-v2 && git pull` | `cd C:\projects\boquita-v2; git pull` |

---

## 2. Orden de un día de partido

1. **Pasar la cola** → [queue-manager](queue-manager/README.md): `python queue_bot.py`, dashboard en http://localhost:5000. Cuando una sesión pasa, **sube automáticamente las cookies al Worker**.
2. **Obtener cookies para popular** → En `popular-reserva`:
   - Ver cuándo se generaron: `python download_latest_cookies.py --status` (o abrí `https://boca-cookies.rosaleseze86.workers.dev/api/cookies/status`)
   - Bajar las cookies: `python download_latest_cookies.py` (las guarda en `Downloads` y local).
3. **Popular**: correr el script de reserva → [popular-reserva](popular-reserva/README.md):
   `python order-popu-familia-rapido.py --evento 870 --workers 8 --delay 1`
4. **Pagar sin fila**: abrir la extensión en Firefox o Chrome con el link `/go/Cangele2015` → [popular-reserva, paso 5](popular-reserva/README.md#5-pagar-sin-fila-extensión).
5. **Plateas**: primero `cookie-refresher-proxy.js`, después `laterales-v22-multi.js` → [platea](platea/README.md).
