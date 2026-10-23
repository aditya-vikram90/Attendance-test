# Enterprise Attendance & Shift Management Portal
## Comprehensive User Guide & Operational Manual

| Metadata | Details |
| :--- | :--- |
| **System Module** | Attendance Service (`attendance-service`) |
| **Target Audience** | Software Engineers, Tech Leads, Project Managers, System Administrators, HR/Operations |
| **Access URL** | `https://pm.keenable.io/attendance/` |
| **Identity Provider** | Keycloak Enterprise Single Sign-On (SSO) |
| **Document Version** | 3.0 (Production Release) |

---

## 1. Introduction & Purpose

### 1.1 The Problem It Solves
Historically, engineering organizations managed attendance through disconnected, manual tools:
* **Fragmented Spreadsheets**: Separate Excel files maintained by individual project leads led to missing records and zero central visibility.
* **Manual Day-by-Day Entry for Multi-Day Leaves**: When an engineer took an approved 5-day vacation, the Project Manager had to log in every single day to manually mark them on leave.
* **Client Site vs. Head Office Ambiguity**: Engineers deployed at client locations frequently visit the Head Office for internal sprint meetings, hardware upgrades, or reviews. Without clear operational remarks, this led to disputes regarding client billing and attendance validity.
* **Bench Pool Blindspots**: Administrators lacked immediate visibility into available unassigned engineers, causing delays in resource reallocation.

### 1.2 The Solution
The **Attendance & Shift Management Portal** provides a fast, unified operational platform directly integrated with **Keycloak Enterprise SSO**:
* **Centralized Attendance Tracking**: Real-time project rosters with check-in/out times and lateness tracking.
* **Automated Advance Leave Pre-Marking**: Pre-approved leaves are entered once by the PM; the system automatically marks all future working dates (skipping weekends).
* **Operational Remarks Transparency**: Distinguishes between Client Site duty and Head Office visits across all summaries, Excel exports, and employee dashboards.
* **Bench Mobility**: 1-click live search and cross-project transfers for Administrators.

---

## 2. Getting Started & Single Sign-On (SSO)

### 2.1 Accessing the Portal
1. Open your web browser and navigate to:  
   **`https://pm.keenable.io/attendance/`**
2. If you are not already authenticated with the company SSO, you will be redirected to the secure **Keycloak Login Screen**.

### 2.2 Authenticating via Keycloak SSO
1. Enter your standard company **Email** or **Username** and **Password**.
2. Click **Sign In**.
3. Once authenticated, Keycloak securely redirects you back to your customized Attendance dashboard based on your assigned role.

```
┌────────────────────────────────────────────────────────────────────────────────────────────────┐
│  Attendance  |  Enter attendance  |  My team  |  Summary  |  Trends  |  Projects  |  My attendance│
│                                                                        User: Vikram Singh [PM] │
└────────────────────────────────────────────────────────────────────────────────────────────────┘
```

### 2.3 Navigation Overview
* **Enter attendance (`/`)**: Daily operational attendance sheet for PMs and Leads.
* **My team (`/team`)**: Project roster overview, shift timings, and Admin Team Management modal.
* **Summary (`/summary`)**: Daily KPI cards, task handover details, and Excel exports.
* **Trends (`/trends`)**: Interactive graphical attendance patterns and engineer regularity scorecards.
* **My attendance (`/me`)**: Personal monthly calendar and shift records for team members.
* **Log Out**: Terminates your active session locally and globally across Keycloak.

---

## 3. Attendance Status Codes & Terminology

Every attendance entry uses standardized codes:

| Code | Status | Description | Typical Use Case |
| :---: | :--- | :--- | :--- |
| **`P`** | **Present** | Engineer attended work on shift. | On duty at Client Site or Head Office. |
| **`A`** | **Absent** | Unplanned or unnotified absence. | Engineer did not report to work and provided no notice. |
| **`L`** | **Leave** | Full-day approved leave. | Pre-approved Casual, Sick, or Earned Leave. |
| **`HD`** | **Half Day** | Half-day shift completed. | Reported for 1st half or 2nd half with PM approval. |
| **`W`** | **Work From Home** | Remote working duty. | Pre-approved remote work from home. |
| **`H`** | **Holiday** | Official holiday / day off. | Public holidays, company festivals, or scheduled off. |
| **`CO`** | **Comp-Off** | Compensatory day off. | Redeeming compensatory credit earned on weekend duty. |

