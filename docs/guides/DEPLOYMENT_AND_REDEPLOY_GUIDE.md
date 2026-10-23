# Attendance Service — Development, Deployment & Redeploy Guide

This document details the exact, step-by-step workflow used to develop changes locally, transfer (shift) updated files to the production server, rebuild the container image, restart the service, and verify runtime health.

---

## 1. Environment & Architecture Overview

| Component | Specification |
| :--- | :--- |
| **Server Host** | `159.65.155.30` |
| **SSH User** | `root` |
| **Local Repository Path** | `/home/user/Desktop/Projects/management/attendance/` |
| **Remote Server Path** | `/opt/attendance-service/` |
| **Container Engine** | **Podman** |
| **Container Name** | `attendance` |
| **Container Image** | `localhost/attendance:latest` |
| **Service Manager** | **systemd** unit: `attendance.service` (managed via Podman Quadlet at `/etc/containers/systemd/attendance.container`) |
| **Reverse Proxy** | **Nginx** (routes `https://pm.keenable.io/attendance/` to container port `8000`) |
| **Production Database** | PostgreSQL container `openproject-db` (Database: `attendance`, User: `attendance`) |
| **Git Branch** | `attendance-management` |

---

## 2. Step-by-Step Workflow

### Step 1: Make Code Changes Locally

All application code resides under the `attendance-service/` directory:
* **Backend logic & API**: `attendance-service/app.py`
* **UI Templates**: `attendance-service/templates/` (`me.html`, `team.html`, `base.html`, etc.)

After modifying and testing files locally, commit the changes to Git:
```bash
cd "/home/user/Desktop/Projects/management/attendance"
git add attendance-service/
git commit -m "feat: description of changes"
git push origin attendance-management
```

---

### Step 2: Transfer (Shift) Files to the Server

Files can be transferred from your local machine to the server using **`scp`**.

#### Option A: Transfer Individual Updated Files (Fastest)
```bash
# Shift backend app.py
scp attendance-service/app.py root@159.65.155.30:/opt/attendance-service/app.py

# Shift frontend templates
scp -r attendance-service/templates/ root@159.65.155.30:/opt/attendance-service/
```

#### Option B: Pull Changes Directly on the Server via Git
```bash
ssh root@159.65.155.30 "cd /opt/attendance-service && git pull origin attendance-management"
```

---

### Step 3: Rebuild the Container Image

The attendance application runs inside a Podman container. After transferring new files, rebuild the container image:

```bash
ssh root@159.65.155.30 "podman build -t localhost/attendance:latest /opt/attendance-service"
```

> [!TIP]
> **Build Cache Efficiency**: Podman caches system dependencies and Python packages (`requirements.txt`). Only modified files (such as `app.py` or templates) are copied, allowing the rebuild to finish in **2 to 3 seconds**.

---

### Step 4: Restart the Service

The container is integrated with `systemd` via Podman Quadlet. Restarting the systemd service automatically tears down the previous running container and boots a new container from the newly built image:

```bash
ssh root@159.65.155.30 "systemctl restart attendance"
```

---

### Step 5: Verification & Diagnostics

#### 1. Check Service Status
```bash
ssh root@159.65.155.30 "systemctl status attendance --no-pager"
```
*Expected output*: `Active: active (running)`

#### 2. Monitor Live Application Logs
```bash
ssh root@159.65.155.30 "podman logs -f attendance"
```
*(Press `Ctrl+C` to exit log viewing).*

#### 3. Inspect PostgreSQL Database
If database columns or records were modified:
```bash
# View app_users table
ssh root@159.65.155.30 "podman exec openproject-db psql -U attendance -d attendance -c 'SELECT id, name, email, role_title, current_project_id FROM app_users;'"

# View team assignments table
ssh root@159.65.155.30 "podman exec openproject-db psql -U attendance -d attendance -c 'SELECT member_id, name, project_id, assigned_from, assigned_to FROM team;'"
```

---

## 3. All-in-One One-Liner Command

For day-to-day rapid development, run this single compound command from your local terminal. It shifts `app.py` and templates, rebuilds the container, restarts the service, and verifies the running status:

```bash
scp attendance-service/app.py root@159.65.155.30:/opt/attendance-service/app.py && \
scp -r attendance-service/templates/ root@159.65.155.30:/opt/attendance-service/ && \
ssh root@159.65.155.30 "podman build -t localhost/attendance:latest /opt/attendance-service && systemctl restart attendance && systemctl status attendance --no-pager"
```

---

## 4. Optional Helper Script (`deploy.sh`)

You can create an executable script `deploy.sh` in the root of the repository to automate redeployments:

```bash
#!/usr/bin/env bash
set -e

SERVER="root@159.65.155.30"
REMOTE_DIR="/opt/attendance-service"

echo "==> Transferring files to server..."
scp attendance-service/app.py "$SERVER:$REMOTE_DIR/app.py"
scp -r attendance-service/templates/ "$SERVER:$REMOTE_DIR/"

echo "==> Rebuilding container image..."
ssh "$SERVER" "podman build -t localhost/attendance:latest $REMOTE_DIR"

echo "==> Restarting attendance service..."
ssh "$SERVER" "systemctl restart attendance"

echo "==> Checking service status..."
ssh "$SERVER" "systemctl status attendance --no-pager"

echo "==> Deployment complete!"
```
