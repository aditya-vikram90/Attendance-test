# Implementation Plan: Attendance Service Enhancements & Bug Fixes

Address the 5 critical issues identified during testing: date-aware attendance filtering for newly assigned users in Summary and Trends, Keycloak signout session termination, removing the shift arrival chart, adding user-wise journey tracking in Trends and Summary (for both Leads/Admins and individual Engineers), and interactive tooltips with improved bar chart visualization.

---

## User Review Required

> [!IMPORTANT]
> **No code changes will be deployed until you explicitly review and approve this plan.**
> Please review the proposed solutions below for each of the 5 issues.

---

## 1. Issue Understanding & Root Cause Analysis

### Issue 1: Newly Created/Assigned Users Shown as Absent in Summary & Trends
* **Symptom**: 
  * `Arun Kumar Pal` (assigned to *Mobile Banking App* today, Oct 14) shows `Absent (no info)` in `/summary?date=2026-10-14` and `1 absent (0 of 1)` in `/trends`.
  * `Mohd Sameer` (assigned to *Client Web Portal* today, Oct 14) shows `Absent (no info)` in Summary and `2 absent (0 of 2, Irregular)` in Trends.
* **Root Cause**:
  * Earlier, we added `assigned_from` / `assigned_to` filtering to `/me`, which is why their personal attendance page correctly shows `Unassigned / Bench`.
  * However, **`/summary` (`build_summary()`)** and **`/trends` (`trends()`)** still fetch `roster(pids)` (all current active members) without checking whether the user was actually assigned on that date ($assigned\_from \le date \le assigned\_to$).
  * In addition, `build_summary()` marks any unentered member as `Absent` even when attendance for their project has not been entered at all for that day.
* **Solution**:
  1. **Date-Aware Roster**: Modify `roster(pids, for_date=...)` or filter members against their `assigned_from` and `assigned_to` timestamps. If a user was not assigned to the project on date $D$, they must not be evaluated as absent for date $D$.
  2. **Summary Unentered vs. Absent**: In `build_summary()`, if no attendance has been entered for an engineer's project on that date (`entered(u, recs)` is False), do not classify them as `Absent`. Only classify as `Absent` if attendance was entered for that project on that date and the user was left blank/unmarked.

---

### Issue 2: Sign Out Is Not Working
* **Symptom**: Clicking "Sign out" redirects or reloads, but the user remains logged in.
* **Root Cause**:
  * `/logout` clears the local Flask `session`, then redirects to Keycloak's logout endpoint:
    `{issuer}/protocol/openid-connect/logout?client_id={client_id}&post_logout_redirect_uri={base_url}/`
  * In OpenID Connect (OIDC RP-Initiated Logout), if `id_token_hint` is missing, Keycloak does not automatically terminate the Keycloak browser SSO session without user interaction.
  * Furthermore, Keycloak redirects back to `{base_url}/` (the root URL), which has `@login_required`. The browser immediately triggers `/login`, which detects the still-active Keycloak SSO cookie and automatically logs the user right back in!
* **Solution**:
  1. Store `id_token` in Flask session upon login callback (`auth_callback`).
  2. In `/logout`, pass `id_token_hint={id_token}` to Keycloak's logout endpoint so Keycloak terminates the realm session.
  3. Direct `post_logout_redirect_uri` to a clean dedicated logout endpoint (e.g. `/attendance/login?logged_out=1`) that renders a "You have signed out" message with a "Log in again" button rather than auto-redirecting back to Keycloak.

---

### Issue 3: Comment Out "Arrival trend: average minutes after own shift start"
* **Symptom**: The chart "Arrival trend: average minutes after own shift start" is cluttering the Trends page.
* **Solution**:
  * Comment out the SVG section in `templates/trends.html` using Jinja comments `{# ... #}` so it is safely preserved in the template for future use without being rendered to the user.

---

### Issue 4: User-Wise Trends & Summary Journey (For Admins, Leads, and Engineers)
* **Symptom**: 
  * Managers/Leads cannot focus on an individual engineer's journey across the month.
  * Engineers (`role == 'engineer'`) are hard-redirected away from `/trends` and `/summary` (`my_role() == "engineer" and request.endpoint != "me": return redirect(url_for("me"))`).
* **Solution**:
  1. **Engineer Access Scoping**:
     * Allow engineers to access `/trends` and `/summary`.
     * For engineers, automatically scope `user_id` to their own account (`my_member_ids()`), disabling switching to other users.
  2. **User Dropdown Filter**:
     * Add a `User` filter dropdown on `/trends` and `/summary` (populated with team members for Leads/Admins, or locked to self for Engineers).
     * In `/trends`, selecting a specific user filters the Daily Pattern chart and regularity stats to display that individual's daily attendance journey over the period.
     * In `/summary`, selecting a user highlights their monthly record, attendance percentage, and irregularity status.

