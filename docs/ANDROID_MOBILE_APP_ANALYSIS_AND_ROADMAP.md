# Android Mobile Application (K&A Attendance)
## Comprehensive Technical Analysis, Architecture Specification & Defect Assessment Report

---

### Document Overview
- **Document Title:** K&A Attendance Android Mobile Application &mdash; Codebase Analysis, Architecture Specification & Readiness Assessment
- **Application Path:** `/home/user/Desktop/Projects/management/android`
- **Package Name:** `io.keenable.attendance`
- **Target Android Version:** Android 14 (API 34) | Minimum SDK: Android 8.0 (API 26)
- **Primary Technology Stack:** Kotlin, Jetpack Compose, Google Play Services Location/Geofencing, AppAuth (OAuth2/PKCE), AndroidX WorkManager, EncryptedSharedPreferences, SQLite.
- **Backend Service:** Attendance Portal Mobile API (`attendance-service/mobile.py`)
- **Document Purpose:** Complete architectural audit, code analysis, identification of current issues/missing components, and an actionable roadmap to make the mobile application fully operational.

---

## 1. Executive Summary & Codebase Architecture

### 1.1 Purpose and Philosophy of the Mobile App
The **K&A Attendance Android App** is designed for **zero-touch automated attendance tracking**. Unlike traditional mobile attendance applications that require employees to open the app and manually tap "Clock In" or "Clock Out", this application operates automatically in the background using physical work site geofences:
1. **Passive Arrival Detection:** When an employee physically enters a designated work site perimeter (e.g. UPSC Dholpur House HQ, 250m radius), the phone's OS triggers a geofence crossing.
2. **Dwell Verification:** The server requires the employee to stay inside the boundary for a configurable dwell window (e.g. 5 minutes) before officially confirming arrival.
3. **Passive Departure Detection:** When the employee leaves the boundary and remains outside for the dwell-out threshold (e.g. 10 minutes), the departure is recorded.
4. **Anti-Spoofing & Device Binding:** The app detects mock locations (GPS spoofing apps), rooted devices, developer options, and connects to physical Wi-Fi BSSIDs/SSIDs for dual-factor physical presence verification. Each device is cryptographically bound to one employee.

---

### 1.2 High-Level Architectural Diagram

```
+----------------------------------------------------------------------------------------------------+
|                                    Android Mobile Application                                      |
|                                     (io.keenable.attendance)                                       |
+----------------------------------------------------------------------------------------------------+
|                                                                                                    |
|  [ Presentation Layer - Jetpack Compose ]                                                          |
|    MainActivity.kt -> AppVm (State Machine: Loading -> SignedOut -> Consent -> Perms -> Main)      |
|    Tabs: Today (Summary/Events/Disputes) | History (14 Days) | Settings (Battery/Sign-out)         |
|                                                                                                    |
|  [ Security & Identity Layer ]                 [ Anti-Spoofing & Trust Engine ]                    |
|    Auth.kt (AppAuth, OAuth2 + PKCE)              Trust.kt (isMock, Root Detection, Wi-Fi BSSID)   |
|    Store.kt (EncryptedSharedPreferences)                                                           |
|                                                                                                    |
|  [ Location & Geofencing Engine ]              [ Offline Event Queue & Networking ]                |
|    Geo.kt (LocationServices GeofencingClient)    Queue (SQLite queue.db)                           |
|    GeofenceReceiver (BroadcastReceiver)          UploadWorker (WorkManager, Exponential Backoff)   |
|    BackupCheckWorker (15m Periodic Poller)       Api.kt (OkHttpClient with Bearer Token)           |
|                                                                                                    |
+-------------------------------------------------+--------------------------------------------------+
                                                  | REST APIs over HTTPS (Bearer JWT)
                                                  v
+----------------------------------------------------------------------------------------------------+
|                                 Attendance Portal Backend API                                      |
|                                 (attendance-service/mobile.py)                                     |
|  Endpoints: /api/m/config, /api/m/device, /api/m/sites, /api/m/event, /api/m/me/today, /review     |
+----------------------------------------------------------------------------------------------------+
```

---

### 1.3 Key Source Files & Their Responsibilities

