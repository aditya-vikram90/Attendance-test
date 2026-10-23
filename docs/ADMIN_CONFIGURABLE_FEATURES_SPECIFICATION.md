# Dynamic Admin Configuration Engine: Web, Email & Mobile Specification

This document provides the definitive, comprehensive specification of all features and parameters that are configurable via the **Admin UI** (`/attendance/admin/settings`). System administrators can toggle features on or off, enable or disable specific email notifications, and tune behavioral parameters in real time without redeploying backend servers or rebuilding Android APKs.

---

# PART 1: Web Application Configurable Features

## 1.1 Summary Matrix

| Feature Toggle | When Enabled | When Disabled |
| :--- | :--- | :--- |
| **Auto-Verification of Geofence Punches** | System automatically marks geofenced punches with a green "Verified" badge. | All punches remain in a "Pending Verification" state until PM or Admin manually approves them. |
| **PM / TL Manual Punch Editing** | Project Managers and Team Leads can manually adjust or insert In/Out punch times for team members on `/review`. | Punch editing is restricted strictly to Super Admins; PMs have read-only view. |
| **Mandatory Remarks on Manual Edit** | Forces PMs/Admins to enter an explanation note before saving any manual punch change. | Edits can be saved immediately without typing an explanation reason. |
| **Historical Attendance Lock Window** | Records older than the configured days (e.g. 7 days) are frozen and cannot be modified. | Past records remain editable indefinitely regardless of how many days or months have passed. |
| **Raw GPS Coordinates & Accuracy Display** | Shows exact latitude, longitude, distance, and accuracy numbers in the review table. | Hides raw coordinates, showing only the work site name for cleaner UI and privacy. |
| **Direct Punch Record Deletion** | Provides an authorized "Delete Punch" option on `/review` to remove false or erroneous punches. | Punch records cannot be deleted by anyone; only status overrides are allowed to maintain audit integrity. |
| **Web-Based Direct Check-In Button** | Displays a manual "Mark Attendance" button on the web portal (`/checkin` or `/me`) for desktop users. | Completely removes web check-in; attendance can strictly be recorded via the mobile app with geofencing. |
| **Advance Notice Cutoff Enforcement** | Rejects leave applications submitted fewer than the required notice days in advance (e.g. minimum 2 days notice). | Employees can apply for leaves retroactively or on the same day without notice restrictions. |
| **Negative Leave Balance (LWP) Tolerance** | Allows employees to apply for leave even when their quota is exhausted, auto-tagging excess days as Leave Without Pay. | Leave application form is hard-blocked if current available leave balance is zero. |
| **Half-Day (First/Second Half) Option** | Provides options to apply for First Half (09:30–13:30) or Second Half (14:30–18:30) partial leave. | Leaves can only be applied for full calendar days (1.0 day increments). |
| **Medical Certificate Upload Requirement** | Mandates file upload of a doctor's certificate for sick leaves exceeding the threshold (e.g. > 2 days). | Sick leaves of any duration can be submitted without requiring supporting document attachments. |
| **Pending Leave Auto-Escalation to HR** | Automatically escalates leave requests to HR if the assigned PM does not decide within 48 hours. | Leaves remain pending indefinitely in the PM's queue until manually acted upon. |
| **Employee Self-Cancellation of Approved Leaves** | Employees can cancel their own upcoming approved leave before the leave date arrives. | Once approved by PM, only HR or Admin can revoke or cancel the leave record. |
| **Sandwich Rule Enforcement** | Automatically counts intervening weekends/holidays as paid leave if an employee takes leave on both Friday and Monday. | Weekends and declared holidays are strictly excluded from leave deduction regardless of adjacent leave days. |
| **Multi-Tier Approval Hierarchy** | Routes leave and attendance regularization requests through a multi-tier chain (Team Lead → Project Manager → HR). | Uses a single-tier approval workflow where either the TL or PM's decision is final. |
| **Manager Self-Approval Guard** | Strictly prevents PMs, TLs, and Admins from approving their own leaves or punch regularizations. | Allows managers to self-approve their own attendance and leave records. |
| **Employee Right-to-Reply (Objections)** | When a leave or punch is rejected, an "Objection / Clarification" button allows the employee to respond with evidence. | Rejections are final and closed; employee must re-apply or discuss offline. |
| **Out-of-Office Proxy Approver** | Allows PMs going on leave to designate a temporary peer proxy to approve attendance on their behalf. | Approval rights remain tied strictly to the assigned PM; escalations go directly to Super Admin. |
| **Concurrent Multi-Site Assignment** | Employees can be allocated to multiple active work sites simultaneously (e.g. Main Office + Client HQ). | Employees are locked to exactly one designated primary work site at any given time. |
| **Project-Specific Week-Off Schedule** | Allows different projects to configure custom week-offs (e.g. Sunday only vs 5-day week vs 2nd/4th Saturday). | Enforces a single global company-wide week-off schedule for all projects. |
| **External Client Officer Read-Only Access** | Generates a restricted, read-only attendance dashboard view for external client nodal officers. | The web portal is completely inaccessible to anyone outside the internal company roster. |
| **Unassigned / Bench Engineer Pool** | Enables the dedicated "Bench Pool" view on `/team` to track and reallocate engineers awaiting project deployment. | Hides the bench pool; all active employees must be assigned to an active project. |
| **PM Device Unbind Permission** | Empowers Project Managers to unbind a team member's registered smartphone when they change phones. | Only Super Admins can unbind devices, ensuring maximum hardware security. |
| **Automated Keycloak SSO Onboarding** | Automatically provisions a new employee profile in the database upon their first successful Keycloak SSO login. | New users cannot access the portal until an administrator manually creates their employee record first. |
| **Payroll Working Day Formula** | Computes monthly payout and deductions strictly based on actual working days (excluding project week-offs). | Uses standard 30 calendar days flat division for monthly salary calculations. |
| **Overtime (OT) Hours Tracking** | Automatically tracks, tallies, and exports hours worked beyond the standard 8-hour shift in separate export columns. | Ignores overtime; all completed shifts are capped at standard daily hours. |
| **Sensitive GPS Data Masking in Exports** | Hides raw GPS coordinates from standard Excel/CSV exports, showing only site names and timestamps. | Includes exact latitude, longitude, distance, and accuracy numbers in all exported files. |

