# Technical Implementation Plan: Keycloak Unified Identity & Single Sign-Out (SLO) Architecture

**Document Version**: 1.4.0  
**Date**: October 19, 2026  
**Author**: Engineering Team  
**Status**: Architecture Approved / Implementation Roadmap  
**Target Environments**:
- **Keycloak IdP**: `https://pm.keenable.io/auth/` (Realm: `keenable`)
- **OpenProject**: `https://pm.keenable.io/`
- **Attendance Application**: `https://pm.keenable.io/attendance/`

---

## Executive Summary: Keycloak as the ONLY Source for User Creation

> [!IMPORTANT]
> **Key Architecture Change: STOPPING Manual User Entry on Attendance (`/attendance/team`)**
> - **Stopping "Add Engineers" Manual Creation**: Previously on the **My team** page (`https://pm.keenable.io/attendance/team`), the **"Add engineers"** section allowed TL/PMs to type in Engineer Name, Role, Mobile Number, and Email ("Added by hand"). **This manual user creation form on `/attendance/team` is now COMPLETELY REMOVED / STOPPED.**
> - **Selecting from Keycloak Users**: On `https://pm.keenable.io/attendance/team`, TL/PMs will **ONLY select engineers from the list of pre-existing Keycloak users** via a Keycloak Directory Dropdown.
> - **Single Source of Truth**: All user identities (Username, Name, Email, Contact Number, Roles) are created **exclusively in Keycloak Admin Console** by administrators.
> - **OpenProject Reference Rows**: Direct user creation in OpenProject is disabled. When a Keycloak-created user logs in for the first time, OpenProject automatically generates a read-only reference row.

---

## 1. What Has Been Done So Far & How It Works

```
┌──────────────────────────────────────────────────────────────────────────────────────────────────┐
│                                 CURRENT IMPLEMENTATION STATUS                                    │
├───────────────────────────────┼───────────────────────────────────┼──────────────────────────────┤
│ Component                     │ Work Completed                    │ Status                       │
├───────────────────────────────┼───────────────────────────────────┼──────────────────────────────┤
│ OpenProject Direct SSO        │ Auto-Redirect OIDC Extension      │ Deployed & Working           │
│                               │ (`keycloak_sso.rb`)               │ (Direct to Keycloak Login)   │
├───────────────────────────────┼───────────────────────────────────┼──────────────────────────────┤
│ Attendance Roles              │ Keycloak Realm Roles Enforced     │ Deployed & Working           │
│                               │ (`attendance-service/app.py`)     │ (Legacy DB Overrides Purged) │
├───────────────────────────────┼───────────────────────────────────┼──────────────────────────────┤
│ OpenProject Password Checks   │ Sudo-mode bypassed for SSO users; │ Deployed & Working           │
│                               │ Direct Keycloak Grant Verification│                              │
└───────────────────────────────┴───────────────────────────────────┴──────────────────────────────┘
```

### Details of Current Implementation:

1. **Direct Auto-Redirect Keycloak SSO (`keycloak_sso.rb`)**:
   - **ALREADY IMPLEMENTED**: Unauthenticated access to OpenProject (`https://pm.keenable.io/` or `/login`) is **automatically redirected directly to Keycloak's login page** (`/auth/realms/keenable/protocol/openid-connect/auth`).
   - Users do **not** see any OpenProject native login form or local password input boxes.
   - Handles OAuth authorization code callbacks, exchanges codes for JWT tokens, and seamlessly provisions/authenticates the user in OpenProject.

2. **Attendance Application Single Source of Truth for Roles**:
   - Refactored `my_role()` in `attendance-service/app.py` so Keycloak realm roles (`admin`, `manager`, `lead`, `member`) are strictly enforced.
   - Purged legacy overrides in the `attendance.access` PostgreSQL database table so user permissions dynamically mirror Keycloak roles.

3. **OpenProject Sudo-Mode Password Confirmation Patch**:
   - Patched OpenProject's `PasswordConfirmation` module and `User` model.
   - When administrators perform sensitive operations (e.g., deleting users, changing system parameters), OpenProject verifies credentials against Keycloak's Direct Password Grant API, preventing "Wrong password" errors for SSO accounts.

---

## 2. What Needs To Be Done (Strict Keycloak-First Identity Architecture)

```mermaid
flowchart TD
    subgraph Keycloak - ONLY Place Where Users Are Created
        KC[Keycloak Admin Console]
        KC -->|1. Admin creates user in Keycloak| KCD[(Keycloak Directory)]
    end

    subgraph Attendance App (/attendance/team) - Local Entry STOPPED
        KCD -->|2. TL/PM selects engineer from Keycloak list| ATT[Attendance My Team Page]
        ATT -->|No user creation / Stores only sub ID| ATTB[(Attendance DB - Business Data Only)]
    end

    subgraph OpenProject App
        KCD -->|3. First sign-in auto-creates reference row| OP[OpenProject]
        OP -->|Read-only copy| OPB[(OpenProject DB - Reference Rows)]
    end
```

