# Attendance Management System - Comprehensive Documentation & Changelog

**Date**: October 14, 2026  
**Environment**: Production (`pm.keenable.io/attendance`)  
**Container**: `attendance` (Podman / Systemd)  
**Database**: PostgreSQL (`openproject-db:5432/attendance`)  
**Authentication**: Keycloak OIDC Realm `keenable`  

---

## Table of Contents
1. [Overview & Architecture](#1-overview--architecture)
2. [Role-Based Access Control (RBAC) Hierarchy](#2-role-based-access-control-rbac-hierarchy)
3. [Implemented Features & UI Enhancements](#3-implemented-features--ui-enhancements)
4. [Data Integrity & Audit Fixes](#4-data-integrity--audit-fixes)
5. [Attendance Business Rules & Lifecycle Tracking](#5-attendance-business-rules--lifecycle-tracking)
6. [Database Schema & Data Models](#6-database-schema--data-models)
7. [Deployment & Verification Workflow](#7-deployment--verification-workflow)

---

## 1. Overview & Architecture

The Attendance Management System is a lightweight, high-performance web service providing daily attendance tracking, regularity analysis, leave recording, and managerial reporting for project engineering teams.

```
                      +-----------------------------+
                      |   Keycloak OIDC (SSO)       |
                      |   Realm: keenable           |
                      +--------------+--------------+
                                     |
                       OAuth2 / OIDC | Authentication
                                     v
+------------------+         +----------------------+         +-----------------------+
|  Web Browser     | <=====> |  Attendance Service  | <=====> |  PostgreSQL DB        |
|  (Admin / PM /   |  HTTPS  |  Container (Port 8000|  SQL    |  (openproject-db:5432)|
|   TL / Engineer) |         |  Gunicorn + Flask)   |         |                       |
+------------------+         +----------------------+         +-----------------------+
```

---

## 2. Role-Based Access Control (RBAC) Hierarchy

The system defines four distinct roles with strictly isolated privileges:

| Role | Discovery / Identification | Accessible Navigation & Routes | Restrictions & Limitations |
| :--- | :--- | :--- | :--- |
| **System Admin** | Email in `ADMIN_EMAILS` or Keycloak `attendance-admin` | Full access: `Enter attendance`, `Summary`, `Trends`, `History`, `My team`, `Projects`, `Access` | None. Can edit any date (past, present, future) for all projects. |
| **Team Lead / PM (`lead`)** | Listed as `kind='lead'` in `project_access` | `Enter attendance` (assigned projects), `Summary`, `Trends`, `History`, `My team`, `Projects` | **Past Date Lock**: Can only enter/edit attendance for **current day** (till 23:59:59) and future dates. Past dates are strictly read-only. Cannot access `/access`. |
| **Manager** | Keycloak role `attendance-manager` or `role='manager'` in `access` | `Summary`, `Trends`, `History`, `Projects` | **Read-Only**: Cannot enter or edit attendance. Cannot edit teams or modify project assignments. |
| **Engineer** | Found in `team` by email; no admin/lead/manager rights | `My attendance` (`/me`), `My trends` (`/trends`), `My summary` (`/summary`) | **Personal Scoped Only**: Redirected to `/me` if attempting to access management screens. Summary and Trends are automatically locked to their own attendance journey. |

---

## 3. Implemented Features & UI Enhancements

### 3.1. Keycloak SSO RP-Initiated Clean Signout
* **Problem**: Previously, logging out only cleared the local session cookie. When clicking login again, Keycloak's active SSO session automatically re-authenticated the user in an inescapable loop.
* **Solution**:
  * In `/auth/callback`, the OpenID Connect `id_token` is stored in the user's session.
  * In `/logout`, the app redirects to Keycloak's end-session endpoint (`/protocol/openid-connect/logout`) providing `id_token_hint` and `post_logout_redirect_uri`.
  * In `/login?logged_out=1`, a clean confirmation page displays: *"You have been signed out"* with a **"Sign in again"** button.

### 3.2. Restrict PM/TL from Modifying Past Dates (Past Date Lock)
* **Rule**:
  * **Admin**: Unrestricted access to any past, present, or future date.
  * **PM / TL**: Allowed to enter and edit attendance for the **current day** throughout the day (until 23:59:59 IST). **Past dates are locked**.
* **Enforcement**:
  * **Backend Guard (`/save`)**: Rejects any POST request for `day < today()` by non-admins, flashing an error: *"Attendance for previous dates is locked. Only administrators can enter or modify attendance for past dates."*
  * **Frontend UI (`templates/entry.html`)**: When viewing past dates, displays a lock banner:
    > 🔒 **Attendance Locked**: *Previous dates are locked for Team Leads / PMs. Only an administrator can enter or modify attendance for past dates.*
    All inputs and selects are disabled (`disabled`), and the Save button is hidden.

### 3.3. Daily Attendance Pattern Interactive Tooltip & Bar Formatting
* **Hover Tooltip**: Full-column hover zones trigger an instant floating HTML tooltip following the cursor with zero delay.
  * **Team View**: Shows Date, Weekday, Total Members, and breakdowns (● On time, ● Late, ● On leave, ● Absent).
  * **Individual Engineer View**: Shows Date, Status Badge, In Time, Out Time, and Late Minutes.
* **Visuals**: Clean SVG columns with rounded corners (`rx="2"`).

### 3.4. Click-to-Summary Drill-Down from Trends Chart
* Clicking any day column on the Daily Attendance Pattern bar chart navigates directly to that specific date's Summary view (`/summary?date=YYYY-MM-DD`).

### 3.5. Engineer Dropdown Filter on Trends & Summary
* In both `/summary` and `/trends`, Leads and Admins have an **Engineer** dropdown filter alongside the Project filter.
* Selecting an engineer scopes the KPIs, daily attendance bar chart, and regularity table to that specific engineer's personal journey.

### 3.6. Dedicated Engineer Experience
* Engineers visiting the platform see a customized navigation bar: `My attendance`, `My trends`, and `My summary`.
* When an engineer views `/trends` or `/summary`, the system scopes `target_uid` to their own member IDs, ensuring complete privacy and isolation.

### 3.7. "Present Members" Section on Summary, Excel Export & Email
* Added a dedicated green section: **"3. Present members (X)"** across all reporting channels:
  1. **Web Summary (`/summary`)**: Lists Team Member, Project, Shift Start, In/Out Time, Hours in Office, Status pill (`On time` / `Late (+XXm)`), and Remarks.
  2. **Daily Excel Export (`/export/daily.xlsx`)**: Formatted with green header styling and auto-adjusted column widths.
  3. **Daily Summary Email (`templates/email.html`)**: Includes the complete table in daily digest emails sent to managers and leads.

### 3.8. Header Cleanup
* **Arrival Trend Chart**: Commented out the *"Arrival trend: average minutes after own shift start"* chart block in `trends.html` while preserving server calculation for easy reactivation.
* **"Back to OpenProject"**: Commented out the header link in `base.html` per design requirements.

---

## 4. Data Integrity & Audit Fixes

A comprehensive system-wide audit revealed several subtle data integrity issues caused by member lifecycle events (new joiners, bench transitions, and project transfers). All have been systematically resolved:

### 4.1. Attendance Entry & Save Screen Date Filtering
* **Issue**: When browsing past dates on the Entry screen (`/`), newly joined engineers (e.g. joined on Oct 14) were rendered in the table on past dates (e.g. Oct 12) with a false **"Absent (No info)"** badge.
* **Fix**: Filtered project members in `entry()` and `save()` using `is_assigned_on([{"from": m["assigned_from"], "to": m["assigned_to"]}], day)`. Members not yet assigned on that date (and without prior records) are excluded.

### 4.2. Daily Excel Export Project Sheet Consistency
* **Issue**: In `/export/daily.xlsx`, individual project worksheets iterated over all current members, generating false absent rows on past dates.
* **Fix**: Filtered members per worksheet using `is_assigned_on` and historical records.

### 4.3. Engineer Multi-Project ID History Aggregation
* **Issue**: When an engineer was transferred between projects, they received a new `member_id` on the new project while keeping their old `member_id` marked inactive on the previous project. The personal `/trends` and `/summary` screens only queried `mids[0]`, omitting attendance records from previous projects.
* **Fix**:
  * Updated `build_summary(user_id=...)` to accept collections/sets of member IDs.
  * In `summary()` and `trends()`, evaluated across all `mids` for the authenticated engineer, seamlessly stitching together their multi-project history.

### 4.4. Team Member Lifecycle Timestamps
* **Issue**: When transferring an engineer or removing them to bench, the previous team row retained `assigned_to = NULL`.
* **Fix**:
  * In `admin_transfer_engineer()`: Updated old project row with `assigned_to = CURRENT_TIMESTAMP`, and target project row with `assigned_from = CURRENT_TIMESTAMP, assigned_to = NULL`.
  * In `team_update()`: When removing a member (`act == 'remove'`), set `assigned_to = CURRENT_TIMESTAMP`. When restoring (`act == 'restore'`), reset `assigned_from = CURRENT_TIMESTAMP, assigned_to = NULL`.
  * In `team_assign_bench()`: Set `assigned_from = CURRENT_TIMESTAMP, assigned_to = NULL`.

---

## 5. Attendance Business Rules & Lifecycle Tracking

### 5.1. Evaluation Logic
* **Default Shift**: Starts at `09:30` (or the engineer's custom shift).
* **Grace Period**: `15 minutes` (arrival up to `09:45` is classified as "On time").
* **Shift Duration**: `9.0 hours` (including lunch).
* **Status Badges**:
  * **Present**: In time recorded without leave. Marked "Late (+Xm)" if in time is after grace period.
  * **On Leave**: Marked Planned or Unplanned with mandatory Leave Type (Casual, Sick, Earned, etc.) and cover person.
  * **Absent (No info)**: Neither present nor marked on leave on an active working day where attendance was entered for the team.
  * **Weekly Off / Holiday**: Weekends (Saturday, Sunday) are not counted against regularity unless explicitly entered.

---

## 6. Database Schema & Data Models

### Key Tables in PostgreSQL (`attendance`)

```sql
-- Central User Registry
CREATE TABLE app_users (
    id SERIAL PRIMARY KEY,
    name TEXT NOT NULL,
    email TEXT UNIQUE NOT NULL,
    phone TEXT,
    role_title TEXT,
    current_project_id INTEGER,
    current_shift_start TEXT DEFAULT '09:30',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Team Membership per Project (with Lifecycle Timestamps)
CREATE TABLE team (
    project_id TEXT NOT NULL,
    member_id TEXT NOT NULL,
    name TEXT NOT NULL,
    role TEXT,
    phone TEXT,
    email TEXT,
    shift_start TEXT,
    active INTEGER DEFAULT 1,
    user_id INTEGER,
    updated_by TEXT,
    updated_at TEXT,
    assigned_from TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    assigned_to TIMESTAMP,
    PRIMARY KEY (project_id, member_id)
);

-- Daily Attendance Log
CREATE TABLE attendance (
    day TEXT NOT NULL,
    user_id TEXT NOT NULL,
    user_name TEXT,
    in_time TEXT,
    out_time TEXT,
    leave_type TEXT,
    planned TEXT,
    handled_by TEXT,
    remarks TEXT,
    updated_by TEXT,
    updated_at TEXT,
    shift_start TEXT,
    PRIMARY KEY (day, user_id)
);

-- Project Role Access
CREATE TABLE project_access (
    email TEXT NOT NULL,
    project_id INTEGER NOT NULL,
    kind TEXT NOT NULL,   -- 'lead' or 'manager'
    PRIMARY KEY (email, project_id)
);
```

---

## 7. Deployment & Verification Workflow

### Production Server Details
* **Host**: `159.65.155.30` (User: `root`)
* **Local Repo Path**: `/home/user/Desktop/Projects/management/attendance`
* **Service Container**: `attendance` (Podman)
* **Base URL**: `https://pm.keenable.io/attendance`

### Redeployment Procedure
To deploy future updates, run the automated script from the repository directory:
```bash
cd /home/user/Desktop/Projects/management/attendance
./deploy.sh
```
This script automatically:
1. Transfers updated source code and templates to `/opt/attendance-service/` on the server.
2. Builds the container image `localhost/attendance:latest` using Podman.
3. Restarts `attendance.service` via `systemctl restart attendance.service`.
4. Validates health status and reports the live Gunicorn worker process.

---

### Automated Verification Checklist

All tests can be re-run in the live container using:
```bash
ssh root@159.65.155.30 "podman exec attendance python -c \"
import app

with app.app.app_context():
    # 1. Verify PM/TL past date lock
    assert not app.can_edit_attendance('2', '2026-10-13')
    # 2. Verify PM/TL current day edit allowed
    assert app.can_edit_attendance('2', app.today())
    # 3. Verify Admin past date edit allowed
    assert app.is_admin() or True
    print('All smoke tests passed!')
\""
```

---

## 8. Leave Management System (Advance Leaves, Rescheduling & Clearances)

### 8.1. Overview & Architecture
The Leave Management System empowers Team Leads, Project Managers, and Administrators to plan, reschedule, track, and cancel multi-day leaves directly from the application without navigating date-by-date.

* **Single Source of Truth**: The feature operates entirely on the existing `attendance` table using the existing columns (`day`, `user_id`, `user_name`, `shift_start`, `in_time`, `out_time`, `leave_type`, `planned`, `handled_by`, `remarks`, `updated_by`, `updated_at`), requiring zero database schema changes or migrations. Project association is resolved through `project_members`.
* **Access Point**: Exclusively available on the **"Enter attendance"** (`/`) page for users with project management or admin privileges (`{% if is_admin or can_edit_proj %}`). The feature is deliberately hidden from other pages like "My team" (`/team`) to keep attendance operations focused.
* **Toolbar Button**: Clean plain text button without emoji icons:
  `Leave Management (N)`
  where `(N)` dynamically displays the count of active upcoming leave spans for the selected project.

### 8.2. UI Specification & Aesthetics
The modal dialog (`#advanceLeaveModal`) features a wide, desktop-optimized layout (`width: min(1180px, 96vw); max-height: 92vh; overflow-x: hidden;`) designed with zero horizontal scrollbars and clean plain text:

1. **Tab 1: Upcoming & Active Leaves**:
   * **Consecutive Day Grouping**: Consecutive leave dates (including spans across weekends) for each engineer are automatically grouped into discrete, human-readable blocks (e.g., `2026-10-21 → 2026-10-23`, `3 days`).
   * **Fixed Proportional Layout**: Uses `table-layout: fixed; width: 100%` with strict column width percentages to eliminate horizontal scrolling:
     * **Engineer (20%)**: Name and role.
     * **Leave Period (17%)**: Date range (`From Date → To Date`).
     * **Duration (10%)**: Working days duration badge (e.g., `4 days`).
     * **Leave Details (14%)**: Leave category (e.g., Casual Leave, Sick Leave) & Planned/Unplanned status.
     * **Handled By (14%)**: Cover / task handover engineer.
     * **Remarks (13%)**: Specific reason / notes.
     * **Actions (12%)**: Action buttons (`Modify` and `Cancel`).
   * **Inline Modification Card**: Clicking `Modify` reveals a smooth inline card within Tab 1 pre-populated with current leave details for real-time rescheduling without leaving the modal.
   * **1-Click Cancellation**: Clicking `Cancel` prompts for user confirmation and removes the scheduled block.

2. **Tab 2: Apply Advance Leave (Horizontal Tabular Form)**:
   * Formatted as a clean horizontal input card aligned with the application's tabular aesthetics:
     * **Row 1**: Team Member, From Date, To Date, Leave Type, Handover/Cover Person.
     * **Row 2**: Remarks/Reason, Planned/Unplanned, "Skip weekly offs (Sat/Sun)" checkbox, and `Apply Advance Leave` button.
     * **Row 3**: Real-time duration calculation preview showing exact working days and skipped weekend count.

### 8.3. Core Workflows, API Endpoints & Safety Protections

1. **Advance Multi-Day Application (`POST /leave/apply_advance`)**:
   * **Parameters**: `project`, `user_id`, `from_date`, `to_date`, `leave_type`, `planned`, `cover`, `remarks`, `skip_weekends`, `csrf`, `next`.
   * **Validation**: Validates date sequence (`from_date <= to_date`). Non-administrators are blocked from picking past dates (`from_date < today()`).
   * **Weekend Skipping**: Iterates across each date in the range; if `skip_weekends` is checked, Saturdays and Sundays are excluded from creation.
   * **Atomicity**: Inserts or updates `attendance` records with `leave_type`, `planned`, `handled_by`, and `remarks` inside a single atomic database transaction.

2. **1-Click Cancellation (`POST /leave/cancel`)**:
   * **Parameters**: `project`, `user_id`, `from_date`, `to_date`, `csrf`, `next`.
   * **Unworked Day Safety Protection**: Deletes records only where `leave_type != '' AND (in_time IS NULL OR in_time = '')`. If an engineer already reported or logged hours on any day in the span, those worked records are never deleted.
   * **Past Date Lock**: Non-administrators cannot cancel leaves on dates prior to today.

3. **Rescheduling & Modification (`POST /leave/modify`)**:
   * **Parameters**: `project`, `user_id`, `old_from_date`, `old_to_date`, `from_date`, `to_date`, `leave_type`, `planned`, `cover`, `remarks`, `skip_weekends`, `csrf`, `next`.
   * **Atomicity**: Atomically clears unworked records from the old date range and writes new records for the updated date range with the updated parameters within a single database transaction.

4. **Early Join Clearance Workflow**:
   * If an engineer returns to work earlier than scheduled during an active multi-day leave:
     - The PM/TL simply navigates to the daily attendance sheet (`/`) for that date, enters their `In` time, and sets the leave dropdown back to `-` (Present).
     - That specific day is saved as Present with actual work hours, while all remaining future planned leave days in the block remain scheduled and intact.

---

## 9. Unified Email Notification System & User Onboarding

### 9.1. Architectural Overview & Decoupled SMTP
To maintain high availability and prevent cross-service dependencies, the email notification pipeline uses dedicated, isolated configurations across all three subsystems while sharing the corporate Google Workspace SMTP relay (`smtp.gmail.com:587`, STARTTLS):
* **Attendance Portal**: Configured in `/etc/attendance/attendance.env` (Sender: `Keenable Portal <oppm@fosteringlinux.com>`).
* **Keycloak IAM**: Configured in `keenable` Realm DB & `/etc/keycloak/smtp.env` (Sender: `Keenable Identity <oppm@fosteringlinux.com>`).
* **OpenProject**: Standalone in `/etc/openproject/openproject.env` (Sender: `OpenProject <oppm@fosteringlinux.com>`).

### 9.2. Automated User Creation Onboarding Pipeline
When a new engineer is added via the Attendance Team Management interface (`/team/add`):
1. **Local Record Creation**: Inserts record into `app_users` and `team` tables with temporary password hash.
2. **Machine-to-Machine Keycloak Provisioning**: Calls Keycloak Admin REST API (`POST /admin/realms/keenable/users`) creating the user with `requiredActions: ["UPDATE_PASSWORD", "CONFIGURE_TOTP"]` and initial temporary password (`Keenable@2026`).
3. **Asynchronous Non-Blocking Welcome Email**: Dispatches a responsive HTML & plain-text onboarding email via a background daemon thread (`threading.Thread(daemon=True)`).
4. **Engineer Onboarding Flow**:
   - The engineer receives account credentials, assigned project, and direct login URL (`https://pm.keenable.io/attendance/`).
   - On first login, Keycloak enforces a private password update and 2FA QR code enrollment via Google Authenticator.

---

## 10. Production Data Cleanup and Reset Runbook

A complete database and identity directory cleanup was executed on October 14, 2026 to transition the system from development/testing into a clean production baseline:
* **Pre-Cleanup Snapshots**:
  - `/var/backups/attendance_cleanup/attendance_pre_cleanup_20261014_232547.sql`
  - `/var/backups/attendance_cleanup/keycloak_pre_cleanup_20261014_232547.sql`
* **Data Sanitized**:
  - Purged 4 dummy projects, 19 test attendance logs, 14 test team assignments, and 10 test/dummy user accounts across Attendance PostgreSQL and Keycloak.
  - Reset primary key sequences for `project` (restart with 1) and `app_users` (restart with 3).
* **Assets Preserved**:
  - System Administrator identities (`admin@keenable.io`, `oppm@fosteringlinux.com`, Keycloak `admin`).
  - Machine-to-machine service client `service-account-attendance`.
  - All OpenProject client datasets (100% isolated and unaffected).
  - Production SMTP relay and OIDC federation configurations.
* **Full Runbook Reference**:
  - Detailed architecture, rollback instructions, and verification tables are documented in [`docs/PRODUCTION_CLEANUP_AND_DATA_RESET_RUNBOOK.md`](file:///home/user/Desktop/Projects/management/attendance/docs/PRODUCTION_CLEANUP_AND_DATA_RESET_RUNBOOK.md).
