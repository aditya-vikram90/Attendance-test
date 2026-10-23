# Attendance Management Portal
## Demonstration Presentation Deck (Slide-by-Slide Script)

| Presentation Metadata | Details |
| :--- | :--- |
| **Interactive HTML Deck** | [`docs/PORTAL_DEMO_PRESENTATION.html`](./PORTAL_DEMO_PRESENTATION.html) |
| **Format** | Responsive Interactive HTML (with Light/Dark Mode) + Markdown Slide Deck |
| **Target Audience** | Stakeholders, Project Managers, Engineering Leads, HR & Operations |
| **System URL** | `https://pm.keenable.io/attendance/` |

---

### Slide 1: Portal Overview & Purpose
* **Title**: Attendance Management Portal
* **Subtitle**: One central place to manage team assignments, mark daily shift attendance, and download reports.
* **Why We Built It**:
  Engineers work across multiple projects and client sites. Management previously had no single, reliable view of who is absent without information, who is on leave and covering their tasks, who arrived late, and who is not completing the 9-hour shift. Attendance was trapped in separate per-project spreadsheets with zero history and no trend analysis.
  The portal provides one daily operational record for every project team, filled by the TL/PM with automated validation, an executive daily summary for management, and long-term trend analysis.
* **Core Pillars**:
  1. **Central User Directory**: Loads employees automatically from company Keycloak SSO. Search anyone easily and move engineers between projects in 1 click.
  2. **Daily Shifts & Leaves**: Mark project attendance quickly, track exact check-in and check-out times, track WFH and half-days, and pre-fill approved multi-day leaves automatically.
  3. **Reports, Trends & Excel Downloads**: See daily summaries, review attendance trends (7 to 365 days or custom dates) with instant engineer search, and export formatted Excel sheets in 1 click.

---

### Slide 2: Why We Built This (Problem Statement & Scope)
* **Title**: Common Problems in Team Attendance
* **Subtitle**: Managing teams across multiple projects using spreadsheets creates confusion and wasted time.
* **Pain Points**:
  1. **No Proper Tracking of Check-In & Check-Out Times**: Engineers check in and out at different times without accurate time records. Without timestamps, project leads cannot track punctuality, late arrivals, or total hours worked properly.
  2. **Scattered Spreadsheets & Hidden Bench Pool**: Project leads kept isolated files. Management could not easily see available bench engineers for new project staffing.
  3. **Repeating the Same Leave Entry Every Day**: When an engineer took an approved 5-day leave, the manager had to open the sheet and type "Leave" every single morning.
  4. **Missing Long-Term Attendance Trends**: Management had no simple way to spot repeated late arrivals or compare team punctuality over months or weekdays.
  5. **Confusion Over Client Site vs. Head Office Duty**: When engineers visited the Head Office for sprint reviews or IT setups, no clear note was recorded, creating confusion in timesheets.

---

