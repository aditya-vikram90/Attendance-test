# OpenProject Identity & Credential Synchronization Guide

## 1. Executive Summary

This document describes the unified identity and credential architecture between **Central Identity** (`users` database), **Attendance Management**, **Keycloak**, and **OpenProject Community Edition**.

Because OpenProject Community Edition restricts the built-in OpenID Connect (OIDC) and SAML provider plugins behind an Enterprise Edition license key (`sso_auth_providers`), this system achieves **Single Sign-On and Unified Credential Management** via a high-performance, real-time PostgreSQL Foreign Data Wrapper (`postgres_fdw`) synchronization pipeline.

---

## 2. Architecture Overview

```
+-----------------------------------------------------------------------------------+
|                                KEYCLOAK REALM                                      |
|                       (Federated via Java Storage SPI)                            |
+-----------------------------------------+-----------------------------------------+
                                          |
                                          v
+-----------------------------------------------------------------------------------+
|                         CENTRAL IDENTITY DATABASE                                 |
|                               (users.app_users)                                   |
|                 (Single Source of Truth: ID, Roles, BCrypt Hash)                   |
+---------------------+---------------------------------------+---------------------+
                      |                                       |
                      | (postgres_fdw Trigger)                | (postgres_fdw)
                      v                                       v
+---------------------------------------+   +---------------------------------------+
|          OPENPROJECT DATABASE         |   |          ATTENDANCE DATABASE          |
|    (openproject.users / passwords)    |   |     (attendance.access / punch / ...) |
+---------------------------------------+   +---------------------------------------+
```

### Key Technical Pillars:
1. **Identical Password Hashing**: OpenProject authenticates passwords using native **BCrypt** (`UserPassword::Bcrypt`). The central database also hashes passwords with standard **BCrypt** (`crypt('...', gen_salt('bf', 10))`).
2. **Real-Time Cross-Database Triggers**: When a user is created, updated, or changes their password in Attendance or Keycloak, a PostgreSQL trigger immediately mirrors the change into OpenProject's `users` and `user_passwords` tables.
3. **No Enterprise Licensing Required**: Runs 100% natively on OpenProject Community Edition without modifying proprietary core files or violating licensing.

---

## 3. Database Schema & Foreign Tables

In database `users`, the following foreign resources connect to database `openproject`:

* **Foreign Server**: `openproject_db_server` (`127.0.0.1:5432`, dbname `openproject`)
* **Foreign User Mapping**: `users_admin` -> `openproject`
* **Foreign Tables**:
  - `op_remote_users`: Maps to `openproject.users` (for user lookups and updates)
  - `op_remote_users_insert`: Maps to `openproject.users` (omits `id` to allow OpenProject's serial sequence `users_id_seq` to assign IDs safely)
  - `op_remote_user_passwords`: Maps to `openproject.user_passwords` (for password lookups and updates)
  - `op_remote_user_passwords_insert`: Maps to `openproject.user_passwords` (omits `id` to allow `user_passwords_id_seq` to assign IDs safely)

---

## 4. Cross-Database Trigger Implementation

Trigger: `trg_sync_app_users_to_openproject`  
Table: `users.app_users` (AFTER INSERT OR UPDATE FOR EACH ROW)  
Function: `fn_sync_app_users_to_openproject()`

### Synchronization Rules:
1. **Name & Profile**:
   - First name and last name are extracted and synchronized to OpenProject `firstname` and `lastname`.
   - Email is synchronized to `mail`.
2. **Account Status**:
   - `active = 1` in central identity -> `status = 1` (Active) in OpenProject.
   - `active = 0` in central identity -> `status = 3` (Locked/Inactive) in OpenProject.
3. **Administrator Privilege**:
   - `system_role = 'admin'` -> `admin = true` in OpenProject.
   - `system_role IN ('project-manager', 'member')` -> `admin = false` in OpenProject.
4. **BCrypt Passwords**:
   - When `password_hash` is updated, the trigger updates or inserts a record in OpenProject `user_passwords` with `type = 'UserPassword::Bcrypt'` and `hashed_password = NEW.password_hash`.

---

## 5. User Lifecycle & Data Preservation

When an employee departs or is removed:
- Their account in `users.app_users` is deactivated (`active = 0`).
- The trigger marks their OpenProject status as **Locked** (`status = 3`).
- **Data Integrity Guarantee**: OpenProject does **NOT** delete the user record. All work packages, project tasks, comments, time bookings, and audit trails remain intact with proper attribution.

---

## 6. Backups and Rollback

### Legacy User Backups (Created 2026-10-15 23:36 IST):
- SQL Dump: `/var/backups/openproject_legacy_users_20261015.sql`
- JSON Dump: `/root/management/attendance/docs/backups/legacy_openproject_users.json`

To restore any legacy demo account if required:
```bash
podman exec -i openproject-db psql -U openproject -d openproject < /var/backups/openproject_legacy_users_20261015.sql
```

---

## 7. Verification Commands

To check the synchronization status across databases:

```bash
# 1. Check central master users:
podman exec openproject-db psql -U users_admin -d users -c "SELECT id, email, system_role, active FROM app_users;"

# 2. Check active OpenProject users:
podman exec openproject-db psql -U openproject -d openproject -c "SELECT id, login, mail, status, admin FROM users WHERE status = 1;"

# 3. Test OpenProject authentication via Rails runner:
podman exec openproject bundle exec rails runner 'u = User.try_to_login("mohd.sadik@fosteringlinux.com", "Keenable@2026"); puts u ? "SUCCESS" : "FAILED"'
```
