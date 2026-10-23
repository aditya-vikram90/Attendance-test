"""Attendance service for OpenProject teams.
Lead/admin enters in/out times and leave; summary by web page, email and Excel.
OpenProject is only READ (projects, members, open work packages) - nothing is written to it."""
import calendar, io, json, math, os, re, secrets, smtplib, sqlite3, ssl, threading, time
from datetime import date, datetime, timedelta
from email.message import EmailMessage
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from functools import wraps
from urllib.parse import urlencode
from zoneinfo import ZoneInfo

import requests
from flask import (Flask, abort, flash, g, has_request_context, jsonify, redirect, render_template, request,
                   send_file, session, url_for)
from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter
from werkzeug.middleware.proxy_fix import ProxyFix
import app_config, mailer

E = os.environ.get
DEV = E("DEV_MODE", "0") == "1"
OP_URL = E("OP_URL", "").rstrip("/")
OP_API_KEY = E("OP_API_KEY", "")
OP_PROJECTS = [x.strip() for x in E("OP_PROJECTS", "").split(",") if x.strip()]
ADMIN_EMAILS = {x.strip().lower() for x in E("ADMIN_EMAILS", "").split(",") if x.strip()}
if DEV: ADMIN_EMAILS.add("dev@example.com")
OP_ON = DEV or bool(OP_URL and OP_API_KEY)
TZ = ZoneInfo(E("TZ_NAME", "Asia/Kolkata"))
SHIFT_START = E("SHIFT_START", "09:30")
GRACE_MIN = int(E("GRACE_MIN", "15"))
SHIFT_MIN = int(float(E("SHIFT_HOURS", "9")) * 60)
WEEKLY_OFF = {x.strip().lower()[:3] for x in E("WEEKLY_OFF", "Sat,Sun").split(",") if x.strip()}
LEVELS = (0, 1, 2, 3)          # PM0 = top ... PM3 = lowest
DAYS = ('mon', 'tue', 'wed', 'thu', 'fri', 'sat', 'sun')
DEFAULT_HOURS = int(E("APPROVAL_HOURS", "24"))
MARK_BACK_DAYS = int(E("SELF_MARK_BACK_DAYS", "1"))
PLANNED_DAYS = int(E("LEAVE_PLANNED_DAYS", "3"))
APPROVE_HOURS = int(E("LEAVE_APPROVAL_HOURS", "30"))
CAPACITY_PCT = int(E("CAPACITY_PCT", "60"))
MAX_LEAVE_DAYS = 60
mnow = lambda: datetime.now(TZ)
def stamp(): return mnow().isoformat(timespec="seconds")
LEAVE_TYPES = [x.strip() for x in E("LEAVE_TYPES", "Casual Leave,Sick Leave,Earned Leave,Comp Off,Half Day,Other").split(",")]
DB_PATH = E("DB_PATH", "/data/attendance.db")
SUMMARY_TO = [x.strip() for x in E("SUMMARY_TO", "").split(",") if x.strip()]
SUMMARY_TIME = E("SUMMARY_TIME", "11:00")
BASE_URL = E("BASE_URL", "").rstrip("/")
DATABASE_URL = E("DATABASE_URL", "")                       # postgresql://user:password@host:5432/attendance ; empty = SQLite file
PG = DATABASE_URL.startswith(("postgres://", "postgresql://"))
KC_ADMIN_ROLE = E("KC_ADMIN_ROLE", "admin")                  # Keycloak role: System Administrator
KC_MANAGER_ROLE = E("KC_MANAGER_ROLE", "project-manager")    # Keycloak role: Project Manager
KC_MEMBER_ROLE = E("KC_MEMBER_ROLE", "member")               # Keycloak role: Team Member
if PG:
    import psycopg2, psycopg2.extras

app = Flask(__name__)
app.secret_key = E("SECRET_KEY") or secrets.token_hex(32)
# x_prefix lets Nginx serve the app under a sub-path such as /attendance (it sends X-Forwarded-Prefix)
app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1, x_prefix=1)
from urllib.parse import urlparse
app.config.update(SESSION_COOKIE_NAME="attendance_session", SESSION_COOKIE_PATH="/", SESSION_COOKIE_HTTPONLY=True, SESSION_COOKIE_SAMESITE="Lax",
                  SESSION_COOKIE_SECURE=BASE_URL.startswith("https://"),   # sign-in cookie is HTTPS-only when the site is HTTPS
                  PERMANENT_SESSION_LIFETIME=timedelta(hours=10))

oauth = None
if not DEV and E("OIDC_ISSUER"):
    from authlib.integrations.flask_client import OAuth
    oauth = OAuth(app)
    oauth.register("kc", client_id=E("OIDC_CLIENT_ID"), client_secret=E("OIDC_CLIENT_SECRET"),
                   server_metadata_url=E("OIDC_ISSUER", "").rstrip("/") + "/.well-known/openid-configuration",
                   client_kwargs={"scope": "openid email profile"})

# ---------------------------------------------------------------- database
class Conn:
    """Small wrapper so the same SQL runs on SQLite (default) and PostgreSQL (when DATABASE_URL is set)."""
    def __init__(self):
        if PG: self.c = psycopg2.connect(DATABASE_URL, cursor_factory=psycopg2.extras.RealDictCursor)
        else:
            os.makedirs(os.path.dirname(DB_PATH) or ".", exist_ok=True)
            self.c = sqlite3.connect(DB_PATH); self.c.row_factory = sqlite3.Row
    def execute(self, sql, params=()):
        if not PG: return self.c.execute(sql, tuple(params))
        cur = self.c.cursor(); cur.execute(sql.replace("%", "%%").replace("?", "%s"), tuple(params)); return cur
    def insert_id(self, sql, params=()):
        """Run an INSERT on a table with an auto id and return the new id."""
        if PG: return self.execute(sql + " RETURNING id", params).fetchone()["id"]
        return self.execute(sql, params).lastrowid
    def commit(self): self.c.commit()
    def rollback(self): self.c.rollback()
    def close(self): self.c.close()

AGG = "string_agg" if PG else "group_concat"

def db():
    if "db" not in g: g.db = Conn()
    return g.db

@app.teardown_appcontext
def _close(_):
    d = g.pop("db", None)
    if d: d.close()

def init_db():
    c = Conn(); auto = "SERIAL PRIMARY KEY" if PG else "INTEGER PRIMARY KEY AUTOINCREMENT"
    for ddl in (
        """CREATE TABLE IF NOT EXISTS attendance(
             day TEXT NOT NULL, user_id TEXT NOT NULL, user_name TEXT NOT NULL,
             in_time TEXT, out_time TEXT, leave_type TEXT, planned TEXT, handled_by TEXT, remarks TEXT,
             updated_by TEXT, updated_at TEXT, shift_start TEXT, PRIMARY KEY(day, user_id))""",
        """CREATE TABLE IF NOT EXISTS team(
             project_id TEXT NOT NULL, member_id TEXT NOT NULL, name TEXT NOT NULL, role TEXT, phone TEXT, email TEXT, shift_start TEXT,
             op_user_id TEXT, active INTEGER NOT NULL DEFAULT 1, updated_by TEXT, updated_at TEXT, PRIMARY KEY(project_id, member_id))""",
        f"""CREATE TABLE IF NOT EXISTS project(
             id {auto}, name TEXT NOT NULL, op_project_id TEXT, parent_id INTEGER,
             active INTEGER NOT NULL DEFAULT 1, created_by TEXT, created_at TEXT)""",
        "CREATE TABLE IF NOT EXISTS access(email TEXT PRIMARY KEY, name TEXT, role TEXT NOT NULL, all_projects INTEGER NOT NULL DEFAULT 0)",
        "CREATE TABLE IF NOT EXISTS project_access(project_id TEXT NOT NULL, email TEXT NOT NULL, kind TEXT NOT NULL, PRIMARY KEY(project_id, email, kind))",
        "CREATE TABLE IF NOT EXISTS watch(email TEXT NOT NULL, project_id TEXT NOT NULL, PRIMARY KEY(email, project_id))",
        "CREATE TABLE IF NOT EXISTS meta(k TEXT PRIMARY KEY, v TEXT)",
        f"CREATE TABLE IF NOT EXISTS revoked_sessions(id {auto}, sub TEXT, sid TEXT, revoked_at TEXT)",
        "CREATE TABLE IF NOT EXISTS pm_chain(project_id TEXT NOT NULL, level INTEGER NOT NULL, email TEXT NOT NULL, PRIMARY KEY(project_id, level))",
        """CREATE TABLE IF NOT EXISTS project_info(project_id TEXT PRIMARY KEY, owner_name TEXT, owner_email TEXT, owner_phone TEXT,
             location TEXT, lat TEXT, lon TEXT, updated_by TEXT, updated_at TEXT, min_capacity TEXT, weekly_off TEXT)""",
        """CREATE TABLE IF NOT EXISTS client_officer(project_id TEXT NOT NULL, member_id TEXT NOT NULL, name TEXT, email TEXT, phone TEXT,
             PRIMARY KEY(project_id, member_id))""",
        """CREATE TABLE IF NOT EXISTS approval(day TEXT NOT NULL, user_id TEXT NOT NULL, project_id TEXT, source TEXT, status TEXT NOT NULL,
             assigned_to TEXT, created_at TEXT, due_at TEXT, escalated_at TEXT, decided_by TEXT, decided_at TEXT, note TEXT, PRIMARY KEY(day, user_id))""",
        f"CREATE TABLE IF NOT EXISTS approval_miss(id {auto}, approver TEXT, project_id TEXT, day TEXT, user_id TEXT, missed_at TEXT)",
        f"CREATE TABLE IF NOT EXISTS objection(id {auto}, day TEXT, user_id TEXT, email TEXT, project_id TEXT, body TEXT, status TEXT NOT NULL DEFAULT 'open', reply TEXT, created_at TEXT, closed_by TEXT, closed_at TEXT, req_in TEXT, req_out TEXT, applied TEXT)",
        f"CREATE TABLE IF NOT EXISTS notice(id {auto}, email TEXT NOT NULL, kind TEXT, title TEXT, body TEXT, link TEXT, created_at TEXT, acked_at TEXT)",
        f"""CREATE TABLE IF NOT EXISTS leave_request(
             id {auto}, user_id TEXT NOT NULL, project_id TEXT, email TEXT, name TEXT, from_date TEXT NOT NULL, to_date TEXT NOT NULL,
             leave_type TEXT, reason TEXT, planned TEXT, status TEXT NOT NULL, assigned_to TEXT, created_at TEXT, due_at TEXT, decided_by TEXT, decided_at TEXT, note TEXT,
             suggest_from TEXT, suggest_to TEXT, capacity_full INTEGER NOT NULL DEFAULT 0, cap_days TEXT, is_extension INTEGER NOT NULL DEFAULT 0, ext_of INTEGER,
             early_join TEXT, escalations INTEGER NOT NULL DEFAULT 0, handled_by TEXT)""",
        f"CREATE TABLE IF NOT EXISTS leave_miss(id {auto}, request_id INTEGER, approver TEXT, project_id TEXT, missed_at TEXT, escalated_to TEXT)",
        "CREATE INDEX IF NOT EXISTS attendance_user ON attendance(user_id, day)",
        "CREATE INDEX IF NOT EXISTS revoked_sub_sid ON revoked_sessions(sub, sid)",
        "CREATE INDEX IF NOT EXISTS notice_open ON notice(email, acked_at)",
        "CREATE INDEX IF NOT EXISTS approval_status ON approval(status, assigned_to)",
        "CREATE INDEX IF NOT EXISTS leave_req_user ON leave_request(user_id, status)",
        "CREATE INDEX IF NOT EXISTS leave_status ON leave_request(status, assigned_to)"):
        c.execute(ddl)
    c.commit()
    # columns added after the first versions - harmless if they already exist
    for tbl, col in (
        ("team", "phone TEXT"),
        ("team", "email TEXT"),
        ("team", "shift_start TEXT"),
        ("team", "weekly_off TEXT"),
        ("project_info", "weekly_off TEXT"),
        ("project_info", "min_capacity TEXT"),
        ("attendance", "shift_start TEXT"),
        ("attendance", "duty_status TEXT DEFAULT 'Present'"),
        ("attendance", "approval_status TEXT DEFAULT 'Approved'"),
        ("attendance", "submitted_by TEXT DEFAULT ''"),
        ("attendance", "approved_by TEXT DEFAULT ''"),
        ("attendance", "approved_at TEXT DEFAULT ''"),
        ("attendance", "rejection_reason TEXT DEFAULT ''"),
        ("project", "parent_id INTEGER"),
        ("objection", "req_in TEXT"),
        ("objection", "req_out TEXT"),
        ("objection", "applied TEXT"),
        ("leave_request", "handled_by TEXT"),
        ("leave_request", "escalations INTEGER NOT NULL DEFAULT 0"),
        ("leave_request", "early_join TEXT"),
    ):
        try: c.execute(f"ALTER TABLE {tbl} ADD COLUMN {'IF NOT EXISTS ' if PG else ''}{col}"); c.commit()
        except Exception: c.rollback()
    try:
        app_config.init_config_table(c)
    except Exception as ex:
        app.logger.warning("app_config init warning: %s", ex)
    c.close()
init_db()

# ---------------------------------------------------------------- OpenProject (read only)
_cache = {}
def cached(key, ttl, fn):
    hit = _cache.get(key)
    if hit and hit[0] > time.time(): return hit[1]
    val = fn(); _cache[key] = (time.time() + ttl, val); return val

def op_get(path, params=None):
    r = requests.get(OP_URL + path, params=params, auth=("apikey", OP_API_KEY), timeout=20)
    r.raise_for_status(); return r.json()

def op_all(path, params=None):
    out, offset = [], 1
    while True:
        p = dict(params or {}, pageSize=200, offset=offset)
        j = op_get(path, p); els = j.get("_embedded", {}).get("elements", [])
        out += els
        if not els or len(out) >= j.get("total", 0): return out
        offset += 1

DEMO = {"projects": [{"id": "1", "name": "Project A"}, {"id": "2", "name": "Project B"}],
        "members": {"1": [("11", "Team Member 1"), ("12", "Team Member 2"), ("13", "Team Member 3"), ("14", "Team Member 4"), ("15", "Team Member 5")],
                    "2": [("21", "Team Member 6"), ("22", "Team Member 7"), ("11", "Team Member 1")]}}

def op_projects():
    """Projects in OpenProject - only used to offer an optional link."""
    if DEV: return DEMO["projects"]
    if not OP_ON: return []
    def load():
        els = op_all("/api/v3/projects", {"filters": json.dumps([{"active": {"operator": "=", "values": ["t"]}}])})
        ps = [{"id": str(e["id"]), "name": e["name"], "identifier": e.get("identifier", "")} for e in els]
        if OP_PROJECTS: ps = [p for p in ps if p["identifier"] in OP_PROJECTS or p["name"] in OP_PROJECTS]
        return sorted(ps, key=lambda p: p["name"].lower())
    return cached("projects", 300, load)

def op_members(pid):
    """OpenProject members of a project: [{id, name, roles}] - users only (groups are skipped)."""
    if DEV: return [{"id": i, "name": n, "roles": []} for i, n in DEMO["members"].get(str(pid), [])]
    def load():
        els = op_all("/api/v3/memberships", {"filters": json.dumps([{"project": {"operator": "=", "values": [str(pid)]}}])})
        out = {}
        for e in els:
            pr = e["_links"]["principal"]
            if "/users/" not in pr.get("href", ""): continue
            uid = pr["href"].rsplit("/", 1)[-1]
            out[uid] = {"id": uid, "name": pr.get("title", uid),
                        "roles": [r.get("title", "") for r in e["_links"].get("roles", [])]}
        return sorted(out.values(), key=lambda m: m["name"].lower())
    return cached(("members", str(pid)), 300, load)

def op_user(uid):
    return cached(("user", uid), 900, lambda: op_get(f"/api/v3/users/{uid}"))

def open_tasks(uid):
    """Open work packages assigned to this user. Never raises - returns [] on failure."""
    if not uid or not OP_ON: return []
    if DEV:
        return [{"id": 101, "subject": "Sample open task", "project": "Project A", "status": "In progress", "due": "", "url": "#"}] if uid == "14" else []
    def load():
        try:
            f = json.dumps([{"assignee": {"operator": "=", "values": [str(uid)]}}, {"status": {"operator": "o", "values": []}}])
            els = op_get("/api/v3/work_packages", {"filters": f, "pageSize": 50}).get("_embedded", {}).get("elements", [])
            return [{"id": e["id"], "subject": e.get("subject", ""), "project": e["_links"].get("project", {}).get("title", ""),
                     "status": e["_links"].get("status", {}).get("title", ""), "due": e.get("dueDate") or "",
                     "url": f"{OP_URL}/work_packages/{e['id']}"} for e in els]
        except Exception as ex:
            app.logger.warning("open_tasks failed for %s: %s", uid, ex); return []
    return cached(("tasks", uid), 300, load)

# ---------------------------------------------------------------- projects (created in this service)
# ---- validation (the same rules are also enforced in the browser)
import unicodedata
def _letter(ch): return unicodedata.category(ch)[0] in "LM"       # letters and their combining marks, any language

def _ok(t, extra, lo, hi, first_digit=False):
    """Text of lo..hi chars made of letters plus the 'extra' characters, starting with a letter (or digit if allowed)."""
    return (lo <= len(t) <= hi and all(_letter(c) or c in extra for c in t)
            and (unicodedata.category(t[0])[0] == "L" or (first_digit and t[0].isdigit())) and sum(c.isalpha() for c in t) >= (1 if first_digit else 2))

class _Rule:
    def __init__(self, fn): self.fn = fn
    def match(self, t): return self.fn(t)
NAME_RE = _Rule(lambda t: _ok(t, " .'-", 2, 100))
ROLE_RE = _Rule(lambda t: _ok(t, "0123456789 .&/()+-", 2, 60))
PROJECT_RE = _Rule(lambda t: _ok(t, "0123456789 .&/()+,:_-", 2, 80, first_digit=True))
EMAIL_RE = re.compile(r"^[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}$")
PHONE_RE = re.compile(r"^(?:\+?91|0)?([6-9]\d{9})$")
def mail_ok(s): return (not s) or bool(EMAIL_RE.match(s))

def squash(t): return " ".join((t or "").split())

def v_name(t):
    t = squash(t)
    if not NAME_RE.match(t): raise ValueError("Name must be letters only (spaces, dot, apostrophe and hyphen allowed), at least 2 letters.")
    return t

def v_role(t):
    t = squash(t)
    if not ROLE_RE.match(t): raise ValueError("Role must start with a letter and be a real role name, for example \"DevOps Engineer\" or \"L2 Support\".")
    return t

def v_phone(t):
    m = PHONE_RE.match(re.sub(r"[\s\-()]", "", t or ""))
    if not m: raise ValueError("Contact number must be a 10-digit mobile number starting with 6, 7, 8 or 9 (+91 or 0 in front is fine).")
    return m.group(1)

def v_mail(t):
    """Compulsory. Email for employee profile and login."""
    t = (t or "").strip().lower()
    if not t: raise ValueError("Email address is required.")
    if not EMAIL_RE.match(t): raise ValueError("Email is not a valid address.")
    return t

def v_shift(t):
    """Optional own shift start (HH:MM). Empty = the default shift."""
    t = (t or "").strip()
    if t and (not re.fullmatch(r"([01]\d|2[0-3]):[0-5]\d", t)): raise ValueError("Shift start must be a time like 14:00.")
    return "" if t == SHIFT_START else t

def v_project(t):
    t = squash(t)
    if not PROJECT_RE.match(t): raise ValueError("Project name must be 2-80 characters, start with a letter or digit, and contain at least one letter.")
    return t

def split_emails(txt):
    """-> (valid emails, invalid entries)"""
    parts = [e.strip().lower() for e in re.split(r"[,;\s]+", txt or "") if e.strip()]
    return sorted({e for e in parts if EMAIL_RE.match(e)}), [e for e in parts if not EMAIL_RE.match(e)]

def projects(include_archived=False):
    """Main projects and sub-projects. 'name' is the full label ("Main / Sub"), 'short' the project's own name."""
    rows = {str(r["id"]): r for r in db().execute("SELECT * FROM project")}
    out = []
    for i, r in rows.items():
        par = rows.get(str(r["parent_id"])) if r.get("parent_id") else None
        r_act = r.get("active", 1)
        p_act = par.get("active", 1) if par else 1
        act = 1 if r_act and p_act else 0
        if act or include_archived:
            out.append({"id": i, "short": r["name"], "name": (par["name"] + " / " if par else "") + r["name"], "op_id": r.get("op_project_id") or "",
                        "active": act, "own_active": r_act, "parent": str(r["parent_id"]) if par else ""})
    return sorted(out, key=lambda p: p["name"].lower())

def proj(pid):
    return next((p for p in projects(True) if p["id"] == str(pid)), None)

def chain(pid):
    """[(level, email)] for the project, PM0 first; falls back to the main project's chain."""
    ids = [str(pid)]
    p = proj(pid)
    if p and p.get("parent"): ids.append(str(p["parent"]))
    for i in ids:
        rows = [(r["level"], r["email"].lower()) for r in db().execute("SELECT level,email FROM pm_chain WHERE project_id=? ORDER BY level", (i,))]
        if rows: return rows
    return []

def op_candidates(pid):
    """OpenProject members of the linked project, if this project is linked."""
    p = proj(pid)
    return op_members(p["op_id"]) if p and p["op_id"] and OP_ON else []

# ---------------------------------------------------------------- teams (kept in this service by the TL/PM)
def team(pid, active_only=True):
    q = ("SELECT * FROM team WHERE project_id=?" +
         (" AND active=1" if active_only else "") +
         " ORDER BY active DESC, (CASE WHEN lower(role) LIKE '%manager%' OR lower(role) LIKE '%lead%' THEN 0 ELSE 1 END), lower(name)")
    return [{"id": r["member_id"], "name": r["name"], "role": r["role"] or "", "phone": r["phone"] or "", "email": r["email"] or "", "shift": r["shift_start"] or "",
             "op_uid": r["op_user_id"] or "", "active": r["active"], "user_id": r["user_id"] if "user_id" in r.keys() else None,
             "assigned_from": r["assigned_from"] if "assigned_from" in r.keys() else None,
             "assigned_to": r["assigned_to"] if "assigned_to" in r.keys() else None}
            for r in db().execute(q, (str(pid),))]

def members(pid): return team(pid)

def is_assigned_on(assignments, day_str):
    """Returns True if at least one assignment was active on the given date (day_str: 'YYYY-MM-DD')."""
    if not assignments: return True
    d = date.fromisoformat(day_str)
    has_any_dates = False
    for a in assignments:
        af = a.get("from"); at = a.get("to")
        if af or at: has_any_dates = True
        af_d = af.date() if hasattr(af, "date") else (date.fromisoformat(str(af)[:10]) if af else None)
        at_d = at.date() if hasattr(at, "date") else (date.fromisoformat(str(at)[:10]) if at else None)
        if af_d and d < af_d: continue
        if at_d and d > at_d: continue
        return True
    return not has_any_dates

def roster(pids=None, include_inactive=False):
    """{member_id: {name, role, projects:[names], op_uid, active, assignments:[...]}} for the given projects (None = all)."""
    out = {}
    for p in projects():
        if pids is not None and p["id"] not in pids: continue
        for m in team(p["id"], active_only=not include_inactive):
            e = out.setdefault(m["id"], {"id": m["id"], "name": m["name"], "role": m.get("role", ""), "projects": [], "op_uid": m["op_uid"], "active": 0, "assignments": []})
            e["role"] = e.get("role") or m.get("role", "")
            e["projects"].append(p["name"]); e["active"] = max(e["active"], m["active"])
            e["assignments"].append({
                "project_id": p["id"],
                "project_name": p["name"],
                "from": m.get("assigned_from"),
                "to": m.get("assigned_to"),
            })
    return out

# ---------------------------------------------------------------- auth
def current_user(): return session.get("user") if has_request_context() else None

def login_required(fn):
    @wraps(fn)
    def w(*a, **k):
        if DEV and not current_user():
            session["user"] = {"email": "dev@example.com", "name": "Dev Admin", "login": "dev"}
        if not current_user():
            session["next"] = request.script_root + request.full_path; return redirect(url_for("login"))
        if my_role() is None:
            return render_template("message.html", msg="Your account has no access yet. Ask your TL/PM to add your email to the team, "
                                   "or the administrator to give you access."), 403
        if my_role() == "engineer" and request.endpoint not in ("me", "me_attendance", "checkin", "trends", "summary") and not (request.endpoint or "").startswith("wf_e_"): return redirect(url_for("me"))
        return fn(*a, **k)
    return w

def email(): return ((current_user() or {}).get("email") or "").lower()

def has_role(r): return bool(r) and r in ((current_user() or {}).get("roles") or [])

def is_admin(): return (bool(email()) and email() in ADMIN_EMAILS) or has_role(KC_ADMIN_ROLE)

def access_row(): return db().execute("SELECT * FROM access WHERE email=?", (email(),)).fetchone()

def my_role():
    """admin (settings file) | manager | lead (TL/PM) | None (no access)."""
    if not current_user(): return None
    if is_admin(): return "admin"
    r = access_row()
    if r:
        if r["role"] == "lead":
            has_projects = db().execute("SELECT 1 FROM project_access WHERE lower(email)=? AND kind IN ('lead', 'pm')", (email(),)).fetchone()
            has_chain = db().execute("SELECT 1 FROM pm_chain WHERE lower(email)=?", (email(),)).fetchone()
            if not has_projects and not has_chain:
                db().execute("DELETE FROM access WHERE lower(email)=? AND role='lead'", (email(),))
                db().commit()
                r = None
        if r: return r["role"]
    if db().execute("SELECT 1 FROM pm_chain WHERE lower(email)=?", (email(),)).fetchone():
        return "lead"
    if has_role(KC_MANAGER_ROLE): return "manager"
    return "engineer" if (my_member_ids() or has_role(KC_MEMBER_ROLE)) else None

def my_member_ids():
    """Team-member records whose email is the signed-in person's email."""
    return [r["member_id"] for r in db().execute("SELECT DISTINCT member_id FROM team WHERE lower(email)=?", (email(),))] if email() else []

def watched():
    """Projects this manager/admin chose to watch (empty = no choice made, show everything allowed)."""
    w = {r["project_id"] for r in db().execute("SELECT project_id FROM watch WHERE email=?", (email(),))}
    return [p for p in my_projects() if p["id"] in w or p["parent"] in w]   # a watched main project brings its sub-projects

def shown_projects():
    return (watched() if my_role() in ("admin", "manager") else []) or my_projects()

def my_projects(include_archived=False):
    """Admin: all. Manager: all, or the selected ones. TL/PM: only the projects they lead.
    Access to a main project includes all its sub-projects."""
    ps = projects(include_archived)
    if is_admin(): return ps
    r = access_row()
    if not r and not db().execute("SELECT 1 FROM pm_chain WHERE lower(email)=?", (email(),)).fetchone():
        return ps if has_role(KC_MANAGER_ROLE) else []
    if r and r["role"] == "manager" and r["all_projects"]: return ps
    mine = {str(x["project_id"]) for x in db().execute("SELECT project_id FROM project_access WHERE lower(email)=?", (email(),))}
    mine |= {str(x["project_id"]) for x in db().execute("SELECT project_id FROM pm_chain WHERE lower(email)=?", (email(),))}
    return [p for p in ps if p["id"] in mine or p["parent"] in mine]

def my_pids(): return [p["id"] for p in my_projects()]

def can_view(pid): return str(pid) in my_pids()

