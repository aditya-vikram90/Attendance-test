# Comprehensive Analysis: Issues Identified After OpenProject SSO Implementation

**Document Version**: 1.0.0  
**Timestamp**: 2026-10-16 14:35:00 IST  
**Document Path**: `/home/user/Desktop/Projects/management/attendance/docs/20261016_FOUND_ISSUES_AFTER_SSO_IMPL_IN_OPENPROJECT.md`  
**Reference Environments**:
- Keycloak: `https://pm.keenable.io/auth/` (Realm: `keenable`)
- Attendance Application: `https://pm.keenable.io/attendance/`
- OpenProject: `https://pm.keenable.io/`

---

## Executive Summary

Following the initial deployment and live verification of the OpenProject Auto-Redirect Keycloak OIDC SSO extension, comprehensive end-to-end testing revealed 5 specific functional and operational issues across OpenProject, Attendance, and Keycloak:

1. **Role Discrepancy in Attendance**: A user assigned the `member` role in Keycloak is displayed as `TL/PM` with privileged access inside Attendance.
2. **Password Confirmation Failure in OpenProject**: Administrators receive "Wrong password" errors when attempting sensitive operations (e.g., deleting a user, updating user passwords).
3. **Infinite Re-Login Loop on Sign Out**: Clicking "Sign out" in OpenProject does not log the user out; it immediately re-authenticates and lands back on the dashboard.
4. **Outbound User Provisioning Expectation**: A test user created manually inside OpenProject (`test@keenable.com`) does not appear in Keycloak.
5. **Role Desynchronization (Role Revocation Not Reflected)**: Unassigning the `admin` role from a user in Keycloak does not revoke admin privileges in OpenProject or Attendance.

This document provides a root-cause breakdown of each issue, architectural explanations, and the remediation path for each.

---

## Detailed Breakdown & Root Cause Analysis

```
┌───────────────────────────────────────────────────────────────────────────────────────────────────┐
│                                       ISSUE MATRIX OVERVIEW                                       │
├────┬─────────────────────────────┬──────────────────────────┬──────────────────────────┬──────────┤
│ #  │ Issue Title                 │ Affected Component       │ Primary Root Cause       │ Status   │
├────┼─────────────────────────────┼──────────────────────────┼──────────────────────────┼──────────┤
│ 1  │ Wrong Role in Attendance    │ Attendance App           │ Local DB `access` table  │ FIXED &  │
│    │ (`member` vs `TL/PM`)       │ (`attendance` DB)        │ overrides Keycloak roles │ VERIFIED │
├────┼─────────────────────────────┼──────────────────────────┼──────────────────────────┼──────────┤
│ 2  │ Password Error on Sensitive │ OpenProject              │ Sudo-mode checks local   │ FIXED &  │
│    │ Operations (Delete/Update)  │ (`PasswordConfirmation`) │ DB hash; user has no OP  │ VERIFIED │
│    │                             │                          │ password                 │          │
├────┼─────────────────────────────┼──────────────────────────┼──────────────────────────┼──────────┤
│ 3  │ Sign Out Not Working in     │ OpenProject              │ Keycloak OIDC session    │ FIXED &  │
│    │ OpenProject                 │ `AccountController`      │ not cleared; /login      │ VERIFIED │
│    │                             │                          │ auto-reauthenticates     │          │
├────┼─────────────────────────────┼──────────────────────────┼──────────────────────────┼──────────┤
│ 4  │ OP-Created User Not in      │ OpenProject / Keycloak   │ Architectural: OIDC is   │ NEXT     │
│    │ Keycloak                    │ Data Flow Direction      │ Inbound (IdP -> SP),     │          │
│    │                             │                          │ not bidirectional sync   │          │
├────┼─────────────────────────────┼──────────────────────────┼──────────────────────────┼──────────┤
│ 5  │ Role Revocation in Keycloak │ OpenProject & Attendance │ OP persists `admin` flag │ PENDING  │
│    │ Not Reflected in Apps       │ Role Caching & Overrides │ in DB; Attendance uses   │          │
│    │                             │                          │ static `ADMIN_EMAILS`    │          │
└────┴─────────────────────────────┴──────────────────────────┴──────────────────────────┴──────────┘
```

---

### Issue 1: Wrong Role for User in Attendance Application (`member` in Keycloak &rarr; `TL/PM` in Attendance)

#### Phenomenon:
- In Keycloak Admin Console, user `mohd.sadik@fosteringlinux.com` has the realm role `member` assigned, and does **not** have `admin`, `manager`, or `lead` roles.
- In the Attendance application UI (`/attendance/projects`), the top-right header displays `Mohd Sadik · TL/PM · Sign out`, and the user has access to the "Projects" management tab.

