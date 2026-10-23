# Attendance & Workforce Management System
## Manual Tester Application Guide & UI Reference Manual

---

### Document Overview
- **Document Title:** Attendance System &mdash; Manual Tester Application Guide & UI Walkthrough
- **Target Audience:** QA Engineers, Manual Testers, Test Leads, Product Analysts
- **Scope:** Complete screen-by-screen, button-by-button, and modal-by-modal UI functionality reference.
- **Universal Test Password:** `Keenable@2026` (Pre-configured for all test accounts)
- **Local Application URL:** `http://localhost:8000`
- **Production / Staging URL:** `https://pm.keenable.io/attendance/`

---

## 1. Quick Start: Verified Test Credentials Directory

Log in via the `/login` endpoint using any of the accounts below. All accounts share the exact same password: **`Keenable@2026`**.

| Role Level | User Full Name | Username / Email | Password | UI Landing Page & Navigation Privileges |
| :--- | :--- | :--- | :--- | :--- |
| **Admin** | Ashish Sharma | `ashish.kumar1@fosteringlinux.com` | `Keenable@2026` | Lands on `/`. Full access to all 12 navigation links, including **Access**, **Project Setup**, past-date unlocking, and cross-project transfers. |
| **PM Level 0 (Lead)** | Moumita Roy | `moumita.roy@fosteringlinux.com` | `Keenable@2026` | Lands on `/`. Primary Lead for Project 2 (UPSC). First-line approver for daily entries, leaves, and objections. |
| **PM Level 1 (Manager)** | Mohd Imran | `imran.mohd@fosteringlinux.com` | `Keenable@2026` | Lands on `/`. Deputy Lead 1. Receives leave approvals when team capacity is breached or when PM0 is away. |
| **PM Level 2 (Senior PM)**| Anjali Mehta | `anjali.mehta@fosteringlinux.com` | `Keenable@2026` | Lands on `/`. Deputy Lead 2. Second-tier escalation for SLA breaches. |
| **PM Level 3 (Head)** | Amit Roy | `amit.roy@fosteringlinux.com` | `Keenable@2026` | Lands on `/`. Deputy Lead 3 / Delivery Head. Top project escalation level. |
| **Engineer 1** | Neha Verma | `neha.verma@fosteringlinux.com` | `Keenable@2026` | Lands directly on `/me` (**My attendance**). Restricted to personal attendance, trends, and summary. |
| **Engineer 2** | Pooja Nair | `pooja.nair@fosteringlinux.com` | `Keenable@2026` | Lands directly on `/me`. Security & Compliance Analyst on Project 2. |
| **Engineer 3** | Rohit Gupta | `rohit.gupta@fosteringlinux.com` | `Keenable@2026` | Lands directly on `/me`. Full Stack Developer on Project 2. |
| **Engineer 4** | Manoj Tiwari | `manoj.tiwari@fosteringlinux.com` | `Keenable@2026` | Lands directly on `/me`. Backend Engineer on Project 2. |
| **Engineer 5** | Priya Sharma | `priya.sharma@fosteringlinux.com` | `Keenable@2026` | Lands directly on `/me`. Frontend Developer on Project 2. |
| **Engineer 6** | Vikram Singh | `vikram.singh@fosteringlinux.com` | `Keenable@2026` | Lands directly on `/me`. DevOps Engineer on Project 2. |

---

## 2. Global Header & Dynamic Navigation Bar

The top navigation header (`<header>`) changes dynamically based on the logged-in user's role:

```
[Attendance Logo]  [Enter attendance]  [Summary]  [Trends]  [History]  [Phone check-ins]  [Approvals 1]  [Leaves]  [Project setup]  [My team]  [Projects]  [Access]  [My attendance]    [User Name · Role]  [Sign out]
```

### 2.1 Navigation Visibility by Persona
1. **Admin (`ashish.kumar1@fosteringlinux.com`):**
   - Displays all 12 navigation links: `Enter attendance`, `Summary`, `Trends`, `History`, `Phone check-ins`, `Approvals`, `Leaves`, `Project setup`, `My team`, `Projects`, `Access`, and `My attendance`.
   - Right side: Displays `Ashish Sharma · Admin` and `Sign out`.
