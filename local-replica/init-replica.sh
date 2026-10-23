#!/bin/bash
set -e

echo "=== [1/5] Creating Database Roles (attendance, keycloak, users_admin) ==="
psql -U openproject -d postgres <<-EOSQL
    DO \$\$
    BEGIN
        IF NOT EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = 'attendance') THEN
            CREATE ROLE attendance WITH LOGIN PASSWORD 'Att3nd_Pass_2026_Sec!';
        END IF;
        IF NOT EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = 'keycloak') THEN
            CREATE ROLE keycloak WITH LOGIN PASSWORD 'KC_Db_Pass_2026_Sec!';
        END IF;
        IF NOT EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = 'users_admin') THEN
            CREATE ROLE users_admin WITH LOGIN PASSWORD 'UsersAdmin2026!';
        END IF;
    END \$\$;
EOSQL

echo "=== [2/5] Creating Databases (users, attendance, keycloak) ==="
psql -U openproject -d postgres <<-EOSQL
    SELECT 'CREATE DATABASE users OWNER users_admin' WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'users')\gexec
    SELECT 'CREATE DATABASE attendance OWNER attendance' WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'attendance')\gexec
    SELECT 'CREATE DATABASE keycloak OWNER keycloak' WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'keycloak')\gexec

    GRANT ALL PRIVILEGES ON DATABASE users TO users_admin;
    GRANT ALL PRIVILEGES ON DATABASE users TO attendance;
    GRANT ALL PRIVILEGES ON DATABASE attendance TO attendance;
    GRANT ALL PRIVILEGES ON DATABASE keycloak TO keycloak;
EOSQL

echo "=== [3/5] Initializing 'users' Database & Master app_users Table ==="
psql -U openproject -d users <<-EOSQL
    CREATE EXTENSION IF NOT EXISTS pgcrypto;

    CREATE TABLE IF NOT EXISTS app_users (
        id SERIAL PRIMARY KEY,
        username VARCHAR(120) UNIQUE NOT NULL,
        email VARCHAR(120) UNIQUE NOT NULL,
        name VARCHAR(100) NOT NULL,
        first_name VARCHAR(100) NOT NULL,
        last_name VARCHAR(100) DEFAULT '',
        phone VARCHAR(20) UNIQUE,
        role_title VARCHAR(60) DEFAULT 'Developer',
        system_role VARCHAR(40) DEFAULT 'member',
        password_hash VARCHAR(255) NOT NULL,
        must_change_password BOOLEAN DEFAULT FALSE,
        totp_enabled BOOLEAN DEFAULT FALSE,
        totp_secret VARCHAR(64) DEFAULT NULL,
        current_project_id INT DEFAULT NULL,
        current_shift_start VARCHAR(10) DEFAULT '09:30',
        active INT DEFAULT 1,
        created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
    );

    CREATE INDEX IF NOT EXISTS idx_app_users_email ON app_users(lower(email));

    INSERT INTO app_users (username, email, name, first_name, last_name, phone, role_title, system_role, password_hash, must_change_password, totp_enabled, active)
    VALUES
    ('admin@keenable.io', 'admin@keenable.io', 'System Admin', 'System', 'Admin', '9999999990', 'Admin', 'admin', crypt('KeenableAdmin2026!', gen_salt('bf', 10)), false, true, 1),
    ('pm.sharma@keenable.io', 'pm.sharma@keenable.io', 'Rahul Sharma', 'Rahul', 'Sharma', '9999999991', 'Project Manager', 'project-manager', crypt('KeenablePM2026!', gen_salt('bf', 10)), false, true, 1),
    ('pm.verma@keenable.io', 'pm.verma@keenable.io', 'Priya Verma', 'Priya', 'Verma', '9999999992', 'Project Manager', 'project-manager', crypt('KeenablePM2026!', gen_salt('bf', 10)), false, true, 1),
    ('dev.arun@keenable.io', 'dev.arun@keenable.io', 'Arun Kumar', 'Arun', 'Kumar', '9999999993', 'Frontend Engineer', 'member', crypt('KeenableDev2026!', gen_salt('bf', 10)), false, true, 1),
    ('dev.neha@keenable.io', 'dev.neha@keenable.io', 'Neha Gupta', 'Neha', 'Gupta', '9999999994', 'Backend Engineer', 'member', crypt('KeenableDev2026!', gen_salt('bf', 10)), false, false, 1),
    ('dev.vikram@keenable.io', 'dev.vikram@keenable.io', 'Vikram Singh', 'Vikram', 'Singh', '9999999995', 'DevOps Engineer', 'member', crypt('KeenableDev2026!', gen_salt('bf', 10)), false, false, 1),
    ('dev.sadik@keenable.io', 'dev.sadik@keenable.io', 'Mohd Sadik', 'Mohd', 'Sadik', '9090909090', 'Developer', 'member', crypt('KeenableDev2026!', gen_salt('bf', 10)), false, false, 1)
    ON CONFLICT (email) DO UPDATE SET
        password_hash = EXCLUDED.password_hash,
        system_role = EXCLUDED.system_role;

    GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO users_admin;
    GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO users_admin;
    GRANT SELECT ON ALL TABLES IN SCHEMA public TO attendance;
