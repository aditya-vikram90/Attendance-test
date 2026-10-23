# Post-Demo Feature Roadmap & Task Specification (Priority 1)

This document organizes and consolidates the post-demo user requirements marked as **Priority 1 (Difficulty Level 1: Quick & High Impact)**. Duplicate and overlapping requirements have been unified into structured, modular components.

---

## 📊 Summary of Deduplication & Functional Grouping

The raw 12 task items naturally condense into **4 Core Functional Modules**:

| Module | Raw Task Nos. | Summary Description |
| :--- | :--- | :--- |
| **Module 1: Self-Service Daily Attendance & Same-Day PM Approval** | `1`, `1.1` | Engineers log their daily punches and duty statuses directly; active PM/TL reviews and approves/verifies attendance on the same day. |
| **Module 2: Leave Application, Cancellation & PM Approval Workflow** | `3.1`, `3.3`, `4.7.2` *(Duplicated/Overlap)* | Engineers submit or cancel leaves; PM/TL receives a daily approval queue to Approve, Reject, or Suggest modifications. |
| **Module 3: Leave Intelligence, Rules & Capacity Warnings** | `4.2`, `4.4`, `4.6`, `4.7.1` | Automatic Planned vs. Unplanned classification (3-day rule), consecutive leave extension detection, pre-application team leave visibility, and team capacity warning popups. |
| **Module 4: Project, Site & Client Reporting Officer Metadata** | `5.1`, `5.2`, `5.3` | Project owner contact details, site location/geocoordinates, and client-side reporting officers for assigned engineers. |

---

## 📋 Clean & Consolidated Task List (Priority 1)

### Module 1: Self-Service Daily Attendance & Same-Day Approval

#### Task 1.0: Employee Daily Attendance Self-Entry
* **Original Item**: `Task 1: allow engineers itself to fill the attendance`
* **Description**:
  * Provide a simple, fast check-in / check-out and attendance logging interface on the engineer self-service portal (`/me` or `/checkin`).
  * Engineers can record their In-Time, Out-Time, Status (`Present`, `WFH`, `Half Day`), and duty remarks (e.g., Head Office visit, sprint review, client site duty).
  * Status is marked as `Submitted / Pending Approval` until verified by PM.

#### Task 1.1: Same-Day PM / TL Attendance Approval
* **Original Item**: `Task 1.1: allow the active PM/TL to approve that attendance on the same day`
* **Description**:
  * On the PM daily grid (`/`), show a clear visual indicator for entries submitted by engineers.
  * Active PM/TL can review submitted times and approve with 1 click (e.g., "Approve All" or individual approval), or adjust timestamps if corrections are needed.
  * Ensures attendance is validated on the same business day before executive briefing cutoff.

---

### Module 2: Leave Lifecycle: Application, Cancellation & Review Queue

#### Task 2.0: Employee Leave Application & Cancellation
* **Original Item**: `Task 3.1: Engineer will apply their leave or cancel their leave also`
* **Description**:
  * Engineers can submit leave requests directly from their portal (`/me` -> "Apply Leave").
  * Fields: Leave Date Range (From/To), Leave Type (Casual, Sick, etc.), Reason, and Proposed Cover Colleague.
  * Engineers can cancel a pending or future approved leave before the start date.

#### Task 2.1: PM / TL Daily Leave Approval Queue & Action Options
* **Original Items**:
  * `Task 3.3: PM/TL will approve/reject/suggest modification`
  * `Task 4.7.2: the PM/TL will be shown all the leave application for everyday, so that can be approved accordingly`
  *(These two items are duplicates: 4.7.2 is the daily review view, and 3.3 are the actions).*
* **Description**:
  * **Daily Review Inbox**: PM/TL sees a dedicated daily tab or badge of all incoming leave applications grouped by date and project.
  * **Actions Available**:
    1. **Approve**: Confirms leave and automatically marks the daily grid for those dates (skipping weekends).
    2. **Reject**: Declines request with an optional reason note to the engineer.
    3. **Suggest Modification**: Prompts engineer to adjust dates or reassign cover if project deliverables require presence.

---

### Module 3: Leave Intelligence, Rules & Capacity Guardrails

#### Task 3.0: Planned vs. Unplanned Leave Auto-Classification (Configurable 3-Day Rule)
* **Original Item**: `Task 4.4: planned/unplanned leave - manual entry, if applied before 3 days (configurable in system) will be planned`
* **Description**:
  * System adds a configurable lead-time setting (default: **3 days in advance**).
  * **Automatic Decision for Candidates**: If `Leave Start Date - Application Date >= 3 days`, the leave is automatically classified as **Planned**; if applied `< 3 days`, it defaults to **Unplanned**.
  * **PM/TL Manual Override**: PM/TL retains full authority to manually switch a leave between Planned and Unplanned during approval or daily grid entry.