2. **Project Manager / Team Lead (`moumita.roy`, `imran.mohd`, etc.):**
   - Displays 11 navigation links: Everything except **Access** (which is strictly Admin-only).
   - Right side: Displays `[Name] · TL/PM` and `Sign out`.
   - Displays red pending badge counter on `Approvals [X]` and `Leaves [Y]` when actionable items await their decision.
3. **Engineer (`neha.verma`, `pooja.nair`, etc.):**
   - Streamlined 3-link navbar: `My attendance`, `My trends`, `My summary`.
   - Right side: Displays `[Name] · Engineer` and `Sign out`.
   - Direct access to managerial routes (e.g. typing `/approvals` or `/project/setup` into the URL) is strictly intercepted with **HTTP 403 Forbidden**.

### 2.2 Global Flash Notifications
Whenever an action succeeds or fails, an alert banner renders at the top of the content area:
- **Success (`.flash.ok`):** Light green background (`#e2efda`), e.g. *"Attendance saved."*, *"Leave approved."*, *"Objection accepted."*
- **Error (`.flash.err`):** Light red background (`#fde3e0`), e.g. *"Past days can be changed by an admin only."*, *"Give a reason for the engineer."*

---

## 3. Screen-by-Screen UI Functionality Walkthrough

---

### Screen 1: Enter Attendance (`/`)
*Primary workspace for PMs and Admins to view, mark, and verify daily team attendance.*

```
+--------------------------------------------------------------------------------------------------------------------+
| Date: [ 2026-10-21 ]   Default shift starts 09:30 · grace 15 min · shift 9 h incl. lunch                           |
+--------------------------------------------------------------------------------------------------------------------+
| [ NCLT ]  [[ UPSC (2) ]]  [ NSP ]  [ Shiksha ]  [ Keenable ]                                                       |
+--------------------------------------------------------------------------------------------------------------------+
| ⏳ 2 Engineer Self-Entries Pending Approval                                     [ ✓ Approve All Submitted (2) ]    |
+--------------------------------------------------------------------------------------------------------------------+
| Team member  | Status  | Approval  | In    | Out   | Hours | Late  | Short | Leave Type | Planned? | Task Handled By | Remarks |
| Neha Verma   | Present | ✓ PM/TL   | 09:30 | 18:30 | 9.0h  | -     | -     | -          | -        | -               | Normal  |
| Pooja Nair   | Leave   | ✓ Verified| -     | -     | 0.0h  | -     | -     | PL         | Planned  | Rohit Gupta     | Wedding |
+--------------------------------------------------------------------------------------------------------------------+
| [ Save UPSC ]                                                                                                      |
+--------------------------------------------------------------------------------------------------------------------+
```

#### Visual Elements & Controls
1. **Date Picker (`Date <input type="date">`):**
   - Defaults to `today`. Changing this date automatically triggers a form submit to reload the table for the selected date.
2. **Project Tabs:**
   - Tabs along the top allow switching between projects.
   - Shows amber badge counter `[ X ]` on project tabs that have pending engineer submissions.
3. **Shift Policy Information Banner:**
   - Displays: *"Default shift starts [time] (an engineer's own shift is shown under the name) · grace [grace] min · shift [hours] h incl. lunch"*.
4. **Pending Self-Entries Alert Banner:**
   - Appears when engineers have submitted attendance waiting for PM approval.
   - Includes quick action button: `✓ Approve All Submitted (X)` &mdash; one-click approval of all pending rows.
5. **Past-Date Lock Banner (Crucial Testing Feature):**
   - When a PM views a date earlier than `today` (`date < today`), a bright red warning banner renders:
     `🔒 Attendance Locked: Previous dates are locked for Team Leads / PMs. Only an administrator can enter or modify attendance for past dates.`
   - In this state, all input fields (`In`, `Out`, `Leave type`, `Planned`, `Remarks`) are rendered **disabled (read-only)** for PMs!
   - When logged in as **Admin (`ashish.kumar1`)**, this lock banner does not appear, and all inputs remain fully editable on past dates.