| File Path | Lines | Key Components & Classes | Functional Role |
| :--- | :---: | :--- | :--- |
| `app/build.gradle.kts` | 40 | `plugins`, `android`, `dependencies` | Module build configuration; specifies SDK 34, Jetpack Compose BOM, AppAuth, WorkManager, OkHttp, and Google Play Services Location. |
| `AndroidManifest.xml` | 26 | `<manifest>`, `<application>` | App permissions (`FINE_LOCATION`, `BACKGROUND_LOCATION`, `BOOT_COMPLETED`, etc.), activities, and broadcast receivers. |
| `MainActivity.kt` | 197 | `MainActivity`, `AppVm`, `Root`, `MainScreen` | Entry activity and UI state machine. Manages sign-in flow, consent prompt, 2-step location permission requests, today's attendance display, 14-day history, and dispute filing. |
| `Auth.kt` | 55 | `Auth` class | OpenID Connect authentication using AppAuth (`net.openid:appauth`). Performs browser authorization code exchange with PKCE and token refreshes. |
| `Api.kt` | 45 | `Api`, `ApiResult` | HTTP REST client using OkHttp. Handles `/api/m/device`, `/api/m/sites`, `/api/m/config`, and attaches Keycloak Bearer access tokens. |
| `Geo.kt` | 134 | `Geo`, `GeofenceReceiver`, `BootReceiver`, `UploadWorker`, `SiteSyncWorker`, `BackupCheckWorker` | Core location engine. Registers Google Play Services geofences, handles OS transitions, manages WorkManager background synchronization, and enforces monotonic event aging. |
| `Trust.kt` | 27 | `Trust` object | Security checks: detects mock location providers, developer options, root binaries (`/system/bin/su`), and sniffs connected Wi-Fi SSID/BSSID. |
| `Store.kt` | 76 | `Store`, `Site`, `Pending`, `Queue` | Local storage: AES-256 encrypted shared preferences for tokens and device IDs; SQLite database (`queue.db`) for offline event queuing. |
| `gradle.properties` | 12 | Configuration variables | Defines build properties: `PORTAL_URL`, `KC_ISSUER`, and `KC_CLIENT_ID`. |

---

## 2. In-Depth Operational Workflows

### 2.1 First-Time Onboarding & Permissions Workflow
1. **Launch (`MainActivity.kt`):** The app checks `Auth.signedIn()`. If no refresh token exists, state becomes `Screen.SignedOut`.
2. **Sign-In:** The user taps "Sign in". `Auth.signInIntent()` discovers Keycloak OIDC endpoints via `.well-known/openid-configuration` and launches the system browser with PKCE.
3. **Token Exchange:** The browser redirects to `io.keenable.attendance:/oauth2redirect`. AppAuth catches the authorization code, exchanges it for access/refresh tokens, and securely encrypts them in `EncryptedSharedPreferences`.
4. **Device Registration (`Api.sync()`):** The app transmits its unique hardware UUID and device model to `/api/m/device`.
   - If user is not assigned to a project team, API returns HTTP 403: *"Your email is not in a project team."*
   - If the device is new/replaced, API flags `status="pending"`, and UI alerts: *"This is a new phone. Your TL/PM must approve it before check-ins count."*
5. **Consent Screen (`Screen.Consent`):** If the portal requires consent, the terms of geofenced tracking are displayed. User clicks *"I understand and agree"*, transmitting acceptance to `/api/m/consent`.
6. **Two-Step Location Permission (`Screen.Permissions`):**
   - **Step 1:** Asks for `ACCESS_FINE_LOCATION` and `ACCESS_COARSE_LOCATION` ("While using the app").
   - **Step 2:** Prompts user to select **"Allow all the time"** (`ACCESS_BACKGROUND_LOCATION`).
7. **Main Dashboard (`Screen.Main`):** Once permissions are granted, geofences are registered with Google Play Services and background workers are scheduled.

---

### 2.2 Geofence Detection, Monotonic Aging & Offline Queue
When an employee crosses a work site boundary:
1. Google Play Services wakes up `GeofenceReceiver`.
2. `GeofenceReceiver` grabs the trigger location (or queries `FusedLocationProviderClient.lastLocation`).
3. `Geo.record()` calculates the event attributes:
   - `kind`: `ENTER` or `EXIT`
   - `lat`, `lon`, `accuracy`
   - `mock`: Detected via `Location.isMock`
   - `rooted`: Detected via developer settings or `su` binaries
   - `beacons`: Connected Wi-Fi BSSID/SSID
   - **Monotonic Timestamp (`elapsedAt`):** Stored using `SystemClock.elapsedRealtime()`.
4. Event is saved to local SQLite table `queue.db` (`Pending` record).
5. `UploadWorker` is enqueued via WorkManager.
6. When online, `UploadWorker` computes:
   $$\text{age\_s} = \frac{\text{SystemClock.elapsedRealtime}() - \text{elapsedAt}}{1000.0}$$
   *(If the phone rebooted, it falls back to wall clock difference).*
