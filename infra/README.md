# Azure Infrastructure

This folder contains the Bicep template for hosting the Fiskal sandbox on Azure Container Apps.

Current hosted URL: `https://fiskal-app.happycliff-ffe64e1f.swedencentral.azurecontainerapps.io`

## Resources

- Azure Container Registry for the Docker image.
- Log Analytics workspace for container logs.
- Azure Container Apps managed environment.
- Public Azure Container App with `/healthz` liveness and readiness probes.

## Deploy

Run these commands from the project root after installing Azure CLI:

```powershell
az login
az group create --name rg-AgentExperiment --location swedencentral
$secret = [Convert]::ToBase64String([System.Security.Cryptography.RandomNumberGenerator]::GetBytes(32))
$bootstrap = "mcr.microsoft.com/azuredocs/containerapps-helloworld:latest"
az deployment group create --resource-group rg-AgentExperiment --template-file infra/main.bicep --parameters appName=fiskal imageTag=latest containerImage=$bootstrap targetPort=80 healthProbePath=/ flaskSecretKey=$secret
$acr = az deployment group show --resource-group rg-AgentExperiment --name main --query properties.outputs.containerRegistryName.value -o tsv
$acrImage = az deployment group show --resource-group rg-AgentExperiment --name main --query properties.outputs.acrImageName.value -o tsv
az acr build --registry $acr --image fiskal:latest .
az deployment group create --resource-group rg-AgentExperiment --template-file infra/main.bicep --parameters appName=fiskal imageTag=latest containerImage=$acrImage targetPort=8000 healthProbePath=/healthz flaskSecretKey=$secret
```

Or use the helper script:

```powershell
.\infra\deploy.ps1 -ResourceGroup rg-AgentExperiment -Location swedencentral -AppName fiskal -ImageTag latest
```

The deployment outputs the public Container App URL.
