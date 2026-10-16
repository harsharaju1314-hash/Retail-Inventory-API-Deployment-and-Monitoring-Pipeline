#!/usr/bin/env bash
# ==============================================================================
# Retail Inventory API - EC2 Host Deployment Script
# Automates image building, container lifecycle management, volume configuration,
# and post-deployment validation on the target AWS EC2 instance.
# ==============================================================================

set -euo pipefail

APP_NAME="retail-inventory-api"
CONTAINER_NAME="retail-inventory-api"
IMAGE_TAG="retail-inventory-api:latest"
PORT="5000"

HOST_DATA_DIR="/opt/retail-inventory/data"
HOST_LOG_DIR="/var/log/retail-inventory-api"
CONTAINER_USER_UID=1000
CONTAINER_USER_GID=1000

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

echo "=========================================================="
echo "Starting Deployment for: ${APP_NAME}"
echo "Project Root: ${PROJECT_ROOT}"
echo "Date: $(date -u +"%Y-%m-%dT%H:%M:%SZ")"
echo "=========================================================="

# 1. Verify Docker daemon is running
if ! docker info > /dev/null 2>&1; then
    echo "ERROR: Docker daemon is not running or current user lacks docker group permissions." >&2
    exit 1
fi

# 2. Prepare persistent host directories with correct ownership for container appuser (UID 1000)
echo "[1/5] Ensuring host persistent storage and log directories exist..."
sudo mkdir -p "${HOST_DATA_DIR}" "${HOST_LOG_DIR}"
sudo chown -R "${CONTAINER_USER_UID}:${CONTAINER_USER_GID}" "${HOST_DATA_DIR}" "${HOST_LOG_DIR}"
sudo chmod 755 "${HOST_DATA_DIR}" "${HOST_LOG_DIR}"

# 3. Build Docker container image locally
echo "[2/5] Building Docker image '${IMAGE_TAG}'..."
cd "${PROJECT_ROOT}"
docker build -t "${IMAGE_TAG}" .

# 4. Stop and remove existing container instance if present
echo "[3/5] Managing container lifecycle..."
if docker ps -a --format '{{.Names}}' | grep -Eq "^${CONTAINER_NAME}\$"; then
    echo "Stopping existing container '${CONTAINER_NAME}'..."
    docker stop "${CONTAINER_NAME}" || true
    echo "Removing existing container '${CONTAINER_NAME}'..."
    docker rm "${CONTAINER_NAME}" || true
fi

# 5. Launch updated container
echo "[4/5] Starting new container '${CONTAINER_NAME}'..."
docker run -d \
    --name "${CONTAINER_NAME}" \
    --restart unless-stopped \
    -p "${PORT}:5000" \
    -v "${HOST_DATA_DIR}:/app/data" \
    -v "${HOST_LOG_DIR}:/app/logs" \
    -e DATABASE_PATH="/app/data/inventory.db" \
    -e LOG_FILE_PATH="/app/logs/app.log" \
    -e LOG_LEVEL="INFO" \
    "${IMAGE_TAG}"

# 6. Execute post-deployment health check
echo "[5/5] Executing post-deployment health verification..."
HEALTH_CHECK_SCRIPT="${SCRIPT_DIR}/health_check.sh"
chmod +x "${HEALTH_CHECK_SCRIPT}"

if "${HEALTH_CHECK_SCRIPT}" "http://localhost:${PORT}/health"; then
    echo "=========================================================="
    echo "SUCCESS: Container '${CONTAINER_NAME}' deployed and verified healthy!"
    echo "Cleaning up dangling images..."
    docker image prune -f || true
    echo "=========================================================="
    exit 0
else
    echo "=========================================================="
    echo "ERROR: Health check failed! Showing container logs:"
    docker logs --tail 50 "${CONTAINER_NAME}" || true
    echo "=========================================================="
    exit 1
fi
