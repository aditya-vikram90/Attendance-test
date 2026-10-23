# Attendance & Workforce Management System
## Comprehensive QA Manual Test Case Suite & Execution Matrix

---

### Document Overview
- **Document Title:** Attendance System — Micro-Level QA Manual Test Suite
- **Companion Spreadsheet:** [`ATTENDANCE_SYSTEM_TEST_CASES.xlsx`](file:///home/user/Desktop/Projects/management/attendance/docs/ATTENDANCE_SYSTEM_TEST_CASES.xlsx) (Standard Multi-Sheet Test Tracker)
- **Applicable Environments:** Local Test Instance (`http://localhost:8000`) & Staging/Production (`https://pm.keenable.io/attendance/`)
- **Default Test Password:** `Keenable@2026` (Identical for all test accounts)
- **Primary Test Project:** Project 2 — UPSC (ID: `2`)
- **Coverage Scope:** 88 Micro-Level Test Scenarios across 10 functional modules.

---

## Quick Reference: Test Credentials Directory

| Identifier | Name | Email / Username | Password | Role / Scope |
| :--- | :--- | :--- | :--- | :--- |
| **USR-ADM** | Ashish Sharma | `ashish.kumar1@fosteringlinux.com` | `Keenable@2026` | Admin / All Projects |
| **USR-PM0** | Moumita Roy | `moumita.roy@fosteringlinux.com` | `Keenable@2026` | PM Level 0 (Primary Lead) / Project 2 |
| **USR-PM1** | Mohd Imran | `imran.mohd@fosteringlinux.com` | `Keenable@2026` | PM Level 1 (Deputy Lead) / Project 2 |
| **USR-PM2** | Anjali Mehta | `anjali.mehta@fosteringlinux.com` | `Keenable@2026` | PM Level 2 (Senior PM) / Project 2 |
| **USR-PM3** | Amit Roy | `amit.roy@fosteringlinux.com` | `Keenable@2026` | PM Level 3 (Delivery Head) / Project 2 |
| **USR-ENG1** | Neha Verma | `neha.verma@fosteringlinux.com` | `Keenable@2026` | Engineer / Project 2 |
| **USR-ENG2** | Pooja Nair | `pooja.nair@fosteringlinux.com` | `Keenable@2026` | Engineer / Project 2 |
| **USR-ENG3** | Rohit Gupta | `rohit.gupta@fosteringlinux.com` | `Keenable@2026` | Engineer / Project 2 |
| **USR-ENG4** | Manoj Tiwari | `manoj.tiwari@fosteringlinux.com` | `Keenable@2026` | Engineer / Project 2 |
| **USR-ENG5** | Priya Sharma | `priya.sharma@fosteringlinux.com` | `Keenable@2026` | Engineer / Project 2 |
| **USR-ENG6** | Vikram Singh | `vikram.singh@fosteringlinux.com` | `Keenable@2026` | Engineer / Project 2 |

---

## Functional Suite: Authentication

### TC-AUTH-001: Valid SSO Login for Admin
- **Module / Screen:** Authentication &mdash; `Login Screen`
- **Target Persona:** Admin (`ashish.kumar1@fosteringlinux.com`)
- **Priority:** `P1`
- **Pre-conditions:** User exists in Keycloak and app_users
- **Test Steps:**
  1. Open incognito browser and navigate to /login.
  2. In Keycloak login UI, enter username and password Keenable@2026.
  3. Click Sign In.
- **Test Data:** `Username: ashish.kumar1@fosteringlinux.com, Password: Keenable@2026`
- **Expected Result:**
  Login succeeds without OTP prompts. Redirects to / (Enter Attendance). Header displays 'Ashish Sharma · Admin' with all 12 nav links visible.

### TC-AUTH-002: Valid SSO Login for PM0 (Lead)
- **Module / Screen:** Authentication &mdash; `Login Screen`
- **Target Persona:** PM Level 0 (`moumita.roy@fosteringlinux.com`)
- **Priority:** `P1`
- **Pre-conditions:** PM0 configured on Project 2
- **Test Steps:**
  1. Navigate to /login.
  2. Enter username and password Keenable@2026.
  3. Click Sign In.
- **Test Data:** `Username: moumita.roy@fosteringlinux.com, Password: Keenable@2026`
- **Expected Result:**
  Login succeeds. Redirects to /. Header displays 'Moumita Roy · TL/PM'. Nav shows 11 links (Access is hidden).

### TC-AUTH-003: Valid SSO Login for Engineer
- **Module / Screen:** Authentication &mdash; `Login Screen`
- **Target Persona:** Engineer (`neha.verma@fosteringlinux.com`)
- **Priority:** `P1`
- **Pre-conditions:** Engineer assigned to Project 2
- **Test Steps:**
  1. Navigate to /login.
  2. Enter username and password Keenable@2026.
  3. Click Sign In.
- **Test Data:** `Username: neha.verma@fosteringlinux.com, Password: Keenable@2026`
- **Expected Result:**
  Login succeeds. Automatically redirected directly to /me (My attendance). Header shows 3 links: My attendance, My trends, My summary.

### TC-AUTH-004: Invalid Password Rejection
- **Module / Screen:** Authentication &mdash; `Login Screen`
- **Target Persona:** Any (`moumita.roy@fosteringlinux.com`)
- **Priority:** `P1`
- **Pre-conditions:** App is online
- **Test Steps:**
  1. Navigate to /login.
  2. Enter valid email and incorrect password.
  3. Click Sign In.
- **Test Data:** `Password: WrongPassword@123`
- **Expected Result:**
  Keycloak login page displays error alert: 'Invalid username or password'. No session token issued; user remains unauthenticated.

### TC-AUTH-005: Invalid Username Rejection
- **Module / Screen:** Authentication &mdash; `Login Screen`
- **Target Persona:** Any (`nonexistent.user@fosteringlinux.com`)
- **Priority:** `P2`
- **Pre-conditions:** App is online
- **Test Steps:**
  1. Navigate to /login.
  2. Enter unregistered email and valid password format.
  3. Click Sign In.
- **Test Data:** `Username: nonexistent.user@fosteringlinux.com`
- **Expected Result:**
  Keycloak displays 'Invalid username or password'. No redirect occurs.

### TC-AUTH-006: Single Sign-Out & Session Termination
- **Module / Screen:** Authentication &mdash; `Global Header`
- **Target Persona:** Admin / PM / Eng (`moumita.roy@fosteringlinux.com`)
- **Priority:** `P1`
- **Pre-conditions:** User is actively logged in
- **Test Steps:**
  1. Click 'Sign out' link in top-right header.
  2. Attempt to press browser 'Back' button.
  3. Attempt to navigate directly to http://localhost:8000/.
- **Test Data:** `N/A`
- **Expected Result:**
  Session cookie is destroyed. Pressing Back or hitting protected URL redirects immediately to Keycloak login page.

### TC-AUTH-007: Deep Link Protected Redirection
- **Module / Screen:** Authentication &mdash; `Navigation`
- **Target Persona:** Engineer (`neha.verma@fosteringlinux.com`)
- **Priority:** `P2`
- **Pre-conditions:** Logged out
- **Test Steps:**
  1. Copy URL http://localhost:8000/me.
  2. Paste into fresh incognito tab.
  3. Log in when prompted by Keycloak.
- **Test Data:** `Direct URL: /me`
- **Expected Result:**
  Upon successful login, user is forwarded directly to /me rather than default landing.

### TC-AUTH-008: Password Change Functionality
- **Module / Screen:** Authentication &mdash; `Login Screen`
- **Target Persona:** Engineer (`neha.verma@fosteringlinux.com`)
- **Priority:** `P2`
- **Pre-conditions:** User logged into Keycloak account console
- **Test Steps:**
  1. Open Keycloak account management page.
  2. Navigate to Signing In -> Password.
  3. Submit password change.
- **Test Data:** `New Password: NewPass@2026!`
- **Expected Result:**
  Password update succeeds via writeable Keycloak User Storage SPI. Next login requires new password.

## Functional Suite: RBAC

### TC-RBAC-001: Engineer Forbidden from Daily Entry (/)
- **Module / Screen:** RBAC &mdash; `URL Guarding`
- **Target Persona:** Engineer (`neha.verma@fosteringlinux.com`)
- **Priority:** `P1`
- **Pre-conditions:** Logged in as Neha Verma
- **Test Steps:**
  1. Inspect header navbar; verify 'Enter attendance' is not present.
  2. Manually enter http://localhost:8000/ in browser address bar.
- **Test Data:** `URL: /`
- **Expected Result:**
  Server intercepts request and responds with HTTP 403 Forbidden. No attendance table or managerial controls rendered.

### TC-RBAC-002: Engineer Forbidden from PM Approvals (/approvals)
- **Module / Screen:** RBAC &mdash; `URL Guarding`
- **Target Persona:** Engineer (`neha.verma@fosteringlinux.com`)
- **Priority:** `P1`
- **Pre-conditions:** Logged in as Neha Verma
- **Test Steps:**
  1. Manually enter http://localhost:8000/approvals in address bar.
- **Test Data:** `URL: /approvals`
- **Expected Result:**
  Server responds with HTTP 403 Forbidden.

### TC-RBAC-003: Engineer Forbidden from Leaves Dashboard (/leaves)
- **Module / Screen:** RBAC &mdash; `URL Guarding`
- **Target Persona:** Engineer (`neha.verma@fosteringlinux.com`)
- **Priority:** `P1`
- **Pre-conditions:** Logged in as Neha Verma
- **Test Steps:**
  1. Manually enter http://localhost:8000/leaves in address bar.
- **Test Data:** `URL: /leaves`
- **Expected Result:**
  Server responds with HTTP 403 Forbidden.

### TC-RBAC-004: Engineer Forbidden from Phone Check-ins (/review)
- **Module / Screen:** RBAC &mdash; `URL Guarding`
- **Target Persona:** Engineer (`neha.verma@fosteringlinux.com`)
- **Priority:** `P1`
- **Pre-conditions:** Logged in as Neha Verma
- **Test Steps:**
  1. Manually enter http://localhost:8000/review in address bar.
- **Test Data:** `URL: /review`
- **Expected Result:**
  Server responds with HTTP 403 Forbidden.

### TC-RBAC-005: Engineer Forbidden from Project Setup (/project/setup)
- **Module / Screen:** RBAC &mdash; `URL Guarding`
- **Target Persona:** Engineer (`neha.verma@fosteringlinux.com`)
- **Priority:** `P1`
- **Pre-conditions:** Logged in as Neha Verma
- **Test Steps:**
  1. Manually enter http://localhost:8000/project/setup in address bar.
- **Test Data:** `URL: /project/setup`
- **Expected Result:**
  Server responds with HTTP 403 Forbidden.

### TC-RBAC-006: Engineer Forbidden from Team Management (/team)
- **Module / Screen:** RBAC &mdash; `URL Guarding`
- **Target Persona:** Engineer (`neha.verma@fosteringlinux.com`)
- **Priority:** `P1`
- **Pre-conditions:** Logged in as Neha Verma
- **Test Steps:**
  1. Manually enter http://localhost:8000/team in address bar.
- **Test Data:** `URL: /team`
- **Expected Result:**
  Server responds with HTTP 403 Forbidden.

### TC-RBAC-007: Engineer Forbidden from Access Management (/access)
- **Module / Screen:** RBAC &mdash; `URL Guarding`
- **Target Persona:** Engineer (`neha.verma@fosteringlinux.com`)
- **Priority:** `P1`
- **Pre-conditions:** Logged in as Neha Verma
- **Test Steps:**
  1. Manually enter http://localhost:8000/access in address bar.
- **Test Data:** `URL: /access`
- **Expected Result:**
  Server responds with HTTP 403 Forbidden.

### TC-RBAC-008: Engineer Restricted to Self Data on Summary & Trends
- **Module / Screen:** RBAC &mdash; `Data Isolation`
- **Target Persona:** Engineer (`neha.verma@fosteringlinux.com`)
- **Priority:** `P1`
- **Pre-conditions:** Logged in as Neha Verma
- **Test Steps:**
  1. Navigate to /summary and /trends.
  2. Attempt to add query parameter ?user=35 (Rohit Gupta).
- **Test Data:** `Query: ?user=35`
- **Expected Result:**
  Server overrides user parameter and renders strictly Neha Verma's personal summary and trends.

### TC-RBAC-009: PM Forbidden from Access Management (/access)
- **Module / Screen:** RBAC &mdash; `URL Guarding`
- **Target Persona:** PM Level 0 (`moumita.roy@fosteringlinux.com`)
- **Priority:** `P1`
- **Pre-conditions:** Logged in as Moumita Roy
- **Test Steps:**
  1. Verify 'Access' link is omitted from header.
  2. Manually enter http://localhost:8000/access in address bar.
- **Test Data:** `URL: /access`
- **Expected Result:**
  Server responds with HTTP 403 Forbidden.

### TC-RBAC-010: PM Forbidden from Unauthorized Projects
- **Module / Screen:** RBAC &mdash; `Project Boundary`
- **Target Persona:** PM Level 0 (`moumita.roy@fosteringlinux.com`)
- **Priority:** `P1`
- **Pre-conditions:** Moumita Roy is assigned to Project 2 (UPSC) only
- **Test Steps:**
  1. Open /?project=1 (NCLT).
  2. Attempt to submit attendance POST to /save for project 1.
- **Test Data:** `Project: 1`
- **Expected Result:**
  Server rejects access with HTTP 403 Forbidden. PM cannot view or modify rosters outside assigned scope.

## Functional Suite: Daily Attendance

### TC-ATT-001: Load Attendance Grid for Current Day
- **Module / Screen:** Daily Attendance &mdash; `Enter Attendance (/)`
- **Target Persona:** PM Level 0 (`moumita.roy@fosteringlinux.com`)
- **Priority:** `P1`
- **Pre-conditions:** Logged in as Moumita Roy
- **Test Steps:**
  1. Navigate to /.
  2. Select Project 'UPSC' and current date (today).
- **Test Data:** `Date: today, Project: 2`
- **Expected Result:**
  Roster table loads with all active engineers. Header shows project tabs. Default shift info displayed.

### TC-ATT-002: Mark and Save Present Status with In/Out Times
- **Module / Screen:** Daily Attendance &mdash; `Enter Attendance (/)`
- **Target Persona:** PM Level 0 (`moumita.roy@fosteringlinux.com`)
- **Priority:** `P1`
- **Pre-conditions:** Current day selected
- **Test Steps:**
  1. For Neha Verma, enter In: 09:30, Out: 18:30.
  2. Enter Remarks: 'Normal duty'.
  3. Click 'Save UPSC' button.
- **Test Data:** `In: 09:30, Out: 18:30, Remarks: Normal duty`
- **Expected Result:**
  Page reloads with green flash message 'Attendance saved.'. Neha Verma shows Status pill 'Present' (green) and worked hours '9.0h'.

### TC-ATT-003: Auto-Computation of Late Arrival Time
- **Module / Screen:** Daily Attendance &mdash; `Enter Attendance (/)`
- **Target Persona:** PM Level 0 (`moumita.roy@fosteringlinux.com`)
- **Priority:** `P1`
- **Pre-conditions:** Shift start 09:30 with 15m grace (cutoff 09:45)
- **Test Steps:**
  1. For Rohit Gupta, enter In: 10:15, Out: 18:30.
  2. Click 'Save UPSC'.
- **Test Data:** `In: 10:15, Out: 18:30`
- **Expected Result:**
  Table displays orange warning text in 'Late by' column showing '+0:45' (45 minutes late).

### TC-ATT-004: Auto-Computation of Short Hours Deficit
- **Module / Screen:** Daily Attendance &mdash; `Enter Attendance (/)`
- **Target Persona:** PM Level 0 (`moumita.roy@fosteringlinux.com`)
- **Priority:** `P2`
- **Pre-conditions:** Standard shift is 9 hours
- **Test Steps:**
  1. For Pooja Nair, enter In: 09:30, Out: 15:30 (6.0 hours worked).
  2. Click 'Save UPSC'.
- **Test Data:** `In: 09:30, Out: 15:30`
- **Expected Result:**
  Hours column displays '6.0h'; 'Short by' column displays orange warning text '-3:00'.

### TC-ATT-005: Night Shift Hours Calculation Across Midnight
- **Module / Screen:** Daily Attendance &mdash; `Enter Attendance (/)`
- **Target Persona:** PM Level 0 (`moumita.roy@fosteringlinux.com`)
- **Priority:** `P2`
- **Pre-conditions:** Evening/Night shift
- **Test Steps:**
  1. For Vikram Singh, enter In: 21:00, Out: 05:30 (next morning).
  2. Click 'Save UPSC'.
- **Test Data:** `In: 21:00, Out: 05:30`
- **Expected Result:**
  System detects overnight span and computes worked hours as '8.5h' (not negative hours).

### TC-ATT-006: Mark Leave Type and Planned Status
- **Module / Screen:** Daily Attendance &mdash; `Enter Attendance (/)`
- **Target Persona:** PM Level 0 (`moumita.roy@fosteringlinux.com`)
- **Priority:** `P1`
- **Pre-conditions:** Current day selected
- **Test Steps:**
  1. For Manoj Tiwari, select Leave type: 'PL', Planned: 'Planned'.
  2. Select Task handled by: 'Priya Sharma'.
  3. Click 'Save UPSC'.
- **Test Data:** `Leave: PL, Planned: Planned, Cover: Priya Sharma`
- **Expected Result:**
  Status pill updates to blue 'Leave'. Priya Sharma recorded as cover colleague.

### TC-ATT-007: Dynamic Disablement of Colleagues on Leave from Cover
- **Module / Screen:** Daily Attendance &mdash; `Enter Attendance (/)`
- **Target Persona:** PM Level 0 (`moumita.roy@fosteringlinux.com`)
- **Priority:** `P1`
- **Pre-conditions:** Pooja Nair marked on leave today
- **Test Steps:**
  1. In Pooja Nair's row, select Leave: 'CL'.
  2. Inspect 'Task handled by' dropdown in Manoj Tiwari's row.
- **Test Data:** `Pooja Nair on leave`
- **Expected Result:**
  Dropdown option for Pooja Nair dynamically appends '(on leave)' and is disabled. Selecting Pooja Nair is blocked with red border.

### TC-ATT-008: Mark Absent (Leaving Times Empty)
- **Module / Screen:** Daily Attendance &mdash; `Enter Attendance (/)`
- **Target Persona:** PM Level 0 (`moumita.roy@fosteringlinux.com`)
- **Priority:** `P2`
- **Pre-conditions:** Current day selected
- **Test Steps:**
  1. For Neha Verma, clear In/Out times and leave dropdowns empty.
  2. Click 'Save UPSC'.
- **Test Data:** `In: empty, Out: empty`
- **Expected Result:**
  Neha Verma displays red Status pill 'Absent (No info)'.

### TC-ATT-009: Max Length Validation on Remarks Input
- **Module / Screen:** Daily Attendance &mdash; `Enter Attendance (/)`
- **Target Persona:** PM Level 0 (`moumita.roy@fosteringlinux.com`)
- **Priority:** `P3`
- **Pre-conditions:** Current day selected
- **Test Steps:**
  1. In Remarks input, paste text exceeding 300 characters.
  2. Observe input behavior.
- **Test Data:** `Text > 300 chars`
- **Expected Result:**
  Input field has maxlength='300'; truncates input automatically at 300 characters.

### TC-ATT-010: Strict Past-Date Lock Enforcement for PM
- **Module / Screen:** Daily Attendance &mdash; `Enter Attendance (/)`
- **Target Persona:** PM Level 0 (`moumita.roy@fosteringlinux.com`)
- **Priority:** `P1`
- **Pre-conditions:** Logged in as Moumita Roy
- **Test Steps:**
  1. Change date picker to a past date (e.g. 2026-10-15).
  2. Inspect the page.
- **Test Data:** `Date: past date`
- **Expected Result:**
  Red alert banner appears: '🔒 Attendance Locked: Previous dates are locked for Team Leads / PMs...'. All input fields are disabled/read-only.

### TC-ATT-011: PM Direct POST Bypass Rejection on Past Date
- **Module / Screen:** Daily Attendance &mdash; `Enter Attendance (/)`
- **Target Persona:** PM Level 0 (`moumita.roy@fosteringlinux.com`)
- **Priority:** `P1`
- **Pre-conditions:** Logged in as Moumita Roy
- **Test Steps:**
  1. Attempt to dispatch POST request to /save with date=2026-10-15 and modified times.
- **Test Data:** `POST /save, day=2026-10-15`
- **Expected Result:**
  Server executes can_edit_attendance(); rejects with HTTP 403 Forbidden ('Past days can be changed by an admin only').

### TC-ATT-012: Admin Override: Edit and Save Past-Date Attendance
- **Module / Screen:** Daily Attendance &mdash; `Enter Attendance (/)`
- **Target Persona:** Admin (`ashish.kumar1@fosteringlinux.com`)
- **Priority:** `P1`
- **Pre-conditions:** Logged in as Ashish Sharma
- **Test Steps:**
  1. Open / and change date to past date 2026-10-15.
  2. Note input fields are fully enabled (no lock banner).
  3. Edit Neha Verma's In Time to 09:30 and click Save.
- **Test Data:** `Date: 2026-10-15, In: 09:30`
- **Expected Result:**
  Flash confirms save. Record updates successfully in PostgreSQL attendance table with updated_by='ashish.kumar1@fosteringlinux.com'.

### TC-ATT-013: Inline Approval of Pending Self-Submitted Attendance
- **Module / Screen:** Daily Attendance &mdash; `Enter Attendance (/)`
- **Target Persona:** PM Level 0 (`moumita.roy@fosteringlinux.com`)
- **Priority:** `P1`
- **Pre-conditions:** Engineer submitted self-entry; row highlighted in amber
- **Test Steps:**
  1. On /, locate row with 'Pending' pill.
  2. Click inline green button '✓ Approve'.
- **Test Data:** `Action: Single approve`
- **Expected Result:**
  Row updates immediately to green '✓ Verified' pill. Approval status changes to 'Approved'.

### TC-ATT-014: Inline Rejection of Self-Submitted Attendance with Reason
- **Module / Screen:** Daily Attendance &mdash; `Enter Attendance (/)`
- **Target Persona:** PM Level 0 (`moumita.roy@fosteringlinux.com`)
- **Priority:** `P2`
- **Pre-conditions:** Row with 'Pending' pill
- **Test Steps:**
  1. Click inline red button '✕ Reject'.
  2. In Reject Modal, leave reason empty and submit.
  3. Enter reason 'Timestamps do not match badge log' and submit.
- **Test Data:** `Rejection Reason: Badge mismatch`
- **Expected Result:**
  Empty reason triggers validation. Submitting with reason updates pill to red 'Rejected' with rejection note recorded.

## Functional Suite: Self-Service

### TC-ME-001: Engineer Landing Page Elements Verification
- **Module / Screen:** Self-Service &mdash; `My Attendance (/me)`
- **Target Persona:** Engineer (`neha.verma@fosteringlinux.com`)
- **Priority:** `P1`
- **Pre-conditions:** Logged in as Neha Verma
- **Test Steps:**
  1. Navigate to /me.
  2. Inspect header, shift details, and sections.
- **Test Data:** `URL: /me`
- **Expected Result:**
  Displays 'Neha Verma', role 'UI/UX & Frontend Engineer · UPSC', shift start note 'Your shift starts 09:30 · grace 15 min · shift 9 h lunch'. Two accordions present.

### TC-ME-002: Toggle Attendance Objection Accordion
- **Module / Screen:** Self-Service &mdash; `My Attendance (/me)`
- **Target Persona:** Engineer (`neha.verma@fosteringlinux.com`)
- **Priority:** `P2`
- **Pre-conditions:** On /me
- **Test Steps:**
  1. Click summary bar 'Raise an Attendance Objection / Grievance'.
  2. Click summary bar again.
- **Test Data:** `Click toggle`
- **Expected Result:**
  Accordion smoothly expands displaying objection form and history table. Arrow rotates 180 deg. Second click collapses accordion.

### TC-ME-003: Submit Attendance Objection for Past Date
- **Module / Screen:** Self-Service &mdash; `My Attendance (/me)`
- **Target Persona:** Engineer (`neha.verma@fosteringlinux.com`)
- **Priority:** `P1`
- **Pre-conditions:** On /me
- **Test Steps:**
  1. Expand objection accordion.
  2. Date: select 2026-10-16. Correct IN: 09:30, Correct OUT: 18:30.
  3. Reason: 'Card reader error during exit'.
  4. Click 'Raise Objection'.
- **Test Data:** `Day: 2026-10-16, IN: 09:30, OUT: 18:30, Reason: Card reader error`
- **Expected Result:**
  Flash message: 'Your objection was sent to your TL/PM. You will see the answer here.'. Record appears in 'Your Recent Objections' with pill 'Waiting for PM/TL'.

### TC-ME-004: Validation on Future Date in Objection Form
- **Module / Screen:** Self-Service &mdash; `My Attendance (/me)`
- **Target Persona:** Engineer (`neha.verma@fosteringlinux.com`)
- **Priority:** `P2`
- **Pre-conditions:** On /me
- **Test Steps:**
  1. In objection form, attempt to pick a future date.
  2. Inspect date input max attribute.
- **Test Data:** `Future date`
- **Expected Result:**
  Date picker HTML constraint max='today' prevents selecting future dates.

### TC-ME-005: Toggle Apply for Leave Accordion
- **Module / Screen:** Self-Service &mdash; `My Attendance (/me)`
- **Target Persona:** Engineer (`neha.verma@fosteringlinux.com`)
- **Priority:** `P2`
- **Pre-conditions:** On /me
- **Test Steps:**
  1. Click summary bar 'Apply for Leave'.
- **Test Data:** `Click toggle`
- **Expected Result:**
  Accordion expands revealing leave form, capacity forecast banner (#lvinfo), and 'My Leave Applications' table.

### TC-ME-006: Month Navigation & KPI Card Updates
- **Module / Screen:** Self-Service &mdash; `My Attendance (/me)`
- **Target Persona:** Engineer (`neha.verma@fosteringlinux.com`)
- **Priority:** `P2`
- **Pre-conditions:** On /me
- **Test Steps:**
  1. Locate Month picker input.
  2. Change month from 2026-10 to 2026-09.
  3. Observe page refresh.
- **Test Data:** `Month: 2026-09`
- **Expected Result:**
  Calendar table updates to show September 2026 dates. KPI cards (Present, Leave, Absent, Weekly Off, Hours) recompute for September.

### TC-ME-007: Cancel Future Pending Leave Request
- **Module / Screen:** Self-Service &mdash; `My Attendance (/me)`
- **Target Persona:** Engineer (`neha.verma@fosteringlinux.com`)
- **Priority:** `P1`
- **Pre-conditions:** Active future leave exists in table with status 'Waiting for approver'
- **Test Steps:**
  1. Locate row in 'My Leave Applications' table.
  2. Click 'Cancel' button.
  3. Confirm dialog.
- **Test Data:** `Action: Cancel leave`
- **Expected Result:**
  Flash message: 'Leave cancelled.'. Status pill updates to grey 'Cancelled'.

### TC-ME-008: Cancel Future Approved Leave and Clear Attendance Sheet
- **Module / Screen:** Self-Service &mdash; `My Attendance (/me)`
- **Target Persona:** Engineer (`neha.verma@fosteringlinux.com`)
- **Priority:** `P1`
- **Pre-conditions:** Approved future leave on 2026-10-29; attendance sheet has Leave markers
- **Test Steps:**
  1. On /me, locate approved leave.
  2. Click 'Cancel'.
- **Test Data:** `Action: Cancel approved leave`
- **Expected Result:**
  Leave status updates to 'Cancelled'. Roster row on attendance sheet for 2026-10-29 clears leave entries.

### TC-ME-009: Early Return from Active Ongoing Leave ('I am back early')
- **Module / Screen:** Self-Service &mdash; `My Attendance (/me)`
- **Target Persona:** Engineer (`priya.sharma@fosteringlinux.com`)
- **Priority:** `P1`
- **Pre-conditions:** Approved leave spanning from yesterday to 3 days in future
- **Test Steps:**
  1. Log in as Priya Sharma on /me.
  2. In active leave row, locate button 'I am back early'.
  3. Click button.
- **Test Data:** `Action: Early return`
- **Expected Result:**
  Flash message: 'Recorded: you joined before your leave ended. Mark your attendance as usual.'. Leave to_date truncated to yesterday; future dates unlocked on roster.

### TC-ME-010: Real-Time In-App Alert Banner Display
- **Module / Screen:** Self-Service &mdash; `Notifications (#wfn)`
- **Target Persona:** Engineer (`neha.verma@fosteringlinux.com`)
- **Priority:** `P1`
- **Pre-conditions:** PM just approved Neha's leave or objection
- **Test Steps:**
  1. Log in as Neha Verma.
  2. Observe viewport for notification modal (#wfn).
- **Test Data:** `Event: Leave approved`
- **Expected Result:**
  Floating modal displays with green badge 'APPROVED', title 'Your leave was approved', body text, and timestamp. Badge count shows '1'.

### TC-ME-011: Dismiss Single Notice and Mark Read
- **Module / Screen:** Self-Service &mdash; `Notifications (#wfn)`
- **Target Persona:** Engineer (`neha.verma@fosteringlinux.com`)
- **Priority:** `P2`
- **Pre-conditions:** Notification modal open with 2 items
- **Test Steps:**
  1. Click '×' button on first notification card.
  2. Observe modal count.
- **Test Data:** `Action: Click ×`
- **Expected Result:**
  Notice disappears immediately. Badge counter decrements from 2 to 1. Notice marked acknowledged in PostgreSQL notice table.

### TC-ME-012: Click 'Open ->' Navigation Deep Link
- **Module / Screen:** Self-Service &mdash; `Notifications (#wfn)`
- **Target Persona:** Engineer (`neha.verma@fosteringlinux.com`)
- **Priority:** `P2`
- **Pre-conditions:** Notification has link='/me'
- **Test Steps:**
  1. Click 'Open ->' link inside notification card.
- **Test Data:** `Action: Click Open ->`
- **Expected Result:**
  Notice is automatically dismissed and acknowledged. Page reloads/redirects to target URL.

## Functional Suite: Mobile & Review

### TC-MOB-001: GPS Check-In Inside Geofence Perimeter
- **Module / Screen:** Mobile & Review &mdash; `Mobile API`
- **Target Persona:** Engineer (`neha.verma@fosteringlinux.com`)
- **Priority:** `P1`
- **Pre-conditions:** Site 1 configured at Lat: 28.608, Lon: 77.227, Radius: 250m
- **Test Steps:**
  1. Dispatch POST /api/m/event with lat=28.6081, lon=77.2271, mock=false, accuracy=10.0.
- **Test Data:** `lat: 28.6081, lon: 77.2271, mock: false`
- **Expected Result:**
  API returns {'ok': true}. checkin_event table records event with trust='accepted'.

### TC-MOB-002: GPS Check-In Outside Geofence Perimeter
- **Module / Screen:** Mobile & Review &mdash; `Mobile API`
- **Target Persona:** Engineer (`rohit.gupta@fosteringlinux.com`)
- **Priority:** `P2`
- **Pre-conditions:** Site 1 radius 250m
- **Test Steps:**
  1. Dispatch POST /api/m/event with lat=28.650, lon=77.210 (>5km away).
- **Test Data:** `lat: 28.650, lon: 77.210`
- **Expected Result:**
  Event recorded outside perimeter. app_day.app_in is not stamped.

### TC-MOB-003: Mock Location Detection Rejection (Anti-Spoofing)
- **Module / Screen:** Mobile & Review &mdash; `Mobile API`
- **Target Persona:** Engineer (`rohit.gupta@fosteringlinux.com`)
- **Priority:** `P1`
- **Pre-conditions:** Device transmits mock location flag
- **Test Steps:**
  1. Dispatch POST /api/m/event with mock=true, lat=28.608, lon=77.227.
- **Test Data:** `mock: true`
- **Expected Result:**
  Event tagged with trust='rejected'. Check-in is discarded. On /review, row displays '1 not counted' warning.

### TC-MOB-004: Dwell-In Threshold Verification (5 Minutes)
- **Module / Screen:** Mobile & Review &mdash; `Mobile API`
- **Target Persona:** Engineer (`neha.verma@fosteringlinux.com`)
- **Priority:** `P2`
- **Pre-conditions:** Site dwell_in configured for 5 mins
- **Test Steps:**
  1. Dispatch arrival event.
  2. Check app_day before 5 mins elapse.
  3. Dispatch confirmation event after 5 mins dwell.
- **Test Data:** `Dwell: 5 minutes`
- **Expected Result:**
  app_in timestamp is only committed to app_day after continuous presence for 5 minutes.

### TC-MOB-005: Side-by-Side Reconciliation Table Display
- **Module / Screen:** Mobile & Review &mdash; `Phone Check-ins (/review)`
- **Target Persona:** PM Level 0 (`moumita.roy@fosteringlinux.com`)
- **Priority:** `P1`
- **Pre-conditions:** Logged in as Moumita Roy
- **Test Steps:**
  1. Navigate to /review?project=2&date=today.
  2. Inspect table columns.
- **Test Data:** `URL: /review`
- **Expected Result:**
  Table compares Phone IN/OUT vs Sheet IN/OUT. Shows Went out count, Time out break duration, and Trust column.

### TC-MOB-006: Discrepancy Diff Highlighting
- **Module / Screen:** Mobile & Review &mdash; `Phone Check-ins (/review)`
- **Target Persona:** PM Level 0 (`moumita.roy@fosteringlinux.com`)
- **Priority:** `P1`
- **Pre-conditions:** Neha Verma: Phone IN is 09:28; Sheet IN is empty or 09:30
- **Test Steps:**
  1. On /review, locate Neha Verma's row.
- **Test Data:** `Phone IN: 09:28, Sheet IN: 09:30`
- **Expected Result:**
  Row highlights diff condition. Action column displays 'Use phone times' button.

### TC-MOB-007: Expand Raw GPS Events Details
- **Module / Screen:** Mobile & Review &mdash; `Phone Check-ins (/review)`
- **Target Persona:** PM Level 0 (`moumita.roy@fosteringlinux.com`)
- **Priority:** `P2`
- **Pre-conditions:** Check-in events exist
- **Test Steps:**
  1. Click '<details>' summary link '[X events]'.
- **Test Data:** `Click [X events]`
- **Expected Result:**
  Sub-table expands displaying event time (HH:MM), kind (in/out), trust status, and distance from site center (e.g. '24 m from centre').

### TC-MOB-008: One-Click 'Use Phone Times' Merge
- **Module / Screen:** Mobile & Review &mdash; `Phone Check-ins (/review)`
- **Target Persona:** PM Level 0 (`moumita.roy@fosteringlinux.com`)
- **Priority:** `P1`
- **Pre-conditions:** diff=true for Neha Verma
- **Test Steps:**
  1. Click 'Use phone times' button.
- **Test Data:** `Action: Merge phone times`
- **Expected Result:**
  Flash message: 'Neha Verma: app times accepted.'. Sheet IN updates to 09:28. Diff badge disappears.

### TC-MOB-009: Past-Date Block on 'Use Phone Times' for PM
- **Module / Screen:** Mobile & Review &mdash; `Phone Check-ins (/review)`
- **Target Persona:** PM Level 0 (`moumita.roy@fosteringlinux.com`)
- **Priority:** `P1`
- **Pre-conditions:** View past date /review?date=2026-10-18
- **Test Steps:**
  1. Attempt to click 'Use phone times' on past date.
- **Test Data:** `Date: past date`
- **Expected Result:**
  Server blocks action with HTTP 403 Forbidden ('Past days can be changed by an admin only').

### TC-MOB-010: Approve Replacement Mobile Phone Device
- **Module / Screen:** Mobile & Review &mdash; `Phone Check-ins (/review)`
- **Target Persona:** PM Level 0 (`moumita.roy@fosteringlinux.com`)
- **Priority:** `P1`
- **Pre-conditions:** Engineer logged in from new phone; device in pending state
- **Test Steps:**
  1. On /review, scroll to 'New phones waiting for approval'.
  2. Verify email and model name.
  3. Click 'Approve'.
- **Test Data:** `Action: Approve phone`
- **Expected Result:**
  Flash message: 'New phone approved.'. Device status updates to 'approved'; pending_id cleared.

## Functional Suite: Leave Management

### TC-LEV-001: Apply for Leave >= 3 Days Notice (Auto-Marked Planned)
- **Module / Screen:** Leave Management &mdash; `Apply for Leave (/me)`
- **Target Persona:** Engineer (`neha.verma@fosteringlinux.com`)
- **Priority:** `P1`
- **Pre-conditions:** Today is 2026-10-21. Select dates starting 2026-10-26 (5 days notice).
- **Test Steps:**
  1. On /me, expand 'Apply for Leave'.
  2. From: 2026-10-26, To: 2026-10-27.
  3. Type: 'PL', Reason: 'Family trip'.
  4. Click 'Apply for Leave'.
- **Test Data:** `From: 2026-10-26, To: 2026-10-27, Type: PL`
- **Expected Result:**
  Application created with Planning column showing 'Planned'. Status is 'Waiting for moumita.roy@fosteringlinux.com'.

### TC-LEV-002: Apply for Leave < 3 Days Notice (Auto-Marked Unplanned)
- **Module / Screen:** Leave Management &mdash; `Apply for Leave (/me)`
- **Target Persona:** Engineer (`pooja.nair@fosteringlinux.com`)
- **Priority:** `P1`
- **Pre-conditions:** Today is 2026-10-21. Select tomorrow 2026-10-22 (1 day notice).
- **Test Steps:**
  1. On /me, From: 2026-10-22, To: 2026-10-22.
  2. Type: 'SL', Reason: 'High fever'.
  3. Click 'Apply for Leave'.
- **Test Data:** `From: 2026-10-22, To: 2026-10-22, Type: SL`
- **Expected Result:**
  Application created with Planning column showing 'Unplanned'. Notice rule enforced.

### TC-LEV-003: Validation on End Date Before Start Date
- **Module / Screen:** Leave Management &mdash; `Apply for Leave (/me)`
- **Target Persona:** Engineer (`rohit.gupta@fosteringlinux.com`)
- **Priority:** `P2`
- **Pre-conditions:** On /me leave form
- **Test Steps:**
  1. Enter From: 2026-10-28, To: 2026-10-25.
  2. Click 'Apply for Leave'.
- **Test Data:** `From: 2026-10-28, To: 2026-10-25`
- **Expected Result:**
  Form validation or flash error: 'The last day is before the first day.'. Request blocked.

### TC-LEV-004: Validation on Past Date Leave Application
- **Module / Screen:** Leave Management &mdash; `Apply for Leave (/me)`
- **Target Persona:** Engineer (`rohit.gupta@fosteringlinux.com`)
- **Priority:** `P2`
- **Pre-conditions:** On /me leave form
- **Test Steps:**
  1. Enter From date in the past (e.g. 2026-10-18).
  2. Submit form.
- **Test Data:** `From: 2026-10-18`
- **Expected Result:**
  Flash error: 'You cannot apply for a day that has passed. Ask your TL/PM.'. Request rejected.

### TC-LEV-005: Maximum 30 Days Leave Limit Validation
- **Module / Screen:** Leave Management &mdash; `Apply for Leave (/me)`
- **Target Persona:** Engineer (`manoj.tiwari@fosteringlinux.com`)
- **Priority:** `P2`
- **Pre-conditions:** On /me leave form
- **Test Steps:**
  1. Select date span spanning 45 calendar days.
  2. Submit form.
- **Test Data:** `Span: 45 days`
- **Expected Result:**
  Flash error: 'A request can cover at most 30 days.'. Request rejected.

### TC-LEV-006: Overlapping Leave Application Rejection
- **Module / Screen:** Leave Management &mdash; `Apply for Leave (/me)`
- **Target Persona:** Engineer (`neha.verma@fosteringlinux.com`)
- **Priority:** `P2`
- **Pre-conditions:** Neha has pending/approved leave for 2026-10-26 to 2026-10-27
- **Test Steps:**
  1. Apply for leave covering 2026-10-27 to 2026-10-28.
  2. Submit form.
- **Test Data:** `Dates: 2026-10-27 to 2026-10-28`
- **Expected Result:**
  Flash error: 'You already have an active leave request covering some of these days.'. Request rejected.

### TC-LEV-007: Live Capacity Warning Banner Appearance
- **Module / Screen:** Leave Management &mdash; `Apply for Leave (/me)`
- **Target Persona:** Engineer (`vikram.singh@fosteringlinux.com`)
- **Priority:** `P1`
- **Pre-conditions:** Multiple teammates already on leave on 2026-10-28; capacity threshold breached
- **Test Steps:**
  1. Select From: 2026-10-28, To: 2026-10-28.
  2. Observe #lvinfo container.
- **Test Data:** `Date: 2026-10-28`
- **Expected Result:**
  Light red banner appears displaying: 'Capacity: Team capacity is full on 2026-10-28...'. Lists teammates already on leave.

### TC-LEV-008: Confirmation Prompt on Submitting Capacity-Breached Leave
- **Module / Screen:** Leave Management &mdash; `Apply for Leave (/me)`
- **Target Persona:** Engineer (`vikram.singh@fosteringlinux.com`)
- **Priority:** `P1`
- **Pre-conditions:** Capacity alert banner active
- **Test Steps:**
  1. Click 'Apply for Leave' button.
- **Test Data:** `Submit form`
- **Expected Result:**
  Browser confirm modal displays: 'Team capacity is full on some of these days. Your TL/PM may ask you to withdraw, and a senior PM must approve. Apply anyway?'.

### TC-LEV-009: Auto-Routing Capacity-Breached Leave to PM1
- **Module / Screen:** Leave Management &mdash; `Apply for Leave (/me)`
- **Target Persona:** Engineer (`vikram.singh@fosteringlinux.com`)
- **Priority:** `P1`
- **Pre-conditions:** Capacity is full
- **Test Steps:**
  1. Click OK on confirm dialog.
  2. Verify 'Waiting for' column in My Leave Applications.
- **Test Data:** `Submit confirmed`
- **Expected Result:**
  System automatically escalates approver past PM0 to PM1: 'Waiting for imran.mohd@fosteringlinux.com'. capacity_full flag set to 1.

### TC-LEV-010: PM Approves Leave & Automatically Populates Attendance Sheet
- **Module / Screen:** Leave Management &mdash; `Manager Leaves (/leaves)`
- **Target Persona:** PM Level 0 (`moumita.roy@fosteringlinux.com`)
- **Priority:** `P1`
- **Pre-conditions:** Neha Verma has pending leave for 2026-10-26 to 2026-10-27
- **Test Steps:**
  1. Log in as Moumita Roy on /leaves.
  2. In Neha Verma's row, enter note 'Approved' and click 'Approve'.
  3. Check / for 2026-10-26.
- **Test Data:** `Action: Approve leave`
- **Expected Result:**
  Flash: 'Approved. Written to 2 day(s) on the attendance sheet.'. Roster table for 2026-10-26 shows Neha Verma marked 'Leave', 'PL', 'Planned'.

### TC-LEV-011: PM Rejects Leave with Mandatory Reason
- **Module / Screen:** Leave Management &mdash; `Manager Leaves (/leaves)`
- **Target Persona:** PM Level 0 (`moumita.roy@fosteringlinux.com`)
- **Priority:** `P1`
- **Pre-conditions:** Pending leave from Rohit Gupta
- **Test Steps:**
  1. On /leaves, leave note empty and click 'Reject'.
  2. Enter note 'Client milestone delivery on this date' and click 'Reject'.
- **Test Data:** `Note: Client milestone`
- **Expected Result:**
  Empty note triggers flash error 'Give a reason for the engineer.'. Entering reason updates status to 'rejected' and sends red alert notice to Rohit.

### TC-LEV-012: PM Requests Withdrawal for Capacity-Breached Leave
- **Module / Screen:** Leave Management &mdash; `Manager Leaves (/leaves)`
- **Target Persona:** PM Level 1 (`imran.mohd@fosteringlinux.com`)
- **Priority:** `P2`
- **Pre-conditions:** Capacity-breached leave assigned to PM1 Mohd Imran
- **Test Steps:**
  1. Log in as Mohd Imran on /leaves.
  2. In Vikram Singh's row, click 'Ask to withdraw'.
- **Test Data:** `Action: Ask to withdraw`
- **Expected Result:**
  Flash: 'Engineer asked to withdraw.'. Status updates to 'withdraw_requested'. Orange alert banner sent to Vikram.

### TC-LEV-013: PM Suggests Alternative Dates
- **Module / Screen:** Leave Management &mdash; `Manager Leaves (/leaves)`
- **Target Persona:** PM Level 0 (`moumita.roy@fosteringlinux.com`)
- **Priority:** `P2`
- **Pre-conditions:** Pending leave request
- **Test Steps:**
  1. In leave row, enter sfrom: 2026-11-03, sto: 2026-11-04, note: 'Please consider next week'.
  2. Click 'Suggest'.
- **Test Data:** `Suggested: 2026-11-03 to 2026-11-04`
- **Expected Result:**
  Flash: 'Suggestion sent.'. Status updates to 'modification'. Applicant sees 'Change suggested' pill.

### TC-LEV-014: Engineer Accepts Suggested Dates
- **Module / Screen:** Leave Management &mdash; `My Attendance (/me)`
- **Target Persona:** Engineer (`manoj.tiwari@fosteringlinux.com`)
- **Priority:** `P2`
- **Pre-conditions:** Leave has status 'modification'
- **Test Steps:**
  1. On /me, locate leave card.
  2. Note suggested dates displayed.
  3. Click 'Accept new dates' button.
- **Test Data:** `Action: Accept new dates`
- **Expected Result:**
  Flash: 'You accepted the new dates. Your TL/PM will approve them.'. Dates update to 2026-11-03 to 2026-11-04; status resets to 'pending'.

### TC-LEV-015: Engineer Declines Suggested Dates
- **Module / Screen:** Leave Management &mdash; `My Attendance (/me)`
- **Target Persona:** Engineer (`manoj.tiwari@fosteringlinux.com`)
- **Priority:** `P2`
- **Pre-conditions:** Leave has status 'modification'
- **Test Steps:**
  1. On /me, locate leave card.
  2. Click 'Decline' button.
- **Test Data:** `Action: Decline`
- **Expected Result:**
  Flash: 'Leave request cancelled.'. Status updates to grey 'Cancelled'.

### TC-LEV-016: Team Capacity 30-Day Grid Highlight Check
- **Module / Screen:** Leave Management &mdash; `Manager Leaves (/leaves)`
- **Target Persona:** PM Level 0 (`moumita.roy@fosteringlinux.com`)
- **Priority:** `P1`
- **Pre-conditions:** Capacity breached on 2026-10-28
- **Test Steps:**
  1. On /leaves, scroll to 'Team capacity, next 30 days'.
  2. Locate row for 2026-10-28.
- **Test Data:** `Date: 2026-10-28`
- **Expected Result:**
  Row background is highlighted in red (#ffe3e3). Available headcount is bold red; 'CAPACITY SHORT' displayed in red text.

## Functional Suite: Objections

### TC-OBJ-001: Raise Attendance Objection with Required Fields
- **Module / Screen:** Objections &mdash; `My Attendance (/me)`
- **Target Persona:** Engineer (`neha.verma@fosteringlinux.com`)
- **Priority:** `P1`
- **Pre-conditions:** Past date with incorrect attendance record
- **Test Steps:**
  1. On /me, expand 'Raise an Attendance Objection'.
  2. Day: 2026-10-16, IN: 09:30, OUT: 18:30, Reason: 'Attended full shift; biometric log missing'.
  3. Click 'Raise Objection'.
- **Test Data:** `Day: 2026-10-16, IN: 09:30, OUT: 18:30`
- **Expected Result:**
  Flash confirms submission. Objection created with status 'open'. Row appears in recent objections table.

### TC-OBJ-002: Validation on Non-HH:MM Time Format
- **Module / Screen:** Objections &mdash; `My Attendance (/me)`
- **Target Persona:** Engineer (`neha.verma@fosteringlinux.com`)
- **Priority:** `P3`
- **Pre-conditions:** On objection form
- **Test Steps:**
  1. Enter Correct IN: '25:99'.
  2. Submit.
- **Test Data:** `IN: 25:99`
- **Expected Result:**
  Flash error: 'Requested times must be HH:MM.'. Form submission rejected.

### TC-OBJ-003: PM Header Badge Counter Increment
- **Module / Screen:** Objections &mdash; `PM Approvals (/approvals)`
- **Target Persona:** PM Level 0 (`moumita.roy@fosteringlinux.com`)
- **Priority:** `P1`
- **Pre-conditions:** Objection submitted by Neha Verma
- **Test Steps:**
  1. Log in as Moumita Roy.
  2. Inspect top header navigation bar.
- **Test Data:** `Header bar`
- **Expected Result:**
  'Approvals' navigation link displays red circular counter badge: 'Approvals 1'.

### TC-OBJ-004: PM Reviews Objection Details
- **Module / Screen:** Objections &mdash; `PM Approvals (/approvals)`
- **Target Persona:** PM Level 0 (`moumita.roy@fosteringlinux.com`)
- **Priority:** `P1`
- **Pre-conditions:** On /approvals
- **Test Steps:**
  1. Scroll to 'Engineer objections' section.
  2. Verify Neha Verma's row.
- **Test Data:** `Objection row`
- **Expected Result:**
  Displays Date: 2026-10-16, Engineer: Neha Verma, Project: UPSC, full objection text, and requested correction 'IN 09:30 / OUT 18:30'.

### TC-OBJ-005: PM Accepts Objection & Auto-Corrects Past Attendance
- **Module / Screen:** Objections &mdash; `PM Approvals (/approvals)`
- **Target Persona:** PM Level 0 (`moumita.roy@fosteringlinux.com`)
- **Priority:** `P1`
- **Pre-conditions:** Objection open
- **Test Steps:**
  1. Verify IN: 09:30, OUT: 18:30.
  2. Enter Comment: 'Verified with security desk log. Approved.'.
  3. Click 'Accept and apply times'.
- **Test Data:** `Action: Accept, Comment: Verified`
- **Expected Result:**
  Flash: 'Objection accepted; attendance corrected to IN 09:30 / OUT 18:30.'. Past record for 2026-10-16 updated to Approved with times. Neha receives green notification.

### TC-OBJ-006: Validation on Missing PM Comment
- **Module / Screen:** Objections &mdash; `PM Approvals (/approvals)`
- **Target Persona:** PM Level 0 (`moumita.roy@fosteringlinux.com`)
- **Priority:** `P2`
- **Pre-conditions:** Objection open
- **Test Steps:**
  1. Leave comment field completely empty.
  2. Click 'Accept and apply times' or 'Reject'.
- **Test Data:** `Comment: empty`
- **Expected Result:**
  Client-side required attribute or flash error 'Write a comment for the engineer.' blocks decision.

### TC-OBJ-007: PM Rejects Objection with Explanation
- **Module / Screen:** Objections &mdash; `PM Approvals (/approvals)`
- **Target Persona:** PM Level 0 (`moumita.roy@fosteringlinux.com`)
- **Priority:** `P1`
- **Pre-conditions:** Objection open
- **Test Steps:**
  1. Enter Comment: 'Badge log shows exit at 13:00; half day deducted.'.
  2. Click 'Reject'.
- **Test Data:** `Action: Reject, Comment: Exit at 13:00`
- **Expected Result:**
  Flash: 'Objection rejected.'. Status changes to 'rejected'. Attendance sheet is NOT altered. Engineer receives red notification.

### TC-OBJ-008: Verify Corrected Attendance on Engineer Calendar
- **Module / Screen:** Objections &mdash; `My Attendance (/me)`
- **Target Persona:** Engineer (`neha.verma@fosteringlinux.com`)
- **Priority:** `P1`
- **Pre-conditions:** Objection was accepted
- **Test Steps:**
  1. Log in as Neha Verma on /me.
  2. Inspect monthly attendance calendar for 2026-10-16.
- **Test Data:** `Date: 2026-10-16`
- **Expected Result:**
  Row displays Status 'Present', Approval 'Approved', In '09:30', Out '18:30', Remarks 'Corrected after objection'.

## Functional Suite: PM Hierarchy

### TC-PM-001: Normal Leave Routing to PM0 (Primary Lead)
- **Module / Screen:** PM Hierarchy &mdash; `Routing`
- **Target Persona:** PM Level 0 (`moumita.roy@fosteringlinux.com`)
- **Priority:** `P1`
- **Pre-conditions:** PM0 is active and not on leave
- **Test Steps:**
  1. Neha Verma applies for standard planned leave.
  2. Inspect assigned_to field on leave record.
- **Test Data:** `Applicant: Neha Verma`
- **Expected Result:**
  Request is assigned to 'moumita.roy@fosteringlinux.com'. Appears in Moumita Roy's /leaves queue.

### TC-PM-002: Approver-on-Leave Automatic Bypass (PM0 Away -> PM1 Receives)
- **Module / Screen:** PM Hierarchy &mdash; `Bypass`
- **Target Persona:** PM Level 1 (`imran.mohd@fosteringlinux.com`)
- **Priority:** `P1`
- **Pre-conditions:** PM0 Moumita Roy has approved leave on 2026-10-30
- **Test Steps:**
  1. Neha Verma submits leave specifically for 2026-10-30.
  2. Log in as Mohd Imran on /leaves.
- **Test Data:** `Date: 2026-10-30`
- **Expected Result:**
  System detects PM0 is away. Automatically bypasses PM0 and assigns request to PM1 Mohd Imran ('imran.mohd@fosteringlinux.com').

### TC-PM-003: Cascade Bypass Down Chain (PM0 & PM1 Away -> PM2 Receives)
- **Module / Screen:** PM Hierarchy &mdash; `Bypass`
- **Target Persona:** PM Level 2 (`anjali.mehta@fosteringlinux.com`)
- **Priority:** `P2`
- **Pre-conditions:** Both Moumita Roy and Mohd Imran have approved leave on 2026-11-05
- **Test Steps:**
  1. Pooja Nair submits leave for 2026-11-05.
  2. Log in as Anjali Mehta on /leaves.
- **Test Data:** `Date: 2026-11-05`
- **Expected Result:**
  Both PM0 and PM1 bypassed. Request assigned to PM2 Anjali Mehta ('anjali.mehta@fosteringlinux.com').

### TC-PM-004: SLA Expiration Auto-Escalation to Next PM Level
- **Module / Screen:** PM Hierarchy &mdash; `Escalation`
- **Target Persona:** PM Hierarchy (`Multiple`)
- **Priority:** `P2`
- **Pre-conditions:** Approval SLA configured to 24 hours
- **Test Steps:**
  1. Leave request submitted to PM0.
  2. Advance system clock or mock due_at past SLA threshold.
- **Test Data:** `SLA: 24 hours expired`
- **Expected Result:**
  System escalates request one level up (PM0 -> PM1). approval_miss / leave_miss table records delinquency against PM0.

### TC-PM-005: SLA Miss Audit Tracking in Leave Reports
- **Module / Screen:** PM Hierarchy &mdash; `Escalation`
- **Target Persona:** PM / Admin (`ashish.kumar1@fosteringlinux.com`)
- **Priority:** `P2`
- **Pre-conditions:** SLA miss occurred
- **Test Steps:**
  1. Open /leaves/report.
  2. Inspect 'Leave Approvals Not Decided in Time / SLA Misses' table.
- **Test Data:** `URL: /leaves/report`
- **Expected Result:**
  Table lists project, engineer name, original approver (in orange warn text), escalated_to email, and missed timestamp.

### TC-PM-006: SLA Expiration on Attendance Approvals Escalates to Admin
- **Module / Screen:** PM Hierarchy &mdash; `Attendance`
- **Target Persona:** Admin (`ashish.kumar1@fosteringlinux.com`)
- **Priority:** `P2`
- **Pre-conditions:** Attendance self-entry unattended past SLA
- **Test Steps:**
  1. Log in as Admin Ashish Sharma.
  2. Open /approvals.
- **Test Data:** `URL: /approvals`
- **Expected Result:**
  Item moves to 'Escalated to admin' section. Admin can approve or reject with comments.

### TC-PM-007: Senior PM Can Decide on Behalf of Junior PM
- **Module / Screen:** PM Hierarchy &mdash; `Hierarchy Action`
- **Target Persona:** PM Level 2 (`anjali.mehta@fosteringlinux.com`)
- **Priority:** `P2`
- **Pre-conditions:** Item assigned to PM1 Mohd Imran
- **Test Steps:**
  1. Log in as PM2 Anjali Mehta.
  2. Open /leaves.
- **Test Data:** `Role: PM2`
- **Expected Result:**
  can_approve_leave() recognizes Anjali Mehta is higher in chain than Mohd Imran; grants approval rights.

### TC-PM-008: Junior PM Blocked from Approving Senior PM Escalated Leave
- **Module / Screen:** PM Hierarchy &mdash; `Hierarchy Action`
- **Target Persona:** PM Level 0 (`moumita.roy@fosteringlinux.com`)
- **Priority:** `P1`
- **Pre-conditions:** Leave escalated to PM1 due to capacity breach
- **Test Steps:**
  1. Log in as PM0 Moumita Roy.
  2. Open /leaves.
  3. Attempt to approve capacity-breached leave.
- **Test Data:** `Role: PM0`
- **Expected Result:**
  Approve button is disabled with tooltip: 'Capacity is full: needs a higher level'. Form submit rejected.

## Functional Suite: Reports

### TC-REP-001: Daily Summary Metric Accuracy
- **Module / Screen:** Reports &mdash; `Daily Summary (/summary)`
- **Target Persona:** PM Level 0 (`moumita.roy@fosteringlinux.com`)
- **Priority:** `P1`
- **Pre-conditions:** Roster has 4 Present, 1 Leave, 1 Absent for today
- **Test Steps:**
  1. Open /summary?project=2.
  2. Verify KPI cards.
- **Test Data:** `URL: /summary`
- **Expected Result:**
  Cards display Total Strength: 6, Present: 4, Leave: 1, Absent: 1. Math balances.

### TC-REP-002: Late Arrivals Scorecard on Summary
- **Module / Screen:** Reports &mdash; `Daily Summary (/summary)`
- **Target Persona:** PM Level 0 (`moumita.roy@fosteringlinux.com`)
- **Priority:** `P2`
- **Pre-conditions:** Rohit Gupta arrived at 10:15 (45m late)
- **Test Steps:**
  1. On /summary, inspect Late Arrivals table.
- **Test Data:** `URL: /summary`
- **Expected Result:**
  Rohit Gupta listed with arrival time 10:15 and delay '45 min'.

### TC-REP-003: Missing Check-Outs Scorecard on Summary
- **Module / Screen:** Reports &mdash; `Daily Summary (/summary)`
- **Target Persona:** PM Level 0 (`moumita.roy@fosteringlinux.com`)
- **Priority:** `P2`
- **Pre-conditions:** Pooja Nair has In: 09:30 but Out: empty
- **Test Steps:**
  1. On /summary, inspect Missing Check-Outs table.
- **Test Data:** `URL: /summary`
- **Expected Result:**
  Pooja Nair listed with In time 09:30 and missing exit alert.

### TC-REP-004: Admin Triggers Email Summary Dispatch
- **Module / Screen:** Reports &mdash; `Daily Summary (/summary)`
- **Target Persona:** Admin (`ashish.kumar1@fosteringlinux.com`)
- **Priority:** `P2`
- **Pre-conditions:** Logged in as Admin
- **Test Steps:**
  1. On /summary, click 'Send Email Summary' button.
- **Test Data:** `Action: Send Email Summary`
- **Expected Result:**
  Flash message: 'Summary emailed to [recipients]'. Formatted HTML report sent via SMTP.

### TC-REP-005: Filter Trends Across Predefined Spans
- **Module / Screen:** Reports &mdash; `Trends (/trends)`
- **Target Persona:** PM Level 0 (`moumita.roy@fosteringlinux.com`)
- **Priority:** `P2`
- **Pre-conditions:** On /trends
- **Test Steps:**
  1. Click timeframe buttons: '7 days', '30 days', '90 days', '365 days'.
- **Test Data:** `Timeframes`
- **Expected Result:**
  Charts and KPI metrics update dynamically for each selected span without errors.

### TC-REP-006: Filter Trends by Custom Date Range
- **Module / Screen:** Reports &mdash; `Trends (/trends)`
- **Target Persona:** PM Level 0 (`moumita.roy@fosteringlinux.com`)
- **Priority:** `P2`
- **Pre-conditions:** On /trends
- **Test Steps:**
  1. Click 'Custom' pill.
  2. Set Start: 2026-09-01, End: 2026-10-21.
  3. Click Filter.
- **Test Data:** `Range: 2026-09-01 to 2026-10-21`
- **Expected Result:**
  Metrics and arrival distribution recompute strictly for the custom 51-day window.

### TC-REP-007: Download 6-Sheet OpenPyXL Excel Report
- **Module / Screen:** Reports &mdash; `Leave Report (/leaves/report)`
- **Target Persona:** PM Level 0 (`moumita.roy@fosteringlinux.com`)
- **Priority:** `P1`
- **Pre-conditions:** On /leaves/report
- **Test Steps:**
  1. Click '📥 Download 6-Sheet Excel (.xlsx)' button.
- **Test Data:** `Action: Download report.xlsx`
- **Expected Result:**
  Downloads valid .xlsx spreadsheet containing 6 sheets: Capacity Shortages, SLA Missed Approvals, Leave Extensions, Early Resumes, Leave Mix, Withdrawals.

### TC-REP-008: Download Monthly Attendance Matrix Excel (/export/monthly.xlsx)
- **Module / Screen:** Reports &mdash; `Exports`
- **Target Persona:** PM Level 0 (`moumita.roy@fosteringlinux.com`)
- **Priority:** `P2`
- **Pre-conditions:** Logged in as PM
- **Test Steps:**
  1. Trigger /export/monthly.xlsx?project=2&month=2026-10.
- **Test Data:** `Action: Download monthly.xlsx`
- **Expected Result:**
  Downloads formatted spreadsheet displaying days 1 to 31 grid, employee names, colored status indicators (P, A, L, WO), and monthly totals.

## Functional Suite: Administration

### TC-ADM-001: Configure PM Approval Chain (PM0-PM3)
- **Module / Screen:** Administration &mdash; `Project Setup (/project/setup)`
- **Target Persona:** Admin (`ashish.kumar1@fosteringlinux.com`)
- **Priority:** `P1`
- **Pre-conditions:** Logged in as Admin on Project 2
- **Test Steps:**
  1. On /project/setup, enter PM0: moumita.roy, PM1: imran.mohd, PM2: anjali.mehta, PM3: amit.roy.
  2. Click 'Save PM chain'.
- **Test Data:** `PM0-PM3 emails`
- **Expected Result:**
  Flash message: 'PM approval chain saved.'. pm_chain table stores updated hierarchy.

### TC-ADM-002: Configure Project Client Info & Weekly Offs
- **Module / Screen:** Administration &mdash; `Project Setup (/project/setup)`
- **Target Persona:** Admin (`ashish.kumar1@fosteringlinux.com`)
- **Priority:** `P2`
- **Pre-conditions:** On /project/setup
- **Test Steps:**
  1. Enter Client Name: 'UPSC Admin', Office Location: 'Dholpur House, New Delhi'.
  2. Set Minimum Capacity: 4.
  3. Check Saturday & Sunday.
  4. Click 'Save Project Information'.
- **Test Data:** `Capacity: 4, Weekly Off: Sat, Sun`
- **Expected Result:**
  Flash confirms save. Weekly off policy and minimum capacity stored.

### TC-ADM-003: Add Geofenced Work Site with Coordinates & Radius
- **Module / Screen:** Administration &mdash; `Project Setup (/project/setup)`
- **Target Persona:** Admin (`ashish.kumar1@fosteringlinux.com`)
- **Priority:** `P1`
- **Pre-conditions:** On /project/setup
- **Test Steps:**
  1. Click '+ Add a work site geofence'.
  2. Name: 'UPSC HQ', Lat: 28.6080, Lon: 77.2270, Radius: 250m, Dwell In: 5, Dwell Out: 10.
  3. Click 'Save site'.
- **Test Data:** `Lat: 28.608, Lon: 77.227, Radius: 250`
- **Expected Result:**
  Site saved in PostgreSQL site table. Engineers within 250m can check in via mobile app.

### TC-ADM-004: Inline Shift Start Time Update
- **Module / Screen:** Administration &mdash; `Team Management (/team)`
- **Target Persona:** PM Level 0 (`moumita.roy@fosteringlinux.com`)
- **Priority:** `P2`
- **Pre-conditions:** On /team?project=2
- **Test Steps:**
  1. In Priya Sharma's row, change shift input to '10:00'.
  2. Click 'Save'.
- **Test Data:** `Shift: 10:00`
- **Expected Result:**
  Flash confirms update. Priya Sharma's shift start time updates to 10:00 on daily entry sheet.

### TC-ADM-005: Release Engineer to Bench Pool ('Remove')
- **Module / Screen:** Administration &mdash; `Team Management (/team)`
- **Target Persona:** PM Level 0 (`moumita.roy@fosteringlinux.com`)
- **Priority:** `P1`
- **Pre-conditions:** On /team?project=2
- **Test Steps:**
  1. In Vikram Singh's row, click red 'Remove' button.
  2. Confirm browser alert dialog.
- **Test Data:** `Action: Release to bench`
- **Expected Result:**
  Flash confirms removal. Vikram Singh is marked inactive in project; moved to Bench Pool.

### TC-ADM-006: Add Engineer from Bench Pool via Modal
- **Module / Screen:** Administration &mdash; `Team Management (/team)`
- **Target Persona:** PM Level 0 (`moumita.roy@fosteringlinux.com`)
- **Priority:** `P1`
- **Pre-conditions:** Vikram Singh is on bench
- **Test Steps:**
  1. Click 'Manage Team' button.
  2. Switch to 'Bench Pool' tab.
  3. Locate Vikram Singh and click 'Add to Project'.
- **Test Data:** `Action: Assign from bench`
- **Expected Result:**
  Vikram Singh restored to active team roster. Reappears on daily attendance sheet.

### TC-ADM-007: Admin Transfer Engineer to Another Project
- **Module / Screen:** Administration &mdash; `Team Management (/team)`
- **Target Persona:** Admin (`ashish.kumar1@fosteringlinux.com`)
- **Priority:** `P1`
- **Pre-conditions:** Logged in as Admin on /team?project=2
- **Test Steps:**
  1. In engineer transfer dropdown ('Transfer to...'), select 'Project 1 - NCLT'.
  2. Confirm dialog.
- **Test Data:** `Destination: Project 1`
- **Expected Result:**
  Flash confirms transfer. Engineer deactivated on Project 2; created as active member on Project 1. Historical attendance preserved.

### TC-ADM-008: Grant New Lead Role via Access Page
- **Module / Screen:** Administration &mdash; `Access Control (/access)`
- **Target Persona:** Admin (`ashish.kumar1@fosteringlinux.com`)
- **Priority:** `P1`
- **Pre-conditions:** Logged in as Admin on /access
- **Test Steps:**
  1. Enter email of user.
  2. Role: 'lead', All Projects: checked.
  3. Click 'Save Access'.
- **Test Data:** `Role: lead, All Projects: 1`
- **Expected Result:**
  New row added to access table. User granted global PM privileges on next login.
