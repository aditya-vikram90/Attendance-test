"""
App Configuration Engine: Dynamic runtime settings & feature flags.
Allows Super Admins to configure web features, mobile flags, and email notifications
without redeploying code or restarting services.
"""
import json
import logging
from datetime import datetime

logger = logging.getLogger("app_config")

# In-memory cached dictionary for lightning-fast reads
_CACHE = {}

# Default configuration catalogue (seeded into app_config table on startup)
DEFAULT_CONFIGS = [
    # --- EMAIL NOTIFICATIONS (Configurable per event) ---
    {
        "key": "email.project_assignment_notify_emp",
        "category": "email",
        "data_type": "boolean",
        "value": "true",
        "label": "Project Assignment (To Employee)",
        "description": "Emails the employee when they are assigned or transferred to a project with site and shift details."
    },
    {
        "key": "email.project_assignment_notify_pm",
        "category": "email",
        "data_type": "boolean",
        "value": "true",
        "label": "New Team Member Alert (To PM)",
        "description": "Alerts the Project Manager via email when a new engineer is assigned to their project."
    },
    {
        "key": "email.daily_checkin_confirmation",
        "category": "email",
        "data_type": "boolean",
        "value": "false",
        "label": "Daily Check-In Confirmation (To Employee)",
        "description": "Dispatches a real-time confirmation email to the employee on every morning check-in (timestamp, site, status)."
    },
    {
        "key": "email.daily_checkout_summary",
        "category": "email",
        "data_type": "boolean",
        "value": "false",
        "label": "Daily Check-Out Summary (To Employee)",
        "description": "Dispatches an evening email upon check-out showing total hours worked on site and break durations."
    },
    {
        "key": "email.leave_application_notify_pm",
        "category": "email",
        "data_type": "boolean",
        "value": "true",
        "label": "Leave Application Submitted (To PM & TL)",
        "description": "Immediately emails the Project Manager and Team Lead when an employee submits a leave application."
    },
    {
        "key": "email.leave_application_ack_emp",
        "category": "email",
        "data_type": "boolean",
        "value": "true",
        "label": "Leave Submission Acknowledgement (To Employee)",
        "description": "Sends an acknowledgement email to the employee confirming their leave request was received and routed to PM."
    },
    {
        "key": "email.leave_decision_notify_emp",
        "category": "email",
        "data_type": "boolean",
        "value": "true",
        "label": "Leave Decision - Approved/Rejected (To Employee)",
        "description": "Immediately emails the employee when their leave request is approved or rejected by the manager with remarks."
    },
    {
        "key": "email.dispute_filed_notify_pm",
        "category": "email",
        "data_type": "boolean",
        "value": "true",
        "label": "Attendance Dispute Filed (To PM)",
        "description": "Immediately alerts the Project Manager via email when an employee logs a punch dispute from mobile."
    },
    {
        "key": "email.dispute_resolved_notify_emp",
        "category": "email",
        "data_type": "boolean",
        "value": "true",
        "label": "Attendance Dispute Resolved (To Employee)",
        "description": "Emails the employee when their attendance dispute has been reviewed and resolved by the Project Manager."
    },
    {
        "key": "email.morning_absentee_digest",
        "category": "email",
        "data_type": "boolean",
        "value": "true",
        "label": "Morning Absentee Digest 10:30 AM (To PM)",
        "description": "Automatically emails the PM at 10:30 AM listing project team members who have not checked in."
    },
    {
        "key": "email.evening_summary_report",
        "category": "email",
        "data_type": "boolean",
        "value": "true",
        "label": "Evening Attendance Summary 19:00 PM (To PM & Mgmt)",
        "description": "Dispatches a daily consolidated HTML attendance report to managers at 19:00 PM."
    },
    {
        "key": "email.late_arrival_warning",
        "category": "email",
        "data_type": "boolean",
        "value": "false",
        "label": "Chronic Late Arrival Advisory Warning (To Employee)",
        "description": "Auto-sends an advisory warning to employees who arrive late more than 3 times in a month."
    },

    # --- MOBILE APP FEATURE FLAGS ---
    {
        "key": "mobile.dispute_reporting_enabled",
        "category": "mobile",
        "data_type": "boolean",
        "value": "true",
        "label": "Dispute / Issue Reporting UI",
        "description": "Shows 'Something wrong with today's punch? Report to PM' and 'Report Dispute' buttons on mobile."
    },
    {
        "key": "mobile.check_now_button_enabled",
        "category": "mobile",
        "data_type": "boolean",
        "value": "true",
        "label": "Manual 'Check Now' Location Button",
        "description": "Provides an on-demand GPS check button in the mobile live geofence card."
    },
    {
        "key": "mobile.events_accordion_visible",
        "category": "mobile",
        "data_type": "boolean",
        "value": "true",
        "label": "Geofence Activity Accordion Visibility",
        "description": "Displays the 'Today's Geofence Activity' timeline card showing ENTER/EXIT history."
    },
    {
        "key": "mobile.events_accordion_default_open",
        "category": "mobile",
        "data_type": "boolean",
        "value": "false",
        "label": "Geofence Accordion Default State (Open vs Closed)",
        "description": "When OFF, geofence events accordion is collapsed by default on app launch."
    },
    {
        "key": "mobile.max_events_preview_count",
        "category": "mobile",
        "data_type": "integer",
        "value": "3",
        "label": "Initial Event Preview Count",
        "description": "Number of geofence events to display before showing the 'View all X events' toggle."
    },
    {
        "key": "mobile.offline_punch_allowed",
        "category": "mobile",
        "data_type": "boolean",
        "value": "true",
        "label": "Offline Punch Queue Mode",
        "description": "Allows punches to be recorded without internet and queued locally in Room SQLite."
    },
    {
        "key": "mobile.strict_device_binding",
        "category": "mobile",
        "data_type": "boolean",
        "value": "true",
        "label": "Strict Hardware Device Binding",
        "description": "Restricts employee check-in strictly to their bound registered physical smartphone."
    },
    {
        "key": "mobile.battery_prompt_enabled",
        "category": "mobile",
        "data_type": "boolean",
        "value": "true",
        "label": "Battery Optimization Warning Banner",
        "description": "Shows the warning button directing users to set battery optimization to 'Unrestricted' in Android settings."
    },
    {
        "key": "mobile.mock_location_blocking",
        "category": "mobile",
        "data_type": "boolean",
        "value": "true",
        "label": "Mock GPS / Fake Location Blocker",
        "description": "Rejects and flags attendance punches originating from mock GPS location provider apps."
    },
    {
        "key": "mobile.gps_accuracy_cutoff_m",
        "category": "mobile",
        "data_type": "integer",
        "value": "35",
        "label": "GPS Accuracy Cutoff Threshold (Meters)",
        "description": "Rejects location fixes whose uncertainty exceeds this threshold (e.g. ±35m) to prevent drift errors."
    },
    {
        "key": "mobile.dwell_time_buffer_mins",
        "category": "mobile",
        "data_type": "integer",
        "value": "2",
        "label": "Continuous Dwell-Time Buffer (Minutes)",
        "description": "Requires employee to remain inside geofence continuously for N minutes before confirming punch."
    },
    {
        "key": "mobile.exit_hysteresis_mins",
        "category": "mobile",
        "data_type": "integer",
        "value": "3",
        "label": "Exit Hysteresis Window (Minutes)",
        "description": "Requires employee to remain outside geofence for N minutes before marking a stepped-out break."
    },
    {
        "key": "mobile.banner_announcement_active",
        "category": "mobile",
        "data_type": "boolean",
        "value": "false",
        "label": "Mobile Home Screen Announcement Active",
        "description": "Displays the broadcast announcement card at the top of the mobile home screen."
    },
    {
        "key": "mobile.banner_announcement_text",
        "category": "mobile",
        "data_type": "string",
        "value": "",
        "label": "Broadcast Announcement Text",
        "description": "Custom notice text shown to all mobile app users (e.g. 'Office closed Friday for Diwali')."
    },

    # --- WEB ATTENDANCE REVIEW MODULE ---
    {
        "key": "web_review.auto_verify_geofence",
        "category": "web_review",
        "data_type": "boolean",
        "value": "true",
        "label": "Auto-Verification of Geofence Punches",
        "description": "Automatically verifies punches recorded within authorized geofences with a green verified badge."
    },
    {
        "key": "web_review.allow_pm_override",
        "category": "web_review",
        "data_type": "boolean",
        "value": "true",
        "label": "PM / TL Manual Punch Editing",
        "description": "Allows Project Managers and Team Leads to manually adjust In/Out punch times on /review."
    },
    {
        "key": "web_review.require_edit_reason",
        "category": "web_review",
        "data_type": "boolean",
        "value": "true",
        "label": "Mandatory Remarks on Manual Edit",
        "description": "Requires PMs/Admins to enter an explanation note before saving any modified punch time."
    },
    {
        "key": "web_review.lock_past_days",
        "category": "web_review",
        "data_type": "integer",
        "value": "7",
        "label": "Historical Attendance Lock Window (Days)",
        "description": "Records older than this cutoff are permanently frozen against modifications."
    },
    {
        "key": "web_review.show_gps_coordinates",
        "category": "web_review",
        "data_type": "boolean",
        "value": "true",
        "label": "Raw GPS Coordinates Display",
        "description": "Shows exact latitude, longitude, and accuracy numbers in the review table."
    },
    {
        "key": "web_review.allow_punch_deletion",
        "category": "web_review",
        "data_type": "boolean",
        "value": "false",
        "label": "Direct Punch Record Deletion",
        "description": "Provides an authorized 'Delete Punch' button on /review to remove false or errant punches."
    },

    # --- WEB LEAVES & POLICY ---
    {
        "key": "web_leaves.advance_notice_days",
        "category": "web_leaves",
        "data_type": "integer",
        "value": "2",
        "label": "Advance Notice Cutoff (Days)",
        "description": "Minimum days in advance required for planned leave applications."
    },
    {
        "key": "web_leaves.allow_negative_balance",
        "category": "web_leaves",
        "data_type": "boolean",
        "value": "false",
        "label": "Negative Leave Balance (LWP) Tolerance",
        "description": "Allows employees to apply for leave when quota is exhausted (marked as Leave Without Pay)."
    },
    {
        "key": "web_leaves.enable_half_day",
        "category": "web_leaves",
        "data_type": "boolean",
        "value": "true",
        "label": "Half-Day Leave Option",
        "description": "Enables First Half and Second Half partial day leave options."
    },
    {
        "key": "web_leaves.medical_cert_days",
        "category": "web_leaves",
        "data_type": "integer",
        "value": "2",
        "label": "Medical Certificate Upload Threshold (Days)",
        "description": "Sick leaves exceeding this duration mandate supporting document attachment."
    },
    {
        "key": "web_leaves.auto_escalate_hours",
        "category": "web_leaves",
        "data_type": "integer",
        "value": "48",
        "label": "Pending Leave Auto-Escalation (Hours)",
        "description": "Unanswered leave requests auto-escalate to HR after this duration."
    },
    {
        "key": "web_leaves.allow_employee_cancel",
        "category": "web_leaves",
        "data_type": "boolean",
        "value": "true",
        "label": "Employee Self-Cancellation of Approved Leaves",
        "description": "Allows employees to cancel upcoming approved leaves prior to the date."
    },

    # --- APPROVALS & WORKFLOW ---
    {
        "key": "web_approvals.prevent_self_approval",
        "category": "web_approvals",
        "data_type": "boolean",
        "value": "true",
        "label": "Manager Self-Approval Guard",
        "description": "Strictly prevents managers and TLs from approving their own leaves or punches."
    },
    {
        "key": "web_approvals.objection_reply_enabled",
        "category": "web_approvals",
        "data_type": "boolean",
        "value": "true",
        "label": "Employee Right-to-Reply (Objections)",
        "description": "Enables employees to reply and provide clarification when an approval is contested."
    },
    {
        "key": "web_approvals.proxy_approver_enabled",
        "category": "web_approvals",
        "data_type": "boolean",
        "value": "true",
        "label": "Out-of-Office Proxy Approver Delegation",
        "description": "Allows PMs on vacation to delegate approval authority to a designated peer."
    },

    # --- PROJECTS & TEAM ---
    {
        "key": "web_projects.multi_site_assignment",
        "category": "web_projects",
        "data_type": "boolean",
        "value": "true",
        "label": "Concurrent Multi-Site Assignment",
        "description": "Allows assigning an engineer to multiple work sites concurrently."
    },
    {
        "key": "web_projects.default_geofence_radius",
        "category": "web_projects",
        "data_type": "integer",
        "value": "20",
        "label": "Default Geofence Radius (Meters)",
        "description": "Global baseline radius in meters when adding new work sites."
    },
    {
        "key": "web_team.bench_pool_enabled",
        "category": "web_team",
        "data_type": "boolean",
        "value": "true",
        "label": "Bench / Unassigned Engineer Pool",
        "description": "Enables the Bench pool view on /team for engineers awaiting project deployment."
    },
    {
        "key": "web_team.pm_device_reset_allowed",
        "category": "web_team",
        "data_type": "boolean",
        "value": "false",
        "label": "PM Device Unbind Authority",
        "description": "Allows PMs to reset bound phone IDs for their team members."
    },
    {
        "key": "web_team.default_shift_start",
        "category": "web_team",
        "data_type": "string",
        "value": "09:30",
        "label": "Company Standard Shift Start",
        "description": "Standard shift start timing (HH:MM)."
    },
    {
        "key": "web_team.default_shift_end",
        "category": "web_team",
        "data_type": "string",
        "value": "18:30",
        "label": "Company Standard Shift End",
        "description": "Standard shift end timing (HH:MM)."
    }
]