#### Root Cause:
In `attendance-service/app.py`, the user's role is determined by the `my_role()` function:
```python
def my_role():
    """admin (settings file) | manager | lead (TL/PM) | None (no access)."""
    if not current_user(): return None
    if is_admin(): return "admin"
    r = access_row()
    if r: return r["role"]                    # <-- OVERRIDES KEYCLOAK!
    if has_role(KC_MANAGER_ROLE): return "manager"
    return "engineer" if my_member_ids() else None
```
Notice line 345–346: `r = access_row()`. This executes:
```sql
SELECT * FROM access WHERE email = 'mohd.sadik@fosteringlinux.com';
```
When querying the Attendance PostgreSQL database on `openproject-db`:
```
             email             | name | role | all_projects 
-------------------------------+------+------+--------------
 arunk.pal@fosteringlinux.com  |      | lead |            0
 mohd.sadik@fosteringlinux.com |      | lead |            0
```
Because a legacy record exists in the local `access` table with `role = 'lead'`, Attendance prioritizes this local database row over Keycloak’s token claims. Thus, the user is granted `TL/PM` (`lead`) rights regardless of what role is assigned in Keycloak.

#### Remediation:
1. Clean up or synchronize the local `access` table in the `attendance` database so that Keycloak roles act as the single source of truth.
2. Update `attendance-service/app.py` so that if a user has realm role `member` (or lacks manager/lead roles in Keycloak), the local legacy `access` row is either reconciled or superseded.

---

### Issue 2: Password Error for Sensitive Operations in OpenProject (Deleting User, Updating Password)

#### Phenomenon:
- When an administrator attempts to perform sensitive administrative actions inside OpenProject (such as deleting a user at `/users/:id` or updating a password), OpenProject prompts for "Confirm with your password".
- When entering the administrator password, OpenProject rejects the confirmation with a "Wrong password" error.

#### Root Cause:
OpenProject includes a security filter called `PasswordConfirmation` (`/app/app/controllers/concerns/password_confirmation.rb`):
```ruby
module PasswordConfirmation
  def check_password_confirmation
    return true unless password_confirmation_required?

    password = params[:_password_confirmation]
    return true if password.present? && current_user.check_password?(password)

    flash[:error] = I18n.t(:notice_password_confirmation_failed)
    redirect_back fallback_location: back_url
    false
  end

  def password_confirmation_required?
    OpenProject::Configuration.internal_password_confirmation? &&
      !User.current.uses_external_authentication?
  end
end
```
And in `User` (`/app/app/models/user.rb`):
```ruby
def uses_external_authentication?
  user_auth_provider_links.any?
end
```
Because our custom OIDC extension establishes sessions directly via `login_user!(user)` without creating a legacy OmniAuth link in `user_auth_provider_links`:
1. OpenProject considers the user to be an **internal local database user** (`uses_external_authentication?` returns `false`).
2. OpenProject triggers `current_user.check_password?(password)` and validates against OpenProject's local `user_passwords` table.
3. Users created or provisioned via SSO **do not have a local OpenProject password** (it is null or an unset random hash).
4. Even for pre-existing accounts (like `oppm@fosteringlinux.com`), their Keycloak password differs from the legacy password hash stored in OpenProject's local database.

#### Remediation:
1. In `keycloak_sso.rb`, patch `PasswordConfirmation#password_confirmation_required?` or `User#uses_external_authentication?` to recognize users authenticated via Keycloak OIDC as using external authentication, OR
2. In `KeycloakAccountControllerPatch`, create an association in `user_auth_provider_links` (or bypass `check_password_confirmation` when the session originates from Keycloak OIDC), so that OpenProject does not request a non-existent local database password.

---

### Issue 3: Sign Out Not Working in OpenProject (Infinite Re-Login Loop)

#### Phenomenon:
- An authenticated user in OpenProject clicks their avatar and selects "Sign out".
- Instead of showing a signed-out screen or login prompt, the browser immediately redirects and lands right back on the OpenProject dashboard as the logged-in user.

#### Root Cause:
1. OpenProject's sign-out handler (`AccountController#logout`) clears the local Rails session (`reset_session`) and redirects the user to `/login`.
2. Our SSO patch intercepts unauthenticated requests to `/login` and immediately issues an HTTP 302 redirect to Keycloak:
   `https://pm.keenable.io/auth/realms/keenable/protocol/openid-connect/auth?...`
3. However, clicking "Sign out" in OpenProject **only destroyed OpenProject's Rails session; it did NOT terminate the user's Keycloak SSO session**.
4. In the browser, the Keycloak session cookie (`KEYCLOAK_IDENTITY`) is still completely active.
5. Keycloak receives the `/auth` request, detects the active session, generates a fresh authorization code, and redirects back to `https://pm.keenable.io/login?code=...`.
6. OpenProject exchanges the code and logs the user right back in!

#### Remediation:
We must implement proper **OIDC RP-Initiated Logout** in `keycloak_sso.rb`:
- In `AccountController#logout`, after calling `super` (clearing the Rails session), redirect the user to Keycloak's logout endpoint:
  ```
  https://pm.keenable.io/auth/realms/keenable/protocol/openid-connect/logout?post_logout_redirect_uri=https://pm.keenable.io/login?local=1
  ```
  This clears the Keycloak SSO session and returns the user to the local login page (`/login?local=1`), cleanly ending the session.