---

## 1.2 Detailed Descriptions for Web Application Features

### 1. Auto-Verification of Geofence Punches
- **Module:** Attendance Review (`/review`)
- **Description:** Determines whether system-validated geofence entries/exits are instantly granted verified status or held for supervisor sign-off. When enabled, any check-in that occurs within the work site's allowed radius is marked with a green "Verified" badge automatically, freeing PMs from manual paperwork. When disabled, all punches remain in a yellow "Pending Verification" state until the manager explicitly approves them.

### 2. PM / TL Manual Punch Editing
- **Module:** Attendance Review (`/review`)
- **Description:** Controls permission levels for altering time logs. In many field or client scenarios, employees may forget to punch or have phone issues; enabling this allows frontline Project Managers to adjust In/Out times directly on `/review`. Disabling it restricts all punch modifications strictly to HR/Super Admin to prevent supervisory favoritism.

### 3. Mandatory Remarks on Manual Edit
- **Module:** Attendance Review (`/review`)
- **Description:** Enforces an audit requirement. When enabled, anytime a manager or admin edits an employee's In or Out time on the web, an interactive dialog forces them to input a reason (e.g., "Device battery died, verified via office CCTV"). The reason is permanently saved to the audit log.

### 4. Historical Attendance Lock Window
- **Module:** Attendance Review & Payroll (`/review`, `/summary`)
- **Description:** Sets the cutoff age (in days) after which attendance records become immutable. For example, setting this to 7 days ensures that after weekly reconciliation or payroll cutoff, past records cannot be tampered with or modified retrospectively.

### 5. Raw GPS Coordinates & Accuracy Display
- **Module:** Attendance Review (`/review`)
- **Description:** Controls data visibility for managers. When enabled, table columns display exact coordinates (e.g. `28.6289, 77.3789`), distance from site center (`4m`), and GPS fix uncertainty (`±12m`). When disabled, managers only see human-readable location names (`Noida Office`) for cleaner UI and privacy.

### 6. Direct Punch Record Deletion
- **Module:** Attendance Review (`/review`)
- **Description:** Controls whether errant records can be permanently deleted from the database. In high-compliance environments, deleting records is prohibited (records should only be superseded). When disabled, the delete button is hidden from all web screens.

