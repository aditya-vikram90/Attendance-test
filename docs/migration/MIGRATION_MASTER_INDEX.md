# Central User Database & Keycloak SPI Migration Master Index

This document tracks the end-to-end migration from duplicated Keycloak/Attendance databases to a unified single-database architecture with Keycloak Java User Storage SPI.

---

## 1. Executive Summary & Goals
- **Single Central User Database**: All employee identities, passwords, and project assignments reside in PostgreSQL `attendance.app_users`.
- **Zero Data Duplication**: Keycloak acts strictly as an OpenID Connect federation broker using a custom Java User Storage SPI.
- **Single Active Project Model**: An employee belongs to only 1 active project at a time.
- **Cross-Project Bench Pool**: Inactive or unassigned users appear in an available bench pool accessible to PMs across projects.
- **Duplicate Prevention**: Re-adding an existing user displays their current status without creating a new record.
- **Admin Direct Override**: System administrators can reassign users between projects directly.

---

## 2. Step-by-Step Implementation Dashboard

| Step | Title | Status | Runbook Document |
| :--- | :--- | :---: | :--- |
| **Step 0** | **Safety Backups & Pre-Migration Snapshots** | `COMPLETED` | [STEP_0_SAFETY_BACKUPS.md](STEP_0_SAFETY_BACKUPS.md) |
| **Step 1** | **Central User DB Schema (`app_users`) & Data Backfill** | `COMPLETED` | [STEP_1_CENTRAL_USER_DB.md](STEP_1_CENTRAL_USER_DB.md) |
| **Step 2** | **Keycloak Java User Storage SPI (`.jar` build & mount)** | `COMPLETED` | [STEP_2_KEYCLOAK_JAVA_SPI.md](STEP_2_KEYCLOAK_JAVA_SPI.md) |
| **Step 3** | **Attendance Portal Backend & Team Management Migration** | `COMPLETED` | [STEP_3_PROJECT_AND_TEAM_MIGRATION.md](STEP_3_PROJECT_AND_TEAM_MIGRATION.md) |
| **Step 4** | **End-to-End Verification & User Acceptance Testing** | `COMPLETED` | [STEP_4_VERIFICATION_TESTS.md](STEP_4_VERIFICATION_TESTS.md) |

---

## 3. Detailed Change Log & Verified Milestones

### Milestone 0: Backups & Snapshots (Completed)
- Stored full SQL dumps (`attendance` and `keycloak`) in `/opt/backups/migration_20261012/`.
- Snapshot of code and environment variables saved.
- Verified rollback capability.

### Milestone 1: Central Database Schema & Population (Completed)
- Created `app_users` table in `attendance` PostgreSQL DB with `pgcrypto` BCrypt support.
- Migrated 9 users with phone, separated names, titles, and active project IDs.
- Linked `team.user_id` foreign keys to `app_users.id`.
- User verified tables and data interactively via container console.

### Milestone 2: Keycloak Java User Storage SPI (Completed)
- Developed Keycloak 26 Java SPI plugin `keycloak-attendance-user-storage-1.0.0.jar`.
- Mounted into Keycloak via `/opt/keycloak-providers:/opt/keycloak/providers:Z`.
- Configured component in realm `keenable`.
- Removed local shadow duplicates from Keycloak `user_entity` table.
- All 9 users dynamically federated (`f:<component-id>:<id>`). Password validation executed via PostgreSQL BCrypt.
- **Post-deployment Fix**: Resolved Keycloak 26 `VERIFY_PROFILE` prompt by implementing generic attribute delegation (`getFirstAttribute`, `getAttributeStream`, `getAttributes`) in `AttendanceUserAdapter`, updated setter methods to write directly to `app_users`, restored exact admin/PM credentials, and verified `keycloak.fed_user_attribute` table contains 0 rows.

### Milestone 3: Single-Project Attendance Model & Bench Pool (Completed)
- Deactivated legacy multi-project rows in `team` table.
- Implemented Bench Pool query and rendering in `team_page` and `team.html`.
- Implemented 1-click `/team/assign_bench` route.
- Implemented automatic release to bench in `/team/update` (`action=remove`).
- Added conflict prevention guard in `/team/add` preventing engineers from being assigned to multiple active projects simultaneously.
- Implemented Admin Direct Transfer route `/admin/transfer_engineer` with UI controls for system administrators.
- Verified all 6 acceptance criteria via automated test suite in live attendance container.

---

*Last Updated: 2026-10-13 11:58 IST*

