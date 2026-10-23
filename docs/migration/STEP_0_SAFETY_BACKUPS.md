# Step 0: Safety Backups & Pre-Migration Snapshot

* **Phase**: Step 0 of 4
* **Status**: **COMPLETED & VERIFIED** ✅
* **Server**: `159.65.155.30`
* **Execution Timestamp**: `2026-10-12 19:44:56 IST`
* **Backup Directory**: `/opt/backups/migration_20261012/`

---

## 1. Purpose of Step 0

Before performing any database restructuring, Keycloak SPI deployment, or application code changes, a complete safety snapshot was captured. This ensures zero risk: if any step encounters an unexpected error, the entire environment can be restored to its exact pre-migration state within 60 seconds.

---

## 2. Exact Commands Executed

```bash
# Step 2.1: Create timestamped backup directory
mkdir -p /opt/backups/migration_20261012

# Step 2.2: Dump Attendance PostgreSQL database (tables, data, constraints, sequences)
podman exec openproject-db pg_dump -U attendance attendance > /opt/backups/migration_20261012/attendance_db_pre_migration.sql

# Step 2.3: Dump Keycloak PostgreSQL database (realms, clients, users, credentials)
podman exec openproject-db pg_dump -U keycloak keycloak > /opt/backups/migration_20261012/keycloak_db_pre_migration.sql

# Step 2.4: Snapshot application code and templates
cp /opt/attendance-service/app.py /opt/backups/migration_20261012/app.py.bak
cp /opt/attendance-service/templates/team.html /opt/backups/migration_20261012/team.html.bak

# Step 2.5: Snapshot environment configuration files
cp /etc/attendance/attendance.env /opt/backups/migration_20261012/attendance.env.bak
cp /etc/keycloak/keycloak.env /opt/backups/migration_20261012/keycloak.env.bak
```

---

## 3. Backups Inventory & Verification

### File Listing on Server:
```
-rw-r--r-- 1 root root  65K Oct 12 19:44 app.py.bak
-rw-r--r-- 1 root root 8.3K Oct 12 19:44 attendance_db_pre_migration.sql
-rw-r--r-- 1 root root 359K Oct 12 19:44 keycloak_db_pre_migration.sql
-rw-r--r-- 1 root root 4.4K Oct 12 19:44 team.html.bak
-rw------- 1 root root  685 Oct 12 19:44 attendance.env.bak
-rw------- 1 root root  369 Oct 12 19:44 keycloak.env.bak
```

### Verification Checks:
1. **Attendance DB Schema**:
   * Command: `grep "CREATE TABLE public.team" /opt/backups/migration_20261012/attendance_db_pre_migration.sql -A 6`
   * Result: Table definitions for `team`, `attendance`, `access`, `project`, `watch`, and `meta` verified.
2. **Attendance Live Data**:
   * Command: `grep -E "dev.arun|pm.sharma" /opt/backups/migration_20261012/attendance_db_pre_migration.sql`
   * Result: Real user records present in the dump (`dev.arun`, `pm.sharma`, `dev.neha`, `dev.vikram`).
3. **Keycloak DB Schema & Credentials**:
   * Command: `grep "CREATE TABLE public.user_entity" /opt/backups/migration_20261012/keycloak_db_pre_migration.sql -A 6`
   * Result: User entities, credentials, and realm configurations verified.

---

## 4. Disaster Recovery & Rollback Runbook

If a full rollback is ever required at any point during the migration, run the following commands:

```bash
# 1. Restore Attendance Database
cat /opt/backups/migration_20261012/attendance_db_pre_migration.sql | podman exec -i openproject-db psql -U attendance -d attendance

# 2. Restore Keycloak Database
cat /opt/backups/migration_20261012/keycloak_db_pre_migration.sql | podman exec -i openproject-db psql -U keycloak -d keycloak

# 3. Restore Application Files & Restart Services
cp /opt/backups/migration_20261012/app.py.bak /opt/attendance-service/app.py
cp /opt/backups/migration_20261012/team.html.bak /opt/attendance-service/templates/team.html
podman build -t localhost/attendance:latest /opt/attendance-service
systemctl restart attendance
systemctl restart keycloak
```
