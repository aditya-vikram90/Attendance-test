# Local Development Setup Guide: Attendance + Keycloak SSO + Custom Java SPI + PostgreSQL

This document provides step-by-step instructions to spin up the complete **Attendance Management Stack** locally on your development machine using **Docker / Podman Compose**.

---

## 🏗️ Architecture Overview

The local development stack consists of 4 interconnected services:

```
┌────────────────────────────────────────────────────────────────────────┐
│                          LOCAL DEVELOPMENT STACK                        │
│                                                                        │
│   ┌───────────────────┐    OIDC SSO    ┌───────────────────────────┐   │
│   │ Attendance Service│ ──────────────>│   Keycloak SSO Container  │   │
│   │  (Flask / Python) │                │     (Keycloak 26.0)       │   │
│   │ http://localhost: │                │   http://localhost:8080   │   │
│   └─────────┬─────────┘                └─────────────┬─────────────┘   │
│             │                                        │                 │
│             │ Direct SQL                             │ Custom Java SPI │
│             │ Queries                                │ User Auto-Sync  │
│             ▼                                        ▼                 │
│   ┌────────────────────────────────────────────────────────────┐       │
│   │                   PostgreSQL 16 Database                   │       │
│   │                    localhost:5432                          │       │
│   │       (Tables: app_users, attendance, team, project)       │       │
│   └────────────────────────────────────────────────────────────┘       │
└────────────────────────────────────────────────────────────────────────┘
```

1. **PostgreSQL Database (`postgres:16`)**: Central database running on port `5432`.
2. **Keycloak SSO (`keycloak:26.0`)**: SSO server running on port `8080`.
3. **Keycloak Custom Attendance SPI (`keycloak-attendance-spi`)**: Custom Java Maven provider mounted into Keycloak to dynamically populate PostgreSQL `app_users` whenever users sign in or register.
4. **Attendance Service (`attendance-service`)**: Flask Web Application running on port `8000`.

---

## 📋 Prerequisites

Before starting, ensure your local development machine has:
* **Docker** or **Podman** (with `docker-compose` or `podman-compose`)
* **Java 17+** & **Apache Maven** (`mvn`) (for compiling the SPI)
* **Git**

---

## 🚀 Step-by-Step Local Setup

### Step 1: Clone & Navigate to Repositories
Ensure both repositories exist side-by-side in your workspace:

```bash
cd ~/Desktop/Projects/management/

# 1. Attendance Service Repository
git clone https://github.com/Keen-And-Able/UPSC-ORA.git attendance
cd attendance && git checkout attendance-management

# 2. Keycloak Java SPI Repository
cd ~/Desktop/Projects/management/
git clone https://github.com/Keen-And-Able/keycloak-attendance-spi.git
```

---

### Step 2: Build the Custom Java SPI Extension

Compile the custom Java SPI provider that auto-registers Keycloak users into PostgreSQL `app_users`:

```bash
cd ~/Desktop/Projects/management/keycloak-attendance-spi
mvn clean package
```

*Output*: Generates target binary `target/keycloak-attendance-spi-1.0.jar`.

---

### Step 3: Local Orchestration Configuration (`docker-compose.yml`)

Create a `docker-compose.yml` file in `~/Desktop/Projects/management/attendance/docker-compose.yml`:

```yaml
version: '3.8'

services:
  # 1. Central PostgreSQL Database
  postgres:
    image: postgres:16-alpine
    container_name: local_attendance_postgres
    environment:
      POSTGRES_DB: attendance
      POSTGRES_USER: attendance
      POSTGRES_PASSWORD: attendance_secret_pass
    ports:
      - "5432:5432"
    volumes:
      - pgdata:/var/lib/postgresql/data
      - ./init-local-db.sql:/docker-entrypoint-initdb.d/init-local-db.sql

  # 2. Keycloak SSO Container with Custom SPI Provider
  keycloak:
    image: quay.io/keycloak/keycloak:26.0.0
    container_name: local_attendance_keycloak
    command: start-dev --import-realm
    environment:
      KEYCLOAK_ADMIN: admin
      KEYCLOAK_ADMIN_PASSWORD: admin
      KC_DB: postgres
      KC_DB_URL: jdbc:postgresql://postgres:5432/attendance
      KC_DB_USERNAME: attendance
      KC_DB_PASSWORD: attendance_secret_pass
    ports:
      - "8080:8080"
    volumes:
      - ../keycloak-attendance-spi/target/keycloak-attendance-user-storage-1.0.0.jar:/opt/keycloak/providers/keycloak-attendance-user-storage-1.0.0.jar
    depends_on:
      - postgres

  # 3. Attendance Flask Web Service
  attendance:
    build:
      context: ./attendance-service
    container_name: local_attendance_app
    environment:
      DB_TYPE: postgres
      DB_HOST: postgres
      DB_PORT: 5432
      DB_NAME: attendance
      DB_USER: attendance
      DB_PASS: attendance_secret_pass
      SECRET_KEY: local_dev_secret_key_12345
    ports:
      - "8000:8000"
    depends_on:
      - postgres

volumes:
  pgdata:
```