def can_edit(pid):
    """Admins and the TL/PM of the project (or of its main project) can change things. Managers only view."""
    if not can_view(pid): return False
    if is_admin(): return True
    p = proj(pid); ids = [str(pid)] + ([p["parent"]] if p and p["parent"] else [])
    has_acc = db().execute(f"SELECT 1 FROM project_access WHERE lower(email)=? AND kind IN ('lead', 'pm') AND project_id IN ({','.join('?' * len(ids))})",
                           (email(), *ids)).fetchone() is not None
    return has_acc or any(e == email() for _, e in chain(pid))

def can_edit_attendance(pid, day):
    """Admins can edit any date. PM/TL can edit current day (till end of day) and future dates. Past dates are locked for PM/TL."""
    if not can_edit(pid): return False
    if is_admin(): return True
    if day < today(): return False
    return True

# ------------------------------------------------------------ approvals & notifications helpers
def hours():
    r = db().execute("SELECT v FROM meta WHERE k='approval_hours'").fetchone()
    try: return max(1, int(r["v"])) if r else DEFAULT_HOURS
    except (TypeError, ValueError): return DEFAULT_HOURS

def team_row(user_id):
    return db().execute("SELECT * FROM team WHERE member_id=? AND active=1 ORDER BY project_id LIMIT 1", (user_id,)).fetchone()

def on_leave(email_addr, day):
    """True when this person's own attendance for the day says leave."""
    if not email_addr: return False
    for t in db().execute("SELECT member_id FROM team WHERE lower(email)=?", (email_addr.lower(),)):
        a = db().execute("SELECT leave_type FROM attendance WHERE day=? AND user_id=?", (day, t["member_id"])).fetchone()
        if a and (a["leave_type"] or "").strip(): return True
    return False

def approver_for(pid, day):
    """Primary active PM/TL of the project who is not on leave that day (PM0 -> PM1 -> PM2 -> PM3); '' when nobody is set up."""
    ch = chain(pid)
    if ch:
        for _, em in sorted(ch, key=lambda x: x[0]):
            if not on_leave(em, day): return em
        return ch[0][1] # everybody is away: the top of the chain (PM0)
    leads = [r["email"].lower() for r in db().execute("SELECT email FROM project_access WHERE project_id=? AND kind='lead' ORDER BY email", (str(pid),))]
    for em in leads:
        if not on_leave(em, day): return em
    return leads[0] if leads else ""

def can_decide(row):
    if is_admin(): return True
    if row["status"] == "escalated": return False # escalated items belong to the admin
    pid = row["project_id"]; em = email()
    return any(e == em for _, e in chain(pid)) or can_edit(pid)

def project_people(pid):
    """Every PM/TL of the project: the chain plus the leads (and the main project's)."""
    ids = [str(pid)]; p = proj(pid)
    if p and p.get("parent"): ids.append(str(p["parent"]))
    out = {e for i in ids for _, e in chain(i)}
    for i in ids:
        out |= {r["email"].lower() for r in db().execute("SELECT email FROM project_access WHERE project_id=? AND kind='lead'", (i,))}
    return sorted(out)

def send_mail(to, subject, body):
    if not E("SMTP_HOST") or not to: return
    def go():
        try:
            m = MIMEText(body, "plain", "utf-8"); m["Subject"] = subject; m["From"] = E("SMTP_FROM") or E("SMTP_USER", ""); m["To"] = to
            with smtplib.SMTP(E("SMTP_HOST"), int(E("SMTP_PORT", "587")), timeout=20) as sm:
                sm.starttls(context=ssl.create_default_context())
                if E("SMTP_USER"): sm.login(E("SMTP_USER"), E("SMTP_PASSWORD", ""))
                sm.sendmail(m["From"], [to], m.as_string())
        except Exception as ex: app.logger.error("notice email to %s failed: %s", to, ex)
    threading.Thread(target=go, daemon=True).start()

def notify(emails, kind, title, body, link=""):
    """One popup per person (shown until acknowledged) and an email when SMTP is configured."""
    for em in sorted({(e or "").strip().lower() for e in emails if e}):
        db().execute("INSERT INTO notice(email,kind,title,body,link,created_at) VALUES(?,?,?,?,?,?)", (em, kind, title, body, link, stamp()))
        send_mail(em, title, body + ("\n\n" + (BASE_URL + link) if link else ""))

def wf_refresh():
    """Keep approvals up to date; escalate overdue requests and record SLA misses."""
    t, nowiso = mnow(), stamp(); d0 = (t.date() - timedelta(days=14)).isoformat(); hrs = hours()
    for r in db().execute("SELECT * FROM attendance WHERE day>=? AND in_time IS NOT NULL AND in_time<>''", (d0,)).fetchall():
        r = dict(r); mem = team_row(r["user_id"])
        if not mem: continue
        pid = mem["project_id"]; who = (r.get("updated_by") or "").lower()
        ap = db().execute("SELECT * FROM approval WHERE day=? AND user_id=?", (r["day"], r["user_id"])).fetchone()
        by_engineer = (who == "app" or who == (mem["email"] or "").lower() or (r.get("approval_status") == "Pending") or bool(r.get("submitted_by")))
        if by_engineer and (r.get("approval_status") == "Pending" or not r.get("approval_status")):
            src = "phone" if who == "app" else "engineer"
            assigned = approver_for(pid, r["day"])
            if not ap:
                db().execute("INSERT INTO approval(day,user_id,project_id,source,status,assigned_to,created_at,due_at) VALUES(?,?,?,?,?,?,?,?)",
                             (r["day"], r["user_id"], pid, src, "pending", assigned, nowiso, (t + timedelta(hours=hrs)).isoformat(timespec="seconds")))
                if assigned:
                    notify([assigned], "attendance_pending",
                           f"Attendance approval needed: {mem['name'] if mem else r['user_id']} ({r['day']})",
                           f"{mem['name'] if mem else r['user_id']} checked in via {src} (IN {r.get('in_time') or '--:--'}). Waiting for your approval.",
                           "/approvals")
            elif ap["status"] in ("approved", "rejected") and (r.get("updated_at") or "") > (ap.get("decided_at") or ""):
                db().execute("UPDATE approval SET status='pending', source=?, assigned_to=?, created_at=?, due_at=?, decided_by=NULL, decided_at=NULL, escalated_at=NULL WHERE day=? AND user_id=?",
                             (src, assigned, nowiso, (t + timedelta(hours=hrs)).isoformat(timespec="seconds"), r["day"], r["user_id"]))
                if assigned:
                    notify([assigned], "attendance_pending",
                           f"Attendance updated: {mem['name'] if mem else r['user_id']} ({r['day']})",
                           f"{mem['name'] if mem else r['user_id']} updated attendance. Waiting for your approval.",
                           "/approvals")
            elif ap["status"] == "pending":
                db().execute("UPDATE approval SET assigned_to=?, project_id=? WHERE day=? AND user_id=?", (assigned, pid, r["day"], r["user_id"]))
        elif not by_engineer or r.get("approval_status") == "Approved":
            if not ap:
                db().execute("INSERT INTO approval(day,user_id,project_id,source,status,created_at,decided_by,decided_at,note) VALUES(?,?,?,?,?,?,?,?,?)",
                             (r["day"], r["user_id"], pid, "pm", "approved", nowiso, who, nowiso, "entered by PM/TL"))
            elif ap["status"] in ("pending", "escalated"):
                db().execute("UPDATE approval SET status='approved', decided_by=?, decided_at=?, note='entered by PM/TL' WHERE day=? AND user_id=?", (who, nowiso, r["day"], r["user_id"]))
    
    # SLA escalation for pending approvals
    for ap in db().execute("SELECT * FROM approval WHERE status='pending' AND due_at<?", (nowiso,)).fetchall():
        db().execute("UPDATE approval SET status='escalated', escalated_at=? WHERE day=? AND user_id=?", (nowiso, ap["day"], ap["user_id"]))
        if ap["assigned_to"]:
            db().execute("INSERT INTO approval_miss(approver,project_id,day,user_id,missed_at) VALUES(?,?,?,?,?)", (ap["assigned_to"], ap["project_id"], ap["day"], ap["user_id"], nowiso))
    wf_leave_escalate()
    db().commit()

def safe_refresh():
    try: wf_refresh()
    except Exception as ex:
        app.logger.error("approval refresh: %s", ex)
        try: db().rollback()
        except Exception: pass

def my_member():
    for mid in my_member_ids():
        t = team_row(mid)
        if t: return t
    return None

# ------------------------------------------------------------ leave workflow & capacity engine
def setting(key, default):
    r = db().execute("SELECT v FROM meta WHERE k=?", (key,)).fetchone()
    try: return max(0, int(r["v"])) if r else default
    except (TypeError, ValueError): return default

def planned_days(): return setting("leave_planned_days", PLANNED_DAYS)
def approve_hours(): return max(1, setting("leave_approval_hours", APPROVE_HOURS))

def d_(s): return date.fromisoformat(s)

def span(f, t):
    d = d_(f); out = []
    while d <= d_(t): out.append(d.isoformat()); d += timedelta(days=1)
    return out

def wd(day): return d_(day).strftime("%a").lower()

def work_days(uid, f, t):
    return [x for x in span(f, t) if wd(x) not in off_days(uid)]

def roster_engineers(pid, day):
    """Engineers of the project assigned on that day (PM/TL on the chain are not counted as capacity)."""
    skip = set(project_people(pid))
    out = []
    for m in members(pid):
        if (m["email"] or "").lower() in skip: continue
        if not is_assigned_on([{"from": m.get("assigned_from"), "to": m.get("assigned_to")}], day): continue
        out.append(m)
    return out

def min_cap(pid, total):
    r = db().execute("SELECT min_capacity FROM project_info WHERE project_id=?", (str(pid),)).fetchone()
    try:
        if r and (r["min_capacity"] or "").strip(): return max(0, int(r["min_capacity"]))
    except (TypeError, ValueError): pass
    return math.ceil(total * CAPACITY_PCT / 100) if total else 0

def day_cap(pid, day):
    working = [m for m in roster_engineers(pid, day) if wd(day) not in off_days(m["id"])]
    ids = {m["id"] for m in working}
    away_rows = db().execute("SELECT user_id FROM attendance WHERE day=? AND leave_type IS NOT NULL AND leave_type<>''", (day,)).fetchall()
    away = {r["user_id"] for r in away_rows} & ids
    pend_rows = db().execute("SELECT user_id FROM leave_request WHERE status IN ('pending','modification','withdraw_requested') AND from_date<=? AND to_date>=?", (day, day)).fetchall()
    pend = {r["user_id"] for r in pend_rows} & ids - away
    total = len(working)
    mn = min_cap(pid, total)
    avail = total - len(away)
    
    mem_dict = {m["id"]: m["name"] for m in working}
    names_away = [mem_dict[u] for u in away if u in mem_dict]
    names_pend = [mem_dict[u] for u in pend if u in mem_dict]
    
    return {
        "day": day,
        "total": total,
        "away": len(away),
        "pending": len(pend),
        "available": avail,
        "minimum": mn,
        "short": avail < mn,
        "away_ids": away,
        "pend_ids": pend,
        "names_away": names_away,
        "names_pend": names_pend
    }

def check_capacity(pid, uid, f, t):
    """Days in the range on which approving this leave would leave the team below its minimum."""
    bad = []
    for day in work_days(uid, f, t):
        c = day_cap(pid, day)
        mine = 0 if uid in c["away_ids"] else 1
        if c["total"] and c["available"] - mine < c["minimum"]:
            bad.append({"day": day, "available_after": c["available"] - mine, "minimum": c["minimum"], "total": c["total"], "pending": c["pending"]})
    return bad

def others_leave(pid, uid, f, t):
    """Team-mates who already applied for days that overlap, so people can see before applying."""
    out = []
    for r in db().execute("""SELECT * FROM leave_request WHERE project_id=? AND user_id<>? AND status IN ('pending','approved','modification','withdraw_requested')
                             AND to_date>=? AND from_date<=? ORDER BY from_date""", (str(pid), uid, f, t)).fetchall():
        out.append({"name": r["name"], "from": r["from_date"], "to": r["to_date"], "status": r["status"], "type": r["leave_type"]})
    return out

def level_of(pid, email_addr):
    for lv, e in chain(pid):
        if e == (email_addr or "").lower(): return lv
    return None

def one_above(pid, email_addr):
    """Email of the person one step above `email_addr` on the chain; 'admin' from top or when no chain."""
    lv = level_of(pid, email_addr)
    if lv is None: return "admin"
    above = [(l, e) for l, e in chain(pid) if l < lv]
    return max(above)[1] if above else "admin"

def can_approve_leave(req):
    """Approve rights: admin, the person it is assigned to, or anyone higher on the chain."""
    if is_admin(): return True
    em = email()
    if req["assigned_to"] == "admin": return False
    if em == (req["assigned_to"] or ""): return True
    a, me = level_of(req["project_id"], req["assigned_to"]), level_of(req["project_id"], em)
    return a is not None and me is not None and me < a

def can_manage_leave(pid):
    return is_admin() or can_edit(pid) or level_of(pid, email()) is not None

def write_leave_days(req, who):
    t = team_row(req["user_id"])
    n = 0
    now_stamp = stamp()
    for day in work_days(req["user_id"], req["from_date"], req["to_date"]):
        cur = db().execute("SELECT in_time FROM attendance WHERE day=? AND user_id=?", (day, req["user_id"])).fetchone()
        if cur and (cur["in_time"] or "").strip(): continue # already worked that day
        db().execute("""INSERT INTO attendance(
            day, user_id, user_name, in_time, out_time, leave_type, planned, handled_by,
            remarks, updated_by, updated_at, shift_start, duty_status, approval_status, approved_by, approved_at
        ) VALUES(?,?,?,'','',?,?,?,?,?,?,?,'Present','Approved',?,?)
        ON CONFLICT(day,user_id) DO UPDATE SET
            in_time='',out_time='',leave_type=excluded.leave_type,planned=excluded.planned,
            handled_by=excluded.handled_by,remarks=excluded.remarks,updated_by=excluded.updated_by,
            updated_at=excluded.updated_at,duty_status='Present',approval_status='Approved',
            approved_by=excluded.approved_by,approved_at=excluded.approved_at""",
            (day, req["user_id"], req["name"], req["leave_type"], req["planned"], req.get("handled_by") or "",
             f"Leave #{req['id']}: {(req['reason'] or '')[:100]}", who, now_stamp,
             (t["shift_start"] if t else "") or SHIFT_START, who, now_stamp))
        n += 1
    return n

def clear_leave_days(req, from_day):
    for day in span(max(from_day, req["from_date"]), req["to_date"]):
        db().execute("DELETE FROM attendance WHERE day=? AND user_id=? AND leave_type IS NOT NULL AND leave_type<>'' AND (in_time IS NULL OR in_time='') AND remarks LIKE ?",
                     (day, req["user_id"], f"Leave #{req['id']}:%"))

def wf_leave_escalate():
    t = mnow(); nowiso = stamp(); hrs = approve_hours()
    for r in db().execute("SELECT * FROM leave_request WHERE status='pending' AND due_at<?", (nowiso,)).fetchall():
        r = dict(r)
        above = one_above(r["project_id"], r["assigned_to"]) if r["assigned_to"] != "admin" else "admin"
        db().execute("INSERT INTO leave_miss(request_id,approver,project_id,missed_at,escalated_to) VALUES(?,?,?,?,?)",
                     (r["id"], r["assigned_to"], r["project_id"], nowiso, above))
        db().execute("UPDATE leave_request SET assigned_to=?, due_at=?, escalations=escalations+1 WHERE id=?",
                     (above, (t + timedelta(hours=hrs)).isoformat(timespec="seconds"), r["id"]))
        who = [above] if above != "admin" else [e for e in project_people(r["project_id"])]
        notify(who + [r["assigned_to"] if r["assigned_to"] != "admin" else ""], "leave",
               f"Leave of {r['name']} not decided in time ({r['from_date']} to {r['to_date']})",
               f"Waiting more than {hrs} hours. It now needs {above}.", "/leaves")

def can_create(): return my_role() in ("admin", "lead")

def pick_pids():
    """Project filter from ?project= limited to what this user may see."""
    pid = request.values.get("project", "")
    if pid and can_view(pid):   # a main project brings its sub-projects with it
        return [pid] + [p["id"] for p in my_projects() if p["parent"] == pid], pid
    return [p["id"] for p in shown_projects()], ""

@app.route("/login")
def login():
    if request.args.get("logged_out"):
        return render_template("message.html", msg='You have been signed out. <a href="' + url_for("login") + '" class="btn" style="margin-left:12px">Sign in again</a>')
    if DEV: return redirect(url_for("entry"))
    return oauth.kc.authorize_redirect((BASE_URL or request.url_root.rstrip("/")) + "/auth/callback")

@app.route("/auth/callback")
def auth_callback():
    try:
        tok = oauth.kc.authorize_access_token()
        ui = tok.get("userinfo") or {}
    except Exception as ex:
        app.logger.warning("OAuth authorization failed in callback: %s. Redirecting to login.", ex)
        for k in list(session.keys()):
            if k.startswith("_state_"): session.pop(k, None)
        return redirect(url_for("login"))

    session.permanent = True
    roles = []
    try:      # roles live in the access token Keycloak just handed us over TLS
        import base64
        part = tok.get("access_token", "").split(".")[1]; claims = json.loads(base64.urlsafe_b64decode(part + "=" * (-len(part) % 4)))
        roles = list(claims.get("realm_access", {}).get("roles", [])) + list(claims.get("resource_access", {}).get(E("OIDC_CLIENT_ID", ""), {}).get("roles", []))
    except Exception: pass
    user_email = (ui.get("email") or "").strip().lower()
    user_name = ui.get("name") or ui.get("preferred_username") or (user_email.split("@")[0] if user_email else "User")
    pref_username = ui.get("preferred_username") or (user_email.split("@")[0] if user_email else "user")
    if user_email:
        u_row = db().execute("SELECT id FROM app_users WHERE lower(email) = ?", (user_email,)).fetchone()
        if not u_row:
            parts = user_name.strip().split()
            first_name = ui.get("given_name") or (parts[0] if parts else "")
            last_name = ui.get("family_name") or (" ".join(parts[1:]) if len(parts) > 1 else "")
            is_admin_user = user_email in ADMIN_EMAILS or KC_ADMIN_ROLE in roles
            is_pm_user = KC_MANAGER_ROLE in roles
            role_title = "Admin" if is_admin_user else ("Project Manager" if is_pm_user else "Engineer")
            sys_role = "admin" if is_admin_user else ("project-manager" if is_pm_user else "member")
            db().execute("""
                INSERT INTO app_users (username, email, name, first_name, last_name, role_title, system_role, active, current_project_id, password_hash)
                VALUES (?, ?, ?, ?, ?, ?, ?, 1, NULL, 'OIDC_MANAGED')
            """, (pref_username, user_email, user_name, first_name, last_name, role_title, sys_role))
            db().commit()
    session["user"] = {"roles": roles, "email": user_email, "name": user_name, "login": pref_username}
    session["id_token"] = tok.get("id_token")
    session["kc_sub"] = (claims.get("sub") if 'claims' in locals() else None) or ui.get("sub")
    session["kc_sid"] = claims.get("sid") if 'claims' in locals() else tok.get("sid")
    session["login_time"] = datetime.now(TZ).isoformat()
    return redirect(session.pop("next", None) or url_for("entry"))

@app.before_request
def check_session_revocation():
    if request.endpoint in ("static", "login", "auth_callback", "backchannel_logout"):
        return None
    
    user = session.get("user")
    if not user:
        return None
        
    kc_sub = session.get("kc_sub")
    kc_sid = session.get("kc_sid")
    login_time = str(session.get("login_time") or "")
    
    if kc_sub or kc_sid:
        q = """
            SELECT 1 FROM revoked_sessions 
            WHERE (sid = ? AND sid != '') 
               OR (sub = ? AND sub != '' AND revoked_at >= ?)
            LIMIT 1
        """
        rev = db().execute(q, (kc_sid or "", kc_sub or "", login_time)).fetchone()
        if rev:
            app.logger.info("Session revoked via backchannel logout for user %s (sub=%s, sid=%s, login_time=%s). Clearing session.", user.get("email"), kc_sub, kc_sid, login_time)
            session.clear()
            flash("Your session was terminated remotely via Single Sign-Out. Please sign in again.", "warning")
            return redirect(url_for("login", logged_out=1))
            
    now = time.time()
    last_check = session.get("last_safety_check", 0)
    if now - last_check > 300:
        session["last_safety_check"] = now

@app.route("/auth/backchannel-logout", methods=["POST"])
@app.route("/attendance/auth/backchannel-logout", methods=["POST"])
def backchannel_logout():
    app.logger.info("Backchannel logout hit: content_type=%s, form_keys=%s, data=%s",
                    request.content_type, list(request.form.keys()), request.get_data(as_text=True)[:200])
    logout_token = request.form.get("logout_token") or request.values.get("logout_token")
    if not logout_token and request.content_type == "application/json":
        logout_token = (request.get_json(silent=True) or {}).get("logout_token")
    if not logout_token and request.data:
        # Check raw form body parsing
        from urllib.parse import parse_qs
        parsed = parse_qs(request.get_data(as_text=True))
        if "logout_token" in parsed:
            logout_token = parsed["logout_token"][0]
            
    if not logout_token:
        app.logger.warning("Backchannel logout missing logout_token in form/data/json")
        return "Missing logout_token", 400
        
    try:
        import jwt
        from jwt import PyJWKClient
        
        issuer = E("OIDC_ISSUER", "https://pm.keenable.io/auth/realms/keenable").rstrip("/")
        client_id = E("OIDC_CLIENT_ID", "attendance")
        
        jwks_url = f"{issuer}/protocol/openid-connect/certs"
        kc_internal = E("KEYCLOAK_INTERNAL_URL", "").rstrip("/")
        if kc_internal:
            realm = issuer.split("/realms/")[1].split("/")[0] if "/realms/" in issuer else "keenable"
            jwks_url = f"{kc_internal}/realms/{realm}/protocol/openid-connect/certs"
            
        jwks_client = PyJWKClient(jwks_url, timeout=10)
        signing_key = jwks_client.get_signing_key_from_jwt(logout_token)
        
        claims = jwt.decode(
            logout_token,
            signing_key.key,
            algorithms=["RS256", "ES256", "HS256"],
            audience=client_id,
            issuer=issuer,
            options={"verify_sub": False}
        )
        
        events = claims.get("events", {})
        if "http://schemas.openid.net/event/backchannel-logout" not in events:
            app.logger.warning("Backchannel logout token missing logout event claim")
            return "Invalid logout event", 400
            
        if "nonce" in claims:
            app.logger.warning("Backchannel logout token contains forbidden nonce claim")
            return "Forbidden nonce in logout token", 400
            
        sub = claims.get("sub") or ""
        sid = claims.get("sid") or ""
        
        if not sub and not sid:
            return "Missing sub or sid in logout token", 400
            
        now_str = datetime.now(TZ).isoformat()
        db().execute(
            "INSERT INTO revoked_sessions (sub, sid, revoked_at) VALUES (?, ?, ?)",
            (sub, sid, now_str)
        )
        db().commit()
        app.logger.info("Successfully recorded back-channel logout for sub=%s, sid=%s", sub, sid)
        
        res = Flask.response_class("OK", status=200, mimetype="text/plain")
        res.headers["Cache-Control"] = "no-store"
        res.headers["Pragma"] = "no-cache"
        return res
    except Exception as ex:
        app.logger.error("Error processing backchannel logout: %s", ex, exc_info=True)
        return f"Logout token validation failed: {ex}", 400

def sync_keycloak_users():
    """Fetches users from Keycloak realm and syncs name, contact_number, role, and auto-provisions missing ones into app_users."""
    if DEV: return
    issuer = E("OIDC_ISSUER", "").rstrip("/")
    if not issuer or "/realms/" not in issuer: return
    realm = issuer.split("/realms/")[1].split("/")[0]
    kc_base = E("KEYCLOAK_INTERNAL_URL", "http://keycloak:8080/auth").rstrip("/")
    client_id = E("OIDC_CLIENT_ID", "attendance")
    client_secret = E("OIDC_CLIENT_SECRET", "")
    try:
        tok_res = requests.post(
            f"{kc_base}/realms/{realm}/protocol/openid-connect/token",
            data={"grant_type": "client_credentials", "client_id": client_id, "client_secret": client_secret},
            timeout=5
        )
        if tok_res.status_code != 200: return
        token = tok_res.json().get("access_token")
        
        users_res = requests.get(
            f"{kc_base}/admin/realms/{realm}/users",
            headers={"Authorization": f"Bearer {token}"},
            timeout=5
        )
        if users_res.status_code != 200: return
        changed = False
        for u in users_res.json():
            email_val = (u.get("email") or "").strip().lower()
            uname = (u.get("username") or "").strip()
            if not email_val or uname.startswith("service-account-"):
                continue
            
            fn = (u.get("firstName") or "").strip()
            ln = (u.get("lastName") or "").strip()
            full_name = f"{fn} {ln}".strip() or uname
            attrs = u.get("attributes", {})
            phone_val = ""
            if attrs.get("contact_number"):
                phone_val = str(attrs.get("contact_number")[0]).strip()
            elif attrs.get("phone"):
                phone_val = str(attrs.get("phone")[0]).strip()
            
            existing = db().execute("SELECT id, name, phone FROM app_users WHERE lower(email) = ?", (email_val,)).fetchone()
            if not existing:
                is_admin_user = email_val in ADMIN_EMAILS
                role_title = "Admin" if is_admin_user else "Engineer"
                sys_role = "admin" if is_admin_user else "member"
                db().execute("""
                    INSERT INTO app_users (username, email, name, first_name, last_name, phone, role_title, system_role, active, current_project_id, password_hash)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1, NULL, 'OIDC_MANAGED')
                """, (uname, email_val, full_name, fn, ln, phone_val, role_title, sys_role))
                changed = True
            else:
                if (phone_val and existing["phone"] != phone_val) or (full_name and existing["name"] != full_name):
                    db().execute("""
                        UPDATE app_users 
                        SET name=?, first_name=?, last_name=?, phone=coalesce(nullif(?, ''), phone), updated_at=CURRENT_TIMESTAMP 
                        WHERE id=?
                    """, (full_name, fn, ln, phone_val, existing["id"]))
                    changed = True
        if changed:
            db().commit()
    except Exception as ex:
        app.logger.warning("Error syncing Keycloak users: %s", ex)

@app.route("/logout")
def logout():
    id_tok = session.get("id_token")
    session.clear()
    issuer = E("OIDC_ISSUER", "").rstrip("/")
    client_id = E("OIDC_CLIENT_ID", "")
    base_url = BASE_URL or request.host_url.rstrip("/")
    post_logout_redirect_uri = f"{base_url}/login?logged_out=1"
    if issuer and (id_tok or client_id):
        params = {"post_logout_redirect_uri": post_logout_redirect_uri}
        if id_tok:
            params["id_token_hint"] = id_tok
        elif client_id:
            params["client_id"] = client_id
        logout_url = f"{issuer}/protocol/openid-connect/logout?{urlencode(params)}"
        return redirect(logout_url)
    return redirect(url_for("login", logged_out=1))