### 7. Web-Based Direct Check-In Button
- **Module:** Employee Self-Service (`/checkin`, `/me`)
- **Description:** Dictates whether desktop users can click a button on their browser to mark attendance. If an organization wants to enforce 100% geofence compliance on physical mobile devices, disabling this toggle removes web check-in, requiring all staff to use the Android app.

### 8. Advance Notice Cutoff Enforcement
- **Module:** Leaves Management (`/leaves`, `/me/leave`)
- **Description:** Enforces planning discipline. When enabled, the leave calendar blocks selection of dates within the cutoff period (e.g. 2 days prior to today). When disabled, emergency or retroactive leave applications can be lodged.

### 9. Negative Leave Balance (LWP) Tolerance
- **Module:** Leaves Management (`/leaves`)
- **Description:** Handles leave requests when an employee has 0 remaining paid leaves. When enabled, the application proceeds and tags the requested days as Leave Without Pay (LWP). When disabled, the form errors out: "Insufficient leave balance."

### 10. Half-Day (First/Second Half) Option
- **Module:** Leaves Management (`/leaves`)
- **Description:** Enables partial day leave applications. When enabled, employees can choose "First Half (09:30 - 13:30)" or "Second Half (14:30 - 18:30)", deducting 0.5 days from balance. When disabled, only full-day absences are accepted.

### 11. Medical Certificate Upload Requirement
- **Module:** Leaves Management (`/leaves`)
- **Description:** Controls compliance rules for sick leave. When enabled, if an employee requests sick leave exceeding the configured threshold (e.g. 2 consecutive days), a file attachment input becomes mandatory before submission.

### 12. Pending Leave Auto-Escalation to HR
- **Module:** Approvals & Workflow (`/approvals`)
- **Description:** Prevents operational paralysis when managers are unresponsive. If a leave request sits unanswered in a PM's queue for more than 48 hours, the system automatically elevates the notification and approval rights to the HR department.

### 13. Employee Self-Cancellation of Approved Leaves
- **Module:** Leaves Management (`/me/leave`)
- **Description:** Allows staff flexibility if plans change. When enabled, an employee can cancel an approved leave as long as the date is in the future. Their leave balance is automatically refunded. When disabled, only HR can revoke approved leaves.

### 14. Sandwich Rule Enforcement
- **Module:** Attendance Policy & Payroll
- **Description:** A standard HR payroll policy. If an employee takes leave on Friday and Monday, the intervening Saturday and Sunday are counted as leave days. When disabled, weekends are never deducted from leave balances.

### 15. Multi-Tier Approval Hierarchy
- **Module:** Approvals Workflow (`/approvals`)
- **Description:** Selects the organizational approval chain: 1-tier (Team Lead only), 2-tier (TL approval followed by PM final sign-off), or 3-tier (TL → PM → HR Manager).

### 16. Manager Self-Approval Guard
- **Module:** Approvals Workflow (`/approvals`)
- **Description:** Prevents conflicts of interest. When enabled, if a user is both an approver and the applicant, the system automatically routes the item to their direct supervisor or HR, preventing self-approval.

### 17. Employee Right-to-Reply (Objections)
- **Module:** Approvals & Dispute Resolution (`/approvals`, `/me/objection`)
- **Description:** Ensures fairness. If a PM marks an employee absent or rejects a leave, enabling this gives the employee a button to submit a counter-explanation with supporting details before the decision is permanently locked.

### 18. Out-of-Office Proxy Approver
- **Module:** Approvals Workflow (`/approvals/settings`)
- **Description:** Enables managers to assign an authorized colleague as their temporary proxy approver during vacations, ensuring daily attendance and leave processing continues smoothly.

### 19. Concurrent Multi-Site Assignment
- **Module:** Project & Site Setup (`/projects`, `/project/setup`)
- **Description:** Determines whether an engineer can have multiple authorized check-in sites. When enabled, a roving consultant or field engineer can punch in at either "Site A" or "Site B" without generating out-of-boundary warnings.

### 20. Project-Specific Week-Off Schedule
- **Module:** Project Setup (`/project/setup/weekoff`)
- **Description:** Accommodates operational diversity. When enabled, each project defines its own roster schedule (e.g. 6-day work weeks for construction/field sites, 5-day weeks for software development).

