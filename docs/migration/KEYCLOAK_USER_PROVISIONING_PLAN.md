# Implementation Plan: Automated Keycloak User Provisioning from Attendance

Automatically provision a Keycloak user account in the `keenable` realm whenever a Project Manager or Admin adds a new engineer under the "My team" tab (`/team/add`), configured with a temporary password that forces the user to set their own permanent password on first login (Option 1).

## User Review Required

> [!IMPORTANT]
> **Temporary Password Policy for New Engineers**:
> * When an engineer is added with an email, their initial temporary password will be set to **`Keenable@2026`** (with Keycloak flag `"temporary": true`).
> * Upon their first login at `https://pm.keenable.io/attendance/`, Keycloak will intercept the login and **force them to set their own private password** before granting access.
> * The portal will display an on-screen confirmation banner informing the PM/Lead:
>   `"Added [Name] to team. Keycloak account created with temporary password: Keenable@2026 (User must change password on first login)."`

> [!NOTE]
> **Edge Cases Handled**:
> 1. **Existing Keycloak Users**: If an engineer already has a Keycloak account (e.g. from another project or previous creation), the app detects this (409 Conflict) and cleanly adds them to the project team without throwing an error.
> 2. **Optional Email**: If an engineer is added without an email (manual offline tracking), Keycloak creation is safely skipped.

---

## Proposed Changes

### Component 1: Keycloak Service Account Configuration

Enable Service Accounts on the existing `attendance` client in Keycloak so the Attendance Python backend can securely call Keycloak's Admin REST API using its existing client secret (`Att3nd_Client_Secret_2026!`).

#### Keycloak Commands via `kcadm.sh`
1. Enable service accounts on the `attendance` client:
   ```bash
   kcadm.sh update clients/<attendance-client-id> -r keenable -s serviceAccountsEnabled=true
   ```
2. Grant the service account the `manage-users` role from the `realm-management` client:
   ```bash
   kcadm.sh add-roles -r keenable --uusername service-account-attendance --cclientid realm-management --rolename manage-users
   ```

---

### Component 2: Attendance Service Backend (`app.py`)

#### [MODIFY] [app.py](file:///home/user/Desktop/Projects/Open%20Project/attendance/attendance-service/app.py)

1. **Add Keycloak Admin Helper Function `keycloak_create_user(email, name)`**:
   * Requests an OAuth2 service token using client credentials:
     `POST /auth/realms/keenable/protocol/openid-connect/token` (`grant_type=client_credentials`, `client_id=attendance`, `client_secret=...`).
   * Splits `name` into `firstName` and `lastName`.
   * Calls `POST /auth/admin/realms/keenable/users`:
     ```json
     {
       "username": email,
       "email": email,
       "firstName": first_name,
       "lastName": last_name,
       "enabled": true,
       "emailVerified": true,
       "credentials": [
         {
           "type": "password",
           "value": "Keenable@2026",
           "temporary": true
         }
       ]
     }
     ```
   * Returns a status tuple: `(True, "created")` or `(True, "already_exists")` or `(False, error_msg)`.

2. **Integrate into `team_add()` route (`/team/add`)**:
   * When inserting a new member with a valid `mail`, call `keycloak_create_user(mail, name)`.
   * Format the flash notification to clearly inform the PM of the temporary password:
     ```python
     if kc_status == "created":
         flash(f"Added {name}. Keycloak account created! Temporary password: Keenable@2026 (User must change password on first login).", "ok")
     elif kc_status == "already_exists":
         flash(f"Added {name}. Linked to existing Keycloak account.", "ok")
     elif kc_status == "skipped":
         flash(f"Added {name} to team.", "ok")
     else:
         flash(f"Added {name} to team, but Keycloak account creation failed: {kc_err}", "warn")
     ```

---

### Component 3: Server Configuration & Sync

#### [MODIFY] [attendance.env](file:///etc/attendance/attendance.env)
Ensure internal Keycloak Admin API endpoint is reachable:
* Confirm `KEYCLOAK_ADMIN_URL=http://127.0.0.1:8085/auth` or reuse existing `OIDC_ISSUER`.

---

## Verification Plan

### 1. Keycloak Service Account Verification
* Run `kcadm.sh` to verify `service-account-attendance` has `manage-users` role.
* Test client credentials token generation via `curl`.

### 2. End-to-End Application Flow
1. **Add a New Engineer via Portal UI**:
   * Log into `https://pm.keenable.io/attendance/` as `Rahul Sharma` (`pm.sharma@keenable.io`).
   * Go to **"My team"** tab.
   * Add engineer:
     * Name: `Zaid Khan`
     * Role: `QA Engineer`
     * Phone: `9876543210`
     * Email: `dev.zaid@keenable.io`
     * Shift: `09:30 AM`
   * Click **"Add to team"**.
   * Verify the flash message displays: *"Added Zaid Khan. Keycloak account created! Temporary password: Keenable@2026 (User must change password on first login)."*

2. **Verify in Keycloak DB / Admin API**:
   * Verify user `dev.zaid@keenable.io` exists in Keycloak `user_entity` with `email_verified=true`.
   * Verify credential has `temporary=true` and required action `UPDATE_PASSWORD`.

3. **Verify First-Time Login & Forced Password Reset**:
   * Open an Incognito window and browse to `https://pm.keenable.io/attendance/`.
   * Sign in as `dev.zaid@keenable.io` with temporary password `Keenable@2026`.
   * Confirm Keycloak prompts the user: **"Update password - You need to change your password to activate your account."**
   * Enter a new permanent password (e.g. `ZaidSecure2026!`).
   * Confirm the user is automatically logged in and lands on their personal attendance view (`/me`) showing their shifts and attendance history.