---

## 4. Role Guide: Software Engineer / Team Member

As an Engineer, your primary hub is the **My Attendance** page (`/me`).

```
┌────────────────────────────────────────────────────────────────────────────────────────────────┐
│ Arun Kumar  ·  Civil Services Portal                                                           │
│ Month: [ October 2026 ▼ ]   Your shift starts 09:30 · grace 15 min · shift 8.5 h incl. lunch   │
├────────────────────────────────────────────────────────────────────────────────────────────────┤
│ [ Total Days: 22 ]  [ Present: 18 ]  [ On Leave: 2 ]  [ Late: 1 ]  [ Short Shift: 0 ]          │
├────────────────────────────────────────────────────────────────────────────────────────────────┤
│ Date        Project         Status   In     Out    Worked   Late   Short  Leave   Remarks        │
│ 19-Oct Mon  Client Portal   Present  09:25  18:30  9h 05m   —      —      —       At Head Office │
│ 20-Oct Tue  Client Portal   Leave    —      —      —        —      —      Casual  Family event   │
└────────────────────────────────────────────────────────────────────────────────────────────────┘
```

### 4.1 Viewing Your Personal Attendance
1. Click **My attendance** in the top navigation bar.
2. Select the desired month from the **Month** selector.
3. Review your daily records:
   * **In / Out Times**: Clock-in and clock-out timestamps entered by your lead.
   * **Hours in Office**: Total active working duration logged.
   * **Late by / Short by**: Punctuality indicators showing minutes past shift start or early departure.
   * **Remarks**: Operational notes recorded for that day.

### 4.2 Verifying Head Office Duty
* If you visited the Head Office instead of your normal client site, check the **Remarks** column for that date.
* Ensure your status is marked **Present (`P`)** with a note such as *"Visited Head Office for internal review"*.
* *Note: If a discrepancy exists, notify your Project Manager or Tech Lead immediately.*

### 4.3 Applying for Leaves
> [!IMPORTANT]
> **Leave applications are processed through official email channels, NOT inside this portal.**  
> 1. Submit your leave request to your Project Manager / Tech Lead via company email.  
> 2. Once your PM approves the request, they will log it into the portal's Leave Management module.  
> 3. Your approved future leave dates will automatically appear on your **My attendance** calendar.

---

## 5. Role Guide: Project Manager & Tech Lead (PM/TL)

As a PM or Tech Lead, you are responsible for maintaining daily project attendance and logging email-approved leaves.

### 5.1 Marking Daily Attendance (`/` - Enter Attendance)
1. Navigate to **Enter attendance**.
2. Select your project tab at the top.
3. The page defaults to **Today's Date**. (You can navigate to future dates or today; past dates are locked for non-admins).
4. For each engineer on your roster:
   * **Status**: Select `Present`, `Absent`, `Leave`, `Half Day`, `WFH`, `Holiday`, or `Comp-Off`.
   * **In / Out**: Enter check-in and check-out times (e.g., `09:30` and `18:30`).
   * **Cover Person**: If the engineer is on leave or absent, select a colleague from the dropdown to designate who is covering their operational tasks.
   * **Remarks**: Enter relevant operational context.
5. Click **Save Attendance** at the bottom of the roster.

---

### 5.2 Recording Head Office Visits for Client-Site Engineers
When an engineer deployed to a client site visits the Head Office for internal company business:
1. Keep their status as **Present (`P`)**.
2. Enter their check-in and check-out times.
3. In the **Remarks** field, type the operational context:
   * Example: `"Visited Head Office for internal sprint review and IT setup"`
4. Click **Save Attendance**.
* **Result**: The engineer's project attendance is preserved, the Head Office visit is permanently logged in the audit trail, and client billing records remain clear.

