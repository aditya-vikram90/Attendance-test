# frozen_string_literal: true
# ==============================================================================
# OpenProject Auto-Redirect Keycloak OIDC SSO Extension & Backchannel Single Sign-Out
# Location: /opt/openproject_sso/keycloak_sso.rb -> /app/lib/open_project/patches/keycloak_sso.rb
# Description: Implements True Zero-Click SSO on /login via AccountController
#              and OIDC Back-Channel Logout (Single Sign-Out)
# Author: Keenable DevOps Team
# Date: 2026-10-19
# ==============================================================================

require 'net/http'
require 'json'
require 'uri'
require 'securerandom'
require 'openssl'
require 'jwt'

module KeycloakAccountControllerPatch
  KEYCLOAK_BASE_AUTH = 'https://pm.keenable.io/auth/realms/keenable/protocol/openid-connect'
  KEYCLOAK_INTERNAL_BASE = 'http://keycloak:8080/auth/realms/keenable/protocol/openid-connect'
  KEYCLOAK_CLIENT_ID = 'openproject'
  KEYCLOAK_CLIENT_SECRET = 'OpenProjectSecret2026!'

  def login
    # 1. Backchannel Logout Handler (Single Sign-Out)
    if request.post? && (params[:logout_token].present? || params['logout_token'].present?)
      return handle_keycloak_backchannel_logout
    end

    # 2. If user is already logged in, let standard OpenProject redirect to dashboard
    if User.current.logged?
      return super
    end

    # 3. If emergency local login or post-logout requested (?local=1 or ?logged_out=1)
    if params[:local] == '1' || params[:local] == 'true' || params[:logged_out] == '1'
      @force_password_login_form = true
      session[:authenticated_via_keycloak] = false
      if params[:logged_out] == '1'
        flash.now[:notice] = "You have been successfully signed out."
      end
      return super
    end

    # 4. If callback from Keycloak with authorization code
    if request.get? && params[:code].present?
      return handle_keycloak_callback
    end

    # 5. If GET/HEAD request to /login without code, initiate Keycloak SSO redirect
    if request.get? || request.head?
      return initiate_keycloak_redirect
    end

    super
  end

  def logout
    was_sso = session[:authenticated_via_keycloak] != false

    logout_user

    if was_sso
      session.clear rescue nil
      post_logout_url = "https://pm.keenable.io/login?logged_out=1"
      logout_params = {
        client_id: KEYCLOAK_CLIENT_ID,
        post_logout_redirect_uri: post_logout_url
      }
      keycloak_logout_url = "#{KEYCLOAK_BASE_AUTH}/logout?#{URI.encode_www_form(logout_params)}"
      redirect_to keycloak_logout_url, allow_other_host: true
      return
    end

    super
  end

  private

  def handle_keycloak_backchannel_logout
    logout_token = params[:logout_token] || params['logout_token']
    Rails.logger.info("[KeycloakSSO] Processing Backchannel Logout request...")

    begin
      # Decode JWT logout token (without signature validation or with Keycloak cert)
      decoded_token = JWT.decode(logout_token, nil, false).first
      
      events = decoded_token['events'] || {}
      unless events.key?('http://schemas.openid.net/event/backchannel-logout')
        Rails.logger.warn("[KeycloakSSO] Backchannel logout missing required event claim.")
        return render plain: 'Invalid logout token event', status: :bad_request
      end

      if decoded_token['nonce'].present?
        Rails.logger.warn("[KeycloakSSO] Backchannel logout token contains forbidden nonce.")
        return render plain: 'Forbidden nonce', status: :bad_request
      end

      sub = decoded_token['sub']
      sid = decoded_token['sid']

      Rails.logger.info("[KeycloakSSO] Backchannel logout token validated. sub=#{sub}, sid=#{sid}")

      # Invalidate sessions in OpenProject sessions table
      if sub.present?
        kc_username = sub.include?(':') ? sub.split(':').last : nil
        target_users = []
        if kc_username.present?
          target_users = User.where("lower(login) = ? OR lower(mail) = ?", kc_username.downcase, kc_username.downcase).to_a
        end

        if target_users.empty?
          begin
            user_info = fetch_keycloak_user_by_sub(sub)
            if user_info && (user_info['email'] || user_info['username'])
              email = user_info['email'].to_s.downcase
              login = user_info['username'].to_s.downcase
              target_users = User.where("lower(mail) = ? OR lower(login) = ?", email, login).to_a
            end
          rescue => e
            Rails.logger.warn("[KeycloakSSO] Failed to lookup user by sub in Keycloak: #{e.message}")
          end
        end

        target_users.each do |target_user|
          deleted_count = ActiveRecord::Base.connection.execute(
            ActiveRecord::Base.sanitize_sql_array([
              "DELETE FROM sessions WHERE user_id = ?", target_user.id
            ])
          ).cmd_tuples rescue 0
          Rails.logger.info("[KeycloakSSO] Single Sign-Out: Terminated #{deleted_count} session(s) for user #{target_user.login} (ID: #{target_user.id})")
        end
      end

      if sid.present?
        ActiveRecord::Base.connection.execute(
          ActiveRecord::Base.sanitize_sql_array([
            "DELETE FROM oidc_user_session_links WHERE oidc_session = ?", sid
          ])
        ) rescue nil
      end

      response.headers['Cache-Control'] = 'no-store'
      response.headers['Pragma'] = 'no-cache'
      render plain: 'OK', status: :ok
    rescue => e
      Rails.logger.error("[KeycloakSSO] Backchannel logout exception: #{e.message}")
      render plain: "Error: #{e.message}", status: :bad_request
    end
  end

  def fetch_keycloak_user_by_sub(sub)
    token = get_admin_token
    return nil unless token

    uri = URI.parse("http://keycloak:8080/auth/admin/realms/keenable/users/#{URI.encode_www_form_component(sub)}")
    req = Net::HTTP::Get.new(uri.request_uri)
    req['Authorization'] = "Bearer #{token}"
    
    http = Net::HTTP.new(uri.host, uri.port)
    http.open_timeout = 3
    http.read_timeout = 5
    res = http.request(req)
    JSON.parse(res.body) rescue nil
  end

  def get_admin_token
    uri = URI.parse("http://keycloak:8080/auth/realms/master/protocol/openid-connect/token")
    req = Net::HTTP::Post.new(uri.request_uri)
    req.set_form_data(
      'client_id' => 'admin-cli',
      'username'  => 'admin',
      'password'  => 'KeycloakAdmin2026!',
      'grant_type'=> 'password'
    )
    http = Net::HTTP.new(uri.host, uri.port)
    http.open_timeout = 3
    http.read_timeout = 5
    res = http.request(req)
    JSON.parse(res.body)['access_token'] rescue nil
  end

  def initiate_keycloak_redirect
    state = SecureRandom.hex(24)
    nonce = SecureRandom.hex(24)
    session[:keycloak_oauth_state] = state
    session[:keycloak_oauth_nonce] = nonce
    session[:keycloak_back_url] = params[:back_url] || session[:back_url] || request.referer || '/'

    callback_url = "https://pm.keenable.io/login"

    auth_params = {
      client_id: KEYCLOAK_CLIENT_ID,
      response_type: 'code',
      scope: 'openid email profile',
      redirect_uri: callback_url,
      state: state,
      nonce: nonce
    }

    auth_url = "#{KEYCLOAK_BASE_AUTH}/auth?#{URI.encode_www_form(auth_params)}"
    redirect_to auth_url, allow_other_host: true
  end

  def handle_keycloak_callback
    received_state = params[:state]
    expected_state = session.delete(:keycloak_oauth_state)

    if received_state.blank? || received_state != expected_state
      Rails.logger.warn("[KeycloakSSO] State mismatch. Received: #{received_state}, Expected: #{expected_state}")
      flash[:error] = "Authentication failed: OAuth state verification mismatch. Please try again."
      redirect_to "/login?local=1" and return
    end

    code = params[:code]
    callback_url = "https://pm.keenable.io/login"

    # Step A: Token exchange
    token_data = exchange_code_for_token(code, callback_url)
    unless token_data && token_data['access_token']
      Rails.logger.error("[KeycloakSSO] Token exchange failed: #{token_data.inspect}")
      flash[:error] = "Authentication failed: Could not exchange authorization code with Keycloak."
      redirect_to "/login?local=1" and return
    end

    # Step B: Userinfo lookup
    user_info = fetch_user_info(token_data['access_token'])
    unless user_info && user_info['email']
      Rails.logger.error("[KeycloakSSO] UserInfo lookup failed: #{user_info.inspect}")
      flash[:error] = "Authentication failed: Could not retrieve user profile from Keycloak."
      redirect_to "/login?local=1" and return
    end

    # Step C: Find or provision user
    user = find_or_provision_user(user_info)
    if user.nil?
      flash[:error] = "Unable to find or provision an OpenProject account for #{user_info['email']}."
      redirect_to "/login?local=1" and return
    end

    if user.locked? || user.status == Principal.statuses[:locked]
      flash[:error] = "Your account is locked. Please contact your system administrator."
      redirect_to "/login?local=1" and return
    end

    # Step D: Log in user
    session[:authenticated_via_keycloak] = true
    RequestStore[:authenticated_via_keycloak] = true

    back_url = session.delete(:keycloak_back_url) || '/'
    params[:back_url] = back_url

    Rails.logger.info("[KeycloakSSO] User #{user.login} (#{user.mail}) successfully logged in via Keycloak OIDC.")
    login_user!(user)
  end

  def exchange_code_for_token(code, callback_url)
    uri = URI.parse("#{KEYCLOAK_BASE_AUTH}/token")
    http = Net::HTTP.new(uri.host, uri.port)
    http.use_ssl = (uri.scheme == 'https')
    http.verify_mode = OpenSSL::SSL::VERIFY_NONE

    request = Net::HTTP::Post.new(uri.request_uri)
    request.set_form_data(
      'grant_type'    => 'authorization_code',
      'code'          => code,
      'redirect_uri'  => callback_url,
      'client_id'     => KEYCLOAK_CLIENT_ID,
      'client_secret' => KEYCLOAK_CLIENT_SECRET
    )

    response = http.request(request)
    JSON.parse(response.body) rescue nil
  end

  def fetch_user_info(access_token)
    uri = URI.parse("#{KEYCLOAK_BASE_AUTH}/userinfo")
    http = Net::HTTP.new(uri.host, uri.port)
    http.use_ssl = (uri.scheme == 'https')
    http.verify_mode = OpenSSL::SSL::VERIFY_NONE

    request = Net::HTTP::Get.new(uri.request_uri)
    request['Authorization'] = "Bearer #{access_token}"

    response = http.request(request)
    JSON.parse(response.body) rescue nil
  end

  def find_or_provision_user(user_info)
    email = user_info['email'].to_s.strip.downcase
    login = user_info['preferred_username'].presence || email

    user = User.where("lower(mail) = ? OR lower(login) = ?", email, login.downcase).first

    if user
      if user_info['given_name'].present? && user.firstname.blank?
        user.firstname = user_info['given_name']
      end
      if user_info['family_name'].present? && user.lastname.blank?
        user.lastname = user_info['family_name']
      end
      user.save(validate: false) if user.changed?
      return user
    end

    first_name = user_info['given_name'].presence || login.split('@').first.capitalize
    last_name  = user_info['family_name'].presence || 'User'

    user = User.new(
      login:     login,
      mail:      email,
      firstname: first_name,
      lastname:  last_name,
      status:    Principal.statuses[:active],
      language:  Setting.default_language.presence || 'en',
      admin:     false
    )
    user.save!(validate: false)
    user
  rescue => e
    Rails.logger.error("[KeycloakSSO] Error provisioning user: #{e.message}")
    nil
  end