### Slide 3: Loading Users from Keycloak & Assigning Projects
* **Page URL**: [`https://pm.keenable.io/attendance/team`](https://pm.keenable.io/attendance/team)
* **Title**: Loading Users from Keycloak & Assigning Projects
* **Subtitle**: Centralized login via Keycloak SSO, live directory search, and moving engineers between teams in 1 click.
* **Features**:
  * **Automatic Keycloak User Sync**: Users log in with their regular company Keycloak credentials.
  * **Fast Live Name & Email Search**: Type any part of a name or email to immediately find available bench engineers or project members.
  * **1-Click Project Reallocation**: Transfer an engineer to any project (UPSC, NCLT, Shiksha, NSP) with custom shift start times while preserving their full historical records.
* **Sample Team Table**:
  * *Mohd Imran* (Software Engineer) | Bench Pool -> **Assign to Team** (`UPSC`, `09:30`).
  * *Priya Sharma* (Frontend Engineer) | NCLT -> **Transfer & Reassign** (`UPSC`, `10:00`).
  * *Vikram Singh* (DevOps Engineer) | Bench Pool -> **Assign to Team** (`Shiksha`, `09:30`).
  * *Arun Kumar* (Tech Lead) | UPSC -> **Update Shift / Role** (`NSP`, `09:30`).

---

### Slide 4: Daily Project Attendance & Shift Operations
* **Page URL**: [`https://pm.keenable.io/attendance/`](https://pm.keenable.io/attendance/)
* **Title**: Daily Project Attendance & Shift Operations
* **Subtitle**: Simple daily grid for project leads to mark check-ins, check-outs, lateness, leaves, and handovers.
* **Features**:
  * **Project Tabs**: Switch between project tabs (UPSC, NCLT, Shiksha, NSP).
  * **Status Codes**: Present (`P`), Late (`LT`), Leave (`L`), Half Day (`HD`), Work From Home (`W`), Absent (`A`).
  * **Dedicated Late Column**: Shows exact late minutes computed against shift start (`09:30 + 15m grace`).
  * **Shift Validation**: Night shifts ending next morning, 9-hour shortfall flags, and preventing someone on leave from being selected as task cover.
* **Sample Daily Table**:
  * **Arun Kumar** (Lead) | `09:30` | **Present** | `09:25` | `18:35` | **—** | Cover: — | *Client site deployment*
  * **Mohd Imran** | `09:30` | **Present** | `09:55` | `18:30` | **+25m** | Cover: — | *Metro transit delay*
  * **Priya Sharma** | `10:00` | **Leave** | — | — | **—** | Cover: Vikram Singh | *Advance Casual Leave (Approved on email)*
  * **Vikram Singh** | `09:30` | **Present** | `09:20` | `18:40` | **—** | Cover: — | *Visited Head Office for internal review*
  * **Neha Verma** | `09:30` | **WFH** | `09:30` | `18:30` | **—** | Cover: — | *Approved remote duty (Sprint coding)*
  * **Suresh Patel** | `09:30` | **Half Day** | `09:30` | `14:00` | **—** | Cover: Arun Kumar | *First-half shift · Personal appointment*
  * **Amit Roy** | `09:30` | **Leave** | — | — | **—** | Cover: Mohd Imran | *Advance Sick Leave · Day 2 of 3*

---

### Slide 5: Daily Summary & Excel Downloads
* **Page URL**: [`https://pm.keenable.io/attendance/summary`](https://pm.keenable.io/attendance/summary)
* **Title**: Daily Summary & Excel Downloads
* **Subtitle**: Instant daily numbers, task handover verification, and 1-click Excel sheets ready for management review.
* **Summary Cards**: Total Members (28), Present Today (22), On Leave / WFH (5), Late Arrivals (2).
* **Highlights**:
  * **Absent without info**: Unplanned absences highlighted in red for follow-up.
  * **On Leave & Handover**: Shows task cover colleague and linked OpenProject tickets.
  * **Present Members Table**: Full list with arrival, departure, late time, and location remarks.
  * **1-Click Excel Downloads**: Instant daily `.xlsx` or full monthly project workbook with totals and logs.
  * **Automated Management Email**: Dispatches structured briefing email directly to management.

---

### Slide 6: Attendance Trends: 7 to 365 Days, Custom Dates & User Search
* **Page URL**: [`https://pm.keenable.io/attendance/trends`](https://pm.keenable.io/attendance/trends)
* **Title**: Attendance Trends: 7 to 365 Days, Custom Dates & Search
* **Subtitle**: Interactive graphs, weekday lateness patterns, scorecards, and instant engineer search.
* **Capabilities**:
  * **Extended Time Ranges**: Filter by **7, 14, 30, 60, 90, 180 days (6 months), 365 days (1 year)**, or choose any **Custom Date Range**.
  * **Real-Time Searchable Engineer Combobox**: Instant autofocus search bar (`🔍 Search name or role...`) with real-time filtering, keyboard navigation (`Enter`/`Esc`), and 1-click clear.
  * **Weekday Pattern Matrix**: Discovers which days of the week have the highest late arrivals (e.g. *Monday 38% late* vs *Friday 4% late*).
  * **Engineer Regularity Scorecard**: Identifies regular vs. irregular attendance and shows if punctuality is *Improving*, *Steady*, or *Getting worse*.

---

### Slide 7: Pre-Marking Approved Leaves in Advance
* **Modal Reference**: `Advance Leave Modal on https://pm.keenable.io/attendance/`
* **Title**: Pre-Marking Approved Leaves in Advance
* **Subtitle**: Enter pre-approved email leaves once; future dates are automatically marked while skipping weekends.
* **Workflow**:
  1. **One-Time Setup**: Enter date range (e.g. Oct 20 to Oct 24), leave type, and cover colleague.
  2. **Skips Weekends Automatically**: Saturdays and Sundays are skipped automatically; only weekdays are marked as Leave (`L`).
  3. **Easy Early Return**: If the employee returns early, simply mark today as Present; future leave days remain saved.

---

### Slide 8: Client Site vs. Head Office Duty Remarks
* **Page URL**: [`https://pm.keenable.io/attendance/summary`](https://pm.keenable.io/attendance/summary)
* **Title**: Client Site vs. Head Office Duty Remarks
* **Subtitle**: Recording off-site work locations clearly so internal project timesheets remain 100% accurate.
* **How It Works**:
  * Mark status as **Present (`P`)** with in/out timestamps.
  * Add the reason in **Remarks** (*"Visited Head Office for internal sprint review / IT hardware setup"*).
  * Surfaced in `/me`, `/summary`, daily email broadcasts, and monthly Excel workbooks.

---

### Slide 9: My Attendance: Self-Service Employee View
* **Page URL**: [`https://pm.keenable.io/attendance/me`](https://pm.keenable.io/attendance/me)
* **Title**: My Attendance: Self-Service Employee View
* **Subtitle**: A clear monthly calendar where engineers can check their daily punch times, shifts, and leaves.
* **Employee Actions**:
  * Review personal punch times and total worked hours.
  * Verify assigned shift start time and grace rules.
  * Confirm pre-approved leaves and location remarks.

---

### Slide 10: Infrastructure Architecture & Dual-App Topology
* **Title**: Infrastructure Architecture & Dual-App Topology
* **Subtitle**: One domain, one sign-in, separate application stacks behind a unified TLS reverse proxy.
* **Architecture Diagram**:
  ```text
  [ User Browser ]
         │
         ▼ (HTTPS)
  [ Nginx Reverse Proxy (pm.keenable.io, TLS) ]
         │
         ├───► Route "/" ───────────► [ OpenProject (Podman) ] ───► [ PostgreSQL DB ]
         │                                    ▲
         │                                    │ (Read-only API for Open Tasks)
         │                                    ▼
         └───► Route "/attendance" ──► [ Attendance Portal (Flask) ] ─► [ SQLite DB (WAL) ]
                                              │
                      ┌───────────────────────┴───────────────────────┐
                      ▼                                               ▼
         [ Keycloak SSO (OIDC + SLO) ]                   [ Shared SMTP Relay ]
  ```
* **Key Architecture Pillars**:
  1. **Unified Host Domain**: Both applications run on `pm.keenable.io` under TLS.
  2. **Single Sign-On & Single Sign-Out (SLO)**: Keycloak OIDC handles authentication; logging out in either app immediately terminates the session across both applications.
  3. **OpenProject Task Integration**: Attendance portal reads open tasks via read-only API to audit task handovers when an engineer is on leave.
  4. **Dedicated Data Stores**: OpenProject runs on PostgreSQL; Attendance Portal uses SQLite with Write-Ahead Logging (WAL) for fast, zero-maintenance, lock-free concurrency.

---

### Slide 11: Technology Stack & Security Architecture
* **Title**: Technology Stack & Security Architecture
* **Subtitle**: Small stack, strict security controls, and enterprise-grade role-based access.
* **Technology Matrix**:
  * **Application Engine**: Python 3.12, Flask, Gunicorn WSGI (`--threads 8`)
  * **Pages & Visualizations**: Server-rendered Jinja2 templates with inline SVG dynamic charts
  * **Identity & Authentication**: Keycloak OpenID Connect (`Authlib`), OIDC Authorization Code Flow
  * **Data Storage & Reports**: SQLite 3 (WAL mode) / PostgreSQL + `openpyxl` for Excel generation
* **Security & Governance Controls**:
  * **No Credentials Stored**: Portal stores zero passwords; authentication is completely delegated to Keycloak.
  * **Dynamic 5-Minute Role Re-Verification**: Roles are re-checked against Keycloak every 5 minutes. If a role is revoked or an account is disabled in Keycloak, access is terminated within 5 minutes.
  * **Role-Based Access Control (RBAC)**:
    * *Admin*: Full control over all projects, teams, settings, and user allocations.
    * *Lead / PM*: Attendance entry, leave modal, and summaries for their assigned projects only.
    * *Engineer*: Self-service view (`/me`) restricted exclusively to their personal records.
  * **Web Protection**: CSRF tokens on every form, HTTPS-only secure cookies, and strict input sanitization.
  * **Rules as Settings**: Shift start (default 09:30), 15-minute grace period, 9-hour shift length, and weekly offs are configurable database settings, not hardcoded.

---

### Slide 12: Production Delivery Status & Roadmap
* **Title**: Production Delivery Status & Roadmap
* **Subtitle**: Comprehensive inventory of live production capabilities and upcoming enhancements.
* **Delivery Status Matrix**:

| Feature / Capability | Status | Implementation Details |
| :--- | :---: | :--- |
| **Projects, Teams & Daily Entry** | **LIVE** | Live on `pm.keenable.io/attendance/` with multi-project tabs and in/out logging. |
| **Keycloak SSO & 5-Min Role Re-Check** | **LIVE** | Complete OIDC integration with back-channel Single Sign-Out (SLO). |
| **Keycloak User Directory & Bench Pool** | **LIVE** | Live directory search on `/team`, bench pool management, and 1-click reassignment. |
| **Advance Leave Modal (Skip Weekends)** | **LIVE** | Multi-day leave entry with automatic weekend skipping and cover validation. |
| **WFH & Half-Day Status Tracking** | **LIVE** | Dedicated status codes (`W` and `HD`) with timestamp records. |
| **Extended Trends (7–365 Days & Custom)** | **LIVE** | 7, 14, 30, 60, 90, 180, 365 days, custom date range, and weekday lateness pattern. |
| **Searchable Engineer Dropdown** | **LIVE** | Instant real-time search combobox on `/trends` and `/summary` with keyboard nav. |
| **Excel Downloads & Daily Email Broadcast** | **LIVE** | Single-day and monthly Excel workbooks + automated management briefing email. |
| **Audit-Lock Past Dates for TL/PM** | **NEXT** | Freeze past attendance dates for leads; modifications require admin audit override. |
| **PostgreSQL Dedicated Database Migration** | **NEXT** | Transition attendance tables to dedicated PostgreSQL server (`DATABASE_URL`). |
| **Push Reminders & Cutoff Notifications** | **NEXT** | Automated alerts for project leads prior to the daily 11:00 AM attendance cutoff. |

---

### Slide 13: Step-by-Step Live Demonstration Walkthrough
* **Title**: Step-by-Step Live Demonstration Walkthrough
* **Subtitle**: A realistic end-to-end walkthrough showing how all roles use the portal in practice.
* **Demonstration Steps**:
  1. **Admin ([`/team`](https://pm.keenable.io/attendance/team))**: Searches Keycloak directory, finds an engineer in the Bench Pool, and assigns them to the UPSC project with a 09:30 shift start.
  2. **PM ([`/`](https://pm.keenable.io/attendance/))**: Opens UPSC tab, logs daily attendance with in/out timestamps, observes automated late minutes computation, and enters a Head Office note in Remarks.
  3. **PM (Advance Leave Modal)**: Opens leave modal, enters an approved 4-day leave; future weekdays are pre-filled automatically while weekends are skipped.
  4. **PM / Admin ([`/summary`](https://pm.keenable.io/attendance/summary) & [`/trends`](https://pm.keenable.io/attendance/trends))**: Audits the daily executive summary, opens trends to inspect 180-day patterns, uses the instant engineer search bar, and downloads the monthly Excel workbook.
  5. **Engineer ([`/me`](https://pm.keenable.io/attendance/me))**: Logs in with company Keycloak credentials to verify personal attendance records, shift timings, and duty remarks.
