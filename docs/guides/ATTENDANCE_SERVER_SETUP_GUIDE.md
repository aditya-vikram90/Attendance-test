# Attendance Service & Keycloak SSO - Complete Server Deployment Guide

This document records the exact step-by-step deployment and configuration completed on the server (`pm.keenable.io` / `159.65.155.30`) for the **Attendance Service**, **Keycloak SSO Container**, **OpenProject**, and **Let's Encrypt HTTPS / SSL Setup**.

---

## 🏗️ System Architecture Overview (HTTPS Enabled)

```
                               ┌──────────────────────────────────────────┐
                               │  PUBLIC INTERNET (https://pm.keenable.io)│
                               └────────────────────┬─────────────────────┘
                                                    │ HTTPS Port 443 (SSL)
                                                    ▼
                               ┌──────────────────────────────────────────┐
                               │           NGINX REVERSE PROXY            │
                               │  (/etc/nginx/sites-available/openproject)│
                               │  SSL Cert: /etc/letsencrypt/live/        │
                               └──────┬─────────────────┬───────────┬─────┘
                                      │                 │           │
                    /                 │     /attendance/│           │ /auth/
                                      ▼                 ▼           ▼
┌────────────────────────────────────────────────────────────────────────────────────────┐
│ PODMAN CONTAINER NETWORK (openproject.network)                                         │
│                                                                                        │
│ ┌────────────────────────┐  ┌────────────────────────┐  ┌────────────────────────────┐ │
│ │ Container: openproject │  │ Container: attendance  │  │ Container: keycloak        │ │
│ │ Image: openproject:17  │  │ Image: attendance:latest│ │ Image: keycloak:latest     │ │
│ │ Port: 127.0.0.1:8080   │  │ Port: 127.0.0.1:8090   │  │ Port: 127.0.0.1:8085       │ │
│ └───────────┬────────────┘  └───────────┬────────────┘  └─────────────┬──────────────┘ │
│             │                           │                             │                │
│             └───────────────────────────┼─────────────────────────────┘                │
│                                         ▼                                              │
│                        ┌─────────────────────────────────┐                             │
│                        │ Container: openproject-db       │                             │
│                        │ Image: postgres:17              │                             │
│                        │ Databases:                      │                             │
│                        │  ├── openproject                │                             │
│                        │  ├── attendance                 │                             │
│                        │  └── keycloak                   │                             │
│                        └─────────────────────────────────┘                             │
└────────────────────────────────────────────────────────────────────────────────────────┘
```

---

## 🔒 Step-by-Step Server & HTTPS Setup Completed

### Step 1: Open-Source SSL Installation (Let's Encrypt & Certbot)
1. **Installed Certbot**:
   ```bash
   apt-get update && apt-get install -y certbot python3-certbot-nginx
   ```
2. **Issued SSL Certificate**:
   ```bash
   certbot --nginx -d pm.keenable.io
   ```
3. **Automatic Renewal**: Certbot created a systemd timer (`certbot.timer`) that runs automatically to renew the SSL certificate before 90 days.

---

### Step 2: Keycloak SSO Container Setup (`keycloak.service`)

1. **Environment File** (`/etc/keycloak/keycloak.env`):
   ```env
   KEYCLOAK_ADMIN=admin
   KEYCLOAK_ADMIN_PASSWORD=<ADMIN_PASSWORD>
   KC_DB=postgres
   KC_DB_URL=jdbc:postgresql://openproject-db:5432/keycloak
   KC_DB_USERNAME=keycloak
   KC_DB_PASSWORD=<KEYCLOAK_DB_PASSWORD>
   KC_HOSTNAME_URL=https://pm.keenable.io/auth/
   KC_HOSTNAME_ADMIN_URL=https://pm.keenable.io/auth/
   KC_HTTP_ENABLED=true
   KC_HTTP_RELATIVE_PATH=/auth
   KC_PROXY_HEADERS=xforwarded
   ```

