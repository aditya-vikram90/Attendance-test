# Complete Attendance Portal Feature Roadmap & Functional Specification

This specification documents the complete master list of post-demo requirements, structured by **Functional Modules**, categorized by **Priority Level (1 vs 2)**, and cross-referenced with exact business rules, workflows, hierarchy, and escalation matrices.

---

## 📌 Priority Level Definition

* **Priority 1 (Difficulty 1 - First Phase)**: Core functional flows, self-service entry, daily review queues, basic rules (3-day planned/unplanned, extension tagging, capacity warning popup), and project/client metadata.
* **Priority 2 (Difficulty 2 - Second Phase)**: Automated PM hierarchy (`PM0` to `PM3`), real-time WebSocket/SSE notifications, 30-hour SLA escalation, strict capacity enforcement & one-level-above override, early return audits, and attendance dispute/objection tracking.

---

## 🏗️ Master Feature Matrix by Module

| Module | Task ID | Task Description | Priority | Primary Actor |
| :--- | :--- | :--- | :---: | :--- |
| **1. Daily Attendance** | `1.0` | Engineer self-fills daily attendance (in/out, status, remarks) | **P1** | Engineer |
| | `1.1` | Active PM/TL same-day attendance review & approval | **P1** | Active PM / TL |
| | `1.2` | Engineer attendance objection / grievance submission | **P2** | Engineer |
| **2. PM Hierarchy & Routing** | `2.0` | Automated Active PM determination flow | **P2** | System |
| | `2.1` | 4-Tier PM Hierarchy: Moumita (`PM0`) -> Deepak (`PM1`) -> Amit (`PM2`) -> Aryan (`PM3`) | **P2** | System / Admin |
| **3. Leave Lifecycle** | `3.1` | Engineer applies for leave or cancels pending/future leave | **P1** | Engineer |
| | `3.2` | Real-time in-app forced popup & email notification to project PM/TLs (no refresh) | **P2** | PM / TL |
| | `3.3` | PM/TL action options: Approve, Reject, or Suggest Modification | **P1** | PM / TL |
| | `4.7.2` | Daily calendar/inbox view for PM/TL showing all applications per day | **P1** | PM / TL |
| **4. Leave Rules & SLA** | `4.1` | Immutability: Approved leave cannot be extended directly | **P2** | System / PM |
| | `4.2` | Consecutive leave detection & "Leave Extension" reporting | **P1** | System / Reports |
| | `4.3` | Early join tracking & audit log before leave completion | **P2** | System / PM |
| | `4.4` | Planned vs Unplanned auto-classification (configurable 3-day lead time + PM manual override) | **P1** | System / PM |
| | `4.5` | 30-hour PM approval SLA with auto-escalation to one level above in hierarchy | **P2** | System / Higher PM |
| **5. Capacity & Availability** | `4.6` | Pre-application visibility: Display all applied teammates for selected dates | **P1** | Candidate / PM |
| | `4.7.0` | Minimum team capacity threshold configuration & automatic calculation | **P2** | System / Admin |
| | `4.7.1` | Team capacity warning popup if threshold reached for selected dates | **P1** | Candidate / PM |
| | `4.7.3` | Capacity full: PM/TL request to withdraw based on leave reason | **P2** | PM / TL |
| | `4.7.4` | Capacity full exception approval: Requires one-level-above PM role | **P2** | Higher PM |
| | `4.7.5` | Team capacity deficit reporting (audit of days operating below capacity) | **P2** | Management |
| **6. Project & Client Info** | `5.1` | Project owner contact details (name, email, phone, department) | **P1** | Admin / PM |
| | `5.2` | Project location & GPS geolocation coordinates | **P1** | Admin / PM |
| | `5.3` | Client-side reporting officer details per assigned engineer | **P1** | Admin / PM |

---

## 🔍 Detailed Module Specifications

### Module 1: Daily Attendance & Objection Workflow

