# Step 2: Keycloak Java User Storage SPI Implementation & Deployment

## 1. Executive Summary & Architectural Goals
In Step 2 of our single-database migration, we eliminated all duplicate user storage between Keycloak and the Attendance application. Previously, employee accounts had to be manually synchronized between two disparate databases:
1. Keycloak internal database (`keycloak.user_entity`).
2. Attendance application database (`attendance.team`).

This led to duplicate credentials, out-of-sync profiles, and administrative overhead. 

To solve this permanently, we implemented a custom **Keycloak 26 User Storage SPI (Service Provider Interface)** in Java. With this SPI in place:
* **Keycloak acts strictly as an OpenID Connect federation gateway and identity broker.**
* **PostgreSQL `attendance.app_users` is the single source of truth** for all user identities, emails, passwords, and project assignments.
* When an employee logs in, Keycloak dynamically delegates user lookup, authentication, BCrypt password verification, and credential updates to the Attendance database over JDBC.
* Keycloak stores **zero shadow duplicate users** in its own database.

---

## 2. End-to-End Architectural Flow

```
                                +-----------------------------------+
                                |     Browser / Attendance App      |
                                +-----------------+-----------------+
                                                  |
                                                  | 1. Login (Email + Password)
                                                  v
                                +-----------------------------------+
                                |    Keycloak 26.8.0 Quarkus Core   |
                                +-----------------+-----------------+
                                                  |
                         2. Lookup & Verify       | 3. Delegate to SPI
                                                  v
+---------------------------------------------------------------------------------------------------+
|                     Custom User Storage SPI (keycloak-attendance-user-storage)                   |
|                                                                                                   |
|  [AttendanceUserStorageProviderFactory]                                                           |
|    - Identifies provider as "attendance-user-storage"                                             |
|    - Configured with PostgreSQL JDBC URL, username, and password                                 |
|                                                                                                   |
|  [AttendanceUserStorageProvider]                                                                  |
|    - UserLookupProvider:                                                                          |
|        * getUserByEmail(email)       --> SELECT ... FROM app_users WHERE lower(email) = ?         |
|        * getUserByUsername(username) --> SELECT ... FROM app_users WHERE lower(username) = ?      |
|        * getUserById(id)             --> SELECT ... FROM app_users WHERE id = ?                   |
|    - UserQueryProvider:                                                                           |
|        * searchForUserStream(search) --> Dynamic search across email/name/username in app_users   |
|        * getUsersCount()             --> SELECT count(*) FROM app_users WHERE active = 1          |
|    - CredentialInputValidator:                                                                    |
|        * isValid()                   --> SELECT (crypt(?, password_hash) = password_hash)         |
|    - CredentialInputUpdater:                                                                      |
|        * updateCredential()          --> UPDATE app_users SET password_hash = crypt(?, bf), ...   |
|                                                                                                   |
|  [AttendanceUserAdapter]                                                                          |
|    - Extends AbstractUserAdapterFederatedStorage                                                  |
|    - Maps app_users columns to Keycloak UserModel                                                |
|    - Enforces UPDATE_PASSWORD if must_change_password is true                                     |
|    - Enforces CONFIGURE_TOTP if totp_enabled is false                                             |
+-------------------------------------------------+-------------------------------------------------+
                                                  |
                                                  | 4. Direct SQL over openproject.network
                                                  v
                                +-----------------------------------+
                                |  PostgreSQL Database: attendance  |
                                |         Table: app_users          |
                                +-----------------------------------+
```

---

## 3. How the SPI Links With Keycloak

### 3.1. Java SPI Packaging & Service Loader
Keycloak uses Java standard `ServiceLoader` architecture to discover extensions.
* **Component Factory**: `io.keenable.keycloak.storage.AttendanceUserStorageProviderFactory` implements `org.keycloak.storage.UserStorageProviderFactory`.
* **Registration Descriptor**: Placed in `META-INF/services/org.keycloak.storage.UserStorageProviderFactory`. This file tells Keycloak upon startup which provider factory to instantiate.

### 3.2. Container Volume Mount
Keycloak runs as a containerized systemd unit (`/etc/containers/systemd/keycloak.container`).
We configured Keycloak to scan `/opt/keycloak-providers` on the server by adding the following volume mount:
```ini
[Container]
Image=quay.io/keycloak/keycloak:latest
ContainerName=keycloak
Network=openproject.network
EnvironmentFile=/etc/keycloak/keycloak.env
Volume=/opt/keycloak-providers:/opt/keycloak/providers:Z
PublishPort=127.0.0.1:8085:8080
Exec=start-dev
```
When Keycloak starts up, its Quarkus runtime automatically scans `/opt/keycloak/providers/`, detects our `.jar`, and executes a fast Quarkus augmentation build to bind the provider into Keycloak's core engine.

