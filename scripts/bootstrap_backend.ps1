param(
    [string]$StateBackendDir = "infra/state_backend",
    [string]$MainStackDir = "infra/yc",
    [switch]$SkipApply
)

$ErrorActionPreference = "Stop"

function Write-Step {
    param([string]$Message)
    Write-Host "==> $Message"
}

Write-Step "Initialize Terraform in $StateBackendDir"
terraform -chdir=$StateBackendDir init

if (-not $SkipApply) {
    Write-Step "Apply bootstrap stack for remote state"
    terraform -chdir=$StateBackendDir apply -auto-approve
}

Write-Step "Read remote backend outputs"
$bucket = terraform -chdir=$StateBackendDir output -raw tfstate_bucket_name
$accessKey = terraform -chdir=$StateBackendDir output -raw tfstate_access_key
$secretKey = terraform -chdir=$StateBackendDir output -raw tfstate_secret_key

$backendExample = Join-Path $MainStackDir "backend.hcl.example"
$backendFile = Join-Path $MainStackDir "backend.hcl"

Write-Step "Generate $backendFile"
$backendContent = Get-Content $backendExample -Raw
$backendContent = $backendContent -replace "replace-with-tfstate-bucket-name", [Regex]::Escape($bucket).Replace("\\", "\")
Set-Content -Path $backendFile -Value $backendContent -Encoding ascii

$env:ACCESS_KEY = $accessKey
$env:SECRET_KEY = $secretKey

Write-Step "Reinitialize Terraform backend for $MainStackDir"
terraform -chdir=$MainStackDir init -reconfigure -backend-config=backend.hcl

Write-Step "Done"
Write-Host "backend bucket: $bucket"
Write-Host "backend config: $backendFile"
