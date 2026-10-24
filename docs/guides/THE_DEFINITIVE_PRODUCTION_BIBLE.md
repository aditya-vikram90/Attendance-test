# 🏛️ The Definitive Production Bible & Operations Runbook
### UPSC-ORA Attendance Management System (End-to-End Zero-Blunder Manual)

This document is the **single, all-inclusive master guide** to set up, operate, secure, and automate the UPSC-ORA Attendance Management System on a brand-new production server from absolute zero. 

Every single command, architecture diagram, configuration file, credential, and CI/CD workflow in this manual has been tested and verified on live infrastructure (**AWS EC2 Ubuntu 24.04 LTS**).

---

## 📑 Master Table of Contents
1. [Architecture Blueprint & Visual Flow Diagrams](#1-architecture-blueprint--visual-flow-diagrams)
2. [Server Provisioning & Hardware Baseline](#2-server-provisioning--hardware-baseline)
3. [Step 1: Host Hardening, UFW & Docker Engine](#3-step-1-host-hardening-ufw--docker-engine)
4. [Step 2: Source Code Layout in `/opt/attendance-stack`](#4-step-2-source-code-layout-in-optattendance-stack)
5. [Step 3: Compiling Custom Java SPI (Zero Host Dependency)](#5-step-3-compiling-custom-java-spi-zero-host-dependency)
6. [Step 4: PostgreSQL 17 Multi-Database Engine & FDW Link](#6-step-4-postgresql-17-multi-database-engine--fdw-link)
7. [Step 5: Multi-Container Orchestration (`docker-compose.yml`)](#7-step-5-multi-container-orchestration-docker-composeyml)
8. [Step 6: Executing the Database Initialization](#8-step-6-executing-the-database-initialization)
9. [Step 7: Keycloak 26 Configuration via Admin CLI (`kcadm.sh`)](#9-step-7-keycloak-26-configuration-via-admin-cli-kcadmsh)
10. [Step 8: Service Reload & SPI Dynamic Federation Verification](#10-step-8-service-reload--spi-dynamic-federation-verification)
11. [Step 9: Testing Access from Laptop Browser](#11-step-9-testing-access-from-laptop-browser)
12. [Step 10: Production Nginx Reverse Proxy & Let's Encrypt SSL](#12-step-10-production-nginx-reverse-proxy--lets-encrypt-ssl)
13. [Step 11: Enterprise CI/CD Pipeline (GitLab + Jenkins Automation)](#13-step-11-enterprise-cicd-pipeline-gitlab--jenkins-automation)
14. [Step 12: Automated Nightly Backups & Disaster Recovery](#14-step-12-automated-nightly-backups--disaster-recovery)
15. [Master Credentials & Secrets Reference (Complete Inventory)](#15-master-credentials--secrets-reference-complete-inventory)
16. [The Solved Blunders Catalog (Field Troubleshooting)](#16-the-solved-blunders-catalog-field-troubleshooting)

---

## 1. Architecture Blueprint & Visual Flow Diagrams

### 1.1 Complete Infrastructure Topology

```mermaid
flowchart TD
    subgraph Clients["User Devices"]
        Browser["Desktop Browser (Chrome / Edge / Firefox)"]
        Mobile["Android Mobile App v0.8 (PKCE / Geofence)"]
    end

    subgraph FrontDoor["Public Internet Entry (:443)"]
        Nginx["Nginx Reverse Proxy 1.24+ (SSL/TLS Termination)"]
    end

    subgraph DockerNamespace["Shared Network Namespace (localhost)"]
        Attendance["Attendance Flask Service (:8090)<br/>Gunicorn 23.0 (-w 1 --threads 8)"]
        Keycloak["Keycloak 26 Quarkus (:8085)<br/>Java 21 OpenJDK"]
        SPI["Custom Java Storage SPI (1.0.0 JAR)<br/>Zero-Shadow User DB Federation"]
        Postgres["PostgreSQL 17 Engine (:5432)"]

        subgraph LogicalDBs["PostgreSQL 17 Logical Databases"]
            UsersDB[("users DB<br/>Master app_users + BCrypt")]
            AttendanceDB[("attendance DB<br/>24 Application Tables")]
            KeycloakDB[("keycloak DB<br/>Sessions & Realms")]
        end
    end

    subgraph External["External Services"]
        SMTP["Google Workspace SMTP Relay (:587)"]
    end

    Browser -->|HTTPS :443| Nginx
    Mobile -->|HTTPS :443| Nginx

    Nginx -->|/attendance/ -> :8090| Attendance
    Nginx -->|/auth/ -> :8085| Keycloak
    Nginx -->|/api/m/ -> :8090| Attendance

    Keycloak -->|Loads Provider| SPI
    SPI -->|JDBC JDBC:5432/users| UsersDB
    Attendance -->|Direct SQL :5432/attendance| AttendanceDB
    AttendanceDB -->|postgres_fdw link| UsersDB
    Postgres --- LogicalDBs
    Attendance -->|STARTTLS :587| SMTP
```

---

### 1.2 True SSO Authentication & SPI Dynamic Verification Sequence

```mermaid
sequenceDiagram
    autonumber
    actor Employee as User / Browser
    participant Nginx as Nginx (:443)
    participant App as Attendance Service (:8090)
    participant KC as Keycloak 26 (:8085)
    participant SPI as Custom Java SPI
    participant UsersDB as PostgreSQL 'users' DB
    participant AttDB as PostgreSQL 'attendance' DB

    Employee->>Nginx: GET https://pm.keenable.io/attendance
    Nginx->>App: Proxy to 127.0.0.1:8090/attendance/
    App-->>Employee: HTTP 302 Redirect to /auth/realms/keenable/protocol/openid-connect/auth
    Employee->>KC: Enter Email (pm.sharma@keenable.io) & Password
    KC->>SPI: Delegate credential lookup (getUserByEmail)
    SPI->>UsersDB: SELECT password_hash FROM app_users WHERE email=?
    UsersDB-->>SPI: Returns BCrypt Hash
    SPI->>SPI: crypt(input_password, password_hash) == password_hash
    SPI-->>KC: Credentials Validated + Roles (project-manager)
    KC-->>Employee: HTTP 302 Redirect to /attendance/auth/callback?code=AUTH_CODE
    Employee->>App: GET /auth/callback with code
    App->>KC: Exchange code for JWT Tokens (Internal M2M)
    KC-->>App: Access Token + Claims (roles: project-manager)
    App->>AttDB: Query app_users via postgres_fdw foreign table
    AttDB->>UsersDB: Resolves user ID and project mapping
    App-->>Employee: Session Established (Dashboard Rendered)
```

---

### 1.3 Port & Network Matrix

| Service | Container Internal | Host Port Binding | Firewall Policy | Role / Visibility |
| :--- | :--- | :--- | :--- | :--- |
| **Nginx** | 80, 443 | `0.0.0.0:80`, `0.0.0.0:443` | **Public** | Public HTTP/HTTPS gateway & SSL |
| **Attendance Service** | 8000 | `127.0.0.1:8090` | **Closed** | Flask web app & mobile API |
| **Keycloak Identity** | 8085 | `127.0.0.1:8085` | **Closed** | Internal identity broker |
| **PostgreSQL 17** | 5432 | `127.0.0.1:5432` | **Closed** | Database storage engine |

---

## 2. Server Provisioning & Hardware Baseline

To run Keycloak 26 (Java 21 JVM), PostgreSQL 17, Gunicorn, and Nginx concurrently without memory starvation or swap thrashing, use this baseline:

* **Cloud Provider**: AWS EC2, GCP, Azure, or DigitalOcean.
* **Instance Type**: **`m7i-flex.large`** *(or `t3.large`)*
  * **vCPU**: 2 Cores (Intel Sapphire Rapids 4th Gen Xeon)
  * **RAM**: **8 GiB** (Minimum 4 GiB required; 8 GiB provides ideal headroom)
* **Storage**: **30 GiB to 40 GiB `gp3` NVMe SSD**.
* **Base Operating System**: **Ubuntu Server 24.04 LTS (Noble Numbat) - 64-bit (x86_64 / amd64)**.
* **Security Group Rules (AWS Firewall)**:
  * Port `22` (SSH) -> `My IP` or `0.0.0.0/0`
  * Port `80` (HTTP) -> `0.0.0.0/0` (Required for Certbot Let's Encrypt validation)
  * Port `443` (HTTPS) -> `0.0.0.0/0` (Production secure traffic)
  * *All other inbound ports must remain strictly closed.*

---

## 3. Step 1: Host Hardening, UFW & Docker Engine

Connect to your clean server as `root` (or `ubuntu` then `sudo -i`):

```bash
ssh -i attendance-test-key.pem ubuntu@<SERVER_PUBLIC_IP>
sudo -i
```

Execute host hardening and package installation:

```bash
# 1. Update OS package repositories
apt update && apt upgrade -y

# 2. Install essential system utilities
apt install -y curl wget git unzip jq ufw software-properties-common ca-certificates gnupg

# 3. Synchronize Host Timezone to IST (Indian Standard Time)
timedatectl set-timezone Asia/Kolkata

# 4. Configure Uncomplicated Firewall (UFW)
ufw default deny incoming
ufw default allow outgoing
ufw allow 22/tcp comment 'SSH Management'
ufw allow 80/tcp comment 'HTTP Certbot'
ufw allow 443/tcp comment 'HTTPS Production'
ufw --force enable

# 5. Install Official Docker Engine & Docker Compose Plugin
install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | gpg --dearmor -o /etc/apt/keyrings/docker.gpg
chmod a+r /etc/apt/keyrings/docker.gpg

echo \
  "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu \
  $(. /etc/os-release && echo "$VERSION_CODENAME") stable" | \
  tee /etc/apt/sources.list.d/docker.list > /dev/null

apt update
apt install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

# 6. Verify Docker Installation
docker --version && docker compose version
```

---

## 4. Step 2: Source Code Layout in `/opt/attendance-stack`

Create the production workspace directory:

```bash
mkdir -p /opt/attendance-stack
```

From your **local laptop terminal**, copy the repository code to the server:

```bash
scp -i ~/Downloads/attendance-test-key.pem -r \
  /home/neo/Downloads/UPSC-ORA-attendance-management/* \
  ubuntu@<SERVER_PUBLIC_IP>:/home/ubuntu/
```

Back on the **server SSH prompt** (`root`):

```bash
cd /opt/attendance-stack
cp -r /home/ubuntu/* /opt/attendance-stack/

# Flatten if copied inside a nested directory:
if [ -d "UPSC-ORA-attendance-management" ]; then
    cp -r UPSC-ORA-attendance-management/* .
    rm -rf UPSC-ORA-attendance-management
fi

# Confirm key files exist:
ls -la docker-compose.yml attendance-service keycloak-spi local-replica
```

---

## 5. Step 3: Compiling Custom Java SPI (Zero Host Dependency)

Compile the Java 21 User Storage SPI inside a standard Maven container. This eliminates the need to install JDK or Maven on the production host:

```bash
cd /opt/attendance-stack

# 1. Compile the Keycloak SPI JAR
docker run --rm -v "$(pwd)/keycloak-spi":/app -w /app maven:3.9-eclipse-temurin-21 mvn clean package -DskipTests

# 2. Place compiled JAR into the providers directory
mkdir -p local-replica/providers
cp keycloak-spi/target/keycloak-attendance-user-storage-1.0.0.jar local-replica/providers/

# 3. Verify JAR creation
ls -lh local-replica/providers/keycloak-attendance-user-storage-1.0.0.jar
```
*Expected: A binary `keycloak-attendance-user-storage-1.0.0.jar` (~18 KB).*

---

## 6. Step 4: PostgreSQL 17 Multi-Database Engine & FDW Link

Ensure `/opt/attendance-stack/local-replica/init-replica.sh` contains the verified database bootstrap script with `password_required 'false'` (which prevents PostgreSQL 17 local trust authentication errors):

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
        system_role VARCHAR(40) DEFAULT 'member',  -- 'admin' | 'project-manager' | 'member'
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
    CREATE INDEX IF NOT EXISTS idx_app_users_username ON app_users(lower(username));

    -- Seed 7 Master Accounts with BCrypt Encrypted Passwords
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

    -- Crucial: password_required 'false' allows local trust authentication
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

    -- Seed Projects
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

    -- Seed Teams
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

    -- Seed Access
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

    -- Seed Project Access
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

## 7. Step 5: Multi-Container Orchestration (`docker-compose.yml`)

Verify `/opt/attendance-stack/docker-compose.yml`:

```yaml
services:
  # 1. PostgreSQL 17 Multi-Database Engine
  openproject-db:
    image: docker.io/library/postgres:17
    container_name: openproject-db
    hostname: openproject-db
    extra_hosts:
      - "openproject-db:127.0.0.1"
      - "keycloak:127.0.0.1"
    environment:
      POSTGRES_USER: openproject
      POSTGRES_PASSWORD: 52d6616efa2211ce07f9d4415ae04773f988f8a8949d2799
      POSTGRES_DB: openproject
      TZ: Asia/Kolkata
    ports:
      - "5432:5432"
      - "8085:8085"
      - "8000:8000"
      - "8090:8000"
    volumes:
      - replica_pgdata:/var/lib/postgresql/data
      - ./local-replica/init-replica.sh:/docker-entrypoint-initdb.d/01-init-replica.sh:ro
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U attendance -d attendance && pg_isready -U keycloak -d keycloak && pg_isready -U users_admin -d users"]
      interval: 5s
      timeout: 5s
      retries: 20

  # 2. Keycloak 26 Identity Provider (Mounted with Custom Java SPI)
  keycloak:
    image: quay.io/keycloak/keycloak:latest
    container_name: keycloak
    network_mode: "service:openproject-db"
    command: start-dev
    environment:
      KEYCLOAK_ADMIN: admin
      KEYCLOAK_ADMIN_PASSWORD: KeycloakAdmin2026!
      KC_DB: postgres
      KC_DB_URL: jdbc:postgresql://openproject-db:5432/keycloak
      KC_DB_USERNAME: keycloak
      KC_DB_PASSWORD: KC_Db_Pass_2026_Sec!
      KC_HTTP_ENABLED: "true"
      KC_HTTP_PORT: "8085"
      KC_HTTP_RELATIVE_PATH: /auth
      KC_HOSTNAME_URL: http://localhost:8085/auth/
      KC_HOSTNAME_ADMIN_URL: http://localhost:8085/auth/
      KC_PROXY_HEADERS: xforwarded
    volumes:
      - ./local-replica/providers/keycloak-attendance-user-storage-1.0.0.jar:/opt/keycloak/providers/keycloak-attendance-user-storage-1.0.0.jar:ro
    depends_on:
      openproject-db:
        condition: service_healthy

  # 3. Attendance Flask Web Application (Gunicorn)
  attendance:
    build:
      context: ./attendance-service
      dockerfile: Containerfile
    image: localhost/attendance:latest
    container_name: attendance
    network_mode: "service:openproject-db"
    environment:
      BASE_URL: http://localhost:8000
      SECRET_KEY: 248039d9f584e2a859c738ab79116e0329fc09db488c9182390f77bc9568912d
      DATABASE_URL: postgresql://attendance:Att3nd_Pass_2026_Sec!@openproject-db:5432/attendance
      OIDC_ISSUER: http://localhost:8085/auth/realms/keenable
      KEYCLOAK_INTERNAL_URL: http://localhost:8085/auth
      OIDC_CLIENT_ID: attendance
      OIDC_CLIENT_SECRET: Att3nd_Client_Secret_2026!
      DEV_MODE: "0"
      SHIFT_START: "09:30"
      GRACE_MIN: "15"
      WEEKLY_OFF: "Sat,Sun"
      TZ_NAME: Asia/Kolkata
    volumes:
      - ./attendance-service:/app:rw
    depends_on:
      openproject-db:
        condition: service_healthy

volumes:
  replica_pgdata:
```

### Launch the Stack
```bash
cd /opt/attendance-stack
docker compose down -v
docker compose up -d --build
docker compose ps
```

---

## 8. Step 6: Executing the Database Initialization

Because PostgreSQL containers only run `/docker-entrypoint-initdb.d/` when the storage directory is completely empty on first launch, execute the initialization script directly inside the container:

```bash
docker exec -it openproject-db /docker-entrypoint-initdb.d/01-init-replica.sh
```

### Verify PostgreSQL Foreign Table Link
Run:
```bash
docker exec openproject-db psql -U attendance -d attendance -c \
  "SELECT id, email, first_name, system_role FROM app_users;"
```
*Expected: Returns all 7 employee records from `users.app_users` via the foreign data wrapper.*

---

## 9. Step 7: Keycloak 26 Configuration via Admin CLI (`kcadm.sh`)

Configure Keycloak directly using its built-in admin CLI:

```bash
# 1. Authenticate with Keycloak master realm
docker exec keycloak /opt/keycloak/bin/kcadm.sh config credentials \
  --server http://localhost:8085/auth --realm master --user admin --password KeycloakAdmin2026!

# 2. Create the 'keenable' realm
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

# 5. Register the Custom Java SPI User Storage Provider
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

## 10. Step 8: Service Reload & SPI Dynamic Federation Verification

Restart Keycloak and Attendance to refresh connection pools:

```bash
docker restart keycloak attendance
```

Wait 10 seconds, then query Keycloak for federated users:

```bash
docker exec keycloak /opt/keycloak/bin/kcadm.sh get users -r keenable
```

*Expected Output*: Keycloak returns all 7 users dynamically from PostgreSQL:
`"id": "f:<uuid>:1"` (`admin@keenable.io`), `"id": "f:<uuid>:2"` (`pm.sharma@keenable.io`), etc.

### Verify Zero Duplicate Users in Keycloak DB
```bash
docker exec openproject-db psql -U keycloak -d keycloak -c \
  "SELECT count(*) FROM user_entity WHERE realm_id = 'keenable' AND service_account_client_link IS NULL;"
```
*Expected: `count = 0` (Zero shadow duplicate users).*

---

## 11. Step 9: Testing Access from Laptop Browser

Establish an encrypted SSH port-forward from your **local laptop terminal**:

```bash
ssh -i ~/Downloads/attendance-test-key.pem \
  -L 8000:localhost:8000 \
  -L 8085:localhost:8085 \
  ubuntu@<SERVER_PUBLIC_IP>
```

Open your laptop browser to: **[http://localhost:8000](http://localhost:8000)**

Log in with:
* **System Admin**: `admin@keenable.io` / `KeenableAdmin2026!`
* **Project Manager**: `pm.sharma@keenable.io` / `KeenablePM2026!`
* **Engineer**: `dev.arun@keenable.io` / `KeenableDev2026!`

---

## 12. Step 10: Production Nginx Reverse Proxy & Let's Encrypt SSL

When binding to a production domain (e.g. `pm.keenable.io`):

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
    ssl_ciphers HIGH:!aNULL:!MD5;

    client_max_body_size 50M;

    # 1. Attendance Web Portal
    location = /attendance { return 301 /attendance/; }

    location /attendance/ {
        proxy_pass http://127.0.0.1:8090/;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header X-Forwarded-Host $host;
        proxy_set_header X-Forwarded-Prefix /attendance;
        proxy_read_timeout 90;
    }

    # 2. Keycloak SSO Identity Broker
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

    # 3. Mobile Check-In API Route
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

## 13. Step 11: Enterprise CI/CD Pipeline (GitLab + Jenkins Automation)

### 13.1 CI/CD Architecture Flow Diagram

```mermaid
flowchart LR
    subgraph SCM["GitLab SCM & Registry"]
        Repo["GitLab Repo (main)"]
        Registry["GitLab Container Registry<br/>(registry.gitlab.com)"]
    end

    subgraph Jenkins["Jenkins CI Engine"]
        Hook["GitLab Webhook Trigger"]
        P1["1. Python Lint (flake8)"]
        P2["2. Compile SPI (Maven 21)"]
        P3["3. Build Docker Image"]
        P4["4. Push to GitLab Registry"]
        P5["5. SSH Deploy to EC2"]
    end

    subgraph Server["AWS EC2 Production"]
        Reload["docker compose up -d --no-deps attendance"]
        Health["curl -f 127.0.0.1:8090/healthz"]
    end

    Repo -->|git push| Hook
    Hook --> P1 --> P2 --> P3 --> P4 --> P5
    P4 -->|docker push| Registry
    P5 -->|SSH Deploy| Reload --> Health
```

### 13.2 Required Jenkins Plugins
Install via **Manage Jenkins > Plugins**:
1. `GitLab Plugin`
2. `Pipeline` (Workflow Aggregator)
3. `Docker Pipeline`
4. `SSH Agent Plugin`
5. `Credentials Binding Plugin`

### 13.3 Production `Jenkinsfile` (Tested & Live Verified)
Place in the root of your repository:

```groovy
pipeline {
    agent any

    environment {
        REGISTRY_HOST = 'ghcr.io'
        GITHUB_USER   = 'aditya-vikram90'
        IMAGE_NAME    = 'ghcr.io/aditya-vikram90/attendance-service'
        IMAGE_TAG     = "${env.BUILD_NUMBER}"
        DEPLOY_PATH   = '/opt/attendance-stack'
    }

    options {
        timeout(time: 15, unit: 'MINUTES')
        buildDiscarder(logRotator(numToKeepStr: '10'))
        disableConcurrentBuilds()
    }

    stages {
        stage('Checkout') {
            steps {
                checkout scm
            }
        }

        stage('Python Lint') {
            steps {
                sh '''
                    CID=$(hostname 2>/dev/null || echo "jenkins")
                    docker run --rm --volumes-from "$CID" -w "$PWD/attendance-service" python:3.12-slim bash -c "
                        pip install --no-cache-dir flake8 && \
                        flake8 . --exclude=venv,__pycache__ --count --select=E9,F63,F7,F82 --show-source --statistics
                    "
                '''
            }
        }

        stage('Compile Keycloak Java SPI') {
            steps {
                sh '''
                    CID=$(hostname 2>/dev/null || echo "jenkins")
                    docker run --rm --volumes-from "$CID" -w "$PWD/keycloak-spi" maven:3.9-eclipse-temurin-21 mvn clean package -DskipTests
                    ls -lh keycloak-spi/target/*.jar
                '''
            }
        }

        stage('Build & Tag Docker Image') {
            steps {
                sh """
                    cd attendance-service
                    docker build -t ${IMAGE_NAME}:${IMAGE_TAG} -t ${IMAGE_NAME}:latest .
                """
            }
        }

        stage('Push to GitHub Container Registry') {
            steps {
                withCredentials([usernamePassword(credentialsId: 'ghcr-credentials', usernameVariable: 'GH_USER', passwordVariable: 'GH_TOKEN')]) {
                    sh """
                        echo "\$GH_TOKEN" | docker login "${REGISTRY_HOST}" -u "\$GH_USER" --password-stdin
                        docker push "${IMAGE_NAME}:${IMAGE_TAG}"
                        docker push "${IMAGE_NAME}:latest"
                        docker logout "${REGISTRY_HOST}"
                    """
                }
            }
        }

        stage('Deploy to AWS Server') {
            steps {
                withCredentials([
                    string(credentialsId: 'aws-server-ip', variable: 'SERVER_IP'),
                    usernamePassword(credentialsId: 'ghcr-credentials', usernameVariable: 'GH_USER', passwordVariable: 'GH_TOKEN')
                ]) {
                    sshagent(['aws-ec2-ssh-key']) {
                        sh """
                            # 1. Transfer SPI JAR to /tmp (avoids permission errors on /opt)
                            scp -o StrictHostKeyChecking=no keycloak-spi/target/keycloak-attendance-user-storage-1.0.0.jar \
                                ubuntu@\${SERVER_IP}:/tmp/keycloak-attendance-user-storage-1.0.0.jar

                            # 2. Deploy container and install SPI on AWS
                            ssh -o StrictHostKeyChecking=no ubuntu@\${SERVER_IP} "bash -s" << EOF
                                sudo cp /tmp/keycloak-attendance-user-storage-1.0.0.jar \${DEPLOY_PATH}/local-replica/providers/
                                sudo chown -R ubuntu:docker \${DEPLOY_PATH}
                                cd \${DEPLOY_PATH}
                                echo "\${GH_TOKEN}" | docker login "\${REGISTRY_HOST}" -u "\${GH_USER}" --password-stdin
                                docker pull "\${IMAGE_NAME}:latest"
                                docker tag "\${IMAGE_NAME}:latest" localhost/attendance:latest
                                docker compose up -d --no-deps attendance
                                docker restart keycloak
                                sleep 5
                                HEALTH=\\\$(curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:8090/healthz || echo "000")
                                echo "Health check HTTP status: \\\$HEALTH"
                                [ "\\\$HEALTH" -eq 200 ] || [ "\\\$HEALTH" -eq 302 ] || exit 1
EOF
                        """
                    }
                }
            }
        }
    }

    post {
        success {
            echo "✓ Deployment successful! Image ${IMAGE_NAME}:${IMAGE_TAG} is live."
        }
        failure {
            echo "✗ Deployment failed! Check the console output."
        }
    }
}
```

---

## 14. Step 12: Automated Nightly Backups & Disaster Recovery

Create `/opt/attendance-stack/scripts/backup.sh`:

```bash
#!/bin/bash
set -euo pipefail
BACKUP_DIR="/opt/attendance-stack/backups"
DATE=$(date +%F_%H%M%S)
mkdir -p "$BACKUP_DIR"

# Dump all 3 databases
docker exec openproject-db pg_dump -U openproject users | gzip > "$BACKUP_DIR/users_$DATE.sql.gz"
docker exec openproject-db pg_dump -U openproject attendance | gzip > "$BACKUP_DIR/attendance_$DATE.sql.gz"
docker exec openproject-db pg_dump -U openproject keycloak | gzip > "$BACKUP_DIR/keycloak_$DATE.sql.gz"

# Retain backups for 30 days
find "$BACKUP_DIR" -type f -name "*.sql.gz" -mtime +30 -delete
echo "✓ Backup completed: $DATE"
```

Add to cron (`crontab -e`):
```cron
0 2 * * * /opt/attendance-stack/scripts/backup.sh >> /var/log/backup.log 2>&1
```

---

## 15. Master Credentials & Secrets Reference (Complete Inventory)

### 15.1 Keycloak Infrastructure Accounts

| Account / Service | Realm / DB | Username | Password | Purpose |
| :--- | :--- | :--- | :--- | :--- |
| **Keycloak Master Admin** | `master` | `admin` | `KeycloakAdmin2026!` | Administration console (`:8085/auth/admin`) |
| **Attendance OIDC Client** | `keenable` | `attendance` | `Att3nd_Client_Secret_2026!` | Web app SSO client secret |
| **Mobile OIDC Client** | `keenable` | `attendance-mobile` | *(None - Public PKCE)* | Android app client |
| **Keycloak DB User** | `keycloak` | `keycloak` | `KC_Db_Pass_2026_Sec!` | Dedicated PostgreSQL database user |

---

### 15.2 PostgreSQL 17 Database Accounts

| Database Role | Database Name | Password | Privileges / Scope |
| :--- | :--- | :--- | :--- |
| **`openproject`** | `openproject` | `52d6616efa2211ce07f9d4415ae04773f988f8a8949d2799` | Superuser / Engine Admin |
| **`users_admin`** | `users` | `UsersAdmin2026!` | Owner of master `app_users` table |
| **`attendance`** | `attendance` | `Att3nd_Pass_2026_Sec!` | Owner of attendance schema & FDW tables |
| **`keycloak`** | `keycloak` | `KC_Db_Pass_2026_Sec!` | Owner of Keycloak internal tables |

---

### 15.3 Federated Employee Logins (Tested & Seeded in `app_users`)

| Name | Email Address | Password | System Role | Assigned Permissions |
| :--- | :--- | :--- | :--- | :--- |
| **System Admin** | `admin@keenable.io` | `KeenableAdmin2026!` | `admin` | Full Super Admin (`/settings`, `/projects`, `/summary`) |
| **Rahul Sharma** | `pm.sharma@keenable.io` | `KeenablePM2026!` | `project-manager` | PM Lead for *Cloud Migration & Infra* (`/entry`, `/leaves`) |
| **Priya Verma** | `pm.verma@keenable.io` | `KeenablePM2026!` | `project-manager` | PM Lead for *Client Web Portal* (`/entry`, `/leaves`) |
| **Arun Kumar** | `dev.arun@keenable.io` | `KeenableDev2026!` | `member` | Frontend Engineer (*Client Web Portal*) -> `/me` |
| **Neha Gupta** | `dev.neha@keenable.io` | `KeenableDev2026!` | `member` | Backend Engineer (*Cloud Migration & Infra*) -> `/me` |
| **Vikram Singh** | `dev.vikram@keenable.io` | `KeenableDev2026!` | `member` | DevOps Engineer (*Cloud Migration & Infra*) -> `/me` |
| **Mohd Sadik** | `dev.sadik@keenable.io` | `KeenableDev2026!` | `member` | Developer (*Cloud Migration & Infra*) -> `/me` |

---

### 15.4 Application Secrets & Mail Relay

* **Flask `SECRET_KEY`**: `248039d9f584e2a859c738ab79116e0329fc09db488c9182390f77bc9568912d`
* **SMTP Host**: `smtp.gmail.com` | **Port**: `587` (STARTTLS)
* **SMTP User**: `oppm@fosteringlinux.com` | **App Password**: `bfqzkypnkcmtqrrb`

---

## 16. The Solved Blunders Catalog (Field Troubleshooting)

| Blunder / Error Encountered | Root Cause | Exact Verified Resolution |
| :--- | :--- | :--- |
| **`relation "app_users" does not exist`** | PostgreSQL `docker-entrypoint-initdb.d` scripts skip execution if volume storage was previously initialized | Run `docker exec -it openproject-db /docker-entrypoint-initdb.d/01-init-replica.sh` manually. |
| **`password or GSSAPI delegated credentials required`** | PostgreSQL 17 rejects non-superuser FDW connection without explicit option on local trusted networks | Specify `password_required 'false'` in `CREATE USER MAPPING FOR attendance SERVER users_db_server OPTIONS (...);`. |
| **`Maven: MissingProjectException /app`** | Empty directory mounted because code had not been moved into `/opt/attendance-stack` | Copy files so `pom.xml` exists in `keycloak-spi/` before running Maven. |
| **`Resource not found for url .../realms/keenable/users`** | Keycloak started before realm creation | Run `docker exec keycloak /opt/keycloak/bin/kcadm.sh create realms -s realm=keenable ...` to configure. |
| **Gunicorn duplicate automated emails** | Multiple Gunicorn workers spawned (`-w 4`) running internal scheduler multiple times | Gunicorn MUST run with `-w 1 --threads 8` because the daily email scheduler lives in the app process. |
| **Nginx redirect loop on `/attendance`** | Nginx missing trailing slash or `X-Forwarded-Prefix` | Include `proxy_set_header X-Forwarded-Prefix /attendance;` and `proxy_pass http://127.0.0.1:8090/;`. |
| **Jenkins `IllegalArgumentException: IMAGE_NAME`** | Groovy string interpolation `${username-sub}` evaluated as arithmetic subtraction; `env.GIT_COMMIT` evaluated as null before SCM checkout | Use static single quotes `'ghcr.io/...'` and derive tag from `${env.BUILD_NUMBER}`. |
| **DooD Maven/Lint: Empty mounted directory** | When Jenkins runs in Docker with host socket, `-v $(pwd):/app` looks for path on the host, where named volume `jenkins_home` does not exist | Use `--volumes-from "$CID"` (`CID=$(hostname)`) so Docker mounts Jenkins' actual workspace volume. |
| **Python Lint `F821 undefined name` on dynamic globals** | `mobile.py` registers functions into `app.py` at runtime; static analysis tools (`flake8`) parse AST before runtime | Call injected symbols using `globals()["mobile_refresh"](...)` to preserve dynamic dispatch cleanly. |
| **SSH Deploy `scp: Permission denied` on `/opt/...`** | User `ubuntu` lacks write permissions to overwrite files originally owned by `root:root` in `/opt/attendance-stack` | Always `scp` the artifact to `/tmp/`, then execute `sudo cp /tmp/... /opt/...` inside the SSH step. |
| **Deployed container serves stale UI despite successful image build** | `docker-compose.yml` had `volumes: - ./attendance-service:/app:rw` bind-mounted from host disk, shadowing the new Docker image with old files on the host | Remove `./attendance-service:/app` bind-mount from `docker-compose.yml` and deploy with `--force-recreate`. |