7. The payload is POSTed to `/api/m/event`. The server calculates:
   $$\text{Event Time} = \text{Server Time} - \text{age\_s}$$
   **Crucial Benefit:** The employee cannot cheat attendance by manually changing the clock on their phone!

---

### 2.3 Periodic Backup Check (`BackupCheckWorker`)
Every 15 minutes, `BackupCheckWorker` runs in the background:
- It acquires the phone's current balanced-power location.
- If accuracy $> 100\text{ m}$, the reading is discarded.
- It iterates over all active project sites.
- If the phone is $\le (\text{radius} - 20\text{ m})$ and was previously marked outside, an `ENTER` event is automatically generated.
- If the phone is $\ge (\text{radius} + 50\text{ m})$ and was previously marked inside, an `EXIT` event is automatically generated.
- This serves as a fail-safe in case Android OS missed a boundary crossing.

---

## 3. Critical Issues, Defects & Missing Components in Current Version

Our micro-level code analysis identified **15 critical defects and missing items** preventing the current version from building, running, and functioning properly:

---

### Category A: Build System & Tooling Blockers (P1 - Critical)

#### 1. Missing Gradle Wrapper (`gradlew`)
- **Defect:** The repository at `/home/user/Desktop/Projects/management/android` contains `build.gradle.kts` and `settings.gradle.kts`, but **completely lacks** the Gradle wrapper files:
  - `gradlew` (Linux/macOS shell script)
  - `gradlew.bat` (Windows script)
  - `gradle/wrapper/gradle-wrapper.jar`
  - `gradle/wrapper/gradle-wrapper.properties`
- **Impact:** You cannot build, test, or package the application via command line (`./gradlew assembleDebug`), CI/CD pipelines, or Docker containers without installing a standalone Gradle distribution first.
- **Fix Required:** Generate the Gradle wrapper (Gradle 8.7+ compatible with Android Gradle Plugin 8.5.2).

#### 2. Local Android SDK Not Configured
- **Defect:** `README.md` explicitly notes: *"the source is written but has not been compiled or run yet (it was prepared on a machine without the Android SDK)."*
- **Impact:** The local host environment does not have `ANDROID_HOME`, build-tools 34.0.0, or platform android-34 installed.
- **Fix Required:** Install Android command-line tools or build within an Android SDK Docker container.

---

### Category B: Configuration & Keycloak Integration Defects (P1 - Critical)

#### 3. Invalid Keycloak Issuer URL in `gradle.properties`
- **Defect:** Line 10 of `gradle.properties` specifies:
  ```properties
  KC_ISSUER=http://10.0.2.2:8080/realms/attendance
  ```
  - **Issue A:** In our production and local Docker setups, the Keycloak realm is **`keenable`** (or `master`), **NOT `attendance`**! The path `/realms/attendance` does not exist and will return HTTP 404 when AppAuth attempts to fetch OpenID configuration.
  - **Issue B:** Keycloak in the local docker-compose environment runs on port **`8085`**, NOT `8080`!
  - **Issue C:** The domain `10.0.2.2` only works from inside an official Android emulator. When testing on a physical Android phone over Wi-Fi or mobile data, the app will fail to resolve `10.0.2.2`. It must point to the public domain `https://auth.keenable.io/realms/master` (or local LAN IP).
- **Impact:** The app immediately fails on launch with *"Cannot reach the sign-in service. Check your network."*

#### 4. Missing Keycloak Mobile Client (`KC_CLIENT_ID=attendance-mobile`)
- **Defect:** In `gradle.properties`, `KC_CLIENT_ID` is set to `attendance-mobile`.
- **Impact:** Keycloak does not yet have an `attendance-mobile` client configured.
- **Requirements for Keycloak Client:**
  - Client ID: `attendance-mobile`
  - Client Type: **Public Client** (Client authentication OFF)
  - Standard Flow (Authorization Code) Enabled
  - Direct Access Grants: OFF
  - PKCE: S256 Required
  - Valid Redirect URIs: `io.keenable.attendance:/oauth2redirect`
  - Web Origins: `*`

#### 5. Portal URL Address
- **Defect:** In `gradle.properties`, `PORTAL_URL=http://10.0.2.2:8000`.
- **Impact:** Works only on emulator. For physical device testing, it must point to `https://pm.keenable.io/attendance` (or local host LAN IP e.g. `http://192.168.1.X:8000`).

---

