# Centralized User Management & Keycloak Integration Specification

**Document Version**: 4.0 (Comprehensive Specification)  
**Location**: `/home/user/Desktop/Projects/management/attendance/docs/ARCHITECTURE_AND_DESIGN_SPEC.md`  
**Status**: Approved Architecture & Technical Design Specification  
**Target Scope**: Central Identity Database (`users` DB on `openproject-db`), Complete Pre-Execution System Backup, Keycloak SPI Custom Attributes & Dynamic Role Federation, and Attendance Portal Integration.

---

## 1. Executive Overview & Architectural Principles

This document provides the complete, end-to-end technical specification for unifying user identity, authentication, and authorization across **Keycloak** and the **Attendance System**, with future-proof design for **OpenProject Community Edition**.

### Core Architecture Principles:
1. **Single Source of Truth**:
   * The central database is PostgreSQL database **`users`** on container `openproject-db:5432`.
   * Master user table: `app_users`.
   * Every employee account is stored exactly once in `app_users`.
2. **Separation of Concerns**:
   * **Keycloak**: Handles identity authentication (SSO), profile attributes (`phone`, `role_title`), and native authorization via **Realm Role Mappings** (`admin`, `project-manager`, `member`).
   * **Attendance Portal**: Handles attendance logging, shifts, leave applications, and project team assignments (`project_access` and `team`).
3. **Clean Keycloak Setup**:
   * **Details Tab**: Username, Email, First Name, Last Name.
   * **Attributes Tab**: `phone` (Mobile), `role_title` (Job Designation).
   * **Role Mappings Tab**: Realm Roles (`admin`, `project-manager`, `member`).
   * **No polluting attributes**: Transient application states like `current_project_id` and redundant text strings like `system_role` are excluded from Keycloak attributes.
4. **Single-Action Management ("Smart Role")**:
   * When an Admin or PM creates/updates a user in Attendance, the system writes to `users.app_users`, grants the appropriate Keycloak realm role, and links project permissions in a single click.

---

## 2. Step-by-Step Task & Phase Breakdown

The project implementation is divided into **6 Granular Tasks**. Execution is strictly **one task at a time** with verification and testing after each task:

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                       TASK IMPLEMENTATION SEQUENCE                          │
├─────────────────────────────────────────────────────────────────────────────┤
│ Task 1: Complete System Backup (Pre-Execution Safety)                       │
│ └── Backup all PostgreSQL DBs, Keycloak SPI jars, config, & Git snapshot   │
│                                                                             │
│ Task 2: Create Central Identity Database (`users`) & Table (`app_users`)    │
│ └── Create database `users`, table `app_users`, migrate identity & triggers │
│                                                                             │
│ Task 3: Keycloak Realm Roles & Default Role Configuration                   │
│ └── Configure realm roles `admin`, `project-manager`, `member` in Keycloak  │
│                                                                             │
│ Task 4: Keycloak User Storage SPI Update & Deployment                       │
│ └── Update Java SPI adapter to point to `users` DB & map attributes/roles   │
│                                                                             │
│ Task 5: Attendance Application Connection & "Smart Role" Flow Update        │
│ └── Update `DATABASE_URL` in `app.py` & single-click PM/Engineer creation    │
│                                                                             │
│ Task 6: Final End-to-End System Verification & Rollback Test               │
│ └── Validate Keycloak UI creation, Attendance team form, & cascading delete │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 3. Comprehensive Technical Specifications by Task

### Task 1: Complete System Backup (Pre-Execution Safety)
* **Goal**: Guarantee 100% data safety and instant rollback capability before executing any code or schema changes.
* **Commands & Script**:
  ```bash
  # 1. Create backups directory
  mkdir -p /var/backups

  # 2. Dump all PostgreSQL databases
  podman exec openproject-db pg_dump -U attendance attendance > /var/backups/attendance_pre_migration_$(date +%Y%m%d_%H%M%S).sql
  podman exec openproject-db pg_dump -U keycloak keycloak > /var/backups/keycloak_pre_migration_$(date +%Y%m%d_%H%M%S).sql

  # 3. Backup Keycloak provider jars and environment configuration
  cp -r /opt/keycloak-providers /opt/keycloak-providers.bak_$(date +%Y%m%d_%H%M%S)
  cp /etc/keycloak/keycloak.env /etc/keycloak/keycloak.env.bak_$(date +%Y%m%d_%H%M%S)

  # 4. Create Git snapshot tag
  git commit -am "Pre-central-user-migration snapshot"
  git tag pre-central-user-migration
  ```
