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

Write-Host "Checking Azure CLI account..."
az account show --output none

$existingLocation = az group show --name $ResourceGroup --query location -o tsv 2>$null
if ($LASTEXITCODE -eq 0 -and $existingLocation) {
    $Location = $existingLocation
    Write-Host "Using existing resource group $ResourceGroup in $Location."
} else {
    Write-Host "Creating resource group $ResourceGroup in $Location..."
    az group create --name $ResourceGroup --location $Location --output table
}

$secret = [Convert]::ToBase64String([System.Security.Cryptography.RandomNumberGenerator]::GetBytes(32))
$bootstrapImage = "mcr.microsoft.com/azuredocs/containerapps-helloworld:latest"

Write-Host "Creating Azure resources with a temporary bootstrap image..."
$deployment = az deployment group create `
    --resource-group $ResourceGroup `
    --template-file "infra/main.bicep" `
    --parameters appName=$AppName imageTag=$ImageTag containerImage=$bootstrapImage targetPort=80 healthProbePath=/ flaskSecretKey=$secret `
    --query properties.outputs `
    --output json | ConvertFrom-Json

$registryName = $deployment.containerRegistryName.value
$acrImageName = $deployment.acrImageName.value

Write-Host "Building and pushing the Docker image with Azure Container Registry..."
az acr build `
    --registry $registryName `
    --image "$AppName`:$ImageTag" `
    .

Write-Host "Switching the Container App to the Fiskal image..."
$deployment = az deployment group create `
    --resource-group $ResourceGroup `
    --template-file "infra/main.bicep" `
    --parameters appName=$AppName imageTag=$ImageTag containerImage=$acrImageName targetPort=8000 healthProbePath=/healthz flaskSecretKey=$secret `
    --query properties.outputs `
    --output json | ConvertFrom-Json

$appUrl = $deployment.containerAppUrl.value

Write-Host "Deployment complete."
Write-Host "App URL: $appUrl"