### 21. External Client Officer Read-Only Access
- **Module:** Project Setup (`/project/setup/officers`)
- **Description:** Allows government or client nodal officers to log in with view-only credentials to verify on-site contractor presence without exposing internal employee salaries or company settings.

### 22. Unassigned / Bench Engineer Pool
- **Module:** Team Roster (`/team`)
- **Description:** Activates the "Bench" department view. Engineers between project assignments can be placed on bench status and tracked collectively until redeployed to a client project.

### 23. PM Device Unbind Permission
- **Module:** Team Roster (`/team`)
- **Description:** Controls authority over hardware security. When enabled, PMs can reset an employee's bound phone directly from the team table. When disabled, device unbinding requires a ticket to Super Admin.

### 24. Automated Keycloak SSO Onboarding
- **Module:** Access & Authentication (`/access`)
- **Description:** Reduces admin overhead. When enabled, any employee authenticated via corporate Keycloak SSO is automatically created in the attendance roster with default role permissions.

### 25. Payroll Working Day Formula
- **Module:** Reports & Payroll Export (`/summary`, `/export/monthly.xlsx`)
- **Description:** Switches the monthly salary computation base. "Actual Working Days" deducts pay based strictly on missing scheduled days, while "30 Calendar Days Flat" divides monthly salary by 30 regardless of month length.

### 26. Overtime (OT) Hours Tracking
- **Module:** Reports & Payroll Export (`/summary`)
- **Description:** When enabled, the system computes hours logged beyond 8 hours as overtime and displays them in dedicated export columns. When disabled, overtime calculation is omitted.

### 27. Sensitive GPS Data Masking in Exports
- **Module:** Reports & Payroll Export (`/export/daily.xlsx`)
- **Description:** Ensures compliance with privacy standards. When enabled, exported Excel sheets show site names and times, hiding exact GPS coordinates and hardware serial numbers from third-party recipients.

---

# PART 2: Automated Email Events Configuration Matrix

Every email notification dispatched by the attendance system is individually controllable via toggle switches in the Admin UI under **"Email & Notifications Settings"**.

## 2.1 Email Events Summary Matrix

| Feature Toggle | When Enabled | When Disabled |
| :--- | :--- | :--- |
| **Email: Project Assignment (To Employee)** | Sends an email to the employee when assigned or transferred to a project with site locations, radius, and shift timings. | Assignment is updated in the database silently without dispatching an email to the employee. |
| **Email: New Team Member Alert (To PM)** | Sends an immediate email notification to the Project Manager whenever a new engineer is added to their project team. | PM receives no email; they view new team members directly on the `/team` roster. |
| **Email: Daily Check-In Confirmation (To Employee)** | Dispatches a confirmation email to the employee upon their successful morning check-in (timestamp, site, status). | Check-in confirmation emails are suppressed to prevent daily inbox clutter. |
| **Email: Daily Check-Out & Summary (To Employee)** | Dispatches an evening email to the employee upon check-out showing total hours worked and break durations. | Check-out confirmation emails are suppressed. |
| **Email: Leave Application Submitted (To PM & TL)** | Immediately alerts the Project Manager and Team Lead via email when a team member applies for leave. | Leave requests appear silently in the PM's approval queue without triggering emails. |
| **Email: Leave Application Acknowledgement (To Employee)** | Sends an acknowledgement receipt to the employee confirming their leave request was submitted to PM. | Suppresses employee leave application submission receipts. |
| **Email: Leave Decision - Approved / Rejected (To Employee)** | Instantly emails the employee when their leave request is approved or rejected by the manager with remarks. | Employee is not emailed; they check decision status on the self-service web portal. |
| **Email: Attendance Dispute Filed (To PM)** | Sends an urgent email notification to the Project Manager the moment an employee logs a punch dispute from mobile. | Disputes appear in the PM review queue without sending individual alert emails. |
| **Email: Attendance Dispute Resolved (To Employee)** | Emails the employee when their punch dispute has been reviewed and corrected by the Project Manager. | Suppresses dispute resolution emails. |
| **Email: Morning Absentee Digest 10:30 AM (To PM)** | Automatically emails the PM at 10:30 AM listing all project engineers who have not punched in today. | Suppresses morning absentee alert emails. |
| **Email: Evening Attendance Summary 19:00 PM (To PM & Mgmt)** | Dispatches a daily consolidated HTML attendance and working hours report to managers at 19:00 PM. | Suppresses daily evening summary reports. |
| **Email: Chronic Late Arrival Warning (To Employee)** | Auto-sends an advisory warning email to employees who arrive late more than the threshold (e.g. > 3 times a month). | Suppresses automated late arrival warning emails. |

