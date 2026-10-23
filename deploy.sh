#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SERVER="${DEPLOY_SERVER:-root@159.65.155.30}"
REMOTE_DIR="/opt/attendance-service"
QUADLET_FILE="/etc/containers/systemd/attendance.container"

echo "=========================================================="
echo " Starting Attendance Service Deployment to $SERVER"
echo "=========================================================="

echo "==> Step 1: Transferring application files to server..."
ssh "$SERVER" "mkdir -p $REMOTE_DIR/templates"

scp "$SCRIPT_DIR/attendance-service/app.py" "$SERVER:$REMOTE_DIR/app.py"
scp "$SCRIPT_DIR/attendance-service/mobile.py" "$SERVER:$REMOTE_DIR/mobile.py"
scp "$SCRIPT_DIR/attendance-service/Containerfile" "$SERVER:$REMOTE_DIR/Containerfile"
scp "$SCRIPT_DIR/attendance-service/Dockerfile" "$SERVER:$REMOTE_DIR/Dockerfile"
scp "$SCRIPT_DIR/attendance-service/requirements.txt" "$SERVER:$REMOTE_DIR/requirements.txt"
scp -r "$SCRIPT_DIR/attendance-service/templates/"* "$SERVER:$REMOTE_DIR/templates/"

echo "==> Step 2: Ensuring Quadlet configuration mounts mobile.py..."
ssh "$SERVER" "bash -c '
if ! grep -q \"mobile.py\" $QUADLET_FILE; then
    sed -i \"/app.py:ro/a Volume=$REMOTE_DIR/mobile.py:/app/mobile.py:ro\" $QUADLET_FILE
    systemctl daemon-reload
    echo \"Quadlet updated with mobile.py volume mount.\"
else
    echo \"Quadlet volume mount already present.\"
fi
'"

echo "==> Step 3: Rebuilding container image on server..."
ssh "$SERVER" "podman build -t localhost/attendance:latest $REMOTE_DIR"

echo "==> Step 4: Restarting attendance service..."
ssh "$SERVER" "systemctl restart attendance"

echo "==> Step 5: Verifying service health..."
sleep 3
ssh "$SERVER" "systemctl is-active --quiet attendance"
echo "✓ Service is active (running)."

echo "==> Step 6: Checking HTTP health endpoint on server..."
HEALTH_STATUS=$(ssh "$SERVER" "curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1:8090/ || echo '000'")
echo "Local container HTTP response: $HEALTH_STATUS"

if [ "$HEALTH_STATUS" -eq 200 ] || [ "$HEALTH_STATUS" -eq 302 ]; then
    echo "=========================================================="
    echo "✓ DEPLOYMENT SUCCEEDED!"
    echo "  Live URL: https://pm.keenable.io/attendance"
    echo "=========================================================="
else
    echo "=========================================================="
    echo "⚠ Warning: Received unexpected HTTP code ($HEALTH_STATUS)."
    echo "Recent container logs:"
    ssh "$SERVER" "journalctl -u attendance -n 25 --no-pager"
    exit 1
fi