6. **Roster Table Columns:**
   - **Team member:** Name in bold. Shows `PM / Lead` badge for managers; role title, contact phone number, and custom shift start time.
   - **Status Pill:** Visual colored badge:
     - `Present` (Green `#548235`)
     - `Absent (No info)` (Red `#c00000`)
     - `Leave` (Blue `#2e75b6`)
     - `Weekly Off` (Grey)
   - **Approval Column:**
     - `Pending` (Amber badge) with inline action buttons: `✓ Approve` (green button) and `✕ Reject` (white button with red border).
     - Clicking `✕ Reject` opens the **Reject Attendance Modal** requiring a written reason.
     - `✓ Verified`: Green text for approved self-entries.
     - `✓ PM/TL`: Grey text for entries entered directly by manager.
   - **In / Out Inputs (`<input type="time">`):** Allows typing military format `HH:MM`.
   - **Hours / Late by / Short by:**
     - `Hours`: Computed worked time (e.g. `9:00`, `8:30`). Handles night shifts across midnight.
     - `Late by`: Orange warning text if arrival is after shift start + grace period.
     - `Short by`: Orange warning text if worked hours fall below required shift hours.
   - **Leave type Dropdown:** Select from `CL`, `PL`, `SL`, `Comp-off`, `Maternity/Paternity`, `Unpaid/LWP`.
   - **Planned? Dropdown:** Select `Planned` or `Unplanned`.
   - **Task handled by Dropdown (Smart Conflict Resolution):**
     - Lists all active project colleagues.
     - **Dynamic Behavior:** If a colleague is marked on leave on this same day, JavaScript dynamically appends `(on leave)` to their name and disables selecting them!
   - **Remarks Input (`<input type="text">`):** Free-text field up to 300 characters.
7. **Bottom Action Button:**
   - Blue button: `Save [Project Name]`. Saves all rows.

---

### Screen 2: My Attendance & Engineer Self-Service Portal (`/me`)
*Home dashboard for Engineers to track their monthly attendance, raise disputes, apply for leaves, and monitor real-time approval status.*

```
+--------------------------------------------------------------------------------------------------------------------+
| Neha Verma                                                Your shift starts 09:30 · grace 15 min · shift 9 h lunch |
| UI/UX & Frontend Engineer · UPSC                                                                                   |
+--------------------------------------------------------------------------------------------------------------------+
| ▼ Raise an Attendance Objection / Grievance                                                        [ 1 logged ]    |
|   Date: [ 2026-10-18 ]   Correct IN: [ 09:30 ]   Correct OUT: [ 18:30 ]   Reason: [ Biometric sensor failed ]      |
|   [ Raise Objection ]                                                                                              |
+--------------------------------------------------------------------------------------------------------------------+
| ▼ Apply for Leave                                                                                 [ 2 requests ]   |
|   From: [ 2026-10-26 ]  To: [ 2026-10-27 ]  Type: [ PL v ]  Cover: [ Rohit Gupta v ]  Reason: [ Family wedding ]   |
|   [ Apply for Leave ]                                                                                              |
+--------------------------------------------------------------------------------------------------------------------+
| Month: [ October 2026 v ]                                                                                          |
| [ Present: 18 ]  [ Leave: 2 ]  [ Absent: 0 ]  [ Weekly Off: 6 ]  [ Late: 1 ]  [ Total Hours: 162.0h ]              |
+--------------------------------------------------------------------------------------------------------------------+
| Date         | Project | Status  | Approval | In    | Out   | Hours | Late  | Short | Leave | Handled By  | Remarks    |
| 2026-10-21 W | UPSC    | Present | Approved | 09:28 | 18:32 | 9.0h  | -     | -     | -     | -           | On time    |
+--------------------------------------------------------------------------------------------------------------------+
```

