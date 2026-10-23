# Production-to-Local Complete Replica Setup Guide

This document details the exact architecture, commands, and scripts used to replicate the live production environment (`root@159.65.155.30` / `https://pm.keenable.io/attendance/`) onto a local development machine (`localhost`) with **100% database, user, project, team, role, and Keycloak SSO parity**.

---

## 1. Architecture of the Production & Local Replica Stack

On the production server (`159.65.155.30`), the Attendance and Keycloak identity stack relies on **three containers** and **three interconnected PostgreSQL 17 databases**:

```
┌──────────────────────────────────────────────────────────────────────────────────┐
│                     SHARED NETWORK NAMESPACE (localhost)                         │
│                                                                                  │
│  ┌─────────────────────────┐   OIDC / SSO    ┌────────────────────────────────┐  │
│  │   Attendance Service    │ ──────────────> │     Keycloak 26 Identity       │  │
│  │  http://localhost:8000  │ <────────────── │   http://localhost:8085/auth   │  │
│  │  http://localhost:8090  │   JWT + M2M     │  + Custom User Storage SPI JAR │  │
│  └────────────┬────────────┘                 └───────────────┬────────────────┘  │
│               │                                              │                   │
│               │ SQL (attendance DB)                          │ JDBC (keycloak    │
│               ▼                                              ▼   & users DBs)    │
│  ┌────────────────────────────────────────────────────────────────────────────┐  │
│  │                    openproject-db (PostgreSQL 17)                          │  │
│  │                            localhost:5432                                  │  │
│  │                                                                            │  │
│  │  1. [users DB] (owner: users_admin)                                        │  │
│  │     └── public.app_users (master user credentials + pgcrypto bcrypt)       │  │
│  │            ▲                                                               │  │
│  │            │ postgres_fdw (users_db_server)                                │  │
│  │  2. [attendance DB] (owner: attendance)                                    │  │
│  │     ├── public.app_users (Foreign Table -> users.public.app_users)         │  │
│  │     └── project, team, attendance, access, project_access, watch, meta     │  │
│  │                                                                            │  │
│  │  3. [keycloak DB] (owner: keycloak)                                        │  │
│  │     └── 'keenable' realm, 'attendance' OIDC client, roles, SPI config      │  │
│  └────────────────────────────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────────────────────────────┘
```

### Why All 3 Databases Are Required
1. **`users` Database (`users_admin`)**: Stores the master `public.app_users` table (including `pgcrypto` `crypt()` password hashes). The custom Keycloak SPI (`keycloak-attendance-user-storage-1.0.0.jar`) connects to `jdbc:postgresql://openproject-db:5432/users` to verify user logins.
2. **`attendance` Database (`attendance`)**: Stores all projects (`UPSC`, `BPCL`, `Court`, `Income Tax`, etc.), teams, access roles, and attendance logs. Crucially, `public.app_users` inside `attendance` is a **PostgreSQL Foreign Table (`postgres_fdw`)** pointing directly to `users.public.app_users`.
3. **`keycloak` Database (`keycloak`)**: Stores the `keenable` realm, OIDC client (`attendance`), realm roles (`admin`, `project-manager`, `member`), and federation config.

---

## 2. Step-by-Step Commands Used to Build the Local Replica

### Step 1: Clean Up Old Local Containers, Images, Networks & Volumes
To ensure zero conflicts from previous local setups, clean all existing Docker and Podman resources:

```bash
# Remove all Docker containers, images, volumes, and unused networks
docker rm -f $(docker ps -aq) 2>/dev/null || true
docker rmi -f $(docker images -q) 2>/dev/null || true
docker volume rm -f $(docker volume ls -q) 2>/dev/null || true
docker system prune -af --volumes 2>/dev/null || true

# Remove all Podman containers, images, and volumes
podman rm -f -a 2>/dev/null || true
podman rmi -f -a 2>/dev/null || true
podman volume rm -f -a 2>/dev/null || true
podman system prune -af --volumes 2>/dev/null || true
```

---

### Step 2: Export Production Databases & Custom Keycloak SPI from `159.65.155.30`
Create the local replica directories and pull the read-only PostgreSQL dumps and Keycloak provider `.jar` from the production server:

```bash
cd /home/user/Desktop/Projects/management/attendance
mkdir -p local-replica/dumps local-replica/providers

# 1. Export PostgreSQL cluster roles (openproject, attendance, keycloak, users_admin)
ssh root@159.65.155.30 "podman exec openproject-db pg_dumpall -U openproject --roles-only" \
  > local-replica/dumps/01_roles.sql

# 2. Export 'users' database (master app_users table + pgcrypto)
ssh root@159.65.155.30 "podman exec openproject-db pg_dump -U openproject -d users --clean --if-exists" \
  > local-replica/dumps/02_users.sql

# 3. Export 'attendance' database (projects, teams, attendance, access, and postgres_fdw foreign table)
ssh root@159.65.155.30 "podman exec openproject-db pg_dump -U openproject -d attendance --clean --if-exists" \
  > local-replica/dumps/03_attendance.sql

# 4. Export 'keycloak' database ('keenable' realm, OIDC clients, roles, SPI component config)
ssh root@159.65.155.30 "podman exec openproject-db pg_dump -U openproject -d keycloak --clean --if-exists" \
  > local-replica/dumps/04_keycloak.sql

# 5. Copy the compiled Keycloak Custom User Storage SPI JAR
scp root@159.65.155.30:/opt/keycloak-providers/keycloak-attendance-user-storage-1.0.0.jar \
  local-replica/providers/
```

---

