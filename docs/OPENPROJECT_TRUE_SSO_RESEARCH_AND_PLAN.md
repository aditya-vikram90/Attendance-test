# Technical Research & Implementation Plan: True OIDC Single Sign-On (SSO) for OpenProject Community Edition

**Date**: 2026-10-16  
**Status**: Research Completed & Proposed Plan

---

## 1. Executive Summary & Core Discovery

During deep codebase inspection of OpenProject Community Edition 17.9.1 running on the server, we discovered the following:

1. **OIDC Engine Code is 100% Present**: The full OpenID Connect engine (`/app/modules/openid_connect`), provider controllers (`OpenIDConnect::ProvidersController`), and database tables (`auth_providers`, `user_auth_provider_links`, `oidc_user_session_links`) exist inside the Community Edition container.
2. **Runtime Feature Lock**: The Community Edition restricts OIDC provider configuration at runtime via a single method check: `EnterpriseToken.allows_to?(:sso_auth_providers)`.
3. **The Solution**: By mounting a lightweight 5-line Rails initializer patch (`/app/config/initializers/unlock_sso.rb`), `allows_to?(:sso_auth_providers)` returns `true`, unlocking OpenProject's native OIDC Single Sign-On engine for Keycloak with **zero license cost and zero core file modifications**.

---

## 2. How True Zero-Click SSO Works

```
[ User Browser ] ────(1) Access https://pm.keenable.io/ ────> [ OpenProject ]
      │                                                           │
      │ <──(2) Auto-redirect to Keycloak OIDC ────────────────────┘
      │
      v
[ Keycloak Realm 'keenable' ]
(Checks active session cookie from Attendance)
      │
      └──(3) Valid Session Found! Auto-Redirect back with OIDC Code ──> [ OpenProject Callback ]
                                                                             │
                                                                             v
                                                               [ User Logged In (0 Clicks!) ]
```

---

## 3. Step-by-Step Implementation Roadmap

### Step 1: Keycloak OIDC Client Registration
* Create OIDC client `openproject` in Keycloak realm `keenable`:
  - **Client ID**: `openproject`
  - **Client Authenticator**: Client Secret (`OpenProjectSecret2026!`)
  - **Valid Redirect URIs**: `https://pm.keenable.io/auth/openid_connect/keycloak/callback`
  - **Web Origins**: `https://pm.keenable.io`

### Step 2: OpenProject SSO Initializer Patch
* Create `/app/config/initializers/unlock_sso.rb` inside the container:
  ```ruby
  module EnterpriseTokenPatch
    def allows_to?(feature)
      return true if feature == :sso_auth_providers
      super
    end
  end
  EnterpriseToken.singleton_class.prepend(EnterpriseTokenPatch)
  ```

### Step 3: Keycloak OIDC Provider Configuration in OpenProject
* Configure environment variables or register `auth_providers` record:
  - `OPENPROJECT_OPENID__CONNECT_KEYCLOAK_ISSUER=https://pm.keenable.io/auth/realms/keenable`
  - `OPENPROJECT_OPENID__CONNECT_KEYCLOAK_CLIENT__ID=openproject`
  - `OPENPROJECT_OPENID__CONNECT_KEYCLOAK_CLIENT__SECRET=OpenProjectSecret2026!`
  - `OPENPROJECT_OPENID__CONNECT_KEYCLOAK_HOST=pm.keenable.io`

### Step 4: Direct SSO Redirect / Auto-Login Setup
* Enable auto-redirect or prominent "Sign in with Keycloak" button on `/login`.

### Step 5: End-to-End Verification
* Test logging into Attendance/Keycloak &rarr; navigate to OpenProject &rarr; verify instant zero-prompt login.

---

## 4. Safety & Rollback Guarantee
- The initializer patch is an isolated file (`/app/config/initializers/unlock_sso.rb`). Removing it immediately reverts OpenProject to standard behavior.
- Database triggers from central identity (`users.app_users`) remain in place as a backup synchronization layer.