#### Task 1: Engineer Self-Service Attendance Entry
* **Priority**: `1` (Difficulty: Easy / Immediate)
* **Actor**: Engineer
* **Functional Description**:
  * On `/me` (or dedicated `/checkin`), engineers can enter:
    * In-Time and Out-Time.
    * Status: `Present (P)`, `Work From Home (W)`, or `Half Day (HD)`.
    * Location Remarks: (e.g. *"At client site"*, *"Visited Head Office for sprint review"*, *"IT setup"*).
  * Marked as `Pending Approval` until confirmed by PM.

#### Task 1.1: Same-Day PM / TL Attendance Verification & Approval
* **Priority**: `1` (Difficulty: Easy / Immediate)
* **Actor**: Active PM / TL
* **Functional Description**:
  * On the PM daily grid (`/`), engineer-submitted records appear with an `Awaiting Approval` badge.
  * Active PM/TL can:
    * One-click **Approve All** or approve individually.
    * Edit times/status if correction is required before approval.
  * Must be approved on the **same day** before nightly executive summary cutoff.

#### Unnumbered Task: Attendance Dispute / Objection Mechanism
* **Priority**: `2` (Difficulty: Moderate)
* **Actor**: Engineer
* **Functional Description**:
  * If an engineer finds an error in their attendance marked by PM (e.g. marked absent or late incorrectly), they can click **"Raise Objection"** on `/me`.
  * Engineer enters reason and proof/notes.
  * Objection surfaces in PM review dashboard for reconciliation.

---

### Module 2: PM Hierarchy & Automated Escalation Engine

#### Task 2: Automated Active PM Routing Flow
* **Priority**: `2` (Difficulty: Moderate)
* **Functional Description**:
  * System tracks the **Active Primary PM** for each project.
  * If the primary PM is on approved leave or absent, the system automatically delegates active approval rights to the designated alternate or next in line.

#### Task 2.1: 4-Tier PM Hierarchy Implementation
* **Priority**: `2` (Difficulty: Moderate)
* **Structure**:
  ```text
  Level 0: Moumita  (PM0 - Delivery Head / Director)
             ▲
  Level 1: Deepak   (PM1 - Senior Portfolio PM)
             ▲
  Level 2: Amit     (PM2 - Project Manager)
             ▲
  Level 3: Aryan    (PM3 - Associate PM / Team Lead)
  ```
* **Functional Use**:
  * Drives escalation when approval SLA breaches (Task 4.5).
  * Required for capacity-full leave exception approvals (Task 4.7.4).

---

### Module 3: Leave Application, Real-Time Notifications & Review Queue

#### Task 3.1: Employee Leave Application & Cancellation
* **Priority**: `1` (Difficulty: Easy / Immediate)
* **Actor**: Engineer
* **Functional Description**:
  * Engineers apply via modal on `/me`: Date range (From/To), Leave Type (Casual, Sick, etc.), Reason, and Cover Colleague.
  * Engineer can cancel a leave request if it is still `Pending` or before the leave start date.

#### Tasks 3.2 & 3.2.1: Real-Time In-App Forced Acknowledgment & Email
* **Priority**: `2` (Difficulty: Moderate)
* **Actor**: PM / TL
* **Functional Description**:
  * When leave is submitted, all PM/TLs assigned to that project receive:
    1. Instant Email notification.
    2. Real-time in-app notification popup (via WebSocket / SSE / short poll) that appears **without requiring a page refresh**.
  * The popup forces an acknowledgment so urgent leaves are never overlooked.

#### Task 3.3 & Task 4.7.2: Daily Leave Review Inbox & Action Trio
* **Priority**: `1` (Difficulty: Easy / Immediate)
* **Actor**: PM / TL
* **Functional Description**:
  * **Daily Inbox View (`4.7.2`)**: PM/TL sees all pending applications grouped day-by-day.
  * **Action Options (`3.3`)**:
    1. **Approve**: Confirms leave; updates daily attendance sheet automatically.
    2. **Reject**: Declines with a feedback comment.
    3. **Suggest Modification**: Returns request to engineer to adjust dates or swap cover colleague.

---

### Module 4: Leave Rules, SLA Escalation & Capacity Intelligence

