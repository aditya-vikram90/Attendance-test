# Master Migration Tracker: Single User Database & Keycloak Java SPI

This living document tracks the step-by-step migration of the **Attendance & Keycloak Authentication Architecture** from a dual-database model to a unified single database with Keycloak Java User Storage SPI federation, single-active-project assignment, cross-project bench pool, and admin override controls.

---

## 1. Architectural Evolution: Earlier vs. New

### A. What Was Earlier (The Historical Architecture)

```
[Attendance Portal]                                 [Keycloak SSO]
       │                                                   │
       ▼                                                   ▼
PostgreSQL 'attendance' DB                          PostgreSQL 'keycloak' DB
Table: 'team'                                       Table: 'user_entity' & 'credential'
- project_id                                        - username
- member_id                                         - email
- name, email, phone, role                          - first_name, last_name, password_hash
- active (1 / 0)                                    - requiredActions (UPDATE_PASSWORD, etc.)
```

#### Major Limitations of the Earlier Architecture:
1. **Data Duplication**: User identities (names, emails, phones) were stored in two separate places—Attendance's `team` table and Keycloak's `user_entity` table.
2. **Synchronization Fragility**: Creating a user in Attendance required calling Keycloak's Admin REST API behind the scenes. If the network glitched or Keycloak restarted, the two databases became out of sync.
3. **Project Isolation**: When an engineer was marked inactive (`active = 0`) in Project A, they were completely invisible to Project Managers in Project B and C. There was no company-wide talent bench.
4. **No Single Active Project Enforcement**: Engineers could inadvertently be added across multiple projects without clear ownership.

---

### B. What Is Being Done Now (The Unified Architecture)

```
                               ┌────────────────────────────────────────────────────────┐
                               │             CENTRAL POSTGRESQL DATABASE                │
                               │                                                        │
                               │   ┌────────────────────────────────────────────────┐   │
                               │   │                   app_users                    │   │
                               │   │────────────────────────────────────────────────│   │
                               │   │ id (PK)                                        │   │
                               │   │ email, phone, name, first_name, last_name      │   │
                               │   │ password_hash, must_change_password            │   │
                               │   │ totp_enabled                                   │   │
                               │   │ current_project_id (FK -> project.id)          │   │
                               │   │ active (1 = active employee, 0 = offboarded)   │   │
                               │   └───────────────────────┬────────────────────────┘   │
                               │                           │ 1                          │
                               │                           │                            │
                               │                           │ *                          │
                               │   ┌───────────────────────▼────────────────────────┐   │
                               │   │                      team                      │   │
                               │   │────────────────────────────────────────────────│   │
                               │   │ (project_id, member_id) [PK]                   │   │
                               │   │ user_id (FK -> app_users.id)                   │   │
                               │   │ role, shift_start, active (1 / 0)              │   │
                               │   │ updated_by, updated_at                         │   │
                               │   └────────────────────────────────────────────────┘   │
                               └───────────▲────────────────────────────▲───────────────┘
                                           │                            │
                                    Direct │ JDBC                       │ Direct SQL
                                           │                            │
                       ┌───────────────────┴───────┐   ┌────────────────┴───────────────┐
                       │        KEYCLOAK 26        │   │       ATTENDANCE SERVICE       │
                       │                           │   │                                │
                       │ Custom Java SPI Provider  │   │ • Active Team List             │
                       │ (UserStorageProvider)     │   │ • Available Bench Pool         │
                       │ Authenticates directly    │   │ • Duplicate Prevention Lookup  │
                       │ against 'app_users' table │   │ • Admin Direct Movement        │
                       └───────────────────────────┘   └────────────────────────────────┘
```

#### Core Benefits of the New Architecture:
1. **Single Source of Truth**: All user identities exist once in `app_users`. Keycloak stores zero duplicate user accounts.
2. **True Federation**: Keycloak acts purely as an OIDC / OAuth2 gateway, checking credentials dynamically against `app_users` via its custom Java SPI.
3. **Strict Single Active Project**: An engineer can be active in **exactly one project at a time** (`current_project_id`).
4. **Global Inactive / Available Pool (Bench)**: Any engineer released from a project (`current_project_id IS NULL`) immediately becomes visible in the "Available Engineers" pool for all other projects.
5. **Duplicate Prevention**: Entering an existing email or phone displays their live assignment status and blocks duplicate creation.
6. **Admin Direct Movement Override**: Admins can reassign any engineer directly from one project to another in 1 click.

