package io.keenable.keycloak.storage;

import org.jboss.logging.Logger;
import org.keycloak.component.ComponentModel;
import org.keycloak.credential.CredentialInput;
import org.keycloak.credential.CredentialInputUpdater;
import org.keycloak.credential.CredentialInputValidator;
import org.keycloak.models.GroupModel;
import org.keycloak.models.KeycloakSession;
import org.keycloak.models.RealmModel;
import org.keycloak.models.UserModel;
import org.keycloak.models.credential.PasswordCredentialModel;
import org.keycloak.storage.StorageId;
import org.keycloak.storage.UserStorageProvider;
import org.keycloak.storage.user.UserLookupProvider;
import org.keycloak.storage.user.UserQueryProvider;
import org.keycloak.storage.user.UserRegistrationProvider;

import java.sql.Connection;
import java.sql.DriverManager;
import java.sql.PreparedStatement;
import java.sql.ResultSet;
import java.sql.SQLException;
import java.util.ArrayList;
import java.util.List;
import java.util.Map;
import java.util.stream.Stream;

public class AttendanceUserStorageProvider implements UserStorageProvider, UserLookupProvider,
        UserQueryProvider, CredentialInputValidator, CredentialInputUpdater, UserRegistrationProvider {

    private static final Logger logger = Logger.getLogger(AttendanceUserStorageProvider.class);

    private final KeycloakSession session;
    private final ComponentModel model;

    public AttendanceUserStorageProvider(KeycloakSession session, ComponentModel model) {
        this.session = session;
        this.model = model;
    }

    public Connection getConnection() throws SQLException {
        String url = model.get("jdbcUrl", "jdbc:postgresql://openproject-db:5432/users");
        String user = model.get("dbUser", "users_admin");
        String pass = model.get("dbPassword", "UsersAdmin2026!");
        return DriverManager.getConnection(url, user, pass);
    }

    @Override
    public void close() {
        // No persistent resources to close
    }

    @Override
    public UserModel getUserById(RealmModel realm, String id) {
        String externalId = StorageId.externalId(id);
        try {
            int userId = Integer.parseInt(externalId);
            return findUser(realm, "SELECT id, username, email, first_name, last_name, phone, role_title, system_role, must_change_password, totp_enabled, active FROM app_users WHERE id = ?", userId);
        } catch (NumberFormatException e) {
            return null;
        }
    }

    @Override
    public UserModel getUserByUsername(RealmModel realm, String username) {
        return findUser(realm, "SELECT id, username, email, first_name, last_name, phone, role_title, system_role, must_change_password, totp_enabled, active FROM app_users WHERE lower(username) = lower(?) OR lower(email) = lower(?)", username, username);
    }

    @Override
    public UserModel getUserByEmail(RealmModel realm, String email) {
        return findUser(realm, "SELECT id, username, email, first_name, last_name, phone, role_title, system_role, must_change_password, totp_enabled, active FROM app_users WHERE lower(email) = lower(?)", email);
    }

    private UserModel findUser(RealmModel realm, String sql, Object... params) {
        try (Connection conn = getConnection();
             PreparedStatement ps = conn.prepareStatement(sql)) {
            for (int i = 0; i < params.length; i++) {
                ps.setObject(i + 1, params[i]);
            }
            try (ResultSet rs = ps.executeQuery()) {
                if (rs.next()) {
                    AttendanceUser u = new AttendanceUser(
                            rs.getInt("id"),
                            rs.getString("username"),
                            rs.getString("email"),
                            rs.getString("first_name"),
                            rs.getString("last_name"),
                            rs.getString("phone"),
                            rs.getString("role_title"),
                            rs.getString("system_role"),
                            rs.getBoolean("must_change_password"),
                            rs.getBoolean("totp_enabled"),
                            rs.getInt("active")
                    );
                    return new AttendanceUserAdapter(session, realm, model, u, this);
                }
            }
        } catch (Exception e) {
            logger.error("Failed to query user from users DB", e);
        }
        return null;
    }

    @Override
    public int getUsersCount(RealmModel realm) {
        try (Connection conn = getConnection();
             PreparedStatement ps = conn.prepareStatement("SELECT count(*) FROM app_users WHERE active = 1");
             ResultSet rs = ps.executeQuery()) {
            if (rs.next()) return rs.getInt(1);
        } catch (Exception e) {
            logger.error("Failed to count users", e);
        }
        return 0;
    }

    @Override
    public Stream<UserModel> searchForUserStream(RealmModel realm, Map<String, String> params, Integer firstResult, Integer maxResults) {
        String search = params.get("keycloak.session.realm.users.query.search");
        if (search == null) search = params.get("username");
        if (search == null) search = params.get("email");
        return searchForUserStream(realm, search != null ? search : "", firstResult, maxResults);
    }

    @Override
    public Stream<UserModel> searchForUserStream(RealmModel realm, String search, Integer firstResult, Integer maxResults) {
        List<UserModel> users = new ArrayList<>();
        StringBuilder sql = new StringBuilder("SELECT id, username, email, first_name, last_name, phone, role_title, system_role, must_change_password, totp_enabled, active FROM app_users WHERE active = 1");
        boolean hasFilter = search != null && !search.trim().isEmpty();
        if (hasFilter) {
            sql.append(" AND (lower(email) LIKE ? OR lower(first_name) LIKE ? OR lower(last_name) LIKE ? OR lower(username) LIKE ?)");
        }
        sql.append(" ORDER BY id");
        if (maxResults != null && maxResults > 0) {
            sql.append(" LIMIT ").append(maxResults);
        }
        if (firstResult != null && firstResult > 0) {
            sql.append(" OFFSET ").append(firstResult);
        }
        try (Connection conn = getConnection();
             PreparedStatement ps = conn.prepareStatement(sql.toString())) {
            if (hasFilter) {
                String pattern = "%" + search.trim().toLowerCase() + "%";
                ps.setString(1, pattern);
                ps.setString(2, pattern);
                ps.setString(3, pattern);
                ps.setString(4, pattern);
            }
            try (ResultSet rs = ps.executeQuery()) {
                while (rs.next()) {
                    AttendanceUser u = new AttendanceUser(
                            rs.getInt("id"),
                            rs.getString("username"),
                            rs.getString("email"),
                            rs.getString("first_name"),
                            rs.getString("last_name"),
                            rs.getString("phone"),
                            rs.getString("role_title"),
                            rs.getString("system_role"),
                            rs.getBoolean("must_change_password"),
                            rs.getBoolean("totp_enabled"),
                            rs.getInt("active")
                    );
                    users.add(new AttendanceUserAdapter(session, realm, model, u, this));
                }
            }
        } catch (Exception e) {
            logger.error("Failed to search users from users DB", e);
        }
        return users.stream();
    }

    @Override
    public Stream<UserModel> getGroupMembersStream(RealmModel realm, GroupModel group, Integer firstResult, Integer maxResults) {
        return Stream.empty();
    }

    @Override
    public Stream<UserModel> searchForUserByUserAttributeStream(RealmModel realm, String attrName, String attrValue) {
        return Stream.empty();
    }

    // --- User Registration / Removal ---

    @Override
    public UserModel addUser(RealmModel realm, String username) {
        String email = username.contains("@") ? username.trim().toLowerCase() : (username.trim() + "@fosteringlinux.com").toLowerCase();
        String name = username.contains("@") ? username.split("@")[0].replace(".", " ").trim() : username.trim();
        try (Connection conn = getConnection();
             PreparedStatement ps = conn.prepareStatement(
                     "INSERT INTO app_users(username, email, name, first_name, last_name, role_title, system_role, active, created_at, updated_at) " +
                     "VALUES (?, ?, ?, ?, '', 'Developer', 'member', 1, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP) RETURNING id")) {
            ps.setString(1, email);
            ps.setString(2, email);
            ps.setString(3, name);
            ps.setString(4, name);
            try (ResultSet rs = ps.executeQuery()) {
                if (rs.next()) {
                    int id = rs.getInt(1);
                    AttendanceUser u = new AttendanceUser(
                            id, email, email, name, "", "", "Developer", "member", false, false, 1
                    );
                    logger.infof("Created user %s (id: %d) in app_users with default system_role=member", email, id);
                    return new AttendanceUserAdapter(session, realm, model, u, this);
                }
            }
        } catch (Exception e) {
            logger.error("Failed to add user " + username, e);
        }
        return null;
    }

    @Override
    public boolean removeUser(RealmModel realm, UserModel user) {
        String externalId = StorageId.externalId(user.getId());
        try {
            int userId = Integer.parseInt(externalId);
            try (Connection conn = getConnection();
                 PreparedStatement ps = conn.prepareStatement("DELETE FROM app_users WHERE id = ?")) {
                ps.setInt(1, userId);
                int count = ps.executeUpdate();
                logger.infof("Removed user %s (id: %d) from app_users: %s", user.getUsername(), userId, count > 0);
                return count > 0;
            }
        } catch (Exception e) {
            logger.error("Failed to remove user " + user.getUsername(), e);
            return false;
        }
    }

    // --- Credential Validation ---

    @Override
    public boolean supportsCredentialType(String credentialType) {
        return PasswordCredentialModel.TYPE.equals(credentialType);
    }

    @Override
    public boolean isConfiguredFor(RealmModel realm, UserModel user, String credentialType) {
        return supportsCredentialType(credentialType);
    }

    @Override
    public boolean isValid(RealmModel realm, UserModel user, CredentialInput input) {
        if (!supportsCredentialType(input.getType())) return false;
        String externalId = StorageId.externalId(user.getId());
        try {
            int userId = Integer.parseInt(externalId);
            try (Connection conn = getConnection();
                 PreparedStatement ps = conn.prepareStatement(
                         "SELECT (crypt(?, password_hash) = password_hash) AS match FROM app_users WHERE id = ? AND active = 1")) {
                ps.setString(1, input.getChallengeResponse());
                ps.setInt(2, userId);
                try (ResultSet rs = ps.executeQuery()) {
                    if (rs.next()) {
                        return rs.getBoolean("match");
                    }
                }
            }
        } catch (Exception e) {
            logger.error("Failed to validate credentials for user " + user.getUsername(), e);
        }
        return false;
    }

    // --- Credential Update ---

    @Override
    public boolean updateCredential(RealmModel realm, UserModel user, CredentialInput input) {
        if (!supportsCredentialType(input.getType())) return false;
        String externalId = StorageId.externalId(user.getId());
        try {
            int userId = Integer.parseInt(externalId);
            try (Connection conn = getConnection();
                 PreparedStatement ps = conn.prepareStatement(
                         "UPDATE app_users SET password_hash = crypt(?, gen_salt('bf', 10)), must_change_password = false, updated_at = CURRENT_TIMESTAMP WHERE id = ?")) {
                ps.setString(1, input.getChallengeResponse());
                ps.setInt(2, userId);
                int updated = ps.executeUpdate();
                return updated > 0;
            }
        } catch (Exception e) {
            logger.error("Failed to update password for user " + user.getUsername(), e);
        }
        return false;
    }

    @Override
    public void disableCredentialType(RealmModel realm, UserModel user, String credentialType) {
        // No-op
    }

    @Override
    public Stream<String> getDisableableCredentialTypesStream(RealmModel realm, UserModel user) {
        return Stream.empty();
    }
}
