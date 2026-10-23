#!/usr/bin/env python3
"""
Seed Demo Users and Attendance Script
-------------------------------------
1. Provisions 34 demo users into Keycloak realm 'keenable' with '@fosteringlinux.com' domain.
2. Synchronizes/creates entries in PostgreSQL 'app_users' table (compatible with Foreign Tables).
3. Assigns 30 engineers across 4 projects (UPSC: 13, NCLT: 8, Shiksha: 5, NSP: 4) into 'team' table,
   leaving 4 engineers unassigned in the Bench Pool. Sets assigned_from='2026-09-01' so trends render full history.
4. Populates realistic historical attendance records from 2026-10-01 to 2026-10-19.
"""

import os
import sys
import uuid
import random
import requests
import psycopg2
import psycopg2.extras
from datetime import datetime, date, timedelta

# Configuration
KC_BASE = os.environ.get("KEYCLOAK_INTERNAL_URL", "http://127.0.0.1:8085/auth").rstrip("/")
KC_REALM = os.environ.get("KEYCLOAK_REALM", "keenable")
KC_ADMIN_USER = os.environ.get("KEYCLOAK_ADMIN", "admin")
KC_ADMIN_PASS = os.environ.get("KEYCLOAK_ADMIN_PASSWORD", "KeycloakAdmin2026!")
DEFAULT_PASSWORD = os.environ.get("DEMO_DEFAULT_PASSWORD", "Keenable@2026")

DB_URL = os.environ.get("DATABASE_URL", "postgresql://attendance:Att3nd_Pass_2026_Sec!@127.0.0.1:5432/attendance")

# Project Mapping (Project Name -> DB Project ID)
PROJECT_MAP = {
    "UPSC": 2,
    "NCLT": 1,
    "Shiksha": 4,
    "NSP": 3
}

