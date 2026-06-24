targetScope = 'resourceGroup'

@description('Short application name used for Azure resource names.')
@minLength(3)
@maxLength(18)
param appName string = 'fiskal'

@description('Azure region for all resources. Defaults to the resource group location.')
param location string = resourceGroup().location

@description('Container image tag to deploy from the Azure Container Registry.')
param imageTag string = 'latest'

@description('Optional full container image name. Leave empty to use the image built in the Azure Container Registry.')
param containerImage string = ''

@description('External port exposed by the container.')
param targetPort int = 8000

@description('HTTP path used by Container Apps readiness and liveness probes.')
param healthProbePath string = '/healthz'

@description('Minimum number of running container replicas.')
@minValue(0)
@maxValue(10)
param minReplicas int = 0

@description('Maximum number of running container replicas.')
@minValue(1)
@maxValue(10)
param maxReplicas int = 1

@description('CPU cores assigned to each replica.')
@allowed([
  '0.25'
  '0.5'
  '0.75'
  '1.0'
  '1.25'
  '1.5'
  '1.75'
  '2.0'
])
param cpu string = '0.5'

@description('Memory assigned to each replica.')
@allowed([
  '0.5Gi'
  '1.0Gi'
  '1.5Gi'
  '2.0Gi'
  '3.0Gi'
  '4.0Gi'
])
param memory string = '1.0Gi'

@description('Flask session signing key. Pass a generated value at deployment time.')
@secure()
param flaskSecretKey string

var normalizedAppName = toLower(replace(appName, '-', ''))
var uniqueSuffix = uniqueString(resourceGroup().id, appName)
var registryName = '${normalizedAppName}${uniqueSuffix}'
var logAnalyticsName = '${appName}-logs'
var environmentName = '${appName}-env'
var containerAppName = '${appName}-app'
var acrImageName = '${registryName}.azurecr.io/${appName}:${imageTag}'
var activeImageName = empty(containerImage) ? acrImageName : containerImage

resource registry 'Microsoft.ContainerRegistry/registries@2023-11-01-preview' = {
  name: registryName
  location: location
  sku: {
    name: 'Basic'
  }
  properties: {
    adminUserEnabled: true
  }
}

resource logAnalytics 'Microsoft.OperationalInsights/workspaces@2023-09-01' = {
  name: logAnalyticsName
  location: location
  properties: {
    sku: {
      name: 'PerGB2018'
    }
    retentionInDays: 30
  }
}

resource environment 'Microsoft.App/managedEnvironments@2024-03-01' = {
  name: environmentName
  location: location
  properties: {
    appLogsConfiguration: {
      destination: 'log-analytics'
      logAnalyticsConfiguration: {
        customerId: logAnalytics.properties.customerId
        sharedKey: logAnalytics.listKeys().primarySharedKey
      }
    }
  }
}

resource containerApp 'Microsoft.App/containerApps@2024-03-01' = {
  name: containerAppName
  location: location
  properties: {
    managedEnvironmentId: environment.id
    configuration: {
      activeRevisionsMode: 'Single'
      ingress: {
        external: true
        targetPort: targetPort
        transport: 'auto'
        allowInsecure: false
      }
      registries: [
        {
          server: registry.properties.loginServer
          username: registry.name
          passwordSecretRef: 'acr-password'
        }
      ]
      secrets: [
        {
          name: 'acr-password'
          value: registry.listCredentials().passwords[0].value
        }
        {
          name: 'flask-secret-key'
          value: flaskSecretKey
        }
      ]
    }
    template: {
      containers: [
        {
          name: appName
          image: activeImageName
          env: [
            {
              name: 'PORT'
              value: string(targetPort)
            }
            {
              name: 'FLASK_DEBUG'
              value: '0'
            }
            {
              name: 'FLASK_SECRET_KEY'
              secretRef: 'flask-secret-key'
            }
          ]
          probes: [
            {
              type: 'Liveness'
              httpGet: {
                path: healthProbePath
                port: targetPort
              }
              initialDelaySeconds: 20
              periodSeconds: 30
              timeoutSeconds: 5
            }
            {
              type: 'Readiness'
              httpGet: {
                path: healthProbePath
                port: targetPort
              }
              initialDelaySeconds: 5
              periodSeconds: 15
              timeoutSeconds: 5
            }
          ]
          resources: {
            cpu: json(cpu)
            memory: memory
          }
        }
      ]
      scale: {
        minReplicas: minReplicas
        maxReplicas: maxReplicas
      }
    }
  }
}

output containerRegistryName string = registry.name
output containerRegistryLoginServer string = registry.properties.loginServer
output containerAppName string = containerApp.name
output containerAppUrl string = 'https://${containerApp.properties.configuration.ingress.fqdn}'
output acrImageName string = acrImageName
output deployedImageName string = activeImageName
