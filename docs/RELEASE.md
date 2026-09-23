# AEGIS Master Release Procedure

## Deployment Steps
1. Bump version: `python scripts/release_manager.py --bump patch`
2. Test local stack: `docker-compose -f docker-compose.prod.yml up -d`
3. Commit and push tag to trigger GitHub Actions release pipeline.