### 3.3. Keycloak Realm Component Registration
The provider was linked to the `keenable` realm by registering a new component via the Keycloak Admin CLI (`kcadm.sh`):
* **Provider ID**: `attendance-user-storage`
* **Provider Type**: `org.keycloak.storage.UserStorageProvider`
* **Component Name**: `attendance-postgres-storage`
* **Config**:
  * `jdbcUrl`: `jdbc:postgresql://openproject-db:5432/attendance`
  * `dbUser`: `attendance`
  * `dbPassword`: `Att3nd_Pass_2026_Sec!`
  * `priority`: `0`

---

## 4. Keycloak Federated User ID Convention (`f:...`)

When querying users via Keycloak API or UI, every federated user ID follows Keycloak standard format:
```
f:<component-id>:<database-id>
```
* **`f`**: Identifies the user as **Federated** (meaning the user is mastered in an external database rather than Keycloak internal tables).
* **`<component-id>`**: The unique ID of our User Storage component (`0256f839-1f78-44dc-9c29-e0eeace4ae9c`).
* **`<database-id>`**: The primary key `id` from PostgreSQL `app_users` table (e.g. `1` for admin, `8` for dev.sadik, `9` for dev.zaid).

> [!NOTE]
> **User-Facing Behavior**: Employees and end users **never** see this prefix. Employees log in using standard credentials (`email` + `password`). The `f:` prefix is purely Keycloak internal routing mechanism to identify which SPI handles the user.

---

## 5. Detailed Source Code Implementation

The full source code of the SPI is committed in `attendance/keycloak-spi/`:

### 5.1. Maven POM (`pom.xml`)
Compiled using Java 21 against Keycloak 26.8.0 provided dependencies:
```xml
<project xmlns="http://maven.apache.org/POM/4.0.0"
         xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
         xsi:schemaLocation="http://maven.apache.org/POM/4.0.0 http://maven.apache.org/xsd/maven-4.0.0.xsd">
    <modelVersion>4.0.0</modelVersion>
    <groupId>io.keenable.keycloak</groupId>
    <artifactId>keycloak-attendance-user-storage</artifactId>
    <version>1.0.0</version>
    <packaging>jar</packaging>

    <properties>
        <maven.compiler.source>21</maven.compiler.source>
        <maven.compiler.target>21</maven.compiler.target>
        <keycloak.version>26.8.0</keycloak.version>
    </properties>

    <dependencies>
        <dependency>
            <groupId>org.keycloak</groupId>
            <artifactId>keycloak-server-spi</artifactId>
            <version>${keycloak.version}</version>
            <scope>provided</scope>
        </dependency>
        <dependency>
            <groupId>org.keycloak</groupId>
            <artifactId>keycloak-server-spi-private</artifactId>
            <version>${keycloak.version}</version>
            <scope>provided</scope>
        </dependency>
        <dependency>
            <groupId>org.keycloak</groupId>
            <artifactId>keycloak-model-storage</artifactId>
            <version>${keycloak.version}</version>
            <scope>provided</scope>
        </dependency>
        <dependency>
            <groupId>org.postgresql</groupId>
            <artifactId>postgresql</artifactId>
            <version>42.7.2</version>
            <scope>provided</scope>
        </dependency>
    </dependencies>
</project>
```

### 5.2. Data Model: `AttendanceUser.java`
Represents an individual employee record mapped from `app_users`:
* Fields: `id`, `username`, `email`, `firstName`, `lastName`, `mustChangePassword`, `totpEnabled`, `active`.

### 5.3. UserModel Adapter: `AttendanceUserAdapter.java`
Subclasses `AbstractUserAdapterFederatedStorage`:
* Overrides `getUsername()`, `getEmail()`, `getFirstName()`, `getLastName()`, `isEnabled()`.
* **Dynamic Required Actions**:
  * If `user.isMustChangePassword()` is true, appends `UPDATE_PASSWORD` action.
  * If `!user.isTotpEnabled()` is true, appends `CONFIGURE_TOTP` action.
* **Auto-Update on Completion**: When a user completes their password change or OTP setup, `removeRequiredAction()` automatically executes an `UPDATE app_users SET must_change_password = false / totp_enabled = true`.