### Category C: Android Manifest & Permission Defects (P1 - Critical)

#### 6. Missing Foreground Service & Type Declarations for Android 14 (API 34)
- **Defect:** The app targets SDK 34 (`targetSdk = 34`). In Android 14, background location execution and long-running workers are strictly restricted.
- **Missing Manifest Permissions:**
  ```xml
  <uses-permission android:name="android.permission.FOREGROUND_SERVICE" />
  <uses-permission android:name="android.permission.FOREGROUND_SERVICE_LOCATION" />
  ```
- **Impact:** On Android 14 devices, attempting to trigger background location updates or WorkManager foreground services without these declared permissions will throw `SecurityException` and crash the application.

#### 7. Missing Notification Permission (`POST_NOTIFICATIONS`) for Android 13+ (API 33+)
- **Defect:** `AndroidManifest.xml` does not declare:
  ```xml
  <uses-permission android:name="android.permission.POST_NOTIFICATIONS" />
  ```
- **Impact:** On Android 13 and 14, apps cannot display any status notifications, check-in alerts, or persistent background service notifications without runtime user permission. Notifications will fail silently.

#### 8. AppAuth Custom Scheme Redirect Declaration in Manifest
- **Defect:** While `app/build.gradle.kts` sets `manifestPlaceholders["appAuthRedirectScheme"] = "io.keenable.attendance"`, there is no explicit intent-filter in `AndroidManifest.xml`. If the AppAuth library manifest merge does not automatically wire up `RedirectUriReceiverActivity`, the browser redirect will not route back into the application.
- **Recommended Manifest Addition:**
  ```xml
  <activity android:name="net.openid.appauth.RedirectUriReceiverActivity"
            android:exported="true">
      <intent-filter>
          <action android:name="android.intent.action.VIEW"/>
          <category android:name="android.intent.category.DEFAULT"/>
          <category android:name="android.intent.category.BROWSABLE"/>
          <data android:scheme="io.keenable.attendance"/>
      </intent-filter>
  </activity>
  ```

#### 9. Cleartext Traffic Block in Release Mode
- **Defect:** `AndroidManifest.xml` has `android:usesCleartextTraffic="false"`.
- **Impact:** If a release APK is generated and pointed to an `http://` internal LAN IP or test server, Android's network security policy will block all OkHttp and AppAuth calls with `java.io.IOException: Cleartext HTTP traffic not permitted`. Release builds must communicate strictly over `https://`, or declare a network security config XML.

---

### Category D: UI & User Experience Gaps (P2 - High)

#### 10. Missing App Launcher Icons & Resource Drawables
- **Defect:** In `AndroidManifest.xml`, `<application>` does not define `android:icon` or `android:roundIcon`.
- **Impact:** The application installs with the default generic green Android robot icon.
- **Fix Required:** Add standard mipmap icon assets (`res/mipmap-hdpi`, `res/mipmap-xhdpi`, etc.) with Keenable branding.

#### 11. No Real-Time Visual Indication of Current Geofence Status
- **Defect:** On the `Today` tab of `MainActivity.kt`, the user sees today's attendance summary from the portal, but **cannot see their current geofence status** (i.e. whether the phone currently considers them **INSIDE** or **OUTSIDE** the office).
- **Impact:** An engineer standing at the office cannot tell if their phone has detected the site until the portal processes an event.
- **Fix Required:** Expose a live visual badge on `MainScreen`: e.g. `🟢 Inside: UPSC Dholpur House (HQ)` or `⚪ Outside Work Site`.

#### 12. Manual Check-in / Punch Fallback Missing
- **Defect:** The app relies 100% on passive geofence triggers. If an employee enters a basement, elevator, or Faraday cage where GPS is unavailable, there is no manual "Request Check-In" or "Force Location Check" button.
- **Fix Required:** Add a "Check Location Now" button that calls `BackupCheckWorker` logic on demand.

#### 13. Background Location Permission Friction on Android 11+
- **Defect:** In `PermissionsScreen` of `MainActivity.kt`, Step 2 calls `bg.launch(Manifest.permission.ACCESS_BACKGROUND_LOCATION)`.
- **Impact:** On Android 11 through 14, Android does not show a system permission dialog for background location. Instead, it requires the user to be redirected to the System App Settings screen and manually select "Allow all the time". If the user taps the back button without selecting the option, the app gets stuck in a loop.
- **Fix Required:** Improve the UI guidance to explicitly explain that the user must click "Allow all the time" in the system settings page that opens.

---

### Category E: Concurrency & Stability Deficiencies (P2 - High)