---

## 2.2 Detailed Descriptions for Email Events

### 1. Email: Project Assignment (To Employee)
- **Recipient:** Assigned Employee
- **Trigger:** An admin or PM assigns or transfers an employee to a project via `/team/update` or `/admin/transfer_engineer`.
- **Contents:** Clean branded email welcoming the employee to the project, outlining the assigned work sites, GPS coordinates, allowed radius, standard shift timings (`09:30 - 18:30`), weekly off schedule, and direct contact of their reporting Project Manager.

### 2. Email: New Team Member Alert (To Project Manager)
- **Recipient:** Project Manager & Team Lead
- **Trigger:** A new user is allocated to their project team.
- **Contents:** Alerts the PM that an engineer has been assigned to their roster, including employee name, email, role title, effective date, and assigned work site.

### 3. Email: Daily Check-In Confirmation (To Employee)
- **Recipient:** Checking-in Employee
- **Trigger:** Employee successfully clocks in (`ENTER`) via Android app geofencing or web portal.
- **Contents:** Real-time confirmation showing punch time (e.g. `10:38 AM`), work site name (`Noida Office`), proximity (`3m from center`), and verified geofence badge.

### 4. Email: Daily Check-Out & Summary (To Employee)
- **Recipient:** Checking-out Employee
- **Trigger:** Employee clocks out (`EXIT`) at the end of their shift.
- **Contents:** Daily shift summary displaying arrival time, departure time, net elapsed working duration (e.g. `8h 14m`), break duration, and shift completion badge.

### 5. Email: Leave Application Submitted (To PM & TL)
- **Recipient:** Project Manager & Team Lead
- **Trigger:** Employee applies for Advance Leave or Emergency Leave via `/me/leave/apply`.
- **Contents:** Notification displaying applicant name, leave dates, leave category (Casual, Sick, LWP), duration (Full Day / Half Day), reason/remarks, and direct "Review & Decide in Portal" action link.

### 6. Email: Leave Application Acknowledgement (To Employee)
- **Recipient:** Applying Employee
- **Trigger:** Employee submits a leave request.
- **Contents:** Confirmation that their request has been successfully recorded in the system and routed to their reporting manager for review.

### 7. Email: Leave Decision - Approved / Rejected (To Employee)
- **Recipient:** Employee
- **Trigger:** PM or HR decides on a leave request (`/leaves/decide`).
- **Contents:** Clear notification of approval or rejection, manager's written feedback or justification, and updated available leave balance.

### 8. Email: Attendance Dispute Filed (To PM)
- **Recipient:** Project Manager
- **Trigger:** Employee reports an issue with today's or past punch via the mobile app ("Report to PM").
- **Contents:** High-priority notice outlining date of dispute, issue category (e.g. GPS inaccurate, field visit, phone battery died), employee's written explanation, and a direct link to the review table.

### 9. Email: Attendance Dispute Resolved (To Employee)
- **Recipient:** Employee
- **Trigger:** PM reviews and resolves a dispute (`/review/dispute`).
- **Contents:** Notification that their dispute has been resolved, showing updated punch-in/out times and verification status.

### 10. Email: Morning Absentee Digest 10:30 AM (To PM)
- **Recipient:** Project Manager
- **Trigger:** Daily cron schedule triggers at 10:30 AM (Monday through Saturday).
- **Contents:** Automated digest of scheduled project members who have neither checked in nor submitted an approved leave, allowing frontline managers to quickly check on missing personnel.

### 11. Email: Evening Attendance Summary 19:00 PM (To PM & Management)
- **Recipient:** Project Managers and designated distribution list (`SUMMARY_TO`)
- **Trigger:** Daily cron schedule triggers at 19:00 PM.
- **Contents:** Comprehensive tabular HTML report covering present count, absent count, on-leave count, total hours worked per engineer, and stepped-out break durations.