#### Accordion Section 1: Raise an Attendance Objection / Grievance
- **Accordion Toggle:** Clicking the summary bar smoothly expands or collapses the section. Shows badge with count of logged objections.
- **Date Input:** `<input type="date" name="day" max="today" required>` &mdash; Cannot select future dates.
- **Correct IN / Correct OUT:** Time pickers for the requested corrected timestamps.
- **Description Field:** Text input (up to 500 characters) explaining why the record should be corrected.
- **Button:** `Raise Objection` (White button with blue border).
- **Recent Objections Table:**
  - Displays: `Day`, `Discrepancy / Reason`, `Requested Correction` (e.g. `IN 09:30 / OUT 18:30`), `Status` pill (`Waiting for PM/TL`, `Accepted`, `Rejected`), and `PM/TL Decision & Remarks`.
  - When accepted, displays green confirmation: `✓ Applied to sheet: IN 09:30 / OUT 18:30`.

#### Accordion Section 2: Apply for Leave
- **Accordion Toggle:** Clicking expands or collapses the leave application interface.
- **Notice Text:** *"Applied at least 3 days before the first day = Planned, otherwise Unplanned. Approver decides within 24 hours or it escalates up the PM chain."*
- **Form Fields:**
  - `From` Date (`min=today`) and `To` Date (`min=today`).
  - `Type` Dropdown: `CL`, `PL`, `SL`, `Comp-off`, `Maternity/Paternity`, `Unpaid/LWP`.
  - `Task handled by` Dropdown: Select project colleague to cover responsibilities.
  - `Reason for leave` Input (up to 300 characters).
  - Blue button: `Apply for Leave`.
- **Asynchronous Live Capacity Feedback Banner (`#lvinfo`):**
  - As soon as From/To dates are picked, an asynchronous call checks team capacity in real-time.
  - **Teammates On Leave:** Lists: `Team-mates already applied for these days: [Name] ([dates], [status])`.
  - **Capacity Breach Alert:** If remaining capacity drops below the project minimum, a light red banner displays:
    `Capacity: Team capacity is full on [date] (only X of Y would be at work; minimum Z). Your TL/PM can ask you to withdraw, and approval then needs a senior PM.`
  - **Submit Confirmation Dialog:** If submitted while capacity is breached, a browser confirmation dialog prompts:
    *"Team capacity is full on some of these days. Your TL/PM may ask you to withdraw, and a senior PM must approve. Apply anyway?"*
- **My Leave Applications Table:**
  - **Columns:** `Dates`, `Type`, `Planning` (`Planned` / `Unplanned` / `extension` / `joined early`), `Cover`, `Status`, `Note / Decision`, `Actions`.
  - **Status Pills:**
    - `Approved` (Green)
    - `Rejected` (Red)
    - `Cancelled` (Grey)
    - `Change suggested` (Blue)
    - `Asked to withdraw` (Orange)
    - `Waiting for [approver]` (Amber)
  - **Lifecycle Action Buttons:**
    - If `Change suggested`: Shows `Accept new dates` (blue) and `Decline` (white) buttons.
    - If `can_cancel` (future pending/approved leave): Shows `Cancel` button.
    - If `running` (leave currently ongoing): Shows `I am back early` button (Early Return).
- **Colleagues on Leave on Upcoming Dates Table:**
  - Displays colleagues in the same project who are on leave in the next 30 days.

#### Monthly Roster & KPI Section
- **Month Selector:** `<input type="month">` picker. Selecting another month instantly refreshes the calendar.
- **6 KPI Cards:** `Present`, `Leave`, `Absent`, `Weekly Off`, `Late`, and `Total Hours`.
- **Calendar Grid:** Day-by-day record showing Date, Project, Status pill, Approval pill, In, Out, Hours, Late by, Short by, Leave, and Remarks.

---

### Screen 3: Phone Check-ins & Reconciliation (`/review`)
*Side-by-side reconciliation screen for PMs to verify mobile GPS events against the manual attendance sheet.*

