# Attendance Management System: Comprehensive Audit & Integrity Report

**Generated Date**: October 14, 2026  
**Target Application**: Attendance Management Service (`attendance-service`)  
**Scope**: Full RBAC security scan, cross-screen data reconciliation, and newly created user lifecycle audit.

---

## 1. Executive Summary

A comprehensive system-wide audit was conducted across all user roles (**Engineer**, **Team Lead / PM**, **Manager**, **Admin**) and all functional views (**Entry**, **Summary**, **Trends**, **History**, **My Attendance**, **Exports**, and **Email**).

* **Role-Based Access Control (RBAC)**: **Verified & Secure**. Route-level guards strictly isolate roles. Engineers cannot tamper with attendance or view other projects; Leads are restricted strictly to their assigned projects; Admins maintain global oversight.
* **Newly Created / Bench User Bug**: The root cause of newly created users showing false "Absent" records on Trends and Summary was analyzed. While already resolved for `/me`, `/summary`, and `/trends`, our audit revealed **two remaining places** where newly created engineers still show as absent for past dates.
* **Cross-Screen Parity**: Discovered gaps in the Daily Excel export and Daily Email template where the newly introduced "Present members" section is currently omitted.

---

## 2. Issues Previously Resolved & Verified

The following table documents all issues addressed, implemented, and verified in production:

| Issue | Description | Solution Implemented | Verification Status |
| :--- | :--- | :--- | :--- |
| **Keycloak SSO Signout** | Users clicking signout were not logged out of Keycloak SSO session. | Integrated OpenID Connect RP-Initiated Logout with `id_token_hint`, `post_logout_redirect_uri`, and confirmation landing page. | ✅ Verified Live |
| **Arrival Trend Chart** | "Arrival trend: average minutes after own shift start" cluttered the page. | Cleanly commented out in Jinja template while preserving backend geometry if needed later. | ✅ Verified Live |
| **Engineer Personal Trends & Summary** | Engineers had no visibility into their monthly summary or 30-day attendance patterns. | Allowed engineers access to `/trends` and `/summary`, strictly scoped to their own ID; added "My trends" and "My summary" navigation links. | ✅ Verified Live |
| **Lead / PM User-wise Filter** | Leads/Admins could not filter trends or summary by a specific engineer. | Added an **Engineer** dropdown filter in both `/summary` and `/trends` alongside the Project filter. | ✅ Verified Live |
| **Trends Bar Hover Tooltip** | Hovering on thin SVG bars had a 1-2s delay and missed full-column hover. | Implemented full-column hover zones (`<rect class="chart-col">`) and an instant, floating `#chart-tooltip` box. | ✅ Verified Live |
| **Trends Bar Drill-Down** | Users could not see who was present/on leave for a specific day from the Trends bar. | Configured clickable chart columns with `data-url` that directly navigate to `/summary?date=YYYY-MM-DD` upon click. | ✅ Verified Live |
| **Present Members on Summary** | Summary page lacked a list of members present for the day. | Added dedicated green section **"3. Present members (X)"** with shift start, in/out times, hours in office, status, and remarks. | ✅ Verified Live |
| **Newly Created Users False Absent (Summary & Trends)** | Newly added users were penalized with "Absent (No info)" for dates before they joined. | Added `is_assigned_on(assignments, day)` checks in `build_summary()` and `trends()`, eliminating false absents for past dates. | ✅ Verified Live |

---

## 3. Screen-by-Screen Audit Matrix

We scanned every view in the application to check for data integrity and false "Absent" records for newly created users:

| Screen / Feature | Route / Endpoint | Handles Past Dates for New Users? | Current Status | Notes |
| :--- | :--- | :---: | :---: | :--- |
| **My Attendance** | `/me` | ✅ **YES** | **Clean** | Displays `"Unassigned / Bench"` for dates before `assigned_from`. |
| **Daily Summary** | `/summary` | ✅ **YES** | **Clean** | `build_summary()` skips unassigned engineers on that date. |
| **Trends Chart & Table** | `/trends` | ✅ **YES** | **Clean** | Daily bar and Regularity table skip unassigned dates. |
| **Monthly History** | `/history` | ✅ **YES** | **Clean** | `month_matrix()` outputs `"-"` (white unassigned cell) rather than `"A"`. |
| **Monthly Excel** | `/export/monthly.xlsx` | ✅ **YES** | **Clean** | Reuses `month_matrix()` with proper `"-"` cells. |
| **Attendance Entry** | `/` | ❌ **NO** | **ACTION REQUIRED** | `members(pid)` returns all active members without checking `is_assigned_on(day)`. For past dates, newly created members appear with **"Absent (No info)"**. |
| **Daily Excel Export** | `/export/daily.xlsx` | ❌ **NO** | **ACTION REQUIRED** | Per-project tabs list newly created users as **"Absent (No info)"** on past dates; also lacks the "Present members" section. |
| **Daily Summary Email** | `templates/email.html` | N/A | **ACTION REQUIRED** | Lacks the **"Present members"** table that was added to the web Summary. |