### A. Attendance Application (Stopping Local User Entry on `/attendance/team`)
1. **STOP "Add Engineers" Manual Creation Form**: Remove the manual text input fields (`Engineer name`, `Role`, `Mobile number`, `Email`) under the **"Add engineers"** section on `https://pm.keenable.io/attendance/team` (**My team** page). No users will be "Added by hand".
2. **Keycloak Directory Engineer Picker**: Replace the manual text fields on `/attendance/team` with a searchable **Keycloak Directory Selection Dropdown**. TL/PMs select pre-existing Keycloak users from the list to assign them to a project team and shift.
3. **No User Table**: Attendance maintains **zero user rows**. It stores only the Keycloak User ID (`sub` UUID) against attendance entries and project assignments. Name, email, and phone are read live from Keycloak directory/claims.
4. **Implement OIDC Back-Channel Logout Receiver (Option C)**: Add a POST endpoint `/attendance/auth/backchannel-logout` in Flask to parse `logout_token` JWTs sent by Keycloak and destroy the user's session upon sign-out.
5. **Remove Hardcoded Admins**: Set `ADMIN_EMAILS=""` in `/etc/attendance/attendance.env` so Keycloak roles exclusively govern administrative privileges.
6. **Periodic Token Validation**: Enforce a 5-minute session re-check interval in Attendance session middleware.

### B. OpenProject Application
1. **Disable Native User Creation & Local Passwords**: Set `OPENPROJECT_DISABLE__PASSWORD__LOGIN=true`. Manual creation of users inside OpenProject is prohibited.
2. **Direct Keycloak Login Provider Flag**: Set `OPENPROJECT_OMNIAUTH__DIRECT__LOGIN__PROVIDER=keycloak` to enforce direct login.
3. **Register Back-Channel Logout Receiver**: Configure OpenProject's OIDC logout endpoint in Keycloak so server-to-server logout tokens invalidate OpenProject sessions upon global sign-out.
4. **User Account Linking**: Link existing OpenProject accounts (e.g. `oppm@fosteringlinux.com`) to Keycloak by matching email address upon first sign-in, and purge test-only local accounts.

### C. Keycloak Realm Configuration
1. **User Profile Schema**: Add `contact_number` custom attribute to the Keycloak user profile schema and populate staff phone numbers.
2. **Client Back-Channel Logout Settings**:
   - `attendance` Client: Set Back-Channel Logout URL to `https://pm.keenable.io/attendance/auth/backchannel-logout`, `Backchannel Logout Session Required = ON`, `Frontchannel Logout = OFF`.
   - `openproject` Client: Register OpenProject back-channel logout URL and post-logout redirect URIs (`https://pm.keenable.io/*`).
3. **Session Expirations**: Set Realm `SSO Session Idle` and `SSO Session Max` timeouts to match working day hours (e.g. 8–10 hours).

---

## 3. Detailed UI & User Experience (UI/UX) Changes

### A. Attendance Application UI Impact (`https://pm.keenable.io/attendance/team`)

| Screen / Flow | Previous UI State | Future UI State (Post-Changes) |
| :--- | :--- | :--- |
| **"My team" Page (`/attendance/team`)** | **"Add engineers" Manual Form**: TL/PMs typed Engineer Name, Role, Mobile Number, and Email manually into text inputs ("Added by hand"). | **STOPPED MANUAL ENTRY**: Text inputs removed. Replaced with a **Keycloak Engineer Selection Dropdown**. TL/PMs pick pre-existing users **from the Keycloak user list**. |
| **Team Member Source Column** | Displayed `"Added by hand"` or `"PM/Lead · Added by hand"`. | Displays `"Keycloak User"` with verified attributes read live from Keycloak. |
| **Contact Number / Email Columns** | Manually entered text saved in local database. | Read-only dynamic attributes rendered straight from Keycloak directory. |
| **Sign-Out Action** | Cleared only Attendance Flask cookie. | **Single Sign-Out (SLO)**: Clicking "Sign out" calls Keycloak OIDC logout, which sends back-channel logout calls to OpenProject, logging out **both applications simultaneously** and returning to Keycloak login. |

