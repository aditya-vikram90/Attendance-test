"""
Keenable Attendance Mailer System.
Asynchronous, non-blocking email dispatch using Google Workspace SMTP relay.
All notifications are strictly gated by dynamic admin configuration toggles (app_config).
"""

import os
import smtplib
import ssl
import logging
from concurrent.futures import ThreadPoolExecutor
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from datetime import datetime

import app_config

logger = logging.getLogger("mailer")

# Non-blocking background worker pool
_executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix="mailer")

def _get_smtp_settings():
    return {
        "host": os.environ.get("SMTP_HOST", "smtp.gmail.com").strip(),
        "port": int(os.environ.get("SMTP_PORT", "587")),
        "user": os.environ.get("SMTP_USER", "oppm@fosteringlinux.com").strip(),
        "password": os.environ.get("SMTP_PASSWORD", "bfqzkypnkcmtqrrb").strip(),
        "from_email": os.environ.get("SMTP_FROM", "oppm@fosteringlinux.com").strip(),
        "display_name": os.environ.get("SMTP_DISPLAY_NAME", "Keenable Portal").strip(),
        "base_url": os.environ.get("BASE_URL", "https://pm.keenable.io/attendance").rstrip("/")
    }

def _send_raw_email(to_list, subject, html_content, plain_content=""):
    """Internal synchronous function executed inside ThreadPoolExecutor."""
    cfg = _get_smtp_settings()
    if not cfg["host"] or not to_list:
        logger.warning("SMTP host not configured or recipient list empty.")
        return False, "SMTP host or recipients empty"

    if isinstance(to_list, str):
        to_list = [e.strip() for e in to_list.split(",") if e.strip()]

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = f"{cfg['display_name']} <{cfg['from_email']}>"
    msg["To"] = ", ".join(to_list)

    if not plain_content:
        plain_content = "This email requires an HTML compatible email viewer."

    msg.attach(MIMEText(plain_content, "plain", "utf-8"))
    msg.attach(MIMEText(html_content, "html", "utf-8"))

    try:
        with smtplib.SMTP(cfg["host"], cfg["port"], timeout=20) as server:
            server.starttls(context=ssl.create_default_context())
            if cfg["user"] and cfg["password"]:
                server.login(cfg["user"], cfg["password"])
            server.sendmail(cfg["from_email"], to_list, msg.as_string())
        logger.info("Successfully dispatched email '%s' to %s", subject, to_list)
        return True, "Email sent successfully"
    except Exception as ex:
        err = f"Failed to send email to {to_list}: {ex}"
        logger.error(err)
        return False, str(ex)

def _dispatch_async(config_key, to_list, subject, html_content, plain_content=""):
    """Checks admin toggle before submitting to executor."""
    if config_key and not app_config.get_config(config_key, True):
        logger.info("Email '%s' to %s suppressed by admin config toggle '%s'", subject, to_list, config_key)
        return False

    _executor.submit(_send_raw_email, to_list, subject, html_content, plain_content)
    return True

