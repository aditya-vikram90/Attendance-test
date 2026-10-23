# Attendance Portal Documentation Master Blueprint (Final Approved)
## Complete Outlines, Scope, Terminology, Reporting & Role Specifications

| Document Type | Target File Location | Purpose | Primary Target Audience |
| :--- | :--- | :--- | :--- |
| **1. Technical Document** | `docs/TECHNICAL_DOCUMENTATION.md` | Deep-dive architectural, schema, authentication, reporting algorithms, and deployment reference. | Developers, DevOps, System Architects, IT Leads |
| **2. User Guide** | `docs/USER_GUIDE.md` | Operational manual explaining system purpose, problem statement, login, step-by-step role guides, HO remarks, and reporting utility. | Engineers, Tech Leads, Project Managers, Admins |
| **3. Presentation Deck** | `docs/PORTAL_DEMO_PRESENTATION.md` | Slide-by-slide demonstration pitch for stakeholders and management highlighting real-time operations, accountability, and analytics. | Stakeholders, Project Managers, HR/Ops, Engineering Teams |

---

## 🔑 Terminology & Code Glossary (Fully Explained)

### 1. Attendance Status Codes (`entry.status`)
* **`P` — Present**: The engineer attended work and performed regular duties during their scheduled shift (either at Client Site or Head Office).
* **`A` — Absent**: Unplanned or unexcused absence without prior approval or notice.
* **`L` — Leave**: Approved full-day planned leave (Casual, Sick, Earned Leave) pre-approved on email and logged in advance.
* **`HD` — Half Day**: Half-day duty (attended first half or second half of the shift as approved by PM/TL).
* **`W` — Work From Home (WFH)**: Remote duty performed from home or offsite as approved by the PM/TL.
* **`H` — Holiday**: Official company gazetted holiday, festival holiday, or scheduled non-working day.
* **`CO` — Compensatory Off (Comp-Off)**: Time off granted in lieu of working on a weekend or public holiday.

### 2. Operational Metrics & Table Fields
* **`in_time` — In-Time**: Actual check-in timestamp (e.g., `09:45`).
* **`out_time` — Out-Time**: Actual check-out timestamp (e.g., `18:30`).
* **`late_mins` — Late Arrival (Minutes)**: Automatically calculated minutes arrived past the engineer's assigned shift start time.
* **`early_mins` — Early Departure (Minutes)**: Automatically calculated minutes departed before shift completion.
* **`note` / `remarks` — Daily Remarks**: Operational context note (e.g., *"Visited Head Office for internal review / IT setup"*, *"Client on-site deployment"*, *"Left early for medical checkup"*).
* **`cover_id` — Handover / Cover Engineer**: Colleague designated to handle critical operational tasks during an absence or leave.
* **`shift_start` — Shift Start Time**: The designated starting time for the project/engineer (default: `09:30`).

### 3. Architecture & Authentication Acronyms
* **`SSO` — Single Sign-On**: Centralized login across all company tools using one set of credentials.
* **`SLO` — Single Log-Out**: Global session termination across the portal and Keycloak when signing out.
* **`IdP` — Identity Provider**: Keycloak server managing realms, users, credentials, and roles.
* **`OIDC` — OpenID Connect**: OAuth 2.0 identity protocol layer used for authentication.
* **`SSoT` — Single Source of Truth**: Keycloak serves as the sole authoritative repository for user identity and roles.
* **`RBAC` — Role-Based Access Control**: Permissions governed by user roles (`Admin`, `Project Manager`, `Engineer`).
* **`WAL` — Write-Ahead Logging**: Database mode ensuring atomic transactions and fast concurrent reads.

---

## 🏢 Operational Workflow: Client Site vs. Head Office Duty Logging

* **Core Problem Handled**: Most engineers work deployed at client locations. When an engineer visits the Head Office (HO) for internal meetings, reviews, IT hardware maintenance, or training, they remain actively assigned to their project and on duty.
* **Data Logging**:
  * PM/TL marks status as **Present (`P`)**.
  * Logs specific justification in the **`Remarks`** input box (e.g., *"Visited Head Office for internal sprint review / laptop upgrade"*).
