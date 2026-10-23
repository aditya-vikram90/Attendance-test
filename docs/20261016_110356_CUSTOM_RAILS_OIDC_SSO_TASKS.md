# Custom Rails OIDC SSO Tasks & Execution Tracker

**Timestamp**: 2026-10-16 13:52:00 IST  
**Document Path**: `/home/user/Desktop/Projects/management/attendance/docs/20261016_110356_CUSTOM_RAILS_OIDC_SSO_TASKS.md`  
**Execution Rule**: We execute **ONE step at a time**. After completing each step, we stop, report the exact verification output, and wait for explicit user approval before proceeding to the next step.

---

## 1. Architectural Overview

To achieve **True Zero-Click Single Sign-On (SSO)** in OpenProject Community Edition without Enterprise license bypasses:
- We develop a self-contained Rails extension in `/home/user/Desktop/Projects/management/openproject_sso/keycloak_sso.rb`.
- The extension intercepts unauthenticated visits to `/login`, immediately redirecting the user to Keycloak realm `keenable` (`/auth/realms/keenable/protocol/openid-connect/auth`).
- Keycloak detects the user's active session from Attendance and immediately redirects back to `https://pm.keenable.io/login?code=...`.
- OpenProject exchanges the code for the user profile, sets the native Rails session (`login_user!(user)`), and drops the user straight onto the dashboard with zero manual clicks or password entry.
- Emergency local password login is preserved at `https://pm.keenable.io/login?local=1`.
- Mounted declaratively via Podman Quadlet (`/etc/containers/systemd/openproject.container`) as a read-only volume into OpenProject's native patch loader (`/app/lib/open_project/patches/keycloak_sso.rb`).
- All prior temporary FDW database objects have been cleanly reverted, keeping the central identity database (`users`) 100% decoupled and pristine.

---

## 2. Step-by-Step Task Tracker

### Step 0: Clean Reversion of Database Password-Sharing Objects
* **Status**: `COMPLETED` (Verified on 2026-10-16 11:10:40 IST)
* **Actions Completed**:
  1. Dropped trigger `trg_sync_app_users_to_openproject` from `app_users` table.
  2. Dropped trigger function `fn_sync_app_users_to_openproject()`.
  3. Dropped foreign tables: `op_remote_users_insert`, `op_remote_user_passwords_insert`, `op_remote_users`, `op_remote_user_passwords`.
  4. Dropped user mapping and foreign server `openproject_db_server CASCADE`.
  5. Restored `fn_app_users_after_delete()` to its clean attendance-only version.
* **Verification Result**: Verified database catalog in `users` database:
  - Foreign servers: Only `attendance_db_server` remains (`openproject_db_server` removed).
  - Foreign tables: Only `remote_access`, `remote_project_access`, `remote_watch`, `remote_team` remain (all `op_remote_*` removed).
  - Triggers on `app_users`: Only `trg_app_users_delete` remains.
  - Central database `users` is 100% decoupled.

---

### Step 1: Keycloak OIDC Client Configuration
* **Status**: `COMPLETED` (Verified on 2026-10-16 10:54:20 IST)
* **Configuration**:
  - Realm: `keenable`
  - Client ID: `openproject`
  - Secret: `OpenProjectSecret2026!`
  - Callback URIs:
    - `https://pm.keenable.io/login`
    - `https://pm.keenable.io/*`
  - Web Origins: `https://pm.keenable.io`
* **Verification Result**: Verified client registration and configuration via `kcadm.sh get clients/1eccbd20-5f4b-4b6c-9449-0111273259e4 -r keenable`.

---

### Step 2: Develop Auto-Redirect Rails OIDC SSO Extension
* **Status**: `COMPLETED` (Verified on 2026-10-16 13:31:00 IST)
* **Target File**: `/home/user/Desktop/Projects/management/openproject_sso/keycloak_sso.rb`
* **Actions Completed**:
  1. Built `KeycloakAccountControllerPatch` prepended directly into OpenProject's `AccountController`.
  2. Automatically intercepts GET/HEAD requests to `/login` when user is unauthenticated, generating CSRF `state` and redirecting directly to Keycloak OIDC authorize URL.
  3. Preserves `params[:local] == '1'` bypass to allow emergency administrator / local password logins.
  4. Implements authorization code exchange with Keycloak `/token` endpoint and profile retrieval from `/userinfo`.
  5. Auto-provisions or links OpenProject `User` records by email/login, and executes `login_user!(user)`.
* **Verification Result**: `ruby -c /home/user/Desktop/Projects/management/openproject_sso/keycloak_sso.rb` &rarr; `Syntax OK`.

---

### Step 3: Deploy via Podman Quadlet & Verify Auto-Redirect
* **Status**: `COMPLETED` (Verified on 2026-10-16 13:51:23 IST)
* **Target Path**: `/app/lib/open_project/patches/keycloak_sso.rb` inside container `openproject`
* **Actions Completed**:
  1. Copied script to `/opt/openproject_sso/keycloak_sso.rb` on the server host.
  2. Added declarative read-only volume mount to Podman Quadlet unit `/etc/containers/systemd/openproject.container`:
     `Volume=/opt/openproject_sso/keycloak_sso.rb:/app/lib/open_project/patches/keycloak_sso.rb:ro`
  3. Reloaded systemd (`systemctl daemon-reload`) and restarted OpenProject (`systemctl restart openproject`).
* **Verification Result**:
  - **Auto-Redirect Check**:
    ```bash
    curl -k -s -D - https://pm.keenable.io/login -o /dev/null | grep -E 'HTTP/|location:'
    # Output:
    HTTP/1.1 302 Found
    location: https://pm.keenable.io/auth/realms/keenable/protocol/openid-connect/auth?client_id=openproject&response_type=code&scope=openid+email+profile&redirect_uri=https%3A%2F%2Fpm.keenable.io%2Flogin&state=...
    ```
  - **Local Password Fallback Check**:
    ```bash
    curl -k -s -D - 'https://pm.keenable.io/login?local=1' -o /dev/null | grep -E 'HTTP/|location:'
    # Output:
    HTTP/1.1 200 OK
    ```

---

### Step 4: End-to-End SSO Testing & Browser Verification
* **Status**: `READY FOR USER VERIFICATION`
* **Test Instructions**:
  1. Open a browser and log into Attendance: `https://pm.keenable.io/attendance/`
  2. In another tab (or same tab), visit: `https://pm.keenable.io/` or `https://pm.keenable.io/login`
  3. Observe that you are automatically and instantly logged into the OpenProject dashboard without entering any credentials!
  4. (Optional Emergency Check): Visit `https://pm.keenable.io/login?local=1` to verify the standard password login form is displayed if ever needed.