# Master Users List (34 Total)
USERS_DATA = [
    # UPSC (13 users)
    {"name": "Mohd Imran", "email": "imran.mohd@fosteringlinux.com", "role": "Senior Software Engineer", "project": "UPSC", "shift": "09:30", "phone": "+91 98112 01001"},
    {"name": "Priya Sharma", "email": "priya.sharma@fosteringlinux.com", "role": "Frontend Developer", "project": "UPSC", "shift": "10:00", "phone": "+91 98112 01002"},
    {"name": "Vikram Singh", "email": "vikram.singh@fosteringlinux.com", "role": "DevOps Engineer", "project": "UPSC", "shift": "09:30", "phone": "+91 98112 01003"},
    {"name": "Neha Verma", "email": "neha.verma@fosteringlinux.com", "role": "UI/UX & Frontend Engineer", "project": "UPSC", "shift": "09:30", "phone": "+91 98112 01004"},
    {"name": "Suresh Patel", "email": "suresh.patel@fosteringlinux.com", "role": "Backend Engineer (Python)", "project": "UPSC", "shift": "09:30", "phone": "+91 98112 01005"},
    {"name": "Amit Roy", "email": "amit.roy@fosteringlinux.com", "role": "Database Administrator", "project": "UPSC", "shift": "09:30", "phone": "+91 98112 01006"},
    {"name": "Anjali Mehta", "email": "anjali.mehta@fosteringlinux.com", "role": "QA Automation Engineer", "project": "UPSC", "shift": "09:30", "phone": "+91 98112 01007"},
    {"name": "Rohit Gupta", "email": "rohit.gupta@fosteringlinux.com", "role": "Full Stack Developer", "project": "UPSC", "shift": "09:30", "phone": "+91 98112 01008"},
    {"name": "Pooja Nair", "email": "pooja.nair@fosteringlinux.com", "role": "Security & Compliance Analyst", "project": "UPSC", "shift": "09:30", "phone": "+91 98112 01009"},
    {"name": "Deepak Joshi", "email": "deepak.joshi@fosteringlinux.com", "role": "Systems Engineer", "project": "UPSC", "shift": "09:30", "phone": "+91 98112 01010"},
    {"name": "Kavita Reddy", "email": "kavita.reddy@fosteringlinux.com", "role": "Software Engineer", "project": "UPSC", "shift": "09:30", "phone": "+91 98112 01011"},
    {"name": "Manoj Tiwari", "email": "manoj.tiwari@fosteringlinux.com", "role": "Backend Engineer", "project": "UPSC", "shift": "09:30", "phone": "+91 98112 01012"},
    {"name": "Swati Deshmukh", "email": "swati.deshmukh@fosteringlinux.com", "role": "QA Engineer", "project": "UPSC", "shift": "10:00", "phone": "+91 98112 01013"},

    # NCLT (8 users)
    {"name": "Rahul Saxena", "email": "rahul.saxena@fosteringlinux.com", "role": "Senior Backend Developer", "project": "NCLT", "shift": "09:30", "phone": "+91 98112 02001"},
    {"name": "Divya Choudhary", "email": "divya.c@fosteringlinux.com", "role": "Frontend Developer", "project": "NCLT", "shift": "09:30", "phone": "+91 98112 02002"},
    {"name": "Manish Malhotra", "email": "manish.m@fosteringlinux.com", "role": "Full Stack Engineer", "project": "NCLT", "shift": "09:30", "phone": "+91 98112 02003"},
    {"name": "Sneha Kulkarni", "email": "sneha.k@fosteringlinux.com", "role": "QA Automation Lead", "project": "NCLT", "shift": "09:30", "phone": "+91 98112 02004"},
    {"name": "Harish Iyer", "email": "harish.iyer@fosteringlinux.com", "role": "Cloud Infrastructure Engineer", "project": "NCLT", "shift": "10:00", "phone": "+91 98112 02005"},
    {"name": "Tanvi Shah", "email": "tanvi.shah@fosteringlinux.com", "role": "UI/UX Developer", "project": "NCLT", "shift": "09:30", "phone": "+91 98112 02006"},
    {"name": "Gaurav Bhatia", "email": "gaurav.b@fosteringlinux.com", "role": "Software Engineer", "project": "NCLT", "shift": "09:30", "phone": "+91 98112 02007"},
    {"name": "Ritu Nambiar", "email": "ritu.n@fosteringlinux.com", "role": "Backend Developer", "project": "NCLT", "shift": "09:30", "phone": "+91 98112 02008"},

    # Shiksha (5 users)
    {"name": "Alok Pandey", "email": "alok.pandey@fosteringlinux.com", "role": "Lead Software Engineer", "project": "Shiksha", "shift": "09:30", "phone": "+91 98112 03001"},
    {"name": "Meera Menon", "email": "meera.menon@fosteringlinux.com", "role": "Frontend Engineer (React)", "project": "Shiksha", "shift": "09:30", "phone": "+91 98112 03002"},
    {"name": "Nitin Yadav", "email": "nitin.yadav@fosteringlinux.com", "role": "Backend API Developer", "project": "Shiksha", "shift": "09:30", "phone": "+91 98112 03003"},
    {"name": "Preeti Sen", "email": "preeti.sen@fosteringlinux.com", "role": "QA Tester", "project": "Shiksha", "shift": "09:30", "phone": "+91 98112 03004"},
    {"name": "Varun Rao", "email": "varun.rao@fosteringlinux.com", "role": "DevOps / CI-CD Specialist", "project": "Shiksha", "shift": "09:30", "phone": "+91 98112 03005"},

    # NSP (4 users)
    {"name": "Siddharth Roy", "email": "siddharth.r@fosteringlinux.com", "role": "Senior Full Stack Engineer", "project": "NSP", "shift": "09:30", "phone": "+91 98112 04001"},
    {"name": "Kiran Hegde", "email": "kiran.hegde@fosteringlinux.com", "role": "Frontend Developer", "project": "NSP", "shift": "09:30", "phone": "+91 98112 04002"},
    {"name": "Sunil Pillai", "email": "sunil.pillai@fosteringlinux.com", "role": "Backend Developer (Python)", "project": "NSP", "shift": "09:30", "phone": "+91 98112 04003"},
    {"name": "Aditi Ghosh", "email": "aditi.ghosh@fosteringlinux.com", "role": "QA Automation Engineer", "project": "NSP", "shift": "09:30", "phone": "+91 98112 04004"},

    # Bench Pool (Unassigned - 4 users)
    {"name": "Rakesh Verma", "email": "rakesh.v@fosteringlinux.com", "role": "Cloud DevOps Engineer", "project": None, "shift": "09:30", "phone": "+91 98112 05001"},
    {"name": "Simran Kaur", "email": "simran.k@fosteringlinux.com", "role": "Frontend Specialist", "project": None, "shift": "09:30", "phone": "+91 98112 05002"},
    {"name": "Abhishek Mishra", "email": "abhishek.m@fosteringlinux.com", "role": "Backend Engineer", "project": None, "shift": "09:30", "phone": "+91 98112 05003"},
    {"name": "Nandini Agarwal", "email": "nandini.a@fosteringlinux.com", "role": "QA & Testing Analyst", "project": None, "shift": "09:30", "phone": "+91 98112 05004"},
]