#### 14. SQLite Database Concurrency in `Store.kt`
- **Defect:** In `Store.kt`, `Queue(c)` is created on the fly as a new `SQLiteOpenHelper` instance inside `GeofenceReceiver`, `BackupCheckWorker`, `UploadWorker`, and `MainActivity`.
- **Impact:** In Android SQLite, creating multiple `SQLiteOpenHelper` instances accessing the same file (`queue.db`) across multiple background threads can trigger `android.database.sqlite.SQLiteDatabaseLockedException`.
- **Fix Required:** Make `Queue` a thread-safe singleton object.

#### 15. Aggressive OEM Battery Killers (Samsung, Xiaomi, OnePlus)
- **Defect:** Line 184 in `MainActivity.kt` opens `Settings.ACTION_IGNORE_BATTERY_OPTIMIZATION_SETTINGS`.
- **Impact:** On Xiaomi (MIUI/HyperOS), Samsung (OneUI), and OnePlus (OxygenOS), standard Android battery optimization whitelist is insufficient. These operating systems aggressively kill background processes unless **"Auto-start"** and **"Run in background"** are explicitly granted in the OEM-specific settings.
- **Fix Required:** Include OEM-specific intent helpers or visual guide cards for Xiaomi/Samsung devices.

---

## 4. Verification of Backend API Compatibility

We cross-referenced the Android application's API client (`Api.kt` & `Geo.kt`) with the live backend implementation in `attendance/attendance-service/mobile.py`:

| Android Route | Method | Payload / Headers | Backend Endpoint in `mobile.py` | Compatibility Status |
| :--- | :---: | :--- | :--- | :---: |
| `/api/m/device` | POST | `device_id`, `model` | `mobile.py:164` | **100% Matched** |
| `/api/m/sites` | GET | Bearer token | `mobile.py:178` | **100% Matched** |
| `/api/m/config` | GET | Bearer token | `mobile.py:150` | **100% Matched** |
| `/api/m/consent` | POST | `version` | `mobile.py:156` | **100% Matched** |
| `/api/m/event` | POST | `device_id`, `site_id`, `kind`, `lat`, `lon`, `accuracy`, `age_s`, `mock`, `rooted`, `beacons` | `mobile.py:208` | **100% Matched** |
| `/api/m/me/today` | GET | Bearer token | `mobile.py:331` | **100% Matched** |
| `/api/m/me/history`| GET | `?days=14` | `mobile.py:342` | **100% Matched** |
| `/api/m/dispute` | POST | `day`, `note` | `mobile.py:351` | **100% Matched** |

**Conclusion:** The backend routes in `mobile.py` are already fully implemented, tested, and waiting to receive data from the Android client. Once the Android configuration and build files are corrected, integration will be seamless.

---

## 5. Implementation Roadmap to Make the Mobile App Working

```
[Phase 1: Build Setup] ---> [Phase 2: Keycloak & Config] ---> [Phase 3: Manifest & Perms] ---> [Phase 4: Concurrency & UI] ---> [Phase 5: Field Test]
  - Generate Gradle Wrapper   - Setup 'attendance-mobile'    - Add API 34 Foreground Svc    - Singleton SQLite Queue     - Test on Physical Phone
  - Verify Dependencies       - Fix KC_ISSUER & PORTAL_URL   - Add POST_NOTIFICATIONS        - Inside/Outside Status Badge - Verify /review Reconciliation
```

### Action Items for Next Step:
1. **Generate Gradle Wrapper:** Place standard Gradle 8.7 wrapper (`gradlew`, `gradle/wrapper/gradle-wrapper.properties`).
2. **Correct `gradle.properties`:**
   - Set `KC_ISSUER=https://auth.keenable.io/realms/master` (or staging realm).
   - Set `PORTAL_URL=https://pm.keenable.io/attendance` (or local network IP).
   - Set `KC_CLIENT_ID=attendance-mobile`.
3. **Configure Keycloak Public Client:** Create `attendance-mobile` in Keycloak with redirect URI `io.keenable.attendance:/oauth2redirect`.
4. **Update `AndroidManifest.xml`:**
   - Add `FOREGROUND_SERVICE`, `FOREGROUND_SERVICE_LOCATION`, and `POST_NOTIFICATIONS`.
   - Add explicit AppAuth redirect activity intent-filter.
5. **Optimize `Store.kt`:** Convert `Queue` into a thread-safe singleton.
6. **Enhance UI in `MainActivity.kt`:** Add live geofence status indicator ("Inside Office" vs "Outside").

---