def keycloak_create_user(email, name):
    """Provisions a new user in Keycloak with a temporary password and forced reset on first login."""
    if not email or DEV:
        return ("skipped", None)
    issuer = E("OIDC_ISSUER", "").rstrip("/")
    if not issuer or "/realms/" not in issuer:
        return ("skipped", None)
    realm = issuer.split("/realms/")[1].split("/")[0]
    kc_base = E("KEYCLOAK_INTERNAL_URL", "http://keycloak:8080/auth").rstrip("/")
    client_id = E("OIDC_CLIENT_ID", "attendance")
    client_secret = E("OIDC_CLIENT_SECRET", "")
    try:
        # 1. Obtain service account token via client_credentials
        tok_res = requests.post(
            f"{kc_base}/realms/{realm}/protocol/openid-connect/token",
            data={
                "grant_type": "client_credentials",
                "client_id": client_id,
                "client_secret": client_secret,
            },
            timeout=10,
        )
        if tok_res.status_code != 200:
            app.logger.error("Keycloak token failed (%s): %s", tok_res.status_code, tok_res.text)
            return ("error", f"Keycloak authentication failed ({tok_res.status_code})")
        token = tok_res.json().get("access_token")

        # 2. Parse name into first_name and last_name (last word is surname)
        parts = (name or "").strip().split()
        if not parts:
            first_name, last_name = "", ""
        elif len(parts) == 1:
            first_name, last_name = parts[0], ""
        else:
            first_name, last_name = " ".join(parts[:-1]), parts[-1]

        temp_pass = E("KEYCLOAK_DEFAULT_TEMP_PASSWORD", "Keenable@2026")

        # 3. Create user in Keycloak with temporary password and required actions (Password reset + OTP setup)
        user_payload = {
            "username": email.lower(),
            "email": email.lower(),
            "firstName": first_name,
            "lastName": last_name,
            "enabled": True,
            "emailVerified": True,
            "requiredActions": ["UPDATE_PASSWORD", "CONFIGURE_TOTP"],
            "credentials": [
                {
                    "type": "password",
                    "value": temp_pass,
                    "temporary": True,
                }
            ],
        }
        create_res = requests.post(
            f"{kc_base}/admin/realms/{realm}/users",
            json=user_payload,
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
            timeout=10,
        )
        if create_res.status_code == 201:
            return ("created", temp_pass)
        elif create_res.status_code == 409:
            return ("already_exists", None)
        else:
            app.logger.error("Keycloak create user failed (%s): %s", create_res.status_code, create_res.text)
            return ("error", f"Keycloak error {create_res.status_code}")
    except Exception as ex:
        app.logger.error("Keycloak provisioning exception: %s", ex)
        return ("error", str(ex))

def keycloak_assign_realm_role(email, role_name):
    """Assigns a realm role directly in Keycloak via Keycloak Admin REST API."""
    if not email or DEV:
        return
    issuer = E("OIDC_ISSUER", "").rstrip("/")
    if not issuer or "/realms/" not in issuer:
        return
    realm = issuer.split("/realms/")[1].split("/")[0]
    kc_base = E("KEYCLOAK_INTERNAL_URL", "http://keycloak:8080/auth").rstrip("/")
    client_id = E("OIDC_CLIENT_ID", "attendance")
    client_secret = E("OIDC_CLIENT_SECRET", "")
    try:
        tok_res = requests.post(
            f"{kc_base}/realms/{realm}/protocol/openid-connect/token",
            data={"grant_type": "client_credentials", "client_id": client_id, "client_secret": client_secret},
            timeout=10,
        )
        if tok_res.status_code != 200:
            return
        token = tok_res.json().get("access_token")
        headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
        
        role_res = requests.get(f"{kc_base}/admin/realms/{realm}/roles/{role_name}", headers=headers, timeout=10)
        if role_res.status_code != 200:
            return
        role_obj = [role_res.json()]
        
        users_res = requests.get(f"{kc_base}/admin/realms/{realm}/users", params={"username": email.lower(), "exact": "true"}, headers=headers, timeout=10)
        if users_res.status_code != 200 or not users_res.json():
            return
        user_id = users_res.json()[0]["id"]
        
        requests.post(f"{kc_base}/admin/realms/{realm}/users/{user_id}/role-mappings/realm", json=role_obj, headers=headers, timeout=10)
    except Exception as ex:
        app.logger.warning("Keycloak role assignment exception for %s: %s", email, ex)

def keycloak_remove_realm_role(email, role_name):
    """Removes a realm role in Keycloak via Keycloak Admin REST API."""
    if not email or DEV:
        return
    issuer = E("OIDC_ISSUER", "").rstrip("/")
    if not issuer or "/realms/" not in issuer:
        return
    realm = issuer.split("/realms/")[1].split("/")[0]
    kc_base = E("KEYCLOAK_INTERNAL_URL", "http://keycloak:8080/auth").rstrip("/")
    client_id = E("OIDC_CLIENT_ID", "attendance")
    client_secret = E("OIDC_CLIENT_SECRET", "")
    try:
        tok_res = requests.post(
            f"{kc_base}/realms/{realm}/protocol/openid-connect/token",
            data={"grant_type": "client_credentials", "client_id": client_id, "client_secret": client_secret},
            timeout=10,
        )
        if tok_res.status_code != 200:
            return
        token = tok_res.json().get("access_token")
        headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
        
        role_res = requests.get(f"{kc_base}/admin/realms/{realm}/roles/{role_name}", headers=headers, timeout=10)
        if role_res.status_code != 200:
            return
        role_obj = [role_res.json()]
        
        users_res = requests.get(f"{kc_base}/admin/realms/{realm}/users", params={"username": email.lower(), "exact": "true"}, headers=headers, timeout=10)
        if users_res.status_code != 200 or not users_res.json():
            return
        user_id = users_res.json()[0]["id"]
        
        requests.delete(f"{kc_base}/admin/realms/{realm}/users/{user_id}/role-mappings/realm", json=role_obj, headers=headers, timeout=10)
    except Exception as ex:
        app.logger.warning("Keycloak role removal exception for %s: %s", email, ex)