* **Verification Check**: Verify non-zero byte size for all `.sql` files and presence of git tag `pre-central-user-migration`.

---

### Task 2: Create Central Identity Database (`users`) & Master Table (`app_users`)
* **Goal**: Establish the central database `users` on container `openproject-db:5432`.
* **SQL Schema Script**:
  ```sql
  -- Create central database
  CREATE DATABASE users;

  \c users;

  -- Create master user directory table
  CREATE TABLE IF NOT EXISTS app_users (
      id SERIAL PRIMARY KEY,
      keycloak_user_id VARCHAR(100) UNIQUE,
      username VARCHAR(120) UNIQUE NOT NULL,       -- Email / Username
      email VARCHAR(120) UNIQUE NOT NULL,          -- Primary Email Address
      name VARCHAR(100) NOT NULL,                  -- Full Name (First + Last)
      first_name VARCHAR(50),                      -- Given Name
      last_name VARCHAR(50),                       -- Family Name / Surname
      phone VARCHAR(20),                           -- Contact Phone Number
      role_title VARCHAR(60),                      -- Job Designation (e.g. Senior DevOps, QA)
      system_role VARCHAR(30) DEFAULT 'member',    -- Mapped directly to Keycloak Realm Role
      password_hash VARCHAR(255),
      must_change_password BOOLEAN DEFAULT TRUE,
      totp_enabled BOOLEAN DEFAULT FALSE,
      active INTEGER DEFAULT 1,                     -- Status: 1 = Active, 0 = Inactive
      created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
      updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
  );

  -- Migrate existing user identity data from database 'attendance'
  INSERT INTO app_users (id, keycloak_user_id, username, email, name, first_name, last_name, phone, role_title, system_role, password_hash, must_change_password, totp_enabled, active, created_at, updated_at)
  SELECT id, keycloak_user_id, username, email, name, first_name, last_name, phone, role_title, COALESCE(system_role, 'member'), password_hash, must_change_password, totp_enabled, active, created_at, updated_at
  FROM dblink('dbname=attendance user=attendance', 'SELECT id, keycloak_user_id, username, email, name, first_name, last_name, phone, role_title, system_role, password_hash, must_change_password, totp_enabled, active, created_at, updated_at FROM app_users')
  AS t(id INT, keycloak_user_id VARCHAR, username VARCHAR, email VARCHAR, name VARCHAR, first_name VARCHAR, last_name VARCHAR, phone VARCHAR, role_title VARCHAR, system_role VARCHAR, password_hash VARCHAR, must_change_password BOOLEAN, totp_enabled BOOLEAN, active INT, created_at TIMESTAMP, updated_at TIMESTAMP)
  ON CONFLICT (id) DO UPDATE SET system_role = EXCLUDED.system_role;

  -- Create PostgreSQL Cascading Deletion Trigger
  CREATE OR REPLACE FUNCTION fn_app_users_after_delete() RETURNS trigger AS $$
  BEGIN
      -- Note: Peripheral tables access, project_access, watch, team remain in attendance DB
      RETURN OLD;
  END;
  $$ LANGUAGE plpgsql;

  CREATE TRIGGER trg_app_users_delete
  AFTER DELETE ON app_users
  FOR EACH ROW EXECUTE FUNCTION fn_app_users_after_delete();
  ```
* **Verification Check**: Query `SELECT id, email, system_role FROM users.app_users;` and verify all existing team accounts exist with valid `system_role` values (`admin`, `project-manager`, `member`).

---

### Task 3: Keycloak Realm Roles & Default Role Configuration
* **Goal**: Ensure Keycloak realm `keenable` has standard realm roles and default assignment.
* **Keycloak Configuration Commands**:
  ```bash
  # Authenticate kcadm.sh
  podman exec keycloak /opt/keycloak/bin/kcadm.sh config credentials --server http://localhost:8080/auth --realm master --user admin --password 'KeycloakAdmin2026!'

  # Create Realm Roles
  podman exec keycloak /opt/keycloak/bin/kcadm.sh create roles -r keenable -s name=admin -s 'description=System Administrator' || true
  podman exec keycloak /opt/keycloak/bin/kcadm.sh create roles -r keenable -s name=project-manager -s 'description=Project Manager' || true
  podman exec keycloak /opt/keycloak/bin/kcadm.sh create roles -r keenable -s name=member -s 'description=Standard Team Member' || true

  # Add 'member' to default composite role
  podman exec keycloak /opt/keycloak/bin/kcadm.sh add-roles -r keenable --rname default-roles-keenable --crossparams roleName=member || true
  ```