def init_config_table(conn):
    """Creates the app_config table and seeds defaults if missing."""
    conn.execute("""
        CREATE TABLE IF NOT EXISTS app_config (
            key TEXT PRIMARY KEY,
            category TEXT NOT NULL,
            data_type TEXT NOT NULL,
            value TEXT NOT NULL,
            default_value TEXT NOT NULL,
            label TEXT NOT NULL,
            description TEXT NOT NULL,
            updated_by TEXT,
            updated_at TEXT
        )
    """)
    conn.commit()

    # Seed defaults
    existing = {r["key"] for r in conn.execute("SELECT key FROM app_config").fetchall()}
    now_iso = datetime.now().isoformat()
    for item in DEFAULT_CONFIGS:
        if item["key"] not in existing:
            conn.execute("""
                INSERT INTO app_config (key, category, data_type, value, default_value, label, description, updated_by, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, 'system', ?)
            """, (
                item["key"],
                item["category"],
                item["data_type"],
                item["value"],
                item["value"],
                item["label"],
                item["description"],
                now_iso
            ))
    conn.commit()
    reload_cache(conn)


def reload_cache(conn):
    """Reloads the in-memory cache from database."""
    global _CACHE
    rows = conn.execute("SELECT key, value, data_type FROM app_config").fetchall()
    new_cache = {}
    for r in rows:
        val_str = r["value"]
        dtype = r["data_type"]
        if dtype == "boolean":
            new_cache[r["key"]] = val_str.lower() in ("true", "1", "yes")
        elif dtype == "integer":
            try: new_cache[r["key"]] = int(val_str)
            except Exception: new_cache[r["key"]] = 0
        elif dtype == "float":
            try: new_cache[r["key"]] = float(val_str)
            except Exception: new_cache[r["key"]] = 0.0
        else:
            new_cache[r["key"]] = val_str
    _CACHE = new_cache


def get_config(key, default=None):
    """Returns the parsed configuration value from cache."""
    return _CACHE.get(key, default)


def set_config(conn, key, raw_value, updated_by="admin"):
    """Updates a single configuration key in DB and updates memory cache."""
    str_val = str(raw_value).strip()
    now_iso = datetime.now().isoformat()
    conn.execute("UPDATE app_config SET value=?, updated_by=?, updated_at=? WHERE key=?",
                 (str_val, updated_by, now_iso, key))
    conn.commit()
    reload_cache(conn)


def get_all_configs(conn):
    """Returns all configuration items organized by category."""
    rows = conn.execute("SELECT * FROM app_config ORDER BY category, key").fetchall()
    return [dict(r) for r in rows]


def get_mobile_config_dict():
    """Returns a clean JSON-serializable dictionary of all mobile.* flags."""
    res = {}
    for k, v in _CACHE.items():
        if k.startswith("mobile."):
            short_key = k[len("mobile."):]
            res[short_key] = v
    return res
