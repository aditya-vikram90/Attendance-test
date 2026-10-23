# Demo Users Directory & Bulk Setup Execution Plan

This document contains the complete roster of **34 Demo Engineers** (domain: `@fosteringlinux.com`), their assigned project breakdown across **UPSC**, **NCLT**, **Shiksha**, **NSP**, and the **Bench Pool**, followed by the technical execution steps for bulk Keycloak provisioning and historical attendance generation (1st Oct to 19th Oct 2026).

---

## 📋 1. Project Allocation Summary

| Category / Project | Count | Shift Timing | Purpose / Notes |
| :--- | :---: | :---: | :--- |
| **1. UPSC** | **13** | 09:30 / 10:00 | Core project team (Backend, Frontend, Full Stack, QA, DevOps) |
| **2. NCLT** | **8** | 09:30 / 10:00 | Legal tech digitisation workflow team |
| **3. Shiksha** | **5** | 09:30 | EdTech portal engineering team |
| **4. NSP** | **4** | 09:30 | National scholarship portal team |
| **5. Unassigned (Bench Pool)** | **4** | — | **Deliberately kept unassigned** for live 1-click demo assignment |
| **Total Users** | **34** | — | **All accounts created in Keycloak with `@fosteringlinux.com`** |

---

## 👥 2. Complete User Table

| # | Full Name | Email Address | Role / Designation | Assigned Project | Shift Start | Contact Number |
| :-: | :--- | :--- | :--- | :--- | :-: | :--- |
| **1** | **Mohd Imran** | `imran.mohd@fosteringlinux.com` | Senior Software Engineer | **UPSC** | 09:30 | +91 98112 01001 |
| **2** | **Priya Sharma** | `priya.sharma@fosteringlinux.com` | Frontend Developer | **UPSC** | 10:00 | +91 98112 01002 |
| **3** | **Vikram Singh** | `vikram.singh@fosteringlinux.com` | DevOps Engineer | **UPSC** | 09:30 | +91 98112 01003 |
| **4** | **Neha Verma** | `neha.verma@fosteringlinux.com` | UI/UX & Frontend Engineer | **UPSC** | 09:30 | +91 98112 01004 |
| **5** | **Suresh Patel** | `suresh.patel@fosteringlinux.com` | Backend Engineer (Python) | **UPSC** | 09:30 | +91 98112 01005 |
| **6** | **Amit Roy** | `amit.roy@fosteringlinux.com` | Database Administrator | **UPSC** | 09:30 | +91 98112 01006 |
| **7** | **Anjali Mehta** | `anjali.mehta@fosteringlinux.com` | QA Automation Engineer | **UPSC** | 09:30 | +91 98112 01007 |
| **8** | **Rohit Gupta** | `rohit.gupta@fosteringlinux.com` | Full Stack Developer | **UPSC** | 09:30 | +91 98112 01008 |
| **9** | **Pooja Nair** | `pooja.nair@fosteringlinux.com` | Security & Compliance Analyst | **UPSC** | 09:30 | +91 98112 01009 |
| **10** | **Deepak Joshi** | `deepak.joshi@fosteringlinux.com` | Systems Engineer | **UPSC** | 09:30 | +91 98112 01010 |
| **11** | **Kavita Reddy** | `kavita.reddy@fosteringlinux.com` | Software Engineer | **UPSC** | 09:30 | +91 98112 01011 |
| **12** | **Manoj Tiwari** | `manoj.tiwari@fosteringlinux.com` | Backend Engineer | **UPSC** | 09:30 | +91 98112 01012 |
| **13** | **Swati Deshmukh** | `swati.deshmukh@fosteringlinux.com`| QA Engineer | **UPSC** | 10:00 | +91 98112 01013 |
| **14** | **Rahul Saxena** | `rahul.saxena@fosteringlinux.com` | Senior Backend Developer | **NCLT** | 09:30 | +91 98112 02001 |
| **15** | **Divya Choudhary**| `divya.c@fosteringlinux.com` | Frontend Developer | **NCLT** | 09:30 | +91 98112 02002 |
| **16** | **Manish Malhotra**| `manish.m@fosteringlinux.com` | Full Stack Engineer | **NCLT** | 09:30 | +91 98112 02003 |
| **17** | **Sneha Kulkarni** | `sneha.k@fosteringlinux.com` | QA Automation Lead | **NCLT** | 09:30 | +91 98112 02004 |
| **18** | **Harish Iyer** | `harish.iyer@fosteringlinux.com` | Cloud Infrastructure Engineer | **NCLT** | 10:00 | +91 98112 02005 |
| **19** | **Tanvi Shah** | `tanvi.shah@fosteringlinux.com` | UI/UX Developer | **NCLT** | 09:30 | +91 98112 02006 |
| **20** | **Gaurav Bhatia** | `gaurav.b@fosteringlinux.com` | Software Engineer | **NCLT** | 09:30 | +91 98112 02007 |
| **21** | **Ritu Nambiar** | `ritu.n@fosteringlinux.com` | Backend Developer | **NCLT** | 09:30 | +91 98112 02008 |
| **22** | **Alok Pandey** | `alok.pandey@fosteringlinux.com` | Lead Software Engineer | **Shiksha** | 09:30 | +91 98112 03001 |
| **23** | **Meera Menon** | `meera.menon@fosteringlinux.com` | Frontend Engineer (React) | **Shiksha** | 09:30 | +91 98112 03002 |
| **24** | **Nitin Yadav** | `nitin.yadav@fosteringlinux.com` | Backend API Developer | **Shiksha** | 09:30 | +91 98112 03003 |
| **25** | **Preeti Sen** | `preeti.sen@fosteringlinux.com` | QA Tester | **Shiksha** | 09:30 | +91 98112 03004 |
| **26** | **Varun Rao** | `varun.rao@fosteringlinux.com` | DevOps / CI-CD Specialist | **Shiksha** | 09:30 | +91 98112 03005 |
| **27** | **Siddharth Roy** | `siddharth.r@fosteringlinux.com` | Senior Full Stack Engineer | **NSP** | 09:30 | +91 98112 04001 |
| **28** | **Kiran Hegde** | `kiran.hegde@fosteringlinux.com` | Frontend Developer | **NSP** | 09:30 | +91 98112 04002 |
| **29** | **Sunil Pillai** | `sunil.pillai@fosteringlinux.com` | Backend Developer (Python) | **NSP** | 09:30 | +91 98112 04003 |
| **30** | **Aditi Ghosh** | `aditi.ghosh@fosteringlinux.com` | QA Automation Engineer | **NSP** | 09:30 | +91 98112 04004 |
| **31** | **Rakesh Verma** | `rakesh.v@fosteringlinux.com` | Cloud DevOps Engineer | **Bench Pool (Unassigned)** | — | +91 98112 05001 |
| **32** | **Simran Kaur** | `simran.k@fosteringlinux.com` | Frontend Specialist | **Bench Pool (Unassigned)** | — | +91 98112 05002 |
| **33** | **Abhishek Mishra**| `abhishek.m@fosteringlinux.com` | Backend Engineer | **Bench Pool (Unassigned)** | — | +91 98112 05003 |
| **34** | **Nandini Agarwal**| `nandini.a@fosteringlinux.com` | QA & Testing Analyst | **Bench Pool (Unassigned)** | — | +91 98112 05004 |

