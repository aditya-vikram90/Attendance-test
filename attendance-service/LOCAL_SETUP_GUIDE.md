# Local Testing Guide: Attendance Service

This guide explains how to run and test the **Attendance Service** locally on your computer before deploying it to the production server.

---

## 🚀 App Status: Currently Running Locally!

The Attendance Service is currently built and running locally on your computer in **Demo / Developer Mode (`DEV_MODE=1`)**.

* **Local Web Address**: **[http://localhost:8090](http://localhost:8090)** (or `http://127.0.0.1:8090`)
* **Mode**: Developer Demo Mode (Bypasses Keycloak SSO & automatically logs you in as `dev@example.com` Administrator).
* **Database**: Local SQLite database stored safely in a local container volume.

---

## 🖥️ How to Test the App in Your Browser

1. Open your web browser and go to: **[http://localhost:8090](http://localhost:8090)**
2. You will land directly on the **Projects** page as an **Administrator**.
3. **What you can try**:
   * **Create a Project**: Click "New project", type a project name, and save.
   * **Add Team Members**: Click on your project -> go to **Team** -> Add engineers with their roles and shift start times (e.g., `09:30`).
   * **Mark Daily Attendance**: Go to **Enter attendance** -> Pick a date -> Mark in/out times or select leave types (Casual Leave, Sick Leave, etc.).
   * **View Trends & History**: Check the **History** and **Trends** tabs to view attendance summaries and graphs.

---

## 🛠️ How to Control the Local Container

If you need to stop, restart, or check the status of your local test app from your terminal:

```bash
# Check if the container is running
podman ps -f name=attendance-demo

# View live container logs
podman logs -f attendance-demo

# Stop the local test container
podman stop attendance-demo

# Start the local test container again
podman start attendance-demo

# Completely remove the test container
podman rm -f attendance-demo
```

---

## 📋 Commands to Run It Again Locally in the Future

If you ever stop or remove the local container and want to run it locally again:

```bash
cd "/home/user/Desktop/Projects/Open Project/attendance/attendance-service"

# Build the container image
podman build -t attendance-local .

# Run the container on port 8090 in DEV_MODE
podman run -d --name attendance-demo \
  -e DEV_MODE=1 \
  -e DB_PATH=/data/attendance.db \
  -p 8090:8000 \
  -v attendance-data:/data \
  attendance-local
```

---

## 🔜 Next Steps: Production Server Deployment

Once you are happy with how the app looks and works locally:

1. We will create the `attendance` database inside the existing PostgreSQL container on `pm.keenable.io`.
2. Configure the Keycloak OIDC client (`attendance`) for Single Sign-On.
3. Deploy the Podman Quadlet service file (`/etc/containers/systemd/attendance.container`).
4. Update Nginx to route `http://pm.keenable.io/attendance/` to port `8090`.