---

## 4. Role-Based Access Control (RBAC) Audit

We inspected all `@app.route` handlers and permission checks:

```
[Incoming Request]
        │
        ▼
 ┌───────────────┐
 │ login_required │
 └───────┬───────┘
         │
         ├──> Role == "engineer"?
         │         ├─ Requesting /me, /trends, /summary ──> ALLOW (Locked to own member_id)
         │         └─ Requesting ANY other route ─────────> REDIRECT to /me
         │
         ├──> Role == "lead" (TL/PM)?
         │         ├─ Accessing their own project ────────> ALLOW (can_edit=True)
         │         ├─ Accessing another project ──────────> 403 Forbidden / 404
         │         └─ Accessing /access or /summary/send ─> 403 Forbidden
         │
         ├──> Role == "manager"?
         │         ├─ Viewing watched/all projects ───────> ALLOW (Read-only, can_edit=False)
         │         └─ Submitting attendance /save ────────> 403 Forbidden
         │
         └──> Role == "admin"?
                   └─ Full administrative access across all endpoints.
```

---

## 5. Database & Entity Lifecycle Audit

### Tables Inspected:
* `team` (Postgres / SQLite): Stores project member assignments with `(project_id, member_id)`.
* `app_users`: Central user registry with unique `id`, `email`, `role_title`, and `current_project_id`.
* `attendance`: Primary key `(day, user_id)`. Stores daily attendance punches.
* `access` & `project_access`: Role and project ownership tables.

### Lifecycle Findings:
1. **Single Project Rule**: The business rule *"An engineer can only belong to one active project"* is enforced in `team_assign_bench` and `team_update`.
2. **Missing `assigned_to` on Transfer / Removal**:
   * When an engineer is removed (`action="remove"`) or transferred (`/admin/transfer_engineer`), `team.active` is set to `0`, but `assigned_to` is left as `NULL`.
   * **Recommendation**: Set `assigned_to = CURRENT_TIMESTAMP` when deactivating a project assignment, and ensure `assigned_from = CURRENT_TIMESTAMP, assigned_to = NULL` when activating a new project assignment.
3. **Multi-Project ID Aggregation for Engineers**:
   * When an engineer has been in more than one project across their history, they have multiple `member_id`s in `team`.
   * `my_member_ids()` returns all of them (`['102', 'm:b879...']`), but `/trends` and `/summary` currently selected only `mids[0]`.
   * **Recommendation**: Allow evaluating across all member IDs belonging to the logged-in engineer.

---

## 6. Action Plan for Remaining Fixes

Upon user approval, the following remaining items will be resolved:

1. **Fix 1: Attendance Entry Screen (`/`)**:
   * Filter `members(pid)` by `is_assigned_on([{"from": m["assigned_from"], "to": m["assigned_to"]}], day)` so that newly created engineers do not appear on past dates with false "Absent" pills.
2. **Fix 2: Daily Excel Export (`/export/daily.xlsx`)**:
   * Apply `is_assigned_on` filtering to the per-project tabs so past dates do not list unassigned engineers as absent.
   * Add the **"Present members"** section to the summary tab of the daily Excel spreadsheet.
3. **Fix 3: Daily Summary Email (`email.html`)**:
   * Add the **"Present members"** section to the HTML email template to ensure 100% parity with `/summary`.
4. **Fix 4: Lifecycle Timestamps (`assigned_to`)**:
   * Set `assigned_to = CURRENT_TIMESTAMP` upon engineer removal and project transfer.
5. **Fix 5: Engineer Multi-ID Trends & Summary**:
   * Ensure `/trends` and `/summary` evaluate all `member_id`s for the logged-in engineer so their full cross-project journey is visible.
