-- Migration: Cascading deletion of permissions and active team memberships on app_users delete
-- Applied: 2026-10-15
-- Strategy: Option B (Purge permissions, deactivate team membership, preserve attendance logs)

CREATE OR REPLACE FUNCTION fn_app_users_after_delete()
RETURNS TRIGGER AS $$
BEGIN
    -- 1. Purge authorization permissions
    DELETE FROM access WHERE lower(email) = lower(OLD.email);
    DELETE FROM project_access WHERE lower(email) = lower(OLD.email);
    DELETE FROM watch WHERE lower(email) = lower(OLD.email);
    
    -- 2. Deactivate team assignments
    UPDATE team 
    SET active = 0, 
        assigned_to = CURRENT_TIMESTAMP, 
        user_id = NULL
    WHERE lower(email) = lower(OLD.email) OR (OLD.id IS NOT NULL AND user_id = OLD.id);
    
    RETURN OLD;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_app_users_delete ON app_users;
CREATE TRIGGER trg_app_users_delete
AFTER DELETE ON app_users
FOR EACH ROW
EXECUTE FUNCTION fn_app_users_after_delete();