#### Task 4.4: Planned vs. Unplanned Auto-Classification (3-Day Rule)
* **Priority**: `1` (Difficulty: Easy / Immediate)
* **Rule Engine**:
  * System setting: `planned_leave_min_notice_days = 3` (configurable).
  * **Candidate Self-Application**:
    * If `Leave Start Date - Application Date >= 3 days` -> Classified as **Planned Leave**.
    * If `Leave Start Date - Application Date < 3 days` -> Classified as **Unplanned Leave**.
  * **PM/TL Manual Control**: PM/TL can manually set/override as Unplanned or Planned.

#### Task 4.6: Pre-Application Team Leave Visibility
* **Priority**: `1` (Difficulty: Easy / Immediate)
* **Functional Description**:
  * In the leave modal, picking a date range immediately displays a live list of teammates already on leave or with pending applications for those dates.
  * Prevents scheduling overlapping leaves for engineers sharing the same deliverables.

#### Task 4.7.1: Maximum Leave Capacity Warning Popup
* **Priority**: `1` (Difficulty: Easy / Immediate)
* **Functional Description**:
  * If the number of applied leaves on a target date reaches the project maximum threshold, a warning modal triggers:
    * *"Capacity Warning: Maximum team leave capacity reached for [Date]. Submitting may cause project staffing shortages. Proceed anyway?"*

#### Task 4.2: Consecutive Leave Extension Tracking
* **Priority**: `1` (Difficulty: Easy / Immediate)
* **Functional Description**:
  * If an engineer submits a leave starting on the next business day after an existing leave, the system links the records.
  * Flagged and labeled in reports as **Leave Extension** (e.g. *"Extension to leave of 18-Oct to 20-Oct"*).

#### Task 4.1: Immutability of Approved Leaves
* **Priority**: `2` (Difficulty: Moderate)
* **Functional Description**:
  * Approved leaves cannot be edited directly to extend dates. Any additional days must be requested as a separate consecutive leave subject to review.

#### Task 4.3: Early Return Audit Tracking
* **Priority**: `2` (Difficulty: Moderate)
* **Functional Description**:
  * If an engineer reports back to work before their approved leave end date, mark them Present for that day and log an **Early Join** event with remaining leave days credited back.

#### Task 4.5: 30-Hour Approval SLA & Hierarchy Escalation
* **Priority**: `2` (Difficulty: Moderate)
* **Functional Description**:
  * Configurable SLA timer (default: **30 hours** from leave submission).
  * If the assigned PM/TL does not act within 30 hours, the system:
    1. Triggers an escalation alert to the next level in PM hierarchy (e.g. `PM3 Aryan` -> `PM2 Amit` -> `PM1 Deepak`).
    2. Records the SLA breach in management compliance reports.

#### Tasks 4.7.0, 4.7.3, 4.7.4 & 4.7.5: Advanced Team Capacity Management
* **Priority**: `2` (Difficulty: Moderate)
* **Functional Description**:
  * `4.7.0`: Automatic minimum capacity calculation per project.
  * `4.7.3`: If capacity is full, PM/TL can send a request asking candidate to voluntarily withdraw based on leave reason.
  * `4.7.4`: If leave must be granted despite capacity being full, approval **must be escalated one step above** in the PM hierarchy (`PM3` -> `PM2` -> `PM1`).
  * `4.7.5`: Dedicated management report tracking dates when teams operated under-capacity.

---

### Module 5: Project & Client Information Metadata

#### Task 5.1: Project Owner & Client Sponsor Details
* **Priority**: `1` (Difficulty: Easy / Immediate)
* **Fields Added to Project Profile**:
  * Project Owner / Client POC Full Name
  * Official Email Address
  * Phone Number / Office Landline
  * Client Ministry / Department / Organization

#### Task 5.2: Project Location & Geolocation
* **Priority**: `1` (Difficulty: Easy / Immediate)
* **Fields Added to Project Profile**:
  * Physical Site Address / Building Name
  * City & State
  * Geolocation Coordinates (Latitude & Longitude) for future mobile check-in verification.

#### Task 5.3: Client-Side Reporting Officer per Engineer
* **Priority**: `1` (Difficulty: Easy / Immediate)
* **Fields Added to Team Assignment**:
  * Client Reporting Officer Name (e.g. Director / Under Secretary)
  * Officer Designation & Organization Division
  * Officer Official Email & Phone Number
