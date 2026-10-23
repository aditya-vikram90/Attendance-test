# OpenProject Custom Rails OIDC SSO Tasks & Execution Tracker

**Timestamp**: 2026-10-16 10:54:20 IST  
**Location**: `/home/user/Desktop/Projects/management/attendance/docs/20261016_000724_OPENPROJECT_SSO_TASKS.md`  
**Execution Rule**: We execute **ONE task at a time**. After each task, we stop, run verification/testing, report the results, and wait for explicit user approval before moving to the next task.

---

## Architectural Context: Custom Rails OIDC Middleware

To achieve **True Zero-Click Single Sign-On (SSO)** in OpenProject Community Edition without license restrictions or enterprise bypasses, we implement a custom, self-contained OAuth2/OIDC Rails Engine (`keycloak_sso.rb`). 

The middleware handles the OAuth2 code exchange directly with Keycloak realm `keenable` and establishes OpenProject's native user session (`session[:user_id] = user.id`), enabling seamless zero-click SSO between Attendance and OpenProject.

---

## Step-by-Step Task Breakdown

### Task 1: Keycloak OIDC Client Configuration
* **Status**: `COMPLETED` (Verified on 2026-10-16 10:54:20 IST)
* **Actions Completed**:
  1. Authenticated with Keycloak Admin CLI (`kcadm.sh`).
  2. Configured client `openproject` in realm `keenable` (ID: `1eccbd20-5f4b-4b6c-9449-0111273259e4`).
  3. Added exact callback redirect URIs:
     - `https://pm.keenable.io/auth/keycloak/callback`
     - `https://pm.keenable.io/auth/keycloak/*`
     - `https://pm.keenable.io/*`
  4. Verified web origins: `https://pm.keenable.io`.
  5. Verified client secret: `OpenProjectSecret2026!`.
* **Verification Result**: Verified client configuration via `kcadm.sh get clients/1eccbd20-5f4b-4b6c-9449-0111273259e4 -r keenable`. Client active and fully configured.

---

### Task 2: Develop Custom Rails OIDC SSO Engine Code
* **Status**: `PENDING APPROVAL`
* **Planned Actions**:
  1. Create directory `openproject_sso/` in repository.
  2. Write `openproject_sso/keycloak_sso.rb` implementing:
     - OAuth2 redirect handler (`/auth/keycloak/login`)
     - OAuth2 code exchange and token verification (`/auth/keycloak/callback`)
     - User lookup & session initializer (`session[:user_id] = user.id`)
     - Login page button hook
* **Verification Target**: Syntax verification of Ruby code.

---

### Task 3: Deploy & Mount Initializer to OpenProject Container
* **Status**: `PENDING APPROVAL`
* **Planned Actions**:
  1. Mount `keycloak_sso.rb` into OpenProject at `/app/config/initializers/keycloak_sso.rb`.
  2. Verify initializer load via Rails runner.
  3. Restart OpenProject container.
* **Verification Target**: Verify endpoints `/auth/keycloak/login` and `/auth/keycloak/callback` respond with HTTP 302.

---

### Task 4: End-to-End Browser SSO Verification
* **Status**: `PENDING APPROVAL`
* **Planned Actions**:
  1. Test logging into Attendance (`https://pm.keenable.io/attendance/`).
  2. Navigate to OpenProject (`https://pm.keenable.io/`).
  3. Confirm instant zero-click login into OpenProject dashboard.
  4. Commit all files to Git and update documentation.
* **Verification Target**: User confirms successful zero-click SSO in browser.