* **Multi-View Remarks Surfacing**:
  1. **Personal Dashboard (`/me`)**: Dedicated `Remarks` column displays the recorded location note directly to the engineer.
  2. **Daily & Monthly Summary (`/summary`)**: Displayed under Section 3 (Present members) for PMs and Admins.
  3. **Daily Executive Email Digest (`email.html`)**: Automatically included in the Present members table sent to management.
  4. **Daily Excel Export (`attendance_<date>.xlsx`)**: Recorded on the Summary sheet and every project tab.
  5. **Monthly Excel Export (`attendance_<month>.xlsx`)**: Captured in the `Daily log` audit sheet with exact date, user, status, remarks, and author.
  6. **Trends & Irregularity (`/trends`)**: Day-column click-through navigates to that date's summary showing the full remarks.

---

# 📊 Reporting & Analytics Module Specifications (Summary & Trends)

### 1. Daily & Monthly Summary Portal (`/summary`)
* **Top Executive KPI Cards**: Total Members, Present, Absent (No Info), On Leave, Late, Short of Shift, Not Entered Yet.
* **Categorized Operational Breakdown Tables**:
  * Section 1: Absent - No Information.
  * Section 2: Attendance Not Entered Yet.
  * Section 3: On Leave & Task Handover Breakdown (shows leave type, cover person, and **OpenProject task links**).
  * Section 4: Present Members Roster (In-Time, Out-Time, worked hours, punctuality pill, and **Remarks**).
  * Section 5: Late Arrivals (Late minutes and remarks).
  * Section 6: Shift Shortage Table (Hours in office, short-by duration).
* **Export & Notification Tools**: Daily Excel export, Monthly Excel report, and 1-click email broadcast.

### 2. Trends & Irregularity Analytics Portal (`/trends`)
* **Time Periods**: Last 7, 14, 30, 60, or 90 days.
* **Interactive Stacked SVG Attendance Graph**: Visual stacked bars (On time, Late, On leave, Absent) with hover tooltips and 1-click drill-down to `/summary`.
* **Weekday Lateness Pattern Matrix**: Lateness percentage and counts across Monday through Sunday.
* **Engineer Regularity & Irregularity Scorecard**:
  * Objective rule evaluation: `Irregular` flag, `Direction Trend` (Getting worse, Improving, Steady), late percentages, average arrival deviations.

### 3. Role-by-Role Value of Reports & Analytics

| User Role | Summary & Trends Features Available | Concrete Practical Utility & Business Value |
| :--- | :--- | :--- |
| **Software Engineer** | • Personal summary (`/summary` filtered to self).<br>• Personal trend scorecard & history (`/me`, `/trends`). | • **Payroll & Timesheet Confidence**: Verifies recorded hours, punch times, and Head Office duty remarks against salary expectations.<br>• **Punctuality Self-Audit**: Tracks late arrival occurrences and shift adherence.<br>• **Leave Record Tracking**: Confirms all email-approved leaves are accurately reflected. |
| **Project Manager / Tech Lead (PM/TL)** | • Project-level summary KPIs and drill-down tables.<br>• OpenProject task handover inspection.<br>• Weekday lateness patterns and team irregularity scoring.<br>• 1-Click Daily & Monthly Excel exports. | • **Task Continuity & Risk Mitigation**: Ensures leave-taking engineers have assigned covers for critical client tasks.<br>• **Sprint Capacity Planning**: Adjusts sprint commitments based on true historical attendance rates and upcoming leaves.<br>• **Client Billing & Audit Proof**: Exports clean, timestamped Excel workbooks for client billing reconciliation and Head Office duty justification.<br>• **Early Burnout & Habit Detection**: Identifies chronic late arrivals or sudden shift shortages before projects derail. |
| **System Administrator / Management / HR** | • Organization-wide summary KPIs across all company projects.<br>• Company-wide trend graphs and weekday patterns.<br>• Executive daily email summary broadcasts.<br>• Global monthly Excel exports. | • **Automated Payroll Ingestion**: Provides centralized, validated monthly attendance totals for salary processing.<br>• **Organizational Health & Compliance**: Identifies departments with high unplanned absenteeism or punctuality issues.<br>• **Resource Allocation & Bench Optimization**: Compares attendance and workload across projects to balance underutilized bench resources.<br>• **Executive Oversight**: Fast high-level dashboard and automated email digests without manual consolidation. |