---

## 2. Step-by-Step Migration Roadmap & Status

| Step | Phase | Description | Status |
| :---: | :--- | :--- | :---: |
| **0** | **Safety Backups & Master Tracker** | Full SQL dumps of both DBs, code backups, and initialization of master tracking documentation. | **COMPLETED** ✅ |
| **1** | **Central User Database Schema** | Create `app_users` table in PostgreSQL, migrate existing users/engineers, and verify data consistency. | **PENDING APPROVAL** ⏳ |
| **2** | **Keycloak Java User Storage SPI** | Build Java federation plugin (`.jar`), mount into Keycloak container, enable federation provider in realm `keenable`. | **PENDING** ⏳ |
| **3** | **Attendance Portal Backend & UI** | Implement Single Project enforcement, Bench Pool UI, Duplicate Prevention checks, and Admin Movement override. | **PENDING** ⏳ |
| **4** | **End-to-End System Verification** | Verify login, password reset, OTP setup, cross-project bench allocation, and Admin transfer flows. | **PENDING** ⏳ |

---

## 3. Step Execution Log

### Step 0: Safety Backups & Master Tracker
* **Execution Date & Time**: `2026-10-12 19:44:56 IST`
* **Backup Directory**: `/opt/backups/migration_20261012/` on server `159.65.155.30`

#### Exact Commands Executed:
```bash
# 1. Create timestamped backup directory
mkdir -p /opt/backups/migration_20261012

# 2. Dump PostgreSQL attendance database
podman exec openproject-db pg_dump -U attendance attendance > /opt/backups/migration_20261012/attendance_db_pre_migration.sql

# 3. Dump PostgreSQL keycloak database
podman exec openproject-db pg_dump -U keycloak keycloak > /opt/backups/migration_20261012/keycloak_db_pre_migration.sql

# 4. Backup application code and templates
cp /opt/attendance-service/app.py /opt/backups/migration_20261012/app.py.bak
cp /opt/attendance-service/templates/team.html /opt/backups/migration_20261012/team.html.bak

# 5. Backup service environment configurations
cp /etc/attendance/attendance.env /opt/backups/migration_20261012/attendance.env.bak
cp /etc/keycloak/keycloak.env /opt/backups/migration_20261012/keycloak.env.bak

# 6. Verify backup directory listings
ls -lh /opt/backups/migration_20261012/

# 7. Verify table structures and user records inside backups
grep "CREATE TABLE public.team" /opt/backups/migration_20261012/attendance_db_pre_migration.sql -A 6
grep -E "dev.arun|pm.sharma" /opt/backups/migration_20261012/attendance_db_pre_migration.sql
grep "CREATE TABLE public.user_entity" /opt/backups/migration_20261012/keycloak_db_pre_migration.sql -A 6
grep -E "admin@keenable.io|dev.sadik@keenable.io" /opt/backups/migration_20261012/keycloak_db_pre_migration.sql
```

#### Backups Created & Verified:
| File Name | File Size | Description |
| :--- | :--- | :--- |
| `attendance_db_pre_migration.sql` | `8.3 KB` | Full PostgreSQL dump of `attendance` database (`team`, `attendance`, `project`, `access`). |
| `keycloak_db_pre_migration.sql` | `359 KB` | Full PostgreSQL dump of `keycloak` database (`user_entity`, `credential`, realms). |
| `app.py.bak` | `65 KB` | Backup of existing Flask application code. |
| `team.html.bak` | `4.4 KB` | Backup of existing Team management template. |
| `attendance.env.bak` | `685 B` | Backup of Attendance environment configuration. |
| `keycloak.env.bak` | `369 B` | Backup of Keycloak environment configuration. |

* **Result**: All backups successfully verified and stored.


---

### Step 1: Central User Database Schema (Preview)
* **What will be done upon approval**:
  1. Execute DDL to create `app_users` table in PostgreSQL `attendance` database.
  2. Populate `app_users` with all 8 existing employees (`admin@keenable.io`, `pm.sharma`, `pm.verma`, `dev.arun`, `dev.neha`, `dev.vikram`, `dev.anjali`, `dev.sadik`) with their project associations and BCrypt-hashed credentials.
  3. Verify data integrity with SQL check queries.