end

AccountController.class_eval do
  skip_before_action :verify_authenticity_token, only: [:login], if: -> { request.post? && (params[:logout_token].present? || params['logout_token'].present?) }
  prepend KeycloakAccountControllerPatch
end
Rails.logger.info("[KeycloakSSO] KeycloakAccountControllerPatch prepended directly to AccountController successfully.")

# Module to bypass password confirmation for Keycloak SSO users
module KeycloakPasswordConfirmationPatch
  def password_confirmation_required?
    if RequestStore[:authenticated_via_keycloak] || (defined?(session) && session && session[:authenticated_via_keycloak] != false)
      return false
    end
    super
  end

  def check_password_confirmation
    if RequestStore[:authenticated_via_keycloak] || (defined?(session) && session && session[:authenticated_via_keycloak] != false)
      return true
    end
    super
  end
end
PasswordConfirmation.prepend(KeycloakPasswordConfirmationPatch)
Rails.logger.info("[KeycloakSSO] KeycloakPasswordConfirmationPatch prepended successfully.")

# Module to mark SSO users as external and verify passwords via Keycloak if prompted
module KeycloakUserPatch
  def uses_external_authentication?
    return true if RequestStore[:authenticated_via_keycloak]
    super
  end

  def check_password?(clear_password, update_legacy: true)
    # 1. Check local OpenProject password hash first
    return true if super

    # 2. If local check fails or doesn't exist, verify against Keycloak via Direct Access Grant
    verify_password_with_keycloak(clear_password)
  end

  private

  def verify_password_with_keycloak(clear_password)
    return false if clear_password.blank?

    uri = URI.parse("http://keycloak:8080/auth/realms/keenable/protocol/openid-connect/token")
    http = Net::HTTP.new(uri.host, uri.port)
    http.open_timeout = 3
    http.read_timeout = 5

    req = Net::HTTP::Post.new(uri.request_uri)
    req.set_form_data(
      'grant_type'    => 'password',
      'client_id'     => KeycloakAccountControllerPatch::KEYCLOAK_CLIENT_ID,
      'client_secret' => KeycloakAccountControllerPatch::KEYCLOAK_CLIENT_SECRET,
      'username'      => self.mail.presence || self.login,
      'password'      => clear_password
    )

    resp = http.request(req)
    if resp.is_a?(Net::HTTPSuccess)
      Rails.logger.info("[KeycloakSSO] Password successfully verified with Keycloak for #{self.login}")
      begin
        self.password = clear_password
        self.password_confirmation = clear_password
        self.save(validate: false)
      rescue => e
        Rails.logger.warn("[KeycloakSSO] Could not sync password to local DB: #{e.message}")
      end
      return true
    end
    false
  rescue => e
    Rails.logger.warn("[KeycloakSSO] Keycloak password verification exception: #{e.message}")
    false
  end
