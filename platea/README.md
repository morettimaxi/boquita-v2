# Platea laterales

`laterales-v22-multi.js` consulta los sectores asignados de un evento y reserva cuando hay lugar.
**Antes hay que correr `cookie-refresher-proxy.js`**: hace login, guarda cookies + token + sectores y los refresca cada 3 min.

Antes: instalación del [README principal](../README.md) (Node + `npm install` en esta carpeta).

## Variables

| Variable | Uso | Default |
|---|---|---|
| `BOCA_EMAIL` / `BOCA_PASSWORD` | Login del socio (password en texto plano) | — (obligatorio en el refresher) |
| `EVENT_ID` | Número de evento (URL `.../matches/868/...`) | `868` |
| `ASSIGNED_SECTORS` | Sectores a vigilar, separados por coma | `I,H` |
| `INSTANCE_ID` | Nombre de la instancia (va en el nombre del log) | `inst1` |
| `PROXY_USER` / `PROXY_PASS` | Opcional, proxy IPRoyal | vacío |

`EVENT_ID` tiene que ser **el mismo** en las dos terminales.

## 0. Instalar dependencias (una vez)

| Git Bash | PowerShell |
|---|---|
| `cd /c/projects/boquita-v2/platea && npm install` | `cd C:\projects\boquita-v2\platea; npm install` |

## 1. Terminal 1: cookies + token (primero)

**Git Bash**

```bash
cd /c/projects/boquita-v2/platea
BOCA_EMAIL=socio@mail.com BOCA_PASSWORD='clave' EVENT_ID=868 node cookie-refresher-proxy.js
```

**PowerShell**

```powershell
cd C:\projects\boquita-v2\platea
$env:BOCA_EMAIL="socio@mail.com"; $env:BOCA_PASSWORD="clave"; $env:EVENT_ID="868"
node cookie-refresher-proxy.js
```

Abre Chrome. Esperar a que diga que guardó cookies y token, y que aparezca `sectors-event-868.json` en la carpeta.
**Dejar esta terminal abierta** (refresca cada 3 min).

## 2. Terminal 2: laterales

Abrir otra terminal.

**Git Bash**

```bash
cd /c/projects/boquita-v2/platea
EVENT_ID=868 ASSIGNED_SECTORS=I,H node laterales-v22-multi.js
```

**PowerShell**

```powershell
cd C:\projects\boquita-v2\platea
$env:EVENT_ID="868"; $env:ASSIGNED_SECTORS="I,H"
node laterales-v22-multi.js
```

Con proxy, agregar antes `PROXY_USER=... PROXY_PASS=...` (Git Bash) o `$env:PROXY_USER="..."; $env:PROXY_PASS="..."` (PowerShell).

Cuando reserva escribe en `reserva.txt` y abre un video de YouTube como aviso.

## 3. Cortar

`Ctrl+C` en las dos terminales. Si quedó algún node colgado:

| Git Bash | PowerShell |
|---|---|
| `taskkill //F //IM node.exe` | `taskkill /F /IM node.exe` |

## Archivos que genera (no se suben al repo)

| Archivo | Lo genera |
|---|---|
| `queue-cookies-proxy.txt`, `shared-token-proxy.json`, `sectors-event-<id>.json` | refresher |
| `log-<fecha>-<inst>.txt`, `reserva.txt`, `data-consumption.txt` | laterales |

## Problemas

| Síntoma | Solución |
|---|---|
| `Archivo de cookies no encontrado` | No corriste el paso 1, o estás en otra carpeta. |
| `Falta BOCA_EMAIL / BOCA_PASSWORD` | Setear las variables en la misma terminal del paso 1. |
| No encuentra sectores | `EVENT_ID` distinto entre las dos terminales. |
| `npm` bloqueado en PowerShell | `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned -Force` |
