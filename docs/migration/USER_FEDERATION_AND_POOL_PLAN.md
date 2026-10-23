# Implementation Plan: Centralized User Database with Keycloak Java User Storage SPI & Single-Project Assignment Model

This plan outlines the end-to-end transformation of the Attendance and Keycloak architecture to:
1. **Eliminate user data duplication** by using a single central PostgreSQL user database (`app_users`) and federating Keycloak authentication via a custom **Keycloak Java User Storage SPI**.
2. Enforce a **Strict Single Active Project Model** (an engineer can only be active in one project at a time).
3. Create a **Global Inactive / Available Engineers Pool** across all projects.
4. Implement **Duplicate Prevention & Real-Time Lookups** when adding engineers.
5. Provide an **Admin Direct Movement Override** to reassign any engineer between projects without PM approval.

---

## User Review Required

> [!IMPORTANT]
> **Single Active Project Rule**:
> * An engineer can be active in **exactly ONE project at a time**.
> * When an engineer is removed / released from Project A, their status becomes **Inactive / Available (Bench)**.
> * Inactive engineers automatically appear on the team pages of **all projects** in an "Available Engineers" pool. Any Project Manager can add them to their project with 1 click.

> [!IMPORTANT]
> **Keycloak Java User Storage SPI (No Duplicate DB)**:
> * Keycloak will no longer create or duplicate users in its internal `user_entity` table.
> * Keycloak will use a custom compiled Java `.jar` plugin (`keycloak-attendance-user-storage`) running inside Keycloak.
> * When a user logs in at `https://pm.keenable.io/auth/`, the SPI connects directly to our PostgreSQL `app_users` table over JDBC, verifies the password, checks the status, and triggers forced password reset and OTP setup.

> [!NOTE]
> **Admin Movement Authority**:
> * Project Managers can only add/release engineers within their own projects.
> * Admins (`attendance-admin`) have an override dashboard that allows them to move **any engineer from any project to any other project** in 1 click.

---

## Proposed Changes

```
┌────────────────────────────────────────────────────────────────────────┐
│                        CENTRAL POSTGRESQL DB                           │
│                                                                        │
│   ┌───────────────────────────┐      ┌──────────────────────────────┐  │
│   │        app_users          │      │             team             │  │
│   │───────────────────────────│      │──────────────────────────────│  │
│   │ id (PK)                   │1    *│ project_id (FK)              │  │
│   │ email, phone, name        ├──────┤ user_id (FK)                 │  │
│   │ password_hash             │      │ role, shift_start            │  │
│   │ must_change_password      │      │ active (1=active, 0=released)│  │
│   │ totp_enabled              │      │ updated_by, updated_at       │  │
│   │ current_project_id (FK)   │      └──────────────────────────────┘  │
│   │ active (1=company active) │                                        │
│   └─────────────▲─────────────┘                                        │
└─────────────────┼──────────────────────────────────────────────────────┘
                  │
        ┌─────────┴─────────┐
        │                   │
   JDBC │                   │ Direct SQL
        │                   │
┌───────▼───────────┐   ┌───▼────────────────────────────────────────────┐
│ KEYCLOAK 26       │   │ ATTENDANCE SERVICE (Flask)                     │
│ (Quay.io Podman)  │   │                                                │
│                   │   │ • /team: "My Team" (current active engineers)  │
│ Custom Java SPI   │   │ • /team: "Available Engineers" (Bench Pool)    │
│ (UserStorageProvider) │ • /team/add: Duplicate Prevention Check        │
│                   │   │ • /admin/transfer: Admin Direct Movement       │
└───────────────────┘   └────────────────────────────────────────────────┘
```

---

### Component 1: Database Migration — Central User Table (`app_users`)

#### [NEW] Migration script inside Attendance service / PostgreSQL
Create the central `app_users` table and update the `team` table:

```sql
-- 1. Central user table (Single source of truth)
CREATE TABLE IF NOT EXISTS app_users (
    id SERIAL PRIMARY KEY,
    username VARCHAR(150) UNIQUE NOT NULL,
    email VARCHAR(150) UNIQUE NOT NULL,
    first_name VARCHAR(100) NOT NULL,
    last_name VARCHAR(100) DEFAULT '',
    phone VARCHAR(20) UNIQUE,
    role_title VARCHAR(60) DEFAULT 'Developer',
    password_hash VARCHAR(255) NOT NULL,
    must_change_password BOOLEAN DEFAULT TRUE,
    totp_secret VARCHAR(64) DEFAULT NULL,
    totp_enabled BOOLEAN DEFAULT FALSE,
    current_project_id INT REFERENCES project(id) DEFAULT NULL,
    active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_app_users_email ON app_users(lower(email));
CREATE INDEX IF NOT EXISTS idx_app_users_curr_proj ON app_users(current_project_id);
```

* Populate `app_users` from the existing distinct engineers in `team` and `keycloak.user_entity`.
* Keep `team` table as the historical project assignment table, linking `user_id` to `project_id`.

---

### Component 2: Keycloak Java User Storage SPI

Create a lightweight, standalone Java Maven project: `keycloak-attendance-user-storage`.

#### Files to Create:
1. **`pom.xml`**:
   * Dependencies: `keycloak-core`, `keycloak-server-spi`, `org.postgresql:postgresql:42.7.2`, `bcrypt`.
2. **`AttendanceUserStorageProvider.java`**:
   * Implements `UserStorageProvider`, `UserLookupProvider`, `CredentialInputValidator`, `CredentialInputUpdater`.
   * Connects via JDBC to `jdbc:postgresql://openproject-db:5432/attendance`.
   * `getUserByUsername` / `getUserByEmail`: queries `app_users`.
   * `isValid(PasswordCredential)`: validates BCrypt/PBKDF2 hash against `app_users.password_hash`.
   * `updateCredential`: updates `password_hash` in `app_users` and sets `must_change_password = false`.