def get_kc_admin_token():
    url = f"{KC_BASE}/realms/master/protocol/openid-connect/token"
    res = requests.post(url, data={
        "client_id": "admin-cli",
        "username": KC_ADMIN_USER,
        "password": KC_ADMIN_PASS,
        "grant_type": "password"
    }, timeout=10)
    res.raise_for_status()
    return res.json()["access_token"]

def provision_keycloak_users(token):
    print(f"\n[1/4] Provisioning {len(USERS_DATA)} users in Keycloak realm '{KC_REALM}'...")
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    
    # Get existing users in realm
    users_url = f"{KC_BASE}/admin/realms/{KC_REALM}/users"
    res = requests.get(users_url, headers=headers, params={"max": 200}, timeout=10)
    existing_users = {u.get("email", "").lower(): u for u in res.json()} if res.status_code == 200 else {}

    # Get 'member' role representation
    roles_url = f"{KC_BASE}/admin/realms/{KC_REALM}/roles/member"
    role_res = requests.get(roles_url, headers=headers, timeout=10)
    member_role = [role_res.json()] if role_res.status_code == 200 else []

    created_count = 0
    for u in USERS_DATA:
        em = u["email"].lower()
        parts = u["name"].split()
        first_name = parts[0] if parts else ""
        last_name = " ".join(parts[1:]) if len(parts) > 1 else ""

        if em in existing_users:
            kc_uid = existing_users[em]["id"]
            u["kc_id"] = kc_uid
            # ensure password is set
            requests.put(f"{users_url}/{kc_uid}/reset-password", headers=headers, json={
                "type": "password", "value": DEFAULT_PASSWORD, "temporary": False
            }, timeout=10)
            continue

        payload = {
            "username": em,
            "email": em,
            "firstName": first_name,
            "lastName": last_name,
            "enabled": True,
            "emailVerified": True,
            "credentials": [{"type": "password", "value": DEFAULT_PASSWORD, "temporary": False}]
        }
        create_res = requests.post(users_url, headers=headers, json=payload, timeout=10)
        if create_res.status_code == 201:
            loc = create_res.headers.get("Location", "")
            kc_uid = loc.split("/")[-1] if loc else ""
            u["kc_id"] = kc_uid
            created_count += 1

            # Assign 'member' role
            if member_role and kc_uid:
                requests.post(f"{users_url}/{kc_uid}/role-mappings/realm", headers=headers, json=member_role, timeout=10)
            print(f"  ✓ Created in Keycloak: {u['name']} ({em})")
        else:
            print(f"  ✗ Failed creating {em}: {create_res.status_code} {create_res.text}")

    print(f"  --> Keycloak setup completed ({created_count} newly created, {len(USERS_DATA)-created_count} already verified).")

