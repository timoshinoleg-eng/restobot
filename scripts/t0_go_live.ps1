param(
    [Parameter(Mandatory = $true)]
    [string]$GatewayUrl,

    [Parameter(Mandatory = $true)]
    [string]$TenantId,

    [Parameter(Mandatory = $true)]
    [string]$AdminToken,

    [string]$AdminImage,
    [string]$PublicImage,

    [switch]$SkipDeploy,
    [switch]$SkipPytest,
    [switch]$SkipFrontend,
    [switch]$SkipIngress,
    [switch]$SkipBootstrapCheck,
    [switch]$SkipManualChecks
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$timestamp = Get-Date -Format 'yyyyMMdd-HHmmss'
$logDir = Join-Path $repoRoot 'artifacts\go-live'
New-Item -ItemType Directory -Force -Path $logDir | Out-Null
$logFile = Join-Path $logDir ("t0-go-live-$timestamp.log")

Start-Transcript -Path $logFile -Force | Out-Null

function Step([string]$msg) {
    Write-Host "`n=== $msg ===" -ForegroundColor Cyan
}

function Run([string]$cmd, [string]$cwd = $repoRoot) {
    Write-Host "[$cwd] $cmd" -ForegroundColor DarkGray
    Push-Location $cwd
    try {
        Invoke-Expression $cmd
    }
    finally {
        Pop-Location
    }
}

function Require-Command([string]$name) {
    if (-not (Get-Command $name -ErrorAction SilentlyContinue)) {
        throw "Required command not found: $name"
    }
}

function Pause-Manual([string]$title, [string[]]$checks) {
    if ($SkipManualChecks) {
        Write-Host "SKIP manual step: $title" -ForegroundColor Yellow
        return
    }

    Step $title
    foreach ($check in $checks) {
        Write-Host "[ ] $check"
    }
    $answer = Read-Host "Type 'ok' to continue, anything else to fail"
    if ($answer -ne 'ok') {
        throw "Manual step '$title' was not confirmed"
    }
}

try {
    Step 'Preflight'
    Require-Command git
    Require-Command python

    Run 'git checkout codex/yc-mvp-deploy'
    Run 'git pull --ff-only'
    Run 'git status --short --branch'
    Run 'git rev-parse HEAD'

    if (-not $SkipPytest) {
        Step 'Pytest gates'
        Run 'pytest -q'
        Run 'pytest tests/test_auth.py tests/test_users.py tests/test_admin_routes.py -q'
    }
    else {
        Write-Host 'SKIP pytest gates' -ForegroundColor Yellow
    }

    if (-not $SkipFrontend) {
        Step 'Frontend gates'
        $frontendDir = Join-Path $repoRoot 'frontend\webapp'
        Require-Command npm
        Run 'npm ci' $frontendDir
        Run 'npm run lint' $frontendDir
        Run 'npm run build' $frontendDir
    }
    else {
        Write-Host 'SKIP frontend gates' -ForegroundColor Yellow
    }

    if (-not $SkipDeploy) {
        Step 'Deploy gate'
        if ([string]::IsNullOrWhiteSpace($AdminImage) -or [string]::IsNullOrWhiteSpace($PublicImage)) {
            throw 'Deploy requires -AdminImage and -PublicImage unless -SkipDeploy is set'
        }

        $deployDir = Join-Path $repoRoot 'docker'
        Require-Command bash
        Run "bash ./deploy.sh $AdminImage $PublicImage" $deployDir
    }
    else {
        Write-Host 'SKIP deploy gate' -ForegroundColor Yellow
    }

    if (-not $SkipIngress) {
        Step 'Ingress smoke gate'
        $deployDir = Join-Path $repoRoot 'docker'
        Require-Command bash
        Run "bash ./ingress_smoke.sh $GatewayUrl" $deployDir
    }
    else {
        Write-Host 'SKIP ingress smoke gate' -ForegroundColor Yellow
    }

    if (-not $SkipBootstrapCheck) {
        Pause-Manual 'Bootstrap API disabled check' @(
            'Confirmed ENABLE_BOOTSTRAP_API=false in target runtime env',
            'POST /admin/onboarding returns 403 Bootstrap API is disabled'
        )
    }
    else {
        Write-Host 'SKIP bootstrap disabled check' -ForegroundColor Yellow
    }

    Step 'CLI tenant smoke gate'
    Run "python .\scripts\smoke_cli_tenant.py --gateway-url $GatewayUrl --tenant-id $TenantId --admin-token $AdminToken"

    Pause-Manual 'Admin auth manual gate' @(
        'First login with setup_token completed',
        'Password set and session established',
        'Logout performed and protected route returns 401',
        'Relogin with password succeeds'
    )

    Pause-Manual 'WebApp + YooKassa manual gate' @(
        'Order created via WebApp for pilot tenant',
        'Payment completed in YooKassa test contour',
        'Callback processed and order/payment status updated',
        'Fallback mitigation procedure verified (if callback failed)'
    )

    Pause-Manual 'Bot sanity + backup checkpoint' @(
        'Bot flow sanity checked: start/menu/order/status',
        'Backup checkpoint created per runbook',
        'Go/No-Go checklist signed with artifacts'
    )

    Step 'T-0 completed'
    Write-Host "SUCCESS: all enabled gates passed. Log: $logFile" -ForegroundColor Green
}
catch {
    Write-Error "T-0 FAILED: $($_.Exception.Message)"
    Write-Host "Log: $logFile" -ForegroundColor Yellow
    exit 1
}
finally {
    Stop-Transcript | Out-Null
}
