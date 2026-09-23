# AEGIS Production Deployment Manual

## Cloud Target: AWS ap-south-1 (Mumbai)

### 1. Pre-requisites
- AWS CLI configured with administrator permissions.
- Terraform >= 1.5.0 installed.
- Docker & Docker Compose.

### 2. Infrastructure Provisioning
```bash
cd infrastructure/terraform
terraform init
terraform plan -out=tfplan
terraform apply tfplan
```

### 3. Container Publishing & Rolling Deployment
```bash
python scripts/release_manager.py --bump patch
git tag v3.2.0
git push origin v3.2.0
```

### 4. Health Verification
```bash
python scripts/health_gate.py --endpoint https://api.aegisalert.org
```