def _email_wrapper(title, header_title, content_html):
    """Clean, modern HTML template shell with Keenable navy branding."""
    cfg = _get_smtp_settings()
    portal_url = f"{cfg['base_url']}/"
    return f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<style>
  body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; background: #f8fafc; margin: 0; padding: 24px; color: #1e293b; }}
  .container {{ max-width: 600px; margin: 0 auto; background: #ffffff; border-radius: 12px; border: 1px solid #e2e8f0; overflow: hidden; box-shadow: 0 4px 6px -1px rgba(0,0,0,0.05); }}
  .header {{ background: #1F3864; padding: 24px 32px; color: #ffffff; }}
  .logo {{ display: inline-block; background: #ffffff; color: #1F3864; font-weight: 800; font-size: 16px; width: 28px; height: 28px; line-height: 28px; text-align: center; border-radius: 6px; margin-bottom: 8px; }}
  .header h1 {{ margin: 0; font-size: 18px; font-weight: 700; }}
  .header p {{ margin: 4px 0 0; font-size: 12px; color: #cbd5e1; }}
  .content {{ padding: 32px; }}
  .card {{ background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 8px; padding: 18px; margin: 18px 0; }}
  .card table {{ width: 100%; border-collapse: collapse; }}
  .card td {{ padding: 6px 0; font-size: 13px; vertical-align: top; }}
  .card td.lbl {{ width: 140px; color: #64748b; font-weight: 500; }}
  .card td.val {{ color: #0f172a; font-weight: 600; }}
  .badge-green {{ background: #dcfce7; color: #166534; padding: 3px 8px; border-radius: 4px; font-size: 11px; font-weight: 700; display: inline-block; }}
  .badge-amber {{ background: #fef3c7; color: #b45309; padding: 3px 8px; border-radius: 4px; font-size: 11px; font-weight: 700; display: inline-block; }}
  .badge-red {{ background: #fee2e2; color: #991b1b; padding: 3px 8px; border-radius: 4px; font-size: 11px; font-weight: 700; display: inline-block; }}
  .btn {{ background: #1F3864; color: #ffffff !important; text-decoration: none; padding: 10px 24px; border-radius: 6px; font-size: 13px; font-weight: 600; display: inline-block; margin: 16px 0; }}
  .footer {{ background: #f8fafc; border-top: 1px solid #e2e8f0; padding: 16px 32px; font-size: 11px; color: #94a3b8; line-height: 1.5; }}
</style>
</head>
<body>
<div class="container">
  <div class="header">
    <div class="logo">K</div>
    <h1>{header_title}</h1>
    <p>Keenable Attendance & Project Management System</p>
  </div>
  <div class="content">
    {content_html}
  </div>
  <div class="footer">
    This is an automated notification from Keenable Attendance System.<br>
    Portal URL: <a href="{portal_url}" style="color:#64748b;">{portal_url}</a>
  </div>
</div>
</body>
</html>"""


# ==============================================================================
# Public Notification Functions
# ==============================================================================

def send_test_email(to_email):
    """Sends a synchronous test email and returns (success, message)."""
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    subject = "Keenable Attendance - SMTP Configuration Test"
    content = f"""
    <h3 style="margin-top:0;color:#0f172a;">SMTP Configuration Successful!</h3>
    <p style="font-size:14px;color:#475569;line-height:1.6;">
      This test message confirms that your Google Workspace SMTP relay is properly configured and actively delivering emails.
    </p>
    <div class="card">
      <table>
        <tr><td class="lbl">Server:</td><td class="val">smtp.gmail.com:587 (STARTTLS)</td></tr>
        <tr><td class="lbl">Sender:</td><td class="val">oppm@fosteringlinux.com</td></tr>
        <tr><td class="lbl">Recipient:</td><td class="val">{to_email}</td></tr>
        <tr><td class="lbl">Timestamp:</td><td class="val">{now_str}</td></tr>
        <tr><td class="lbl">Status:</td><td class="val"><span class="badge-green">DELIVERED</span></td></tr>
      </table>
    </div>
    <p style="font-size:12px;color:#64748b;">You can now safely enable automated event notifications in Admin Settings.</p>
    """
    html = _email_wrapper(subject, "SMTP Diagnostics & Verification", content)
    return _send_raw_email([to_email], subject, html, "SMTP Test successful.")


def notify_project_assignment(emp_email, emp_name, project_name, role, sites=None, shift_start="09:30", shift_end="18:30", pm_name="Project Manager", pm_email=""):
    """Notifies employee when assigned or transferred to a project."""
    sites_str = ", ".join([s.get("name", "Site") if isinstance(s, dict) else str(s) for s in (sites or [])]) or "Main Office"
    subject = f"Project Assignment: You have been assigned to {project_name}"
    content = f"""
    <p style="font-size:14px;color:#334155;">Hello <b>{emp_name}</b>,</p>
    <p style="font-size:14px;color:#475569;line-height:1.6;">
      You have been officially assigned to <b>{project_name}</b>. Please find your project onboarding details below:
    </p>
    <div class="card">
      <table>
        <tr><td class="lbl">Project:</td><td class="val">{project_name}</td></tr>
        <tr><td class="lbl">Designated Role:</td><td class="val">{role or 'Software Engineer'}</td></tr>
        <tr><td class="lbl">Work Site(s):</td><td class="val">{sites_str}</td></tr>
        <tr><td class="lbl">Standard Shift:</td><td class="val">{shift_start} - {shift_end}</td></tr>
        <tr><td class="lbl">Reporting Manager:</td><td class="val">{pm_name} {f'({pm_email})' if pm_email else ''}</td></tr>
      </table>
    </div>
    <p style="font-size:13px;color:#64748b;">
      Your mobile attendance app has automatically updated to reflect this project and its authorized geofenced sites.
    </p>
    <center><a href="{_get_smtp_settings()['base_url']}/" class="btn">Open Portal</a></center>
    """
    html = _email_wrapper(subject, "Project Assignment Notification", content)
    _dispatch_async("email.project_assignment_notify_emp", emp_email, subject, html)


def notify_new_team_member(pm_email, pm_name, emp_name, emp_email, role, project_name):
    """Alerts Project Manager when a new engineer is assigned to their team."""
    if not pm_email: return
    subject = f"Team Update: {emp_name} added to {project_name}"
    content = f"""
    <p style="font-size:14px;color:#334155;">Hello <b>{pm_name}</b>,</p>
    <p style="font-size:14px;color:#475569;line-height:1.6;">
      A new engineer has been assigned to your project roster:
    </p>
    <div class="card">
      <table>
        <tr><td class="lbl">Engineer Name:</td><td class="val">{emp_name}</td></tr>
        <tr><td class="lbl">Email:</td><td class="val">{emp_email}</td></tr>
        <tr><td class="lbl">Role:</td><td class="val">{role or 'Software Engineer'}</td></tr>
        <tr><td class="lbl">Project:</td><td class="val">{project_name}</td></tr>
      </table>
    </div>
    <center><a href="{_get_smtp_settings()['base_url']}/team" class="btn">View Team Roster</a></center>
    """
    html = _email_wrapper(subject, "New Team Member Allocated", content)
    _dispatch_async("email.project_assignment_notify_pm", pm_email, subject, html)


def notify_checkin(emp_email, emp_name, site_name, checkin_time, is_geofence=True):
    """Dispatches real-time morning check-in confirmation to employee."""
    subject = f"Check-In Confirmed: {checkin_time} at {site_name}"
    content = f"""
    <p style="font-size:14px;color:#334155;">Hello <b>{emp_name}</b>,</p>
    <p style="font-size:14px;color:#475569;line-height:1.6;">
      Your attendance check-in for today has been recorded:
    </p>
    <div class="card">
      <table>
        <tr><td class="lbl">Punch In Time:</td><td class="val">{checkin_time}</td></tr>
        <tr><td class="lbl">Location / Site:</td><td class="val">{site_name}</td></tr>
        <tr><td class="lbl">Method:</td><td class="val">{'Geofence Auto-Detection' if is_geofence else 'Manual Check-In'}</td></tr>
        <tr><td class="lbl">Verification:</td><td class="val"><span class="badge-green">VERIFIED</span></td></tr>
      </table>
    </div>
    <p style="font-size:12px;color:#94a3b8;">Have a productive workday!</p>
    """
    html = _email_wrapper(subject, "Attendance Check-In Confirmed", content)
    _dispatch_async("email.daily_checkin_confirmation", emp_email, subject, html)


def notify_checkout(emp_email, emp_name, checkout_time, hours_worked, break_minutes=0):
    """Dispatches evening check-out confirmation with hours summary."""
    subject = f"Check-Out Recorded: {checkout_time} — Daily Summary"
    content = f"""
    <p style="font-size:14px;color:#334155;">Hello <b>{emp_name}</b>,</p>
    <p style="font-size:14px;color:#475569;line-height:1.6;">
      Your departure has been recorded. Here is your shift summary for today:
    </p>
    <div class="card">
      <table>
        <tr><td class="lbl">Punch Out Time:</td><td class="val">{checkout_time}</td></tr>
        <tr><td class="lbl">Total Hours on Site:</td><td class="val">{hours_worked}</td></tr>
        <tr><td class="lbl">Breaks Outside Site:</td><td class="val">{break_minutes} min</td></tr>
        <tr><td class="lbl">Shift Status:</td><td class="val"><span class="badge-green">COMPLETED</span></td></tr>
      </table>
    </div>
    """
    html = _email_wrapper(subject, "Daily Shift Summary", content)
    _dispatch_async("email.daily_checkout_summary", emp_email, subject, html)


def notify_leave_applied(pm_emails, emp_name, leave_type, from_date, to_date, reason, is_half_day=False):
    """Alerts PM when an employee submits a leave request."""
    if not pm_emails: return
    duration_str = "Half-Day" if is_half_day else f"{from_date} to {to_date}" if from_date != to_date else from_date
    subject = f"Leave Application: {emp_name} ({leave_type} - {duration_str})"
    content = f"""
    <p style="font-size:14px;color:#334155;">A leave request has been submitted requiring your decision:</p>
    <div class="card">
      <table>
        <tr><td class="lbl">Applicant:</td><td class="val">{emp_name}</td></tr>
        <tr><td class="lbl">Leave Type:</td><td class="val">{leave_type}</td></tr>
        <tr><td class="lbl">Period:</td><td class="val">{duration_str}</td></tr>
        <tr><td class="lbl">Reason:</td><td class="val">{reason or 'Not specified'}</td></tr>
        <tr><td class="lbl">Status:</td><td class="val"><span class="badge-amber">PENDING APPROVAL</span></td></tr>
      </table>
    </div>
    <center><a href="{_get_smtp_settings()['base_url']}/leaves" class="btn">Review & Decide Leave</a></center>
    """
    html = _email_wrapper(subject, "Leave Request Received", content)
    _dispatch_async("email.leave_application_notify_pm", pm_emails, subject, html)


def notify_leave_acknowledgement(emp_email, emp_name, leave_type, from_date, to_date):
    """Sends submission acknowledgement to employee."""
    duration_str = f"{from_date} to {to_date}" if from_date != to_date else from_date
    subject = f"Leave Request Received: {duration_str}"
    content = f"""
    <p style="font-size:14px;color:#334155;">Hello <b>{emp_name}</b>,</p>
    <p style="font-size:14px;color:#475569;line-height:1.6;">
      Your application for <b>{leave_type}</b> ({duration_str}) has been received and routed to your Project Manager for review.
      You will receive an email update once a decision is made.
    </p>
    """
    html = _email_wrapper(subject, "Leave Request Submitted", content)
    _dispatch_async("email.leave_application_ack_emp", emp_email, subject, html)


def notify_leave_decided(emp_email, emp_name, status, decider_name, from_date, to_date, remarks=""):
    """Notifies employee when leave is approved or rejected."""
    is_approved = status.lower() == "approved"
    badge_cls = "badge-green" if is_approved else "badge-red"
    duration_str = f"{from_date} to {to_date}" if from_date != to_date else from_date
    subject = f"Leave Request {status.upper()}: {duration_str}"
    content = f"""
    <p style="font-size:14px;color:#334155;">Hello <b>{emp_name}</b>,</p>
    <p style="font-size:14px;color:#475569;line-height:1.6;">
      Your leave request has been reviewed by <b>{decider_name}</b>:
    </p>
    <div class="card">
      <table>
        <tr><td class="lbl">Leave Period:</td><td class="val">{duration_str}</td></tr>
        <tr><td class="lbl">Decision:</td><td class="val"><span class="{badge_cls}">{status.upper()}</span></td></tr>
        <tr><td class="lbl">Reviewer Remarks:</td><td class="val">{remarks or 'None provided'}</td></tr>
      </table>
    </div>
    <center><a href="{_get_smtp_settings()['base_url']}/me" class="btn">View Attendance Record</a></center>
    """
    html = _email_wrapper(subject, f"Leave Request {status.title()}", content)
    _dispatch_async("email.leave_decision_notify_emp", emp_email, subject, html)


def notify_dispute_filed(pm_emails, emp_name, emp_email, day, category, note):
    """Alerts Project Manager when employee submits an attendance dispute."""
    if not pm_emails: return
    subject = f"Attendance Issue Reported: {emp_name} for {day}"
    content = f"""
    <p style="font-size:14px;color:#334155;">An attendance dispute has been filed from mobile app:</p>
    <div class="card">
      <table>
        <tr><td class="lbl">Employee:</td><td class="val">{emp_name} ({emp_email})</td></tr>
        <tr><td class="lbl">Target Date:</td><td class="val">{day}</td></tr>
        <tr><td class="lbl">Issue Category:</td><td class="val"><span class="badge-amber">{category}</span></td></tr>
        <tr><td class="lbl">Employee Note:</td><td class="val">{note or 'No details provided'}</td></tr>
      </table>
    </div>
    <center><a href="{_get_smtp_settings()['base_url']}/review?day={day}" class="btn">Review & Resolve Dispute</a></center>
    """
    html = _email_wrapper(subject, "Attendance Dispute Alert", content)
    _dispatch_async("email.dispute_filed_notify_pm", pm_emails, subject, html)


def notify_dispute_resolved(emp_email, emp_name, day, updated_in, updated_out, resolver_name):
    """Notifies employee when dispute is resolved."""
    subject = f"Attendance Dispute Resolved for {day}"
    content = f"""
    <p style="font-size:14px;color:#334155;">Hello <b>{emp_name}</b>,</p>
    <p style="font-size:14px;color:#475569;line-height:1.6;">
      Your reported attendance issue for <b>{day}</b> has been reviewed and resolved by <b>{resolver_name}</b>:
    </p>
    <div class="card">
      <table>
        <tr><td class="lbl">Date:</td><td class="val">{day}</td></tr>
        <tr><td class="lbl">Punch In:</td><td class="val">{updated_in or '--:--'}</td></tr>
        <tr><td class="lbl">Punch Out:</td><td class="val">{updated_out or '--:--'}</td></tr>
        <tr><td class="lbl">Resolution:</td><td class="val"><span class="badge-green">RESOLVED & VERIFIED</span></td></tr>
      </table>
    </div>
    """
    html = _email_wrapper(subject, "Attendance Dispute Resolved", content)
    _dispatch_async("email.dispute_resolved_notify_emp", emp_email, subject, html)