```
+--------------------------------------------------------------------------------------------------------------------+
| Date: [ 2026-10-21 ]   [ NCLT ]  [[ UPSC ]]  [ NSP ]                                                                |
+--------------------------------------------------------------------------------------------------------------------+
| Engineer     | Phone IN | Phone OUT | Sheet IN | Sheet OUT | Went out | Time out | Trust | Action                  |
| Neha Verma   | 09:28    | 18:32     | 09:30    | 18:30     | 1        | 35 min   | ok    | [ Use phone times ]     |
| Pooja Nair   | 09:31    | -         | -        | -         | 0        | 0 min    | ok    | [ Use phone times ]     |
+--------------------------------------------------------------------------------------------------------------------+
| New phones waiting for approval                                                                                    |
| rohit.gupta@fosteringlinux.com   Google Pixel 8 Pro            [ Approve ]  [ Refuse ]                             |
+--------------------------------------------------------------------------------------------------------------------+
```

#### Visual Elements & Controls
1. **Side-by-Side Comparison Table:**
   - **Engineer:** Employee name.
   - **Phone IN / Phone OUT:** Timestamps recorded by mobile GPS geofence.
   - **Sheet IN / Sheet OUT:** Timestamps currently stored on the master attendance roster. Shows `(app)` if previously imported from mobile.
   - **Went out / Time out:** Counts temporary exits during the workday and cumulative break duration.
   - **Trust Column:**
     - Displays `ok` (grey) for verified GPS events.
     - Displays `X low` or `X not counted` (orange warning) if mock locations or inaccurate GPS signals were received.
   - **Action Column:**
     - **`Use phone times` Button:** Renders whenever there is a difference between mobile times and sheet times (`diff=true`). Clicking immediately writes mobile times into the master attendance sheet!
     - **Expandable Event Details (`<details>`):** Clicking `[X events]` reveals a sub-table displaying every raw ping with timestamp, direction (`in`/`out`), trust level, and distance in meters from site center (e.g. `24 m from centre`).
2. **New Phones Waiting for Approval Section:**
   - Appears when an engineer changes their mobile device.
   - Displays: Email, Device model name.
   - Action buttons: `Approve` (blue) and `Refuse` (white with red border).
3. **Engineer Disputes Section:**
   - Displays disputes filed via the mobile app with employee note and `Mark resolved` button.

---

### Screen 4: PM Approvals & Objections (`/approvals`)
*Centralized inbox for Project Managers to process daily attendance submissions, resolve objections, and monitor SLA performance.*

```
+--------------------------------------------------------------------------------------------------------------------+
| Approvals                                                                                                          |
| Attendance marked by phone or self-entry waits here. Decided within 24 hours or escalates up the PM chain.         |
+--------------------------------------------------------------------------------------------------------------------+
| Waiting for approval (2)                                                                                           |
| [x] | Date       | Engineer    | Project | IN    | OUT   | From     | Waiting for | Due                        |
| [ ] | 2026-10-21 | Neha Verma  | UPSC    | 09:28 | 18:32 | Phone    | moumita.roy | 2026-10-22 17:00           |
+--------------------------------------------------------------------------------------------------------------------+
| Note: [ Optional remarks...              ]    [ Approve ticked ]   [ Reject ticked ]                               |
+--------------------------------------------------------------------------------------------------------------------+
| Engineer objections (1)                                                                                            |
| Date       | Engineer   | Project | Objection                               | Asks for            | Your decision  |
| 2026-10-18 | Neha Verma | UPSC    | Biometric scanner was down during exit  | IN 09:30 / OUT 18:30| [ Decision Form]|
+--------------------------------------------------------------------------------------------------------------------+
```

#### Visual Elements & Controls
1. **Waiting for Approval Queue:**
   - Checkbox per row for bulk selection.
   - Columns: `Date`, `Engineer`, `Project`, `IN`, `OUT`, `From` (`Phone` or `Engineer`), `Waiting for`, `Due`.
   - **Batch Action Toolbar:**
     - Text input for optional notes/remarks.
     - Blue button: `Approve ticked`.
     - White button with blue border: `Reject ticked`.
2. **Escalated to Admin Queue:**
   - Highlights items in orange where the PM SLA expired and approval responsibility was transferred to Admin.