---

### Issue 4: Newly Created User in OpenProject is Not Visible in Keycloak

#### Phenomenon:
- An administrator navigated to OpenProject `Administration > Users > New user` and created an account: `test@keenable.com` (First Name: "testing", Last Name: "user").
- The user is visible in OpenProject's user list (created on `10/16/2026 08:44 AM`).
- When checking Keycloak Admin Console (`/auth/admin/master/console/#/keenable/users`), `test@keenable.com` does not exist.

#### Root Cause:
1. **Architectural Role Separation**:
   - Keycloak is the **Identity Provider (IdP)**.
   - OpenProject is a **Service Provider (SP / Consumer)**.
   - They do **not** share a database. Keycloak manages identities in the central `users` database; OpenProject manages projects and work packages in its own PostgreSQL database.
2. **One-Way Inbound Federation**:
   - Single Sign-On functions via **Inbound Just-In-Time (JIT) Provisioning**: Keycloak &rarr; OpenProject.
   - When a user is created in Keycloak (or central identity) and logs into OpenProject, OpenProject automatically creates and synchronizes their account.
   - There is **no outbound sync** from OpenProject &rarr; Keycloak. Creating a user inside OpenProject's local UI writes a row to OpenProject's local database only. OpenProject has no webhook or mechanism to push accounts upstream to Keycloak.

#### Remediation & Operational Guidance:
- **Design Principle**: In a centralized identity architecture, **all user provisioning must originate in Keycloak / Attendance Central Identity**.
- Administrators should not create users directly inside OpenProject's local UI. Once created in Keycloak, users automatically appear in OpenProject upon their first login.

---

### Issue 5: Role Revocation in Keycloak Not Reflected in OpenProject or Attendance

#### Phenomenon:
- An administrator unassigns the `admin` role from a user in Keycloak Admin Console.
- In OpenProject, the user still retains administrator privileges.
- In Attendance, the user still sees administrator controls and pages.

#### Root Cause:

#### Part A: OpenProject Role Persistence
1. OpenProject stores user administrator privileges in its local database column: `users.admin` (`boolean`).
2. In our initial `keycloak_sso.rb` implementation, when a user logs in:
   ```ruby
   user = User.where("lower(mail) = ? OR lower(login) = ?", email, login.downcase).first
   ```
   The extension only updates `firstname` and `lastname`. It does **not** synchronize the `admin` column.
3. Therefore, if a user was previously marked as an administrator (`user.admin = true`), OpenProject retains that boolean in its internal database forever, ignoring changes in Keycloak.

#### Part B: Attendance Role Overrides & Caching
1. In `attendance-service/app.py`:
   ```python
   def is_admin():
       return (bool(email()) and email() in ADMIN_EMAILS) or has_role(KC_ADMIN_ROLE)
   ```
2. In `/etc/attendance/attendance.env`:
   ```ini
   ADMIN_EMAILS=admin@example.com,oppm@fosteringlinux.com,admin@keenable.io
   ```
   If the user's email is present in the `ADMIN_EMAILS` environment variable, they are **hardcoded as an administrator** regardless of what roles Keycloak assigns.
3. In addition, Flask stores user attributes in the signed cookie session (`session["user"]`). An active session does not reflect role changes until the user signs out and logs back in.

#### Remediation:
1. **OpenProject**:
   - Configure a Keycloak Protocol Mapper to include realm roles in the OIDC `/userinfo` response.
   - In `keycloak_sso.rb`, synchronize `user.admin = roles.include?('admin')` on every login, so that revoking the admin role in Keycloak immediately demotes the user in OpenProject.
2. **Attendance**:
   - Ensure users who should have roles dynamically controlled by Keycloak are removed from static `ADMIN_EMAILS` in `attendance.env`.
   - Clear or reconcile the local `access` table.

---

## Action Plan & Proposed Fixes

| Issue | Solution Summary | Implementation Complexity |
| :--- | :--- | :--- |
| **Issue 1 (Attendance Role)** | Clear legacy record from `attendance` DB `access` table; ensure Keycloak role mapping is prioritized. | Low (Database update + app logic verification) |
| **Issue 2 (Password Confirmation)** | Patch `PasswordConfirmation#password_confirmation_required?` in OpenProject to recognize SSO users and skip local password prompt. | Low (Add small method override in `keycloak_sso.rb`) |
| **Issue 3 (Sign Out Loop)** | Override `AccountController#logout` in `keycloak_sso.rb` to redirect to Keycloak OIDC logout endpoint. | Low (Add logout hook in `keycloak_sso.rb`) |
| **Issue 4 (Outbound User Sync)** | Document operational standard: All users must be created in Keycloak (Single Source of Truth). | Operational (Documentation & Process) |
| **Issue 5 (Role Sync & Revocation)** | Pass realm roles from Keycloak to OpenProject; update `user.admin` dynamically on every login in `keycloak_sso.rb`. Clean `ADMIN_EMAILS` in Attendance. | Medium (Keycloak client mapper + `keycloak_sso.rb` update) |

---

