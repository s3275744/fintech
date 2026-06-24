param(
    [string]$ResourceGroup = "rg-AgentExperiment",
    [string]$Location = "swedencentral",
    [string]$AppName = "fiskal",
    [string]$ImageTag = "latest"
)

$ErrorActionPreference = "Stop"

$azureCliPath = "C:\Program Files\Microsoft SDKs\Azure\CLI2\wbin"
if (-not (Get-Command az -ErrorAction SilentlyContinue) -and (Test-Path (Join-Path $azureCliPath "az.cmd"))) {
    $env:Path = "$azureCliPath;$env:Path"
}

az account show --output none
$existingLocation = az group show --name $ResourceGroup --query location -o tsv 2>$null
if ($LASTEXITCODE -eq 0 -and $existingLocation) {
    $Location = $existingLocation
} else {
    az group create --name $ResourceGroup --location $Location --output none
}
$secret = [Convert]::ToBase64String([System.Security.Cryptography.RandomNumberGenerator]::GetBytes(32))
az deployment group what-if `
    --resource-group $ResourceGroup `
    --template-file "infra/main.bicep" `
    --parameters appName=$AppName imageTag=$ImageTag targetPort=8000 healthProbePath=/healthz flaskSecretKey=$secret