#### Task 3.1: Pre-Application Team Leave Visibility
* **Original Item**: `Task 4.6: if any candidate/PM/TL apply for a leave, before applying display information of all the applied engineers`
* **Description**:
  * In the leave application form (for engineer and PM), selecting a date range immediately shows a live list/calendar snippet of teammates who are already on leave or have applied for leave on those same dates.
  * Prevents accidental handover conflicts and ensures the engineer selects an available cover colleague.

#### Task 3.2: Maximum Leave Capacity & Staffing Quota Warning Popup
* **Original Item**: `Task 4.7.1: if maximum number of candidates are applied for a leave of same day then show a popup about capacity information`
* **Description**:
  * Define a project staffing threshold (e.g., maximum allowed team members on leave simultaneously, such as $\le 20\%$ of project team or configurable count $N$).
  * If an engineer or PM attempts to apply for leave on a date where the threshold is already reached, a warning modal/popup appears:
    * *"Capacity Warning: 3 engineers on UPSC are already scheduled on leave for 24-Oct. Submitting may exceed team minimum staffing capacity. Proceed anyway?"*
  * Flags high-risk dates to PM during the approval stage.

#### Task 3.3: Consecutive Leave & Leave Extension Tracking
* **Original Item**: `Task 4.2: if consecutive leave applied will be record in report (will be treated as leave extension)`
* **Description**:
  * When a new leave application immediately follows a prior approved leave (e.g. prior leave ended Friday, new leave starts Monday, or prior ended Wednesday, new starts Thursday):
    * The system links the records and flags it as a **Leave Extension**.
  * Tagged in daily summaries, regularity trends, and monthly Excel reports as *"Extension to Leave of [Previous Dates]"*.

---

### Module 4: Project, Site & Client Reporting Officer Metadata

#### Task 4.0: Project Owner & Client POC Details
* **Original Item**: `Task 5.1: project owner details (name, email, phone number etc.)`
* **Description**:
  * Expand project settings to store client project sponsor / owner information:
    * Project Owner Name
    * Official Email Address
    * Contact Phone Number / Office Extension
    * Department / Ministry / Organization Unit

#### Task 4.1: Project Location & Geolocation Coordinates
* **Original Item**: `Task 5.2: location, geolocation`
* **Description**:
  * Add physical deployment location attributes to each project profile:
    * Site Name / Client Building (e.g., *Dholpur House, Shahjahan Road, New Delhi*)
    * City / Region
    * Geolocation Coordinates (Latitude & Longitude) for future geofencing / verification.

#### Task 4.2: Client-Side Reporting Officer per Engineer
* **Original Item**: `Task 5.3: Reporting officer of each engineer at client side`
* **Description**:
  * For each team member assigned to a project, store their designated client-side reporting authority:
    * Client Reporting Officer Name (e.g., Under Secretary / Director / Section Officer)
    * Designation & Client Department
    * Contact Email & Phone
  * Displayed on team profile, engineer self-service card, and exportable in monthly client rosters.

---

## 🔍 Identified Overlaps / Duplicate Analysis

1. **`3.3` and `4.7.2` are two sides of the same approval coin**:
   * `4.7.2` (*"the PM/TL will be shown all the leave application for everyday, so that can be approved accordingly"*) is the **UI View (Daily Queue)**.
   * `3.3` (*"PM/TL will approve/reject/suggest modification"*) are the **Actions** executed on that queue.
   * *Consolidated into*: **Task 2.1 (PM/TL Daily Leave Approval Queue & Action Options)**.

2. **`4.6` and `4.7.1` are tightly connected team availability checks**:
   * `4.6` displays who is already on leave before submitting.
   * `4.7.1` checks if that count exceeds the team capacity and shows a popup alert.
   * *Grouped into*: **Task 3.1 (Visibility)** and **Task 3.2 (Capacity Warning Popup)** within the same modal interaction.

3. **`1` and `1.1` form a single synchronous workflow**:
   * Engineer enters attendance $ightarrow$ PM approves on the same day.
   * *Consolidated into*: **Module 1 (Self-Service Attendance & Same-Day Verification)**.

---

## 🎯 Next Steps

This consolidated specification is saved in `docs/POST_DEMO_PRIORITY_1_TASKS.md`.
Please review the organized structure. When you are ready, let me know which module or task you would like to proceed with first!
