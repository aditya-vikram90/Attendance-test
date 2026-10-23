# Step 3: Attendance Portal Team & Project Allocation Migration

**Status**: ✅ COMPLETED & FULLY VERIFIED  
**Date**: October 13, 2026  
**Component**: Attendance Service Backend (`app.py`), UI Template (`team.html`), Database Synchronization  
**Branch**: `attendance-management`  

---

## 1. Executive Summary

In Step 3, the Attendance Portal was successfully updated to enhance **Team Roster Management, Engineer Allocation, and Reassignment Workflows**. 

Under this model:
1. **Active Team Management**: Every project maintains a clean view of its active team members.
2. **Available Engineers (Bench Pool)**: Unassigned engineers reside in a dedicated pool (`current_project_id IS NULL`) and are clearly displayed on the Team page.
3. **1-Click Allocation**: Project Managers and Admins can assign available engineers to their active project with a single click.
4. **Project Reassignment**: Removing or transferring an engineer preserves 100% of their historical attendance logs while updating their project roster.
5. **Admin Reassignment**: Administrators have full cross-project authority to reassign engineers between teams as project needs evolve.

---

## 2. Database State & Cleanup

Before enabling single-project constraints in the application, legacy redundant project memberships in PostgreSQL were deactivated to reflect the central user assignments:

```sql
-- Deactivate legacy team records where project_id does not match current_project_id
UPDATE team 
SET active = 0 
FROM app_users 
WHERE team.user_id = app_users.id 
  AND team.project_id <> CAST(app_users.current_project_id AS text);
```

### Current Clean Assignment State:
| ID | Engineer Name | Role Title | Active Project | Status |
|:---|:---|:---|:---|:---|
| 1 | System Admin | Admin | — | System Admin |
| 2 | Rahul Sharma | Project Manager | Cloud Migration & Infra (1) | Active PM |
| 3 | Priya Verma | Project Manager | Client Web Portal (2) | Active PM |
| 4 | Arun Kumar | Frontend Engineer | Client Web Portal (2) | Active Engineer |
| 5 | Neha Gupta | Backend Engineer | Cloud Migration & Infra (1) | Active Engineer |
| 6 | Vikram Singh | DevOps Engineer | Cloud Migration & Infra (1) | Active Engineer |
| 7 | Anjali Patel | Mobile Developer | Mobile Banking App (3) | Active Engineer |
| 8 | Mohd Sadik | Developer | Cloud Migration & Infra (1) | Active Engineer |
| 9 | Zaid Khan | QA Engineer | *(None)* | **Available (Bench Pool)** |

---

## 3. Implementation Details

### A. Backend (`attendance-service/app.py`)

1. **Bench Query in `team_page()` (`/team`)**:
   Retrieves all unassigned active company engineers:
   ```python
   bench = [dict(r) for r in db().execute("""
       SELECT id, name, email, phone, role_title, current_shift_start
       FROM app_users
       WHERE active = 1 AND current_project_id IS NULL AND role_title NOT IN ('Admin', 'Project Manager')
       ORDER BY lower(name)
   """).fetchall()]
   ```

2. **1-Click Bench Assignment (`/team/assign_bench` [POST])**:
   * Validates engineer is unassigned (`current_project_id IS NULL`).
   * Sets `app_users.current_project_id = pid`.
   * Inserts or reactivates row in `team` with `active = 1` and `user_id = app_users.id`.
   * Flashes: *"Assigned [Name] from the bench pool to this project."*

3. **Release to Bench in `team_update()` (`/team/update` [POST])**:
   * When action is `"remove"`: Sets `team.active = 0` and `app_users.current_project_id = NULL`.
   * Flashes: *"Removed member from project and released them to the Available Engineers pool."*

4. **Restore Conflict Guard in `team_update()` (`/team/update` [POST])**:
   * When action is `"restore"`: Verifies engineer is not currently assigned to another project.
   * If assigned to another project, blocks restore: *"Cannot restore: [Name] is currently actively assigned to '[Other Project]'."*