3. **Engineer Objections Section:**
   - Displays open disputes filed by engineers from `/me`.
   - Columns: `Date`, `Engineer`, `Project`, `Objection` (full reason), `Asks for` (requested IN/OUT).
   - **Inline Decision Form:**
     - Pre-populated `IN` time input and `OUT` time input (editable by PM).
     - Text input: `Comment for the engineer` (**required**).
     - Blue button: `Accept and apply times` &mdash; Automatically writes times to attendance sheet (even on past dates!) and marks status `Approved`.
     - White button: `Reject` &mdash; Rejects the dispute and notifies the engineer.
4. **Missed Approvals (SLA Delinquency) Scorecard:**
   - Table tracking approvers who failed to decide items within the SLA window (`Approver`, `Project`, `Last 30 days`, `All time`).
5. **Decided in the Last 7 Days Audit Table:**
   - Complete historical log of recent decisions with result pill (`Approved` [green], `Rejected` [red]), decider email, and note.

---

### Screen 5: Manager Leaves Dashboard (`/leaves`)
*Dashboard for PMs to review leave requests, evaluate 30-day capacity forecasts, and manage coverage.*

```
+--------------------------------------------------------------------------------------------------------------------+
| [ Leave Applications Waiting (1) ]   [ 📊 Leave Audit & Reports ]                                                   |
+--------------------------------------------------------------------------------------------------------------------+
| Waiting (1)                                                                                                        |
| Engineer   | Project | Dates                  | Days | Type | Reason / Cover             | Waiting for | Action  |
| Rohit Gupta| UPSC    | 2026-10-28 to 2026-10-28| 1   | PL   | Family event               | imran.mohd  | [Form]  |
|            |         |                        |      | Plan | Cover: Pooja Nair          | due 24h     |         |
+--------------------------------------------------------------------------------------------------------------------+
| Team capacity, next 30 days                                                                                        |
| Date       | Working | On leave | Waiting approval | Available | Minimum | Who                                 |
| 2026-10-28 | 6       | 2        | 1                | 3         | 4       | Away: Neha, Pooja  CAPACITY SHORT   |
+--------------------------------------------------------------------------------------------------------------------+
```

#### Visual Elements & Controls
1. **Top Navigation Tabs:** Toggle between `Leave Applications Waiting` and `📊 Leave Audit & Reports`.
2. **Waiting Queue Table:**
   - Shows applicant name (with red `extension of an earlier leave` indicator if applicable), project, date span, total work days, leave type, planned badge, reason, and cover colleague.
   - **Capacity Warning Badge:** If capacity is breached, displays: `⚠️ Team capacity is full on [dates]. Needs the person above you.`
   - **Decision Form Controls:**
     - Note input: Optional on approval, mandatory on rejection.
     - Planned dropdown: `as Planned/Unplanned`, `Planned`, `Unplanned`.
     - Blue button: `Approve` (Disabled with tooltip if capacity is full and user is not authorized senior PM).
     - White button: `Reject`.
     - White button: `Ask to withdraw` (Appears only when capacity is full).
     - Suggest alternative dates: Date inputs (`sfrom`, `sto`) + `Suggest` button.
3. **Team Capacity, Next 30 Days Forecast Grid:**
   - Columns: `Date`, `Working`, `On leave`, `Waiting for approval`, `Available`, `Minimum`, `Who`.
   - **Shortage Highlight:** Rows where available headcount falls below minimum required are highlighted in red (`#ffe3e3`) with bold red text: `CAPACITY SHORT`.
4. **Decided Recently Table:** Audit history of past leave approvals and rejections.
5. **Admin Settings Bar (Admin Exclusive):**
   - Inputs to adjust global SLA parameters: `Planned if applied at least [X] days ahead` and `Approve within [Y] hours`.

---

### Screen 6: Leave Audit & Management Reports (`/leaves/report`)
*Comprehensive analytics for HR, PMs, and Executives to monitor workforce availability and SLA compliance.*

