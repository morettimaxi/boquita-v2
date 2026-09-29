# boquita-v2

- `queue-manager/` — pasa la cola de Boca Socios con varias sesiones de Chrome. Ver [queue-manager/README.md](queue-manager/README.md).
- `popular-reserva/` — confirma / reserva por API para los socios de `socios.csv`, y extensión para pagar sin fila. Ver [popular-reserva/README.md](popular-reserva/README.md).

## Instalar (Windows, una sola vez)

PowerShell:

```powershell
winget install -e --id Git.Git
winget install -e --id Python.Python.3.12
winget install -e --id Google.Chrome
winget install -e --id GitHub.cli
```

Cerrar y abrir PowerShell:

```powershell
gh auth login
mkdir C:\projects -Force
cd C:\projects
gh repo clone morettimaxi/boquita-v2
cd C:\projects\boquita-v2
python -m pip install -r requirements.txt
setx WORKER_API_KEY "PEGAR_LA_KEY_ACA"
```

Cerrar y abrir PowerShell otra vez (para que tome `WORKER_API_KEY`).
