# Demo Issues Analysis & Resolution Strategy

**Date**: October 14, 2026  
**System**: Attendance Management System & Keycloak SSO Integration  
**Status**: Analysis Complete — Awaiting Approval for Execution  

---

## Executive Summary

During the demo walkthrough of the Attendance Application, two critical operational issues were identified:

1. **Issue 1**: Creating a user in Keycloak allows SSO login to the Attendance portal, but requires PMs/TLs/Admins to manually re-enter all user details (Name, Role, Mobile Number, Email) on the "Add Engineers" page to assign them to a project.
2. **Issue 2**: A newly created engineer or an engineer on the Bench shows **`Absent (no info)`** for past dates in the current month prior to their project assignment date, falsely inflating absent counts.

This document details the root cause of both issues and provides the exact architectural solutions to resolve them permanently.

---

## Issue 1: Keycloak User Provisioning & Project Assignment Workflow

### Problem Statement
When an administrator creates a user in Keycloak (e.g., `sameer` / `dev.sameer@fosteringlinux.com`), the user can log in to the Attendance Application via Keycloak SSO. Upon login, the application correctly states:
> *"Your account has no access yet. Ask your TL/PM to add your email to the team, or the administrator to give you access."*

However, when a Project Manager or Admin tries to assign this user to a project on `/team`, there is no option to pick the existing Keycloak user. Instead, they must fill in the entire **Add Engineers** form from scratch (Name, Role, Mobile Number, Email, Shift Start). Furthermore, the portal permits adding the exact same email again because the user profile was not yet registered in the Attendance PostgreSQL `app_users` table.

### Root Cause
1. **Keycloak Admin Console vs. PostgreSQL Synchronization**:
   * Users created via the Keycloak Admin Console are saved into Keycloak's internal database (`user_entity`).
   * Keycloak's UserStorage SPI handles authentication against PostgreSQL, but does not push newly created Keycloak Admin Console users into PostgreSQL `app_users`.
2. **Missing Auto-Provisioning on First SSO Login**:
   * When a user logs in via Keycloak SSO for the first time, the Attendance app authenticates the OIDC token, but does not auto-create a corresponding row in `app_users` with `current_project_id = NULL` (Unassigned / Bench Pool).

---

### Solution Strategy for Issue 1

1. **Automatic SSO User Provisioning (Auto-Capture)**:
   * When any user logs in via Keycloak OIDC for the first time:
     * Check if their email exists in `app_users`.
     * If not found, automatically insert a new user record in `app_users` with:
       * `name` = OIDC Name (or First Name + Last Name)
       * `email` = OIDC Email
       * `username` = OIDC Preferred Username
       * `current_project_id` = `NULL` *(Unassigned / Available Bench Pool)*
       * `active` = `1`
2. **Immediate Placement into Available Engineers (Bench Pool)**:
   * As soon as a user logs in via Keycloak for the first time, they instantly appear under **Available Engineers (Bench Pool)** on `/team`.
3. **1-Click Project Assignment for PMs/TLs/Admins**:
   * PMs, TLs, and Admins can see the user on the Bench list and click **`+ Assign to this Project`**.
   * **Zero Manual Re-Entry**: PMs no longer need to type the engineer's name, mobile number, or email manually.

---

## Issue 2: False Absences for Unassigned / Bench / Transferred Engineers

### Problem Statement
When a newly created or unassigned engineer (e.g., `Mohd Sameer`) is assigned to a project mid-month (e.g., on Wednesday, October 14, 2026), viewing their monthly attendance on `/me` displays **`Absent (no info)`** (red badge) for past dates in the month (e.g., Monday, October 12, 2026) where attendance was submitted for that project team.

Furthermore, if an engineer is attending the office while on the Bench (working on internal tasks without a project assignment), assuming they were absent on a project they were not assigned to creates false attendance penalties.

### Root Cause
1. **Assumption of Static Monthly Project Membership**:
   * The current attendance calculation checks:
     * *Was attendance submitted for this project team on Date X?* $\rightarrow$ **Yes**.
     * *Does Engineer Y have an in/out/leave entry on Date X?* $\rightarrow$ **No**.
     * $\rightarrow$ **Mark Engineer Y as `Absent (no info)` on Date X.**
2. **Ignored Project Effective Dates**:
   * The calculation does not verify whether Engineer Y was actually assigned to that project on Date X. As a result, dates prior to their project assignment date are falsely flagged as absent.

---

### Solution Strategy for Issue 2

1. **Effective Date Tracking on Team Assignments**:
   * Add `assigned_from` (DATE/TIMESTAMP) and `assigned_to` (DATE/TIMESTAMP) columns to the `team` table.
   * When an engineer is assigned to a project, `assigned_from` is set to the assignment date and `assigned_to` is `NULL`.
   * When an engineer is removed or transferred, `assigned_to` is set to the exit date.

2. **Accurate Day-by-Day Attendance Evaluation Logic**:
   When evaluating Date X for an engineer on `/me` or attendance reports:
   * **Case A (Assigned to Project P on Date X)**:
     * Evaluate their attendance record against Project P's submitted attendance for Date X.
   * **Case B (Transferred from Project P1 to Project P2)**:
     * For dates before transfer, evaluate against Project P1's records.
     * For dates after transfer, evaluate against Project P2's records.
   * **Case C (Unassigned / Bench / Not Yet Hired on Date X)**:
     * Display **`Unassigned / Bench`** (neutral gray styling, 0 penalty) instead of marking them as `Absent (no info)`.

---

## Summary of Changes

| Issue | Root Cause | Proposed Fix | Expected Outcome |
| :--- | :--- | :--- | :--- |
| **Issue 1** | Keycloak created users stay in Keycloak DB and are missing from `app_users`. | Auto-provision `app_users` on first Keycloak OIDC login with `current_project_id = NULL`. | User appears in **Available Engineers (Bench Pool)** immediately; PM assigns with 1 click. |
| **Issue 2** | Attendance evaluator assumes engineer was in current project for all days of the month. | Add `assigned_from` & `assigned_to` to `team`. Evaluate day-by-day against active team dates. | Unassigned/bench dates display **`Unassigned / Bench`** neutrally with 0 absent count. |
