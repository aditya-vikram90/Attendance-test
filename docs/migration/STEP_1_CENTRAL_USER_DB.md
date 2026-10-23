# Step 1: Central User Database Schema (`app_users`)

* **Phase**: Step 1 of 4
* **Status**: **COMPLETED & VERIFIED** ✅
* **Database**: `attendance` on PostgreSQL (`openproject-db:5432`)
* **Execution Timestamp**: `2026-10-12 19:54:00 IST`

---

## 1. Purpose of Step 1

Establish a **single source of truth for all corporate users** inside the PostgreSQL `attendance` database (`app_users` table), eliminating data duplication across Attendance and Keycloak. Link existing historical project team assignments in the `team` table directly to this unified user directory.

---

## 2. Exact DDL and Migration Commands Executed

### Step 2.1: Enable Cryptographic Hashing Extension
```bash
podman exec openproject-db psql -U openproject -d attendance -c "CREATE EXTENSION IF NOT EXISTS pgcrypto;"
```

### Step 2.2: Create Central `app_users` Table & Indexes
```sql
CREATE TABLE IF NOT EXISTS app_users (
    id SERIAL PRIMARY KEY,
    username VARCHAR(120) UNIQUE NOT NULL,
    email VARCHAR(120) UNIQUE NOT NULL,
    name VARCHAR(100) NOT NULL,
    first_name VARCHAR(100) NOT NULL,
    last_name VARCHAR(100) DEFAULT '',
    phone VARCHAR(20) UNIQUE,
    role_title VARCHAR(60) DEFAULT 'Developer',
    password_hash VARCHAR(255) NOT NULL,
    must_change_password BOOLEAN DEFAULT FALSE,
    totp_enabled BOOLEAN DEFAULT FALSE,
    totp_secret VARCHAR(64) DEFAULT NULL,
    current_project_id INT REFERENCES project(id) ON DELETE SET NULL DEFAULT NULL,
    current_shift_start VARCHAR(10) DEFAULT '09:30',
    active INT DEFAULT 1,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_app_users_email ON app_users(lower(email));
CREATE INDEX IF NOT EXISTS idx_app_users_curr_proj ON app_users(current_project_id);
```

### Step 2.3: Populate Initial 9 Employee Accounts with BCrypt Passwords
```sql
INSERT INTO app_users (username, email, name, first_name, last_name, phone, role_title, password_hash, must_change_password, totp_enabled, current_project_id, active)
VALUES
('admin@keenable.io', 'admin@keenable.io', 'System Admin', 'System', 'Admin', '9999999990', 'Admin', crypt('Admin@Keenable2026!', gen_salt('bf', 10)), false, true, NULL, 1),
('pm.sharma@keenable.io', 'pm.sharma@keenable.io', 'Rahul Sharma', 'Rahul', 'Sharma', '9999999991', 'Project Manager', crypt('Lead@Sharma2026!', gen_salt('bf', 10)), false, true, 1, 1),
('pm.verma@keenable.io', 'pm.verma@keenable.io', 'Priya Verma', 'Priya', 'Verma', '9999999992', 'Project Manager', crypt('Lead@Verma2026!', gen_salt('bf', 10)), false, true, 2, 1),
('dev.arun@keenable.io', 'dev.arun@keenable.io', 'Arun Kumar', 'Arun', 'Kumar', '9999999993', 'Frontend Engineer', crypt('KeenableDev2026!', gen_salt('bf', 10)), false, true, 2, 1),
('dev.neha@keenable.io', 'dev.neha@keenable.io', 'Neha Gupta', 'Neha', 'Gupta', '9999999994', 'Backend Engineer', crypt('KeenableDev2026!', gen_salt('bf', 10)), false, false, 1, 1),
('dev.vikram@keenable.io', 'dev.vikram@keenable.io', 'Vikram Singh', 'Vikram', 'Singh', '9999999995', 'DevOps Engineer', crypt('KeenableDev2026!', gen_salt('bf', 10)), false, false, 1, 1),
('dev.anjali@keenable.io', 'dev.anjali@keenable.io', 'Anjali Patel', 'Anjali', 'Patel', '9999999996', 'Mobile Developer', crypt('KeenableDev2026!', gen_salt('bf', 10)), false, false, 3, 1),
('dev.sadik@keenable.io', 'dev.sadik@keenable.io', 'Mohd Sadik', 'Mohd', 'Sadik', '9090909090', 'Developer', crypt('KeenableDev2026!', gen_salt('bf', 10)), false, false, 1, 1),
('dev.zaid@keenable.io', 'dev.zaid@keenable.io', 'Zaid Khan', 'Zaid', 'Khan', '9876543210', 'QA Engineer', crypt('Keenable@2026', gen_salt('bf', 10)), true, false, NULL, 1)
ON CONFLICT (email) DO UPDATE SET
    first_name = EXCLUDED.first_name,
    last_name = EXCLUDED.last_name,
    current_project_id = EXCLUDED.current_project_id,
    updated_at = CURRENT_TIMESTAMP;
```

