package io.keenable.keycloak.storage;

import org.jboss.logging.Logger;
import org.keycloak.component.ComponentModel;
import org.keycloak.models.KeycloakSession;
import org.keycloak.models.RealmModel;
import org.keycloak.models.RoleModel;
import org.keycloak.models.UserModel;
import org.keycloak.storage.StorageId;
import org.keycloak.storage.adapter.AbstractUserAdapterFederatedStorage;

import java.sql.Connection;
import java.sql.PreparedStatement;
import java.util.Collections;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.stream.Collectors;
import java.util.stream.Stream;

public class AttendanceUserAdapter extends AbstractUserAdapterFederatedStorage {
    private static final Logger logger = Logger.getLogger(AttendanceUserAdapter.class);

    private final AttendanceUser user;
    private final AttendanceUserStorageProvider provider;

    public AttendanceUserAdapter(KeycloakSession session, RealmModel realm, ComponentModel model,
                                 AttendanceUser user, AttendanceUserStorageProvider provider) {
        super(session, realm, model);
        this.storageId = new StorageId(storageProviderModel.getId(), String.valueOf(user.getId()));
        this.user = user;
        this.provider = provider;
    }

    @Override
    public String getUsername() {
        return user.getEmail() != null ? user.getEmail() : user.getUsername();
    }

    @Override
    public void setUsername(String username) {
        user.setUsername(username);
        updateUserColumn("username", username);
    }

    @Override
    public String getEmail() {
        return user.getEmail();
    }

    @Override
    public void setEmail(String email) {
        user.setEmail(email);
        updateUserColumn("email", email);
    }

    @Override
    public String getFirstName() {
        return user.getFirstName();
    }

    @Override
    public void setFirstName(String firstName) {
        user.setFirstName(firstName);
        updateUserColumn("first_name", firstName);
        updateFullName();
    }

    @Override
    public String getLastName() {
        return user.getLastName();
    }

    @Override
    public void setLastName(String lastName) {
        user.setLastName(lastName);
        updateUserColumn("last_name", lastName);
        updateFullName();
    }

    @Override
    public boolean isEnabled() {
        return user.getActive() == 1;
    }

    @Override
    public void setEnabled(boolean enabled) {
        user.setActive(enabled ? 1 : 0);
        try (Connection conn = provider.getConnection();
             PreparedStatement ps = conn.prepareStatement("UPDATE app_users SET active = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?")) {
            ps.setInt(1, enabled ? 1 : 0);
            ps.setInt(2, user.getId());
            ps.executeUpdate();
        } catch (Exception e) {
            logger.error("Failed to update active in app_users", e);
        }
    }

    @Override
    public boolean isEmailVerified() {
        return true;
    }

    @Override
    public void setEmailVerified(boolean verified) {
        // Attendance users have pre-verified corporate emails
    }

    // --- Attributes Delegation directly to app_users ---

    @Override
    public String getFirstAttribute(String name) {
        if (name == null) return null;
        if (UserModel.FIRST_NAME.equalsIgnoreCase(name)) {
            return getFirstName();
        }
        if (UserModel.LAST_NAME.equalsIgnoreCase(name)) {
            return getLastName();
        }
        if (UserModel.EMAIL.equalsIgnoreCase(name)) {
            return getEmail();
        }
        if (UserModel.USERNAME.equalsIgnoreCase(name)) {
            return getUsername();
        }
        if ("phone".equalsIgnoreCase(name) && user.getPhone() != null) {
            return user.getPhone();
        }
        if ("role_title".equalsIgnoreCase(name) && user.getRoleTitle() != null) {
            return user.getRoleTitle();
        }
        return super.getFirstAttribute(name);
    }

    @Override
    public Stream<String> getAttributeStream(String name) {
        String val = getFirstAttribute(name);
        if (val != null) {
            return Stream.of(val);
        }
        return super.getAttributeStream(name);
    }

    @Override
    public Map<String, List<String>> getAttributes() {
        Map<String, List<String>> attrs = new HashMap<>(super.getAttributes());
        if (getFirstName() != null) {
            attrs.put(UserModel.FIRST_NAME, Collections.singletonList(getFirstName()));
        }
        if (getLastName() != null) {
            attrs.put(UserModel.LAST_NAME, Collections.singletonList(getLastName()));
        }
        if (getEmail() != null) {
            attrs.put(UserModel.EMAIL, Collections.singletonList(getEmail()));
        }
        if (getUsername() != null) {
            attrs.put(UserModel.USERNAME, Collections.singletonList(getUsername()));
        }
        if (user.getPhone() != null) {
            attrs.put("phone", Collections.singletonList(user.getPhone()));
        }
        if (user.getRoleTitle() != null) {
            attrs.put("role_title", Collections.singletonList(user.getRoleTitle()));
        }
        return Collections.unmodifiableMap(attrs);
    }

    @Override
    public void setSingleAttribute(String name, String value) {
        if (UserModel.FIRST_NAME.equalsIgnoreCase(name)) {
            setFirstName(value);
        } else if (UserModel.LAST_NAME.equalsIgnoreCase(name)) {
            setLastName(value);
        } else if (UserModel.EMAIL.equalsIgnoreCase(name)) {
            setEmail(value);
        } else if ("phone".equalsIgnoreCase(name)) {
            user.setPhone(value);
            updateUserColumn("phone", value);
        } else if ("role_title".equalsIgnoreCase(name)) {
            user.setRoleTitle(value);
            updateUserColumn("role_title", value);
        }
        // Do NOT call super.setSingleAttribute to avoid saving into fed_user_attribute
    }

