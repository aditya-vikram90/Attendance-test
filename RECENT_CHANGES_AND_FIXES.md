# Recent Changes & Fixes Summary

This document summarizes all the specific changes, fixes, and enhancements implemented in the recent updates.

---

## 1. Past Date Attendance Restriction (PM/TL Lock)

### Requirement:
Restrict Project Managers (PM) and Team Leads (TL) from entering or modifying attendance for previous dates. Only Admins can edit past attendance. PMs/TLs are permitted to enter attendance for the current day until midnight (`23:59:59` IST).

### Implementation Details:
* **Backend Permission Rule (`can_edit_attendance`)**:
  * **Admin**: Unrestricted access (can edit past, current, and future dates).
  * **PM / TL**: Can edit current day (`day == today()`) and future dates (for advance planned leave). Cannot edit past dates (`day < today()`).
* **Backend Enforcement (`/save`)**:
  * In `save()` in [`attendance-service/app.py`](file:///home/user/Desktop/Projects/management/attendance/attendance-service/app.py), any save request for a past date submitted by a non-admin is blocked and redirects with an error flash message:
    > *"Attendance for previous dates is locked. Only administrators can enter or modify attendance for past dates."*
* **Frontend UI Lock (`templates/entry.html`)**:
  * When a PM or TL opens a past date from the date picker:
    * Displays an alert banner:
      > 🔒 **Attendance Locked**: *Previous dates are locked for Team Leads / PMs. Only an administrator can enter or modify attendance for past dates.*
    * All input fields (In/Out time, Leave dropdown, Planned/Unplanned, Cover person, Remarks) are set to `disabled`.
    * The **"Save Project"** button is hidden.
    * The footer note shows:
      > 🔒 *Attendance for previous dates is locked for Team Leads / PMs. Contact an administrator to make changes for past dates.*
  * When an Admin opens a past date, the form remains fully editable with the Save button enabled.

---

## 2. Header Cleanup: "Back to OpenProject" Link Removed

### Requirement:
Remove / comment out the "Back to OpenProject" link from the top navigation bar.

### Implementation Details:
* In [`attendance-service/templates/base.html`](file:///home/user/Desktop/Projects/management/attendance/attendance-service/templates/base.html), commented out the link using Jinja comment syntax:
  ```html
  {# {% if op_url %}<a href="{{ op_url }}">Back to OpenProject</a>{% endif %} #}
  ```
* The link is now completely hidden from the header across all user roles.

---

## 3. Data Integrity: Eliminating False "Absent (No Info)" Badges on Past Dates

### Problem:
When navigating to past dates (e.g. October 12) on the Attendance Entry screen (`/`) or downloading the Daily Excel Export, newly joined engineers (who joined on October 14) were appearing in the tables with false **"Absent (No info)"** badges.

### Fix:
* **Attendance Entry Screen (`entry()` & `save()` in `app.py`)**:
  * Filtered project members using `is_assigned_on([{"from": m["assigned_from"], "to": m["assigned_to"]}], day)`.
  * Engineers who were not yet assigned on that date and have no stored attendance record are excluded from the list.
* **Daily Excel Export (`/export/daily.xlsx` in `app.py`)**:
  * Applied the same `is_assigned_on` filtering to all per-project worksheets.

---

## 4. Added "Present Members" Section Across All Reports

### Requirement:
Display a dedicated section showing the list of present members for the day, including their shift details, in/out times, hours in office, status, and remarks.

### Implementation Details:
* **Web Summary Screen (`/summary` and `templates/summary.html`)**:
  * Added section **"3. Present members (X)"** with green styling, displaying:
    * Team member name & contact
    * Project name
    * Shift start time
    * In Time & Out Time
    * Hours in office
    * Status pill (`On time` / `Late (+XXm)`)
    * Remarks
* **Daily Excel Export (`/export/daily.xlsx`)**:
  * Added section **"3. PRESENT MEMBERS"** with green header styling and auto-sized column widths on the Summary worksheet.
* **Daily Digest Email (`templates/email.html`)**:
  * Added the matching **"3. Present members"** table macro to daily summary emails.

---

## 5. Engineer Assignment Lifecycle Timestamps

### Problem:
When transferring an engineer between projects or removing them to the bench, the previous project's assignment record left `assigned_to` as `NULL`, causing ambiguity in historical date boundaries.

### Fix:
* **Project Transfer (`admin_transfer_engineer` in `app.py`)**:
  * Previous project record: `UPDATE team SET active=0, assigned_to=CURRENT_TIMESTAMP ...`
  * New project record: `assigned_from = CURRENT_TIMESTAMP, assigned_to = NULL`.
* **Team Member Removal & Restoration (`team_update` in `app.py`)**:
  * On Remove (`act == "remove"`): `UPDATE team SET active=0, assigned_to=CURRENT_TIMESTAMP ...`
  * On Restore (`act == "restore"`): `UPDATE team SET active=1, assigned_from=CURRENT_TIMESTAMP, assigned_to=NULL ...`
* **Bench Assignment (`team_assign_bench` in `app.py`)**:
  * Sets `assigned_from = CURRENT_TIMESTAMP, assigned_to = NULL`.

---

## 6. Multi-Project / Transferred Engineer History Aggregation

### Problem:
Engineers transferred between projects have multiple `member_id`s in the `team` table. Personal `/trends` and `/summary` screens only queried a single ID, causing attendance from previous projects to be omitted.

### Fix:
* In `build_summary(user_id=...)`: Enhanced `user_id` parameter to accept collections/lists of member IDs.
* In `summary()` and `trends()`: When an engineer logs in, all their associated `mids` are evaluated together, displaying their complete attendance journey across all projects.

---

## 7. Interactive Trends Chart & Drill-Down Navigation

### Enhancements:
1. **Interactive Hover Tooltip (`templates/trends.html`)**:
   * Replaced slow browser `<title>` tooltips with instant floating HTML tooltips following the cursor.
   * **Team View**: Shows total count and color breakdown (● On time, ● Late, ● On leave, ● Absent).
   * **Individual Engineer View**: Shows status badge, In/Out times, and Late minutes.
2. **Click-to-Summary Drill-Down**:
   * Clicking any day column on the Daily Attendance Pattern bar chart navigates directly to that day's summary: `/summary?date=YYYY-MM-DD`.
3. **Engineer Dropdown Filter**:
   * Added an **Engineer** `<select>` dropdown next to Project on `/summary` and `/trends` to inspect individual engineer regularity.
4. **Commented Out Arrival Trend Chart**:
   * Commented out the *"Arrival trend: average minutes after own shift start"* block in `trends.html`.

---

## 8. Keycloak SSO RP-Initiated Clean Signout

### Problem:
Signing out previously only cleared the local cookie, causing users to be automatically re-logged in by Keycloak's active SSO session when navigating back.

### Fix:
* Stored `session["id_token"]` upon authentication callback.
* In `/logout`, redirected to Keycloak's end-session endpoint with `id_token_hint` and `post_logout_redirect_uri`.
* Rendered a clean confirmation page at `/login?logged_out=1` with a **"Sign in again"** button.

---

## 9. Multi-Day Advance Planned Leave Application

### Requirement:
Allow PMs, Team Leads, and Admins to apply approved planned leaves for an engineer across multiple days in advance (e.g., 3-4 days) along with the cover/handover person, without having to manually open and update each day individually.

### Implementation Details:
* **Database Strategy**:
  * Leveraged the existing `attendance` table (`PRIMARY KEY (day, user_id)`).
  * Automatically creates or updates one row per active working day.
  * Zero schema modifications required; 100% instant parity across all reports (Summary, Trends, Excel Export, Email).
* **Backend Endpoint (`/leave/apply_advance`)**:
  * Implemented `@app.route("/leave/apply_advance", methods=["POST"])` with `@login_required` and `can_edit(pid)` checks.
  * Validates date ranges (`from_date <= to_date`, max 60 days).
  * Enforces the past date lock: PMs/TLs cannot apply advance leaves for past dates (`from_date < today()`). Admins have full rights across any period.
  * Iterates across each date in the range, checks `skip_weekends`, and skips weekly offs (Saturday & Sunday).
  * Inserts/updates `attendance` records with `leave_type`, `planned='Planned'`, `handled_by` (cover person), and `remarks` inside a single atomic database transaction.
* **Frontend UI (`templates/entry.html` & `templates/team.html`)**:
  * Added **`📅 Planned Leaves`** button in both the Attendance Entry toolbar (`entry.html`) and the My Team toolbar (`team.html`), displaying active leaves count badge `(N)`.
  * Extracted and upgraded `#advanceLeaveModal` into a comprehensive Unified Leave Center (`templates/advance_leave_modal.html`).
  * Enforced `{% if is_admin or can_edit_proj %}` to guarantee that Administrators and Project Leads always have access regardless of current project filtering.
  * Added `next` parameter support so applying leave from the "My team" screen redirects seamlessly back to "My team" with confirmation flash notifications.
  * Includes a real-time JavaScript counter dynamically displaying the exact working days count and weekend days skipped.

---

## 10. Leave Management System (Advance Leaves, Clearance & Rescheduling)

### Context & Need
Engineers frequently experience schedule shifts: an engineer may return and report to duty earlier than planned, extend a trip, reschedule their leave dates, or have their leave cancelled completely. Previously, modifying or cancelling multi-day leaves required navigating date-by-date through the attendance sheets. Additionally, team leads needed a clean tabular interface without emoji icons and without horizontal scrollbars, scoped exclusively to the attendance entry screen.

### Implemented Solution

1. **Unified Leave Management Modal (`templates/advance_leave_modal.html`)**:
   - Expanded into a wide, 2-tab desktop dialog (`width: min(1180px, 96vw); max-height: 92vh; overflow-x: hidden;`):
     - **Tab 1: Upcoming & Active Leaves**: Displays all scheduled leaves for the project in a clean table with fixed proportions (`table-layout: fixed; width: 100%`) eliminating horizontal scrollbars (Engineer, Leave Period, Duration badge, Leave Details, Handled By, Remarks, and plain text `Modify` and `Cancel` buttons).
     - **Tab 2: Apply Advance Leave**: A compact horizontal input grid matching the tabular design of the application with real-time working days calculation and weekend skipping.
   - Designed in pure plain text with all emoji icons removed.
   - Toolbar button updated to **`Leave Management`** (or `Leave Management (N)` when leaves exist) without any icons.
   - Scoped strictly to the "Enter attendance" screen (`entry.html`); removed from "My team" (`team.html`) and all other pages.

2. **Backend Aggregation & Grouping (`app.py: get_upcoming_leaves`)**:
   - Aggregates future leave records (`day >= today() AND leave_type != ''`) for project members.
   - Automatically merges consecutive days and weekend spans into discrete, human-readable leave blocks (e.g. `2026-10-22 → 2026-10-27`, `4 working days`).

3. **Leave Cancellation Endpoint (`@app.route("/leave/cancel", methods=["POST"])`)**:
   - Allows 1-click revocation of any planned leave block with confirmation.
   - **Safety Guard**: Deletes records only where `leave_type != '' AND (in_time IS NULL OR in_time = '')`, strictly preventing accidental deletion of any day where the engineer actually checked in and worked.
   - **Past Date Lock**: Non-administrators cannot cancel leaves on past dates.

4. **Leave Modification & Rescheduling Endpoint (`@app.route("/leave/modify", methods=["POST"])`)**:
   - Pre-fills current details into an inline edit card within Tab 1.
   - Allows modifying From/To dates (expanding, cutting short, or shifting), leave type, cover person, remarks, and weekend skipping.
   - Performs an atomic database update: clears old unworked dates and writes the updated leave span in a single transaction.

5. **Early Join Clearance on Daily Attendance (`/` & `/save`)**:
   - If an engineer returns early on any day during their leave period, entering their `In` time and changing the leave dropdown back to `-` marks them **Present** for that day while keeping remaining future planned days intact.

---

## 11. Automated User Creation Email & Onboarding System

### Context & Need:
When a new engineer is added to a project, they need their login credentials, assigned project details, and step-by-step instructions to access the portal, reset their temporary password, and configure two-factor authentication (2FA). Rather than tightly coupling with OpenProject's environment files, the system employs isolated, dedicated SMTP configurations across Attendance, Keycloak, and OpenProject.

### Key Implementation Details:
1. **Decoupled SMTP Configurations**:
   - Attendance Service: `/etc/attendance/attendance.env` with `SMTP_HOST=smtp.gmail.com`, `SMTP_PORT=587` (STARTTLS), `SMTP_USER=oppm@fosteringlinux.com`, `SMTP_PASSWORD=bfqzkypnkcmtqrrb`, and `SMTP_DISPLAY_NAME=Keenable Portal`.
   - Keycloak IAM: Configured in `keenable` Realm DB and `/etc/keycloak/smtp.env` with sender `Keenable Identity <oppm@fosteringlinux.com>`.
2. **Machine-to-Machine Provisioning**:
   - In `/team/add`, when a brand new user is created, `keycloak_create_user(mail, name)` is triggered, creating the Keycloak identity with `UPDATE_PASSWORD` and `CONFIGURE_TOTP` required actions.
3. **Asynchronous Non-Blocking Welcome Email**:
   - Implemented `send_welcome_email(to_email, name, role, project_name, temp_password)` and `send_welcome_email_async(...)` using `threading.Thread(daemon=True)`.
   - Sends a modern responsive HTML email with plaintext fallback containing portal URL, login credentials, and 4-step onboarding instructions.
   - Delivery verified live on production container with zero web UI latency.

---

## Summary of Modified Files

| File | Key Changes Made |
| :--- | :--- |
| [`attendance-service/app.py`](file:///home/user/Desktop/Projects/management/attendance/attendance-service/app.py) | • Added `send_welcome_email` and `send_welcome_email_async` with responsive HTML and plain text templates.<br>• Hooked Keycloak provisioning (`keycloak_create_user`) and asynchronous welcome email dispatch into `/team/add`.<br>• Added `ssl`, `MIMEMultipart`, and `MIMEText` imports.<br>• Added `get_upcoming_leaves(pid)` grouping consecutive and weekend-spanning leaves.<br>• Added `@app.route("/leave/cancel")` with unworked safety guards and past date lock.<br>• Added `@app.route("/leave/modify")` with atomic date span rescheduling.<br>• Added `@app.route("/leave/apply_advance")` with admin override and `next_url` support.<br>• Enriched `entry()` context with `upcoming_leaves`.<br>• Added `can_edit_attendance(pid, day)` to lock past dates for PM/TL.<br>• Protected `/save` against past date edits by non-admins.<br>• Filtered `entry()`, `save()`, and `export_daily()` by `is_assigned_on`.<br>• Added `present_list` to `build_summary()` and Excel export. |
| [`docs/EMAIL_NOTIFICATION_SYSTEM_SETUP.md`](file:///home/user/Desktop/Projects/management/attendance/docs/EMAIL_NOTIFICATION_SYSTEM_SETUP.md) | • Comprehensive architecture, decoupled configuration reference, and step-by-step setup runbook for Keycloak and Attendance email notification system. |
| [`attendance-service/templates/advance_leave_modal.html`](file:///home/user/Desktop/Projects/management/attendance/attendance-service/templates/advance_leave_modal.html) | • Designed Leave Management Modal with Tab 1 (Upcoming Leaves Table with Modify/Cancel) and Tab 2 (Compact Horizontal Tabular Apply Form).<br>• Wide layout `min(1180px, 96vw)`, fixed table column widths, zero horizontal scrollbars.<br>• Plain text design with all emoji icons removed. |
| [`attendance-service/templates/entry.html`](file:///home/user/Desktop/Projects/management/attendance/attendance-service/templates/entry.html) | • Added plain text toolbar button `Leave Management (N)`.<br>• Added "Attendance Locked" banner for past dates.<br>• Disabled all form inputs and hid Save button when past date is locked. |
| [`attendance-service/templates/team.html`](file:///home/user/Desktop/Projects/management/attendance/attendance-service/templates/team.html) | • Kept focused on team membership; removed Leave Management button and modal. |
| [`attendance-service/templates/base.html`](file:///home/user/Desktop/Projects/management/attendance/attendance-service/templates/base.html) | • Commented out "Back to OpenProject" link in header.<br>• Added engineer navigation links (`My attendance`, `My trends`, `My summary`). |
| [`attendance-service/templates/summary.html`](file:///home/user/Desktop/Projects/management/attendance/attendance-service/templates/summary.html) | • Added "3. Present members" section.<br>• Added Engineer dropdown filter for Admins and Leads. |
| [`docs/PRODUCTION_CLEANUP_AND_DATA_RESET_RUNBOOK.md`](file:///home/user/Desktop/Projects/management/attendance/docs/PRODUCTION_CLEANUP_AND_DATA_RESET_RUNBOOK.md) | • Comprehensive runbook and audit record for production database cleanup, backup snapshots, Keycloak sanitization, and disaster recovery. |

---

## 12. Production Data Cleanup and Reset Runbook

* **Objective**: Transitioned environment from testing/development to a production baseline for real organizational usage.
* **Pre-Cleanup Snapshots**:
  - `/var/backups/attendance_cleanup/attendance_pre_cleanup_20261014_232547.sql` (17.7 KB)
  - `/var/backups/attendance_cleanup/keycloak_pre_cleanup_20261014_232547.sql` (368.8 KB)
* **Purged Data**:
  - Wiped all dummy projects (`Cloud Migration & Infra`, `Client Web Portal`, `Mobile Banking App`, `sub client app`).
  - Purged all 19 dummy attendance records and 14 test team assignments.
  - Purged 10 dummy and test users across Keycloak and Attendance database.
  - Reset primary key sequences for `project` (restart with 1) and `app_users` (restart with 3).
* **Preserved Assets**:
  - `admin@keenable.io` (System Admin) and `oppm@fosteringlinux.com` (Corporate Admin).
  - Keycloak master admin and `service-account-attendance` M2M provisioning client.
  - All 23 production client projects in OpenProject (100% untouched).
* **Full Documentation**:
  - Refer to [`docs/PRODUCTION_CLEANUP_AND_DATA_RESET_RUNBOOK.md`](file:///home/user/Desktop/Projects/management/attendance/docs/PRODUCTION_CLEANUP_AND_DATA_RESET_RUNBOOK.md).