### 5.4. Core Provider: `AttendanceUserStorageProvider.java`
Implements four Keycloak SPI interfaces:
1. **`UserLookupProvider`**:
   * `getUserByEmail()`: Queries `app_users WHERE lower(email) = lower(?)`.
   * `getUserByUsername()`: Queries `app_users WHERE lower(username) = lower(?) OR lower(email) = lower(?)`.
   * `getUserById()`: Parses external ID integer from `StorageId.externalId(id)` and queries `app_users WHERE id = ?`.
2. **`UserQueryProvider`**:
   * `searchForUserStream()`: Supports searching users in Keycloak Admin UI or REST API using `LIKE %query%` across email, first name, last name, and username.
   * `getUsersCount()`: Returns active employee count (`SELECT count(*) FROM app_users WHERE active = 1`).
3. **`CredentialInputValidator`**:
   * Validates passwords using PostgreSQL native BCrypt:
     ```sql
     SELECT (crypt(?, password_hash) = password_hash) AS match 
     FROM app_users 
     WHERE id = ? AND active = 1;
     ```
4. **`CredentialInputUpdater`**:
   * Updates passwords directly in the database when changed by the user:
     ```sql
     UPDATE app_users 
     SET password_hash = crypt(?, gen_salt('bf', 10)), 
         must_change_password = false, 
         updated_at = CURRENT_TIMESTAMP 
     WHERE id = ?;
     ```

### 5.5. Factory: `AttendanceUserStorageProviderFactory.java`
Implements `UserStorageProviderFactory<AttendanceUserStorageProvider>`:
* Exposes configurable JDBC settings (`jdbcUrl`, `dbUser`, `dbPassword`).
* Provides metadata and help text for Keycloak Administration Console.

---

## 6. Complete Commands Executed for Setup & Deployment

### Step 1: Create Build Directory and Source Files
```bash
mkdir -p /opt/spi-build/src/main/java/io/keenable/keycloak/storage
mkdir -p /opt/spi-build/src/main/resources/META-INF/services
```

### Step 2: Compile & Package SPI with Podman Maven 21
```bash
podman run --rm \
  -v /opt/spi-build:/build:Z \
  -v /root/.m2:/root/.m2:Z \
  -w /build \
  maven:3.9-eclipse-temurin-21-alpine \
  mvn clean package
```
*Build output: `BUILD SUCCESS` in 3.177s -> `/opt/spi-build/target/keycloak-attendance-user-storage-1.0.0.jar` (12 KB).*

### Step 3: Deploy JAR to Keycloak Providers Directory
```bash
mkdir -p /opt/keycloak-providers
cp /opt/spi-build/target/keycloak-attendance-user-storage-1.0.0.jar /opt/keycloak-providers/
chmod -R 755 /opt/keycloak-providers
```

### Step 4: Configure Container Systemd Unit
Updated `/etc/containers/systemd/keycloak.container` with volume mount:
```bash
sed -i "/EnvironmentFile=\/etc\/keycloak\/keycloak.env/a Volume=\/opt\/keycloak-providers:\/opt\/keycloak\/providers:Z" /etc/containers/systemd/keycloak.container
systemctl daemon-reload
systemctl restart keycloak
```

### Step 5: Register SPI Component in Keycloak
```bash
podman exec -i keycloak /opt/keycloak/bin/kcadm.sh create components -r keenable -f - << "EOF"
{
  "name": "attendance-postgres-storage",
  "providerId": "attendance-user-storage",
  "providerType": "org.keycloak.storage.UserStorageProvider",
  "parentId": "7dd17b83-893c-41b4-8849-8e508cd41e67",
  "config": {
    "priority": ["0"],
    "jdbcUrl": ["jdbc:postgresql://openproject-db:5432/attendance"],
    "dbUser": ["attendance"],
    "dbPassword": ["Att3nd_Pass_2026_Sec!"]
  }
}
EOF
```
*Result: Created Keycloak component ID `0256f839-1f78-44dc-9c29-e0eeace4ae9c`.*

### Step 6: Delete Old Shadow Duplicate Users from Keycloak Local Tables
To ensure Keycloak queries `app_users` for 100% of users, we removed duplicate user entities from Keycloak internal database:
```bash
for USER_ID in 887d2a6d-b4e6-4382-aa12-b66342a92560 7c2cbb8f-cedc-4e25-a905-ea5b13f561e0 ec617191-c849-44e9-9b41-40ff9d3488ae 6a8e6667-1cd9-4e33-a7a3-b965dd821625 9279e442-16b2-4b2f-bbe7-f308177fcf53 e4145b4c-8435-47c5-a356-0a51e25e196b 07be5b4a-e6b7-4722-afe2-c382f7a896bb d8e9a4a9-0b80-4187-9ae6-9741833ce23c; do
  podman exec keycloak /opt/keycloak/bin/kcadm.sh delete users/$USER_ID -r keenable
done
```