---

### 5.3 Logging Pre-Approved Advance Leaves (`Leave Management` Modal)
When an engineer's multi-day leave has been pre-approved over email:

```
┌────────────────────────────────────────────────────────────────────────────────────────┐
│ Leave Management                                                                   [×] │
│ Project: Client Web Portal                                                             │
├────────────────────────────────────────────────────────────────────────────────────────┤
│ [ Upcoming & Active Leaves (2) ]    [ Apply Advance Leave ]                            │
├────────────────────────────────────────────────────────────────────────────────────────┤
│ Engineer:      [ Arun Kumar (Software Engineer)                             ▼ ]        │
│ Leave Period:  From [ 2026-10-21 ]  To [ 2026-10-24 ]   (Duration: 4 working days)     │
│ Leave Type:    [ Casual Leave                                               ▼ ]        │
│ Task Handover: [ Vikram Singh (Lead)                                        ▼ ]        │
│ Remarks:       [ Pre-approved on email for personal travel                    ]        │
├────────────────────────────────────────────────────────────────────────────────────────┤
│                                                    [ Cancel ]  [ Save Advance Leave ]  │
└────────────────────────────────────────────────────────────────────────────────────────┘
```

1. On the **Enter attendance** screen, click the **Leave Management** button.
2. Switch to the **Apply Advance Leave** tab.
3. Select the **Engineer**.
4. Choose the **From Date** and **To Date**.
5. Select the **Leave Type** (Casual, Sick, Earned, Comp-Off, Optional).
6. Nominate a **Task Handover** engineer who will handle active client work items.
7. Enter the approved email reference or reason in the **Remarks** field.
8. Click **Save Advance Leave**.

#### Automatic Weekend Skipping
The system automatically identifies Saturdays and Sundays within the date range and skips them. Only official working days are marked with status **`L`**.

#### Rescheduling or Canceling Leaves
1. Open the **Leave Management** modal.
2. In the **Upcoming & Active Leaves** tab, locate the engineer's leave entry.
3. Click **Cancel** to immediately revoke future leave days and restore normal roster status.

#### Handling Early Returns (Reporting to Duty Ahead of Schedule)
If an engineer returns early (e.g., reports to work on Thursday when scheduled off through Friday):
1. Navigate to today's date on the **Enter attendance** screen.
2. Change the engineer's status from `Leave` to **`Present`**.
3. Enter their arrival time and save.
4. **Outcome**: Today is updated to Present; all remaining future leave days (Friday) stay intact without needing to reconfigure the leave.

---

### 5.4 Reviewing Daily & Monthly Summaries (`/summary`)
1. Click **Summary** in the navigation bar.
2. Filter by **Date** and **Project**.
3. **KPI Review**: Check top counters for Present, Absent without info, On Leave, Late arrivals, and Unentered records.
4. **Task Handover Audit (Section 3)**:
   * View who is on leave and verify their assigned cover person.
   * Expand the **Open tasks in OpenProject** accordion to inspect linked tickets and due dates.
5. **Present Members & Remarks (Section 4)**:
   * Verify all active members and review submitted remarks (including Head Office visits).
6. **Exporting Reports**:
   * Click **Download this day (Excel)** to generate an immediate daily audit `.xlsx`.
   * Click **Monthly report (Excel)** to download a complete project workbook with monthly attendance matrices and daily audit logs.

---

### 5.5 Analyzing Team Trends & Regularity (`/trends`)
1. Click **Trends** in the navigation bar.
2. Select your time span: **Last 7, 14, 30, 60, or 90 days**.
3. **Daily Attendance Pattern**: Hover over the stacked SVG bars to see daily attendance distributions. Click any day bar to drill into that day's summary.
4. **Late Arrivals by Weekday**: Check the percentage of lateness per day of the week (e.g., identifying recurring Monday morning lateness).
5. **Engineer Regularity Scorecard**:
   * Review engineers flagged as **`Regular`**, **`Minor`**, or **`Irregular`**.
   * Inspect the **Direction** indicator to see if attendance punctuality is *Improving* or *Getting worse*.

