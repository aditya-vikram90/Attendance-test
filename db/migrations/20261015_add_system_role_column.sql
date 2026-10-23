-- Migration: Add system_role column to app_users
-- Applied: 2026-10-15

ALTER TABLE app_users ADD COLUMN IF NOT EXISTS system_role VARCHAR(30) DEFAULT 'member';

UPDATE app_users SET system_role = 'admin' WHERE lower(email) IN ('admin@keenable.io', 'rohit.kumar@fosteringlinux.com', 'mankesh.pandey@fosteringlinux.com');

UPDATE app_users 
SET system_role = 'project-manager' 
WHERE system_role <> 'admin' 
  AND (
      lower(email) IN (SELECT lower(email) FROM access WHERE role IN ('manager', 'lead'))
      OR lower(email) IN (SELECT lower(email) FROM project_access)
      OR lower(role_title) LIKE '%manager%' 
      OR lower(role_title) LIKE '%lead%'
  );

UPDATE app_users SET system_role = 'member' WHERE system_role IS NULL OR system_role NOT IN ('admin', 'project-manager');