```
+--------------------------------------------------------------------------------------------------------------------+
| Leave Audit & Management Reports                         [ 📥 Download 6-Sheet Excel (.xlsx) ]                     |
+--------------------------------------------------------------------------------------------------------------------+
| Project: [ UPSC v ]   From: [ 2026-09-21 ]   To: [ 2026-12-20 ]   [ Filter Range ]                                 |
+--------------------------------------------------------------------------------------------------------------------+
| [ Capacity Short: 2 ] [ SLA Missed: 1 ] [ Extensions: 1 ] [ Early Resumes: 1 ] [ Planned: 14 ] [ Unplanned: 3 ]    |
+--------------------------------------------------------------------------------------------------------------------+
```

#### Visual Elements & Controls
1. **Filter Toolbar:** Project dropdown, From date, To date, and `Filter Range` button.
2. **Download Button:** Green button: `📥 Download 6-Sheet Excel (.xlsx)` &mdash; Downloads a fully formatted OpenPyXL workbook containing dedicated sheets for all 6 metrics.
3. **6 KPI Summary Cards:**
   - `Capacity short days` (Red border)
   - `SLA missed approvals` (Orange border)
   - `Leave extensions` (Blue border)
   - `Early resumes` (Green border)
   - `Total planned days` (Emerald border)
   - `Total unplanned days` (Amber border)
4. **6 Dedicated Data Tables:**
   - 1. Days Team Ran Short of Capacity
   - 2. Leave Approvals Not Decided in Time / SLA Misses
   - 3. Leave Extensions (Consecutive applications)
   - 4. Early Resumes / Returns to Duty
   - 5. Planned vs Unplanned Leave Mix per Engineer
   - 6. Withdrawal Requests

---

### Screen 7: Trends & Arrival Patterns (`/trends`)
*Visual analytics screen displaying employee punctuality, delay distributions, and day-of-week attendance patterns.*

#### Visual Elements & Controls
1. **Timeframe Selector Pills:**
   - Clickable buttons for predefined ranges: `7 days`, `14 days`, `30 days`, `60 days`, `90 days`, `180 days`, `365 days`, `Custom`.
   - Selecting `Custom` displays Start Date and End Date inputs with a `Filter` button.
2. **Project & User Filters:**
   - PMs and Admins can view project-wide trends or filter to individual engineers.
   - Engineers viewing `/trends` are locked to their own individual statistics.
3. **Summary KPI Cards:**
   - `Total Working Days`, `Present %`, `On-time %`, `Late Arrivals`, `Early Exits`, `Leave Days`, `Absent Days`.
4. **Arrival Timing Distribution Chart:**
   - Bar charts illustrating arrivals categorized by: On-Time, Late 1–15 mins, Late 15–30 mins, Late >30 mins.
5. **Day-of-Week Irregularity Chart:**
   - Analyzes Monday to Friday attendance distributions to identify recurring absenteeism patterns.

---

### Screen 8: Daily Summary & Dispatch (`/summary`)
*Daily project operational snapshot with automated email reporting.*

#### Visual Elements & Controls
1. **Date Picker & Project Tabs:** Allows inspecting historical daily summaries.
2. **KPI Scorecard:** Total Team Strength, Present Today, On Leave, Absent, Late Arrivals (>15m past shift start), Missing Check-Outs.
3. **Late Arrivals Table:** Lists employees who punched in late along with exact delay in minutes.
4. **Missing Check-Outs Table:** Lists employees who clocked in but have no exit timestamp recorded.
5. **Admin Action Button:** `Send Email Summary` &mdash; Dispatches an automated HTML summary to stakeholders via SMTP.

---

### Screen 9: My Team & Bench Management (`/team`)
*Team roster management, shift configuration, bench assignments, and project transfers.*