### Step 2.4: Link `team` Table to `app_users`
```sql
ALTER TABLE team ADD COLUMN IF NOT EXISTS user_id INT REFERENCES app_users(id) ON DELETE SET NULL;

UPDATE team t
SET user_id = u.id
FROM app_users u
WHERE lower(t.email) = lower(u.email)
  AND t.user_id IS NULL;
```

---

## 3. Live Verification Results

### 3.1. User Directory in `app_users`:
```
 id |         email          | first_name | last_name |    role_title     | current_project_id | active | must_change_password | totp_enabled 
----+------------------------+------------+-----------+-------------------+--------------------+--------+----------------------+--------------
  1 | admin@keenable.io      | System     | Admin     | Admin             |                    |      1 | f                    | t
  2 | pm.sharma@keenable.io  | Rahul      | Sharma    | Project Manager   |                  1 |      1 | f                    | t
  3 | pm.verma@keenable.io   | Priya      | Verma     | Project Manager   |                  2 |      1 | f                    | t
  4 | dev.arun@keenable.io   | Arun       | Kumar     | Frontend Engineer |                  2 |      1 | f                    | t
  5 | dev.neha@keenable.io   | Neha       | Gupta     | Backend Engineer  |                  1 |      1 | f                    | f
  6 | dev.vikram@keenable.io | Vikram     | Singh     | DevOps Engineer   |                  1 |      1 | f                    | f
  7 | dev.anjali@keenable.io | Anjali     | Patel     | Mobile Developer  |                  3 |      1 | f                    | f
  8 | dev.sadik@keenable.io  | Mohd       | Sadik     | Developer         |                  1 |      1 | f                    | f
  9 | dev.zaid@keenable.io   | Zaid       | Khan      | QA Engineer       |                    |      1 | t                    | f
```

### 3.2. Team Mapping Linkage (`team.user_id` -> `app_users.id`):
```
 project_id |   member_id    | user_id |     name     |         email          |       role        | active 
------------+----------------+---------+--------------+------------------------+-------------------+--------
 1          | 101            |       5 | Neha Gupta   | dev.neha@keenable.io   | Backend Engineer  |      1
 1          | 102            |       6 | Vikram Singh | dev.vikram@keenable.io | DevOps Engineer   |      1
 1          | m:c6092597758d |       8 | Mohd Sadik   | dev.sadik@keenable.io  | Developer         |      1
 2          | 201            |       4 | Arun Kumar   | dev.arun@keenable.io   | Frontend Engineer |      1
 2          | 202            |       5 | Neha Gupta   | dev.neha@keenable.io   | Backend Engineer  |      1
 2          | m:b4f03c52c110 |       9 | Zaid Khan    | dev.zaid@keenable.io   | QA Engineer       |      0
 3          | 301            |       7 | Anjali Patel | dev.anjali@keenable.io | Mobile Developer  |      1
 3          | 302            |       4 | Arun Kumar   | dev.arun@keenable.io   | Frontend Engineer |      1
```

### 3.3. Password Verification Test:
```sql
SELECT email, (crypt('Admin@Keenable2026!', password_hash) = password_hash) AS admin_match FROM app_users WHERE email='admin@keenable.io';
-- Result: t (Match OK)

SELECT email, (crypt('KeenableDev2026!', password_hash) = password_hash) AS dev_match FROM app_users WHERE email='dev.sadik@keenable.io';
-- Result: t (Match OK)

SELECT email, (crypt('WrongPassword', password_hash) = password_hash) AS bad_match FROM app_users WHERE email='dev.sadik@keenable.io';
-- Result: f (Invalid password correctly rejected)
```

---

## 4. Key Takeaways & Current State
* The central repository `app_users` is active and populated.
* BCrypt hashing is verified and fully functional.
* `current_project_id` tracks active assignments, with `NULL` designating available bench candidates (`dev.zaid@keenable.io`).
* Live attendance operations remain uninterrupted.