---

### Step 4: Create Local Database Initialization Script (`init-local-db.sql`)

Create `~/Desktop/Projects/management/attendance/init-local-db.sql` to initialize local tables and sample seed data:

```sql
-- PostgreSQL Schema Initialization for Attendance Management

-- 1. App Users Table
CREATE TABLE IF NOT EXISTS app_users (
    id SERIAL PRIMARY KEY,
    keycloak_user_id VARCHAR(100) UNIQUE,
    name VARCHAR(100) NOT NULL,
    first_name VARCHAR(50),
    last_name VARCHAR(50),
    email VARCHAR(120) UNIQUE NOT NULL,
    phone VARCHAR(20),
    role_title VARCHAR(60),
    current_project_id INTEGER,
    current_shift_start VARCHAR(10) DEFAULT '09:30',
    active INTEGER DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 2. Projects Table
CREATE TABLE IF NOT EXISTS project (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    op_project_id VARCHAR(50),
    parent_id INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 3. Team Assignments Table
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
    user_id INTEGER REFERENCES app_users(id),
    shift_start VARCHAR(10),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(project_id, member_id)
);

-- 4. Attendance Records Table
CREATE TABLE IF NOT EXISTS attendance (
    day VARCHAR(10) NOT NULL,
    user_id VARCHAR(100) NOT NULL,
    user_name VARCHAR(100),
    in_time VARCHAR(10),
    out_time VARCHAR(10),
    leave_type VARCHAR(20),
    planned VARCHAR(20),
    remarks TEXT,
    handled_by VARCHAR(100),
    updated_by VARCHAR(100),
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    shift_start VARCHAR(10),
    PRIMARY KEY (day, user_id)
);

-- 5. Seed Initial Projects
INSERT INTO project (id, name) VALUES 
(1, 'Cloud Migration & Infra'),
(2, 'Client Web Portal')
ON CONFLICT (id) DO NOTHING;

-- 6. Seed Sample Local Admin User
INSERT INTO app_users (name, first_name, last_name, email, role_title, current_project_id) VALUES 
('System Admin', 'System', 'Admin', 'admin@keenable.io', 'Admin', 1)
ON CONFLICT (email) DO NOTHING;
```

---

### Step 5: Start the Local Stack

Start all services locally with a single command:

```bash
cd ~/Desktop/Projects/management/attendance
docker-compose up --build -d
```

*(If using Podman)*:
```bash
podman-compose up --build -d
```

---

## 🧪 Testing & Verification

1. **Verify Database**:
   ```bash
   docker exec -it local_attendance_postgres psql -U attendance -d attendance -c "\dt"
   ```

2. **Verify Keycloak SSO**:
   * Open `http://localhost:8080` in your browser.
   * Log in with Username: `admin` / Password: `admin`.
   * Check Provider SPI logs:
     ```bash
     docker logs -f local_attendance_keycloak
     ```

3. **Verify Attendance Web App**:
   * Open `http://localhost:8000` in your browser.
   * Log in with local test credentials or Keycloak.
   * Access `/team` to test team management, bench pool, and engineer assignments locally!

---

## 🔄 Development & Code Iteration Workflow

* **Modifying Attendance Service (Python/Flask)**:
  Mount `./attendance-service` into the container for live reload, or run locally:
  ```bash
  cd attendance-service
  export DB_TYPE=postgres DB_HOST=localhost DB_PORT=5432 DB_NAME=attendance DB_USER=attendance DB_PASS=attendance_secret_pass
  python3 app.py
  ```

* **Modifying Keycloak Java SPI**:
  After making edits in `keycloak-attendance-spi/src/`:
  ```bash
  cd ~/Desktop/Projects/management/keycloak-attendance-spi
  mvn clean package
  docker restart local_attendance_keycloak
  ```