### Step 3: Create the Database Restore & Local OIDC Adaptation Script (`local-replica/init-replica.sh`)
When `openproject-db` initializes for the first time, `/docker-entrypoint-initdb.d/01-init-replica.sh` restores all roles and databases and adds `http://localhost:8000/*` and `http://localhost:8090/*` to the `attendance` OIDC client's allowed redirect URIs in the local `keycloak` database so browser logins stay on `localhost`:

```bash
cat << 'EOF' > /home/user/Desktop/Projects/management/attendance/local-replica/init-replica.sh
#!/bin/bash
set -e

echo "=== [1/6] Restoring PostgreSQL Roles (attendance, keycloak, users_admin, openproject) ==="
grep -v "CREATE ROLE openproject;" /dumps/01_roles.sql | psql -U openproject -d postgres

echo "=== [2/6] Creating Databases (users, attendance, keycloak) ==="
psql -U openproject -d postgres <<-EOSQL
    CREATE DATABASE users OWNER users_admin;
    GRANT ALL PRIVILEGES ON DATABASE users TO users_admin;
    GRANT ALL PRIVILEGES ON DATABASE users TO attendance;
    CREATE DATABASE attendance OWNER attendance;
    GRANT ALL PRIVILEGES ON DATABASE attendance TO attendance;
    CREATE DATABASE keycloak OWNER keycloak;
    GRANT ALL PRIVILEGES ON DATABASE keycloak TO keycloak;
EOSQL

echo "=== [3/6] Restoring 'users' Database ==="
psql -U openproject -d users -f /dumps/02_users.sql

echo "=== [4/6] Restoring 'attendance' Database (including postgres_fdw foreign table app_users) ==="
psql -U openproject -d attendance -f /dumps/03_attendance.sql

echo "=== [5/6] Restoring 'keycloak' Database ==="
psql -U openproject -d keycloak -f /dumps/04_keycloak.sql

echo "=== [6/6] Adding localhost Redirect URIs, Web Origins & Backchannel Logout to local Keycloak 'attendance' Client ==="
psql -U openproject -d keycloak <<-EOSQL
    INSERT INTO public.redirect_uris (client_id, value) VALUES
        ('738018fe-7af3-4267-8175-e6987425688b', 'http://localhost:8000/*'),
        ('738018fe-7af3-4267-8175-e6987425688b', 'http://localhost:8090/*'),
        ('738018fe-7af3-4267-8175-e6987425688b', 'http://127.0.0.1:8000/*'),
        ('738018fe-7af3-4267-8175-e6987425688b', 'http://127.0.0.1:8090/*')
    ON CONFLICT DO NOTHING;

    INSERT INTO public.web_origins (client_id, value) VALUES
        ('738018fe-7af3-4267-8175-e6987425688b', 'http://localhost:8000'),
        ('738018fe-7af3-4267-8175-e6987425688b', 'http://localhost:8090'),
        ('738018fe-7af3-4267-8175-e6987425688b', '+')
    ON CONFLICT DO NOTHING;

    UPDATE public.client
    SET root_url = 'http://localhost:8000',
        base_url = 'http://localhost:8000/'
    WHERE id = '738018fe-7af3-4267-8175-e6987425688b';

    UPDATE public.client_attributes
    SET value = 'http://localhost:8000/auth/backchannel-logout'
    WHERE client_id = '738018fe-7af3-4267-8175-e6987425688b'
      AND name = 'backchannel.logout.url';
EOSQL

echo "=== Local Production Database Replica Initialization Complete! ==="
EOF
chmod +x /home/user/Desktop/Projects/management/attendance/local-replica/init-replica.sh
```

---

### Step 4: Configure `docker-compose.yml` with Shared Network Namespace
In `docker-compose.yml`, `keycloak` and `attendance` share the network namespace of `openproject-db` (`network_mode: "service:openproject-db"`). This guarantees that:
* `openproject-db:5432` resolves identically for Keycloak's `jdbcUrl` (`jdbc:postgresql://openproject-db:5432/users`) and Attendance's `DATABASE_URL`.
* `http://localhost:8085/auth/realms/keenable` resolves identically inside the `attendance` container (for backend OIDC metadata/token/JWKS fetches) and in your host browser (for interactive SSO login redirects).
* `./attendance-service` is live-mounted into `/app` inside the `attendance` container so local code/template changes only require `docker restart attendance`.

---

### Step 5: Build & Start the Local Replica Stack

```bash
cd /home/user/Desktop/Projects/management/attendance
docker compose up -d --build
```

---

## 3. Accessing & Testing the Local Replica

| Service | Local URL | Notes |
| :--- | :--- | :--- |
| **Attendance Portal** | `http://localhost:8000` *(or `http://localhost:8090`)* | Redirects to local Keycloak SSO (`http://localhost:8085/auth`) |
| **Keycloak Admin Console** | `http://localhost:8085/auth/admin` | Admin User: `admin` / Password: `KeycloakAdmin2026!` |
| **PostgreSQL 17 Replica** | `localhost:5432` | Databases: `attendance`, `users`, `keycloak` |

### Useful Commands for Daily Local Development

* **Restart Attendance after editing `app.py` or templates**:
  ```bash
  docker restart attendance
  ```
* **Inspect Attendance logs**:
  ```bash
  docker logs -f attendance
  ```
* **Query the local `attendance` database directly**:
  ```bash
  docker exec -it openproject-db psql -U attendance -d attendance
  ```
* **Re-sync fresh data from the production server at any time**:
  ```bash
  cd /home/user/Desktop/Projects/management/attendance
  docker compose down -v
  # Re-run Step 2 commands to pull latest dumps, then:
  docker compose up -d
  ```