---

## ⚙️ 3. Execution Plan & Technical Operations

The setup will be performed in 3 automated steps using a Python/Shell script on the server:

```
[ Step 1: Keycloak Bulk Provisioning ]
       │  (Creates 34 users in Keycloak Realm via Admin API)
       ▼
[ Step 2: Attendance User Sync & Team Assignment ]
       │  (Syncs users into `app_users` & maps to project teams in `team` table)
       ▼
[ Step 3: Realistic Historical Attendance Seeding ]
          (Generates day-by-day attendance from 1st Oct to 19th Oct 2026)
```

### Step 1: Bulk User Creation in Keycloak
1. Authenticate with Keycloak Admin REST API (`/auth/admin/realms/{realm}/users`).
2. Provision each user with:
   - `username`: Email address (e.g. `imran.mohd@fosteringlinux.com`).
   - `email`: `imran.mohd@fosteringlinux.com` (`emailVerified: true`).
   - `firstName`, `lastName`, `enabled: true`.
   - Default temporary password: `Keenable@2026` (or standard demo password).
   - Realm role: `member` (standard engineer).

### Step 2: Synchronize App Directory & Assign Projects
1. Run directory sync so Keycloak user IDs map into the portal `app_users` table.
2. Insert project assignments into the `team` table:
   - **UPSC** (13 users assigned with designated shift start times).
   - **NCLT** (8 users assigned).
   - **Shiksha** (5 users assigned).
   - **NSP** (4 users assigned).
   - **Bench Pool** (4 users left unassigned with `current_project_id = NULL` for live demo).

### Step 3: Realistic Historical Attendance Generation (1st Oct to 19th Oct 2026)
For each assigned engineer, iterate through every day from **2026-10-01 to 2026-10-19**:
1. **Weekends (Saturdays & Sundays)**:
   - Automatically skipped (Oct 3, 4, 10, 11, 17, 18).
2. **Working Days (13 Working Days)**:
   - **Present (`P`) ~85%**:
     - Regular Check-in: `09:15` to `09:32` (Punctual).
     - Regular Check-out: `18:30` to `18:45`.
   - **Late Arrivals (`P` + Late Mins) ~8%**:
     - Check-in: `09:50` to `10:15` (e.g. `+20m` to `+45m` late).
     - Contextual remarks: *"Transit delay / Metro signal delay"*.
   - **Pre-Approved Leaves (`L` / Casual / Sick) ~5%**:
     - Multi-day approved leave spans (e.g., Priya Sharma 3 days on leave) with `handled_by` cover colleagues.
   - **Head Office Duty Remarks ~2%**:
     - Marked Present (`P`) with notes: *"Visited Head Office for internal sprint review / IT setup"*.
   - **Work From Home (`W`) & Half Days (`HD`)**:
     - A small realistic distribution.

---

## 🎯 Verification & Deliverables
After executing the script:
1. **`/team` Page**: Shows 30 active assigned engineers across 4 projects + 4 unassigned bench engineers ready for live assignment.
2. **`/` Daily Roster**: Displays complete daily shift grid for UPSC, NCLT, Shiksha, and NSP.
3. **`/summary` Page**: Displays complete daily attendance stats and working handover tables.
4. **`/trends` Page**: Renders rich graphs, weekday punctuality distributions, and regularity scores for the full 19-day period.
5. **`/me` Page**: Allows any engineer to log in and inspect their personal monthly punch calendar.
