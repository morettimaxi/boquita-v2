# Usuarios: doble click en abrir-firefox.bat
# No necesita Node ni Python.

$ErrorActionPreference = 'Stop'
$Root = $PSScriptRoot
$ExtSrc = Join-Path $Root 'extension'
$FfExt = Join-Path $Root '.firefox-ext'
$GoUrl = 'https://boca-cookies.rosaleseze86.workers.dev/go/Cangele2015'
$ProfileName = 'Boca'
$Port = 2828

function Find-Firefox {
    @(
        "$env:ProgramFiles\Mozilla Firefox\firefox.exe",
        "${env:ProgramFiles(x86)}\Mozilla Firefox\firefox.exe"
    ) | Where-Object { Test-Path $_ } | Select-Object -First 1
}

function Build-FirefoxExt {
    if (-not (Test-Path $ExtSrc)) { throw "No esta la carpeta extension: $ExtSrc" }
    New-Item -ItemType Directory -Force -Path $FfExt | Out-Null
    Copy-Item (Join-Path $ExtSrc 'popup.js') (Join-Path $FfExt 'popup.js') -Force
    Copy-Item (Join-Path $ExtSrc 'popup.html') (Join-Path $FfExt 'popup.html') -Force
    Copy-Item (Join-Path $Root 'firefox-background.js') (Join-Path $FfExt 'background.js') -Force
    Copy-Item (Join-Path $Root 'firefox-content.js') (Join-Path $FfExt 'content.js') -Force
    Copy-Item (Join-Path $Root 'firefox-ls.js') (Join-Path $FfExt 'ls.js') -Force
    $man = Get-Content (Join-Path $ExtSrc 'manifest.json') -Raw | ConvertFrom-Json
    $man.background = @{ scripts = @('background.js') }
    $man | ConvertTo-Json -Depth 8 | Set-Content (Join-Path $FfExt 'manifest.json') -Encoding UTF8
}

function Ensure-BocaProfile([string]$Firefox) {
    $ini = Join-Path $env:APPDATA 'Mozilla\Firefox\profiles.ini'
    if (Test-Path $ini) {
        if (Select-String -Path $ini -Pattern '^Name=Boca\s*$' -Quiet) { return }
    }
    Write-Host 'Creando perfil Boca...'
    Start-Process $Firefox -ArgumentList @('-CreateProfile', $ProfileName) -Wait -WindowStyle Hidden
}

function Read-Marionette([System.IO.Stream]$Stream) {
    $sb = New-Object System.Text.StringBuilder
    while ($true) {
        $b = $Stream.ReadByte()
        if ($b -lt 0) { throw 'Marionette cerro la conexion' }
        if ([char]$b -eq ':') { break }
        [void]$sb.Append([char]$b)
    }
    $len = [int]$sb.ToString()
    $buf = New-Object byte[] $len
    $got = 0
    while ($got -lt $len) {
        $n = $Stream.Read($buf, $got, $len - $got)
        if ($n -le 0) { throw 'Marionette corte a mitad de mensaje' }
        $got += $n
    }
    return [Text.Encoding]::UTF8.GetString($buf)
}

function Send-Marionette([System.IO.Stream]$Stream, [int]$Id, [string]$Command, $Params) {
    $paramsJson = if ($null -eq $Params) { '{}' } else { ($Params | ConvertTo-Json -Compress -Depth 8) }
    $body = "[0,$Id,`"$Command`",$paramsJson]"
    $bytes = [Text.Encoding]::UTF8.GetBytes($body)
    $packet = [Text.Encoding]::UTF8.GetBytes("$($bytes.Length):") + $bytes
    $Stream.Write($packet, 0, $packet.Length)
    $Stream.Flush()
    return Read-Marionette $Stream
}

$firefox = Find-Firefox
if (-not $firefox) { Write-Host 'ERROR: no encuentro Firefox.'; Read-Host 'Enter'; exit 1 }

Write-Host 'Preparando extension...'
Build-FirefoxExt
Ensure-BocaProfile $firefox

Get-NetTCPConnection -LocalPort $Port -ErrorAction SilentlyContinue |
    ForEach-Object { Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue }

Write-Host 'Abriendo Firefox (perfil Boca)...'
$ff = Start-Process $firefox -ArgumentList @(
    '-P', $ProfileName,
    '-no-remote',
    '-marionette',
    'about:blank'
) -PassThru

$client = $null
$stream = $null
for ($i = 0; $i -lt 40; $i++) {
    Start-Sleep -Milliseconds 400
    try {
        $client = New-Object System.Net.Sockets.TcpClient
        $client.Connect('127.0.0.1', $Port)
        $stream = $client.GetStream()
        $stream.ReadTimeout = 20000
        break
    } catch {
        if ($client) { $client.Dispose(); $client = $null }
    }
}
if (-not $stream) {
    Write-Host 'ERROR: Firefox no abrio Marionette (puerto 2828).'
    Read-Host 'Enter'
    exit 1
}

try {
    $hello = Read-Marionette $stream
    Write-Host "Marionette: $hello"
    $r1 = Send-Marionette $stream 1 'WebDriver:NewSession' @{ capabilities = @{ alwaysMatch = @{} } }
    Write-Host "session: $r1"
    $r2 = Send-Marionette $stream 2 'Addon:Install' @{ path = $FfExt; temporary = $true }
    Write-Host "extension: $r2"
    if ($r2 -match '"error"' -and $r2 -notmatch '"error":null') {
        throw "No se pudo instalar la extension: $r2"
    }
    $r3 = Send-Marionette $stream 3 'WebDriver:Navigate' @{ url = $GoUrl }
    Write-Host "go: $r3"
} finally {
    if ($stream) { $stream.Dispose() }
    if ($client) { $client.Dispose() }
}

Write-Host ''
Write-Host 'Listo. Firefox Boca ya tiene la extension. Podes cerrar esta ventana.'
Read-Host 'Enter'
