"""Mobile (Android) check-in for the attendance portal.

The phone sends ENTER / EXIT events when it crosses a site radius. This module checks each event,
stores it, works out the engineer's first IN, last OUT and how often they went out, and fills the
day's attendance. A TL/PM entry always wins. Everything here runs inside the portal's own Flask app."""
import json, math, time
from datetime import date, datetime, timedelta

import requests
from flask import abort, flash, jsonify, redirect, render_template, request, url_for
import app_config, mailer


def register(A):
    """Attach the tables, API, review screen and purge job to the portal module A (app.py)."""
    app, E = A.app, A.E
    MOBILE_CLIENT_ID = E("MOBILE_CLIENT_ID", "attendance-mobile")      # Keycloak public client used by the Android app
    CONSENT_VERSION = E("CONSENT_VERSION", "1")                         # bump when HR changes the consent wording
    ENV_MIN, ENV_MAX = int(E("SITE_RADIUS_MIN", "200")), int(E("SITE_RADIUS_MAX", "300"))     # defaults; the admin can change them on the Projects page

    def limits():
        """(min, max) site radius in metres: the admin's saved setting, else the environment default."""
        try:
            r = {x["k"]: x["v"] for x in A.db().execute("SELECT k,v FROM meta WHERE k IN ('radius_min','radius_max')")}
            return int(r.get("radius_min", ENV_MIN)), int(r.get("radius_max", ENV_MAX))
        except Exception: return ENV_MIN, ENV_MAX
    MAX_ACCURACY = int(E("MAX_ACCURACY_M", "100"))                      # a fix worse than this is ignored
    MAX_SPEED_KMH = float(E("MAX_SPEED_KMH", "200"))                    # faster than this between two events = impossible travel
    MAX_AGE_S = 24 * 3600                                               # an offline event older than this is refused
    RETENTION_DAYS = int(E("EVENT_RETENTION_DAYS", "90"))               # raw coordinates are removed after this many days
    CONSENT_TEXT = E("CONSENT_TEXT", "To mark your attendance automatically, this app records your phone's location only when you enter or leave "
                     "a work-site area. It does not record your route. Your TL/PM can see these entry and exit times. Location details are "
                     "deleted after %d days.") % RETENTION_DAYS

    # ------------------------------------------------------------ tables
    def init():
        c = A.Conn(); auto = "SERIAL PRIMARY KEY" if A.PG else "INTEGER PRIMARY KEY AUTOINCREMENT"; real = "DOUBLE PRECISION" if A.PG else "REAL"
        for ddl in (
            f"""CREATE TABLE IF NOT EXISTS site(id {auto}, project_id TEXT NOT NULL, name TEXT NOT NULL, lat {real} NOT NULL, lon {real} NOT NULL,
                 radius INTEGER NOT NULL, dwell_in INTEGER NOT NULL DEFAULT 5, dwell_out INTEGER NOT NULL DEFAULT 10,
                 beacon_mode TEXT NOT NULL DEFAULT 'off', beacon_ids TEXT, active INTEGER NOT NULL DEFAULT 1, updated_by TEXT, updated_at TEXT)""",
            f"""CREATE TABLE IF NOT EXISTS checkin_event(id {auto}, day TEXT NOT NULL, member_id TEXT NOT NULL, email TEXT NOT NULL, site_id INTEGER NOT NULL,
                 project_id TEXT, kind TEXT NOT NULL, event_at TEXT NOT NULL, received_at TEXT NOT NULL, lat {real}, lon {real}, accuracy {real}, distance_m {real},
                 trust TEXT NOT NULL, reasons TEXT, device_id TEXT, beacons TEXT)""",
            "CREATE TABLE IF NOT EXISTS device(email TEXT PRIMARY KEY, device_id TEXT NOT NULL, model TEXT, status TEXT NOT NULL, pending_id TEXT, pending_model TEXT, registered_at TEXT, approved_by TEXT)",
            "CREATE TABLE IF NOT EXISTS consent(email TEXT NOT NULL, version TEXT NOT NULL, accepted_at TEXT NOT NULL, PRIMARY KEY(email, version))",
            """CREATE TABLE IF NOT EXISTS app_day(day TEXT NOT NULL, user_id TEXT NOT NULL, app_in TEXT, app_out TEXT, exits INTEGER NOT NULL DEFAULT 0, break_min INTEGER NOT NULL DEFAULT 0,
                 low_trust INTEGER NOT NULL DEFAULT 0, flagged INTEGER NOT NULL DEFAULT 0, merged_in TEXT, merged_out TEXT, note TEXT, updated_at TEXT, PRIMARY KEY(day, user_id))""",
            f"""CREATE TABLE IF NOT EXISTS app_dispute(id {auto}, day TEXT NOT NULL, user_id TEXT NOT NULL, email TEXT NOT NULL, note TEXT NOT NULL, created_at TEXT NOT NULL,
                 status TEXT NOT NULL DEFAULT 'open', resolved_by TEXT)""",
            "CREATE INDEX IF NOT EXISTS ev_member_day ON checkin_event(member_id, day)",
            "CREATE INDEX IF NOT EXISTS ev_received ON checkin_event(received_at)"):
            c.execute(ddl)
        c.commit(); c.close()
    init()

    # ------------------------------------------------------------ helpers
    A.mnow = lambda: datetime.now(A.TZ)          # the clock; tests replace it
    def now(): return A.mnow()

    def dist_m(la1, lo1, la2, lo2):
        p = math.pi / 180; a = math.sin((la2 - la1) * p / 2) ** 2 + math.cos(la1 * p) * math.cos(la2 * p) * math.sin((lo2 - lo1) * p / 2) ** 2
        return 6371000 * 2 * math.asin(math.sqrt(a))

    def day_for(ts, shift_start):
        """The attendance day an event belongs to. A night-shift engineer's early-morning events belong to the day the shift started."""
        st = A.mins(shift_start) if A.mins(shift_start or "") is not None else A.mins(A.SHIFT_START)
        m = ts.hour * 60 + ts.minute
        return ((ts.date() - timedelta(days=1)) if A.is_night(st) and m < st - 720 else ts.date()).isoformat()

    def members_by_email(em):
        """Team rows (active) for this email, across projects."""
        out = []
        for r in A.db().execute("SELECT * FROM team WHERE lower(email)=? AND active=1", (em.lower(),)):
            r = dict(r)
            if hasattr(A, "is_assigned_on") and "assigned_from" in r and not A.is_assigned_on([{"from": r.get("assigned_from"), "to": r.get("assigned_to")}], now().date().isoformat()):
                continue                                   # no longer (or not yet) assigned to that project
            out.append(r)
        return out

    def allowed_projects(pid):
        """A site on a main project also serves its sub-projects, and a site on a sub-project is for that sub-project only."""
        return [pid] + [p["id"] for p in A.projects() if p["parent"] == str(pid)]

    def sites_for(em):
        rows = members_by_email(em); out = []
        pids = {r["project_id"] for r in rows}
        for s in A.db().execute("SELECT * FROM site WHERE active=1 ORDER BY id"):
            if any(p in pids for p in allowed_projects(s["project_id"])): out.append(dict(s))
        return out

    def member_for_site(em, site):
        pids = allowed_projects(site["project_id"])
        for r in members_by_email(em):
            if r["project_id"] in pids: return r
        return None

    # ------------------------------------------------------------ Keycloak bearer token
    EXTRA_ISSUERS = {x.strip() for x in E("MOBILE_ISSUERS", "").split(",") if x.strip()}     # other issuer addresses to accept (local testing from an emulator)
    JWKS_URL = E("MOBILE_JWKS_URL", "")                                                    # where the portal fetches Keycloak's signing keys, if different from discovery
    _jwks = {"at": 0, "keys": None}
    _meta = {"at": 0, "doc": None}

    def kc_meta():
        """Keycloak's OpenID discovery document (cached for an hour)."""
        if not _meta["doc"] or time.time() - _meta["at"] > 3600:
            iss = E("OIDC_ISSUER", "").rstrip("/"); internal = E("KEYCLOAK_INTERNAL_URL", "").rstrip("/")
            base = (internal + "/realms/" + iss.split("/realms/")[1]) if internal and "/realms/" in iss else iss
            _meta["doc"] = requests.get(base + "/.well-known/openid-configuration", timeout=10).json(); _meta["at"] = time.time()
        return _meta["doc"]

    def token_user():
        """Email of the signed-in engineer from the Authorization: Bearer token (Keycloak access token of the mobile client)."""
        h = (request.headers.get("X-Dev-User") or "").strip().lower()
        if h and (A.DEV or E("ALLOW_DEV_HEADER", "1") == "1"):
            return h
        tok = (request.headers.get("Authorization") or "")[7:] if (request.headers.get("Authorization") or "").lower().startswith("bearer ") else ""
        if not tok: return None
        from authlib.jose import JsonWebKey, jwt
        try:
            meta = kc_meta()
            if not _jwks["keys"] or time.time() - _jwks["at"] > 3600:
                _jwks["keys"] = JsonWebKey.import_key_set(requests.get(JWKS_URL or meta["jwks_uri"], timeout=10).json()); _jwks["at"] = time.time()
            c = jwt.decode(tok, _jwks["keys"]); c.validate()          # signature, expiry
            expected_realm = meta.get("issuer", "").split("/realms/")[-1] if "/realms/" in meta.get("issuer", "") else ""
            iss_match = (c.get("iss") == meta.get("issuer")) or (c.get("iss") in EXTRA_ISSUERS) or (expected_realm and str(c.get("iss", "")).endswith(f"/realms/{expected_realm}"))
            if not iss_match:
                app.logger.warning("mobile token rejected: issuer mismatch (got '%s', expected '%s')", c.get("iss"), meta.get("issuer"))
                return None
            if c.get("azp") != MOBILE_CLIENT_ID and c.get("azp") != "attendance": return None          # token must have been issued to the mobile app or attendance client
            return (c.get("email") or "").lower() or None
        except Exception as ex:
            app.logger.warning("mobile token rejected: %s", ex); return None

    def api(fn):
        from functools import wraps
        @wraps(fn)
        def w(*a, **k):
            em = token_user()
            if not em: return jsonify(error="unauthorized"), 401
            if not members_by_email(em): return jsonify(error="not_in_any_team", message="Your email is not in any project team. Ask your TL/PM."), 403
            return fn(em, *a, **k)
        return w

    def consented(em):
        return A.db().execute("SELECT 1 FROM consent WHERE email=? AND version=?", (em, CONSENT_VERSION)).fetchone() is not None

    def device_state(em, device_id):
        """'approved' | 'pending' | 'unknown' for this phone."""
        d = A.db().execute("SELECT * FROM device WHERE email=?", (em,)).fetchone()
        if not d or d["device_id"] != device_id: return "pending" if d and d["pending_id"] == device_id else "unknown"
        return d["status"]

    # ------------------------------------------------------------ API
    @app.route("/api/m/config")
    @api
    def m_config(em):
        return jsonify(consent_version=CONSENT_VERSION, consent_text=CONSENT_TEXT, consented=consented(em), max_accuracy_m=MAX_ACCURACY,
                       radius_min=limits()[0], radius_max=limits()[1], flags=app_config.get_mobile_config_dict())

    @app.route("/api/m/consent", methods=["POST"])
    @api
    def m_consent(em):
        v = str((request.get_json(silent=True) or {}).get("version", ""))
        if v != CONSENT_VERSION: return jsonify(error="consent_version", message="Please read the current text again.", consent_version=CONSENT_VERSION), 409
        A.db().execute("INSERT INTO consent(email,version,accepted_at) VALUES(?,?,?) ON CONFLICT DO NOTHING", (em, v, now().isoformat(timespec="seconds"))); A.db().commit()
        return jsonify(ok=True)

    @app.route("/api/m/device", methods=["POST"])
    @api
    def m_device(em):
        j = request.get_json(silent=True) or {}; did = str(j.get("device_id", ""))[:80]; model = str(j.get("model", ""))[:80]
        if len(did) < 8: return jsonify(error="bad_device"), 400
        d = A.db().execute("SELECT * FROM device WHERE email=?", (em,)).fetchone(); t = now().isoformat(timespec="seconds")
        if not d:
            A.db().execute("INSERT INTO device(email,device_id,model,status,registered_at,approved_by) VALUES(?,?,?,?,?,?)", (em, did, model, "approved", t, "first phone")); status = "approved"
        elif d["device_id"] == did: status = d["status"]
        elif E("AUTO_APPROVE_DEVICES", "1") == "1":
            A.db().execute("UPDATE device SET device_id=?, model=?, status='approved', approved_by='auto_approved', registered_at=? WHERE email=?", (did, model, t, em)); status = "approved"
        else:       # a different phone: wait for the TL/PM to approve it
            A.db().execute("UPDATE device SET pending_id=?, pending_model=? WHERE email=?", (did, model, em)); status = "pending"
        A.db().commit()
        return jsonify(status=status)

    @app.route("/api/m/sites")
    @api
    def m_sites(em):
        return jsonify(sites=[{"id": s["id"], "name": s["name"], "lat": s["lat"], "lon": s["lon"], "radius": s["radius"], "dwell_in": s["dwell_in"],
                               "dwell_out": s["dwell_out"], "beacon_mode": s["beacon_mode"], "beacon_ids": [x for x in (s["beacon_ids"] or "").split(",") if x]}
                              for s in sites_for(em)])

    def judge(em, member, site, kind, lat, lon, acc, mock, rooted, beacons, event_at):
        """-> (trust, reasons, distance). trust: ok | low | rejected | flagged. low-trust events still count; rejected and flagged ones do not."""
        reasons, trust = [], "ok"
        d = dist_m(lat, lon, site["lat"], site["lon"])
        if mock: return "rejected", ["mock_location"], d
        if acc is None or acc > MAX_ACCURACY: return "rejected", ["poor_accuracy"], d
        if kind == "ENTER" and d > site["radius"] + max(acc, 50): return "rejected", ["not_inside_radius"], d
        if kind == "EXIT" and d < site["radius"] - max(acc, 50): trust = "low"; reasons.append("exit_but_inside")
        if rooted: trust = "low"; reasons.append("rooted_or_developer_mode")
        mode = site["beacon_mode"]; want = [x for x in (site["beacon_ids"] or "").split(",") if x]
        if mode in ("any", "all") and want and kind == "ENTER":
            seen = set(beacons or [])
            ok = (any(w in seen for w in want) if mode == "any" else all(w in seen for w in want))
            if not ok: trust = "low"; reasons.append("beacon_missing")
        prev = A.db().execute("SELECT lat,lon,event_at FROM checkin_event WHERE email=? AND trust IN ('ok','low') AND lat IS NOT NULL ORDER BY event_at DESC LIMIT 1", (em,)).fetchone()
        if prev:
            try:
                hrs = (event_at - datetime.fromisoformat(prev["event_at"])).total_seconds() / 3600
                km = dist_m(lat, lon, prev["lat"], prev["lon"]) / 1000
                if hrs > 0 and km > 1 and km / hrs > MAX_SPEED_KMH: trust = "low"; reasons.append("impossible_travel")
            except Exception: pass
        return trust, reasons, d

    @app.route("/api/m/event", methods=["POST"])
    @api
    def m_event(em):
        j = request.get_json(silent=True) or {}
        if not consented(em): return jsonify(error="consent_required"), 403
        did = str(j.get("device_id", ""))
        if len(did) < 8: return jsonify(error="bad_request"), 400
        st = device_state(em, did)
        if st != "approved": return jsonify(error="device_" + st, message="This phone is not approved yet. Your TL/PM must approve it."), 409
        try:
            site = A.db().execute("SELECT * FROM site WHERE id=? AND active=1", (int(j.get("site_id", 0)),)).fetchone()
            kind = str(j.get("kind", "")).upper(); lat, lon = float(j["lat"]), float(j["lon"]); acc = float(j["accuracy"]); age = float(j.get("age_s", 0))
        except (KeyError, ValueError, TypeError): return jsonify(error="bad_request"), 400
        if kind not in ("ENTER", "EXIT") or not site: return jsonify(error="bad_request"), 400
        if not (-90 <= lat <= 90 and -180 <= lon <= 180) or not (0 <= age <= MAX_AGE_S): return jsonify(error="bad_request"), 400
        member = member_for_site(em, dict(site))
        if not member: return jsonify(error="not_in_site_team", message="You are not in this site's project team."), 403
        recv = now(); event_at = recv - timedelta(seconds=age)       # the server's clock; the phone only says how long ago it happened
        dedupe = A.db().execute("SELECT id,trust,reasons FROM checkin_event WHERE email=? AND site_id=? AND kind=? AND event_at=? AND trust<>'rejected'", (em, site["id"], kind, event_at.isoformat(timespec="seconds"))).fetchone()
        if dedupe: return jsonify(result=dedupe["trust"], reasons=[x for x in (dedupe["reasons"] or "").split(",") if x], id=dedupe["id"], duplicate=True)
        trust, reasons, d = judge(em, member, dict(site), kind, lat, lon, acc, bool(j.get("mock")), bool(j.get("rooted")), j.get("beacons") or [], event_at)
        day = day_for(event_at, member["shift_start"])
        rec = A.db().execute("SELECT leave_type FROM attendance WHERE day=? AND user_id=?", (day, member["member_id"])).fetchone()
        if trust in ("ok", "low") and rec and rec["leave_type"]: trust = "flagged"; reasons.append("on_leave_day")
        eid = A.db().insert_id("""INSERT INTO checkin_event(day,member_id,email,site_id,project_id,kind,event_at,received_at,lat,lon,accuracy,distance_m,trust,reasons,device_id,beacons)
                                  VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                               (day, member["member_id"], em, site["id"], site["project_id"], kind, event_at.isoformat(timespec="seconds"), recv.isoformat(timespec="seconds"),
                                lat, lon, acc, round(d, 1), trust, ",".join(reasons), did, ",".join(map(str, (j.get("beacons") or [])[:20]))))
        A.db().commit()
        recompute(day, member)
        if trust in ("ok", "low"):
            try:
                time_str = event_at.strftime("%H:%M")
                if kind == "ENTER":
                    mailer.notify_checkin(em, member["name"], site["name"], time_str, is_geofence=True)
                elif kind == "EXIT":
                    mailer.notify_checkout(em, member["name"], time_str, hours_worked="Shift Logged", break_minutes=0)
            except Exception as ex:
                app.logger.warning("mailer checkin/out notify error: %s", ex)
        return jsonify(result=trust, reasons=reasons, id=eid, day=day)

    # ------------------------------------------------------------ day figures from the events
    def hhmm(ts): return ts.strftime("%H:%M")

    def derive(day, member):
        """First IN, last OUT, number of times the engineer went out and the minutes spent out, from this engineer's counted events."""
        evs = [dict(r) for r in A.db().execute("SELECT * FROM checkin_event WHERE day=? AND member_id=? ORDER BY event_at", (day, member["member_id"]))]
        good = [e for e in evs if e["trust"] in ("ok", "low")]
        sites = {}
        for e in good: sites.setdefault(e["site_id"], A.db().execute("SELECT dwell_in,dwell_out FROM site WHERE id=?", (e["site_id"],)).fetchone())
        # inside / outside spans in time order; a repeated ENTER or EXIT adds nothing
        spans, cur = [], None
        for e in good:
            t = datetime.fromisoformat(e["event_at"])
            if e["kind"] == "ENTER" and cur is None: cur = t
            elif e["kind"] == "EXIT" and cur is not None: spans.append((cur, t)); cur = None
        if cur is not None: spans.append((cur, None))
        dw_in = min([(s["dwell_in"] if s else 5) for s in sites.values()] or [5])
        dw_out = min([(s["dwell_out"] if s else 10) for s in sites.values()] or [10])
        # a pass-by (inside for less than the check-in dwell) is not a visit; the last open span is a visit once the dwell has passed
        n = now()
        real = [(a, b) for a, b in spans if (((b or n) - a).total_seconds() >= dw_in * 60)]
        out = {"app_in": None, "app_out": None, "exits": 0, "break_min": 0}
        if not real: return out, evs
        out["app_in"] = hhmm(real[0][0])
        last = real[-1]
        if last[1] is not None and (n - last[1]).total_seconds() >= dw_out * 60: out["app_out"] = hhmm(last[1])     # out for the dwell time: the day is over
        gaps = [(real[i][1], real[i + 1][0]) for i in range(len(real) - 1)]
        out["exits"] = len(gaps)                                                                                   # times they went out and came back
        out["break_min"] = int(sum((b - a).total_seconds() for a, b in gaps) // 60)
        return out, evs

    def recompute(day, member):
        f, evs = derive(day, member); u = member["member_id"]; t = now().isoformat(timespec="seconds")
        low = sum(1 for e in evs if e["trust"] == "low"); flg = sum(1 for e in evs if e["trust"] == "flagged")
        d = A.db()
        old = d.execute("SELECT * FROM app_day WHERE day=? AND user_id=?", (day, u)).fetchone()
        cur = d.execute("SELECT * FROM attendance WHERE day=? AND user_id=?", (day, u)).fetchone()
        merged_in, merged_out = (old["merged_in"] if old else None), (old["merged_out"] if old else None)
        if not (cur and cur["leave_type"]):
            # the app may fill a time only when it is empty or was last written by the app - a TL/PM entry always wins
            def take(field, new, was):
                have = (cur[field] if cur else "") or ""
                if new: return new if (have == "" or have == (was or "")) else None
                return "" if (was and have == was) else None          # the phone value no longer stands (it was a pass-by): take it back
            ni, no = take("in_time", f["app_in"], merged_in), take("out_time", f["app_out"], merged_out)
            if cur:
                sets, args = [], []
                if ni is not None: sets.append("in_time=?"); args.append(ni)
                if no is not None: sets.append("out_time=?"); args.append(no)
                if sets:
                    d.execute(f"UPDATE attendance SET {','.join(sets)}, updated_by='app', updated_at=? WHERE day=? AND user_id=?", (*args, t, day, u))
            elif ni or no:
                d.execute("""INSERT INTO attendance(day,user_id,user_name,in_time,out_time,leave_type,planned,handled_by,remarks,updated_by,updated_at,shift_start)
                             VALUES(?,?,?,?,?,'','','','','app',?,?)""", (day, u, member["name"], ni or "", no or "", t, member["shift_start"] or A.SHIFT_START))
            if ni is not None: merged_in = ni or None
            if no is not None: merged_out = no or None
        d.execute("""INSERT INTO app_day(day,user_id,app_in,app_out,exits,break_min,low_trust,flagged,merged_in,merged_out,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?)
                     ON CONFLICT(day,user_id) DO UPDATE SET app_in=excluded.app_in,app_out=excluded.app_out,exits=excluded.exits,break_min=excluded.break_min,
                     low_trust=excluded.low_trust,flagged=excluded.flagged,merged_in=excluded.merged_in,merged_out=excluded.merged_out,updated_at=excluded.updated_at""",
                  (day, u, f["app_in"], f["app_out"], f["exits"], f["break_min"], low, flg, merged_in, merged_out, t))
        d.commit()

    def refresh(day, member_ids=None):
        """Work the day's figures out again from the stored events (the wait times pass with the clock, so this is also run every minute)."""
        seen = set()
        for r in A.db().execute("SELECT DISTINCT member_id, email, project_id FROM checkin_event WHERE day=?", (day,)).fetchall():
            if member_ids and r["member_id"] in seen: continue
            m = next((x for x in members_by_email(r["email"]) if x["member_id"] == r["member_id"]), None)
            if m and (not member_ids or r["member_id"] in member_ids): recompute(day, m); seen.add(r["member_id"])

    def in_ctx(fn):
        from flask import has_app_context
        def w(*a, **k):
            if has_app_context(): return fn(*a, **k)
            with app.app_context(): return fn(*a, **k)       # the background thread has no request
        return w

    def refresh_recent():
        t = now().date(); [refresh((t - timedelta(days=i)).isoformat()) for i in (0, 1)]
    A.mobile_refresh_recent, A.mobile_refresh = in_ctx(refresh_recent), in_ctx(refresh)

    def day_view(em, day):
        out = []
        for m in members_by_email(em):
            a = A.db().execute("SELECT * FROM app_day WHERE day=? AND user_id=?", (day, m["member_id"])).fetchone()
            r = A.db().execute("SELECT * FROM attendance WHERE day=? AND user_id=?", (day, m["member_id"])).fetchone()
            ev = A.evaluate(dict(r) if r else None)
            out.append({"project": (A.proj(m["project_id"]) or {}).get("name", ""), "status": ev["status"], "in": (r["in_time"] if r else "") or "", "out": (r["out_time"] if r else "") or "",
                        "went_out": a["exits"] if a else 0, "minutes_out": a["break_min"] if a else 0, "leave": (r["leave_type"] if r else "") or ""})
        return out

    @app.route("/api/m/me/today")
    @api
    def m_today(em):
        day = request.args.get("date") or now().date().isoformat()
        try: date.fromisoformat(day)
        except ValueError: return jsonify(error="bad_date"), 400
        refresh(day)
        evs = [dict(id=r["id"], kind=r["kind"], at=r["event_at"], site=r["site_id"], result=r["trust"], reasons=r["reasons"] or "",
                    distance=r["distance_m"], accuracy=r["accuracy"])
               for r in A.db().execute("SELECT * FROM checkin_event WHERE email=? AND day=? ORDER BY event_at", (em, day))]
        return jsonify(day=day, summary=day_view(em, day), events=evs)

    @app.route("/api/m/me/history")
    @api
    def m_history(em):
        days = max(1, min(60, int(request.args.get("days", 14) or 14))); out = []
        for i in range(days):
            d = (now().date() - timedelta(days=i)).isoformat(); v = day_view(em, d)
            if any(x["in"] or x["out"] or x["leave"] for x in v):
                evs = [dict(id=r["id"], kind=r["kind"], at=r["event_at"], site=r["site_id"], result=r["trust"], reasons=r["reasons"] or "",
                            distance=r["distance_m"], accuracy=r["accuracy"])
                       for r in A.db().execute("SELECT * FROM checkin_event WHERE email=? AND day=? ORDER BY event_at", (em, d))]
                out.append({"day": d, "summary": v, "events": evs})
        return jsonify(days=out)

    @app.route("/api/m/dispute", methods=["POST"])
    @api
    def m_dispute(em):
        j = request.get_json(silent=True) or {}; note = " ".join(str(j.get("note", "")).split())[:300]; day = str(j.get("day", ""))
        try: date.fromisoformat(day)
        except ValueError: return jsonify(error="bad_date"), 400
        ms = members_by_email(em)
        if len(note) < 3 or not ms: return jsonify(error="bad_request"), 400
        A.db().execute("INSERT INTO app_dispute(day,user_id,email,note,created_at) VALUES(?,?,?,?,?)", (day, ms[0]["member_id"], em, note, now().isoformat(timespec="seconds"))); A.db().commit()
        try:
            category = "Punch Discrepancy"
            if note.startswith("[") and "]" in note:
                category = note[1:note.index("]")]
            p_leads = [r["email"] for r in A.db().execute("SELECT email FROM project_access WHERE project_id=? AND kind='lead'", (str(ms[0]["project_id"]),)).fetchall() if r["email"]]
            mailer.notify_dispute_filed(p_leads, ms[0]["name"], em, day, category, note)
        except Exception as ex:
            app.logger.warning("mailer dispute notify error: %s", ex)
        return jsonify(ok=True)

    # ------------------------------------------------------------ review screen (TL/PM, admin; managers view only)
    @app.route("/review")
    @A.login_required
    def review():
        day = A.get_day(); ps = A.shown_projects(); refresh(day)
        pid = request.args.get("project") or (ps[0]["id"] if ps else "")
        if pid not in [p["id"] for p in A.my_projects()]: abort(404)
        rows = []
        for m in A.members(pid):
            a = A.db().execute("SELECT * FROM app_day WHERE day=? AND user_id=?", (day, m["id"])).fetchone()
            r = A.db().execute("SELECT * FROM attendance WHERE day=? AND user_id=?", (day, m["id"])).fetchone()
            evs = [dict(x) for x in A.db().execute("SELECT * FROM checkin_event WHERE day=? AND member_id=? ORDER BY event_at", (day, m["id"]))]
            for e in evs: e["time"] = (e["event_at"] or "")[11:16]
            diff = bool(a and r and ((a["app_in"] and a["app_in"] != (r["in_time"] or "")) or (a["app_out"] and a["app_out"] != (r["out_time"] or ""))))
            rows.append({"m": m, "a": dict(a) if a else None, "r": dict(r) if r else {}, "evs": evs, "diff": diff,
                         "bad": sum(1 for e in evs if e["trust"] in ("rejected", "flagged"))})
        devices = [dict(d) for d in A.db().execute("SELECT * FROM device WHERE pending_id IS NOT NULL AND pending_id<>'' ORDER BY email")
                   if any(mm["email"].lower() == d["email"] for p in [pid] for mm in A.members(p))]
        disputes = [dict(d) for d in A.db().execute("SELECT * FROM app_dispute WHERE day=? AND status='open' ORDER BY id", (day,))
                    if d["user_id"] in {m["id"] for m in A.members(pid)}]
        return render_template("review.html", day=day, projects=ps, pid=pid, rows=rows, devices=devices, disputes=disputes, editable=A.can_edit(pid),
                               sites=[dict(s) for s in A.db().execute("SELECT * FROM site WHERE project_id=? AND active=1", (pid,))])

    @app.route("/review/accept", methods=["POST"])
    @A.login_required
    def review_accept():
        f = request.form; pid, uid, day = f.get("project", ""), f.get("user", ""), A.get_day()
        can = A.can_edit_attendance(pid, day) if hasattr(A, "can_edit_attendance") else A.can_edit(pid)
        if not can: abort(403, "Past days can be changed by an admin only.")
        m = next((x for x in A.members(pid) if x["id"] == uid), None)
        a = A.db().execute("SELECT * FROM app_day WHERE day=? AND user_id=?", (day, uid)).fetchone()
        if not m or not a: abort(404)
        r = A.db().execute("SELECT * FROM attendance WHERE day=? AND user_id=?", (day, uid)).fetchone(); t = now().isoformat(timespec="seconds"); who = A.email()
        if r and r["leave_type"]: flash(f"{m['name']} is marked on leave - clear the leave first.", "err"); return redirect(url_for("review", date=day, project=pid))
        i, o = a["app_in"] or (r["in_time"] if r else ""), a["app_out"] or (r["out_time"] if r else "")
        if r: A.db().execute("UPDATE attendance SET in_time=?, out_time=?, updated_by=?, updated_at=? WHERE day=? AND user_id=?", (i, o, who, t, day, uid))
        else: A.db().execute("""INSERT INTO attendance(day,user_id,user_name,in_time,out_time,leave_type,planned,handled_by,remarks,updated_by,updated_at,shift_start)
                                VALUES(?,?,?,?,?,'','','','',?,?,?)""", (day, uid, m["name"], i, o, who, t, m["shift"] or A.SHIFT_START))
        A.db().execute("UPDATE app_day SET merged_in=?, merged_out=? WHERE day=? AND user_id=?", (i, o, day, uid)); A.db().commit()
        flash(f"{m['name']}: app times accepted.", "ok"); return redirect(url_for("review", date=day, project=pid))

    @app.route("/review/device", methods=["POST"])
    @A.login_required
    def review_device():
        f = request.form; em = f.get("email", "").lower(); pid = f.get("project", "")
        if not A.can_edit(pid) or not any(x["email"].lower() == em for x in A.members(pid)): abort(403)
        d = A.db().execute("SELECT * FROM device WHERE email=?", (em,)).fetchone()
        if not d or not d["pending_id"]: abort(404)
        if f.get("action") == "approve":
            A.db().execute("UPDATE device SET device_id=?, model=?, status='approved', pending_id=NULL, pending_model=NULL, approved_by=?, registered_at=? WHERE email=?",
                           (d["pending_id"], d["pending_model"], A.email(), now().isoformat(timespec="seconds"), em)); flash("New phone approved.", "ok")
        else:
            A.db().execute("UPDATE device SET pending_id=NULL, pending_model=NULL WHERE email=?", (em,)); flash("New phone refused.", "ok")
        A.db().commit(); return redirect(url_for("review", project=pid, date=A.get_day()))

    @app.route("/review/dispute", methods=["POST"])
    @A.login_required
    def review_dispute():
        pid = request.form.get("project", "")
        if not A.can_edit(pid): abort(403)
        d = A.db().execute("SELECT * FROM app_dispute WHERE id=?", (int(request.form.get("id", 0) or 0),)).fetchone()
        if not d or d["user_id"] not in {m["id"] for m in A.members(pid)}: abort(404)
        A.db().execute("UPDATE app_dispute SET status='resolved', resolved_by=? WHERE id=?", (A.email(), d["id"])); A.db().commit()
        try:
            att = A.db().execute("SELECT in_time, out_time FROM attendance WHERE day=? AND user_id=?", (d["day"], d["user_id"])).fetchone()
            in_t = att["in_time"] if att else ""
            out_t = att["out_time"] if att else ""
            mem = A.team_row(d["user_id"])
            emp_name = mem["name"] if mem else d["email"]
            mailer.notify_dispute_resolved(d["email"], emp_name, d["day"], in_t, out_t, A.email())
        except Exception as ex:
            app.logger.warning("mailer dispute resolve error: %s", ex)
        flash("Marked as resolved.", "ok"); return redirect(url_for("review", project=pid, date=A.get_day()))

    # ------------------------------------------------------------ site setup (TL/PM, admin)
    @app.route("/sites/save", methods=["POST"])
    @A.login_required
    def sites_save():
        f = request.form; pid = f.get("project", "")
        if not A.can_edit(pid): abort(403, "Only the project lead or an admin can set up a site.")
        class Bad(ValueError): pass
        try:
            try: name = A.v_project(f.get("name", ""))
            except ValueError as ex: raise Bad(str(ex))
            try: lat, lon, rad = float(f.get("lat", "")), float(f.get("lon", "")), int(f.get("radius", "")); di, do = int(f.get("dwell_in", "5")), int(f.get("dwell_out", "10"))
            except ValueError: raise Bad("Latitude, longitude, radius and wait times must be numbers.")
            mode = f.get("beacon_mode", "off")
            if not (-90 <= lat <= 90 and -180 <= lon <= 180): raise Bad("Latitude must be between -90 and 90 and longitude between -180 and 180.")
            lo, hi = limits()
            if not (lo <= rad <= hi): raise Bad(f"Radius must be between {lo} and {hi} metres.")
            if not (1 <= di <= 60 and 1 <= do <= 120): raise Bad("Wait times must be 1 to 60 minutes (arrival) and 1 to 120 minutes (leaving).")
            if mode not in ("off", "any", "all"): raise Bad("Unknown beacon setting.")
            ids = [x.strip().upper() for x in f.get("beacon_ids", "").replace("\n", ",").split(",") if x.strip()]
            if mode != "off" and not ids: raise Bad("Enter at least one Wi-Fi/Bluetooth identifier, or set the beacon rule to Off.")
            if any(len(x) > 64 for x in ids) or len(ids) > 20: raise Bad("Beacon identifiers: up to 20, each up to 64 characters.")
        except Bad as ex:
            flash(str(ex), "err"); return redirect(f.get("next") or request.referrer or url_for("projects_page"))
        sid, t = f.get("site_id", ""), now().isoformat(timespec="seconds")
        if f.get("action") == "remove" and sid:
            A.db().execute("UPDATE site SET active=0, updated_by=?, updated_at=? WHERE id=? AND project_id=?", (A.email(), t, sid, pid)); flash("Site removed.", "ok")
        elif sid:
            A.db().execute("UPDATE site SET name=?,lat=?,lon=?,radius=?,dwell_in=?,dwell_out=?,beacon_mode=?,beacon_ids=?,updated_by=?,updated_at=? WHERE id=? AND project_id=?",
                           (name, lat, lon, rad, di, do, mode, ",".join(ids), A.email(), t, sid, pid)); flash("Site saved.", "ok")
        else:
            A.db().execute("INSERT INTO site(project_id,name,lat,lon,radius,dwell_in,dwell_out,beacon_mode,beacon_ids,updated_by,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?)",
                           (pid, name, lat, lon, rad, di, do, mode, ",".join(ids), A.email(), t)); flash("Site added.", "ok")
        A.db().commit(); return redirect(f.get("next") or request.referrer or url_for("projects_page"))

    # ------------------------------------------------------------ retention
    def purge_events():
        """Remove coordinates from events older than the retention period; the IN/OUT times stay in the attendance record."""
        cut = (now() - timedelta(days=RETENTION_DAYS)).isoformat(timespec="seconds"); c = A.Conn()
        n = c.execute("UPDATE checkin_event SET lat=NULL, lon=NULL, accuracy=NULL, beacons=NULL WHERE received_at<? AND lat IS NOT NULL", (cut,)).rowcount
        c.commit(); c.close(); return n

    A.purge_events = purge_events
    A.mobile_site_rows = lambda pid: [dict(s) for s in A.db().execute("SELECT * FROM site WHERE project_id=? AND active=1 ORDER BY id", (str(pid),))]
    A.MOBILE = {"radius_min": ENV_MIN, "radius_max": ENV_MAX, "retention_days": RETENTION_DAYS}

    @app.context_processor
    def mobile_ctx(): return {"mobile": {"radius_min": limits()[0], "radius_max": limits()[1], "retention_days": RETENTION_DAYS}}

    @app.route("/sites/limits", methods=["POST"])
    @A.login_required
    def sites_limits():
        if not A.is_admin(): abort(403)
        nxt = request.form.get("next") or request.referrer or url_for("projects_page")
        try: lo, hi = int(request.form.get("lo", "")), int(request.form.get("hi", ""))
        except ValueError: lo = hi = 0
        if not (5 <= lo <= hi <= 5000): flash("Give two whole numbers, minimum 5 and maximum 5000 metres, minimum not above maximum.", "err"); return redirect(nxt)
        for k, v in (("radius_min", lo), ("radius_max", hi)):
            A.db().execute("INSERT INTO meta(k,v) VALUES(?,?) ON CONFLICT(k) DO UPDATE SET v=excluded.v", (k, str(v)))
        A.db().commit(); flash(f"Site radius can now be set between {lo} and {hi} metres.", "ok"); return redirect(nxt)
