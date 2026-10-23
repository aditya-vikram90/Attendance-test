# Attendance Application - Role-Based Testing Guide

The realistic standalone testing environment for the **Attendance Service** is now **fully provisioned and ready for testing** at [https://pm.keenable.io/attendance/](https://pm.keenable.io/attendance/).

---

## 🔑 Test Credentials Matrix (`@keenable.io`)

All user accounts have been created in Keycloak with verified emails and active passwords:

| Role Category | Full Name | Email / Username | Password | Keycloak Role | Access Scope |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **System Admin** | System Administrator | `admin@keenable.io` | `KeenableAdmin2026!` | `attendance-admin` | Full control across all projects & settings |
| **Project Manager** | Rahul Sharma | `pm.sharma@keenable.io` | `KeenablePM2026!` | `attendance-manager` | Lead for *Cloud Migration & Infra* |
| **Project Manager** | Priya Verma | `pm.verma@keenable.io` | `KeenablePM2026!` | `attendance-manager` | Lead for *Client Portal* & *Mobile App* |
| **Frontend Engineer** | Arun Kumar | `dev.arun@keenable.io` | `KeenableDev2026!` | *(Standard User)* | Member in *Client Portal* & *Mobile App* |
| **Backend Engineer** | Neha Gupta | `dev.neha@keenable.io` | `KeenableDev2026!` | *(Standard User)* | Member in *Cloud Migration* & *Client Portal* |
| **DevOps Engineer** | Vikram Singh | `dev.vikram@keenable.io` | `KeenableDev2026!` | *(Standard User)* | Member in *Cloud Migration & Infra* |
| **Mobile Developer** | Anjali Patel | `dev.anjali@keenable.io` | `KeenableDev2026!` | *(Standard User)* | Member in *Mobile Banking App* |

---

## 📁 Provisioned Projects & Team Mapping

```
1. ☁️ Cloud Migration & Infra
   ├── Lead: Rahul Sharma (pm.sharma@keenable.io)
   └── Members:
       ├── Neha Gupta (dev.neha@keenable.io)
       └── Vikram Singh (dev.vikram@keenable.io)

2. 💻 Client Web Portal
   ├── Lead: Priya Verma (pm.verma@keenable.io)
   └── Members:
       ├── Arun Kumar (dev.arun@keenable.io)
       └── Neha Gupta (dev.neha@keenable.io)

3. 📱 Mobile Banking App
   ├── Lead: Priya Verma (pm.verma@keenable.io)
   └── Members:
       ├── Anjali Patel (dev.anjali@keenable.io)
       └── Arun Kumar (dev.arun@keenable.io)
```

---

## 📊 Seeded Attendance Scenarios (Today)

* **Arun Kumar**: `In: 09:15` | `Out: 18:30` → **On-time check-in** (completed 9h 15m shift).
* **Vikram Singh**: `In: 10:10` | `Out: 19:15` → **Late Arrival** (Shift start 09:30 + 15m grace period = 09:45).
* **Neha Gupta**: `Casual Leave (CL)` | `Planned` | **Handled by Vikram Singh**.
* **Anjali Patel**: `Sick Leave (SL)` | `Unplanned` | Remarks: "Viral fever".

---

## 🧪 Step-by-Step Role Testing Guide

> 💡 **Tip**: Use an **Incognito / Private Window** or click **"Sign out"** when switching between different accounts.

### Test 1: Administrator Experience
1. Open **[https://pm.keenable.io/attendance/](https://pm.keenable.io/attendance/)**.
2. Sign in as:
   * **Username**: `admin@keenable.io`
   * **Password**: `KeenableAdmin2026!`
3. **What to verify**:
   * **Dashboard**: You can see all 3 projects (`Cloud Migration`, `Client Web Portal`, `Mobile Banking App`).
   * **Projects Tab (`/projects`)**: You can create new projects, edit existing projects, and change leads.
   * **Summary Tab (`/summary`)**: You can view global attendance percentages, late arrival stats, and click **"Export to Excel"** to download the complete monthly report.

---

### Test 2: Project Manager / Lead Experience
1. Sign out, or open a fresh Incognito tab at **[https://pm.keenable.io/attendance/](https://pm.keenable.io/attendance/)**.
2. Sign in as:
   * **Username**: `pm.verma@keenable.io`
   * **Password**: `KeenablePM2026!`
3. **What to verify**:
   * **Projects Shown**: Priya Verma leads `Client Web Portal` and `Mobile Banking App`.
   * **Attendance Entry (`/entry`)**: You can record, modify, or mark leaves for Arun Kumar, Neha Gupta, and Anjali Patel.
   * **Trends**: View attendance graphs and punctuality stats specifically for her teams.

---

### Test 3: Engineer Experience
1. Sign out, or open a fresh Incognito tab at **[https://pm.keenable.io/attendance/](https://pm.keenable.io/attendance/)**.
2. Sign in as:
   * **Username**: `dev.arun@keenable.io`
   * **Password**: `KeenableDev2026!`
3. **What to verify**:
   * **Auto-Redirect to `/me`**: Regular engineers are automatically routed to their personal dashboard.
   * **Personal Log**: Arun can see his `09:15 - 18:30` check-in for today, total hours worked, and monthly breakdown.
   * **Security Protection**: If Arun attempts to visit `/projects` or `/summary`, access is blocked with a 403 Forbidden message.
