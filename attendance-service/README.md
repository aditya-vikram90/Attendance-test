# Attendance service for OpenProject

A small web service that sits beside OpenProject.

- **Who uses it:** admins, managers, TL/PMs, and engineers (who see only their own attendance).
- **Projects:** created inside the service by an admin or a TL/PM. Linking a project to an OpenProject project is optional.
- **Main and sub-projects:** a main project can have any number of sub-projects, each with its own team and attendance. The TL/PM (or manager) of a main project also gets its sub-projects, and Summary, History and Excel for a main project include them.
- **Own shift per engineer:** each engineer can have their own shift start time on the team page; if none is set the default `SHIFT_START` (09:30) applies. Late arrival is judged against that engineer's shift. Night shifts that end the next morning are handled. The shift in force is saved with each day's entry, so changing a shift later does not alter past days.
- **Trends:** a Trends page shows, for the last 7 to 90 days, the daily on-time / late / leave / absent pattern, the average arrival against shift start, lateness by weekday, and a per-engineer regularity table that flags irregular attendance.
- **Database:** SQLite by default; set `DATABASE_URL` to use PostgreSQL (see GO-LIVE.md).
- **Keycloak roles:** `attendance-admin` and `attendance-manager` roles are honoured, in addition to the email-based access.
- **Validation:** engineer name is letters only; role must start with a letter; contact number must be a 10-digit mobile number (6-9 first, +91 or 0 in front accepted) and unique within a project; emails and project names are checked too.
- **My team:** the TL/PM adds each engineer with role and contact number (typed by hand, or ticked from the linked OpenProject project's members).
- **Enter attendance:** the TL/PM fills in time, out time and leave for each engineer, one tab per project.
- **History:** every entry is stored in the database. The History page shows any past month as a day-by-day grid; click a day to open that day's summary.
- **OpenProject (optional, read only):** for linked projects it offers the members as team candidates and shows the open work packages of anyone on leave. Nothing is written to OpenProject. Leave `OP_URL` empty to run without it.
- **Sign-in:** Keycloak single sign-on.
- **Summary:** web page, daily email, daily Excel and monthly Excel, for all your projects or one selected project.

**Going live: follow GO-LIVE.md.**

## Try it on your laptop first (no OpenProject, no Keycloak)

Demo mode skips sign-in and signs you in as an admin. Start on the Projects page and create a project.

```bash
# Build the container image from this folder and name it "attendance"
podman build -t attendance .

# Run it in demo mode on port 8090; data is kept in a throwaway volume
podman run --rm -e DEV_MODE=1 -p 8090:8000 -v attendance-demo:/data localhost/attendance
```

Open http://localhost:8090.

## Install on the server

**1. Keycloak client.** In the realm OpenProject uses, create a client:
client ID `attendance`, client authentication ON, valid redirect URI
`https://pm.keenable.io/attendance/auth/callback`. Copy its secret from the Credentials tab.

**2. OpenProject API token.** Sign in to OpenProject as an admin user, go to
My account > Access tokens, and generate an API token. An admin token is needed so the
service can read all projects, memberships and member emails.

**3. Settings file.**

```bash
# Create the settings folder
sudo mkdir -p /etc/attendance

# Copy the example settings there, then fill in every "change-me" value
sudo cp deploy/attendance.env.example /etc/attendance/attendance.env

# Make the file readable by root only - it holds the token and passwords
sudo chmod 600 /etc/attendance/attendance.env

# Print a random string to use as SECRET_KEY
openssl rand -hex 32
```

**4. Build and start (Podman Quadlet).**

```bash
# Build the image as root so the systemd unit can find it
sudo podman build -t attendance .

# Install the Quadlet unit that describes the container
sudo cp deploy/attendance.container /etc/containers/systemd/

# Make systemd read the new unit
sudo systemctl daemon-reload

# Start the service (it also starts on every boot)
sudo systemctl start attendance

# Check it is running and see the latest log lines
sudo systemctl status attendance

# Confirm it answers locally - should print "ok"
curl http://127.0.0.1:8090/healthz
```

**5. Nginx.** Copy `deploy/nginx-attendance.conf` into your Nginx sites, set the server
name and certificate, then:

```bash
# Check the Nginx configuration for mistakes
sudo nginx -t

# Apply the new configuration without dropping connections
sudo systemctl reload nginx
```

## Link from OpenProject

As far as I know OpenProject Community has no setting for a custom link in the top
menu. Two ways that work:

- **Project side menu:** create a wiki page in the project containing the link to
  the attendance service, then use the wiki page's More > Configure menu item to show it
  in the project menu.
- **Project overview:** add a "Custom text" widget to the project overview page with the link.

Because both use the same Keycloak sign-in, clicking the link does not ask for a password again.
The service itself has a "Back to OpenProject" link in its header.

## Who can do what

| Person | Set where | Sees | Can change |
|---|---|---|---|
| Admin | `ADMIN_EMAILS` in the settings file | All projects | Everything: projects, TL/PMs, access, teams, attendance |
| Manager | Access page (by an admin) | All projects, or the ones the admin ticked. Can tick a personal watch list on the Projects page | Nothing - view and Excel only |
| TL/PM | "TL/PM emails" under Edit on a project, or the Access page | Only their own projects (a main project includes its sub-projects) | Their teams and attendance; can add projects and sub-projects |
| Engineer | Their email on the team page | Only their own attendance ("My attendance") | Nothing |
| Anyone else | - | No access | - |

A person is recognised by the email Keycloak reports at sign-in, so type emails exactly as they are in Keycloak.
The daily email covers all projects and goes to `SUMMARY_TO`.

In demo mode the header has an "act as email" box so you can try each role without Keycloak.

## Rules (all in the settings file)

| Setting | Default | Meaning |
|---|---|---|
| `SHIFT_START` | 09:30 | Shift start time |
| `GRACE_MIN` | 15 | Arriving later than start + grace counts as late |
| `SHIFT_HOURS` | 9 | 8 hours work + 1 hour lunch |
| `WEEKLY_OFF` | Sat,Sun | Days not counted as absent in the monthly report, no email sent |
| `SUMMARY_TIME` | 11:00 | Time the daily email is sent |

After changing settings: `sudo systemctl restart attendance` (restarts the container so it reads the new values).

## Things to know

- Removing an engineer from a team keeps their past attendance; they still appear in History and the monthly report for months where they have entries.
- An engineer picked from OpenProject who belongs to several projects has **one** attendance record per day; it shows in each project tab.
- There is no holiday calendar. In the monthly report, a working day where nothing was entered for anyone shows `-` instead of marking everyone absent.
- Project and member lists from OpenProject are cached for 5 minutes.
- Data is in the `attendance-data` volume (`/data/attendance.db`, SQLite). Back it up with:

```bash
# Copy the database file out of the running container to the current folder
sudo podman cp attendance:/data/attendance.db ./attendance-backup.db
```

## Update to a new version

```bash
# Rebuild the image from the updated folder
sudo podman build -t attendance .

# Restart so the service runs the new image
sudo systemctl restart attendance
```
