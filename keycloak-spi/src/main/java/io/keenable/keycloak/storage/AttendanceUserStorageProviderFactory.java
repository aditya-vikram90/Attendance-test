package io.keenable.keycloak.storage;

import org.keycloak.component.ComponentModel;
import org.keycloak.models.KeycloakSession;
import org.keycloak.provider.ProviderConfigProperty;
import org.keycloak.provider.ProviderConfigurationBuilder;
import org.keycloak.storage.UserStorageProviderFactory;

import java.util.List;

public class AttendanceUserStorageProviderFactory implements UserStorageProviderFactory<AttendanceUserStorageProvider> {
    public static final String PROVIDER_NAME = "attendance-user-storage";

    @Override
    public String getId() {
        return PROVIDER_NAME;
    }

    @Override
    public AttendanceUserStorageProvider create(KeycloakSession session, ComponentModel model) {
        return new AttendanceUserStorageProvider(session, model);
    }

    @Override
    public String getHelpText() {
        return "Federates users directly from central users PostgreSQL database";
    }

    @Override
    public List<ProviderConfigProperty> getConfigProperties() {
        return ProviderConfigurationBuilder.create()
                .property("jdbcUrl", "JDBC URL", "PostgreSQL JDBC URL to users database",
                        ProviderConfigProperty.STRING_TYPE, "jdbc:postgresql://openproject-db:5432/users", null)
                .property("dbUser", "Database User", "Database username",
                        ProviderConfigProperty.STRING_TYPE, "users_admin", null)
                .property("dbPassword", "Database Password", "Database password",
                        ProviderConfigProperty.PASSWORD, "UsersAdmin2026!", null)
                .build();
    }
}