---

## 7. Verification & Live Test Evidence

### Verification 1: Zero Duplicate Users in Keycloak DB
```bash
podman exec openproject-db psql -U keycloak -d keycloak -c "SELECT id, username, email FROM user_entity WHERE realm_id = '7dd17b83-893c-41b4-8849-8e508cd41e67';"
```
*Result: Only `service-account-attendance` exists in Keycloak database. All employee records have zero duplication.*

### Verification 2: Dynamic User Federation Query
```bash
podman exec keycloak /opt/keycloak/bin/kcadm.sh get users -r keenable
```
*Result: Keycloak returned all 9 users dynamically mapped to their `app_users` IDs:*
* `admin@keenable.io` -> `f:0256f839-1f78-44dc-9c29-e0eeace4ae9c:1`
* `pm.sharma@keenable.io` -> `f:0256f839-1f78-44dc-9c29-e0eeace4ae9c:2`
* `pm.verma@keenable.io` -> `f:0256f839-1f78-44dc-9c29-e0eeace4ae9c:3`
* `dev.arun@keenable.io` -> `f:0256f839-1f78-44dc-9c29-e0eeace4ae9c:4`
* `dev.neha@keenable.io` -> `f:0256f839-1f78-44dc-9c29-e0eeace4ae9c:5`
* `dev.vikram@keenable.io` -> `f:0256f839-1f78-44dc-9c29-e0eeace4ae9c:6`
* `dev.anjali@keenable.io` -> `f:0256f839-1f78-44dc-9c29-e0eeace4ae9c:7`
* `dev.sadik@keenable.io` -> `f:0256f839-1f78-44dc-9c29-e0eeace4ae9c:8`
* `dev.zaid@keenable.io` -> `f:0256f839-1f78-44dc-9c29-e0eeace4ae9c:9`

### Verification 3: Authentication & Security Flow
* **Invalid password**: Returns `{"error":"invalid_grant","error_description":"Invalid user credentials"}`.
* **Valid password**: Successfully accepted by SPI; Keycloak triggers required actions `UPDATE_PASSWORD` and `CONFIGURE_TOTP` based on `app_users.must_change_password` and `app_users.totp_enabled` flags.

---

## 8. Post-Deployment Challenges Encountered & Resolutions

During initial browser authentication testing, three critical operational issues were identified and permanently resolved:

### 8.1. Challenge 1: Admin & PM Login Failures (`invalid_user_credentials`)
* **Symptom**: 
  When attempting to sign in as `admin@keenable.io`, `pm.sharma@keenable.io`, or `pm.verma@keenable.io`, Keycloak rejected the login with *"Invalid username or password"*. Keycloak container logs confirmed:
  `error="invalid_user_credentials", userId="f:0256f839-1f78-44dc-9c29-e0eeace4ae9c:1"`.
* **Root Cause**: 
  During Step 1 database population, initial seeds used generic temporary passwords (`Admin@Keenable2026!`, `Lead@Sharma2026!`, `Lead@Verma2026!`) instead of the team's established corporate credentials.
* **Resolution**: 
  Updated credentials directly in PostgreSQL `attendance.app_users` using native BCrypt `pgcrypto`:
  ```sql
  UPDATE app_users 
  SET password_hash = crypt('KeenableAdmin2026!', gen_salt('bf', 10)),
      must_change_password = false
  WHERE email = 'admin@keenable.io';

  UPDATE app_users 
  SET password_hash = crypt('KeenablePM2026!', gen_salt('bf', 10)),
      must_change_password = false
  WHERE email IN ('pm.sharma@keenable.io', 'pm.verma@keenable.io');
  ```
  *Result*: Authentication succeeded immediately across all administrative accounts.

---

### 8.2. Challenge 2: Mandatory "Update Account Information" Prompt (`execution=VERIFY_PROFILE`)
* **Symptom**: 
  When users logged in, Keycloak intercepted the session with an *"Update Account Information"* form displaying errors: *"Please specify this field"* for Email, First Name, and Last Name.
* **Root Cause**: 
  Keycloak 26 enforces the **Declarative User Profile** validator on every login. The User Profile engine does not call `getFirstName()` or `getLastName()` directly; instead, it queries the generic attribute methods:
  * `getFirstAttribute("firstName")`
  * `getAttributeStream("lastName")`
  * `getAttributes()`
  
  In the initial `AttendanceUserAdapter`, only standard getters were implemented. Keycloak's base `AbstractUserAdapterFederatedStorage` fell back to its internal federated storage table, found no attributes, and erroneously assumed the user lacked basic profile data.
