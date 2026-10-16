#!/usr/bin/env bash
# ==============================================================================
# Retail Inventory API - Post-Deployment Health Check Probe
# Validates that the application is running and responding with HTTP 200
# and status 'healthy'. Used in CI/CD pipelines and deployment scripts.
# ==============================================================================

set -euo pipefail

TARGET_URL="${1:-http://localhost:5000/health}"
MAX_RETRIES="${MAX_RETRIES:-12}"
RETRY_INTERVAL="${RETRY_INTERVAL:-5}"

echo "=========================================================="
echo "Starting health check against: ${TARGET_URL}"
echo "Max Retries: ${MAX_RETRIES} | Interval: ${RETRY_INTERVAL}s"
echo "=========================================================="

ATTEMPT=1
TEMP_FILE="$(mktemp)"
trap 'rm -f "${TEMP_FILE}"' EXIT

while [ "${ATTEMPT}" -le "${MAX_RETRIES}" ]; do
    TIMESTAMP="$(date -u +"%Y-%m-%dT%H:%M:%SZ")"
    echo "[${TIMESTAMP}] Attempt ${ATTEMPT}/${MAX_RETRIES}: Checking ${TARGET_URL}..."

    HTTP_STATUS=$(curl --silent --show-error --max-time 5 \
        --write-out "%{http_code}" \
        --output "${TEMP_FILE}" \
        "${TARGET_URL}" || echo "000")

    if [ "${HTTP_STATUS}" -eq 200 ]; then
        if grep -q '"status":[[:space:]]*"healthy"' "${TEMP_FILE}"; then
            echo "[${TIMESTAMP}] SUCCESS: Application responded with HTTP 200 and healthy status!"
            cat "${TEMP_FILE}"
            echo ""
            exit 0
        else
            echo "[${TIMESTAMP}] WARNING: HTTP 200 received but payload does not indicate healthy:"
            cat "${TEMP_FILE}"
            echo ""
        fi
    else
        echo "[${TIMESTAMP}] PENDING: Received HTTP status ${HTTP_STATUS}. Waiting ${RETRY_INTERVAL}s..."
    fi

    ATTEMPT=$((ATTEMPT + 1))
    sleep "${RETRY_INTERVAL}"
done

echo "=========================================================="
echo "ERROR: Health check failed after ${MAX_RETRIES} attempts."
echo "Application at ${TARGET_URL} did not return healthy status."
echo "=========================================================="
exit 1