---

## 6. Role Guide: System Administrator

Administrators possess organization-wide authority across all projects, team allocations, and historical records.

### 6.1 Team Management & Bench Pool Allocations (`/team`)
1. Navigate to **My team** and select any project.
2. Click the **Manage Team** button to launch the management modal.

```
┌────────────────────────────────────────────────────────────────────────────────────────┐
│ Manage Team                                                                        [×] │
│ Current View: Civil Services Portal                                                    │
├────────────────────────────────────────────────────────────────────────────────────────┤
│ Search Engineer by Email or Name:                                                      │
│ [ imran                                                                              ] │
├────────────────────────────────────────────────────────────────────────────────────────┤
│  Mohd Imran (Software Engineer)                               Current: Bench Pool      │
│  Email: imran.mohd@fosteringlinux.com  ·  Contact: +91 9876543210                       │
│  Target Project: [ Civil Services Portal ▼ ]  Shift starts: [ 09:30 ]                  │
│                                                          [ + Assign to Team ]          │
└────────────────────────────────────────────────────────────────────────────────────────┘
```

#### Live Debounced Directory Search
* Type the engineer's name or email (e.g., `imran` or `mohd`).
* The directory searches dynamically as you pause typing.

#### Assigning Bench Engineers to a Project
1. Find an engineer whose status displays **`Current: Bench Pool`**.
2. Select the **Target Project**.
3. Set their **Shift starts** time (default: `09:30`).
4. Click **+ Assign to Team**.

#### 1-Click Cross-Project Transfers
1. Search for an engineer currently assigned to another project.
2. Their card will show a warning: `Current: Project A`.
3. In the **Target Project** dropdown, select **Project B**.
4. The button updates dynamically to **Transfer & Assign**.
5. Click **Transfer & Assign**.
   * *The engineer is atomically released from Project A and assigned to Project B.*
   * *Historical attendance in Project A is completely preserved.*

#### Releasing Members to Bench
1. On the **My team** roster table, locate the member.
2. Click **Release to Bench Pool**.
3. The engineer is moved to the bench pool; their past attendance remains intact.

---

### 6.2 Administrative Historical Overrides
Unlike PMs (who are locked to today and future dates), Administrators can navigate to any past date on the **Enter attendance** screen to audit, correct, or adjust historical records.

### 6.3 Executive Reporting & Daily Email Broadcasts
1. On the **Summary** page, Admins can view aggregated metrics across **All my projects**.
2. Click **Email this summary now** to trigger an immediate formatted HTML attendance digest to executive leadership and department heads.

---

## 7. Frequently Asked Questions (FAQ) & Troubleshooting

### Q1: An engineer visited the Head Office today instead of the client site. What should be done?
**Answer**: Mark the engineer as **Present (`P`)** on the daily attendance sheet. In the **Remarks** input box, explicitly type: `"Visited Head Office for internal sprint review / IT hardware maintenance"`. This ensures their attendance is counted while maintaining audit transparency for client billing.

### Q2: Why is the "Save Attendance" button locked for past dates?
**Answer**: Project Managers and Tech Leads are restricted from altering historical attendance records to maintain audit integrity. Only System Administrators have permission to edit past records.

### Q3: How do I handle an engineer returning from leave earlier than planned?
**Answer**: On the Enter Attendance screen, navigate to today's date, switch the engineer's status from `Leave` to **`Present`**, enter their check-in time, and save. The system updates today to Present and automatically keeps all remaining future leave days intact.

### Q4: An engineer's name is not appearing in the project roster. How do I add them?
**Answer**: Contact a System Administrator. The Administrator can open the **Manage Team** modal on `/team`, search for the engineer in the Keycloak directory, and assign or transfer them to your project in one click.

### Q5: Can engineers apply for leave directly through the portal?
**Answer**: No. Leave requests must be submitted and approved through company email. Once approved by the manager/lead, the PM or Admin enters the leave into the portal's **Leave Management** modal to pre-populate future dates.
