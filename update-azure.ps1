# Azure Update Script for Web Health Monitor
# Run this script after modifying your code to push updates to Azure.

Write-Host "--- Starting Update Process for Azure ---" -ForegroundColor Cyan

# 1. Login to ACR
Write-Host "Step 1: Logging into Azure Container Registry..."
az acr login --name healthmonitorregistry

# 2. Build the new Docker image
Write-Host "Step 2: Building new Docker image..."
docker build -t healthmonitorregistry.azurecr.io/api:latest .

# 3. Push the image to Azure
Write-Host "Step 3: Pushing image to Azure..."
docker push healthmonitorregistry.azurecr.io/api:latest

# 4. Apply Kubernetes changes (in case manifests changed)
Write-Host "Step 4: Syncing Kubernetes manifests..."
kubectl apply -f ./k8s/deployment.yaml

# 5. Restart the Kubernetes Deployment
Write-Host "Step 5: Restarting Kubernetes pods..."
kubectl rollout restart deployment api-deployment
kubectl rollout restart deployment worker-deployment

Write-Host "Update Complete! Your changes will be live in a minute." -ForegroundColor Green
Write-Host "Check status with: kubectl get pods"