* **Resolution**: 
  Overrode generic attribute methods in `AttendanceUserAdapter.java` to route attribute lookups directly to `AttendanceUser` POJO:
  ```java
  @Override
  public String getFirstAttribute(String name) {
      if (name == null) return null;
      if (UserModel.FIRST_NAME.equalsIgnoreCase(name)) return getFirstName();
      if (UserModel.LAST_NAME.equalsIgnoreCase(name)) return getLastName();
      if (UserModel.EMAIL.equalsIgnoreCase(name)) return getEmail();
      if (UserModel.USERNAME.equalsIgnoreCase(name)) return getUsername();
      if ("phone".equalsIgnoreCase(name) && user.getPhone() != null) return user.getPhone();
      return super.getFirstAttribute(name);
  }

  @Override
  public Stream<String> getAttributeStream(String name) {
      String val = getFirstAttribute(name);
      return val != null ? Stream.of(val) : super.getAttributeStream(name);
  }

  @Override
  public Map<String, List<String>> getAttributes() {
      Map<String, List<String>> attrs = new HashMap<>(super.getAttributes());
      if (getFirstName() != null) attrs.put(UserModel.FIRST_NAME, List.of(getFirstName()));
      if (getLastName() != null) attrs.put(UserModel.LAST_NAME, List.of(getLastName()));
      if (getEmail() != null) attrs.put(UserModel.EMAIL, List.of(getEmail()));
      if (getUsername() != null) attrs.put(UserModel.USERNAME, List.of(getUsername()));
      return Collections.unmodifiableMap(attrs);
  }
  ```
  *Result*: Keycloak recognizes complete user profiles directly upon login. The `VERIFY_PROFILE` prompt no longer appears.

---

### 8.3. Challenge 3: Unintended Storage in Keycloak DB (`fed_user_attribute`)
* **Symptom**: 
  Submitting the "Update Account Information" screen caused Keycloak to insert rows into PostgreSQL `keycloak.fed_user_attribute` (`FIRST_NAME`, `LAST_NAME`, `EMAIL`), violating the zero-shadow-duplicate architecture.
* **Root Cause**: 
  In Keycloak's `AbstractUserAdapterFederatedStorage`, the default `setSingleAttribute()` method writes values directly into Keycloak's internal `fed_user_attribute` table.
* **Resolution**:
  1. Overrode attribute modification methods in `AttendanceUserAdapter.java` to persist changes directly into `attendance.app_users` via SQL, explicitly bypassing `super.setSingleAttribute()`:
     ```java
     @Override
     public void setFirstName(String firstName) {
         user.setFirstName(firstName);
         updateUserColumn("first_name", firstName);
         updateFullName();
     }

     @Override
     public void setLastName(String lastName) {
         user.setLastName(lastName);
         updateUserColumn("last_name", lastName);
         updateFullName();
     }

     @Override
     public void setSingleAttribute(String name, String value) {
         if (UserModel.FIRST_NAME.equalsIgnoreCase(name)) setFirstName(value);
         else if (UserModel.LAST_NAME.equalsIgnoreCase(name)) setLastName(value);
         else if (UserModel.EMAIL.equalsIgnoreCase(name)) setEmail(value);
         else if ("phone".equalsIgnoreCase(name)) updateUserColumn("phone", value);
         // Bypasses super.setSingleAttribute to prevent writes to fed_user_attribute
     }
     ```
  2. Purged existing test rows from Keycloak database:
     ```sql
     DELETE FROM fed_user_attribute;
     ```
  *Result*: Keycloak database `fed_user_attribute` table count is strictly **0**. 100% of employee data remains in `attendance.app_users`.

---

### 8.4. Final Verification Matrix After Fixes

| User Account | Role | Expected Password | Keycloak Lookup | Direct Token Auth | Attributes Source | Shadow Duplicates |
| :--- | :--- | :--- | :---: | :---: | :---: | :---: |
| `admin@keenable.io` | Admin | `KeenableAdmin2026!` | `f:...:1` | **SUCCESS** | `app_users` | **0** |
| `pm.sharma@keenable.io` | PM | `KeenablePM2026!` | `f:...:2` | **SUCCESS** | `app_users` | **0** |
| `pm.verma@keenable.io` | PM | `KeenablePM2026!` | `f:...:3` | **SUCCESS** | `app_users` | **0** |
| `dev.arun@keenable.io` | Engineer | `KeenableDev2026!` | `f:...:4` | **SUCCESS** | `app_users` | **0** |
| `dev.zaid@keenable.io` | Bench QA | `Keenable@2026` | `f:...:9` | **SUCCESS** | `app_users` | **0** |