* **Verification Check**: Run `kcadm.sh get-roles -r keenable` and verify `admin`, `project-manager`, and `member` exist.

---

### Task 4: Keycloak User Storage SPI Update & Deployment
* **Goal**: Update Java SPI code to connect to database `users`, expose custom attributes (`phone`, `role_title`), and dynamically map realm roles.
* **SPI Java Implementation Details**:
  * **`AttendanceUserStorageProvider.java`**:
    * JDBC URL: `jdbc:postgresql://openproject-db:5432/users`
    * `addUser()`: Inserts into `users.app_users` with default `system_role = 'member'`.
    * `removeUser()`: Executes `DELETE FROM users.app_users WHERE id = ?`.
  * **`AttendanceUserAdapter.java`**:
    * Custom Attributes: Exposes `phone` and `role_title`.
    * Realm Role Mapping (`getRealmRoleMappingsStream()` and `hasRole()`):
      * If `app_users.system_role == 'admin'` -> Grants Keycloak realm role `admin`.
      * If `app_users.system_role == 'project-manager'` -> Grants Keycloak realm role `project-manager`.
      * Always grants default Keycloak realm role `member`.
* **Build & Deploy Commands**:
  ```bash
  # Build jar with Maven container
  podman run --rm -v /opt/spi-build:/usr/src/app -w /usr/src/app docker.io/library/maven:3.9-eclipse-temurin-21-alpine mvn clean package

  # Deploy jar and restart Keycloak
  cp /opt/spi-build/target/keycloak-attendance-user-storage-1.0.0.jar /opt/keycloak-providers/
  systemctl restart keycloak
  ```
* **Verification Check**: Check Keycloak container logs (`podman logs keycloak`) for `AttendanceUserStorageProviderFactory initialized` and test logging into Keycloak Admin UI.

---

### Task 5: Attendance Application Connection & "Smart Role" Flow Update
* **Goal**: Point Attendance app to database `users` and implement single-action PM/Engineer creation.
* **Backend Modifications (`app.py`)**:
  1. Connection String:
     `DATABASE_URL = "postgresql://attendance:AttendancePass2026!@openproject-db:5432/users"`
  2. Role Constants:
     * `KC_ADMIN_ROLE = "admin"`
     * `KC_MANAGER_ROLE = "project-manager"`
     * `KC_MEMBER_ROLE = "member"`
  3. "Smart Role" Logic in `/team/add` and `/team/update`:
     * If chosen role is `Project Manager` or `Team Lead`:
       * Set `system_role = 'project-manager'` in `app_users`.
       * Automatically assign Keycloak realm role `project-manager`.
       * Automatically grant project access in `project_access`.
     * If chosen role is `Admin`:
       * Set `system_role = 'admin'` in `app_users`.
       * Automatically assign Keycloak realm role `admin`.
     * Otherwise:
       * Set `system_role = 'member'` in `app_users`.
       * Automatically assign default Keycloak realm role `member`.
  4. Restart Container: `systemctl restart attendance`.
* **Verification Check**: Access Attendance UI, add a new user under Team as "Project Manager", verify DB record in `users.app_users`, Keycloak role assignment, and project PM controls.

---

### Task 6: Final End-to-End System Verification & Testing
* **Goal**: Validate complete data flow, role mappings, and cascading deletion safety.
* **Test Matrix**:
  1. **Test Case 1 (Keycloak UI Creation)**: Create user in Keycloak Admin UI -> Verify insertion in `users.app_users` with custom attributes `phone` and `role_title`.
  2. **Test Case 2 (Attendance Portal Creation)**: Create "Project Manager" in Attendance -> Verify Keycloak receives `project-manager` role mapping and Attendance grants PM dashboard access.
  3. **Test Case 3 (Cascading Deletion Safety)**: Delete user in Keycloak UI -> Verify PostgreSQL trigger deletes `access` and `project_access` rows, sets `team.active = 0`, and preserves `attendance` history logs.
* **Verification Check**: All 3 test cases pass cleanly with zero errors.

---

## 4. Documentation Location Summary

All project documentation is saved in the workspace repository:
* **Architecture Specification**: [docs/ARCHITECTURE_AND_DESIGN_SPEC.md](file:///home/user/Desktop/Projects/management/attendance/docs/ARCHITECTURE_AND_DESIGN_SPEC.md)
* **Execution Task Tracker**: [docs/TASKS.md](file:///home/user/Desktop/Projects/management/attendance/docs/TASKS.md)