---

### Issue 5: Daily Attendance Pattern Hover Tooltips & Bar Chart Rendering
* **Symptom**: 
  * Default SVG `<title>` tooltips have an annoying browser delay, are difficult to trigger on thin SVG rects, and only show a single slice rather than the day's full status.
  * Bars are thin slivers with excessive empty horizontal space across 30 days.
* **Solution**:
  1. **Full-Column Hover Zone**: Add a transparent `<rect>` overlay covering the entire vertical column for each day, making it effortless to hover over any day regardless of bar height.
  2. **Rich Interactive Tooltip**: Create an instant HTML/CSS floating tooltip (or SVG overlay card) that displays on hover:
     * Date & weekday (e.g., `Wed, 14 Oct 2026`)
     * Total present (On-time count + Late count)
     * On leave count & Absent count
     * When filtered by a specific user: exact status (`Present at 10:00 (Late by 30m)`, `On Leave`, `Unassigned / Bench`, or `Weekly off`).
  3. **Visual Bar Enhancements**: Increase bar thickness, set a minimum visible height for nonzero entries, and add rounded corners for a modern, legible appearance.

---

## Proposed Changes

### Backend (`attendance-service/app.py`)

#### [MODIFY] [app.py](file:///home/user/Desktop/Projects/management/attendance/attendance-service/app.py)
* **`build_summary(day, with_tasks=True, pids=None, user_id=None)`**:
  * Filter roster using `assigned_from` and `assigned_to` for date `day`.
  * Check `entered_checker()` so team members whose project attendance hasn't been submitted for `day` are not incorrectly marked as `Absent`.
  * Support optional `user_id` parameter to filter for an individual user's summary.
* **`trends()`**:
  * In the daily loop, check each member's assignment date range (`assigned_from <= ds <= assigned_to`). Skip past days when the engineer was not yet part of that project team.
  * Support `user` query parameter (`?user=<member_id>`) to generate user-specific daily trends.
* **`auth_callback()` & `logout()`**:
  * Capture and persist `tok.get("id_token")` in `session["id_token"]`.
  * Update `/logout` to pass `id_token_hint` and redirect to `/login?logged_out=1`.
  * Update `/login` to render a clean signed-out screen when `?logged_out=1` is present.
* **Role Permissions (`login_required`)**:
  * Allow engineers to view `/trends` and `/summary`, auto-locking the view to their own member record.

---

### Frontend Templates (`attendance-service/templates/`)

#### [MODIFY] [trends.html](file:///home/user/Desktop/Projects/management/attendance/attendance-service/templates/trends.html)
* Comment out the "Arrival trend: average minutes after own shift start" section.
* Add **User** selector dropdown in the filter bar.
* Replace native SVG `<title>` tags with full-column hover targets and an instant rich tooltip component showing full daily breakdown.
* Enhance SVG bar styling (proportional width, rounded caps, clear contrast).

#### [MODIFY] [summary.html](file:///home/user/Desktop/Projects/management/attendance/attendance-service/templates/summary.html)
* Add **User** filter dropdown in the filter bar.
* Distinguish between confirmed `Absent` vs. unentered projects.

#### [MODIFY] [base.html](file:///home/user/Desktop/Projects/management/attendance/attendance-service/templates/base.html)
* Update navigation links so engineers can see "Trends" and "Summary" tabs (scoped to their own data).
* Include CSS styles for the interactive chart tooltip.

---

## Verification Plan

### Automated / Diagnostic Verification
1. Run test client queries inside the container simulating:
   * `Arun Kumar Pal` and `Mohd Sameer` on `/trends` and `/summary` to verify `absent == 0`.
   * Engineer role accessing `/trends` and `/summary` to verify data is scoped exclusively to themselves.
   * Keycloak logout flow generating valid `id_token_hint`.

### Manual Browser Verification
1. Log in as Admin/TL:
   * Verify `/summary` shows 0 absent for newly created engineers whose attendance is unentered.
   * Verify `/trends` displays the User dropdown and accurately shows an individual's monthly journey.
   * Hover over the Daily Attendance Pattern bars to confirm immediate, rich tooltip rendering.
   * Confirm the arrival trend chart is hidden.
2. Log in as Engineer (`dev.vishal@fosteringlinux.com`):
   * Confirm Trends and Summary are visible and display their own attendance history.
3. Sign Out Verification:
   * Click "Sign out" and verify the session terminates cleanly in both Keycloak and the application without auto-logging back in.
