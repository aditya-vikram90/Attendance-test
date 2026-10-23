# Keenable Attendance Portal

This repository contains the Keenable Attendance Tracking Application, its deployment documentation, operational guides, and database migration runbooks.

---

## Directory Structure

```
attendance/
├── attendance-service/       # Python/Flask Application Source Code
│   ├── app.py                # Main application routes & logic
│   ├── templates/            # HTML templates (Jinja2)
│   ├── static/               # CSS, JS, and image assets
│   └── requirements.txt      # Python dependencies
│
├── docs/                     # Documentation & Runbooks
│   ├── migration/            # Central user database migration documentation
│   │   ├── MIGRATION_MASTER_INDEX.md
│   │   ├── MIGRATION_MASTER_TRACKER.md
│   │   ├── STEP_0_SAFETY_BACKUPS.md
│   │   ├── STEP_1_CENTRAL_USER_DB.md
│   │   ├── STEP_2_KEYCLOAK_JAVA_SPI.md
│   │   ├── USER_FEDERATION_AND_POOL_PLAN.md
│   │   ├── KEYCLOAK_USER_PROVISIONING_PLAN.md
│   │   └── KEYCLOAK_USER_CREATION_FLOW.md
│   │
│   └── guides/               # Reference guides and manuals
│       ├── ATTENDANCE_LOCAL_SETUP_GUIDE.md
│       ├── ATTENDANCE_SERVER_SETUP_GUIDE.md
│       ├── ATTENDANCE_ROLE_TESTING_GUIDE.md
│       └── DATABASE_SCHEMA_REFERENCE.md
│
├── backups/                  # Database migration snapshots and backups
│   └── migration_20261012/
│
└── archives/                 # Original project archives
    └── attendance-service.zip
```

---

## Related Projects
* **Keycloak User Storage SPI**: Located at `../keycloak-attendance-spi/`
  * Standalone Java Maven plugin connecting Keycloak 26 directly to the Attendance PostgreSQL database.