---

# 📚 Document Outlines

### 1. Document 1: `docs/TECHNICAL_DOCUMENTATION.md`
1. System Architecture & Keycloak Single Source of Truth (SSoT).
2. Technology Stack & Infrastructure (Python 3.12, Flask, Gunicorn, Jinja2, Vanilla ES6, SQLite WAL, Podman, Nginx).
3. Authentication & Keycloak Integration (OIDC Confidential Client, SSO, SLO Backchannel/Frontchannel, Profile sync).
4. Role-Based Access Control (RBAC) & Past-Date Locking (`can_edit_attendance`).
5. Database Schema & Data Models (`app_users`, `project`, `team`, `project_access`, `entry`, `advance_leave`, `backchannel_logout_tokens`).
6. Core Business Logic & Algorithms:
   - Advance Leave Pre-Marking (batch insert, weekend skipping, early return clearance).
   - Shift & Lateness Calculation engine (`late_mins`, `early_mins`).
   - Reporting & Analytics Engine (KPI computation, regularity scoring, direction trends, weekday matrices, `openpyxl` Excel generation).
   - Remarks & Operational Notes Lifecycle (Head Office duty logging, audit persistence).
   - Live Debounced Search & Admin Cross-Project Transfers.
7. API & Route Reference (Web endpoints & REST APIs).
8. Deployment, Systemd Operations & Maintenance.

### 2. Document 2: `docs/USER_GUIDE.md`
1. Introduction & Operational Problem Statement.
2. Authentication & Keycloak Enterprise SSO.
3. Software Engineer Guide (`/me`): Personal calendar, shift timings, tracking pre-approved leaves, verifying Head Office remarks.
4. Project Manager / Tech Lead Guide:
   - Daily attendance entry (`/`) with status codes, shift in/out, and notes.
   - Logging Head Office visits (Marking Present + HO remarks).
   - Advance Leave Management modal (logging email-approved multi-day leaves, automatic weekend skipping, rescheduling, early return).
   - Summary & Reporting (`/summary`): KPIs, OpenProject task covers, daily/monthly Excel exports for client billing.
   - Trends & Team Regularity (`/trends`): Analyzing team attendance patterns and irregularity flags.
5. System Administrator Guide:
   - Live user directory search, Bench Pool allocation, and 1-Click Cross-Project Transfers.
   - Company-wide summary, trends, and executive email broadcasts.
   - Historical date overrides and project configuration.
6. FAQ & Operational Best Practices.

### 3. Document 3: `docs/PORTAL_DEMO_PRESENTATION.md`
* Slide 1: Title & Vision.
* Slide 2: The Challenge (Spreadsheets, manual leave entries, bench visibility gaps, client vs. HO tracking).
* Slide 3: The Solution Overview (Keycloak SSO, real-time tracking, advance leave automation).
* Slide 4: Architectural Highlights (Single Source of Truth, high-speed lightweight UI, granular RBAC).
* Slide 5: Daily Attendance & Shift Tracking (Fast project tabs, in/out timestamps, late flags, HO remarks).
* Slide 6: Advance Leave Pre-Marking (1-click entry for email-approved leaves, auto-marking future dates, weekend skipping).
* Slide 7: Team Mobility & Bench Allocation (Live debounced directory search, 1-click cross-project transfers).
* Slide 8: Real-Time Summary & Audit Reports (`/summary` - KPIs, task covers, Excel exports for client billing).
* Slide 9: Visual Trends & Regularity Analytics (`/trends` - interactive charts, weekday matrices, irregularity scoring).
* Slide 10: Realistic Live Demo Flow (PM daily entry & HO remark $\rightarrow$ PM advance leave entry $\rightarrow$ Summary/Trends review & Excel export $\rightarrow$ Admin team transfer $\rightarrow$ Engineer `/me` verification).
* Slide 11: Business Impact & ROI (90% admin reduction, zero missed leaves, full audit compliance).
* Slide 12: Summary & Q&A.