EOSQL

echo "=== [4/5] Initializing 'attendance' Database (Foreign Table & Seed Data) ==="
psql -U openproject -d attendance <<-EOSQL
    CREATE EXTENSION IF NOT EXISTS pgcrypto;
    CREATE EXTENSION IF NOT EXISTS postgres_fdw;

    CREATE SERVER IF NOT EXISTS users_db_server
        FOREIGN DATA WRAPPER postgres_fdw
        OPTIONS (host '127.0.0.1', dbname 'users', port '5432');

    DROP USER MAPPING IF EXISTS FOR attendance SERVER users_db_server;
    CREATE USER MAPPING FOR attendance
        SERVER users_db_server
        OPTIONS (user 'users_admin', password 'UsersAdmin2026!', password_required 'false');

    DROP USER MAPPING IF EXISTS FOR openproject SERVER users_db_server;
    CREATE USER MAPPING FOR openproject
        SERVER users_db_server
        OPTIONS (user 'users_admin', password 'UsersAdmin2026!', password_required 'false');

    DROP FOREIGN TABLE IF EXISTS app_users;
    IMPORT FOREIGN SCHEMA public LIMIT TO (app_users) FROM SERVER users_db_server INTO public;

    -- Seed Projects
    CREATE TABLE IF NOT EXISTS project (
        id SERIAL PRIMARY KEY,
        name VARCHAR(100) NOT NULL,
        op_project_id VARCHAR(50),
        parent_id INTEGER,
        active INTEGER DEFAULT 1,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );

    INSERT INTO project (id, name) VALUES 
    (1, 'Cloud Migration & Infra'),
    (2, 'Client Web Portal')
    ON CONFLICT (id) DO NOTHING;

    -- Seed Team Assignments
    CREATE TABLE IF NOT EXISTS team (
        id SERIAL PRIMARY KEY,
        project_id VARCHAR(50) NOT NULL,
        member_id VARCHAR(100) NOT NULL,
        name VARCHAR(100) NOT NULL,
        role VARCHAR(60),
        phone VARCHAR(20),
        email VARCHAR(120),
        op_user_id VARCHAR(50),
        active INTEGER DEFAULT 1,
        user_id INTEGER,
        shift_start VARCHAR(10),
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        assigned_from TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        assigned_to TIMESTAMP,
        UNIQUE(project_id, member_id)
    );

    INSERT INTO team (project_id, member_id, name, role, email, phone, shift_start, active) VALUES
    ('1', 'm_101', 'Rahul Sharma', 'Project Manager', 'pm.sharma@keenable.io', '9999999991', '09:30', 1),
    ('1', 'm_102', 'Neha Gupta', 'Backend Engineer', 'dev.neha@keenable.io', '9999999994', '09:30', 1),
    ('1', 'm_103', 'Vikram Singh', 'DevOps Engineer', 'dev.vikram@keenable.io', '9999999995', '09:30', 1),
    ('1', 'm_104', 'Mohd Sadik', 'Developer', 'dev.sadik@keenable.io', '9090909090', '09:30', 1),
    ('2', 'm_201', 'Priya Verma', 'Project Manager', 'pm.verma@keenable.io', '9999999992', '09:30', 1),
    ('2', 'm_202', 'Arun Kumar', 'Frontend Engineer', 'dev.arun@keenable.io', '9999999993', '09:30', 1)
    ON CONFLICT (project_id, member_id) DO NOTHING;

    -- Seed Access
    CREATE TABLE IF NOT EXISTS access (
        email TEXT PRIMARY KEY,
        name TEXT,
        role TEXT NOT NULL,
        all_projects INTEGER NOT NULL DEFAULT 0
    );

    INSERT INTO access (email, name, role, all_projects) VALUES
    ('admin@keenable.io', 'System Admin', 'admin', 1),
    ('pm.sharma@keenable.io', 'Rahul Sharma', 'lead', 0),
    ('pm.verma@keenable.io', 'Priya Verma', 'lead', 0)
    ON CONFLICT (email) DO NOTHING;

    -- Seed Project Access
    CREATE TABLE IF NOT EXISTS project_access (
        project_id TEXT NOT NULL,
        email TEXT NOT NULL,
        kind TEXT NOT NULL,
        PRIMARY KEY(project_id, email, kind)
    );

    INSERT INTO project_access (project_id, email, kind) VALUES
    ('1', 'pm.sharma@keenable.io', 'lead'),
    ('2', 'pm.verma@keenable.io', 'lead')
    ON CONFLICT (project_id, email, kind) DO NOTHING;

    GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO attendance;
    GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO attendance;
EOSQL

echo "=== [5/5] Database Initialization Complete! ==="