### 12. Email: Chronic Late Arrival Warning (To Employee)
- **Recipient:** Employee (CC Project Manager)
- **Trigger:** System detects an employee has arrived past the 15-minute grace period more than 3 times in a calendar month.
- **Contents:** Automated, polite advisory outlining the dates and arrival times of late punches, encouraging adherence to shift schedules.

---

# PART 3: Mobile Application Configurable Features

## 3.1 Summary Matrix

| Feature Toggle | When Enabled | When Disabled |
| :--- | :--- | :--- |
| **Dispute / Issue Reporting** | Displays "Something wrong with today's punch? Report to PM" and "Report Dispute" on Today and History tabs. | Completely hides all dispute reporting buttons and dialogs from the mobile app. |
| **Manual "Check Now" Button** | Shows the "Check Now" button inside the live geofence card for on-demand GPS verification. | Hides the manual button; the app marks attendance strictly via passive background geofencing. |
| **Geofence Activity Accordion** | Displays the "Today's Geofence Activity" timeline card showing ENTER/EXIT history. | Completely hides the raw geofence activity card for a simpler, distraction-free dashboard. |
| **Geofence Accordion Default State** | The geofence activity accordion opens in expanded view automatically on launch. | The accordion is collapsed by default, requiring a tap to expand. |
| **Maximum Event Preview Count** | Limits initial events to the configured count (e.g. 3) with a "View all X events" toggle. | Shows all events in a single continuous scrollable list without a preview cap. |
| **Offline Punch Mode** | Allows punches to be recorded without network connectivity and saved to an encrypted local queue. | Punches strictly require active internet; offline punches fail with a connection error. |
| **Strict Device Binding** | Rejects login and stops background tracking if the phone's hardware ID does not match the bound device. | Allows logging in and tracking from any phone without hardware ID restrictions. |
| **Battery Optimization Advisory Banner** | Shows the warning button directing users to set battery optimization to "Unrestricted" in Android settings. | Suppresses the battery optimization advisory banner completely. |
| **Mock GPS / Fake Location Blocker** | Immediately rejects and flags punches originating from fake GPS or developer mock location providers. | Soft warning only; does not block punches (useful during lab testing). |
| **GPS Accuracy Cutoff Threshold** | Rejects location fixes whose uncertainty exceeds the threshold (e.g. ±35m) to prevent drift errors. | Accepts all location fixes reported by the Android OS regardless of accuracy value. |
| **Continuous Dwell-Time Buffer** | Requires employee to remain inside geofence continuously for N minutes (e.g. 2 min) before confirming punch. | Fires punch-in immediately upon the first GPS coordinate fix detected inside boundary. |
| **Exit / Step-Out Hysteresis Window** | Requires employee to remain outside geofence for N minutes (e.g. 3 min) before marking a stepped-out break. | Marks stepped-out break instantly upon the first coordinate reading outside boundary. |
| **Home Screen Broadcast Banner** | Displays an admin-configured high-priority announcement card at the top of the mobile screen. | Hides the announcement card from the mobile home screen. |

---

## 3.2 Detailed Descriptions for Mobile Application Features

### 1. Dispute / Issue Reporting
- **Screen:** Today Tab & History Tab
- **Description:** Allows employees to raise discrepancies (e.g., "GPS was delayed", "Was at client office"). When enabled, interactive buttons open an issue submission dialog with pre-set categories. When disabled, the UI is hidden, preventing dispute submissions when HR is not processing disputes.

### 2. Manual "Check Now" Button
- **Screen:** Today Tab (Live Geofence Card)
- **Description:** Provides reassurance to users by allowing them to tap a button to immediately trigger high-accuracy GPS and evaluate proximity. When disabled, the button is removed, and the app operates 100% silently in the background.

### 3. Geofence Activity Accordion
- **Screen:** Today Tab
- **Description:** Dictates whether employees can see their raw event logs (e.g. 10:38 ENTER, 10:44 EXIT). When enabled, builds transparency. When disabled, employees only see high-level summary metrics (In Time, Out Time, Hours Worked), hiding raw triggers.

### 4. Geofence Accordion Default State
- **Screen:** Today Tab
- **Description:** Determines visual cleanliness. When set to `False` (default), the accordion remains closed on screen load, keeping the UI compact. When set to `True`, the list is expanded automatically on startup.

