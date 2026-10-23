# 🚀 Complete Production Deployment & Operations Guide
## UPSC-ORA Attendance Management System (End-to-End Master Manual)

This is the **definitive, production-tested manual** to deploy the UPSC-ORA Attendance Management System from absolute zero on a new server in one go. Every command, configuration, secret, and operational step in this guide has been verified on live Ubuntu 24.04 LTS infrastructure.

---

## 📑 Table of Contents
1. [Architecture Overview & Port Matrix](#1-architecture-overview--port-matrix)
2. [Server Provisioning (AWS EC2 / VPS)](#2-server-provisioning-aws-ec2--vps)
3. [Step 1: Host System Hardening & Dependencies](#3-step-1-host-system-hardening--dependencies)
4. [Step 2: Transferring Code to `/opt/attendance-stack`](#4-step-2-transferring-code-to-optattendance-stack)
5. [Step 3: Compile Custom Keycloak Java SPI](#5-step-3-compile-custom-keycloak-java-spi)
6. [Step 4: Prepare the Database Initialization Script](#6-step-4-prepare-the-database-initialization-script)
7. [Step 5: Launch the Docker Container Stack](#7-step-5-launch-the-docker-container-stack)
8. [Step 6: Initialize PostgreSQL Databases & FDW](#8-step-6-initialize-postgresql-databases--fdw)
9. [Step 7: Configure Keycloak via Admin CLI (`kcadm.sh`)](#9-step-7-configure-keycloak-via-admin-cli-kcadmsh)
10. [Step 8: Restart Services & Verify Live SPI Federation](#10-step-8-restart-services--verify-live-spi-federation)
11. [Step 9: Testing Access from Your Browser](#11-step-9-testing-access-from-your-browser)
12. [Step 10: Nginx Front-Door Reverse Proxy & SSL](#12-step-10-nginx-front-door-reverse-proxy--ssl)
13. [Step 11: CI/CD Automation Pipeline (GitHub Actions)](#13-step-11-cicd-automation-pipeline-github-actions)
14. [Step 12: Nightly Backup Automation](#14-step-12-nightly-backup-automation)
15. [Master Credentials Reference](#15-master-credentials-reference)
16. [Troubleshooting & Solved Blunders Catalog](#16-troubleshooting--solved-blunders-catalog)

---

## 1. Architecture Overview & Port Matrix

The production system operates across 3 interconnected containers in a shared network namespace:

```
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                              PRODUCTION SERVER (Host)                                  │
│                                                                                        │
│   ┌──────────────────────────┐     OIDC SSO      ┌──────────────────────────────────┐  │
│   │    Attendance Service    │ ────────────────> │       Keycloak 26 Identity       │  │
│   │    (Flask / Gunicorn)    │                   │          (Quarkus JVM)           │  │
│   │    Port: 8000 / 8090     │ <──────────────── │            Port: 8085            │  │
│   │                          │    JWT / Roles    │  + Attendance Storage SPI (JAR)  │  │
│   └────────────┬─────────────┘                   └────────────────┬─────────────────┘  │
│                │                                                  │                    │
│                │ Direct SQL                                       │ JDBC User Query    │
│                ▼                                                  ▼                    │
│   ┌─────────────────────────────────────────────────────────────────────────────────┐  │
│   │                         openproject-db (PostgreSQL 17)                          │  │
│   │                                   Port: 5432                                    │  │
│   │                                                                                 │  │
│   │   1. [users DB] (Owner: users_admin)                                            │  │
│   │      └── public.app_users (master employee table with BCrypt passwords)        │  │
│   │             ▲                                                                   │  │
│   │             │ postgres_fdw (users_db_server)                                    │  │
│   │   2. [attendance DB] (Owner: attendance)                                        │  │
│   │      ├── public.app_users (Foreign Table link to users.public.app_users)        │  │
│   │      └── project, team, attendance, access, approval, leave_request, etc.       │  │
│   │                                                                                 │  │
│   │   3. [keycloak DB] (Owner: keycloak)                                            │  │
│   │      └── 'keenable' realm, clients, sessions (ZERO shadow duplicate users)      │  │
│   └─────────────────────────────────────────────────────────────────────────────────┘  │
└────────────────────────────────────────────────────────────────────────────────────────┘
```

### Port Matrix

| Service | Container Port | Host Port | Firewall Status | Description |
| :--- | :--- | :--- | :--- | :--- |
| **Nginx** | 80, 443 | `80`, `443` | **Public** | Reverse proxy & Let's Encrypt SSL |
| **Attendance Service** | 8000 | `127.0.0.1:8090` | **Closed** | Flask web application |
| **Keycloak Identity** | 8085 | `127.0.0.1:8085` | **Closed** | Identity Provider |
| **PostgreSQL 17** | 5432 | `127.0.0.1:5432` | **Closed** | Database engine |

---

## 2. Server Provisioning (AWS EC2 / VPS)

* **Instance Type**: `m7i-flex.large` *(or `t3.large`)* – 2 vCPU, 8 GB RAM.
* **Operating System**: **Ubuntu Server 24.04 LTS (amd64)**.
* **Storage**: 30 GiB `gp3` NVMe root volume.
* **Security Group Rules**:
  * `22` (SSH) -> Your IP or Anywhere (`0.0.0.0/0`)
  * `80` (HTTP) -> Anywhere (`0.0.0.0/0`)
  * `443` (HTTPS) -> Anywhere (`0.0.0.0/0`)

---

## 3. Step 1: Host System Hardening & Dependencies

Connect to the server via SSH:
```bash
ssh -i attendance-test-key.pem ubuntu@<SERVER_PUBLIC_IP>
sudo -i
```

Run base system setup:
```bash
# Update packages
apt update && apt upgrade -y

# Install system utilities
apt install -y curl wget git unzip jq ufw software-properties-common ca-certificates gnupg

# Set Timezone to IST
timedatectl set-timezone Asia/Kolkata

# Configure Firewall
ufw default deny incoming
ufw default allow outgoing
ufw allow 22/tcp comment 'SSH'
ufw allow 80/tcp comment 'HTTP'
ufw allow 443/tcp comment 'HTTPS'
ufw --force enable

# Install Docker Engine & Compose
install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | gpg --dearmor -o /etc/apt/keyrings/docker.gpg
chmod a+r /etc/apt/keyrings/docker.gpg

echo \
  "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu \
  $(. /etc/os-release && echo "$VERSION_CODENAME") stable" | \
  tee /etc/apt/sources.list.d/docker.list > /dev/null

apt update
apt install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

# Verify Docker
docker --version && docker compose version
```

---

## 4. Step 2: Transferring Code to `/opt/attendance-stack`

Create the production directory on the server:
```bash
mkdir -p /opt/attendance-stack
```

From your **local computer terminal**, copy the project files to the server:
```bash
scp -i ~/Downloads/attendance-test-key.pem -r \
  /home/neo/Downloads/UPSC-ORA-attendance-management/* \
  ubuntu@<SERVER_PUBLIC_IP>:/home/ubuntu/
```

Back in your **server SSH session** (`sudo -i`):
```bash
cd /opt/attendance-stack
cp -r /home/ubuntu/* /opt/attendance-stack/

# If files landed inside a subfolder, move them to /opt/attendance-stack:
if [ -d "UPSC-ORA-attendance-management" ]; then
    cp -r UPSC-ORA-attendance-management/* .
    rm -rf UPSC-ORA-attendance-management
fi

# Ensure keycloak-spi has the POM file
ls -la keycloak-spi/pom.xml
```

---

## 5. Step 3: Compile Custom Keycloak Java SPI

Compile the Java 21 User Storage SPI using a Maven container (no local Java/Maven required on host):

```bash
cd /opt/attendance-stack

# 1. Compile the Keycloak SPI JAR
docker run --rm -v "$(pwd)/keycloak-spi":/app -w /app maven:3.9-eclipse-temurin-21 mvn clean package -DskipTests

# 2. Place compiled JAR into providers directory
mkdir -p local-replica/providers
cp keycloak-spi/target/keycloak-attendance-user-storage-1.0.0.jar local-replica/providers/

# Verify the JAR
ls -lh local-replica/providers/keycloak-attendance-user-storage-1.0.0.jar
```

---

## 6. Step 4: Prepare the Database Initialization Script

Ensure `/opt/attendance-stack/local-replica/init-replica.sh` has the verified `password_required 'false'` FDW option:

```bash
cat << 'EOF' > /opt/attendance-stack/local-replica/init-replica.sh
#!/bin/bash
set -e

echo "=== [1/5] Creating Database Roles (attendance, keycloak, users_admin) ==="
psql -U openproject -d postgres <<-EOSQL
    DO \$\$
    BEGIN
        IF NOT EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = 'attendance') THEN
            CREATE ROLE attendance WITH LOGIN PASSWORD 'Att3nd_Pass_2026_Sec!';
        END IF;
        IF NOT EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = 'keycloak') THEN
            CREATE ROLE keycloak WITH LOGIN PASSWORD 'KC_Db_Pass_2026_Sec!';
        END IF;
        IF NOT EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = 'users_admin') THEN
            CREATE ROLE users_admin WITH LOGIN PASSWORD 'UsersAdmin2026!';
        END IF;
    END \$\$;
EOSQL

echo "=== [2/5] Creating Databases (users, attendance, keycloak) ==="
psql -U openproject -d postgres <<-EOSQL
    SELECT 'CREATE DATABASE users OWNER users_admin' WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'users')\gexec
    SELECT 'CREATE DATABASE attendance OWNER attendance' WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'attendance')\gexec
    SELECT 'CREATE DATABASE keycloak OWNER keycloak' WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'keycloak')\gexec

    GRANT ALL PRIVILEGES ON DATABASE users TO users_admin;
    GRANT ALL PRIVILEGES ON DATABASE users TO attendance;
    GRANT ALL PRIVILEGES ON DATABASE attendance TO attendance;
    GRANT ALL PRIVILEGES ON DATABASE keycloak TO keycloak;
EOSQL

echo "=== [3/5] Initializing 'users' Database & Master app_users Table ==="
psql -U openproject -d users <<-EOSQL
    CREATE EXTENSION IF NOT EXISTS pgcrypto;

    CREATE TABLE IF NOT EXISTS app_users (
        id SERIAL PRIMARY KEY,
        username VARCHAR(120) UNIQUE NOT NULL,
        email VARCHAR(120) UNIQUE NOT NULL,
        name VARCHAR(100) NOT NULL,
        first_name VARCHAR(100) NOT NULL,
        last_name VARCHAR(100) DEFAULT '',
        phone VARCHAR(20) UNIQUE,
        role_title VARCHAR(60) DEFAULT 'Developer',
        system_role VARCHAR(40) DEFAULT 'member',
        password_hash VARCHAR(255) NOT NULL,
        must_change_password BOOLEAN DEFAULT FALSE,
        totp_enabled BOOLEAN DEFAULT FALSE,
        totp_secret VARCHAR(64) DEFAULT NULL,
        current_project_id INT DEFAULT NULL,
        current_shift_start VARCHAR(10) DEFAULT '09:30',
        active INT DEFAULT 1,
        created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
    );

    CREATE INDEX IF NOT EXISTS idx_app_users_email ON app_users(lower(email));

    INSERT INTO app_users (username, email, name, first_name, last_name, phone, role_title, system_role, password_hash, must_change_password, totp_enabled, active)
    VALUES
    ('admin@keenable.io', 'admin@keenable.io', 'System Admin', 'System', 'Admin', '9999999990', 'Admin', 'admin', crypt('KeenableAdmin2026!', gen_salt('bf', 10)), false, true, 1),
    ('pm.sharma@keenable.io', 'pm.sharma@keenable.io', 'Rahul Sharma', 'Rahul', 'Sharma', '9999999991', 'Project Manager', 'project-manager', crypt('KeenablePM2026!', gen_salt('bf', 10)), false, true, 1),
    ('pm.verma@keenable.io', 'pm.verma@keenable.io', 'Priya Verma', 'Priya', 'Verma', '9999999992', 'Project Manager', 'project-manager', crypt('KeenablePM2026!', gen_salt('bf', 10)), false, true, 1),
    ('dev.arun@keenable.io', 'dev.arun@keenable.io', 'Arun Kumar', 'Arun', 'Kumar', '9999999993', 'Frontend Engineer', 'member', crypt('KeenableDev2026!', gen_salt('bf', 10)), false, true, 1),
    ('dev.neha@keenable.io', 'dev.neha@keenable.io', 'Neha Gupta', 'Neha', 'Gupta', '9999999994', 'Backend Engineer', 'member', crypt('KeenableDev2026!', gen_salt('bf', 10)), false, false, 1),
    ('dev.vikram@keenable.io', 'dev.vikram@keenable.io', 'Vikram Singh', 'Vikram', 'Singh', '9999999995', 'DevOps Engineer', 'member', crypt('KeenableDev2026!', gen_salt('bf', 10)), false, false, 1),
    ('dev.sadik@keenable.io', 'dev.sadik@keenable.io', 'Mohd Sadik', 'Mohd', 'Sadik', '9090909090', 'Developer', 'member', crypt('KeenableDev2026!', gen_salt('bf', 10)), false, false, 1)
    ON CONFLICT (email) DO UPDATE SET
        password_hash = EXCLUDED.password_hash,
        system_role = EXCLUDED.system_role;

    GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO users_admin;
    GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO users_admin;
    GRANT SELECT ON ALL TABLES IN SCHEMA public TO attendance;
EOSQL

echo "=== [4/5] Initializing 'attendance' Database (Foreign Table & Seed Data) ==="
psql -U openproject -d attendance <<-EOSQL
    CREATE EXTENSION IF NOT EXISTS pgcrypto;
    CREATE EXTENSION IF NOT EXISTS postgres_fdw;

    CREATE SERVER IF NOT EXISTS users_db_server
        FOREIGN DATA WRAPPER postgres_fdw
        OPTIONS (host '127.0.0.1', dbname 'users', port '5432');

    DROP USER MAPPING IF EXISTS FOR attendance SERVER users_db_server;
    CREATE USER MAPPING FOR attendance
        SERVER users_db_server
        OPTIONS (user 'users_admin', password 'UsersAdmin2026!', password_required 'false');

    DROP USER MAPPING IF EXISTS FOR openproject SERVER users_db_server;
    CREATE USER MAPPING FOR openproject
        SERVER users_db_server
        OPTIONS (user 'users_admin', password 'UsersAdmin2026!', password_required 'false');

    DROP FOREIGN TABLE IF EXISTS app_users;
    IMPORT FOREIGN SCHEMA public LIMIT TO (app_users) FROM SERVER users_db_server INTO public;

    CREATE TABLE IF NOT EXISTS project (
        id SERIAL PRIMARY KEY,
        name VARCHAR(100) NOT NULL,
        op_project_id VARCHAR(50),
        parent_id INTEGER,
        active INTEGER DEFAULT 1,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );

    INSERT INTO project (id, name) VALUES 
    (1, 'Cloud Migration & Infra'),
    (2, 'Client Web Portal')
    ON CONFLICT (id) DO NOTHING;

    CREATE TABLE IF NOT EXISTS team (
        id SERIAL PRIMARY KEY,
        project_id VARCHAR(50) NOT NULL,
        member_id VARCHAR(100) NOT NULL,
        name VARCHAR(100) NOT NULL,
        role VARCHAR(60),
        phone VARCHAR(20),
        email VARCHAR(120),
        op_user_id VARCHAR(50),
        active INTEGER DEFAULT 1,
        user_id INTEGER,
        shift_start VARCHAR(10),
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        assigned_from TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        assigned_to TIMESTAMP,
        UNIQUE(project_id, member_id)
    );

    INSERT INTO team (project_id, member_id, name, role, email, phone, shift_start, active) VALUES
    ('1', 'm_101', 'Rahul Sharma', 'Project Manager', 'pm.sharma@keenable.io', '9999999991', '09:30', 1),
    ('1', 'm_102', 'Neha Gupta', 'Backend Engineer', 'dev.neha@keenable.io', '9999999994', '09:30', 1),
    ('1', 'm_103', 'Vikram Singh', 'DevOps Engineer', 'dev.vikram@keenable.io', '9999999995', '09:30', 1),
    ('1', 'm_104', 'Mohd Sadik', 'Developer', 'dev.sadik@keenable.io', '9090909090', '09:30', 1),
    ('2', 'm_201', 'Priya Verma', 'Project Manager', 'pm.verma@keenable.io', '9999999992', '09:30', 1),
    ('2', 'm_202', 'Arun Kumar', 'Frontend Engineer', 'dev.arun@keenable.io', '9999999993', '09:30', 1)
    ON CONFLICT (project_id, member_id) DO NOTHING;

    CREATE TABLE IF NOT EXISTS access (
        email TEXT PRIMARY KEY,
        name TEXT,
        role TEXT NOT NULL,
        all_projects INTEGER NOT NULL DEFAULT 0
    );

    INSERT INTO access (email, name, role, all_projects) VALUES
    ('admin@keenable.io', 'System Admin', 'admin', 1),
    ('pm.sharma@keenable.io', 'Rahul Sharma', 'lead', 0),
    ('pm.verma@keenable.io', 'Priya Verma', 'lead', 0)
    ON CONFLICT (email) DO NOTHING;

    CREATE TABLE IF NOT EXISTS project_access (
        project_id TEXT NOT NULL,
        email TEXT NOT NULL,
        kind TEXT NOT NULL,
        PRIMARY KEY(project_id, email, kind)
    );

    INSERT INTO project_access (project_id, email, kind) VALUES
    ('1', 'pm.sharma@keenable.io', 'lead'),
    ('2', 'pm.verma@keenable.io', 'lead')
    ON CONFLICT (project_id, email, kind) DO NOTHING;

    GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO attendance;
    GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO attendance;
EOSQL

echo "=== [5/5] Database Initialization Complete! ==="
EOF

chmod +x /opt/attendance-stack/local-replica/init-replica.sh
```

---

## 7. Step 5: Launch the Docker Container Stack

Verify `docker-compose.yml` mounts the JAR and the initialization script:

```bash
cd /opt/attendance-stack

# Stop any previous containers and launch fresh
docker compose down -v
docker compose up -d --build

# Verify container status
docker compose ps
```

All 3 containers (`openproject-db`, `keycloak`, `attendance`) will be in **Up** status.

---

## 8. Step 6: Initialize PostgreSQL Databases & FDW

Execute the initialization script inside the running PostgreSQL container:

```bash
docker exec -it openproject-db /docker-entrypoint-initdb.d/01-init-replica.sh
```

Verify that the `app_users` foreign table resolves in the `attendance` database:

```bash
docker exec openproject-db psql -U attendance -d attendance -c \
  "SELECT id, email, first_name, system_role FROM app_users;"
```

You will see all 7 users returned successfully.

---

## 9. Step 7: Configure Keycloak via Admin CLI (`kcadm.sh`)

Configure Keycloak directly using its built-in admin CLI:

```bash
# 1. Authenticate kcadm.sh with Keycloak master realm
docker exec keycloak /opt/keycloak/bin/kcadm.sh config credentials \
  --server http://localhost:8085/auth --realm master --user admin --password KeycloakAdmin2026!

# 2. Create 'keenable' realm
docker exec keycloak /opt/keycloak/bin/kcadm.sh create realms \
  -s realm=keenable \
  -s enabled=true \
  -s sslRequired=NONE

# 3. Create required realm roles
docker exec keycloak /opt/keycloak/bin/kcadm.sh create roles -r keenable -s name=admin
docker exec keycloak /opt/keycloak/bin/kcadm.sh create roles -r keenable -s name=project-manager
docker exec keycloak /opt/keycloak/bin/kcadm.sh create roles -r keenable -s name=member

# 4. Create 'attendance' OIDC confidential client
docker exec keycloak /opt/keycloak/bin/kcadm.sh create clients -r keenable \
  -s clientId=attendance \
  -s enabled=true \
  -s publicClient=false \
  -s secret=Att3nd_Client_Secret_2026! \
  -s standardFlowEnabled=true \
  -s directAccessGrantsEnabled=true \
  -s 'redirectUris=["http://localhost:8000/*","http://localhost:8090/*","http://127.0.0.1:8000/*","http://127.0.0.1:8090/*","https://pm.keenable.io/attendance/*"]' \
  -s 'webOrigins=["*"]'

# 5. Register Custom Java SPI User Storage Provider
docker exec keycloak /opt/keycloak/bin/kcadm.sh create components -r keenable \
  -s name=attendance-postgres-storage \
  -s providerId=attendance-user-storage \
  -s providerType=org.keycloak.storage.UserStorageProvider \
  -s 'config.jdbcUrl=["jdbc:postgresql://openproject-db:5432/users"]' \
  -s 'config.dbUser=["users_admin"]' \
  -s 'config.dbPassword=["UsersAdmin2026!"]' \
  -s 'config.priority=["0"]'
```

---

## 10. Step 8: Restart Services & Verify Live SPI Federation

Restart Keycloak and Attendance so they reload connections:

```bash
docker restart keycloak attendance
```

Wait 10 seconds, then query Keycloak:

```bash
docker exec keycloak /opt/keycloak/bin/kcadm.sh get users -r keenable
```

Keycloak will return all 7 users dynamically with IDs matching `f:<uuid>:<id>`.

---

## 11. Step 9: Testing Access from Your Browser

### Via Secure SSH Tunnel (Recommended for Initial Testing)
On your **local computer terminal**, run:

```bash
ssh -i ~/Downloads/attendance-test-key.pem \
  -L 8000:localhost:8000 \
  -L 8085:localhost:8085 \
  ubuntu@<SERVER_PUBLIC_IP>
```

Open your browser to: **[http://localhost:8000](http://localhost:8000)**

Log in with:
* **System Admin**: `admin@keenable.io` / `KeenableAdmin2026!`
* **Project Manager**: `pm.sharma@keenable.io` / `KeenablePM2026!`
* **Engineer**: `dev.arun@keenable.io` / `KeenableDev2026!`

---

## 12. Step 10: Nginx Front-Door Reverse Proxy & SSL

When mapping to a production domain (e.g. `pm.keenable.io`):

```bash
apt install -y nginx certbot python3-certbot-nginx

# Obtain SSL Certificate
certbot certonly --nginx -d pm.keenable.io --non-interactive --agree-tos -m admin@keenable.io
```

Configure `/etc/nginx/sites-available/pm.keenable.io`:

```nginx
server {
    listen 80;
    server_name pm.keenable.io;
    return 301 https://$host$request_uri;
}

server {
    listen 443 ssl http2;
    server_name pm.keenable.io;

    ssl_certificate /etc/letsencrypt/live/pm.keenable.io/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/pm.keenable.io/privkey.pem;
    ssl_protocols TLSv1.2 TLSv1.3;

    client_max_body_size 50M;

    # Attendance Portal
    location = /attendance { return 301 /attendance/; }

    location /attendance/ {
        proxy_pass http://127.0.0.1:8090/;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header X-Forwarded-Prefix /attendance;
    }

    # Keycloak SSO
    location /auth/ {
        proxy_pass http://127.0.0.1:8085/auth/;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_buffer_size 128k;
        proxy_buffers 4 256k;
        proxy_busy_buffers_size 256k;
    }

    # Mobile API
    location /api/m/ {
        proxy_pass http://127.0.0.1:8090/api/m/;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

Enable site:
```bash
ln -sf /etc/nginx/sites-available/pm.keenable.io /etc/nginx/sites-enabled/
nginx -t && systemctl reload nginx
```

---

## 13. Step 11: CI/CD Automation Pipeline (GitHub Actions)

Create `.github/workflows/deploy.yml` in your GitHub repository:

```yaml
name: Deploy Attendance Production

on:
  push:
    branches: [main]

jobs:
  build-and-deploy:
    runs-on: ubuntu-latest
    steps:
      - name: Checkout Code
        uses: actions/checkout@v4

      - name: Compile Keycloak SPI
        run: |
          cd keycloak-spi
          mvn clean package -DskipTests

      - name: Deploy to Server via SSH
        uses: appleboy/ssh-action@v1.0.3
        with:
          host: ${{ secrets.SERVER_HOST }}
          username: ${{ secrets.SERVER_USER }}
          key: ${{ secrets.SERVER_SSH_KEY }}
          script: |
            cd /opt/attendance-stack
            git pull origin main
            docker compose build attendance
            docker restart attendance
            sleep 5
            curl -f http://127.0.0.1:8090/healthz || exit 1
```

---

## 14. Step 12: Nightly Backup Automation

Create `/opt/attendance-stack/scripts/backup.sh`:

```bash
#!/bin/bash
set -euo pipefail
BACKUP_DIR="/opt/attendance-stack/backups"
DATE=$(date +%F_%H%M%S)
mkdir -p "$BACKUP_DIR"

docker exec openproject-db pg_dump -U openproject users | gzip > "$BACKUP_DIR/users_$DATE.sql.gz"
docker exec openproject-db pg_dump -U openproject attendance | gzip > "$BACKUP_DIR/attendance_$DATE.sql.gz"
docker exec openproject-db pg_dump -U openproject keycloak | gzip > "$BACKUP_DIR/keycloak_$DATE.sql.gz"

find "$BACKUP_DIR" -type f -name "*.sql.gz" -mtime +30 -delete
echo "✓ Backup completed: $DATE"
```

Add to cron (`crontab -e`):
```cron
0 2 * * * /opt/attendance-stack/scripts/backup.sh >> /var/log/backup.log 2>&1
```

---

## 15. Master Credentials Reference

*See dedicated document: [PRODUCTION_CREDENTIALS_REFERENCE.md](file:///home/neo/Downloads/UPSC-ORA-attendance-management/docs/guides/PRODUCTION_CREDENTIALS_REFERENCE.md)*

### Quick Reference:
* **Keycloak Admin**: User: `admin` | Password: `KeycloakAdmin2026!`
* **OIDC Client Secret**: `Att3nd_Client_Secret_2026!`
* **PostgreSQL Superuser**: User: `openproject` | Password: `52d6616efa2211ce07f9d4415ae04773f988f8a8949d2799`
* **PostgreSQL `users_admin`**: User: `users_admin` | Password: `UsersAdmin2026!`
* **PostgreSQL `attendance`**: User: `attendance` | Password: `Att3nd_Pass_2026_Sec!`
* **PostgreSQL `keycloak`**: User: `keycloak` | Password: `KC_Db_Pass_2026_Sec!`

---

## 16. Troubleshooting & Solved Blunders Catalog

| Issue Encountered | Root Cause | Permanent Resolution |
| :--- | :--- | :--- |
| **`relation "app_users" does not exist`** | PostgreSQL `docker-entrypoint-initdb.d` skips execution if volume data already exists | Run `docker exec -it openproject-db /docker-entrypoint-initdb.d/01-init-replica.sh` manually |
| **`password or GSSAPI delegated credentials required`** | PostgreSQL 17 rejects non-superuser FDW connection without explicit option on local trusted networks | Add `password_required 'false'` to the user mapping in `init-replica.sh` |
| **`Resource not found for url .../realms/keenable/users`** | Keycloak started before realm creation | Create realm with `kcadm.sh create realms -s realm=keenable ...` |
| **`Maven: MissingProjectException /app`** | Mounted directory was empty because code was not in `/opt/attendance-stack` | Copy repository files so `pom.xml` exists in `keycloak-spi/` |
| **Gunicorn sends duplicate emails** | More than 1 Gunicorn worker ran in container | Always run `-w 1 --threads 8` because schedulers live in the app process |
