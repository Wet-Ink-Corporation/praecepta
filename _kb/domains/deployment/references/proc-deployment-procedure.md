# Deployment Procedure

> Step-by-step deployment guide

---

## Overview

This document provides deployment procedures for development and production environments.

---

## Local Development

### Prerequisites

- Docker Desktop 4.x+
- Python 3.12+
- uv (package manager)
- Git

### First-Time Setup

```bash
# 1. Clone repository
git clone https://github.com/org/{Project}.git
cd {Project}

# 2. Create environment file
cp .env.example .env
# Edit .env with your API keys (Voyage, Cohere, OpenAI)

# 3. Start infrastructure
docker compose up -d postgres neo4j redis spicedb

# 4. Wait for services to be healthy
docker compose ps  # All should show "healthy"

# 5. Initialize databases
docker compose exec postgres psql -U {Project} -f /docker-entrypoint-initdb.d/init.sql

# 6. Load SpiceDB schema
docker compose exec spicedb zed schema write /schema.zed

# 7. Install Python dependencies
uv sync

# 8. Run migrations (if any)
uv run alembic upgrade head

# 9. Start application
uv run uvicorn {project}.main:app --reload

# 10. Verify
curl http://localhost:8000/health
```

### Full Stack Start

```bash
# Start all services
docker compose up -d

# View logs
docker compose logs -f api

# Stop all services
docker compose down

# Reset (including volumes)
docker compose down -v
```

---

## Production Deployment (Azure)

### Prerequisites

- Azure subscription
- Azure CLI installed and authenticated
- Terraform or Bicep for IaC
- Container registry access

### Infrastructure Provisioning

```bash
# 1. Login to Azure
az login
az account set --subscription <subscription-id>

# 2. Create resource group
az group create \
  --name {Project}-prod \
  --location eastus

# 3. Deploy infrastructure (Bicep)
az deployment group create \
  --resource-group {Project}-prod \
  --template-file infrastructure/main.bicep \
  --parameters environmentName=prod

# 4. Configure Key Vault secrets
az keyvault secret set --vault-name {Project}-kv --name database-url --value "<connection-string>"
az keyvault secret set --vault-name {Project}-kv --name voyage-api-key --value "<api-key>"
# ... additional secrets
```

### Application Deployment

```bash
# 1. Build container image
docker build -t {Project}:$(git rev-parse --short HEAD) .

# 2. Push to Azure Container Registry
az acr login --name {Project}registry
docker tag {Project}:$(git rev-parse --short HEAD) {Project}registry.azurecr.io/{Project}:$(git rev-parse --short HEAD)
docker push {Project}registry.azurecr.io/{Project}:$(git rev-parse --short HEAD)

# 3. Update Container App
az containerapp update \
  --name {app}-api \
  --resource-group {Project}-prod \
  --image {Project}registry.azurecr.io/{Project}:$(git rev-parse --short HEAD)

# 4. Verify deployment
az containerapp logs show \
  --name {app}-api \
  --resource-group {Project}-prod \
  --follow
```

### Database Migrations

```bash
# Run migrations against production database
# (Use bastion/jump host or VPN for secure access)

# Option 1: Container job
az containerapp job create \
  --name migration-job \
  --resource-group {Project}-prod \
  --environment {Project}-env \
  --image {Project}registry.azurecr.io/{Project}:$(git rev-parse --short HEAD) \
  --command "alembic upgrade head" \
  --trigger-type Manual

az containerapp job start --name migration-job --resource-group {Project}-prod

# Option 2: Azure Cloud Shell (with private endpoint access)
alembic upgrade head
```

---

## Rollback Procedure

### Container App Rollback

```bash
# List revisions
az containerapp revision list \
  --name {app}-api \
  --resource-group {Project}-prod \
  --output table

# Activate previous revision
az containerapp revision activate \
  --name {app}-api \
  --resource-group {Project}-prod \
  --revision <previous-revision-name>

# Update traffic split
az containerapp ingress traffic set \
  --name {app}-api \
  --resource-group {Project}-prod \
  --revision-weight <previous-revision>=100
```

### Database Rollback

```bash
# Check current migration
alembic current

# Rollback one step
alembic downgrade -1

# Rollback to specific revision
alembic downgrade <revision-id>
```

---

## Health Verification

### Post-Deployment Checks