def sync_and_assign_db(conn):
    print("\n[2/4] Syncing 'app_users' and assigning teams in PostgreSQL...")
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    now_iso = datetime.now().strftime("%Y-%m-%dT%H:%M:%S+05:30")
    assigned_team_members = []

    for u in USERS_DATA:
        em = u["email"].lower()
        parts = u["name"].split()
        first_name = parts[0] if parts else ""
        last_name = " ".join(parts[1:]) if len(parts) > 1 else ""
        proj_id = PROJECT_MAP.get(u["project"]) if u["project"] else None
        shift_start = u["shift"] or "09:30"

        # 1. Foreign Table safe upsert for app_users
        cur.execute("SELECT id FROM app_users WHERE lower(email) = %s;", (em,))
        user_row = cur.fetchone()
        if user_row:
            app_user_id = user_row["id"]
            cur.execute("""
                UPDATE app_users SET name=%s, first_name=%s, last_name=%s, phone=%s, role_title=%s,
                       current_project_id=%s, current_shift_start=%s, active=1, updated_at=CURRENT_TIMESTAMP
                WHERE id=%s;
            """, (u["name"], first_name, last_name, u["phone"], u["role"], proj_id, shift_start, app_user_id))
        else:
            cur.execute("""
                INSERT INTO app_users (username, email, name, first_name, last_name, phone, role_title, current_project_id, current_shift_start, active, system_role, updated_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, 1, 'member', CURRENT_TIMESTAMP)
                RETURNING id;
            """, (em, em, u["name"], first_name, last_name, u["phone"], u["role"], proj_id, shift_start))
            app_user_id = cur.fetchone()["id"]

        # 2. Team Table assignment (Explicitly setting assigned_from = '2026-09-01 00:00:00' for full trend rendering)
        if proj_id:
            proj_str = str(proj_id)
            cur.execute("SELECT member_id FROM team WHERE lower(email) = %s AND project_id = %s;", (em, proj_str))
            existing_tm = cur.fetchone()
            if existing_tm:
                member_id = existing_tm["member_id"]
                cur.execute("""
                    UPDATE team SET name=%s, role=%s, phone=%s, shift_start=%s, active=1, user_id=%s, updated_by='admin@keenable.io', updated_at=%s, assigned_from='2026-09-01 00:00:00'
                    WHERE project_id=%s AND member_id=%s;
                """, (u["name"], u["role"], u["phone"], shift_start, app_user_id, now_iso, proj_str, member_id))
            else:
                member_id = f"m:{uuid.uuid4().hex[:12]}"
                cur.execute("""
                    INSERT INTO team (project_id, member_id, name, role, phone, email, shift_start, active, updated_by, updated_at, user_id, assigned_from)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, 1, 'admin@keenable.io', %s, %s, '2026-09-01 00:00:00');
                """, (proj_str, member_id, u["name"], u["role"], u["phone"], em, shift_start, now_iso, app_user_id))

            assigned_team_members.append({
                "member_id": member_id,
                "name": u["name"],
                "email": em,
                "project_name": u["project"],
                "project_id": proj_str,
                "shift_start": shift_start,
                "role": u["role"]
            })
        else:
            # Unassigned bench member: ensure no active team mapping
            cur.execute("UPDATE team SET active=0 WHERE lower(email)=%s;", (em,))

    conn.commit()
    print(f"  --> Assigned {len(assigned_team_members)} engineers to projects. 4 engineers left in Bench Pool.")
    return assigned_team_members