### 5. Maximum Event Preview Count
- **Screen:** Today Tab
- **Description:** Solves vertical screen clutter. Limits the displayed events to a neat preview (e.g., 3 events). If an employee steps in and out 10 times, the card shows 3 items plus a "View all 10 events" toggle button.

### 6. Offline Punch Mode
- **Screen:** App-wide Sync Engine
- **Description:** Critical for basements, remote sites, or poor cellular connectivity. When enabled, punches are signed, timestamped via system clock, and queued in Room SQLite. When network returns, they sync automatically. When disabled, punches are refused without internet.

### 7. Strict Device Binding
- **Screen:** Authentication & Background Service
- **Description:** Prevents buddy-punching. When enabled, the app binds the employee's account to their physical phone hardware ID. Logging in on a colleague's phone is blocked. When disabled, users can log in from any Android smartphone.

### 8. Battery Optimization Advisory Banner
- **Screen:** Profile Tab & Home Banner
- **Description:** Android OS aggressively kills background location services unless battery usage is set to "Unrestricted". When enabled, the app displays a prominent button opening the exact Android system settings page. When disabled, the prompt is suppressed.

### 9. Mock GPS / Fake Location Blocker
- **Screen:** Background Tracking Engine
- **Description:** Prevents GPS spoofing apps (e.g., "Fake GPS Location"). When enabled, any coordinate marked as mock provider by Android Location API is discarded and flagged as a security violation.

### 10. GPS Accuracy Cutoff Threshold
- **Screen:** Location Service Filter
- **Description:** Sets maximum tolerable GPS error margin in meters (e.g. `35m`). If cell-tower triangulation provides a weak fix of `±100m`, the app rejects it and waits for fine GPS satellite lock, eliminating false triggers.

### 11. Continuous Dwell-Time Buffer
- **Screen:** Geofence Decision Engine
- **Description:** Prevents "drive-by" check-ins. If an employee drives or walks past the office building without entering, a 2-minute buffer ensures they must physically remain inside the boundary for 120 seconds before an attendance punch is booked.

### 12. Exit / Step-Out Hysteresis Window
- **Screen:** Geofence Decision Engine
- **Description:** Prevents false break deductions caused by temporary GPS drift (e.g., sitting near a window where satellite reception fluctuates). An exit is only registered after the device stays outside for more than 3 continuous minutes.

### 13. Home Screen Broadcast Banner
- **Screen:** Today Tab (Top Banner)
- **Description:** Enables administrators to broadcast urgent or informative notices to all mobile app users instantly (e.g., "Office will close at 3 PM today for Diwali celebrations"). Admins update text on the web, and it renders on mobile devices within minutes.

---

# PART 4: Database & API Implementation Architecture

### 4.1 Database Table Schema (`app_config`)
```sql
CREATE TABLE IF NOT EXISTS app_config (
    key TEXT PRIMARY KEY,
    category TEXT NOT NULL,          -- 'mobile', 'web_review', 'web_leaves', 'web_approvals', 'web_projects', 'web_team', 'web_email', 'web_export'
    data_type TEXT NOT NULL,         -- 'boolean', 'integer', 'float', 'string', 'time'
    value TEXT NOT NULL,             -- 'true', 'false', '35', '09:30', etc.
    default_value TEXT NOT NULL,
    label TEXT NOT NULL,
    description TEXT NOT NULL,
    requires_client_restart INTEGER DEFAULT 0,
    updated_by TEXT,
    updated_at TEXT
);
```

### 4.2 Dynamic Remote Config Endpoint (`/api/m/config`)
Returns an optimized JSON object of active mobile flags:
```json
{
  "ok": true,
  "config": {
    "dispute_reporting_enabled": true,
    "check_now_button_enabled": true,
    "events_accordion_visible": true,
    "events_accordion_default_open": false,
    "max_events_preview_count": 3,
    "offline_punch_allowed": true,
    "strict_device_binding": true,
    "battery_prompt_enabled": true,
    "mock_location_blocking": true,
    "gps_accuracy_cutoff_m": 35,
    "dwell_time_buffer_mins": 2,
    "exit_hysteresis_mins": 3,
    "banner_announcement_active": false,
    "banner_announcement_text": ""
  }
}
```