#### Visual Elements & Controls
1. **Top Action Button:** `Manage Team` &mdash; Opens the multi-tab team management modal.
2. **Team Roster Table:**
   - Columns: `Engineer`, `Role`, `Contact number`, `Email`, `Shift start`, `Source`, `Action`.
   - **Inline Shift Start Time Editor:** Each row contains a time input `<input type="time" name="shift">` with a `Save` button to configure custom shifts.
   - **Profile Completeness Badge:** Flags `Incomplete Profile` if phone or role title is missing.
   - **Release to Bench Button:** Red text `Remove` button with confirmation prompt: *"Are you sure you want to release [Name] to the Bench Pool?"*.
   - **Admin Transfer Dropdown (`Transfer to...`):** Dropdown listing other active projects. Selecting a destination project immediately reassigns the engineer.
   - **Restore Button:** For inactive members, displays `Put back` button to restore them to active roster.
3. **Manage Team Modal (3 Tabs):**
   - **Tab 1 (Keycloak Directory):** Browse and search active enterprise users to add to the project.
   - **Tab 2 (Bench Pool):** Shows engineers not currently assigned to any project for immediate one-click assignment.
   - **Tab 3 (Direct Add):** Form to enter Full Name, Email, Role, Shift start, and Phone.

---

### Screen 10: Project Setup & Escalation Hierarchy (`/project/setup`)
*Configuration center for PM hierarchies, geofences, and working days.*

#### Visual Elements & Controls
1. **PM Approval Chain Card:**
   - Four level inputs: `PM0 (Primary Project Lead)`, `PM1 (Deputy 1)`, `PM2 (Deputy 2)`, `PM3 (Deputy 3)`.
   - Blue button: `Save PM chain`.
2. **Project Information & Capacity Rules Card:**
   - Owner / Client Lead Name, Email, Phone, Office Address.
   - **Minimum Capacity Input:** Set minimum engineers required on duty each day (defaults to 60% if blank).
   - **Default Weekly Off Checkboxes:** Checkboxes for Monday through Sunday.
   - Blue button: `Save Project Information`.
3. **Phone Check-in Sites & Work Geofences Card:**
   - Lists configured geofences for mobile app tracking.
   - Fields: `Site Name`, `Latitude`, `Longitude`, `Radius (metres)`, `Arrival wait (dwell_in minutes)`, `Leaving wait (dwell_out minutes)`, `Wi-Fi/Bluetooth check mode`, `Beacon identifiers`.
   - **`📍 Use my location` GPS Button:** Automatically captures the browser's current latitude and longitude.
   - Action buttons: `Save site`, `Remove`, and `+ Add a work site geofence`.
   - **Admin Global Limits Bar:** Allows Admins to restrict minimum (e.g. 5m) and maximum (e.g. 5000m) allowed geofence radii across the application.

---

### Screen 11: Access Rights Management (`/access`)
*Admin-exclusive control panel to grant and revoke managerial roles.*

#### Visual Elements & Controls
1. **Grant Access Form:**
   - Email input.
   - Role dropdown: `admin`, `lead`.
   - `All Projects` Checkbox: Grants global visibility across every project.
   - Blue button: `Save Access`.
2. **Current Access Table:**
   - Lists all configured managers and administrators with their granted scope.

---

### Screen 12: Real-Time In-App Notification Center (`#wfn`)
*Floating notification modal that alerts users in real-time without requiring manual page reloads.*

#### Visual Elements & Controls
1. **Floating Alert Drawer (`#wfn`):**
   - Renders in the center of the viewport with a semi-transparent backdrop.
   - Top bar: Shows "Notifications" title, total count badge, and `Dismiss all` button.
2. **4 Color-Coded Themes:**
   - **Green Theme (`APPROVED` / `ACCEPTED`):** Green border, light green background. Used when leave or objections are approved.
   - **Red Theme (`REJECTED` / `DECLINED`):** Red border, light red background. Used when leave or objections are denied.
   - **Orange Theme (`ACTION REQUIRED`):** Orange border, light orange background. Used for withdrawal requests, capacity shortages, and SLA notices.
   - **Blue Theme (`NOTICE`):** Blue border, light blue background. General notices.
3. **Item Action Controls:**
   - Dismiss button (`×`): Closes the single notice and marks it read in the database.
   - `Open →` Link: Directly navigates to the relevant page (`/me`, `/leaves`, or `/approvals`) and automatically dismisses the notice.

---