5. **Conflict Prevention in `team_add()` (`/team/add` [POST])**:
   * Looks up engineer in `app_users` by email or phone:
     * **If active in another project**: Rejects addition with informative error.
     * **If on bench**: Automatically assigns from bench to this project.
     * **If brand new employee**: Inserts into `app_users` with BCrypt temporary password `Keenable@2026` (`must_change_password = true`) and adds to `team`.

6. **Admin Direct Transfer Route (`/admin/transfer_engineer` [POST])**:
   * Admin-only endpoint.
   * Deactivates engineer in old project (`team.active = 0`).
   * Updates `app_users.current_project_id = target_pid`.
   * Inserts or reactivates engineer in target project (`team.active = 1`).

---

### B. Frontend (`attendance-service/templates/team.html`)

1. **Available Engineers (Bench Pool) Table**:
   * Displays all unassigned engineers with columns: **Engineer Name**, **Role Title**, **Contact Number**, **Email**, and **Action**.
   * 1-Click button: **`+ Assign to this Project`**.
   * When empty: *"No unassigned engineers currently on the bench. All company engineers are assigned to active projects. You can add new engineers below under 'Add engineers'."*

2. **Admin Transfer Section**:
   * Rendered only for administrators (`is_admin`).
   * Provides quick selection of any engineer and target project with a **"Transfer Engineer Now"** action.

3. **Anchor Navigation**:
   * Added `id="add-engineers"` to the addition form, allowing direct jump navigation from the empty bench alert.

---

## 4. Commands Executed During Step 3

### Database Cleanup:
```bash
ssh root@159.65.155.30 "
podman exec openproject-db psql -U attendance -d attendance -c \"
UPDATE team 
SET active = 0 
FROM app_users 
WHERE team.user_id = app_users.id 
  AND team.project_id <> CAST(app_users.current_project_id AS text);
\""
```

### Deploy Files to Server:
```bash
scp attendance-service/app.py root@159.65.155.30:/opt/attendance-service/app.py
scp attendance-service/templates/team.html root@159.65.155.30:/opt/attendance-service/templates/team.html
```

### Rebuild Container & Restart Service:
```bash
ssh root@159.65.155.30 "
podman build -t localhost/attendance:latest /opt/attendance-service && \
systemctl restart attendance && \
systemctl status attendance --no-pager
"
```

---

## 5. Verification & Acceptance Test Results

An automated acceptance test suite was executed directly against the live attendance container covering all 6 core requirements:

| Test Case | Scenario | Expected Result | Live Result |
|:---|:---|:---|:---|
| **Test 1** | Bench Pool Rendering | Zaid Khan appears in Bench Pool table | **PASS** ✅ |
| **Test 2** | 1-Click Bench Assignment | Zaid Khan moves to Project 1, DB updated, empty bench message displayed | **PASS** ✅ |
| **Test 3** | Duplicate Conflict Guard | Attempting to add Neha Gupta (Project 1) to Project 2 is rejected | **PASS** ✅ |
| **Test 4** | Admin Direct Transfer | Admin moves Zaid Khan from Project 1 to Project 2 directly | **PASS** ✅ |
| **Test 5** | Release to Bench | Removing Zaid Khan from Project 2 clears project and returns him to Bench | **PASS** ✅ |
| **Test 6** | Restore Safe Guard | Cannot restore inactive member if assigned to another project in interim | **PASS** ✅ |

**Summary Output**: `=== ALL ACCEPTANCE TESTS PASSED SUCCESSFULLY! ===`

---

## 6. Post-Migration UI/UX Refinements & Bug Fixes

Following live testing, 3 UI/UX issues were resolved:
1. **Transferred Member Status Badge**:
   - Inactive project records where the engineer is actively assigned to another project now display `Active in: <Project Name>` badge instead of a misleading "Put back" button.
   - The source description displays `transferred to <Project Name>` instead of generic `removed`.
2. **Admin Transfer Dynamic Target Filtering**:
   - The Admin Transfer panel now attaches `data-current-project` and dynamically disables/hides the engineer's current project from the "Transfer To Project" list.
   - Backend validation in `/admin/transfer_engineer` verifies that an engineer cannot be transferred to their own current project.
3. **Refined Conflict Messaging**:
   - `team_add()` provides explicit error messaging when entering an email or contact number belonging to an existing active engineer, explaining who the email belongs to and where they are assigned.

