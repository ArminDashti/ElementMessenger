# Installs or updates the local Element Messenger Docker stack (Synapse + Element Web).
# Requires Docker Desktop. Run from repo root:
#   powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\install-local-element-docker.ps1
#   powershell ... -File .\scripts\install-local-element-docker.ps1 -BuildWebApp

param(
    [switch]$BuildWebApp
)

$ErrorActionPreference = "Stop"
$RepoRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
$ComposeDir = Join-Path $RepoRoot "docker\local"
$EnvFile = Join-Path $ComposeDir ".env"
$EnvExample = Join-Path $ComposeDir ".env.example"
$SynapseData = Join-Path $ComposeDir "data\synapse"

function Ensure-EnvFile {
    if (-not (Test-Path $EnvFile)) {
        if (-not (Test-Path $EnvExample)) {
            throw "Missing $EnvExample"
        }
        Copy-Item $EnvExample $EnvFile
        Write-Host "Created $EnvFile - set SYNAPSE_ADMIN_PASSWORD before continuing." -ForegroundColor Yellow
    }
}

function Get-DotEnv {
    param([string]$Path)
    $vars = @{}
    Get-Content $Path | ForEach-Object {
        if ($_ -match '^\s*#' -or $_ -match '^\s*$') { return }
        $pair = $_ -split '=', 2
        if ($pair.Count -eq 2) {
            $vars[$pair[0].Trim()] = $pair[1].Trim()
        }
    }
    return $vars
}

function Ensure-SynapseConfig {
    param([hashtable]$EnvVars)
    New-Item -ItemType Directory -Force -Path $SynapseData | Out-Null
    $homeserver = Join-Path $SynapseData "homeserver.yaml"
    if (Test-Path $homeserver) {
        return
    }

    $serverName = $EnvVars["SYNAPSE_SERVER_NAME"]
    if (-not $serverName) { $serverName = "localhost" }
    $reportStats = $EnvVars["SYNAPSE_REPORT_STATS"]
    if (-not $reportStats) { $reportStats = "no" }

    Write-Host "Generating Synapse configuration in $SynapseData ..."
    docker run --rm `
        -v "${SynapseData}:/data" `
        -e "SYNAPSE_SERVER_NAME=$serverName" `
        -e "SYNAPSE_REPORT_STATS=$reportStats" `
        matrixdotorg/synapse:latest generate | Out-Null

    $content = Get-Content $homeserver -Raw
    if ($content -notmatch "enable_registration:") {
        $content += @"

enable_registration: true
enable_registration_without_verification: true
registration_shared_secret: "local-docker-registration-secret-change-me"
"@
        Set-Content -Path $homeserver -Value $content -NoNewline
    }
}

function Stop-LegacyElementContainer {
    $names = docker ps -a --format "{{.Names}}"
    foreach ($name in $names) {
        if ($name -ne "element-web-local") {
            continue
        }
        Write-Host "Stopping legacy container element-web-local ..."
        docker stop element-web-local | Out-Null
        docker rm element-web-local | Out-Null
    }
}

function Build-ElementWebApp {
    Write-Host "Building Element Web from this repo (apps/web) ..."
    Push-Location (Join-Path $RepoRoot "apps\web")
    try {
        pnpm build
        if ($LASTEXITCODE -ne 0) { throw "pnpm build failed in apps/web" }
    } finally {
        Pop-Location
    }
}

function Wait-SynapseReady {
    $deadline = (Get-Date).AddMinutes(3)
    do {
        try {
            $null = Invoke-WebRequest -Uri "http://127.0.0.1:8008/_matrix/client/versions" -UseBasicParsing -TimeoutSec 5
            return
        } catch {
            Start-Sleep -Seconds 3
        }
    } while ((Get-Date) -lt $deadline)
    throw "Synapse did not become ready on http://127.0.0.1:8008"
}

function Ensure-AdminUser {
    param([hashtable]$EnvVars)
    $user = $EnvVars["SYNAPSE_ADMIN_USER"]
    $pass = $EnvVars["SYNAPSE_ADMIN_PASSWORD"]
    if (-not $user -or -not $pass -or $pass -eq "changeme") {
        Write-Host "Skip admin user: set SYNAPSE_ADMIN_USER and SYNAPSE_ADMIN_PASSWORD in $EnvFile" -ForegroundColor Yellow
        return
    }

    Wait-SynapseReady

    $check = docker compose exec -T synapse register_new_matrix_user http://localhost:8008 `
        -c /data/homeserver.yaml -a -u $user -p $pass 2>&1
    if ($LASTEXITCODE -eq 0) {
        Write-Host "Registered Matrix user: $user"
    } elseif ($check -match "already") {
        Write-Host "Matrix user $user already exists."
    } else {
        Write-Host $check
    }
}

Ensure-EnvFile
$envVars = Get-DotEnv -Path $EnvFile
Ensure-SynapseConfig -EnvVars $envVars
Stop-LegacyElementContainer
if ($BuildWebApp) {
    Build-ElementWebApp
}

Push-Location $ComposeDir
try {
    docker compose up -d --remove-orphans
    if ($LASTEXITCODE -ne 0) { throw "docker compose up failed" }

    $deadline = (Get-Date).AddMinutes(3)
    do {
        Start-Sleep -Seconds 3
        $health = docker inspect --format "{{.State.Health.Status}}" element-messenger-element-web-1 2>$null
        $running = docker inspect --format "{{.State.Running}}" element-messenger-synapse-1 2>$null
        if ($running -eq "true" -and ($health -eq "healthy" -or $health -eq "")) { break }
    } while ((Get-Date) -lt $deadline)

    Ensure-AdminUser -EnvVars $envVars

    Write-Host ""
    Write-Host "Element Messenger (local Docker)" -ForegroundColor Green
    Write-Host "  Web client:  http://127.0.0.1:8090"
    Write-Host "  Homeserver:  http://127.0.0.1:8008"
    Write-Host "  Sign in with your local Matrix user on server localhost"
    Write-Host ""
    Write-Host "After code changes: cd apps/web; pnpm build; then recreate element-web." -ForegroundColor Cyan
}
finally {
    Pop-Location
}