2. **Systemd Quadlet File** (`/etc/containers/systemd/keycloak.container`):
   ```ini
   [Unit]
   Description=Keycloak Identity Provider
   After=openproject-db.service
   Requires=openproject-db.service

   [Container]
   Image=quay.io/keycloak/keycloak:latest
   ContainerName=keycloak
   Network=openproject.network
   EnvironmentFile=/etc/keycloak/keycloak.env
   PublishPort=127.0.0.1:8085:8080
   Exec=start-dev

   [Service]
   Restart=always
   TimeoutStartSec=600

   [Install]
   WantedBy=multi-user.target default.target
   ```

3. **Keycloak Realm & OIDC Client**:
   * **Realm**: `keenable` (`sslRequired=NONE`)
   * **OIDC Client**: `attendance`
   * **Valid Redirect URIs**:
     * `https://pm.keenable.io/attendance/auth/callback`
     * `https://pm.keenable.io/attendance/`
     * `https://pm.keenable.io/attendance/*`
   * **Web Origins**: `https://pm.keenable.io`
   * **Realm Roles**: `attendance-admin`, `attendance-manager`
   * **Admin User**: `admin@example.com` (assigned `attendance-admin` role)

---

### Step 3: Attendance Application Setup (`attendance.service`)

1. **Source Code Location**: `/opt/attendance-service/`
2. **Built Container Image**:
   ```bash
   podman build -t attendance /opt/attendance-service/
   ```

3. **Environment File** (`/etc/attendance/attendance.env`):
   ```env
   BASE_URL=https://pm.keenable.io/attendance
   SECRET_KEY=<SECRET_KEY>
   DATABASE_URL=postgresql://attendance:<ATTENDANCE_DB_PASSWORD>@openproject-db:5432/attendance

   # Keycloak OIDC Integration (HTTPS)
   OIDC_ISSUER=https://pm.keenable.io/auth/realms/keenable
   OIDC_CLIENT_ID=attendance
   OIDC_CLIENT_SECRET=<KEYCLOAK_CLIENT_SECRET>

   # Internal OpenProject Container Integration
   OP_URL=http://openproject:80

   ADMIN_EMAILS=admin@example.com,oppm@fosteringlinux.com
   SHIFT_START=09:30
   GRACE_MIN=15
   WEEKLY_OFF=Sat,Sun
   ```

4. **Systemd Quadlet File** (`/etc/containers/systemd/attendance.container`):
   ```ini
   [Unit]
   Description=Attendance Service
   After=openproject-db.service keycloak.service
   Requires=openproject-db.service keycloak.service

   [Container]
   Image=localhost/attendance:latest
   ContainerName=attendance
   Network=openproject.network
   EnvironmentFile=/etc/attendance/attendance.env
   PublishPort=127.0.0.1:8090:8000

   [Service]
   Restart=always
   TimeoutStartSec=300

   [Install]
   WantedBy=multi-user.target default.target
   ```

---

### Step 4: OpenProject Configuration (`/etc/openproject/openproject.env`)

```env
OPENPROJECT_HOST__NAME=pm.keenable.io
OPENPROJECT_HTTPS=true
OPENPROJECT_HSTS=true
```

---

## 🛠️ Service Management Commands Quick Reference

### Check Service Status:
```bash
systemctl status openproject
systemctl status attendance
systemctl status keycloak
```

### View Live Logs:
```bash
journalctl -u attendance -f
journalctl -u keycloak -f
```

### Restart Services:
```bash
systemctl restart openproject
systemctl restart attendance
systemctl restart keycloak
systemctl reload nginx
```

---

## 🔗 Endpoints Summary (All HTTPS)

| Service | Access URL | Description |
| :--- | :--- | :--- |
| **OpenProject** | [https://pm.keenable.io/](https://pm.keenable.io/) | Main Project Management application |
| **Attendance App** | [https://pm.keenable.io/attendance/](https://pm.keenable.io/attendance/) | Attendance & Shift tracking application |
| **Keycloak Admin** | [https://pm.keenable.io/auth/admin/](https://pm.keenable.io/auth/admin/) | Keycloak SSO Management Console |
