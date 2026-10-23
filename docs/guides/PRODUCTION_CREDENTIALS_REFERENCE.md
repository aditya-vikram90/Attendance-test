# 🔐 Master Credentials & Secrets Reference

This document contains every credential, database secret, administrative password, and test user account configured across the Attendance Management infrastructure.

---

## 1. Keycloak Identity Provider Credentials

### 1.1 Master Admin Console
* **URL**: `http://localhost:8085/auth/admin` *(or `https://<DOMAIN>/auth/admin`)*
* **Realm**: `master`
* **Username**: `admin`
* **Password**: `KeycloakAdmin2026!`

### 1.2 OpenID Connect (OIDC) Clients (`keenable` realm)

| Client ID | Client Type | Client Secret | Purpose |
| :--- | :--- | :--- | :--- |
| **`attendance`** | Confidential | `Att3nd_Client_Secret_2026!` | Used by the Flask/Gunicorn Attendance Service |
| **`attendance-mobile`** | Public (PKCE) | *(None - Public Client)* | Used by the Android mobile application |
| **`openproject`** | Confidential | `OpenProjectSecret2026!` | Used by OpenProject zero-click SSO |

---

## 2. PostgreSQL 17 Database Credentials

* **Internal Connection**: `127.0.0.1:5432` / `openproject-db:5432`

| Role / User | Password | Database | Privileges / Scope |
| :--- | :--- | :--- | :--- |
| **`openproject`** | `52d6616efa2211ce07f9d4415ae04773f988f8a8949d2799` | `openproject` | Engine Superuser / Admin |
| **`users_admin`** | `UsersAdmin2026!` | `users` | Owner of master `app_users` table |
| **`keycloak`** | `KC_Db_Pass_2026_Sec!` | `keycloak` | Owner of Keycloak internal schema |
| **`attendance`** | `Att3nd_Pass_2026_Sec!` | `attendance` | Owner of attendance tables + FDW mapping |

### Database Connection Strings (Internal)
* **Attendance App**: `postgresql://attendance:Att3nd_Pass_2026_Sec!@openproject-db:5432/attendance`
* **Keycloak Quarkus**: `jdbc:postgresql://openproject-db:5432/keycloak` (User: `keycloak`, Pass: `KC_Db_Pass_2026_Sec!`)
* **Keycloak SPI**: `jdbc:postgresql://openproject-db:5432/users` (User: `users_admin`, Pass: `UsersAdmin2026!`)

---

## 3. Federated Employee Accounts (`@keenable.io`)

These users are stored in PostgreSQL (`users.app_users`), verified with BCrypt (`gen_salt('bf', 10)`), and dynamically authenticated by Keycloak:

| Full Name | Email / Username | Password | System Role | Assigned Project / Permissions |
| :--- | :--- | :--- | :--- | :--- |
| **System Admin** | `admin@keenable.io` | `KeenableAdmin2026!` | `admin` | Full Super Admin (`/settings`, `/projects`, `/summary`) |
| **Rahul Sharma** | `pm.sharma@keenable.io` | `KeenablePM2026!` | `project-manager` | Lead for *Cloud Migration & Infra* (`/entry`, `/leaves`) |
| **Priya Verma** | `pm.verma@keenable.io` | `KeenablePM2026!` | `project-manager` | Lead for *Client Web Portal* (`/entry`, `/leaves`) |
| **Arun Kumar** | `dev.arun@keenable.io` | `KeenableDev2026!` | `member` | Frontend Engineer (*Client Web Portal*) -> `/me` |
| **Neha Gupta** | `dev.neha@keenable.io` | `KeenableDev2026!` | `member` | Backend Engineer (*Cloud Migration & Infra*) -> `/me` |
| **Vikram Singh** | `dev.vikram@keenable.io` | `KeenableDev2026!` | `member` | DevOps Engineer (*Cloud Migration & Infra*) -> `/me` |
| **Mohd Sadik** | `dev.sadik@keenable.io` | `KeenableDev2026!` | `member` | Developer (*Cloud Migration & Infra*) -> `/me` |

---

## 4. Application Secrets & Integrations

### 4.1 Flask Application Secret Key
* **`SECRET_KEY`**: `248039d9f584e2a859c738ab79116e0329fc09db488c9182390f77bc9568912d`

### 4.2 SMTP Relay (Google Workspace)
* **SMTP Host**: `smtp.gmail.com`
* **SMTP Port**: `587` (STARTTLS)
* **SMTP User**: `oppm@fosteringlinux.com`
* **SMTP App Password**: `bfqzkypnkcmtqrrb`
* **From Address**: `oppm@fosteringlinux.com`
* **Display Name**: `Keenable Portal`