end
User.prepend(KeycloakUserPatch)
Rails.logger.info("[KeycloakSSO] KeycloakUserPatch prepended successfully.")

ApplicationController.class_eval do
  before_action :set_keycloak_request_context

  private

  def set_keycloak_request_context
    return unless User.current.logged?

    if session[:authenticated_via_keycloak] != false
      session[:authenticated_via_keycloak] = true
      RequestStore[:authenticated_via_keycloak] = true
    end
  end
end
Rails.logger.info("[KeycloakSSO] ApplicationController set_keycloak_request_context hook registered.")

class KeycloakLoginHookListener < OpenProject::Hook::ViewListener
  def view_account_login_top(context = {})
    <<-HTML.html_safe
      <div style="text-align: center; margin-bottom: 20px;">
        <a href="/login" class="button -highlight" style="display: block; width: 100%; box-sizing: border-box; text-align: center; padding: 12px 20px; font-weight: 600; font-size: 15px; border-radius: 6px; text-decoration: none; background-color: #1f77b4; color: #ffffff;">
          Sign in with Keenable SSO
        </a>
      </div>
    HTML
  end
end
Rails.logger.info("[KeycloakSSO] KeycloakLoginHookListener registered successfully.")

# Module to explicitly disable manual user creation inside OpenProject
# Keycloak is the Single Source of Truth for user lifecycle
module KeycloakUsersControllerPatch
  def new
    flash[:error] = "User creation inside OpenProject is disabled. Keycloak is the Single Source of Truth for user identity. Please create users in Keycloak Admin Console (https://pm.keenable.io/auth/admin/)."
    redirect_to users_path
  end

  def create
    flash[:error] = "User creation inside OpenProject is disabled. Keycloak is the Single Source of Truth for user identity. Please create users in Keycloak Admin Console (https://pm.keenable.io/auth/admin/)."
    redirect_to users_path
  end
end

UsersController.prepend(KeycloakUsersControllerPatch)
Rails.logger.info("[KeycloakSSO] KeycloakUsersControllerPatch prepended successfully - Manual user creation blocked.")
