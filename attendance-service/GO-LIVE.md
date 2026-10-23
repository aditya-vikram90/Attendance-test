# Go-live for testing

Goal: the attendance service runs beside OpenProject on the same server, stores its data in the same
PostgreSQL server, and signs people in through the same Keycloak, so nobody logs in twice.

The service is served at `https://pm.keenable.io/attendance`, on the same domain and certificate as OpenProject.
No new DNS record or certificate is needed. Replace `keycloak.example.com` and `your-realm` with your Keycloak address and realm.

## 1. Address

Nothing new to set up. The domain is `pm.keenable.io`:

| Address | What opens |
|---|---|
| `https://pm.keenable.io/` | OpenProject - this stays the default page, exactly as now |
| `https://pm.keenable.io/attendance/` | The attendance service |

The Nginx block in step 6 only catches addresses that begin with `/attendance`; everything else keeps going to OpenProject.

**HTTPS:** this guide uses `https://`. If the site currently answers only on `http://`, set up the certificate first
(for example `sudo certbot --nginx -d pm.keenable.io`, which requests a certificate for the domain and adds it to Nginx).
Keycloak sign-in and the session cookies of both OpenProject and this service should not run over plain HTTP.
If you must test on plain HTTP for a short while, write `http://` in `BASE_URL` and in the Keycloak redirect URI; the service then
allows its cookie over HTTP.

## 2. Database: same PostgreSQL server, separate database

The service gets its own database and its own user inside the PostgreSQL container OpenProject already uses.
It never touches OpenProject's tables.

```bash
# Open a SQL prompt inside the OpenProject database container as the PostgreSQL superuser.
# If your superuser is not "postgres", use the name from your openproject-db settings.
sudo podman exec -it openproject-db psql -U postgres
```

Then at the `postgres=#` prompt:

```sql
-- Create a login for the service (choose a strong password)
CREATE USER attendance WITH PASSWORD 'choose-a-strong-password';
-- Create its own database, owned by that login
CREATE DATABASE attendance OWNER attendance;
-- Leave the SQL prompt
\q
```

The service creates its tables by itself on first start.

Both containers must be on the same Podman network so the name `openproject-db` resolves:

```bash
# Show which network(s) the database container is attached to
sudo podman inspect openproject-db --format '{{range $k,$v := .NetworkSettings.Networks}}{{$k}} {{end}}'
```

Put that network name in `deploy/attendance.container` on the `Network=` line (remove the `#`).
If the database container uses the default "podman" network instead of a named one, containers cannot find each
other by name there; in that case publish the database port to localhost only and use
`host.containers.internal` as the host in `DATABASE_URL`.

## 3. Keycloak: client and roles

In the realm OpenProject uses:

1. **Client:** Clients > Create client. Client ID `attendance`, Client authentication ON, Standard flow ON.
   Valid redirect URI `https://pm.keenable.io/attendance/auth/callback`. Web origin `https://pm.keenable.io`.
   Copy the secret from the Credentials tab.
2. **Roles (optional but recommended):** Realm roles > Create role, twice: `attendance-admin` and `attendance-manager`.
   Assign `attendance-admin` to yourself and `attendance-manager` to senior managers who should view every project.
3. Nothing is needed for TL/PMs and engineers in Keycloak: they are recognised by their email.

Because OpenProject and this service share the realm, someone already signed in to OpenProject is signed in here
without seeing a login page.

## 4. Settings file

```bash
# Create the settings folder
sudo mkdir -p /etc/attendance

# Copy the example settings, then edit every "change-me" value
sudo cp deploy/attendance.env.example /etc/attendance/attendance.env

# Keep it readable by root only - it holds passwords and tokens
sudo chmod 600 /etc/attendance/attendance.env

# Print a random string to paste in as SECRET_KEY
openssl rand -hex 32
```

Values to set: `BASE_URL` (`https://pm.keenable.io/attendance`, no trailing slash), `SECRET_KEY`, `DATABASE_URL` (password from step 2), `OIDC_ISSUER`, `OIDC_CLIENT_SECRET`,
`ADMIN_EMAILS` (your email, as a fallback admin), `OP_URL` + `OP_API_KEY` (optional), `SUMMARY_TO` and `SMTP_*`
(same mail details OpenProject uses), `SHIFT_START`, `GRACE_MIN`, `WEEKLY_OFF`.
Make sure there is no `DEV_MODE` line.

## 5. Build and start

```bash
# Build the image as root so systemd can find it
sudo podman build -t attendance .

# Install the Quadlet unit (after setting the Network= line)
sudo cp deploy/attendance.container /etc/containers/systemd/

# Make systemd read the new unit
sudo systemctl daemon-reload

# Start the service; it also starts on every boot
sudo systemctl start attendance

# See the last log lines - look for database or Keycloak errors
sudo journalctl -u attendance -n 40 --no-pager

# Should print "ok"
curl http://127.0.0.1:8090/healthz
```

## 6. Nginx

Open the Nginx file that serves pm.keenable.io and paste the contents of `deploy/nginx-attendance.conf`
inside its `server { ... }` block, above the existing `location / { ... }` block.

```bash
# Find which Nginx file serves the OpenProject site
sudo grep -rl "pm.keenable.io" /etc/nginx/

# After pasting the block in, check the configuration for mistakes
sudo nginx -t

# Apply it without dropping connections
sudo systemctl reload nginx

# Should print "ok" - this goes through Nginx and the /attendance path
curl https://pm.keenable.io/attendance/healthz
```

## 7. Who gets what (RBAC)

| Role | How a person gets it | What they see |
|---|---|---|
| Admin | Keycloak role `attendance-admin`, or email in `ADMIN_EMAILS` | Everything |
| Sr Manager, all teams | Keycloak role `attendance-manager` | All projects, view only |
| Sr Manager, selected teams | Admin adds them on the Access page and ticks their projects | Only those projects (and their sub-projects), view only |
| Project Manager / TL | Admin types their email under Edit on the project | Only their projects: team, attendance, summary, trends, history |
| Engineer | TL/PM fills in their email on the team page | Only "My attendance" |
| Anyone else in the realm | - | "No access yet" message |

## 8. Link from OpenProject

Pick one for the test phase:

- **Project menu (per project):** in the project, create a wiki page named "Attendance" containing the link
  `https://pm.keenable.io/attendance/`, then on that page choose More > Configure menu item > Show as menu item in project navigation.
- **Project overview:** add a "Custom text" widget with the link.
- **Everyone's home page:** Administration > Settings > General > Welcome block text; add the link there.

A real top-level "Attendance" tab inside OpenProject needs a small OpenProject plugin and a custom OpenProject image.
That depends on your OpenProject version, so it is best done after the test phase.

## 9. Test checklist

1. Open OpenProject, sign in, click the Attendance link: you should land in the service with no second login.
2. As admin: create a project, set a TL/PM email, add a manager on the Access page.
3. As that TL/PM (another browser or private window): you see only that project; add engineers with emails; enter a day.
4. As an engineer: you land on "My attendance" and every other address sends you back there.
5. As a manager with selected projects: you see only those; nothing is editable.
6. Summary > "Email this summary now" arrives.
7. Restart the service (`sudo systemctl restart attendance`) and confirm the data is still there (it is in PostgreSQL).

## 10. Backup

The attendance database lives in the same PostgreSQL server, so add it to your existing backup script:

```bash
# Dump the attendance database to a dated file
sudo podman exec openproject-db pg_dump -U postgres attendance | gzip > /root/backup/attendance-$(date +%F).sql.gz
```
