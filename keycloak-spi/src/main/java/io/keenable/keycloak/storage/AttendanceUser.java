package io.keenable.keycloak.storage;

public class AttendanceUser {
    private int id;
    private String username;
    private String email;
    private String firstName;
    private String lastName;
    private String phone;
    private String roleTitle;
    private String systemRole;
    private boolean mustChangePassword;
    private boolean totpEnabled;
    private int active;

    public AttendanceUser(int id, String username, String email, String firstName, String lastName,
                          String phone, String roleTitle, String systemRole,
                          boolean mustChangePassword, boolean totpEnabled, int active) {
        this.id = id;
        this.username = username;
        this.email = email;
        this.firstName = firstName;
        this.lastName = lastName;
        this.phone = phone;
        this.roleTitle = roleTitle;
        this.systemRole = systemRole != null ? systemRole : "member";
        this.mustChangePassword = mustChangePassword;
        this.totpEnabled = totpEnabled;
        this.active = active;
    }

    public int getId() { return id; }
    public String getUsername() { return username; }
    public void setUsername(String username) { this.username = username; }
    public String getEmail() { return email; }
    public void setEmail(String email) { this.email = email; }
    public String getFirstName() { return firstName; }
    public void setFirstName(String firstName) { this.firstName = firstName; }
    public String getLastName() { return lastName; }
    public void setLastName(String lastName) { this.lastName = lastName; }
    public String getPhone() { return phone; }
    public void setPhone(String phone) { this.phone = phone; }
    public String getRoleTitle() { return roleTitle; }
    public void setRoleTitle(String roleTitle) { this.roleTitle = roleTitle; }
    public String getSystemRole() { return systemRole; }
    public void setSystemRole(String systemRole) { this.systemRole = systemRole; }
    public boolean isMustChangePassword() { return mustChangePassword; }
    public void setMustChangePassword(boolean mustChangePassword) { this.mustChangePassword = mustChangePassword; }
    public boolean isTotpEnabled() { return totpEnabled; }
    public void setTotpEnabled(boolean totpEnabled) { this.totpEnabled = totpEnabled; }
    public int getActive() { return active; }
    public void setActive(int active) { this.active = active; }
}