```bash
#!/bin/bash
# scripts/verify-deployment.sh

API_URL="${1:-http://localhost:8000}"

echo "Checking health endpoint..."
curl -s "$API_URL/health" | jq .

echo "Checking readiness..."
curl -s "$API_URL/ready" | jq .

echo "Running smoke tests..."
# Basic search
curl -s -X POST "$API_URL/api/v1/search" \
  -H "Content-Type: application/json" \
  -d '{"query": "test query", "top_k": 5}' | jq .

# Block creation
curl -s -X POST "$API_URL/api/v1/blocks" \
  -H "Content-Type: application/json" \
  -d '{"title": "Test Block", "scope_type": "PROJECT", "scope_id": "00000000-0000-0000-0000-000000000001"}' | jq .

echo "Deployment verification complete."
```

### Monitoring Dashboard Checks

After deployment, verify:

1. **API metrics**
   - Request rate returning to normal
   - Error rate < 1%
   - Latency p99 within SLA

2. **Worker metrics**
   - Projection lag < 30s
   - Queue depth normal
   - No dead letters

3. **Database metrics**
   - Connection pool healthy
   - Query latency normal
   - No locks/deadlocks

---

## CI/CD Pipeline

### GitHub Actions Example

```yaml
# .github/workflows/deploy.yml
name: Deploy

on:
  push:
    branches: [main]

jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.12'

      - name: Install dependencies
        run: |
          pip install uv
          uv sync

      - name: Run tests
        run: uv run pytest

      - name: Build container
        run: |
          docker build -t {Project}:${{ github.sha }} .

      - name: Login to ACR
        uses: azure/docker-login@v1
        with:
          login-server: {Project}registry.azurecr.io
          username: ${{ secrets.ACR_USERNAME }}
          password: ${{ secrets.ACR_PASSWORD }}

      - name: Push to ACR
        run: |
          docker tag {Project}:${{ github.sha }} {Project}registry.azurecr.io/{Project}:${{ github.sha }}
          docker push {Project}registry.azurecr.io/{Project}:${{ github.sha }}

  deploy-staging:
    needs: build
    runs-on: ubuntu-latest
    environment: staging
    steps:
      - name: Login to Azure
        uses: azure/login@v1
        with:
          creds: ${{ secrets.AZURE_CREDENTIALS }}

      - name: Deploy to staging
        run: |
          az containerapp update \
            --name {app}-api \
            --resource-group {Project}-staging \
            --image {Project}registry.azurecr.io/{Project}:${{ github.sha }}

      - name: Verify staging
        run: |
          sleep 30
          curl -f https://{Project}-staging.azurecontainerapps.io/health

  deploy-production:
    needs: deploy-staging
    runs-on: ubuntu-latest
    environment: production
    steps:
      - name: Login to Azure
        uses: azure/login@v1
        with:
          creds: ${{ secrets.AZURE_CREDENTIALS }}

      - name: Deploy to production
        run: |
          az containerapp update \
            --name {app}-api \
            --resource-group {Project}-prod \
            --image {Project}registry.azurecr.io/{Project}:${{ github.sha }}

      - name: Verify production
        run: |
          sleep 30
          curl -f https://{Project}.azurecontainerapps.io/health
```

---

## Troubleshooting

### Common Issues

| Issue | Diagnosis | Resolution |
|-------|-----------|------------|
| API not starting | Check logs for import errors | Verify dependencies installed |
| Database connection failed | Check connection string | Verify network access, credentials |
| Projection lagging | Check notification log backlog | Scale worker, check for errors |
| SpiceDB errors | Check schema loaded | Reload schema, verify relationships |
| Embedding API failures | Check API key, rate limits | Verify key valid, add retries |

### Log Access

```bash
# Local
docker compose logs -f api

# Azure Container Apps
az containerapp logs show \
  --name {app}-api \
  --resource-group {Project}-prod \
  --follow

# Query Application Insights
az monitor app-insights query \
  --app {Project}-insights \
  --analytics-query "traces | where timestamp > ago(1h) | order by timestamp desc"
```

---

## See Also

- [Infrastructure](con-infrastructure.md) - Service topology
- [Deployment Configs](ref-deployment-configs.md) - Configuration files
- [Observability](../../observability/references/con-observability.md) - Monitoring setup
