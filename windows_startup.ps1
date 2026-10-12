$ErrorActionPreference = "Stop"

$PortalDir = "D:\python\amz_portal"
$PythonExe = "C:\Users\Windows\AppData\Local\Python\bin\python.exe"
$PortalScript = Join-Path $PortalDir "portal.py"
$RuntimeDir = Join-Path $PortalDir ".portal-runtime"
$StartupLog = Join-Path $RuntimeDir "startup.log"
$PortalOutLog = Join-Path $RuntimeDir "portal.out.log"
$PortalErrorLog = Join-Path $RuntimeDir "portal.err.log"

$NginxRoot = "D:\Personal\investment\stock\stock-portal"
$NginxExe = Join-Path $NginxRoot "runtime\nginx\nginx.exe"
$NginxPrefix = "D:/Personal/investment/stock/stock-portal/nginx/"

New-Item -ItemType Directory -Force -Path $RuntimeDir | Out-Null

function Write-StartupLog {
    param([string]$Message)

    $timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    Add-Content -LiteralPath $StartupLog -Value "[$timestamp] $Message"
}

function Test-LocalPort {
    param([int]$Port)

    $client = [System.Net.Sockets.TcpClient]::new()
    try {
        $task = $client.ConnectAsync("127.0.0.1", $Port)
        return $task.Wait(1000) -and $client.Connected
    }
    catch {
        return $false
    }
    finally {
        $client.Dispose()
    }
}

try {
    if (Test-LocalPort -Port 5000) {
        Write-StartupLog "Portal already listening on port 5000."
    }
    else {
        if (-not (Test-Path -LiteralPath $PythonExe)) {
            throw "Python executable not found: $PythonExe"
        }
        if (-not (Test-Path -LiteralPath (Join-Path $PortalDir ".env"))) {
            throw "Portal environment file not found: $PortalDir\.env"
        }

        Start-Process `
            -FilePath $PythonExe `
            -ArgumentList $PortalScript `
            -WorkingDirectory $PortalDir `
            -RedirectStandardOutput $PortalOutLog `
            -RedirectStandardError $PortalErrorLog `
            -WindowStyle Hidden
        Write-StartupLog "Portal start requested on port 5000."
    }

    if (Get-Process -Name nginx -ErrorAction SilentlyContinue) {
        Write-StartupLog "Nginx is already running."
    }
    else {
        if (-not (Test-Path -LiteralPath $NginxExe)) {
            throw "Nginx executable not found: $NginxExe"
        }

        Start-Process `
            -FilePath $NginxExe `
            -ArgumentList "-p", $NginxPrefix, "-c", "nginx.conf" `
            -WorkingDirectory $NginxRoot `
            -WindowStyle Hidden
        Write-StartupLog "Nginx start requested on port 8443."
    }
}
catch {
    Write-StartupLog "Startup failed: $($_.Exception.Message)"
    throw
}