#### Visual UI Refactoring Concept: `/attendance/team`
```
┌──────────────────────────────────────────────────────────────────────────────────────────────────┐
│ REFACTORED ATTENDANCE MY TEAM PAGE (https://pm.keenable.io/attendance/team)                      │
├──────────────────────────────────────────────────────────────────────────────────────────────────┤
│ Add Engineer to Team: [ Select Engineer from Keycloak Directory List ▾ ]                          │
│                        │ Search: mohd.sadik@fosteringlinux.com       │                           │
│                        │ Mohd Sadik (mohd.sadik@fosteringlinux)     │                           │
│                        └─────────────────────────────────────────────┘                           │
│ Project: [ test project ▾ ]   Shift Start: [ 09:30 AM ▾ ]   [ + Add Engineer to Team ]           │
├──────────────────────────────────────────────────────────────────────────────────────────────────┤
│ Team Members (Fetched Live from Keycloak Directory):                                             │
│ • Arun Kumar Pal │ Project Manager │ 9650239996 │ arunk.pal@fosteringlinux.com  │ Source: Keycloak │
│ • Mohd Sadik     │ Developer       │ 8279726323 │ mohd.sadik@fosteringlinux.com │ Source: Keycloak │
└──────────────────────────────────────────────────────────────────────────────────────────────────┘
```

---

### B. OpenProject Application UI Impact

| Screen / Flow | Current Deployed State | Future State (Post-Changes) |
| :--- | :--- | :--- |
| **Login Page (`/login`)** | **ALREADY ACTIVE**: Unauthenticated access directly auto-redirects to Keycloak's login screen. No local form is shown. | Maintained via environment variable `OPENPROJECT_OMNIAUTH__DIRECT__LOGIN__PROVIDER=keycloak`. |
| **User Creation (`/admin/users`)** | Native user creation form currently accessible to admins. | **DISABLED**. "Create User" form hidden/disabled. Reference rows auto-created upon first Keycloak login. |
| **Sign-Out Action** | Clears local OpenProject session and redirects to Keycloak logout. | **OIDC Back-Channel Logout**: Clicking "Sign out" in OpenProject terminates sessions across **both** OpenProject and Attendance, taking the user directly to Keycloak's login page. |

---

## 4. Joiner, Mover, Leaver (JML) Workflow Comparison

```
┌──────────────────────────────────────────────────────────────────────────────────────────────────┐
│                                 UNIFIED WORKFLOW MATRIX (SSOT)                                   │
├─────────────────┬────────────────────────────────────────────────────────────────────────────────┤
│ Scenario        │ Unified Workflow Execution                                                     │
├─────────────────┼────────────────────────────────────────────────────────────────────────────────┤
│ **New Joiner**  │ 1. Admin creates user **ONLY in Keycloak** (Name, Email, Phone, Role).         │
│                 │ 2. TL/PM on `/attendance/team` assigns them by selecting from Keycloak list.   │
│                 │ 3. User signs into OpenProject; reference row created automatically.           │
├─────────────────┼────────────────────────────────────────────────────────────────────────────────┤
│ **Role Change** │ 1. Role updated **ONLY in Keycloak** (`engineer` → `lead`/`manager`/`admin`).   │
│                 │ 2. Role change reflects across Attendance and OpenProject within < 5 minutes.  │
├─────────────────┼────────────────────────────────────────────────────────────────────────────────┤
│ **Leaver/Exit** │ 1. Account disabled **ONLY in Keycloak**.                                      │
│                 │ 2. OIDC Back-Channel Logout instantly revokes sessions in OP and Attendance.   │
└─────────────────┴────────────────────────────────────────────────────────────────────────────────┘
```

---

## 5. Technical Implementation Roadmap & Checklist

### Phase 1: OpenProject Environment Flags & Back-Channel Logout
- [ ] Set `OPENPROJECT_DISABLE__PASSWORD__LOGIN=true` in OpenProject environment.
- [ ] Set `OPENPROJECT_OMNIAUTH__DIRECT__LOGIN__PROVIDER=keycloak`.
- [ ] Register OpenProject Back-Channel Logout URL in Keycloak client `openproject`.

### Phase 2: Attendance Application Refactoring (`/attendance/team`)
- [ ] **STOP "Add engineers" manual creation form**: Remove manual text input fields (`Engineer name`, `Role`, `Mobile number`, `Email`) from `/attendance/team`.
- [ ] Implement Keycloak User Directory Search API in Attendance backend.
- [ ] Replace "Add engineers" section on `/attendance/team` with **Keycloak Engineer Selection Dropdown**.
- [ ] Add POST `/attendance/auth/backchannel-logout` endpoint to `attendance-service/app.py`.
- [ ] Set `ADMIN_EMAILS=""` in `/etc/attendance/attendance.env`.
- [ ] Implement 5-minute session validity re-check middleware in Attendance.

### Phase 3: Keycloak Realm Settings & User Cleanup
- [ ] Add `contact_number` user attribute schema in Keycloak and populate staff phone numbers.
- [ ] Configure Keycloak `attendance` client Back-Channel Logout settings.
- [ ] Link existing local accounts by email; remove temporary test accounts.
- [ ] Set Realm SSO Session Idle / Max timeouts to match working day hours.