def send_welcome_email(to_email, name, role, project_name, temp_password):
    """Formats and dispatches the HTML onboarding email via SMTP."""
    if not to_email:
        return

    smtp_host = E("SMTP_HOST", "smtp.gmail.com")
    smtp_port = int(E("SMTP_PORT", "587"))
    smtp_user = E("SMTP_USER", "")
    smtp_password = E("SMTP_PASSWORD", "")
    smtp_from = E("SMTP_FROM", smtp_user or "oppm@fosteringlinux.com")
    from_name = E("SMTP_DISPLAY_NAME", "Keenable Portal")
    base_url = E("BASE_URL", "https://pm.keenable.io/attendance").rstrip("/")
    portal_url = f"{base_url}/"

    subject = "Welcome to Keenable - Your Account Credentials & Onboarding Instructions"

    plain_text = f"""Hello {name},

Welcome to Keenable! Your account for the Attendance and Project Management portal has been created.

Here are your account details:
--------------------------------------------------
Login / Email:        {to_email}
Portal URL:           {portal_url}
Temporary Password:   {temp_password}
Assigned Project:     {project_name}
Role Title:           {role or 'Software Engineer'}
--------------------------------------------------

First-Time Onboarding Instructions:
1. Navigate to: {portal_url}
2. Sign in with your email and the temporary password above.
3. You will be prompted to update your password to a strong personal password.
4. Set up two-factor authentication (2FA) by scanning the QR code with Google Authenticator or Microsoft Authenticator.

Important Security Notice:
Please keep these credentials safe and do not share this email. You must change your temporary password immediately upon your first sign in.

Best regards,
Keenable Engineering Team
"""

    html_body = f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<style>
  body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; background: #f1f5f9; margin: 0; padding: 24px; color: #1e293b; }}
  .container {{ max-width: 600px; margin: 0 auto; background: #ffffff; border-radius: 8px; border: 1px solid #e2e8f0; overflow: hidden; box-shadow: 0 4px 6px -1px rgba(0,0,0,0.06); }}
  .header {{ background: #0f172a; padding: 24px 32px; color: #ffffff; }}
  .header h1 {{ margin: 0; font-size: 20px; font-weight: 600; letter-spacing: -0.02em; }}
  .header p {{ margin: 6px 0 0; font-size: 13px; color: #94a3b8; }}
  .content {{ padding: 32px; }}
  .greeting {{ font-size: 16px; font-weight: 600; margin-bottom: 12px; }}
  .intro {{ font-size: 14px; line-height: 1.6; color: #475569; margin-bottom: 24px; }}
  .card {{ background: #f8fafc; border: 1px solid #cbd5e1; border-radius: 6px; padding: 20px; margin-bottom: 24px; }}
  .card table {{ width: 100%; border-collapse: collapse; }}
  .card td {{ padding: 6px 0; font-size: 13px; vertical-align: top; }}
  .card td.label {{ width: 140px; color: #64748b; font-weight: 500; }}
  .card td.val {{ color: #0f172a; font-weight: 600; }}
  .card td.pwd {{ font-family: monospace; font-size: 14px; color: #0284c7; background: #e0f2fe; padding: 4px 8px; border-radius: 4px; display: inline-block; }}
  .steps {{ margin: 24px 0; }}
  .steps h3 {{ font-size: 14px; margin: 0 0 12px; color: #0f172a; }}
  .step-item {{ display: flex; gap: 12px; margin-bottom: 10px; font-size: 13px; line-height: 1.5; color: #334155; }}
  .step-num {{ background: #0284c7; color: #ffffff; width: 20px; height: 20px; border-radius: 50%; display: flex; align-items: center; justify-content: center; font-size: 11px; font-weight: bold; flex-shrink: 0; margin-top: 1px; }}
  .btn-wrap {{ text-align: center; margin: 32px 0 16px; }}
  .btn {{ background: #0284c7; color: #ffffff !important; text-decoration: none; padding: 12px 28px; border-radius: 6px; font-size: 14px; font-weight: 600; display: inline-block; }}
  .footer {{ background: #f8fafc; border-top: 1px solid #e2e8f0; padding: 18px 32px; font-size: 12px; color: #94a3b8; line-height: 1.5; }}
  .footer strong {{ color: #64748b; }}
</style>
</head>
<body>
<div class="container">
  <div class="header">
    <h1>Keenable Attendance & Projects</h1>
    <p>Account Provisioning & Onboarding</p>
  </div>
  <div class="content">
    <div class="greeting">Hello {name},</div>
    <div class="intro">Welcome to the team! Your portal account has been created. You can use this account to track your daily attendance, view project assignments, trends, and manage your leaves.</div>

    <div class="card">
      <table>
        <tr><td class="label">Portal URL:</td><td class="val"><a href="{portal_url}" style="color:#0284c7;text-decoration:none;">{portal_url}</a></td></tr>
        <tr><td class="label">Login / Email:</td><td class="val">{to_email}</td></tr>
        <tr><td class="label">Project:</td><td class="val">{project_name}</td></tr>
        <tr><td class="label">Role:</td><td class="val">{role or 'Software Engineer'}</td></tr>
        <tr><td class="label">Temporary Password:</td><td class="val"><span class="pwd">{temp_password}</span></td></tr>
      </table>
    </div>

    <div class="steps">
      <h3>Getting Started:</h3>
      <div class="step-item"><div class="step-num">1</div><div>Click the button below to open the Keenable Portal login page.</div></div>
      <div class="step-item"><div class="step-num">2</div><div>Sign in with your email and the temporary password provided above.</div></div>
      <div class="step-item"><div class="step-num">3</div><div>Set your strong private password when prompted.</div></div>
      <div class="step-item"><div class="step-num">4</div><div>Set up Mobile Authenticator (2FA) by scanning the QR code with Google Authenticator or Microsoft Authenticator.</div></div>
    </div>

    <div class="btn-wrap">
      <a href="{portal_url}" class="btn">Sign In to Keenable Portal</a>
    </div>
  </div>
  <div class="footer">
    <strong>Security Notice:</strong> Please keep this information secure. You will be required to change your temporary password immediately upon your first sign in. If you did not expect this account, please contact your administrator.
  </div>
</div>
</body>
</html>
"""

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = f"{from_name} <{smtp_from}>"
    msg["To"] = to_email
    msg.attach(MIMEText(plain_text, "plain", "utf-8"))
    msg.attach(MIMEText(html_body, "html", "utf-8"))

    try:
        with smtplib.SMTP(smtp_host, smtp_port, timeout=20) as server:
            server.starttls(context=ssl.create_default_context())
            if smtp_user and smtp_password:
                server.login(smtp_user, smtp_password)
            server.sendmail(smtp_from, [to_email], msg.as_string())
        app.logger.info("Welcome onboarding email sent to %s", to_email)
    except Exception as ex:
        app.logger.error("Failed to send welcome email to %s: %s", to_email, ex)

def send_welcome_email_async(to_email, name, role, project_name, temp_password):
    """Dispatches the welcome email asynchronously in a non-blocking daemon thread."""
    if not to_email:
        return
    t = threading.Thread(
        target=send_welcome_email,
        args=(to_email, name, role, project_name, temp_password),
        daemon=True,
    )
    t.start()

@app.before_request
def csrf():
    if request.endpoint == "backchannel_logout" or (request.endpoint or "").startswith("m_") or (request.path or "").startswith("/api/m/"):
        return None
    if "csrf" not in session: session["csrf"] = secrets.token_hex(16)
    if request.method == "POST" and request.form.get("csrf") != session["csrf"]: abort(400, "Bad form token")

# ---------------------------------------------------------------- attendance logic
def mins(t):
    try: h, m = t.split(":"); return int(h) * 60 + int(m)
    except Exception: return None

def hm(m):
    return "" if m is None else f"{m // 60}:{m % 60:02d}"

def shift_of(rec):
    """Shift start (minutes) that applied to this record: the engineer's own shift saved with it, else the default."""
    own = rec["shift_start"] if "shift_start" in rec.keys() else ""
    m = mins(own or "")
    return m if m is not None else mins(SHIFT_START)

def is_night(start_min): return start_min + SHIFT_MIN > 1440     # the shift runs past midnight

def evaluate(rec):
    """rec: dict/Row or None -> status + late/short figures (minutes)."""
    out = {"status": "Absent", "duty_status": "Present", "late_by": None, "worked": None, "short_by": None, "dev": None}
    if not rec: return out
    if rec["leave_type"]: out["status"] = "On Leave"; return out
    i, o = mins(rec["in_time"] or ""), mins(rec["out_time"] or "")
    if i is None: return out
    ds = (rec["duty_status"] if "duty_status" in rec.keys() else "") or "Present"
    out["status"] = "Present"
    out["duty_status"] = ds
    st = shift_of(rec); night = is_night(st)
    arrived = i + 1440 if night and i < st - 720 else i          # night shift, arrived after midnight
    out["dev"] = arrived - st                                     # minutes after (+) or before (-) own shift start
    if arrived > st + GRACE_MIN: out["late_by"] = arrived - st
    if o is not None and o < i and night: o += 1440              # night shift ends the next morning
    if o is not None and o >= i:
        out["worked"] = o - i
        req_min = (SHIFT_MIN // 2) if ds == "Half Day" else SHIFT_MIN
        if out["worked"] < req_min: out["short_by"] = req_min - out["worked"]
    return out

def records(day):
    return {r["user_id"]: dict(r) for r in db().execute("SELECT * FROM attendance WHERE day=?", (day,))}

def build_summary(day, with_tasks=True, pids=None, user_id=None):
    if "mobile_refresh" in globals():
        try: mobile_refresh(day)
        except Exception: pass
    ros, recs = roster(pids), records(day)
    entered = entered_checker()
    s = {"day": day, "absent": [], "leave": [], "late": [], "short": [], "unentered": [], "present_list": [], "total": 0, "present": 0}
    for uid, m in sorted(ros.items(), key=lambda kv: (0 if ('manager' in (kv[1].get('role', '') or '').lower() or 'lead' in (kv[1].get('role', '') or '').lower()) else 1, kv[1]["name"].lower())):
        if user_id:
            if isinstance(user_id, (list, set, tuple)):
                if uid not in user_id: continue
            elif uid != user_id:
                continue
        if not is_assigned_on(m.get("assignments", []), day):
            continue
        s["total"] += 1
        rec = recs.get(uid); ev = evaluate(rec)
        row = {"name": m["name"], "projects": ", ".join(m["projects"]), "uid": uid, **(rec or {}), **ev,
               "late_hm": hm(ev["late_by"]), "worked_hm": hm(ev["worked"]), "short_hm": hm(ev["short_by"])}
        if rec:
            if ev["status"] == "Absent": s["absent"].append(row)
            elif ev["status"] == "On Leave":
                row["tasks"] = open_tasks(m["op_uid"]) if with_tasks else []
                s["leave"].append(row)
            else:
                s["present"] += 1
                s["present_list"].append(row)
                if ev["late_by"] is not None: s["late"].append(row)
                if ev["short_by"] is not None: s["short"].append(row)
        else:
            if entered(uid, recs):
                s["absent"].append(row)
            else:
                s["unentered"].append(row)
    return s

def today(): return datetime.now(TZ).date().isoformat()

def off_days(uid):
    """Weekly-off weekdays ('mon'..'sun') of one team member: their own setting, else the project's default, else the site-wide WEEKLY_OFF."""
    c = getattr(g, "_offs", None) if has_request_context() else None
    if c is None:
        c = {}
        try:
            for r in db().execute("SELECT t.member_id, t.weekly_off AS own, pi.weekly_off AS dflt FROM team t LEFT JOIN project_info pi ON pi.project_id=t.project_id"):
                v = {x.strip().lower()[:3] for x in (r["own"] or r["dflt"] or "").split(",") if x.strip()}
                if v and r["member_id"] not in c: c[r["member_id"]] = v
        except Exception:
            try: db().rollback()
            except Exception: pass
        if has_request_context():
            g._offs = c
    return c.get(uid) or WEEKLY_OFF

def get_day():
    d = request.values.get("date") or today()
    try: date.fromisoformat(d)
    except ValueError: abort(400, "Bad date")
    return d

# ---------------------------------------------------------------- pages
@app.context_processor
def inject():
    n = 0
    leave_p = 0
    try:
        if current_user() and my_role() in ("admin", "lead", "manager"):
            if is_admin():
                n = db().execute("SELECT count(*) AS n FROM approval WHERE status IN ('pending','escalated')").fetchone()["n"]
                leave_p = db().execute("SELECT count(*) AS n FROM leave_request WHERE status='pending'").fetchone()["n"]
            else:
                n = db().execute("SELECT count(*) AS n FROM approval WHERE status='pending' AND lower(assigned_to)=?", (email(),)).fetchone()["n"]
                leave_p = db().execute("SELECT count(*) AS n FROM leave_request WHERE status='pending' AND lower(assigned_to)=?", (email(),)).fetchone()["n"]
    except Exception: pass
    return {"user": current_user(), "csrf": session.get("csrf", ""), "op_url": OP_URL, "role": my_role(), "dev": DEV, "is_member": bool(current_user() and my_member_ids()),
            "pat": {"name": r"[\p{L}][\p{L}\p{M} .'\-]{1,99}", "role": r"[\p{L}][\p{L}\p{M}0-9 .&\/\(\)+\-]{1,59}",
                    "phone": r"(\+?91[ \-]?|0)?[6-9][0-9]{4}[ \-]?[0-9]{5}", "project": r"[\p{L}0-9][\p{L}\p{M}0-9 .&\/\(\)+,:_\-]{1,79}"},
            "shift_start": SHIFT_START, "grace": GRACE_MIN, "shift_hours": SHIFT_MIN / 60, "is_admin": is_admin(), "today": today(),
            "wf_pending": n, "wf_leave_pending": leave_p}

@app.route("/healthz")
def healthz(): return "ok"

@app.route("/")
@login_required
def entry():
    day, ps = get_day(), shown_projects()
    if not ps: return redirect(url_for("projects_page"))
    pid = request.args.get("project") or ps[0]["id"]
    if pid not in [p["id"] for p in ps]: ps = my_projects()
    all_m = members(pid)
    if not all_m and can_edit(pid): flash("This project has no team yet - add engineers under My team.", "err")
    recs = records(day)
    ms = [m for m in all_m if recs.get(m["id"]) or is_assigned_on([{"from": m.get("assigned_from"), "to": m.get("assigned_to")}], day)]
    rows = [{"m": m, "r": recs.get(m["id"], {}), "ev": evaluate(recs.get(m["id"]))} for m in ms]
    for r in rows:
        r["late_hm"], r["worked_hm"], r["short_hm"] = hm(r["ev"]["late_by"]), hm(r["ev"]["worked"]), hm(r["ev"]["short_by"])
    here = {m["id"] for m in ms}
    away = sorted({r["user_name"] for u, r in recs.items() if u not in here and r["leave_type"]})   # on leave, entered in another tab
    editable = can_edit_attendance(pid, day)
    past_locked = (day < today()) and not is_admin() and can_edit(pid)
    upcoming_leaves = get_upcoming_leaves(pid)
    pending_count = sum(1 for r in rows if r["r"] and (r["r"].get("approval_status") or "Approved") == "Pending")
    pending_by_proj = {}
    for p in ps:
        p_uids = {m["id"] for m in members(p["id"]) if recs.get(m["id"]) or is_assigned_on([{"from": m.get("assigned_from"), "to": m.get("assigned_to")}], day)}
        c_pend = sum(1 for uid in p_uids if recs.get(uid) and (recs[uid].get("approval_status") or "Approved") == "Pending")
        if c_pend:
            pending_by_proj[p["id"]] = c_pend
    return render_template("entry.html", day=day, projects=ps, pid=pid, rows=rows, members=ms, covers=cover_choices(pid), away=away,
                           leave_types=LEAVE_TYPES, editable=editable, past_locked=past_locked, can_edit_proj=(is_admin() or can_edit(pid)), is_admin=is_admin(),
                           upcoming_leaves=upcoming_leaves, pending_count=pending_count, pending_by_proj=pending_by_proj)

def get_upcoming_leaves(pid):
    """Return active/upcoming planned leaves for members of project `pid` starting from today."""
    ms = members(pid)
    if not ms: return []
    uids = [m["id"] for m in ms]
    m_map = {m["id"]: m for m in ms}
    placeholders = ",".join("?" for _ in uids)
    rows = db().execute(f"""
        SELECT day, user_id, user_name, leave_type, planned, handled_by, remarks, in_time
        FROM attendance
        WHERE day >= ? AND user_id IN ({placeholders}) AND leave_type != ''
        ORDER BY user_id, day ASC
    """, [today()] + uids).fetchall()

    leaves = []
    current_span = None

    for r in rows:
        d = date.fromisoformat(r["day"])
        u = r["user_id"]
        lt = r["leave_type"]
        cov = r["handled_by"] or ""
        rem = r["remarks"] or ""
        pl = r["planned"] or "Planned"

        can_merge = False
        if current_span and current_span["user_id"] == u and current_span["leave_type"] == lt and current_span["handled_by"] == cov:
            last_d = date.fromisoformat(current_span["to_date"])
            gap = (d - last_d).days
            if gap == 1:
                can_merge = True
            elif gap <= 3:
                all_weekends = True
                chk = last_d + timedelta(days=1)
                while chk < d:
                    if chk.strftime("%a").lower() not in off_days(u):
                        all_weekends = False
                        break
                    chk += timedelta(days=1)
                if all_weekends:
                    can_merge = True

        if can_merge:
            current_span["to_date"] = r["day"]
            current_span["days"].append(r["day"])
            current_span["working_days"] += 1
            if rem and rem not in current_span["remarks"]:
                current_span["remarks"] = (current_span["remarks"] + " | " + rem).strip(" | ")
        else:
            if current_span:
                leaves.append(current_span)
            current_span = {
                "user_id": u,
                "user_name": r["user_name"],
                "role": m_map.get(u, {}).get("role", ""),
                "from_date": r["day"],
                "to_date": r["day"],
                "leave_type": lt,
                "planned": pl,
                "handled_by": cov,
                "remarks": rem,
                "working_days": 1,
                "days": [r["day"]]
            }
    if current_span:
        leaves.append(current_span)

    leaves.sort(key=lambda x: (x["from_date"], x["user_name"]))
    return leaves

def cover_choices(pid):
    """Who may be picked under "Task handled by": engineers of this project, its main project and its sibling sub-projects."""
    p = proj(pid); root = (p["parent"] or p["id"]) if p else str(pid); seen, out = set(), []
    for q in [x for x in projects() if x["id"] == str(pid)] + [x for x in projects() if x["id"] != str(pid) and (x["id"] == root or x["parent"] == root)]:
        for m in team(q["id"]):
            if m["name"] not in seen: seen.add(m["name"]); out.append(m)
    return out

@app.route("/save", methods=["POST"])
@login_required
def save():
    day, pid = get_day(), request.form.get("project", "")
    if not can_edit(pid): abort(403, "Only the project lead or an admin can enter attendance.")
    if not can_edit_attendance(pid, day):
        flash("Attendance for previous dates is locked. Only administrators can enter or modify attendance for past dates.", "err")
        return redirect(url_for("entry", date=day, project=pid))
    f, who, n, errs, warns = request.form, (current_user() or {}).get("email", ""), 0, [], []
    ms, stored = members(pid), records(day)
    ms = [m for m in ms if stored.get(m["id"]) or is_assigned_on([{"from": m.get("assigned_from"), "to": m.get("assigned_to")}], day)]
    here = {m["id"] for m in ms}
    leave_now = {m["name"] for m in ms if (f.get(f"leave_{m['id']}") or "").strip() in LEAVE_TYPES}          # on leave in this form
    on_leave = leave_now | {r["user_name"] for u, r in stored.items() if u not in here and r["leave_type"]}  # plus those saved in other tabs
    allowed_cover = {m["name"] for m in cover_choices(pid)}
    approved_n = 0
    now_iso = datetime.now(TZ).isoformat(timespec="seconds")
    for m in ms:
        u = m["id"]; g_ = lambda k: (f.get(f"{k}_{u}") or "").strip()
        i, o, lt, pl, cov, rem = g_("in"), g_("out"), g_("leave"), g_("planned"), g_("cover"), g_("remarks")
        if (i and mins(i) is None) or (o and mins(o) is None): errs.append(f"{m['name']}: time not understood"); continue
        if o and not i: errs.append(f"{m['name']}: out time given without in time"); continue
        own = mins(m["shift"]) if m["shift"] else mins(SHIFT_START)
        if i and o and mins(o) < mins(i) and not is_night(own): errs.append(f"{m['name']}: out time is before in time"); continue
        if lt and lt not in LEAVE_TYPES: continue
        if not lt: pl, cov = "", ""
        if cov and cov in on_leave:
            warns.append(f"{cov} is also on leave on this date, so cannot handle {m['name']}'s tasks. The leave is saved without a cover person - choose someone else."); cov = ""
        elif cov and cov not in allowed_cover and cov != (stored.get(u) or {}).get("handled_by"):
            cov = ""
        if pl not in ("", "Planned", "Unplanned"): pl = ""
        if not any([i, o, lt, rem]):
            db().execute("DELETE FROM attendance WHERE day=? AND user_id=?", (day, u)); continue
        was_pending = (stored.get(u) or {}).get("approval_status") == "Pending"
        if was_pending:
            approved_n += 1
        db().execute("""INSERT INTO attendance(day,user_id,user_name,in_time,out_time,leave_type,planned,handled_by,remarks,updated_by,updated_at,shift_start,approval_status,rejection_reason,approved_by,approved_at)
            VALUES(?,?,?,?,?,?,?,?,?,?,?,?,'Approved','',?,?) ON CONFLICT(day,user_id) DO UPDATE SET user_name=excluded.user_name,in_time=excluded.in_time,shift_start=excluded.shift_start,
            out_time=excluded.out_time,leave_type=excluded.leave_type,planned=excluded.planned,handled_by=excluded.handled_by,
            remarks=excluded.remarks,updated_by=excluded.updated_by,updated_at=excluded.updated_at,
            approval_status='Approved',rejection_reason='',approved_by=excluded.approved_by,approved_at=excluded.approved_at""",
            (day, u, m["name"], i, o, lt, pl, cov, rem, who, now_iso, m["shift"] or SHIFT_START, who, now_iso))
        n += 1
    for u, r in stored.items():      # someone in another tab was relying on a person who is now on leave
        if u not in here and r["handled_by"] and r["handled_by"] in leave_now:
            db().execute("UPDATE attendance SET handled_by='' WHERE day=? AND user_id=?", (day, u))
            warns.append(f"{r['handled_by']} is now on leave, so was removed as the cover person for {r['user_name']}. Choose someone else for {r['user_name']}.")
    db().commit()
    msg = f"Saved {n} entr{'y' if n == 1 else 'ies'}."
    if approved_n:
        msg += f" ({approved_n} engineer self-entr{'y' if approved_n == 1 else 'ies'} verified & approved.)"
    flash(msg, "ok")
    for w in warns: flash(w, "err")
    for e in errs: flash("Not saved - " + e, "err")
    return redirect(url_for("entry", date=day, project=pid))

@app.route("/attendance/approve", methods=["POST"])
@login_required
def approve_attendance():
    day, pid = get_day(), (request.form.get("project") or "").strip()
    if not can_edit(pid):
        abort(403, "Only the active PM / Team Lead or an administrator can approve attendance.")
    if not can_edit_attendance(pid, day):
        flash("Same-day approval rule: Attendance for previous dates is locked for PM/TL. Contact an administrator.", "err")
        return redirect(url_for("entry", date=day, project=pid))

    mode = (request.form.get("mode") or "single").strip()
    target_uid = (request.form.get("user_id") or "").strip()
    f = request.form
    who = email()
    now_iso = datetime.now(TZ).isoformat(timespec="seconds")

    ms, stored = members(pid), records(day)
    ms_map = {m["id"]: m for m in ms}
    allowed_cover = {m["name"] for m in cover_choices(pid)}

    if mode == "all":
        targets = [u for u in ms_map if stored.get(u) and (stored[u].get("approval_status") or "Approved") == "Pending"]
    else:
        targets = [target_uid] if (target_uid and target_uid in ms_map and stored.get(target_uid)) else []

    if not targets:
        flash("No pending attendance submissions found to approve.", "err")
        return redirect(url_for("entry", date=day, project=pid))

    approved_names = []
    errs = []
    for u in targets:
        m = ms_map[u]
        ex = stored[u]
        # Allow PM/TL to adjust row inputs inline before clicking Approve
        i = (f.get(f"in_{u}") if f"in_{u}" in f else ex.get("in_time") or "").strip()
        o = (f.get(f"out_{u}") if f"out_{u}" in f else ex.get("out_time") or "").strip()
        lt = (f.get(f"leave_{u}") if f"leave_{u}" in f else ex.get("leave_type") or "").strip()
        pl = (f.get(f"planned_{u}") if f"planned_{u}" in f else ex.get("planned") or "").strip()
        cov = (f.get(f"cover_{u}") if f"cover_{u}" in f else ex.get("handled_by") or "").strip()
        rem = (f.get(f"remarks_{u}") if f"remarks_{u}" in f else ex.get("remarks") or "").strip()

        if (i and mins(i) is None) or (o and mins(o) is None):
            errs.append(f"{m['name']}: invalid time format"); continue
        if o and not i:
            errs.append(f"{m['name']}: out time given without in time"); continue
        own = mins(m["shift"]) if m["shift"] else mins(SHIFT_START)
        if i and o and mins(o) < mins(i) and not is_night(own):
            errs.append(f"{m['name']}: out time is before in time"); continue
        if lt and lt not in LEAVE_TYPES:
            lt = ex.get("leave_type") or ""
        if not lt:
            pl, cov = "", ""
        elif pl not in ("Planned", "Unplanned"):
            pl = ex.get("planned") or "Unplanned"
        if cov and cov not in allowed_cover and cov != (ex.get("handled_by") or ""):
            cov = ""

        db().execute("""
            UPDATE attendance
            SET in_time=?, out_time=?, leave_type=?, planned=?, handled_by=?, remarks=?,
                approval_status='Approved', rejection_reason='', approved_by=?, approved_at=?, updated_by=?, updated_at=?
            WHERE day=? AND user_id=?
        """, (i, o, lt, pl, cov, rem, who, now_iso, who, now_iso, day, u))
        approved_names.append(m["name"])

    db().commit()
    if approved_names:
        if len(approved_names) == 1:
            flash(f"Approved today's attendance for {approved_names[0]}.", "ok")
        else:
            flash(f"Approved {len(approved_names)} attendance submissions ({', '.join(approved_names)}).", "ok")
    for e in errs:
        flash("Not approved - " + e, "err")
    return redirect(url_for("entry", date=day, project=pid))

@app.route("/attendance/reject", methods=["POST"])
@login_required
def reject_attendance():
    day, pid = get_day(), (request.form.get("project") or "").strip()
    if not can_edit(pid):
        abort(403, "Only the active PM / Team Lead or an administrator can reject attendance.")
    if not can_edit_attendance(pid, day):
        flash("Same-day approval rule: Attendance for previous dates is locked for PM/TL. Contact an administrator.", "err")
        return redirect(url_for("entry", date=day, project=pid))

    target_uid = (request.form.get("user_id") or "").strip()
    reason = (request.form.get("reason") or "").strip()[:300]
    if not reason:
        flash("Please provide a rejection remark / reason so the engineer knows what to correct.", "err")
        return redirect(url_for("entry", date=day, project=pid))

    ms = members(pid)
    ms_map = {m["id"]: m for m in ms}
    if not (target_uid and target_uid in ms_map):
        flash("Team member not found in this project.", "err")
        return redirect(url_for("entry", date=day, project=pid))

    who = email()
    now_iso = datetime.now(TZ).isoformat(timespec="seconds")
    m = ms_map[target_uid]

    db().execute("""
        UPDATE attendance
        SET approval_status='Rejected', rejection_reason=?, approved_by=?, approved_at=?, updated_by=?, updated_at=?
        WHERE day=? AND user_id=?
    """, (reason, who, now_iso, who, now_iso, day, target_uid))
    db().commit()

    flash(f"Rejected attendance for {m['name']} (Reason: '{reason}'). The engineer can now review, correct, and resubmit.", "ok")
    return redirect(url_for("entry", date=day, project=pid))

@app.route("/leave/apply_advance", methods=["POST"])
@login_required
def leave_apply_advance():
    f = request.form
    pid = f.get("project", "").strip()
    if not (is_admin() or can_edit(pid)): abort(403, "Only the project lead or an admin can apply advance leave.")

    next_url = f.get("next", "").strip()
    back_url = next_url if (next_url and next_url.startswith("/")) else url_for("entry", project=pid)

    uid = f.get("user_id", "").strip()
    from_date = f.get("from_date", "").strip()
    to_date = f.get("to_date", "").strip()
    lt = f.get("leave_type", "").strip()
    pl = f.get("planned", "Planned").strip() or "Planned"
    cov = f.get("cover", "").strip()
    rem = f.get("remarks", "").strip()
    skip_weekends = bool(f.get("skip_weekends"))

    if not uid or not from_date or not to_date:
        flash("Please choose the team member and provide both From and To dates.", "err")
        return redirect(back_url)

    try:
        from_d = date.fromisoformat(from_date)
        to_d = date.fromisoformat(to_date)
    except ValueError:
        flash("Invalid date format provided.", "err")
        return redirect(back_url)

    if from_d > to_d:
        flash("From Date must be before or equal to To Date.", "err")
        return redirect(back_url)

    if (to_d - from_d).days > 60:
        flash("Advance leave range cannot exceed 60 days.", "err")
        return redirect(back_url)

    td = date.fromisoformat(today())
    if from_d < td and not is_admin():
        flash("Attendance for previous dates is locked. Only administrators can enter or modify attendance for past dates.", "err")
        return redirect(back_url)

    ms = members(pid)
    target_m = next((m for m in ms if m["id"] == uid), None)
    if not target_m:
        flash("Selected team member not found in this project.", "err")
        return redirect(back_url)

    if lt not in LEAVE_TYPES:
        flash("Please select a valid leave type.", "err")
        return redirect(back_url)

    allowed_cover = {m["name"] for m in cover_choices(pid)}
    if cov and cov not in allowed_cover:
        cov = ""

    who = (current_user() or {}).get("email", "")
    applied_count = 0
    cur_d = from_d
    shift = target_m["shift"] or SHIFT_START

    while cur_d <= to_d:
        ds = cur_d.isoformat()
        is_off = cur_d.strftime("%a").lower() in off_days(uid)
        if not (skip_weekends and is_off):
            db().execute("""INSERT INTO attendance(day,user_id,user_name,in_time,out_time,leave_type,planned,handled_by,remarks,updated_by,updated_at,shift_start)
                VALUES(?,?,?,'','',?,?,?,?,?,?,?)
                ON CONFLICT(day,user_id) DO UPDATE SET
                    user_name=excluded.user_name,
                    in_time='',
                    out_time='',
                    leave_type=excluded.leave_type,
                    planned=excluded.planned,
                    handled_by=excluded.handled_by,
                    remarks=excluded.remarks,
                    updated_by=excluded.updated_by,
                    updated_at=excluded.updated_at,
                    shift_start=excluded.shift_start""",
                (ds, uid, target_m["name"], lt, pl, cov, rem, who, datetime.now(TZ).isoformat(timespec="seconds"), shift))
            applied_count += 1
        cur_d += timedelta(days=1)

    db().commit()
    flash(f"Successfully applied {pl} ({lt}) for {target_m['name']} across {applied_count} day{'s' if applied_count != 1 else ''} ({from_date} to {to_date}).", "ok")
    if next_url and next_url.startswith("/"):
        return redirect(next_url)
    return redirect(url_for("entry", date=from_date, project=pid))

@app.route("/leave/cancel", methods=["POST"])
@login_required
def leave_cancel():
    f = request.form
    pid = f.get("project", "").strip()
    if not (is_admin() or can_edit(pid)):
        abort(403, "Only the project lead or an admin can cancel leaves.")

    next_url = f.get("next", "").strip()
    back_url = next_url if (next_url and next_url.startswith("/")) else url_for("entry", project=pid)

    uid = f.get("user_id", "").strip()
    from_date = f.get("from_date", "").strip()
    to_date = f.get("to_date", "").strip()

    if not uid or not from_date or not to_date:
        flash("Invalid cancellation parameters provided.", "err")
        return redirect(back_url)

    try:
        from_d = date.fromisoformat(from_date)
        to_d = date.fromisoformat(to_date)
    except ValueError:
        flash("Invalid date format provided.", "err")
        return redirect(back_url)

    td = date.fromisoformat(today())
    if from_d < td and not is_admin():
        flash("Attendance for previous dates is locked. Only administrators can modify or cancel past leaves.", "err")
        return redirect(back_url)

    cur = db().execute("""
        DELETE FROM attendance
        WHERE user_id = ? AND day >= ? AND day <= ? AND leave_type != '' AND (in_time IS NULL OR in_time = '')
    """, (uid, from_date, to_date))
    deleted_count = cur.rowcount
    db().commit()

    flash(f"Cancelled planned leave across {deleted_count} day{'s' if deleted_count != 1 else ''} ({from_date} to {to_date}).", "ok")
    return redirect(back_url)

@app.route("/leave/modify", methods=["POST"])
@login_required
def leave_modify():
    f = request.form
    pid = f.get("project", "").strip()
    if not (is_admin() or can_edit(pid)):
        abort(403, "Only the project lead or an admin can modify leaves.")

    next_url = f.get("next", "").strip()
    back_url = next_url if (next_url and next_url.startswith("/")) else url_for("entry", project=pid)

    uid = f.get("user_id", "").strip()
    old_from = f.get("old_from_date", "").strip()
    old_to = f.get("old_to_date", "").strip()
    new_from = f.get("from_date", "").strip()
    new_to = f.get("to_date", "").strip()
    lt = f.get("leave_type", "").strip()
    pl = f.get("planned", "Planned").strip() or "Planned"
    cov = f.get("cover", "").strip()
    rem = f.get("remarks", "").strip()
    skip_weekends = bool(f.get("skip_weekends"))

    if not uid or not new_from or not new_to:
        flash("Please provide both From and To dates.", "err")
        return redirect(back_url)

    try:
        new_from_d = date.fromisoformat(new_from)
        new_to_d = date.fromisoformat(new_to)
    except ValueError:
        flash("Invalid date format provided.", "err")
        return redirect(back_url)

    if new_from_d > new_to_d:
        flash("From Date must be before or equal to To Date.", "err")
        return redirect(back_url)

    if (new_to_d - new_from_d).days > 60:
        flash("Leave range cannot exceed 60 days.", "err")
        return redirect(back_url)

    td = date.fromisoformat(today())
    if new_from_d < td and not is_admin():
        flash("Attendance for previous dates is locked. Only administrators can enter or modify attendance for past dates.", "err")
        return redirect(back_url)

    ms = members(pid)
    target_m = next((m for m in ms if m["id"] == uid), None)
    if not target_m:
        flash("Selected team member not found in this project.", "err")
        return redirect(back_url)

    if lt not in LEAVE_TYPES:
        flash("Please select a valid leave type.", "err")
        return redirect(back_url)

    allowed_cover = {m["name"] for m in cover_choices(pid)}
    if cov and cov not in allowed_cover:
        cov = ""

    # Atomic clear of previous date span (unworked records only)
    if old_from and old_to:
        try:
            old_from_d = date.fromisoformat(old_from)
            if old_from_d >= td or is_admin():
                db().execute("""
                    DELETE FROM attendance
                    WHERE user_id = ? AND day >= ? AND day <= ? AND leave_type != '' AND (in_time IS NULL OR in_time = '')
                """, (uid, old_from, old_to))
        except ValueError:
            pass

    who = (current_user() or {}).get("email", "")
    applied_count = 0
    cur_d = new_from_d
    shift = target_m["shift"] or SHIFT_START

    while cur_d <= new_to_d:
        ds = cur_d.isoformat()
        is_off = cur_d.strftime("%a").lower() in off_days(uid)
        if not (skip_weekends and is_off):
            db().execute("""INSERT INTO attendance(day,user_id,user_name,in_time,out_time,leave_type,planned,handled_by,remarks,updated_by,updated_at,shift_start)
                VALUES(?,?,?,'','',?,?,?,?,?,?,?)
                ON CONFLICT(day,user_id) DO UPDATE SET
                    user_name=excluded.user_name,
                    in_time='',
                    out_time='',
                    leave_type=excluded.leave_type,
                    planned=excluded.planned,
                    handled_by=excluded.handled_by,
                    remarks=excluded.remarks,
                    updated_by=excluded.updated_by,
                    updated_at=excluded.updated_at,
                    shift_start=excluded.shift_start""",
                (ds, uid, target_m["name"], lt, pl, cov, rem, who, datetime.now(TZ).isoformat(timespec="seconds"), shift))
            applied_count += 1
        cur_d += timedelta(days=1)

    db().commit()
    flash(f"Updated planned leave for {target_m['name']} to {new_from} → {new_to} ({applied_count} working day{'s' if applied_count != 1 else ''}).", "ok")
    return redirect(back_url)

@app.route("/summary")
@login_required
def summary():
    day = get_day(); pids, pid = pick_pids()
    is_eng = my_role() == "engineer"
    target_uid = request.args.get("user", "").strip()
    if is_eng:
        mids = my_member_ids()
        target_uid = mids[0] if mids else ""
        eng_pids = [str(r["project_id"]) for r in db().execute("SELECT project_id FROM team WHERE lower(email)=?", (email(),))]
        pids = eng_pids if eng_pids else pids

    ros = roster(pids)
    users_list = []
    if not is_eng:
        for uid, m in sorted(ros.items(), key=lambda kv: (0 if ('manager' in (kv[1].get('role', '') or '').lower() or 'lead' in (kv[1].get('role', '') or '').lower()) else 1, kv[1]["name"].lower())):
            role_tag = f" [{m['role']}]" if m.get("role") else ""
            users_list.append({"id": uid, "name": m["name"] + role_tag, "projects": ", ".join(m["projects"])})

    s_data = build_summary(day, pids=pids, user_id=mids if is_eng else (target_uid or None))
    return render_template("summary.html", s=s_data, day=day, month=day[:7], projects=my_projects(), pid=pid,
                           users=users_list, target_uid=target_uid, is_engineer=is_eng,
                           mail_ready=bool(SUMMARY_TO and E("SMTP_HOST")))

@app.route("/summary/send", methods=["POST"])
@login_required
def summary_send():
    if not is_admin(): abort(403)
    day = get_day()
    try: send_summary(day); flash("Summary emailed to " + ", ".join(SUMMARY_TO), "ok")
    except Exception as ex: flash(f"Email failed: {ex}", "err")
    return redirect(url_for("summary", date=day))

# ---------------------------------------------------------------- projects and access
def _sync_lead_as_member(pid, em, name=None):
    """Ensures a project lead (PM/TL) is present as an active member in the project team table."""
    em = (em or "").strip().lower()
    if not em or not pid: return
    u = db().execute("SELECT * FROM app_users WHERE lower(email)=?", (em,)).fetchone()
    phone = u["phone"] if u and u["phone"] else ""
    shift = u["current_shift_start"] if u and u["current_shift_start"] else SHIFT_START
    full_name = name or (u["name"] if u and u["name"] else em.split("@")[0].replace(".", " ").title())
    user_id = u["id"] if u else None

    tm = db().execute("SELECT member_id, active, role FROM team WHERE project_id=? AND (lower(email)=? OR (user_id IS NOT NULL AND user_id=?))",
                      (str(pid), em, user_id or -1)).fetchone()
    if tm:
        db().execute("""
            UPDATE team
            SET active=1,
                name=coalesce(nullif(name, ''), ?),
                role=case when role in ('', 'Developer', 'Engineer') then 'Project Manager' else role end,
                email=coalesce(nullif(email, ''), ?),
                user_id=coalesce(user_id, ?),
                assigned_to=NULL,
                updated_by=?, updated_at=?
            WHERE project_id=? AND member_id=?
        """, (full_name, em, user_id, *_stamp(), str(pid), tm["member_id"]))
    else:
        mid = "m:" + secrets.token_hex(6)
        db().execute("""
            INSERT INTO team(project_id, member_id, name, role, phone, email, shift_start, active, user_id, assigned_from, updated_by, updated_at)
            VALUES(?, ?, ?, 'Project Manager', ?, ?, ?, 1, ?, CURRENT_TIMESTAMP, ?, ?)
        """, (str(pid), mid, full_name, phone, em, shift, user_id, *_stamp()))
    db().execute("UPDATE app_users SET system_role='project-manager', updated_at=CURRENT_TIMESTAMP WHERE lower(email)=? AND system_role!='admin'", (em,))
    keycloak_assign_realm_role(em, "project-manager")

def _set_leads(pid, emails):
    old_leads = [r["email"].lower() for r in db().execute("SELECT email FROM project_access WHERE project_id=? AND kind='lead'", (str(pid),))]
    new_emails = [e.strip().lower() for e in emails if e.strip()]

    # Deactivate team membership for leads removed from this project
    removed = set(old_leads) - set(new_emails)
    for rem in removed:
        db().execute("UPDATE team SET active=0, assigned_to=CURRENT_TIMESTAMP, updated_by=?, updated_at=? WHERE project_id=? AND lower(email)=? AND (lower(role) LIKE '%manager%' OR lower(role) LIKE '%lead%')",
                     (*_stamp(), str(pid), rem))
        other_leads = db().execute("SELECT count(*) as cnt FROM project_access WHERE lower(email)=? AND project_id!=? AND kind IN ('lead', 'pm')", (rem, str(pid))).fetchone()
        if not other_leads or other_leads["cnt"] == 0:
            db().execute("DELETE FROM access WHERE lower(email)=? AND role='lead'", (rem.lower(),))
            db().execute("UPDATE app_users SET system_role='member', updated_at=CURRENT_TIMESTAMP WHERE lower(email)=? AND system_role='project-manager'", (rem,))
            keycloak_remove_realm_role(rem, "project-manager")

    db().execute("DELETE FROM project_access WHERE project_id=? AND kind='lead'", (str(pid),))
    for e in new_emails:
        db().execute("INSERT INTO access(email,name,role,all_projects) VALUES(?,?,'lead',0) ON CONFLICT DO NOTHING", (e, ""))
        db().execute("INSERT INTO project_access(project_id,email,kind) VALUES(?,?,'lead') ON CONFLICT DO NOTHING", (str(pid), e))
        _sync_lead_as_member(pid, e)

def _parent_choices():
    """Main projects this user may put a sub-project under."""
    return [p for p in my_projects() if not p["parent"] and can_edit(p["id"])]

def _dup_project(name, parent, skip=""):
    return any(p["short"].lower() == name.lower() and p["parent"] == parent and p["id"] != skip for p in projects(True))

@app.route("/projects")
@login_required
def projects_page():
    ps = my_projects(include_archived=is_admin())
    for p in ps:
        p["leads"] = ", ".join(r["email"] for r in db().execute("SELECT email FROM project_access WHERE project_id=? AND kind='lead' ORDER BY email", (p["id"],)))
        p["count"] = len(team(p["id"])); p["editable"] = can_edit(p["id"])
        p["has_subs"] = any(q["parent"] == p["id"] for q in ps)
        p["sites"] = mobile_site_rows(p["id"]) if "mobile_site_rows" in globals() else []
    return render_template("projects.html", day=today(), projects=ps, op_projects=op_projects(), can_create=can_create(),
                           watching={p["id"] for p in watched()})

@app.route("/projects/watch", methods=["POST"])
@login_required
def projects_watch():
    if my_role() not in ("admin", "manager"): abort(403)
    allowed = set(my_pids())
    db().execute("DELETE FROM watch WHERE email=?", (email(),))
    for pid in request.form.getlist("watch"):
        if pid in allowed: db().execute("INSERT INTO watch(email,project_id) VALUES(?,?) ON CONFLICT DO NOTHING", (email(), pid))
    db().commit(); n = len(watched())
    flash(f"You are now watching {n} project{'s' if n != 1 else ''}." if n else "No selection - you will see all your projects.", "ok")
    return redirect(url_for("projects_page"))

@app.route("/projects/create", methods=["POST"])
@login_required
def projects_create():
    if not can_create(): abort(403, "Only an admin or a TL/PM can create a project.")
    f = request.form; parent = f.get("parent", "").strip()
    try:
        name = v_project(f.get("name", ""))
        if parent and parent not in [p["id"] for p in _parent_choices()]: raise ValueError("Choose a main project you are allowed to manage.")
        if _dup_project(name, parent): raise ValueError("A project with this name already exists here.")
        leads, bad = split_emails(f.get("leads", "")) if is_admin() else ([], [])
        if bad: raise ValueError("Not a valid email: " + ", ".join(bad))
    except ValueError as ex:
        flash(str(ex), "err"); return redirect(url_for("projects_page"))
    new_id = db().insert_id("INSERT INTO project(name,op_project_id,parent_id,active,created_by,created_at) VALUES(?,?,?,1,?,?)",
                       (name, f.get("op_id", "").strip(), int(parent) if parent else None, *_stamp()))
    if not is_admin() and not parent: leads = [email()]      # a TL/PM owns the main project they create; sub-projects follow the main one
    _set_leads(new_id, leads); db().commit()
    flash(f"{'Sub-project' if parent else 'Project'} \"{name}\" added. Add its engineers under Team"
          + (", and set its TL/PM under Edit." if is_admin() and not parent else "."), "ok")
    return redirect(url_for("projects_page"))

@app.route("/projects/update", methods=["POST"])
@login_required
def projects_update():
    f = request.form; pid = f.get("project", ""); act = f.get("action", "save"); p = proj(pid)
    if not p or not (can_edit(pid) or is_admin()): abort(403)
    if act in ("archive", "restore"):
        if not is_admin(): abort(403, "Only an admin can archive a project.")
        db().execute("UPDATE project SET active=? WHERE id=?", (0 if act == "archive" else 1, pid))
    else:
        try:
            name = v_project(f.get("name", "")); parent = p["parent"]
            if is_admin() and "parent" in f:
                parent = f.get("parent", "").strip()
                if parent:
                    par = proj(parent)
                    if not par or par["parent"] or parent == pid: raise ValueError("Choose a main project (not a sub-project) as the parent.")
                    if any(q["parent"] == pid for q in projects(True)): raise ValueError("This project has sub-projects, so it cannot become a sub-project itself.")
            if _dup_project(name, parent, skip=pid): raise ValueError("A project with this name already exists here.")
            leads, bad = split_emails(f.get("leads", "")) if is_admin() else ([], [])
            if bad: raise ValueError("Not a valid email: " + ", ".join(bad))
        except ValueError as ex:
            flash(str(ex), "err"); return redirect(url_for("projects_page"))
        db().execute("UPDATE project SET name=?,op_project_id=?,parent_id=? WHERE id=?", (name, f.get("op_id", "").strip(), int(parent) if parent else None, pid))
        if is_admin(): _set_leads(pid, leads)
    db().commit(); flash("Project updated.", "ok")
    return redirect(url_for("projects_page"))

# ------------------------------------------------------------ project setup: PM chain, project information, client officers
@app.route("/project/setup")
@login_required
def wf_setup():
    ps = [p for p in my_projects() if can_edit(p["id"])]
    if not ps: abort(403, "Only a project lead or an admin can open project setup.")
    pid = request.args.get("project") or ps[0]["id"]
    if pid not in [p["id"] for p in ps]: abort(403)
    ch = {lv: em for lv, em in chain(pid)}
    info = db().execute("SELECT * FROM project_info WHERE project_id=?", (pid,)).fetchone()
    offs = {r["member_id"]: dict(r) for r in db().execute("SELECT * FROM client_officer WHERE project_id=?", (pid,))}
    mem = members(pid)
    own = {r["member_id"]: {x for x in (r["weekly_off"] or "").split(",") if x} for r in db().execute("SELECT member_id, weekly_off FROM team WHERE project_id=?", (pid,))}
    dflt = {x for x in ((info["weekly_off"] if info else "") or "").split(",") if x}
    sites = mobile_site_rows(pid) if "mobile_site_rows" in globals() else []
    return render_template("project_setup.html", projects=ps, pid=pid, chain=ch, levels=LEVELS, info=dict(info) if info else {},
                           members=mem, officers=offs, days=DAYS, own_off=own, dflt_off=dflt, site_off=sorted(WEEKLY_OFF),
                           sites=sites)

@app.route("/project/setup/chain", methods=["POST"])
@login_required
def wf_chain_save():
    pid = request.form.get("project", "")
    if not can_edit(pid): abort(403)
    new = {}
    for lv in LEVELS:
        em = (request.form.get(f"pm{lv}") or "").strip().lower()
        if em and not EMAIL_RE.match(em): flash(f"PM{lv}: not a valid email.", "err"); return redirect(url_for("wf_setup", project=pid))
        if em: new[lv] = em
    if len(set(new.values())) != len(new): flash("The same person cannot hold two levels.", "err"); return redirect(url_for("wf_setup", project=pid))
    db().execute("DELETE FROM pm_chain WHERE project_id=?", (pid,))
    for lv, em in new.items():
        db().execute("INSERT INTO pm_chain(project_id,level,email) VALUES(?,?,?)", (pid, lv, em))
        # a chain member must be able to open and approve in this project: give TL/PM access to it
        db().execute("INSERT INTO access(email,name,role,all_projects) VALUES(?,?,?,0) ON CONFLICT(email) DO NOTHING", (em, em.split("@")[0], "lead"))
        db().execute("INSERT INTO project_access(project_id,email,kind) VALUES(?,?,?) ON CONFLICT DO NOTHING", (pid, em, "lead"))
    db().commit(); flash("PM chain saved. Each person was also given TL/PM access to this project.", "ok")
    return redirect(url_for("wf_setup", project=pid))

@app.route("/project/setup/info", methods=["POST"])
@login_required
def wf_info_save():
    f = request.form; pid = f.get("project", "")
    if not can_edit(pid): abort(403)
    get_f = lambda k, n=120: (f.get(k) or "").strip()[:n]
    lat, lon = get_f("lat", 20), get_f("lon", 20)
    try:
        if lat or lon:
            if not (-90 <= float(lat) <= 90 and -180 <= float(lon) <= 180): raise ValueError
    except ValueError: flash("Latitude must be -90..90 and longitude -180..180, or leave both empty.", "err"); return redirect(url_for("wf_setup", project=pid))
    if not mail_ok(get_f("owner_email")): flash("Owner email is not valid.", "err"); return redirect(url_for("wf_setup", project=pid))
    mc = get_f("min_capacity", 5)
    if mc and not mc.isdigit(): flash("Minimum capacity must be a whole number, or empty for automatic.", "err"); return redirect(url_for("wf_setup", project=pid))
    wo = ",".join(d for d in DAYS if d in f.getlist("woff"))
    db().execute("""INSERT INTO project_info(project_id,owner_name,owner_email,owner_phone,location,lat,lon,updated_by,updated_at,min_capacity,weekly_off) VALUES(?,?,?,?,?,?,?,?,?,?,?)
        ON CONFLICT(project_id) DO UPDATE SET owner_name=excluded.owner_name,owner_email=excluded.owner_email,owner_phone=excluded.owner_phone,
        location=excluded.location,lat=excluded.lat,lon=excluded.lon,updated_by=excluded.updated_by,updated_at=excluded.updated_at,min_capacity=excluded.min_capacity,weekly_off=excluded.weekly_off""",
        (pid, get_f("owner_name"), get_f("owner_email"), get_f("owner_phone", 30), get_f("location", 200), lat, lon, email(), stamp(), mc, wo))
    db().commit(); flash("Project information saved.", "ok"); return redirect(url_for("wf_setup", project=pid))

@app.route("/project/setup/weekoff", methods=["POST"])
@login_required
def wf_weekoff_save():
    f = request.form; pid = f.get("project", "")
    if not can_edit(pid): abort(403)
    for m in members(pid):
        if f.get(f"wo_present_{m['id']}") is None: continue
        v = ",".join(d for d in DAYS if d in f.getlist(f"wo_{m['id']}"))
        db().execute("UPDATE team SET weekly_off=?, updated_by=?, updated_at=? WHERE project_id=? AND member_id=?", (v, email(), stamp(), pid, m["id"]))
    db().commit(); flash("Weekly off saved. Leave days, the attendance sheet and reports now follow each person's own days off.", "ok"); return redirect(url_for("wf_setup", project=pid))

@app.route("/project/setup/officers", methods=["POST"])
@login_required
def wf_officers_save():
    f = request.form; pid = f.get("project", "")
    if not can_edit(pid): abort(403)
    for m in members(pid):
        nm, em, ph = (f.get(f"o_name_{m['id']}") or "").strip()[:100], (f.get(f"o_email_{m['id']}") or "").strip()[:120], (f.get(f"o_phone_{m['id']}") or "").strip()[:30]
        if em and not EMAIL_RE.match(em): flash(f"{m['name']}: officer email is not valid (nothing saved for this person).", "err"); continue
        if not (nm or em or ph): db().execute("DELETE FROM client_officer WHERE project_id=? AND member_id=?", (pid, m["id"])); continue
        db().execute("""INSERT INTO client_officer(project_id,member_id,name,email,phone) VALUES(?,?,?,?,?)
            ON CONFLICT(project_id,member_id) DO UPDATE SET name=excluded.name,email=excluded.email,phone=excluded.phone""", (pid, m["id"], nm, em, ph))
    db().commit(); flash("Client reporting officers saved.", "ok"); return redirect(url_for("wf_setup", project=pid))

# ------------------------------------------------------------ notices: live popup (must be acknowledged) + email
@app.route("/wf/notices")
@login_required
def wf_e_notices():
    rows = db().execute("SELECT id,kind,title,body,link,created_at FROM notice WHERE lower(email)=? AND acked_at IS NULL ORDER BY id LIMIT 20", (email(),)).fetchall()
    return jsonify(notices=[dict(r) for r in rows])

@app.route("/wf/notices/ack", methods=["POST"])
@login_required
def wf_e_ack():
    for i in request.form.getlist("id"):
        db().execute("UPDATE notice SET acked_at=? WHERE id=? AND lower(email)=? AND acked_at IS NULL", (stamp(), i, email()))
    db().commit()
    return jsonify(ok=True)

# ------------------------------------------------------------ approvals screen & decisions
@app.route("/approvals")
@login_required
def wf_approvals():
    if my_role() not in ("admin", "lead", "manager"): abort(403)
    safe_refresh()
    pids = set(my_pids())
    me = email()
    adm = is_admin()
    names = {p["id"]: p["name"] for p in projects(True)}
    def hydrate(rows):
        out = []
        for a in rows:
            a = dict(a)
            if a["project_id"] not in pids and not adm: continue
            at = db().execute("SELECT * FROM attendance WHERE day=? AND user_id=?", (a["day"], a["user_id"])).fetchone()
            a["name"] = (at["user_name"] if at else a["user_id"])
            a["in_time"] = at["in_time"] if at else ""
            a["out_time"] = at["out_time"] if at else ""
            a["project"] = names.get(a["project_id"], a["project_id"])
            a["mine"] = can_decide(a)
            try:
                a["events"] = db().execute("SELECT count(*) AS n FROM checkin_event WHERE day=? AND member_id=?", (a["day"], a["user_id"])).fetchone()["n"]
            except Exception:
                try: db().rollback()
                except Exception: pass
                a["events"] = 0
            out.append(a)
        return out
    waiting = hydrate(db().execute("SELECT * FROM approval WHERE status='pending' ORDER BY due_at").fetchall())
    escalated = hydrate(db().execute("SELECT * FROM approval WHERE status='escalated' ORDER BY escalated_at").fetchall())
    recent = hydrate(db().execute("SELECT * FROM approval WHERE status IN ('approved','rejected') AND decided_at>=? ORDER BY decided_at DESC LIMIT 60",
                                  ((mnow() - timedelta(days=7)).isoformat(timespec="seconds"),)).fetchall())
    d30 = (mnow() - timedelta(days=30)).isoformat(timespec="seconds")
    misses = [dict(r) for r in db().execute("""SELECT approver, project_id, count(*) AS total, sum(CASE WHEN missed_at>=? THEN 1 ELSE 0 END) AS last30
                                                FROM approval_miss GROUP BY approver, project_id ORDER BY total DESC""", (d30,)).fetchall()]
    misses = [m for m in misses if adm or m["project_id"] in pids]
    for m in misses:
        m["project"] = names.get(m["project_id"], m["project_id"])
        m["last30"] = m["last30"] or 0
    objections = [dict(o) for o in db().execute("SELECT * FROM objection WHERE status='open' ORDER BY id").fetchall()]
    objections = [o for o in objections if adm or o["project_id"] in pids]
    for o in objections:
        u = db().execute("SELECT user_name FROM attendance WHERE day=? AND user_id=?", (o["day"], o["user_id"])).fetchone()
        o["name"] = (u["user_name"] if u else o["email"])
        o["project"] = names.get(o["project_id"], "")
    return render_template("approvals.html", waiting=waiting, escalated=escalated, recent=recent, misses=misses, objections=objections,
                           hours=hours(), me=me, adm=adm, can_reply=my_role() in ("admin", "lead"))

@app.route("/approvals/decide", methods=["POST"])
@login_required
def wf_decide():
    act = request.form.get("action")
    note = (request.form.get("note") or "").strip()[:300]
    if act not in ("approve", "reject"): abort(400)
    n = 0
    now_stamp = stamp()
    for key in request.form.getlist("key"):
        try: day, uid = key.split("|", 1)
        except ValueError: continue
        ap = db().execute("SELECT * FROM approval WHERE day=? AND user_id=?", (day, uid)).fetchone()
        if not ap or ap["status"] not in ("pending", "escalated") or not can_decide(ap): continue
        new_app_status = "Approved" if act == "approve" else "Rejected"
        db().execute("UPDATE approval SET status=?, decided_by=?, decided_at=?, note=? WHERE day=? AND user_id=?",
                     ("approved" if act == "approve" else "rejected", email(), now_stamp, note, day, uid))
        # Fix Bug #1: Synchronize attendance table
        db().execute("""UPDATE attendance
                        SET approval_status=?, approved_by=?, approved_at=?, rejection_reason=?
                        WHERE day=? AND user_id=?""",
                     (new_app_status, email(), now_stamp, (note if act == "reject" else ""), day, uid))
        mem = team_row(uid)
        if mem and mem["email"]:
            if act == "reject":
                notify([mem["email"]], "approval_rejected", f"Attendance for {day} was rejected",
                       f"Your TL/PM ({email()}) rejected your attendance for {day}.\nReason: {note or 'No remarks provided.'}\nPlease review and resubmit.", "/me")
            else:
                notify([mem["email"]], "approval_approved", f"Attendance for {day} approved",
                       f"Your attendance for {day} has been approved by {email()}.", "/me")
        n += 1
    db().commit()
    flash(f"{n} request{'' if n == 1 else 's'} {'approved' if act == 'approve' else 'rejected'}.", "ok" if n else "err")
    return redirect(url_for("wf_approvals"))

@app.route("/approvals/settings", methods=["POST"])
@login_required
def wf_settings():
    if not is_admin(): abort(403)
    try: h = int(request.form.get("hours", ""))
    except ValueError: h = 0
    if not 1 <= h <= 240:
        flash("Hours must be between 1 and 240.", "err")
        return redirect(url_for("wf_approvals"))
    db().execute("INSERT INTO meta(k,v) VALUES('approval_hours',?) ON CONFLICT(k) DO UPDATE SET v=excluded.v", (str(h),))
    db().commit()
    flash(f"Approvals not decided within {h} hours now go to the admin.", "ok")
    return redirect(url_for("wf_approvals"))

@app.route("/approvals/objection/reply", methods=["POST"])
@login_required
def wf_objection_reply():
    f = request.form
    o = db().execute("SELECT * FROM objection WHERE id=?", (f.get("id", ""),)).fetchone()
    if not o or o["status"] != "open" or not (is_admin() or can_edit(o["project_id"]) or any(e == email() for _, e in chain(o["project_id"]))):
        abort(403)
    act, comment = f.get("action", "reject"), (f.get("reply") or "").strip()[:500]
    if not comment:
        flash("Write a comment for the engineer.", "err")
        return redirect(url_for("wf_approvals"))
    applied = ""
    now_stamp = stamp()
    if act == "accept":
        i, out = (f.get("in") or o["req_in"] or "").strip(), (f.get("out") or o["req_out"] or "").strip()
        if i or out:
            if (i and mins(i) is None) or (out and mins(out) is None):
                flash("Times must be HH:MM.", "err")
                return redirect(url_for("wf_approvals"))
            t = team_row(o["user_id"])
            cur = db().execute("SELECT * FROM attendance WHERE day=? AND user_id=?", (o["day"], o["user_id"])).fetchone()
            ni = i or (cur["in_time"] if cur else "")
            no = out or (cur["out_time"] if cur else "")
            if ni and no and mins(no) < mins(ni) and not is_night(mins(t["shift_start"]) if t and t["shift_start"] else mins(SHIFT_START)):
                flash("OUT is before IN. Nothing changed.", "err")
                return redirect(url_for("wf_approvals"))
            nm = (t["name"] if t else (cur["user_name"] if cur else o["email"]))
            db().execute("""INSERT INTO attendance(day,user_id,user_name,in_time,out_time,leave_type,planned,handled_by,remarks,updated_by,updated_at,shift_start,approval_status,approved_by,approved_at)
                VALUES(?,?,?,?,?,'','','',?,?,?,?,'Approved',?,?)
                ON CONFLICT(day,user_id) DO UPDATE SET in_time=excluded.in_time,out_time=excluded.out_time,updated_by=excluded.updated_by,updated_at=excluded.updated_at,approval_status='Approved',approved_by=excluded.approved_by,approved_at=excluded.approved_at""",
                (o["day"], o["user_id"], nm, ni, no, "Corrected after objection", email(), now_stamp, (t["shift_start"] if t else "") or SHIFT_START, email(), now_stamp))
            applied = f"IN {ni or '-'} / OUT {no or '-'}"
    db().execute("UPDATE objection SET status=?, reply=?, closed_by=?, closed_at=?, applied=? WHERE id=?",
                 ("accepted" if act == "accept" else "rejected", comment, email(), now_stamp, applied, o["id"]))
    notify([o["email"]], "objection", f"Your objection for {o['day']} was {'accepted' if act == 'accept' else 'rejected'}",
           comment + (f"\nCorrected to {applied}." if applied else ""), "/me")
    db().commit()
    safe_refresh()
    flash("Objection " + ("accepted" + (f"; attendance corrected to {applied}" if applied else " (no times changed - edit the sheet if needed)") if act == "accept" else "rejected") + ".", "ok")
    return redirect(url_for("wf_approvals"))

@app.route("/me/objection", methods=["POST"])
@login_required
def wf_e_objection():
    m = my_member()
    if not m: abort(403, "You are not in an active project team.")
    body = (request.form.get("body") or "").strip()[:500]
    day = request.form.get("day", "")
    ri = (request.form.get("req_in") or "").strip()
    ro = (request.form.get("req_out") or "").strip()
    if not body or not day:
        flash("Pick the day and say what is wrong.", "err")
        return redirect(url_for("me"))
    if (ri and mins(ri) is None) or (ro and mins(ro) is None):
        flash("Requested times must be HH:MM.", "err")
        return redirect(url_for("me"))
    db().execute("INSERT INTO objection(day,user_id,email,project_id,body,created_at,req_in,req_out) VALUES(?,?,?,?,?,?,?,?)",
                 (day, m["member_id"], email(), m["project_id"], body, stamp(), ri, ro))
    notify(project_people(m["project_id"]), "objection", f"Attendance objection from {m['name']} ({day})",
           body + (f"\nAsks for IN {ri or '-'} / OUT {ro or '-'}." if ri or ro else ""), "/approvals")
    db().commit()
    flash("Your objection was sent to your TL/PM. You will see the answer here.", "ok")
    return redirect(url_for("me"))

# ------------------------------------------------------------ leave workflow: engineer & PM/TL routes
@app.route("/me/leave/check")
@login_required
def wf_e_leave_check():
    m = my_member()
    if not m: return jsonify(error="not in a team"), 403
    f, t = request.args.get("from", ""), request.args.get("to", "")
    try: assert d_(f) <= d_(t)
    except Exception: return jsonify(days=[], text="")
    bad = check_capacity(m["project_id"], m["member_id"], f, t)
    others = others_leave(m["project_id"], m["member_id"], f, t)
    txt = ""
    if bad:
        txt = "Team capacity is full on " + ", ".join(f"{b['day']} (only {b['available_after']} of {b['total']} would be at work; minimum {b['minimum']})" for b in bad[:6]) + ". Your TL/PM can ask you to withdraw, and approval then needs a senior PM."
    return jsonify(capacity_full=bool(bad), text=txt, others=others)

@app.route("/me/leave/apply", methods=["POST"])
@login_required
def wf_e_leave_apply():
    m = my_member()
    if not m: abort(403, "You are not in a project team.")
    f = request.form
    fd, td_ = f.get("from", ""), f.get("to", "") or f.get("from", "")
    lt, reason = f.get("leave_type", ""), (f.get("reason") or "").strip()[:300]
    cover = (f.get("cover") or "").strip()
    try: a, b = d_(fd), d_(td_)
    except ValueError:
        flash("Choose valid dates.", "err")
        return redirect(url_for("me"))
    td_today = d_(today())
    if b < a:
        flash("The last day is before the first day.", "err")
        return redirect(url_for("me"))
    if a < td_today:
        flash("You cannot apply for a day that has passed. Ask your TL/PM.", "err")
        return redirect(url_for("me"))
    if (b - a).days + 1 > MAX_LEAVE_DAYS:
        flash(f"A request can cover at most {MAX_LEAVE_DAYS} days.", "err")
        return redirect(url_for("me"))
    if lt not in LEAVE_TYPES:
        flash("Choose a valid leave type.", "err")
        return redirect(url_for("me"))
    if not work_days(m["member_id"], fd, td_):
        flash("All those days are your weekly off.", "err")
        return redirect(url_for("me"))
    uid, pid = m["member_id"], m["project_id"]
    if db().execute("SELECT 1 FROM leave_request WHERE user_id=? AND status IN ('pending','approved','modification','withdraw_requested') AND to_date>=? AND from_date<=?", (uid, fd, td_)).fetchone():
        flash("You already have an active leave request covering some of these days.", "err")
        return redirect(url_for("me"))
    planned = "Planned" if (a - td_today).days >= planned_days() else "Unplanned"
    ext = None
    for r in db().execute("SELECT * FROM leave_request WHERE user_id=? AND status='approved' AND to_date<? ORDER BY to_date DESC", (uid, fd)).fetchall():
        gap = [x for x in span((d_(r["to_date"]) + timedelta(days=1)).isoformat(), (a - timedelta(days=1)).isoformat())] if d_(r["to_date"]) + timedelta(days=1) < a else []
        if all(wd(x) in off_days(uid) for x in gap):
            ext = dict(r)
            break
    bad = check_capacity(pid, uid, fd, td_)
    normal = approver_for(pid, fd)
    assigned = one_above(pid, normal) if bad else normal
    due = (mnow() + timedelta(hours=approve_hours())).isoformat(timespec="seconds")
    now_stamp = stamp()
    db().execute("""INSERT INTO leave_request(user_id,project_id,email,name,from_date,to_date,leave_type,reason,planned,status,assigned_to,created_at,due_at,capacity_full,cap_days,is_extension,ext_of,handled_by)
                    VALUES(?,?,?,?,?,?,?,?,?,'pending',?,?,?,?,?,?,?,?)""",
                 (uid, pid, email(), m["name"], fd, td_, lt, reason, planned, assigned or "admin", now_stamp, due, 1 if bad else 0, ",".join(x["day"] for x in bad), 1 if ext else 0, ext["id"] if ext else None, cover))
    body = f"{m['name']} applied for {lt} from {fd} to {td_} ({planned}). {reason}".strip()
    if cover: body += f"\nCover person: {cover}."
    if ext: body += f"\nThis continues the approved leave that ended {ext['to_date']} (recorded as an extension)."
    if bad: body += "\nTEAM CAPACITY IS FULL on " + ", ".join(x["day"] for x in bad[:6]) + ". Approval needs one level above."
    notify(project_people(pid) + ([assigned] if assigned and assigned != "admin" else []), "leave", f"Leave application: {m['name']} ({fd} to {td_})", body, "/leaves")
    try:
        p_leads = project_people(pid) + ([assigned] if assigned and assigned != "admin" else [])
        mailer.notify_leave_applied(p_leads, m["name"], lt, fd, td_, reason, is_half_day=(lt == "Half Day"))
        mailer.notify_leave_acknowledgement(email(), m["name"], lt, fd, td_)
    except Exception as ex:
        app.logger.warning("mailer leave_applied error: %s", ex)
    db().commit()
    flash("Leave applied. Your TL/PM was notified." + (" Team capacity is full on some of these days, so a senior PM will decide." if bad else ""), "ok")
    return redirect(url_for("me"))

@app.route("/me/leave/cancel", methods=["POST"])
@login_required
def wf_e_leave_cancel():
    m = my_member()
    r = db().execute("SELECT * FROM leave_request WHERE id=?", (request.form.get("id", ""),)).fetchone()
    if not m or not r or r["user_id"] != m["member_id"]: abort(403)
    td_today = today()
    now_stamp = stamp()
    if r["status"] in ("pending", "modification", "withdraw_requested"):
        new_st = "cancelled"
    elif r["status"] == "approved" and r["to_date"] >= td_today:
        if r["from_date"] <= td_today:
            flash("This leave has already started. Use 'I am back early' instead.", "err")
            return redirect(url_for("me"))
        clear_leave_days(dict(r), r["from_date"])
        new_st = "cancelled"
    else:
        flash("This leave cannot be cancelled.", "err")
        return redirect(url_for("me"))
    db().execute("UPDATE leave_request SET status=?, decided_at=?, note=? WHERE id=?", (new_st, now_stamp, (r["note"] or "") + " | cancelled by engineer", r["id"]))
    # Auto-dismiss / acknowledge any stale pending "leave request" notices for this leave
    db().execute("UPDATE notice SET acked_at=? WHERE kind='leave' AND link='/leaves' AND title LIKE ? AND acked_at IS NULL",
                 (now_stamp, f"%{r['name']}%"))
    notify(project_people(r["project_id"]), "leave_cancelled", f"Leave cancelled: {r['name']} ({r['from_date']} to {r['to_date']})", "The engineer cancelled this leave.", "/leaves")
    db().commit()
    flash("Leave cancelled.", "ok")
    return redirect(url_for("me"))

@app.route("/me/leave/early", methods=["POST"])
@login_required
def wf_e_leave_early():
    m = my_member()
    r = db().execute("SELECT * FROM leave_request WHERE id=?", (request.form.get("id", ""),)).fetchone()
    td_today = today()
    if not m or not r or r["user_id"] != m["member_id"]: abort(403)
    if r["status"] != "approved" or not (r["from_date"] <= td_today <= r["to_date"]) or r["early_join"]:
        flash("You can only join early while an approved leave is currently running.", "err")
        return redirect(url_for("me"))
    clear_leave_days(dict(r), td_today)
    db().execute("UPDATE leave_request SET early_join=? WHERE id=?", (td_today, r["id"]))
    notify(project_people(r["project_id"]), "leave", f"{r['name']} joined early", f"Leave was until {r['to_date']}; back at work on {td_today}.", "/leaves")
    db().commit()
    flash("Recorded: you joined before your leave ended. Mark your attendance as usual.", "ok")
    return redirect(url_for("me"))

@app.route("/me/leave/answer", methods=["POST"])
@login_required
def wf_e_leave_answer():
    m = my_member()
    r = db().execute("SELECT * FROM leave_request WHERE id=?", (request.form.get("id", ""),)).fetchone()
    if not m or not r or r["user_id"] != m["member_id"] or r["status"] != "modification": abort(403)
    if request.form.get("action") == "accept":
        bad = check_capacity(r["project_id"], r["user_id"], r["suggest_from"], r["suggest_to"])
        normal = approver_for(r["project_id"], r["suggest_from"])
        db().execute("UPDATE leave_request SET from_date=?, to_date=?, suggest_from=NULL, suggest_to=NULL, status='pending', capacity_full=?, cap_days=?, assigned_to=?, due_at=? WHERE id=?",
                     (r["suggest_from"], r["suggest_to"], 1 if bad else 0, ",".join(x["day"] for x in bad), one_above(r["project_id"], normal) if bad else normal,
                      (mnow() + timedelta(hours=approve_hours())).isoformat(timespec="seconds"), r["id"]))
        notify(project_people(r["project_id"]), "leave", f"{r['name']} accepted the suggested dates", f"Now {r['suggest_from']} to {r['suggest_to']}. Waiting for your approval.", "/leaves")
        flash("You accepted the new dates. Your TL/PM will approve them.", "ok")
    else:
        db().execute("UPDATE leave_request SET status='cancelled', note=? WHERE id=?", ((r["note"] or "") + " | engineer declined the suggestion", r["id"]))
        notify(project_people(r["project_id"]), "leave", f"{r['name']} declined the suggested dates", "The leave request is cancelled.", "/leaves")
        flash("Leave request cancelled.", "ok")
    db().commit()
    return redirect(url_for("me"))

def visible_leave_requests(where, args=()):
    pids = set(my_pids())
    adm = is_admin()
    out = []
    names = {p["id"]: p["name"] for p in projects(True)}
    for r in db().execute(f"SELECT * FROM leave_request WHERE {where}", args).fetchall():
        r = dict(r)
        if not adm and r["project_id"] not in pids: continue
        r["project"] = names.get(r["project_id"], r["project_id"])
        r["can_approve"] = can_approve_leave(r)
        r["can_manage"] = can_manage_leave(r["project_id"])
        r["days"] = len(work_days(r["user_id"], r["from_date"], r["to_date"]))
        out.append(r)
    return out

@app.route("/leaves")
@login_required
def wf_leaves():
    if my_role() not in ("admin", "lead", "manager"): abort(403)
    safe_refresh()
    ps = my_projects()
    pid = request.args.get("project") or (ps[0]["id"] if ps else "")
    if pid and pid not in [p["id"] for p in ps]: abort(404)
    pending = visible_leave_requests("status IN ('pending','modification','withdraw_requested') ORDER BY due_at")
    recent = visible_leave_requests("status IN ('approved','rejected','cancelled') ORDER BY decided_at DESC LIMIT 60")
    cal = []
    if pid:
        t = d_(today())
        for i in range(30):
            day = (t + timedelta(days=i)).isoformat()
            c = day_cap(pid, day)
            c["day"] = day
            cal.append(c)
    return render_template("leaves.html", pending=pending, recent=recent, cal=cal, projects=ps, pid=pid, adm=is_admin(), hours=approve_hours(), pdays=planned_days(),
                           csrf=session.get("csrf", ""))

@app.route("/leaves/decide", methods=["POST"])
@login_required
def wf_leave_decide():
    f = request.form
    r = db().execute("SELECT * FROM leave_request WHERE id=?", (f.get("id", ""),)).fetchone()
    if not r or not can_manage_leave(r["project_id"]): abort(403)
    r = dict(r)
    if r["status"] not in ("pending", "modification", "withdraw_requested"):
        flash("This leave request is no longer pending (it may have been cancelled by the applicant or already decided).", "err")
        return redirect(url_for("wf_leaves"))
    act = f.get("action")
    note = (f.get("note") or "").strip()[:300]
    now_stamp = stamp()
    if act == "approve":
        if not can_approve_leave(r):
            flash("Team capacity is full or this is waiting for someone above you. You can reject, ask the engineer to withdraw, or suggest other dates.", "err")
            return redirect(url_for("wf_leaves"))
        pl = f.get("planned")
        planned = r["planned"] if pl == "auto" else (pl or r["planned"])
        r["planned"] = planned
        cur = db().execute("UPDATE leave_request SET status='approved', decided_by=?, decided_at=?, note=?, planned=? WHERE id=? AND status IN ('pending', 'modification', 'withdraw_requested')",
                     (email(), now_stamp, note, planned, r["id"]))
        if cur.rowcount == 0:
            flash("Action failed: This leave request was cancelled or already decided.", "err")
            return redirect(url_for("wf_leaves"))
        n = write_leave_days(r, email())
        notify([r["email"]], "leave_approved", f"Your leave was approved ({r['from_date']} to {r['to_date']})",
               f"{planned} leave approved by {email()}.\n{note}\nWritten to {n} day(s) on the attendance sheet.", "/me")
        try: mailer.notify_leave_decided(r["email"], r["name"], "approved", email(), r["from_date"], r["to_date"], remarks=note)
        except Exception as ex: app.logger.warning("mailer leave_decided error: %s", ex)
        flash(f"Approved. Written to {n} day(s) on the attendance sheet.", "ok")
    elif act == "reject":
        if not note:
            flash("Give a reason for the engineer.", "err")
            return redirect(url_for("wf_leaves"))
        cur = db().execute("UPDATE leave_request SET status='rejected', decided_by=?, decided_at=?, note=? WHERE id=? AND status IN ('pending', 'modification', 'withdraw_requested')",
                     (email(), now_stamp, note, r["id"]))
        if cur.rowcount == 0:
            flash("Action failed: This leave request was cancelled or already decided.", "err")
            return redirect(url_for("wf_leaves"))
        notify([r["email"]], "leave_rejected", f"Your leave was rejected ({r['from_date']} to {r['to_date']})", f"Reason: {note}", "/me")
        try: mailer.notify_leave_decided(r["email"], r["name"], "rejected", email(), r["from_date"], r["to_date"], remarks=note)
        except Exception as ex: app.logger.warning("mailer leave_decided error: %s", ex)
        flash("Leave rejected.", "ok")
    elif act == "withdraw":
        cur = db().execute("UPDATE leave_request SET status='withdraw_requested', note=? WHERE id=? AND status IN ('pending', 'modification')", (note, r["id"]))
        if cur.rowcount == 0:
            flash("Action failed: This leave request is no longer pending.", "err")
            return redirect(url_for("wf_leaves"))
        notify([r["email"]], "leave_withdraw", f"Please withdraw your leave ({r['from_date']} to {r['to_date']})",
               f"Team capacity is full on those days. {note}\nOpen My attendance to withdraw or speak with your PM.", "/me")
        flash("Engineer asked to withdraw.", "ok")
    elif act == "suggest":
        sf, st = f.get("sfrom", ""), f.get("sto", "")
        try: assert d_(sf) <= d_(st) and d_(sf) >= d_(today())
        except Exception:
            flash("Give valid suggested dates (not in the past).", "err")
            return redirect(url_for("wf_leaves"))
        cur = db().execute("UPDATE leave_request SET status='modification', suggest_from=?, suggest_to=?, note=? WHERE id=? AND status IN ('pending', 'modification')", (sf, st, note, r["id"]))
        if cur.rowcount == 0:
            flash("Action failed: This leave request is no longer pending.", "err")
            return redirect(url_for("wf_leaves"))
        notify([r["email"]], "leave_suggest", f"Change suggested for your leave ({r['from_date']} to {r['to_date']})", f"Suggested: {sf} to {st}. {note}", "/me")
        flash("Suggestion sent.", "ok")
    else: abort(400)
    db().commit()
    return redirect(url_for("wf_leaves"))

@app.route("/leaves/settings", methods=["POST"])
@login_required
def wf_leave_settings():
    if not is_admin(): abort(403)
    try: pd, hh = int(request.form.get("pdays", "")), int(request.form.get("hours", ""))
    except ValueError: pd = hh = -1
    if not (0 <= pd <= 60 and 1 <= hh <= 240):
        flash("Planned-leave days 0-60 and hours 1-240.", "err")
        return redirect(url_for("wf_leaves"))
    for k, v in (("leave_planned_days", pd), ("leave_approval_hours", hh)):
        db().execute("INSERT INTO meta(k,v) VALUES(?,?) ON CONFLICT(k) DO UPDATE SET v=excluded.v", (k, str(v)))
    db().commit()
    flash("Leave settings saved.", "ok")
    return redirect(url_for("wf_leaves"))

def leave_report_data(pid, f, t):
    rows = {"capacity": [], "late": [], "ext": [], "early": [], "mix": [], "withdraw": []}
    for p in ([pid] if pid else [x["id"] for x in my_projects()]):
        pname = next((x["name"] for x in projects(True) if x["id"] == p), p)
        for day in span(f, t):
            c = day_cap(p, day)
            if c["total"] and c["short"]:
                rows["capacity"].append({"project": pname, "day": day, "total": c["total"], "away": c["away"], "available": c["available"], "minimum": c["minimum"], "pending": c["pending"]})
    pids = set(my_pids())
    adm = is_admin()
    names = {p["id"]: p["name"] for p in projects(True)}
    t_end = t + "T23:59:59"
    for m in db().execute("SELECT * FROM leave_miss WHERE missed_at>=? AND missed_at<=? ORDER BY id DESC", (f, t_end)).fetchall():
        if (adm or m["project_id"] in pids) and (not pid or m["project_id"] == pid):
            q = db().execute("SELECT name,from_date,to_date FROM leave_request WHERE id=?", (m["request_id"],)).fetchone()
            rows["late"].append({"project": names.get(m["project_id"], m["project_id"]), "engineer": q["name"] if q else "", "leave": f"{q['from_date']} to {q['to_date']}" if q else "", "approver": m["approver"], "escalated_to": m["escalated_to"], "at": (m["missed_at"] or "")[:16].replace("T", " ")})
    for r in visible_leave_requests("to_date>=? AND from_date<=? ORDER BY from_date", (f, t)):
        if pid and r["project_id"] != pid: continue
        if r["is_extension"] and r["status"] != "cancelled":
            o = db().execute("SELECT from_date,to_date FROM leave_request WHERE id=?", (r["ext_of"],)).fetchone()
            rows["ext"].append({"project": r["project"], "engineer": r["name"], "original": f"{o['from_date']} to {o['to_date']}" if o else "", "extension": f"{r['from_date']} to {r['to_date']}", "status": r["status"]})
        if r["early_join"] and r["status"] != "cancelled":
            rows["early"].append({"project": r["project"], "engineer": r["name"], "leave": f"{r['from_date']} to {r['to_date']}", "joined": r["early_join"]})
        if r["status"] in ("approved", "pending"):
            rows["mix"].append(r)
        if (r["status"] == "withdraw_requested" or "withdraw" in (r["note"] or "")) and r["status"] != "cancelled":
            rows["withdraw"].append({"project": r["project"], "engineer": r["name"], "leave": f"{r['from_date']} to {r['to_date']}", "status": r["status"]})
    mix = {}
    for r in rows["mix"]:
        k = (r["project"], r["name"])
        mix.setdefault(k, {"project": r["project"], "engineer": r["name"], "planned": 0, "unplanned": 0})
        mix[k]["planned" if r["planned"] == "Planned" else "unplanned"] += r["days"]
    rows["mix"] = sorted(mix.values(), key=lambda x: (x["project"], x["engineer"]))
    return rows

def range_args():
    f = request.args.get("from") or (d_(today()) - timedelta(days=30)).isoformat()
    t = request.args.get("to") or (d_(today()) + timedelta(days=60)).isoformat()
    try: assert d_(f) <= d_(t) and (d_(t) - d_(f)).days <= 366
    except Exception: f, t = (d_(today()) - timedelta(days=30)).isoformat(), (d_(today()) + timedelta(days=60)).isoformat()
    return f, t

@app.route("/leaves/report")
@login_required
def wf_leave_report():
    if my_role() not in ("admin", "lead", "manager"): abort(403)
    pid = request.args.get("project", "")
    f, t = range_args()
    if pid and pid not in [p["id"] for p in my_projects()]: abort(404)
    rows = leave_report_data(pid, f, t)
    tot_planned = sum(x["planned"] for x in rows["mix"])
    tot_unplanned = sum(x["unplanned"] for x in rows["mix"])
    kpis = {
        "Capacity short days": len(rows["capacity"]),
        "SLA missed approvals": len(rows["late"]),
        "Leave extensions": len(rows["ext"]),
        "Early resumes": len(rows["early"]),
        "Total planned days": tot_planned,
        "Total unplanned days": tot_unplanned,
    }
    return render_template("leave_report.html", rows=rows, kpis=kpis, projects=my_projects(), pid=pid, f=f, t=t)

@app.route("/leaves/report.xlsx")
@login_required
def wf_leave_report_xlsx():
    if my_role() not in ("admin", "lead", "manager"): abort(403)
    pid = request.args.get("project", "")
    f, t = range_args()
    rows = leave_report_data(pid, f, t)
    wb = Workbook()
    first = True
    sheets = (("Capacity short", "capacity", ["project", "day", "total", "away", "available", "minimum", "pending"]),
              ("Approval overdue", "late", ["project", "engineer", "leave", "approver", "escalated_to", "at"]),
              ("Extensions", "ext", ["project", "engineer", "original", "extension", "status"]),
              ("Early joins", "early", ["project", "engineer", "leave", "joined"]),
              ("Planned vs unplanned (days)", "mix", ["project", "engineer", "planned", "unplanned"]),
              ("Withdraw requests", "withdraw", ["project", "engineer", "leave", "status"]))

    header_fill = PatternFill(start_color="1F3864", end_color="1F3864", fill_type="solid")
    header_font = Font(name="Arial", size=10, bold=True, color="FFFFFF")
    cell_font = Font(name="Arial", size=10)

    for title, key, cols in sheets:
        ws = wb.active if first else wb.create_sheet()
        first = False
        ws.title = title[:31]

        # Header row
        ws.append([c.replace("_", " ").title() for c in cols])
        for col_idx in range(1, len(cols) + 1):
            cell = ws.cell(row=1, column=col_idx)
            cell.fill = header_fill
            cell.font = header_font
            cell.alignment = Alignment(horizontal="center", vertical="center")

        # Data rows
        for r in rows[key]:
            row_vals = [r.get(c, "") for c in cols]
            ws.append(row_vals)
            cur_row = ws.max_row
            for col_idx in range(1, len(cols) + 1):
                cell = ws.cell(row=cur_row, column=col_idx)
                cell.font = cell_font
                cell.alignment = Alignment(vertical="center")

        # Auto-fit column widths
        for col in ws.columns:
            max_len = max(len(str(cell.value or "")) for cell in col)
            col_letter = get_column_letter(col[0].column)
            ws.column_dimensions[col_letter].width = max(max_len + 4, 12)

    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    return send_file(buf, as_attachment=True, download_name=f"leave_report_{f}_{t}.xlsx", mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

@app.route("/access")
@login_required
def access_page():
    if not is_admin(): abort(403, "Only an admin can manage access.")
    rows = [dict(r) for r in db().execute("SELECT * FROM access ORDER BY role DESC, email")]
    for r in rows:
        r["pids"] = {x["project_id"] for x in db().execute("SELECT project_id FROM project_access WHERE email=? AND kind=?", (r["email"], r["role"]))}
    return render_template("access.html", day=today(), rows=rows, projects=projects(), admins=sorted(ADMIN_EMAILS))

@app.route("/access/save", methods=["POST"])
@login_required
def access_save():
    if not is_admin(): abort(403)
    f = request.form; em = f.get("email", "").strip().lower(); role = f.get("role", "")
    nm = squash(f.get("name", ""))
    if not EMAIL_RE.match(em) or role not in ("manager", "lead") or (nm and not NAME_RE.match(nm)):
        flash("Give a valid email, a role, and a name made of letters only.", "err"); return redirect(url_for("access_page"))
    if f.get("action") == "remove":
        db().execute("DELETE FROM access WHERE email=?", (em,))
        db().execute("DELETE FROM project_access WHERE email=?", (em,))
        db().execute("UPDATE team SET active=0, assigned_to=CURRENT_TIMESTAMP, updated_by=?, updated_at=? WHERE lower(email)=? AND (lower(role) LIKE '%manager%' OR lower(role) LIKE '%lead%')", (*_stamp(), em))
    else:
        allp = 1 if role == "manager" and f.get("scope") == "all" else 0
        db().execute("""INSERT INTO access(email,name,role,all_projects) VALUES(?,?,?,?)
            ON CONFLICT(email) DO UPDATE SET name=excluded.name,role=excluded.role,all_projects=excluded.all_projects""",
            (em, nm, role, allp))
        if role == "lead":
            old_pids = [r["project_id"] for r in db().execute("SELECT project_id FROM project_access WHERE email=? AND kind='lead'", (em,))]
            valid = {p["id"] for p in projects(True)}
            new_pids = [pid for pid in f.getlist("projects") if pid in valid]
            removed_pids = set(old_pids) - set(new_pids)
            for rpid in removed_pids:
                db().execute("UPDATE team SET active=0, assigned_to=CURRENT_TIMESTAMP, updated_by=?, updated_at=? WHERE project_id=? AND lower(email)=? AND (lower(role) LIKE '%manager%' OR lower(role) LIKE '%lead%')",
                             (*_stamp(), str(rpid), em))
        db().execute("DELETE FROM project_access WHERE email=? AND kind=?", (em, role))
        valid = {p["id"] for p in projects(True)}
        for pid in f.getlist("projects"):
            if pid in valid:
                db().execute("INSERT INTO project_access(project_id,email,kind) VALUES(?,?,?) ON CONFLICT DO NOTHING", (pid, em, role))
                if role == "lead":
                    _sync_lead_as_member(pid, em, name=nm)
    db().commit(); flash("Access updated.", "ok")
    return redirect(url_for("access_page"))

@app.route("/settings")
@login_required
def settings_page():
    if not is_admin(): abort(403, "Only an administrator can access system settings.")
    configs = app_config.get_all_configs(db())
    return render_template("settings.html", configs=configs, day=today())

@app.route("/settings/save", methods=["POST"])
@login_required
def settings_save():
    if not is_admin(): abort(403)
    f = request.form
    admin_email = email()
    configs = app_config.get_all_configs(db())
    for c in configs:
        k = c["key"]
        dtype = c["data_type"]
        form_key = f"cfg_{k}"
        if dtype == "boolean":
            new_val = "true" if form_key in f else "false"
            app_config.set_config(db(), k, new_val, updated_by=admin_email)
        elif form_key in f:
            new_val = f.get(form_key, "").strip()
            app_config.set_config(db(), k, new_val, updated_by=admin_email)
    flash("Configuration settings updated successfully.", "ok")
    return redirect(url_for("settings_page"))

@app.route("/settings/test-email", methods=["POST"])
@login_required
def settings_test_email():
    if not is_admin(): return jsonify(ok=False, message="Unauthorized"), 403
    target_email = (request.form.get("email") or "").strip()
    if not target_email or not EMAIL_RE.match(target_email):
        return jsonify(ok=False, message="Please enter a valid email address.")
    ok, msg = mailer.send_test_email(target_email)
    return jsonify(ok=ok, message=msg)

if DEV:
    @app.route("/dev/as")
    def dev_as():
        """Demo mode only: act as another email to try the TL/PM and manager views."""
        em = request.args.get("email", "dev@example.com").strip().lower()
        session["user"] = {"email": em, "name": em, "login": em, "roles": [x for x in request.args.get("roles", "").split(",") if x]}
        return redirect(url_for("entry"))

# ---------------------------------------------------------------- team management
def _pid_or_403(pid):
    if not can_edit(pid): abort(403, "Only the lead of this project or an admin can do this.")
    return str(pid)

@app.route("/team")
@login_required
def team_page():
    ps = [p for p in my_projects() if can_edit(p["id"])]
    if not ps: return redirect(url_for("projects_page"))
    pid = request.args.get("project") or ps[0]["id"]; _pid_or_403(pid)
    tm = team(pid, active_only=False); have = {m["op_uid"] for m in tm if m["op_uid"]}
    
    # Enrich inactive members with current project status & filter out transferred engineers (Option 1)
    visible_tm = []
    for m in tm:
        m["other_project"] = None
        if not m["active"]:
            u = None
            if m.get("user_id"):
                u = db().execute("SELECT current_project_id FROM app_users WHERE id=?", (m["user_id"],)).fetchone()
            elif m.get("email"):
                u = db().execute("SELECT current_project_id FROM app_users WHERE lower(email)=?", (m["email"].lower(),)).fetchone()
            if u and u["current_project_id"] and str(u["current_project_id"]) != str(pid):
                cp = proj(u["current_project_id"])
                m["other_project"] = cp["name"] if cp else f"Project {u['current_project_id']}"
                # Transferred to another project: hide from this project's active team list
                continue
        visible_tm.append(m)
    tm = visible_tm

    try:
        sync_keycloak_users()
    except Exception:
        pass

    active_user_ids = {m["user_id"] for m in tm if m["active"] and m.get("user_id")}
    active_emails = {m["email"].lower() for m in tm if m["active"] and m.get("email")}

    available_keycloak_users = [
        dict(r) for r in db().execute("""
            SELECT u.id, u.name, u.email, u.phone, u.role_title, u.current_project_id, p.name as current_project_name
            FROM app_users u
            LEFT JOIN project p ON u.current_project_id = p.id
            WHERE u.active = 1 AND u.role_title NOT IN ('Admin')
            ORDER BY (CASE WHEN u.current_project_id IS NULL THEN 0 ELSE 1 END), lower(u.name)
        """).fetchall()
        if r["id"] not in active_user_ids and (not r["email"] or r["email"].lower() not in active_emails)
    ]

    bench = [dict(r) for r in db().execute("""
        SELECT id, name, email, phone, role_title, current_shift_start
        FROM app_users
        WHERE active = 1 AND current_project_id IS NULL AND role_title NOT IN ('Admin', 'Project Manager')
        ORDER BY lower(name)
    """).fetchall()]
    all_engineers = []
    if is_admin():
        all_engineers = [dict(r) for r in db().execute("""
            SELECT u.id, u.name, u.email, u.role_title, u.current_project_id, p.name as project_name
            FROM app_users u
            LEFT JOIN project p ON u.current_project_id = p.id
            WHERE u.active = 1 AND u.role_title NOT IN ('Admin', 'Project Manager')
            ORDER BY lower(u.name)
        """).fetchall()]
    ms = members(pid)
    next_url = url_for("team_page", project=pid)
    upcoming_leaves = get_upcoming_leaves(pid)
    cur_p = next((p for p in ps if str(p["id"]) == str(pid)), None)
    cur_pname = cur_p["name"] if cur_p else str(pid)
    all_pr_list = [{"id": str(p["id"]), "name": p["name"]} for p in projects()]
    return render_template("team.html", day=today(), projects=ps, pid=pid, cur_pname=cur_pname, team=tm, members=ms, covers=cover_choices(pid),
                           leave_types=LEAVE_TYPES, can_edit_proj=(is_admin() or can_edit(pid)), next_url=next_url,
                           candidates=[m for m in op_candidates(pid) if m["id"] not in have], linked=bool(proj(pid)["op_id"]),
                           bench=bench, all_engineers=all_engineers, all_projects=all_pr_list, is_admin=is_admin(), shift_start=SHIFT_START,
                           upcoming_leaves=upcoming_leaves)

@app.route("/api/users/search")
@login_required
def api_users_search():
    q = (request.args.get("q") or "").strip()
    pid = request.args.get("project", "")
    if not q:
        return jsonify([])
    
    try:
        sync_keycloak_users()
    except Exception:
        pass
    
    term = f"%{q.lower()}%"
    rows = db().execute("""
        SELECT u.id, u.name, u.email, u.phone, u.role_title, u.current_project_id, u.current_shift_start, p.name as current_project_name
        FROM app_users u
        LEFT JOIN project p ON u.current_project_id = p.id
        WHERE u.active = 1 
          AND (lower(u.email) LIKE ? OR lower(u.name) LIKE ? OR lower(u.username) LIKE ?)
        ORDER BY (CASE WHEN u.current_project_id IS NULL THEN 0 ELSE 1 END), lower(u.name)
        LIMIT 20
    """, (term, term, term)).fetchall()
    
    results = []
    for r in rows:
        status_label = "Bench Pool"
        if r["current_project_id"]:
            if pid and str(r["current_project_id"]) == str(pid):
                status_label = "Already on this project"
            else:
                status_label = f"Active in: {r['current_project_name'] or 'Project ' + str(r['current_project_id'])}"
        
        results.append({
            "id": r["id"],
            "name": r["name"],
            "email": r["email"] or "",
            "phone": r["phone"] or "",
            "role": r["role_title"] or "Developer",
            "current_project_id": r["current_project_id"],
            "current_project_name": r["current_project_name"] or "",
            "current_shift_start": r["current_shift_start"] or SHIFT_START,
            "status": status_label,
            "is_current_project": bool(pid and str(r["current_project_id"]) == str(pid)),
            "is_other_project": bool(r["current_project_id"] and str(r["current_project_id"]) != str(pid))
        })
    return jsonify(results)

def _stamp(): return ((current_user() or {}).get("email", ""), datetime.now(TZ).isoformat(timespec="seconds"))

def _mail_free(pid, mail, skip=""):
    d = mail and db().execute("SELECT name FROM team WHERE project_id=? AND lower(email)=? AND active=1 AND member_id<>?", (pid, mail, skip)).fetchone()
    if d: raise ValueError(f"This email is already used by {d['name']} in this project.")

def _phone_taken(pid, phone, skip=""):
    return db().execute("SELECT name FROM team WHERE project_id=? AND phone=? AND active=1 AND member_id<>?", (pid, phone, skip)).fetchone()

@app.route("/team/assign_bench", methods=["POST"])
@login_required
def team_assign_bench():
    pid = _pid_or_403(request.form.get("project", ""))
    uid = request.form.get("user_id")
    if not uid:
        flash("Invalid engineer selected.", "err")
        return redirect(url_for("team_page", project=pid))
    
    u = db().execute("SELECT * FROM app_users WHERE id=? AND active=1", (uid,)).fetchone()
    if not u:
        flash("Engineer not found or inactive.", "err")
        return redirect(url_for("team_page", project=pid))
    
    if u["current_project_id"]:
        cp = proj(u["current_project_id"])
        pname = cp["name"] if cp else f"Project {u['current_project_id']}"
        flash(f"Conflict: {u['name']} is already assigned to '{pname}'. An engineer can only belong to one active project.", "err")
        return redirect(url_for("team_page", project=pid))
    
    # 1. Update central user active project
    db().execute("UPDATE app_users SET current_project_id=?, updated_at=CURRENT_TIMESTAMP WHERE id=?", (pid, uid))
    
    # 2. Check if engineer already had a record in team for this project
    existing_tm = db().execute("SELECT member_id FROM team WHERE project_id=? AND (user_id=? OR (email IS NOT NULL AND email<>'' AND lower(email)=?))",
                               (pid, uid, (u["email"] or "").lower())).fetchone()
    mid = existing_tm["member_id"] if existing_tm else "m:" + secrets.token_hex(6)
    shift = u["current_shift_start"] or SHIFT_START
    db().execute("""
        INSERT INTO team(project_id, member_id, name, role, phone, email, shift_start, active, user_id, updated_by, updated_at, assigned_from, assigned_to)
        VALUES (?, ?, ?, ?, ?, ?, ?, 1, ?, ?, ?, CURRENT_TIMESTAMP, NULL)
        ON CONFLICT(project_id, member_id) DO UPDATE 
        SET active=1, name=EXCLUDED.name, role=EXCLUDED.role, phone=EXCLUDED.phone, 
            email=EXCLUDED.email, user_id=EXCLUDED.user_id, updated_by=EXCLUDED.updated_by, updated_at=EXCLUDED.updated_at,
            assigned_from=CURRENT_TIMESTAMP, assigned_to=NULL
    """, (pid, mid, u["name"], u["role_title"] or "", u["phone"] or "", u["email"] or "", shift, uid, *_stamp()))
    
    db().commit()
    flash(f"Assigned {u['name']} from the bench pool to this project.", "ok")
    return redirect(url_for("team_page", project=pid))

@app.route("/admin/transfer_engineer", methods=["POST"])
@login_required
def admin_transfer_engineer():
    if not is_admin():
        abort(403, "Only administrators can transfer engineers between projects.")
    uid = request.form.get("user_id")
    target_pid = request.form.get("target_project")
    if not uid or not target_pid:
        flash("Invalid transfer request.", "err")
        return redirect(url_for("projects_page"))
    
    u = db().execute("SELECT * FROM app_users WHERE id=?", (uid,)).fetchone()
    if not u:
        flash("Engineer not found.", "err")
        return redirect(url_for("projects_page"))
    
    tp = proj(target_pid)
    if not tp:
        flash("Target project not found.", "err")
        return redirect(url_for("projects_page"))
    
    if str(u["current_project_id"]) == str(target_pid):
        flash(f"{u['name']} is already assigned to '{tp['name']}'.", "err")
        return redirect(url_for("team_page", project=target_pid))
    
    old_pid = u["current_project_id"]
    if old_pid:
        db().execute("UPDATE team SET active=0, assigned_to=CURRENT_TIMESTAMP, updated_by=?, updated_at=? WHERE project_id=? AND (user_id=? OR (email IS NOT NULL AND email<>'' AND lower(email)=?))",
                     (*_stamp(), str(old_pid), uid, (u["email"] or "").lower()))
        if u["email"]:
            db().execute("DELETE FROM project_access WHERE project_id=? AND lower(email)=?", (str(old_pid), u["email"].lower()))
    
    db().execute("UPDATE app_users SET current_project_id=?, updated_at=CURRENT_TIMESTAMP WHERE id=?", (target_pid, uid))
    
    existing_tm = db().execute("SELECT member_id FROM team WHERE project_id=? AND (user_id=? OR (email IS NOT NULL AND email<>'' AND lower(email)=?))",
                               (str(target_pid), uid, (u["email"] or "").lower())).fetchone()
    mid = existing_tm["member_id"] if existing_tm else "m:" + secrets.token_hex(6)
    shift = u["current_shift_start"] or SHIFT_START
    db().execute("""
        INSERT INTO team(project_id, member_id, name, role, phone, email, shift_start, active, user_id, updated_by, updated_at, assigned_from, assigned_to)
        VALUES (?, ?, ?, ?, ?, ?, ?, 1, ?, ?, ?, CURRENT_TIMESTAMP, NULL)
        ON CONFLICT(project_id, member_id) DO UPDATE 
        SET active=1, name=EXCLUDED.name, role=EXCLUDED.role, phone=EXCLUDED.phone, 
            email=EXCLUDED.email, user_id=EXCLUDED.user_id, updated_by=EXCLUDED.updated_by, updated_at=EXCLUDED.updated_at,
            assigned_from=CURRENT_TIMESTAMP, assigned_to=NULL
    """, (str(target_pid), mid, u["name"], u["role_title"] or "", u["phone"] or "", u["email"] or "", shift, uid, *_stamp()))
    
    if _is_pm_role(u["role_title"]) and u["email"]:
        db().execute("INSERT INTO project_access(project_id, email, kind) VALUES (?, ?, 'lead') ON CONFLICT DO NOTHING", (str(target_pid), u["email"].lower()))
        db().execute("INSERT INTO project_access(project_id, email, kind) VALUES (?, ?, 'pm') ON CONFLICT DO NOTHING", (str(target_pid), u["email"].lower()))
        keycloak_assign_realm_role(u["email"].lower(), "project-manager")
    
    redirect_pid = request.form.get("current_project") or target_pid
    db().commit()
    try:
        sites = mobile_site_rows(target_pid) if "mobile_site_rows" in globals() else []
        pm_leads = [r["email"] for r in db().execute("SELECT email FROM project_access WHERE project_id=? AND kind='lead'", (str(target_pid),)).fetchall() if r["email"]]
        mailer.notify_project_assignment(u["email"], u["name"], tp["name"], u["role_title"], sites=sites)
        for pme in pm_leads:
            mailer.notify_new_team_member(pme, "Project Manager", u["name"], u["email"], u["role_title"], tp["name"])
    except Exception as ex:
        app.logger.warning("mailer transfer notify error: %s", ex)
    flash(f"Successfully transferred {u['name']} to project '{tp['name']}'.", "ok")
    return redirect(url_for("team_page", project=redirect_pid))

def _is_pm_role(role_title):
    r = (role_title or "").strip().lower()
    return any(k in r for k in ("project manager", "team lead", "lead", "pm")) and "admin" not in r

@app.route("/team/add", methods=["POST"])
@login_required
def team_add():
    pid = _pid_or_403(request.form.get("project", "")); n = 0; f = request.form
    by_id = {m["id"]: m for m in op_candidates(pid)}
    for uid in f.getlist("op"):
        if uid in by_id:
            db().execute("""INSERT INTO team(project_id,member_id,name,role,op_user_id,active,updated_by,updated_at) VALUES(?,?,?,?,?,1,?,?)
                ON CONFLICT(project_id,member_id) DO UPDATE SET active=1""", (pid, "op:" + uid, by_id[uid]["name"], "", uid, *_stamp())); n += 1

    if f.get("user_id"):
        uid = f.get("user_id")
        u = db().execute("SELECT * FROM app_users WHERE id=? AND active=1", (uid,)).fetchone()
        if not u:
            flash("Selected Keycloak engineer not found or inactive.", "err")
            return redirect(url_for("team_page", project=pid))
        
        if u["current_project_id"] and str(u["current_project_id"]) == str(pid):
            shift = (f.get("shift") or "").strip() or u.get("current_shift_start") or SHIFT_START
            db().execute("UPDATE app_users SET current_shift_start=?, updated_at=CURRENT_TIMESTAMP WHERE id=?", (shift, uid))
            db().execute("UPDATE team SET shift_start=?, updated_by=?, updated_at=? WHERE project_id=? AND (user_id=? OR (email IS NOT NULL AND email<>'' AND lower(email)=?))",
                         (shift, *_stamp(), pid, uid, (u["email"] or "").lower()))
            db().commit()
            flash(f"Updated shift start time for {u['name']}.", "ok")
            return redirect(url_for("team_page", project=pid))
        
        is_transfer = False
        if u["current_project_id"] and str(u["current_project_id"]) != str(pid):
            if is_admin():
                is_transfer = True
                old_pid = u["current_project_id"]
                if old_pid:
                    db().execute("UPDATE team SET active=0, assigned_to=CURRENT_TIMESTAMP, updated_by=?, updated_at=? WHERE project_id=? AND (user_id=? OR (email IS NOT NULL AND email<>'' AND lower(email)=?))",
                                 (*_stamp(), str(old_pid), uid, (u["email"] or "").lower()))
                    if u["email"]:
                        db().execute("DELETE FROM project_access WHERE project_id=? AND lower(email)=?", (str(old_pid), u["email"].lower()))
            else:
                cp = proj(u["current_project_id"])
                pname = cp["name"] if cp else f"Project {u['current_project_id']}"
                flash(f"Conflict: {u['name']} is already assigned to '{pname}'. An engineer can only belong to one active project. Please request an Admin transfer.", "err")
                return redirect(url_for("team_page", project=pid))
        
        role = (f.get("role") or "").strip() or u["role_title"] or "Engineer"
        shift = (f.get("shift") or "").strip() or u.get("current_shift_start") or SHIFT_START
        is_pm = _is_pm_role(role)
        target_sys_role = "project-manager" if is_pm else (u.get("system_role") or "member")
        
        db().execute("""
            UPDATE app_users 
            SET current_project_id=?, role_title=?, current_shift_start=?, system_role=?, updated_at=CURRENT_TIMESTAMP 
            WHERE id=?
        """, (pid, role, shift, target_sys_role, uid))
        
        if is_pm and u["email"]:
            db().execute("INSERT INTO project_access(project_id, email, kind) VALUES (?, ?, 'lead') ON CONFLICT DO NOTHING", (str(pid), u["email"].lower()))
            db().execute("INSERT INTO project_access(project_id, email, kind) VALUES (?, ?, 'pm') ON CONFLICT DO NOTHING", (str(pid), u["email"].lower()))
            keycloak_assign_realm_role(u["email"].lower(), "project-manager")
        
        existing_tm = db().execute("SELECT member_id FROM team WHERE project_id=? AND (user_id=? OR (email IS NOT NULL AND email<>'' AND lower(email)=?))",
                                   (pid, uid, (u["email"] or "").lower())).fetchone()
        mid = existing_tm["member_id"] if existing_tm else "m:" + secrets.token_hex(6)
        db().execute("""
            INSERT INTO team(project_id, member_id, name, role, phone, email, shift_start, active, user_id, updated_by, updated_at, assigned_from, assigned_to)
            VALUES (?, ?, ?, ?, ?, ?, ?, 1, ?, ?, ?, CURRENT_TIMESTAMP, NULL)
            ON CONFLICT(project_id, member_id) DO UPDATE 
            SET active=1, name=EXCLUDED.name, role=EXCLUDED.role, phone=EXCLUDED.phone, 
                email=EXCLUDED.email, user_id=EXCLUDED.user_id, shift_start=EXCLUDED.shift_start, updated_by=EXCLUDED.updated_by, updated_at=EXCLUDED.updated_at,
                assigned_from=CURRENT_TIMESTAMP, assigned_to=NULL
        """, (pid, mid, u["name"], role, u["phone"] or "", u["email"] or "", shift, uid, *_stamp()))
        
        db().commit()
        msg = f"Successfully transferred and assigned {u['name']} to project." if is_transfer else f"Assigned {u['name']} to project."
        flash(msg, "ok")
        return redirect(url_for("team_page", project=pid))
    if any(f.get(k, "").strip() for k in ("name", "role", "phone", "email")):
        try:
            name, role, phone, mail, shift = v_name(f.get("name")), v_role(f.get("role")), v_phone(f.get("phone")), v_mail(f.get("email")), v_shift(f.get("shift"))
            dup = _phone_taken(pid, phone)
            if dup: raise ValueError(f"This contact number is already used by {dup['name']} in this project.")
            _mail_free(pid, mail)
            if any(m["name"].lower() == name.lower() for m in team(pid)): raise ValueError(f"{name} is already in this team.")
        except ValueError as ex:
            db().commit(); flash(f"Not added - {ex}", "err"); return redirect(url_for("team_page", project=pid))
        
        # Central User Management & Single-Project Conflict Check
        u_existing = None
        if mail:
            u_existing = db().execute("SELECT * FROM app_users WHERE lower(email)=?", (mail.lower(),)).fetchone()
        if not u_existing and phone:
            u_existing = db().execute("SELECT * FROM app_users WHERE phone=?", (phone,)).fetchone()
        
        if u_existing:
            # Check existing project assignment
            if u_existing["current_project_id"] and str(u_existing["current_project_id"]) != str(pid):
                cp = proj(u_existing["current_project_id"])
                pname = cp["name"] if cp else f"Project {u_existing['current_project_id']}"
                flash(f"Conflict: This email/phone is already registered to {u_existing['name']} ({u_existing['email'] or u_existing['phone']}), who is actively assigned to '{pname}'. Single-project model allows only one active project per engineer. Please request an Admin transfer.", "err")
                return redirect(url_for("team_page", project=pid))
            elif u_existing["current_project_id"] and str(u_existing["current_project_id"]) == str(pid):
                flash(f"{u_existing['name']} is already actively assigned to this project.", "err")
                return redirect(url_for("team_page", project=pid))
            else:
                # On the bench! Assign them to this project
                is_pm = _is_pm_role(role)
                target_sys_role = "project-manager" if is_pm else (u_existing.get("system_role") or "member")
                db().execute("UPDATE app_users SET current_project_id=?, role_title=coalesce(nullif(?, ''), role_title), system_role=?, updated_at=CURRENT_TIMESTAMP WHERE id=?", (pid, role, target_sys_role, u_existing["id"]))
                if is_pm and (mail or u_existing.get("email")):
                    em_val = (mail or u_existing.get("email") or "").lower()
                    if em_val:
                        db().execute("INSERT INTO project_access(project_id, email, kind) VALUES (?, ?, 'lead') ON CONFLICT DO NOTHING", (str(pid), em_val))
                        db().execute("INSERT INTO project_access(project_id, email, kind) VALUES (?, ?, 'pm') ON CONFLICT DO NOTHING", (str(pid), em_val))
                existing_tm = db().execute("SELECT member_id FROM team WHERE project_id=? AND (user_id=? OR (email IS NOT NULL AND email<>'' AND lower(email)=?))",
                                           (pid, u_existing["id"], (mail or u_existing["email"] or "").lower())).fetchone()
                mid = existing_tm["member_id"] if existing_tm else "m:" + secrets.token_hex(6)
                db().execute("""
                    INSERT INTO team(project_id, member_id, name, role, phone, email, shift_start, active, user_id, updated_by, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, 1, ?, ?, ?)
                    ON CONFLICT(project_id, member_id) DO UPDATE 
                    SET active=1, name=EXCLUDED.name, role=EXCLUDED.role, phone=EXCLUDED.phone, 
                        email=EXCLUDED.email, user_id=EXCLUDED.user_id, updated_by=EXCLUDED.updated_by, updated_at=EXCLUDED.updated_at
                """, (pid, mid, name, role, phone, mail or u_existing["email"], shift, u_existing["id"], *_stamp()))
                db().commit()
                flash(f"Assigned existing engineer {u_existing['name']} from the bench pool to this project.", "ok")
                return redirect(url_for("team_page", project=pid))
        else:
            # Brand new employee
            parts = (name or "").strip().split()
            fn = parts[0] if parts else ""
            ln = " ".join(parts[1:]) if len(parts) > 1 else ""
            temp_pass = E("KEYCLOAK_DEFAULT_TEMP_PASSWORD", "Keenable@2026")
            is_pm = _is_pm_role(role)
            target_sys_role = "project-manager" if is_pm else "member"
            
            cur = db().execute("""
                INSERT INTO app_users(username, email, name, first_name, last_name, phone, role_title, system_role,
                                      password_hash, must_change_password, totp_enabled, current_project_id, current_shift_start, active)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, crypt(?, gen_salt('bf', 10)), true, false, ?, ?, 1)
                RETURNING id
            """, (mail.lower() if mail else phone, mail.lower() if mail else "", name, fn, ln, phone, role, target_sys_role, temp_pass, pid, shift))
            new_uid = cur.fetchone()["id"]
            
            mid = "m:" + secrets.token_hex(6)
            db().execute("INSERT INTO team(project_id,member_id,name,role,phone,email,shift_start,op_user_id,active,user_id,updated_by,updated_at) VALUES(?,?,?,?,?,?,?,'',1,?,?,?)",
                         (pid, mid, name, role, phone, mail, shift, new_uid, *_stamp()))
            
            if is_pm and mail:
                db().execute("INSERT INTO project_access(project_id, email, kind) VALUES (?, ?, 'lead') ON CONFLICT DO NOTHING", (str(pid), mail.lower()))
                db().execute("INSERT INTO project_access(project_id, email, kind) VALUES (?, ?, 'pm') ON CONFLICT DO NOTHING", (str(pid), mail.lower()))
            db().commit()

            # 1. Machine-to-Machine Provisioning in Keycloak
            if mail:
                keycloak_create_user(mail, name)
                if is_pm:
                    keycloak_assign_realm_role(mail, "project-manager")

            # 2. Asynchronous Welcome & Credentials Email Dispatch
            cp = proj(pid)
            pname = cp["name"] if cp else f"Project {pid}"
            if mail:
                send_welcome_email_async(mail, name, role, pname, temp_pass)
                flash(f"Added {name} to project. Central account created and onboarding email sent to {mail}!", "ok")
            else:
                flash(f"Added {name} to project. Central account created! Temporary password: {temp_pass}", "ok")
            return redirect(url_for("team_page", project=pid))

    db().commit(); flash(f"Added {n} member{'s' if n != 1 else ''}." if n else "Nothing to add.", "ok" if n else "err")
    return redirect(url_for("team_page", project=pid))

@app.route("/team/update", methods=["POST"])
@login_required
def team_update():
    f = request.form; pid = _pid_or_403(f.get("project", "")); mid, act = f.get("member", ""), f.get("action", "save")
    if act == "remove":
        tm_row = db().execute("SELECT user_id, name, email, role FROM team WHERE project_id=? AND member_id=?", (pid, mid)).fetchone()
        if not is_admin() and tm_row and tm_row["email"] and tm_row["email"].lower() == email():
            flash("A Project Manager cannot remove themselves from their project. An administrator must reassign the project lead.", "err")
            return redirect(url_for("team_page", project=pid))
        db().execute("UPDATE team SET active=0, assigned_to=CURRENT_TIMESTAMP, updated_by=?, updated_at=? WHERE project_id=? AND member_id=?", (*_stamp(), pid, mid))
        if tm_row and tm_row["user_id"]:
            db().execute("UPDATE app_users SET current_project_id=NULL, updated_at=CURRENT_TIMESTAMP WHERE id=? AND current_project_id=?", (tm_row["user_id"], pid))
        elif tm_row and tm_row["email"]:
            db().execute("UPDATE app_users SET current_project_id=NULL, updated_at=CURRENT_TIMESTAMP WHERE lower(email)=? AND current_project_id=?", (tm_row["email"].lower(), pid))
        
        if tm_row and tm_row["email"]:
            db().execute("DELETE FROM project_access WHERE project_id=? AND lower(email)=?", (str(pid), tm_row["email"].lower()))
            other_leads = db().execute("SELECT count(*) as cnt FROM project_access WHERE lower(email)=? AND kind IN ('lead', 'pm')", (tm_row["email"].lower(),)).fetchone()
            if not other_leads or other_leads["cnt"] == 0:
                db().execute("UPDATE app_users SET system_role='member', updated_at=CURRENT_TIMESTAMP WHERE lower(email)=? AND system_role='project-manager'", (tm_row["email"].lower(),))
                keycloak_remove_realm_role(tm_row["email"].lower(), "project-manager")
        
        db().commit()
        flash("Removed member from project and released them to the Available Engineers pool.", "ok")
        return redirect(url_for("team_page", project=pid))
    elif act == "restore":
        tm_row = db().execute("SELECT user_id, name, email FROM team WHERE project_id=? AND member_id=?", (pid, mid)).fetchone()
        u = None
        if tm_row and tm_row["user_id"]:
            u = db().execute("SELECT id, name, current_project_id FROM app_users WHERE id=?", (tm_row["user_id"],)).fetchone()
        elif tm_row and tm_row["email"]:
            u = db().execute("SELECT id, name, current_project_id FROM app_users WHERE lower(email)=?", (tm_row["email"].lower(),)).fetchone()
        
        if u and u["current_project_id"] and str(u["current_project_id"]) != str(pid):
            cp = proj(u["current_project_id"])
            pname = cp["name"] if cp else f"Project {u['current_project_id']}"
            flash(f"Cannot restore: {u['name']} is currently actively assigned to '{pname}'. An engineer can only belong to one active project.", "err")
            return redirect(url_for("team_page", project=pid))
        
        db().execute("UPDATE team SET active=1, assigned_from=CURRENT_TIMESTAMP, assigned_to=NULL, updated_by=?, updated_at=? WHERE project_id=? AND member_id=?", (*_stamp(), pid, mid))
        if u:
            db().execute("UPDATE app_users SET current_project_id=?, updated_at=CURRENT_TIMESTAMP WHERE id=?", (pid, u["id"]))
        db().commit()
        flash("Team updated. Member restored to project.", "ok")
        return redirect(url_for("team_page", project=pid))
    else:
        tm_row = db().execute("SELECT * FROM team WHERE project_id=? AND member_id=?", (pid, mid)).fetchone()
        if not tm_row:
            flash("Team member not found.", "err")
            return redirect(url_for("team_page", project=pid))
        
        try:
            shift = v_shift(f.get("shift") or tm_row.get("shift_start") or SHIFT_START)
        except ValueError as ex:
            flash(f"Not saved - {ex}", "err"); return redirect(url_for("team_page", project=pid))
        
        db().execute("UPDATE team SET shift_start=?, updated_by=?, updated_at=? WHERE project_id=? AND member_id=?",
                     (shift, *_stamp(), pid, mid))
        
        if tm_row.get("user_id"):
            db().execute("UPDATE app_users SET current_shift_start=?, updated_at=CURRENT_TIMESTAMP WHERE id=?", (shift, tm_row["user_id"]))
        elif tm_row.get("email"):
            db().execute("UPDATE app_users SET current_shift_start=?, updated_at=CURRENT_TIMESTAMP WHERE lower(email)=?", (shift, tm_row["email"].lower()))
        
        db().commit()
        flash(f"Updated shift time for {tm_row['name']} to {shift}.", "ok")
        return redirect(url_for("team_page", project=pid))

# ---------------------------------------------------------------- an engineer's own attendance
DUTY_STATUSES = ("Present", "WFH", "Half Day")

@app.route("/checkin")
@login_required
def checkin():
    return redirect(url_for("me"))

@app.route("/me/attendance", methods=["POST"])
@login_required
def me_attendance():
    mids = my_member_ids()
    if not mids:
        flash("Your account is not assigned to an active project team yet.", "err")
        return redirect(url_for("me"))
    ph = ",".join("?" * len(mids))
    active_tm = db().execute(
        f"SELECT t.member_id, t.name, t.role, t.shift_start, t.project_id, p.name AS project_name "
        f"FROM team t JOIN project p ON CAST(p.id AS TEXT)=t.project_id "
        f"WHERE t.member_id IN ({ph}) AND t.active=1 ORDER BY t.updated_at DESC LIMIT 1",
        mids
    ).fetchone()
    if not active_tm:
        flash("You are currently unassigned (on the bench) and cannot log project attendance.", "err")
        return redirect(url_for("me"))

    td = today()
    submitted_day = (request.form.get("day") or td).strip()
    if submitted_day != td:
        flash("Self-service attendance can only be logged for today.", "err")
        return redirect(url_for("me"))

    existing = db().execute(
        f"SELECT * FROM attendance WHERE day=? AND user_id IN ({ph}) ORDER BY updated_at DESC LIMIT 1",
        (td, *mids)
    ).fetchone()
    if existing:
        ex_app = (existing["approval_status"] if "approval_status" in existing.keys() else "") or ""
        if ex_app == "Approved" and (existing.get("in_time") or existing.get("leave_type") or existing.get("remarks")):
            flash("Today's attendance has already been verified and locked by your PM/TL.", "err")
            return redirect(url_for("me"))

    in_time = (request.form.get("in_time") or "").strip()
    out_time = (request.form.get("out_time") or "").strip()
    leave_type = (request.form.get("leave_type") or "").strip()
    planned = (request.form.get("planned") or "").strip()
    cover = (request.form.get("cover") or "").strip()
    remarks = (request.form.get("remarks") or "").strip()[:300]

    if (in_time and mins(in_time) is None) or (out_time and mins(out_time) is None):
        flash("Invalid time format. Please use HH:MM.", "err")
        return redirect(url_for("me"))
    if out_time and not in_time:
        flash("Out Time cannot be given without In Time.", "err")
        return redirect(url_for("me"))

    shift = active_tm["shift_start"] or SHIFT_START
    own_min = mins(shift) if shift else mins(SHIFT_START)
    if in_time and out_time and mins(out_time) < mins(in_time) and not is_night(own_min):
        flash("Out Time cannot be earlier than In Time.", "err")
        return redirect(url_for("me"))

    if leave_type and leave_type not in LEAVE_TYPES:
        flash("Invalid leave type selected.", "err")
        return redirect(url_for("me"))

    pid = active_tm["project_id"]
    stored_today = records(td)
    on_leave_today = {r["user_name"] for u, r in stored_today.items() if u not in mids and r.get("leave_type")}
    allowed_cover = {m["name"] for m in cover_choices(pid) if m["id"] not in mids and m["name"] != active_tm["name"]}

    if not leave_type:
        planned, cover = "", ""
    else:
        if planned not in ("Planned", "Unplanned"):
            planned = "Unplanned"
        if cover and cover in on_leave_today:
            flash(f"{cover} is also on leave today, so cannot handle your tasks. Saved without cover person.", "err")
            cover = ""
        elif cover and cover not in allowed_cover and cover != ((existing["handled_by"] if existing else "") or ""):
            cover = ""

    target_uid = existing["user_id"] if existing else active_tm["member_id"]
    if not any([in_time, out_time, leave_type, remarks]):
        if existing and ((existing["approval_status"] if "approval_status" in existing.keys() else "") == "Pending"):
            db().execute("DELETE FROM attendance WHERE day=? AND user_id=?", (td, target_uid))
            db().execute("DELETE FROM approval WHERE day=? AND user_id=?", (td, target_uid))
            db().commit()
            flash("Cleared today's unverified attendance entry.", "ok")
        else:
            flash("Please enter your In Time or select a Leave Type to submit today's attendance.", "err")
        return redirect(url_for("me"))

    duty_status = "Half Day" if leave_type == "Half Day" else "Present"
    now_iso = datetime.now(TZ).isoformat(timespec="seconds")
    who = email()

    db().execute("""
        INSERT INTO attendance(
            day, user_id, user_name, in_time, out_time, leave_type, planned, handled_by,
            remarks, updated_by, updated_at, shift_start, duty_status, approval_status, rejection_reason, submitted_by, approved_by, approved_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'Pending', '', ?, '', '')
        ON CONFLICT(day, user_id) DO UPDATE SET
            user_name=excluded.user_name,
            in_time=excluded.in_time,
            out_time=excluded.out_time,
            leave_type=excluded.leave_type,
            planned=excluded.planned,
            handled_by=excluded.handled_by,
            remarks=excluded.remarks,
            updated_by=excluded.updated_by,
            updated_at=excluded.updated_at,
            shift_start=excluded.shift_start,
            duty_status=excluded.duty_status,
            approval_status='Pending',
            rejection_reason='',
            submitted_by=excluded.submitted_by,
            approved_by='',
            approved_at=''
    """, (td, target_uid, active_tm["name"], in_time, out_time, leave_type, planned, cover, remarks, who, now_iso, shift, duty_status, who))

    # Immediately create/update approval record and notify assigned PM/TL
    hrs = hours()
    appr = approver_for(pid, td)
    due_iso = (mnow() + timedelta(hours=hrs)).isoformat(timespec="seconds")
    db().execute("""
        INSERT INTO approval(day, user_id, project_id, source, status, assigned_to, created_at, due_at)
        VALUES (?, ?, ?, 'engineer', 'pending', ?, ?, ?)
        ON CONFLICT(day, user_id) DO UPDATE SET
            status='pending', source='engineer', project_id=excluded.project_id,
            assigned_to=excluded.assigned_to, created_at=excluded.created_at, due_at=excluded.due_at,
            decided_by=NULL, decided_at=NULL, note=NULL, escalated_at=NULL
    """, (td, target_uid, pid, appr, now_iso, due_iso))

    if appr:
        in_out_str = f"IN {in_time or '--:--'} / OUT {out_time or '--:--'}" if (in_time or out_time) else (leave_type or "Attendance")
        notify([appr], "attendance_pending",
               f"Attendance approval needed: {active_tm['name']} ({td})",
               f"{active_tm['name']} submitted attendance ({in_out_str}). Waiting for your approval.",
               "/approvals")

    db().commit()

    flash("Today's attendance has been saved and marked as Submitted (Pending PM/TL Approval).", "ok")
    return redirect(url_for("me"))

@app.route("/me")
@login_required
def me():
    mids = my_member_ids()
    if not mids: return render_template("message.html", msg="Your account is not assigned to a project team yet. Ask your TL/PM or Administrator to assign you from the Available Engineers pool on the Team page.")
    month = request.args.get("month") or today()[:7]
    try: datetime.strptime(month, "%Y-%m")
    except ValueError: abort(400, "Bad month")
    y, mo = map(int, month.split("-")); nd = calendar.monthrange(y, mo)[1]; td = today(); ph = ",".join("?" * len(mids))
    recs = {r["day"]: dict(r) for r in db().execute(f"SELECT * FROM attendance WHERE user_id IN ({ph}) AND day LIKE ?", (*mids, month + "-%"))}
    by = {}; entered = entered_checker()
    for r in db().execute("SELECT day, user_id FROM attendance WHERE day LIKE ?", (month + "-%",)): by.setdefault(r["day"], set()).add(r["user_id"])
    info = db().execute(f"SELECT max(t.name) AS name, max(t.role) AS role, max(t.shift_start) AS shift, {AGG}(p.name, ', ') AS projects FROM team t JOIN project p ON CAST(p.id AS TEXT)=t.project_id WHERE t.member_id IN ({ph})", mids).fetchone()

    active_tm = db().execute(
        f"SELECT t.member_id, t.name, t.role, t.shift_start, t.project_id, p.name AS project_name "
        f"FROM team t JOIN project p ON CAST(p.id AS TEXT)=t.project_id "
        f"WHERE t.member_id IN ({ph}) AND t.active=1 ORDER BY t.updated_at DESC LIMIT 1",
        mids
    ).fetchone()
    today_row = db().execute(
        f"SELECT * FROM attendance WHERE day=? AND user_id IN ({ph}) ORDER BY updated_at DESC LIMIT 1",
        (td, *mids)
    ).fetchone()
    today_rec = dict(today_row) if today_row else {}
    today_ev = evaluate(today_rec) if today_rec else evaluate(None)
    today_hm = {
        "worked": hm(today_ev["worked"]),
        "late": hm(today_ev["late_by"]),
        "short": hm(today_ev["short_by"]),
    }
    today_locked_reason = ""
    ex_app = (today_rec.get("approval_status") or "") if today_rec else ""
    if not active_tm:
        today_locked_reason = "You are currently unassigned (on the bench)."
    elif today_rec and ex_app == "Approved" and (today_rec.get("in_time") or today_rec.get("leave_type") or today_rec.get("remarks")):
        if today_rec.get("leave_type"):
            today_locked_reason = f"You are marked On Leave today ({today_rec['leave_type']}) — verified & approved by your PM/TL."
        else:
            today_locked_reason = "Today's attendance has been verified and approved by your PM/TL."

    covers = []
    away_today = []
    if active_tm:
        pid = active_tm["project_id"]
        covers = [c for c in cover_choices(pid) if c["id"] not in mids and c["name"] != active_tm["name"]]
        stored_today = records(td)
        away_today = sorted({r["user_name"] for u, r in stored_today.items() if u not in mids and r.get("leave_type")})
    
    # Query team assignment history date spans for this member with project names
    tm_spans = db().execute(f"""
        SELECT t.project_id, t.active, p.name AS project_name,
               substr(cast(t.assigned_from as text), 1, 10) AS start_day,
               substr(cast(t.assigned_to as text), 1, 10) AS end_day
        FROM team t
        JOIN project p ON CAST(p.id AS TEXT) = t.project_id
        WHERE t.member_id IN ({ph})
    """, mids).fetchall()

    active_uid = active_tm["member_id"] if active_tm else (mids[0] if mids else "")
    my_off = off_days(active_uid) if active_uid else WEEKLY_OFF
    rows, tot = [], {"Present": 0, "Late": 0, "Short of shift": 0, "On leave": 0, "Absent (no info)": 0}
    for d in range(1, nd + 1):
        ds = f"{month}-{d:02d}"
        if ds > td: break
        rec = recs.get(ds); ev = evaluate(rec); wd = date(y, mo, d).strftime("%a")
        
        # Check which project the user was assigned to on date ds
        assigned_proj = None
        for sp in tm_spans:
            if (sp["start_day"] or "0000-00-00") <= ds and (not sp["end_day"] or sp["end_day"] >= ds):
                assigned_proj = sp["project_name"]
                break
        was_assigned = bool(assigned_proj)
        if rec and not assigned_proj and tm_spans:
            assigned_proj = tm_spans[0]["project_name"]

        if rec:
            if ev["status"] == "Absent": st, cls = "Absent (no info)", "Absent"; tot[st] += 1
            elif ev["status"] == "On Leave": st, cls = "On leave", "Leave"; tot[st] += 1
            else:
                st, cls = "Present", "Present"; tot["Present"] += 1
                tot["Late"] += ev["late_by"] is not None; tot["Short of shift"] += ev["short_by"] is not None
        elif wd.lower() in my_off: st, cls = "Weekly off", ""
        elif not was_assigned: st, cls = "Unassigned / Bench", ""
        elif not any(entered(u, by.get(ds)) for u in mids): st, cls = "Not entered yet", ""
        elif ev["status"] == "Absent": st, cls = "Absent (no info)", "Absent"; tot[st] += 1
        elif ev["status"] == "On Leave": st, cls = "On leave", "Leave"; tot[st] += 1
        else:
            st, cls = "Present", "Present"; tot["Present"] += 1
            tot["Late"] += ev["late_by"] is not None; tot["Short of shift"] += ev["short_by"] is not None
        
        proj_display = assigned_proj if was_assigned else ("—" if st == "Unassigned / Bench" else (assigned_proj or "—"))
        rows.append({"day": ds, "wd": wd, "status": st, "cls": cls, "project": proj_display, "r": rec or {}, "late": hm(ev["late_by"]), "worked": hm(ev["worked"]), "short": hm(ev["short_by"])})
    wf_obj = [dict(o) for o in db().execute(f"SELECT * FROM objection WHERE user_id IN ({ph}) ORDER BY id DESC LIMIT 20", mids).fetchall()]
    t_mem = my_member()
    lv_mine = [dict(r) for r in db().execute(f"SELECT * FROM leave_request WHERE user_id IN ({ph}) ORDER BY id DESC LIMIT 30", mids).fetchall()]
    for r in lv_mine:
        r["running"] = (r["status"] == "approved" and r["from_date"] <= td <= r["to_date"] and not r.get("early_join"))
        r["can_cancel"] = (r["status"] in ("pending", "modification", "withdraw_requested") or (r["status"] == "approved" and r["from_date"] > td))
    lv_team = []
    if t_mem:
        for r in db().execute("""SELECT * FROM leave_request WHERE project_id=? AND user_id<>? AND status IN ('pending','approved','modification','withdraw_requested') AND to_date>=? ORDER BY from_date LIMIT 40""",
                              (str(t_mem["project_id"]), t_mem["member_id"], td)).fetchall():
            lv_team.append(dict(r))
    return render_template("me.html", day=td, month=month, rows=rows, tot=tot, info=info,
                           active_tm=active_tm, today_rec=today_rec, today_ev=today_ev, today_hm=today_hm,
                           today_locked_reason=today_locked_reason, leave_types=LEAVE_TYPES, covers=covers, away=away_today,
                           wf_obj=wf_obj, wf_hours=hours(),
                           lv_mine=lv_mine, lv_team=lv_team, lv_types=LEAVE_TYPES, lv_planned_days=planned_days(), lv_hours=approve_hours())

# ---------------------------------------------------------------- trends: arrival pattern and irregularity
def signed(m): return "" if m is None else ("on time" if m == 0 else f"{'+' if m > 0 else '-'}{abs(m) // 60}:{abs(m) % 60:02d}")

@app.route("/trends")
@login_required
def trends():
    days_param = request.args.get("days", "30").strip()
    start_param = request.args.get("start", "").strip()
    end_param = request.args.get("end", "").strip()

    is_custom = False
    if days_param == "custom":
        if start_param and end_param:
            try:
                start = date.fromisoformat(start_param)
                end = date.fromisoformat(end_param)
                if start > end:
                    start, end = end, start
                # Safety limit: up to 1095 days (~3 years)
                if (end - start).days > 1095:
                    start = end - timedelta(days=1095)
                span = (end - start).days + 1
                is_custom = True
                selected_days = "custom"
            except (ValueError, TypeError):
                span = 30
                end = date.fromisoformat(today())
                start = end - timedelta(days=span - 1)
                selected_days = "30"
        else:
            span = 30
            end = date.fromisoformat(today())
            start = end - timedelta(days=span - 1)
            is_custom = True
            selected_days = "custom"
    else:
        try: span = int(days_param)
        except ValueError: span = 30
        if span not in (7, 14, 30, 60, 90, 180, 365): span = 30
        selected_days = str(span)
        end = date.fromisoformat(today())
        start = end - timedelta(days=span - 1)

    is_eng = my_role() == "engineer"
    mids = my_member_ids()
    target_uid = request.args.get("user", "").strip()
    if is_eng:
        target_uid = mids[0] if mids else ""

    pids, pid = pick_pids()
    if is_eng:
        eng_pids = [str(r["project_id"]) for r in db().execute("SELECT project_id FROM team WHERE lower(email)=?", (email(),))]
        pids = eng_pids if eng_pids else pids

    ros = roster(pids)
    users_list = []
    if not is_eng:
        for uid, m in sorted(ros.items(), key=lambda kv: (0 if ('manager' in (kv[1].get('role', '') or '').lower() or 'lead' in (kv[1].get('role', '') or '').lower()) else 1, kv[1]["name"].lower())):
            role_tag = f" [{m['role']}]" if m.get("role") else ""
            users_list.append({"id": uid, "name": m["name"] + role_tag, "projects": ", ".join(m["projects"])})

    by = {}
    for r in db().execute("SELECT * FROM attendance WHERE day>=? AND day<=?", (start.isoformat(), end.isoformat())):
        by.setdefault(r["day"], {})[r["user_id"]] = dict(r)
    per = {u: {"uid": u, "name": m["name"], "projects": ", ".join(m["projects"]), "days": 0, "present": 0, "late": 0, "late_min": 0, "short": 0,
               "pl": 0, "ul": 0, "absent": 0, "dev": [], "seq": []} for u, m in ros.items()}
    entered = entered_checker()
    wk = [{"wd": w, "present": 0, "late": 0} for w in ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")]
    daily, d = [], start
    while d <= end:
        ds = d.isoformat(); recs = by.get(ds)
        c = {"day": ds, "label": d.strftime("%d %b"), "wd": d.strftime("%a"), "ontime": 0, "late": 0, "leave": 0, "absent": 0, "entered": False, "devs": [], "details": []}
        eval_users = [u for u in mids if u in ros] if is_eng else ([target_uid] if (target_uid and target_uid in ros) else (ros if recs else ()))
        for u in eval_users:
            m = ros.get(u, {})
            if not is_assigned_on(m.get("assignments", []), ds): continue
            rec = (recs or {}).get(u)
            u_off = d.strftime("%a").lower() in off_days(u)
            if (not rec and u_off) or not entered(u, recs): continue      # only days on which that engineer's team was filled in
            c["entered"] = True
            ev = evaluate(rec); p = per[u]; p["days"] += 1
            st = ev["status"]
            detail = {"name": m["name"], "status": st, "in_time": (rec or {}).get("in_time") or "", "out_time": (rec or {}).get("out_time") or "", "late_hm": hm(ev["late_by"])}
            c["details"].append(detail)
            if st == "Absent": c["absent"] += 1; p["absent"] += 1
            elif st == "On Leave":
                c["leave"] += 1; p["pl" if (rec or {}).get("planned") == "Planned" else "ul"] += 1
            else:
                late = ev["late_by"] is not None
                p["present"] += 1; p["dev"].append(ev["dev"]); p["seq"].append(1 if late else 0); c["devs"].append(ev["dev"])
                wk[d.weekday()]["present"] += 1; wk[d.weekday()]["late"] += late
                c["late" if late else "ontime"] += 1
                if late: p["late"] += 1; p["late_min"] += ev["late_by"]
                if ev["short_by"] is not None: p["short"] += 1
        c["total"] = c["ontime"] + c["late"] + c["leave"] + c["absent"]
        c["avg_dev"] = round(sum(c["devs"]) / len(c["devs"])) if c["devs"] else None
        daily.append(c); d += timedelta(days=1)
    people = []
    for p in per.values():
        if is_eng:
            if p["uid"] not in mids: continue
        elif target_uid and p["uid"] != target_uid:
            continue
        p["late_pct"] = round(100 * p["late"] / p["present"]) if p["present"] else 0
        p["avg_dev"] = signed(round(sum(p["dev"]) / len(p["dev"]))) if p["dev"] else ""
        p["avg_late"] = hm(p["late_min"] // p["late"]) if p["late"] else ""
        h = len(p["seq"]) // 2; p["trend"] = ""
        if len(p["seq"]) >= 6:
            a, b = sum(p["seq"][:h]) / h, sum(p["seq"][h:]) / (len(p["seq"]) - h)
            p["trend"] = "Getting worse" if b - a >= 0.2 else "Improving" if a - b >= 0.2 else "Steady"
        p["score"] = p["late"] + p["short"] + 2 * p["ul"] + 3 * p["absent"]
        p["irregular"] = (p["late"] >= 2 and p["late_pct"] >= 30) or p["absent"] >= 2 or p["ul"] >= 2 or p["short"] >= 3
        people.append(p)
    people.sort(key=lambda p: (-p["score"], p["name"].lower()))
    for w in wk: w["pct"] = round(100 * w["late"] / w["present"]) if w["present"] else None
    
    # chart geometry (SVG is drawn in the template from these numbers)
    W, H, L, B, T = 900, 230, 34, 34, 10
    n = len(daily)
    slot = (W - L - 6) / max(n, 1)
    # Dynamic bar width scaling to prevent overlapping bars on 180 and 365 day charts
    if slot >= 6.0:
        bw = max(4.0, slot * 0.72)
    elif slot >= 3.0:
        bw = max(2.2, slot * 0.75)
    else:
        bw = max(1.2, slot * 0.82)

    top = max([c["total"] for c in daily] + [1])
    ph = H - B - T

    # Intelligent tick step based on date span
    if n <= 14: step = 1
    elif n <= 45: step = 3
    elif n <= 90: step = 7
    elif n <= 180: step = 14
    else: step = max(1, -(-n // 12))

    for i, c in enumerate(daily):
        c["x"] = round(L + i * slot + (slot - bw) / 2, 1)
        c["w"] = round(bw, 1)
        c["hx"] = round(L + i * slot, 1)
        c["hw"] = round(slot, 1)
        c["tick"] = (i % step == 0) or i == n - 1
        y = H - B
        c["seg"] = []
        for key, col, lab in (("ontime", "#548235", "On time"), ("late", "#bf8f00", "Late"), ("leave", "#2e75b6", "On leave"), ("absent", "#c00000", "Absent (no info)")):
            hgt = c[key] / top * ph
            if c[key]: y -= hgt; c["seg"].append({"y": round(y, 1), "h": round(max(hgt - 1, 1), 1), "col": col, "tip": f"{c['label']} {c['wd']}: {c[key]} {lab.lower()}"})

        tip_lines = [f"<div style='font-weight:600;margin-bottom:4px'>{c['label']} ({c['wd']})</div>"]
        if not c["entered"]:
            tip_lines.append("<div style='color:#94a3b8'>No attendance entered</div>")
        elif target_uid and c["details"]:
            det = c["details"][0]
            st = det["status"]
            col = {"On time": "#4ade80", "Late": "#facc15", "On Leave": "#60a5fa", "Absent": "#f87171"}.get(st, "#cbd5e1")
            tip_lines.append(f"<div style='color:{col};font-weight:600'>{st}</div>")
            if det["in_time"]:
                tip_lines.append(f"<div>In: {det['in_time']} &nbsp; Out: {det['out_time'] or '—'}</div>")
            if det["late_hm"]:
                tip_lines.append(f"<div style='color:#facc15'>Late by: {det['late_hm']}</div>")
        else:
            tip_lines.append(f"<div>Total evaluated: {c['total']}</div>")
            if c["ontime"]: tip_lines.append(f"<div style='color:#4ade80'>● On time: {c['ontime']}</div>")
            if c["late"]: tip_lines.append(f"<div style='color:#facc15'>● Late: {c['late']}</div>")
            if c["leave"]: tip_lines.append(f"<div style='color:#60a5fa'>● On leave: {c['leave']}</div>")
            if c["absent"]: tip_lines.append(f"<div style='color:#f87171'>● Absent: {c['absent']}</div>")

        if c["entered"]:
            tip_lines.append("<div style='margin-top:6px;padding-top:4px;border-top:1px solid #334155;color:#94a3b8;font-size:11px'>Click bar to view full day summary →</div>")
        c["tip_html"] = "".join(tip_lines)

    devs = [c["avg_dev"] for c in daily if c["avg_dev"] is not None]
    lo, hi = min(devs + [-15]), max(devs + [GRACE_MIN + 15]); H2 = 170; ph2 = H2 - B - T
    yv = lambda v: round(T + (hi - v) / (hi - lo) * ph2, 1)
    pts = [(round(c["x"] + c["w"] / 2, 1), yv(c["avg_dev"]), c) for c in daily if c["avg_dev"] is not None]
    return render_template("trends.html", day=today(), span=span, selected_days=selected_days, is_custom=is_custom,
                           projects=my_projects(), pid=pid, daily=daily, people=people, wk=wk,
                           users=users_list, target_uid=target_uid, is_engineer=is_eng,
                           g={"W": W, "H": H, "L": L, "B": B, "T": T, "top": top, "H2": H2, "y0": yv(0), "yg": yv(GRACE_MIN), "pts": pts,
                              "line": " ".join(f"{x},{y}" for x, y, _ in pts)}, signed=signed,
                           entered=sum(1 for c in daily if c["entered"]), start=start.isoformat(), end=end.isoformat())

# ---------------------------------------------------------------- history
@app.route("/history")
@login_required
def history():
    month = request.args.get("month") or today()[:7]
    try: datetime.strptime(month, "%Y-%m")
    except ValueError: abort(400, "Bad month")
    ps = my_projects(); pids, pid = pick_pids()
    nd, data, _ = month_matrix(month, pids); y, mo = map(int, month.split("-"))
    days = [{"n": d, "wd": date(y, mo, d).strftime("%a"), "iso": f"{month}-{d:02d}"} for d in range(1, nd + 1)]
    return render_template("history.html", day=today(), month=month, projects=ps, pid=pid,
                           days=days, data=data, codes=CODES, fills={c[0]: c[2] for c in CODES})

@app.errorhandler(requests.RequestException)
def op_down(e):
    app.logger.error("OpenProject call failed: %s", e)
    return render_template("message.html", msg="Could not reach OpenProject. Check OP_URL and OP_API_KEY, then try again."), 502

# ---------------------------------------------------------------- Excel
THIN = Side(style="thin", color="BFBFBF"); BOX = Border(left=THIN, right=THIN, top=THIN, bottom=THIN)
def _hdr(ws, row, vals, color="1F3864"):
    for j, v in enumerate(vals, 1):
        c = ws.cell(row, j, v); c.font = Font(name="Arial", bold=True, color="FFFFFF", size=10)
        c.fill = PatternFill("solid", fgColor=color); c.border = BOX
        c.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
def _row(ws, row, vals):
    for j, v in enumerate(vals, 1):
        c = ws.cell(row, j, v); c.font = Font(name="Arial", size=10); c.border = BOX
        c.alignment = Alignment(vertical="center", wrap_text=True)
def _widths(ws, ws_widths):
    for j, w in enumerate(ws_widths, 1): ws.column_dimensions[get_column_letter(j)].width = w
def _xlsx(wb, name):
    buf = io.BytesIO(); wb.save(buf); buf.seek(0)
    return send_file(buf, as_attachment=True, download_name=name,
                     mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

@app.route("/export/daily.xlsx")
@login_required
def export_daily():
    day = get_day(); pids, _ = pick_pids(); s = build_summary(day, with_tasks=False, pids=pids); wb = Workbook(); ws = wb.active; ws.title = "Summary"
    ws["A1"] = f"Daily Attendance Summary - {date.fromisoformat(day):%A, %d-%b-%Y}"; ws["A1"].font = Font(name="Arial", bold=True, size=14)
    _hdr(ws, 3, ["Total Members", "Present", "Absent (No info)", "On Leave", "Late", "Short of shift"])
    _row(ws, 4, [s["total"], s["present"], len(s["absent"]), len(s["leave"]), len(s["late"]), len(s["short"])])
    r = 6
    secs = [("1. ABSENT - NO INFORMATION", "C00000", s["absent"], ["Team Member", "Project", "Remarks"], lambda x: [x["name"], x["projects"], x.get("remarks", "")]),
            ("2. ON LEAVE - TASK HANDLED BY", "2E75B6", s["leave"], ["Team Member", "Project", "Leave Type", "Planned / Unplanned", "Task Handled By", "Remarks"],
             lambda x: [x["name"], x["projects"], x["leave_type"], x["planned"] or "Not marked", x["handled_by"], x["remarks"]]),
            ("3. PRESENT MEMBERS", "2E7D32", s.get("present_list", []), ["Team Member", "Project", "Shift Start", "In Time", "Out Time", "Status", "Remarks"],
             lambda x: [x["name"], x["projects"], x.get("shift_start") or SHIFT_START, x.get("in_time", ""), x.get("out_time", ""), ("Late (+" + x["late_hm"] + ")") if x.get("late_hm") else "On time", x.get("remarks", "")]),
            ("4. LATE ARRIVALS", "BF8F00", s["late"], ["Team Member", "Project", "Shift Start", "In Time", "Late By", "Remarks"],
             lambda x: [x["name"], x["projects"], x.get("shift_start") or SHIFT_START, x["in_time"], x["late_hm"], x["remarks"]]),
            ("5. NOT COMPLETING SHIFT", "C55A11", s["short"], ["Team Member", "Project", "In Time", "Out Time", "Hours in Office", "Short By"],
             lambda x: [x["name"], x["projects"], x["in_time"], x["out_time"], x["worked_hm"], x["short_hm"]])]
    for title, col, items, heads, fn in secs:
        c = ws.cell(r, 1, f"{title}  ({len(items)})"); c.font = Font(name="Arial", bold=True, color="FFFFFF", size=11)
        for j in range(1, 8): ws.cell(r, j).fill = PatternFill("solid", fgColor=col)
        r += 1; _hdr(ws, r, heads, "595959"); r += 1
        for x in items or [None]:
            _row(ws, r, fn(x) if x else ["None"]); r += 1
        r += 1
    _widths(ws, [28, 26, 18, 20, 24, 20, 30])
    recs = records(day)
    for p in [p for p in my_projects() if p["id"] in pids]:
        w = wb.create_sheet("".join(ch for ch in p["name"].replace(" / ", " - ") if ch not in '[]:*?/\\')[:31] or "Project")
        _hdr(w, 1, ["Team Member", "Role", "Contact", "Shift Start", "Status", "In Time", "Out Time", "Hours in Office", "Late By", "Short By", "Leave Type", "Planned / Unplanned", "Task Handled By", "Remarks"])
        p_members = [m for m in members(p["id"]) if recs.get(m["id"]) or is_assigned_on([{"from": m.get("assigned_from"), "to": m.get("assigned_to")}], day)]
        for i, m in enumerate(p_members, 2):
            rec = recs.get(m["id"]) or {}; ev = evaluate(rec or None)
            _row(w, i, [m["name"], m["role"], m["phone"], rec.get("shift_start") or m["shift"] or SHIFT_START, "Absent (No info)" if ev["status"] == "Absent" else ev["status"], rec.get("in_time", ""), rec.get("out_time", ""),
                        hm(ev["worked"]), hm(ev["late_by"]), hm(ev["short_by"]), rec.get("leave_type", ""), rec.get("planned", ""),
                        rec.get("handled_by", ""), rec.get("remarks", "")])
        _widths(w, [26, 18, 16, 10, 16, 10, 10, 12, 10, 10, 16, 14, 24, 32]); w.freeze_panes = "B2"
    return _xlsx(wb, f"attendance_{day}.xlsx")

CODES = [("P", "Present, on time, full shift", "E2EFDA"), ("LT", "Late arrival", "FFF2CC"), ("SH", "Short of shift hours", "FCE4D6"),
         ("LS", "Late and short", "F8CBAD"), ("PL", "Planned leave", "DDEBF7"), ("UL", "Unplanned leave", "BDD7EE"),
         ("L", "Leave (planned/unplanned not marked)", "DDEBF7"), ("A", "Absent - no information", "FF9999"),
         ("WO", "Weekly off", "EDEDED"), ("-", "No attendance entered for this engineer's team that day (holiday or not filled)", "FFFFFF")]

def entered_checker():
    """-> f(member_id, that_day's_records): True when attendance was entered that day for at least one person
    in one of the member's own projects. A day nobody filled in for a team is 'not entered', not 'absent'."""
    mates = {}
    for p in projects(True):
        ids = {m["id"] for m in team(p["id"], active_only=False)}
        for u in ids: mates.setdefault(u, set()).update(ids)
    return lambda u, recs: bool(recs) and not mates.get(u, set()).isdisjoint(recs)

def month_matrix(month, pids=None):
    y, mo = map(int, month.split("-")); nd = calendar.monthrange(y, mo)[1]; td = today()
    rows = db().execute("SELECT * FROM attendance WHERE day LIKE ? ORDER BY day,user_name", (month + "-%",)).fetchall()
    ros = roster(pids, include_inactive=True); seen = {r["user_id"] for r in rows}
    ros = {k: v for k, v in ros.items() if v["active"] or k in seen}   # removed members stay while they have history
    rows = [r for r in rows if r["user_id"] in ros]
    by = {}
    for r in rows: by.setdefault(r["day"], {})[r["user_id"]] = dict(r)
    out = []; entered = entered_checker()
    for uid, m in sorted(ros.items(), key=lambda kv: kv[1]["name"].lower()):
        codes, tot, worked = [], {c[0]: 0 for c in CODES}, []
        for d in range(1, nd + 1):
            ds = f"{month}-{d:02d}"; rec = by.get(ds, {}).get(uid)
            off = date(y, mo, d).strftime("%a").lower() in off_days(uid)
            if ds > td: code = ""
            elif not is_assigned_on(m.get("assignments", []), ds): code = "-"
            elif not rec and off: code = "WO"
            elif not entered(uid, by.get(ds)): code = "-"
            else:
                ev = evaluate(rec)
                if ev["status"] == "Absent": code = "A"
                elif ev["status"] == "On Leave": code = {"Planned": "PL", "Unplanned": "UL"}.get(rec["planned"], "L")
                else:
                    code = "LS" if ev["late_by"] is not None and ev["short_by"] is not None else "LT" if ev["late_by"] is not None else "SH" if ev["short_by"] is not None else "P"
                    if ev["worked"] is not None: worked.append(ev["worked"])
            codes.append(code)
            if code: tot[code] += 1
        out.append({"name": m["name"], "projects": ", ".join(m["projects"]), "codes": codes, "tot": tot,
                    "avg": hm(sum(worked) // len(worked)) if worked else ""})
    return nd, out, rows

@app.route("/export/monthly.xlsx")
@login_required
def export_monthly():
    month = request.args.get("month") or today()[:7]
    try: datetime.strptime(month, "%Y-%m")
    except ValueError: abort(400, "Bad month")
    pids, _ = pick_pids(); nd, data, rows = month_matrix(month, pids); y, mo = map(int, month.split("-"))
    wb = Workbook(); ws = wb.active; ws.title = "Monthly"
    ws["A1"] = f"Monthly Attendance - {date(y, mo, 1):%B %Y}"; ws["A1"].font = Font(name="Arial", bold=True, size=14)
    tots = ["Present days", "Late", "Short of shift", "Planned leave", "Unplanned leave", "Leave (not marked)", "Absent (no info)", "Avg hours in office"]
    _hdr(ws, 3, ["Team Member", "Project"] + [f"{d}\n{date(y, mo, d):%a}" for d in range(1, nd + 1)] + tots)
    ws.row_dimensions[3].height = 42; fills = {c[0]: c[2] for c in CODES}
    for i, x in enumerate(data, 4):
        t = x["tot"]
        _row(ws, i, [x["name"], x["projects"]] + x["codes"] + [t["P"] + t["LT"] + t["SH"] + t["LS"], t["LT"] + t["LS"], t["SH"] + t["LS"],
                                                              t["PL"], t["UL"], t["L"], t["A"], x["avg"]])
        for j, code in enumerate(x["codes"], 3):
            c = ws.cell(i, j); c.alignment = Alignment(horizontal="center")
            if code in fills: c.fill = PatternFill("solid", fgColor=fills[code])
        for j in range(3 + nd, 3 + nd + len(tots)): ws.cell(i, j).alignment = Alignment(horizontal="center")
    _widths(ws, [26, 24] + [5] * nd + [10] * len(tots)); ws.freeze_panes = "C4"
    r = len(data) + 6; ws.cell(r, 1, "Legend").font = Font(name="Arial", bold=True)
    for k, (code, text, col) in enumerate(CODES, 1):
        c = ws.cell(r + k, 1, code); c.fill = PatternFill("solid", fgColor=col); c.border = BOX; c.font = Font(name="Arial", size=10)
        ws.cell(r + k, 2, text).font = Font(name="Arial", size=10)
    ws.cell(r + len(CODES) + 2, 1, f"Rules: shift starts {SHIFT_START}, grace {GRACE_MIN} min, shift length {SHIFT_MIN / 60:g} h (incl. lunch). "
            f"Weekly off: {', '.join(sorted(WEEKLY_OFF))}. Present days include late/short days.").font = Font(name="Arial", size=9, italic=True)
    lg = wb.create_sheet("Daily log")
    _hdr(lg, 1, ["Date", "Team Member", "Status", "In Time", "Out Time", "Hours in Office", "Late By", "Short By", "Leave Type", "Planned / Unplanned", "Task Handled By", "Remarks", "Entered By"])
    for i, rec in enumerate(rows, 2):
        ev = evaluate(rec)
        _row(lg, i, [rec["day"], rec["user_name"], ev["status"], rec["in_time"], rec["out_time"], hm(ev["worked"]), hm(ev["late_by"]), hm(ev["short_by"]),
                     rec["leave_type"], rec["planned"], rec["handled_by"], rec["remarks"], rec["updated_by"]])
    _widths(lg, [12, 26, 12, 10, 10, 12, 10, 10, 16, 14, 24, 32, 26]); lg.freeze_panes = "C2"
    return _xlsx(wb, f"attendance_{month}.xlsx")

# ---------------------------------------------------------------- email
def send_summary(day):
    with app.app_context():
        s = build_summary(day)
        html = render_template("email.html", s=s, day=day, base_url=BASE_URL, shift_start=SHIFT_START,
                               grace=GRACE_MIN, shift_hours=SHIFT_MIN / 60)
    msg = EmailMessage()
    msg["Subject"] = f"Attendance {date.fromisoformat(day):%d-%b-%Y}: {len(s['absent'])} absent, {len(s['leave'])} on leave, {len(s['late'])} late, {len(s['short'])} short"
    msg["From"] = E("SMTP_FROM") or E("SMTP_USER", ""); msg["To"] = ", ".join(SUMMARY_TO)
    msg.set_content("Open this email in an HTML-capable mail client."); msg.add_alternative(html, subtype="html")
    with smtplib.SMTP(E("SMTP_HOST"), int(E("SMTP_PORT", "587")), timeout=30) as sm:
        sm.starttls()
        if E("SMTP_USER"): sm.login(E("SMTP_USER"), E("SMTP_PASSWORD", ""))
        sm.send_message(msg)

def scheduler():
    """Once per day: purge old location details. On working days at SUMMARY_TIME: send the summary email (when email is configured)."""
    while True:
        try:
            now = datetime.now(TZ); d = now.date().isoformat(); c = Conn()
            if c.execute("INSERT INTO meta(k,v) VALUES(?,?) ON CONFLICT DO NOTHING", ("purge_" + d, now.isoformat())).rowcount:
                c.commit()
                if "purge_events" in globals():
                    n = purge_events()
                    if n: app.logger.info("removed location details from %d old check-in events", n)
            c.commit()
            if "mobile_refresh_recent" in globals():
                mobile_refresh_recent()                         # phone check-ins: wait times pass with the clock, so work the day out again
            globals().get("wf_refresh_bg", lambda: None)()      # approvals: new items, re-routing, escalation to admin
            if SUMMARY_TO and E("SMTP_HOST") and now.strftime("%H:%M") >= SUMMARY_TIME and now.strftime("%a").lower() not in WEEKLY_OFF:
                if c.execute("INSERT INTO meta(k,v) VALUES(?,?) ON CONFLICT DO NOTHING", ("sent_" + d, now.isoformat())).rowcount:
                    c.commit()
                    try: send_summary(d)
                    except Exception as ex:
                        app.logger.error("summary email failed: %s", ex)
                        c.execute("DELETE FROM meta WHERE k=?", ("sent_" + d,)); c.commit(); time.sleep(600)
            c.close()
        except Exception as ex:
            app.logger.error("scheduler: %s", ex)
        time.sleep(60)

import sys, mobile
mobile.register(sys.modules[__name__])

if E("RUN_SCHEDULER", "1") == "1":
    threading.Thread(target=scheduler, daemon=True).start()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000, debug=DEV)
