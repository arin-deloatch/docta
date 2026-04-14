# Docker Deployment

This directory contains files for deploying the GraphQL polling daemon in Docker.

## Quick Start

### 1. Prepare configuration

```bash
cd deployment/docker

# Copy and edit environment variables
cp .env.example .env
nano .env  # Add your credentials

# Copy and customize config file
cp ../../deployment/config-templates/graphql_polling.example.yaml config/graphql_polling.yaml
nano config/graphql_polling.yaml  # Customize for your environment
```

### 2. Build and run

```bash
# Build the image
docker-compose build

# Start the service
docker-compose up -d

# View logs
docker-compose logs -f graphql-poller

# Check status
docker-compose ps
```

## Management

### View logs

```bash
# Real-time logs
docker-compose logs -f graphql-poller

# Last 100 lines
docker-compose logs --tail=100 graphql-poller

# Since specific time
docker-compose logs --since 2026-04-09T10:00:00 graphql-poller
```

### Control service

```bash
# Stop service
docker-compose stop

# Restart service
docker-compose restart

# Stop and remove containers
docker-compose down

# Stop and remove containers + volumes (WARNING: deletes state)
docker-compose down -v
```

### Execute commands in container

```bash
# Check daemon status
docker-compose exec graphql-poller doc-diff-tracker daemon-status \
    --config /app/config/graphql_polling.yaml

# Run single poll cycle (for testing)
docker-compose exec graphql-poller doc-diff-tracker daemon-run-once \
    --config /app/config/graphql_polling.yaml \
    --verbose

# Open shell in container
docker-compose exec graphql-poller /bin/bash
```

## Volume Management

Data is persisted in Docker volumes:

- `poller-data`: Downloaded HTML content
- `poller-state`: Polling state and backups
- `poller-output`: Pipeline reports (delta, semantic, QA)
- `poller-tmp`: Temporary workspace (can be cleared)

### Inspect volumes

```bash
# List volumes
docker volume ls | grep poller

# Inspect volume
docker volume inspect deployment_poller-state

# Browse volume contents
docker run --rm -v deployment_poller-state:/data alpine ls -la /data
```

### Backup volumes

```bash
# Backup state volume
docker run --rm \
    -v deployment_poller-state:/data \
    -v $(pwd)/backups:/backup \
    alpine tar czf /backup/poller-state-$(date +%Y%m%d).tar.gz -C /data .

# Backup output volume
docker run --rm \
    -v deployment_poller-output:/data \
    -v $(pwd)/backups:/backup \
    alpine tar czf /backup/poller-output-$(date +%Y%m%d).tar.gz -C /data .
```

### Restore volumes

```bash
# Restore state volume
docker run --rm \
    -v deployment_poller-state:/data \
    -v $(pwd)/backups:/backup \
    alpine sh -c "rm -rf /data/* && tar xzf /backup/poller-state-20260409.tar.gz -C /data"
```

## Troubleshooting

### Container exits immediately

Check logs for errors:
```bash
docker-compose logs graphql-poller
```

Common issues:
- Missing or invalid configuration file
- Missing environment variables
- Invalid GraphQL endpoint or credentials

### Test configuration manually

```bash
# Run single poll cycle with verbose output
docker-compose run --rm graphql-poller \
    doc-diff-tracker daemon-run-once \
    --config /app/config/graphql_polling.yaml \
    --verbose
```

### Permission issues

If you encounter permission issues with volumes:

```bash
# Check ownership
docker-compose exec graphql-poller ls -la /app/data

# Fix ownership (if needed)
docker-compose exec --user root graphql-poller \
    chown -R docpoller:docpoller /app/data /app/config/state /app/output
```

### Network issues

If the container can't reach the GraphQL endpoint:

1. For VPN access, use host network mode:
   ```yaml
   # In docker-compose.yml
   services:
     graphql-poller:
       network_mode: "host"
   ```

2. Or connect to a VPN sidecar container:
   ```yaml
   # In docker-compose.yml
   services:
     graphql-poller:
       depends_on:
         - vpn
       network_mode: "service:vpn"
     
     vpn:
       image: your-vpn-image
       # VPN configuration
   ```

### Memory limits

If hitting memory limits:

```yaml
# In docker-compose.yml
deploy:
  resources:
    limits:
      memory: 4G  # Increase limit
```

## Production Deployment

### OpenShift/Kubernetes

For production Kubernetes deployment, see `../k8s/` directory which contains:
- Deployment manifest
- PersistentVolumeClaim definitions
- ConfigMap and Secret examples
- Service definitions

### Custom CA Certificates

If you need custom CA certificates for SSL:

1. Add volume mount in `docker-compose.yml`:
   ```yaml
   volumes:
     - ./certs/ca-bundle.crt:/app/certs/ca-bundle.crt:ro
   ```

2. Set environment variable:
   ```bash
   # In .env
   GRAPHQL_CERT_PATH=/app/certs/ca-bundle.crt
   ```

## Monitoring

### Health checks

The container includes a health check that runs every 5 minutes:

```bash
# Check health status
docker inspect deployment_graphql-poller | jq '.[0].State.Health'
```

### Resource usage

```bash
# Real-time stats
docker stats deployment_graphql-poller

# Resource usage over time
docker stats --no-stream deployment_graphql-poller
```

## Upgrading

```bash
# Pull latest code
cd /path/to/doc-diff-tracker
git pull

# Rebuild image
cd deployment/docker
docker-compose build

# Restart with new image
docker-compose up -d
```

The state and data volumes persist across upgrades.