def seed_historical_attendance(conn, assigned_members):
    print("\n[3/4] Generating realistic daily attendance records (2026-10-01 to 2026-10-19)...")
    cur = conn.cursor()

    # Generate dates from 2026-10-01 to 2026-10-19
    start_date = date(2026, 10, 1)
    end_date = date(2026, 10, 19)
    cur_date = start_date

    work_days = []
    while cur_date <= end_date:
        # 5 = Saturday, 6 = Sunday
        if cur_date.weekday() not in (5, 6):
            work_days.append(cur_date.strftime("%Y-%m-%d"))
        cur_date += timedelta(days=1)

    print(f"  Target working days: {len(work_days)} days ({work_days[0]} to {work_days[-1]})")

    # Group members by project for task cover colleague selection
    by_project = {}
    for m in assigned_members:
        by_project.setdefault(m["project_name"], []).append(m)

    random.seed(42)  # Deterministic seed for reproducible realistic data

    total_records = 0

    for day_str in work_days:
        day_obj = datetime.strptime(day_str, "%Y-%m-%d").date()
        is_monday = day_obj.weekday() == 0

        for m in assigned_members:
            mem_id = m["member_id"]
            mem_name = m["name"]
            shift_start = m["shift_start"]
            p_name = m["project_name"]
            peers = [p["name"] for p in by_project[p_name] if p["name"] != mem_name]
            cover_person = random.choice(peers) if peers else ""

            # Deterministic scenario variation per user / date
            user_hash = hash(f"{m['email']}_{day_str}") % 100

            in_time = ""
            out_time = ""
            leave_type = ""
            planned = ""
            handled_by = ""
            remarks = ""

            # 1. Planned multi-day Leave Scenario
            if m["name"] == "Priya Sharma" and day_str in ("2026-10-06", "2026-10-07", "2026-10-08"):
                leave_type = "Casual Leave"
                planned = "Planned"
                handled_by = "Vikram Singh"
                remarks = "Pre-approved Casual Leave (Personal family event)"
            elif m["name"] == "Rahul Saxena" and day_str in ("2026-10-13", "2026-10-14"):
                leave_type = "Sick Leave"
                planned = "Planned"
                handled_by = "Divya Choudhary"
                remarks = "Pre-approved Sick Leave · Recovering from fever"
            elif m["name"] == "Manoj Tiwari" and day_str in ("2026-10-15", "2026-10-16"):
                leave_type = "Casual Leave"
                planned = "Planned"
                handled_by = "Mohd Imran"
                remarks = "Pre-approved Casual Leave"
            elif user_hash < 4:  # ~4% random occasional leave
                leave_type = random.choice(["Casual Leave", "Sick Leave", "Earned Leave"])
                planned = "Planned"
                handled_by = cover_person
                remarks = f"Advance {leave_type} (Approved on email)"

            # 2. Half Day Scenario (~2%)
            elif user_hash in (4, 5):
                in_time = "09:30"
                out_time = "14:00"
                leave_type = "Half Day"
                handled_by = cover_person
                remarks = "First-half shift · Personal medical appointment"

            # 3. Work From Home Scenario (~4%)
            elif user_hash in (6, 7, 8, 9):
                in_time = shift_start
                out_time = "18:30"
                remarks = "Approved remote duty (Sprint feature build)"

            # 4. Head Office Visit Remark Scenario (~3%)
            elif user_hash in (10, 11, 12):
                in_time = "09:22"
                out_time = "18:40"
                remarks = "Visited Head Office for internal sprint review / IT setup"

            # 5. Late Arrival Scenario (Higher on Mondays ~25%, other days ~10%)
            elif (is_monday and user_hash < 32) or (not is_monday and user_hash < 18):
                late_mins = random.randint(18, 48)
                base_hour, base_min = map(int, shift_start.split(":"))
                tot_min = base_hour * 60 + base_min + late_mins
                in_h = tot_min // 60
                in_m = tot_min % 60
                in_time = f"{in_h:02d}:{in_m:02d}"
                out_time = random.choice(["18:35", "18:45", "19:00", "18:30"])
                remarks = random.choice([
                    "Metro transit delay",
                    "Traffic congestion near highway",
                    "Public transport delay",
                    ""
                ])

            # 6. Regular Punctual Day (~75%)
            else:
                base_hour, base_min = map(int, shift_start.split(":"))
                early_mins = random.randint(-15, 2)
                tot_min = base_hour * 60 + base_min + early_mins
                in_h = tot_min // 60
                in_m = tot_min % 60
                in_time = f"{in_h:02d}:{in_m:02d}"
                out_time = random.choice(["18:30", "18:35", "18:40", "18:45"])
                remarks = "" if random.random() > 0.15 else "Client site duty"

            # Upsert into attendance table
            now_stamp = f"{day_str}T20:00:00+05:30"
            cur.execute("""
                INSERT INTO attendance (day, user_id, user_name, in_time, out_time, leave_type, planned, handled_by, remarks, updated_by, updated_at, shift_start)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, 'admin@keenable.io', %s, %s)
                ON CONFLICT (day, user_id) DO UPDATE SET
                    user_name = EXCLUDED.user_name,
                    in_time = EXCLUDED.in_time,
                    out_time = EXCLUDED.out_time,
                    leave_type = EXCLUDED.leave_type,
                    planned = EXCLUDED.planned,
                    handled_by = EXCLUDED.handled_by,
                    remarks = EXCLUDED.remarks,
                    updated_by = EXCLUDED.updated_by,
                    updated_at = EXCLUDED.updated_at,
                    shift_start = EXCLUDED.shift_start;
            """, (day_str, mem_id, mem_name, in_time, out_time, leave_type, planned, handled_by, remarks, now_stamp, shift_start))
            total_records += 1

    conn.commit()
    print(f"  --> Inserted/Updated {total_records} transactional attendance records across {len(work_days)} working days.")

def main():
    print("=" * 70)
    print("ATTENDANCE PORTAL: DEMO USERS PROVISIONING & DATA SEEDING")
    print("=" * 70)

    # 1. Keycloak Admin
    try:
        token = get_kc_admin_token()
        provision_keycloak_users(token)
    except Exception as e:
        print(f"ERROR connecting to Keycloak: {e}")
        sys.exit(1)

    # 2. Database Connection
    try:
        conn = psycopg2.connect(DB_URL)
    except Exception as e:
        print(f"ERROR connecting to Database ({DB_URL}): {e}")
        sys.exit(1)

    # 3. DB Sync & Project Assignment
    assigned_members = sync_and_assign_db(conn)

    # 4. Historical Attendance Seeding
    seed_historical_attendance(conn, assigned_members)

    conn.close()
    print("\n[4/4] COMPLETE: All 34 demo users provisioned & attendance generated successfully!")
    print("=" * 70)

if __name__ == "__main__":
    main()