3. **`AttendanceUserAdapter.java`**:
   * Wraps `app_users` record as a Keycloak `UserModel`.
   * Sets `requiredActions`:
     * If `must_change_password`: adds `"UPDATE_PASSWORD"`.
     * If `!totp_enabled`: adds `"CONFIGURE_TOTP"`.
4. **`AttendanceUserStorageProviderFactory.java`**:
   * Provider ID: `"attendance-federation"`.
5. **`META-INF/services/org.keycloak.storage.UserStorageProviderFactory`**:
   * Standard Java SPI registration.

#### Build & Deployment:
* Build the `.jar` inside a temporary `maven:3.9-eclipse-temurin-21-alpine` container:
  `mvn clean package` ➔ `keycloak-attendance-user-storage-1.0.jar`.
* Place `.jar` in `/opt/keycloak-providers/` on the server.
* Mount `/opt/keycloak-providers/:/opt/keycloak/providers/:Z` in `/etc/containers/systemd/keycloak.container`.
* Register provider in realm `keenable` via Keycloak Admin API or CLI.

---

### Component 3: Attendance Portal Backend & UI Updates (`app.py` & `team.html`)

#### [MODIFY] [app.py](file:///home/user/Desktop/Projects/Open%20Project/attendance/attendance-service/app.py)

1. **User Management Methods**:
   * `get_available_engineers()`: queries `app_users WHERE active=true AND current_project_id IS NULL`.
   * `assign_user_to_project(user_id, project_id, role, shift, updated_by)`:
     * Checks if user is already assigned to a project (`current_project_id IS NOT NULL`). If yes and not admin, rejects.
     * Updates `app_users SET current_project_id = pid`.
     * Inserts/updates `team` table with `active = 1`.
   * `release_user_from_project(user_id, project_id, updated_by)`:
     * Updates `team SET active = 0`.
     * Updates `app_users SET current_project_id = NULL`.
     * The engineer enters the global available pool.

2. **Route Updates**:
   * **`GET /team`**:
     * Passes `available_engineers` (all engineers on bench with no current project).
     * Passes `all_active_engineers` for lookup and conflict warnings.
   * **`POST /team/add` (Enhanced with Duplicate Prevention)**:
     * If email/phone matches an existing user:
       * If `current_project_id == pid`: flash error *"Already in this project."*
       * If `current_project_id != NULL`: flash warning *"Engineer is currently active in [Project Name]. PM must release them first, or Admin must transfer."*
       * If `current_project_id IS NULL`: automatically assign them to this project (`assign_user_to_project`).
     * If new user:
       * Creates user in `app_users` with default password `Keenable@2026`.
       * Assigns to current project.
   * **`POST /team/assign_available` [NEW]**:
     * PM selects an available engineer from the bench list and assigns them in 1 click.
   * **`POST /admin/transfer_engineer` [NEW]**:
     * Allowed only for role `admin`.
     * Takes `user_id` and `target_project_id`.
     * Releases user from old project (if any) and reassigns them to target project directly.

#### [MODIFY] [team.html](file:///home/user/Desktop/Projects/Open%20Project/attendance/attendance-service/templates/team.html)
* **Add Section: "Available Engineers (Not in any project)"**:
  * Displays table of all engineers currently on the bench (`current_project_id IS NULL`).
  * Each row has an **"Add to this Project"** button with role and shift input.
* **Update "Add by hand" form**:
  * Real-time duplicate warning helper text.
* **Add Admin Transfer Bar** (visible only if `role == 'admin'`):
  * Dropdown to pick any engineer and move them to the selected project immediately.

---

## Verification Plan

### 1. Keycloak Java SPI Verification
* Build and package the Java User Storage SPI.
* Verify Keycloak loads `attendance-federation` provider without error in container logs.
* Test authentication in Keycloak:
  * Create a user in `app_users` with password `Keenable@2026`.
  * Attempt sign-in on `https://pm.keenable.io/auth/realms/keenable/account/`.
  * Confirm Keycloak queries `app_users`, authenticates successfully, and shows `UPDATE_PASSWORD` and `CONFIGURE_TOTP` screens.
  * Verify Keycloak's `user_entity` table remains free of duplicate user data.

### 2. Single Project Constraint & Bench Pool Verification
* Add engineer `Vikram Singh` to Project 1 (`Cloud Migration & Infra`).
* Verify `current_project_id = 1`.
* Switch to Project 2 (`Client Web Portal`):
  * Verify `Vikram Singh` does **NOT** appear in the Available Engineers pool of Project 2.
  * Attempt to add `dev.vikram@keenable.io` to Project 2 by hand.
  * Confirm the system blocks addition with message: *"Engineer is currently active in Cloud Migration & Infra."*

### 3. Release & Reassign (PM Mutual Transfer)
* In Project 1, click **"Remove"** on `Vikram Singh`.
* Confirm `Vikram Singh` is now marked inactive in Project 1 and `current_project_id = NULL`.
* Switch to Project 2:
  * Confirm `Vikram Singh` immediately appears in **"Available Engineers"**.
  * Click **"Add to this Project"**.
  * Confirm `Vikram Singh` is now active in Project 2!

### 4. Admin Direct Movement Override
* Log in as Admin (`admin@keenable.io`).
* Use the Admin Transfer panel to move `Vikram Singh` directly from Project 2 back to Project 1.
* Confirm the transfer happens instantly in 1 click without requiring PM approval.