    @Override
    public void setAttribute(String name, List<String> values) {
        String val = (values != null && !values.isEmpty()) ? values.get(0) : null;
        setSingleAttribute(name, val);
    }

    @Override
    public void removeAttribute(String name) {
        if (UserModel.FIRST_NAME.equalsIgnoreCase(name)) {
            setFirstName("");
        } else if (UserModel.LAST_NAME.equalsIgnoreCase(name)) {
            setLastName("");
        } else if ("phone".equalsIgnoreCase(name)) {
            user.setPhone(null);
            updateUserColumn("phone", null);
        } else if ("role_title".equalsIgnoreCase(name)) {
            user.setRoleTitle(null);
            updateUserColumn("role_title", null);
        }
        // Do NOT call super.removeAttribute
    }

    // --- Dynamic Realm Role Mappings ---

    @Override
    public Stream<RoleModel> getRoleMappingsStream() {
        Set<RoleModel> roles = super.getRoleMappingsStream().collect(Collectors.toSet());
        String sysRole = user.getSystemRole() != null ? user.getSystemRole().trim().toLowerCase() : "member";
        RoleModel memberRole = realm.getRole("member");
        if (memberRole != null) {
            roles.add(memberRole);
        }
        if ("admin".equalsIgnoreCase(sysRole)) {
            RoleModel adminRole = realm.getRole("admin");
            if (adminRole != null) roles.add(adminRole);
        } else if ("project-manager".equalsIgnoreCase(sysRole)) {
            RoleModel pmRole = realm.getRole("project-manager");
            if (pmRole != null) roles.add(pmRole);
        }
        return roles.stream();
    }

    @Override
    public Stream<RoleModel> getRealmRoleMappingsStream() {
        return getRoleMappingsStream().filter(r -> !r.isClientRole());
    }

    @Override
    public boolean hasRole(RoleModel role) {
        String roleName = role.getName();
        String sysRole = user.getSystemRole() != null ? user.getSystemRole().trim().toLowerCase() : "member";
        if ("admin".equalsIgnoreCase(roleName) && "admin".equalsIgnoreCase(sysRole)) {
            return true;
        }
        if ("project-manager".equalsIgnoreCase(roleName) && "project-manager".equalsIgnoreCase(sysRole)) {
            return true;
        }
        if ("member".equalsIgnoreCase(roleName)) {
            return true;
        }
        return super.hasRole(role);
    }

    @Override
    public void grantRole(RoleModel role) {
        super.grantRole(role);
        String roleName = role.getName();
        if ("admin".equalsIgnoreCase(roleName)) {
            user.setSystemRole("admin");
            updateUserColumn("system_role", "admin");
        } else if ("project-manager".equalsIgnoreCase(roleName)) {
            user.setSystemRole("project-manager");
            updateUserColumn("system_role", "project-manager");
        } else if ("member".equalsIgnoreCase(roleName) && !"admin".equalsIgnoreCase(user.getSystemRole()) && !"project-manager".equalsIgnoreCase(user.getSystemRole())) {
            user.setSystemRole("member");
            updateUserColumn("system_role", "member");
        }
    }

    @Override
    public void deleteRoleMapping(RoleModel role) {
        super.deleteRoleMapping(role);
        String roleName = role.getName();
        if ("admin".equalsIgnoreCase(roleName) || "project-manager".equalsIgnoreCase(roleName)) {
            user.setSystemRole("member");
            updateUserColumn("system_role", "member");
        }
    }

    // --- Required Actions (First Login Password Reset & TOTP) ---

    @Override
    public Stream<String> getRequiredActionsStream() {
        Set<String> actions = super.getRequiredActionsStream().collect(Collectors.toSet());
        if (user.isMustChangePassword()) {
            actions.add(UserModel.RequiredAction.UPDATE_PASSWORD.name());
        }
        if (!user.isTotpEnabled()) {
            actions.add(UserModel.RequiredAction.CONFIGURE_TOTP.name());
        }
        return actions.stream();
    }

    @Override
    public void removeRequiredAction(String action) {
        if (UserModel.RequiredAction.UPDATE_PASSWORD.name().equals(action)) {
            user.setMustChangePassword(false);
            updateUserFlag("must_change_password", false);
        } else if (UserModel.RequiredAction.CONFIGURE_TOTP.name().equals(action)) {
            user.setTotpEnabled(true);
            updateUserFlag("totp_enabled", true);
        }
        super.removeRequiredAction(action);
    }

    @Override
    public void removeRequiredAction(UserModel.RequiredAction action) {
        removeRequiredAction(action.name());
    }

    private void updateUserFlag(String column, boolean val) {
        try (Connection conn = provider.getConnection();
             PreparedStatement ps = conn.prepareStatement("UPDATE app_users SET " + column + " = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?")) {
            ps.setBoolean(1, val);
            ps.setInt(2, user.getId());
            ps.executeUpdate();
        } catch (Exception e) {
            logger.error("Failed to update flag " + column + " in app_users", e);
        }
    }

    private void updateUserColumn(String column, String value) {
        try (Connection conn = provider.getConnection();
             PreparedStatement ps = conn.prepareStatement("UPDATE app_users SET " + column + " = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?")) {
            ps.setString(1, value);
            ps.setInt(2, user.getId());
            ps.executeUpdate();
        } catch (Exception e) {
            logger.error("Failed to update column " + column + " in app_users", e);
        }
    }

    private void updateFullName() {
        String fn = user.getFirstName() != null ? user.getFirstName() : "";
        String ln = user.getLastName() != null ? user.getLastName() : "";
        String full = (fn + " " + ln).trim();
        updateUserColumn("name", full);
    }
}
