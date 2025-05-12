# account/views.py

import jwt
import requests
from datetime import datetime, timedelta
from django.conf import settings
from django.shortcuts import render, redirect
from django.contrib import messages
from django.contrib.auth.hashers import make_password, check_password
from django.urls import reverse
from django.utils.crypto import get_random_string
from .models import Account

########################################
# Helper: Generate JWT
########################################
def generate_jwt_token(account):
    """
    Generates a JWT token for the given account.
    Expires in 1 day.
    """
    payload = {
        'user_id': account.user_id,
        'exp': datetime.utcnow() + timedelta(days=1),
        'iat': datetime.utcnow(),
    }
    token = jwt.encode(payload, settings.SECRET_KEY, algorithm='HS256')
    return token

########################################
# Register View (POST /account/register/)
########################################
def register_view(request):
    if request.method == 'POST':
        username = request.POST.get('username')
        email = request.POST.get('email')
        password = request.POST.get('password')

        # Basic checks
        if not username or not email or not password:
            messages.error(request, "All fields are required.")
            return redirect('/register.html')

        # Check duplicates
        if Account.objects.filter(email=email).exists():
            messages.error(request, "Account creation failed: Email already used.")
            return redirect('/register.html')
        if Account.objects.filter(username=username).exists():
            messages.error(request, "Account creation failed: Username already used.")
            return redirect('/register.html')

        # Create user
        hashed_pw = make_password(password)
        account = Account(username=username, email=email, password=hashed_pw)
        account.save()

        messages.success(request, "Account created successfully! Please log in.")
        return redirect('/login.html')
    else:
        # If someone tries GET /account/register/ => redirect or show error
        return redirect('/register.html')

########################################
# Login View (POST /account/login/)
########################################
def login_view(request):
    if request.method == 'POST':
        email = request.POST.get('email')
        password = request.POST.get('password')

        if not email or not password:
            messages.error(request, "Please provide email and password.")
            return redirect('/login.html')

        try:
            account = Account.objects.get(email=email)
        except Account.DoesNotExist:
            messages.error(request, "Invalid credentials (user not found).")
            return redirect('/login.html')

        if check_password(password, account.password):
            token = generate_jwt_token(account)
            request.session['jwt_token'] = token
            # messages.success(request, "Login successful!")
            return redirect('/dashboard.html')
        else:
            messages.error(request, "Invalid credentials (wrong password).")
            return redirect('/login.html')
    else:
        return redirect('/login.html')

########################################
# Google OAuth Start (GET /account/login/google/)
########################################
def google_login_start(request):
    # Real Google OAuth flow
    state = get_random_string(16)
    request.session['google_oauth_state'] = state

    google_auth_url = "https://accounts.google.com/o/oauth2/v2/auth"
    scope = "openid email profile"
    redirect_uri = request.build_absolute_uri(reverse('account:google_callback'))

    from urllib.parse import urlencode
    params = {
        'client_id': settings.GOOGLE_CLIENT_ID,
        'response_type': 'code',
        'redirect_uri': redirect_uri,
        'scope': scope,
        'state': state,
        'access_type': 'offline',
        'prompt': 'select_account',
    }
    url = google_auth_url + "?" + urlencode(params)
    return redirect(url)

########################################
# Google OAuth Callback (/account/login/google/callback/)
########################################
def google_login_callback(request):
    code = request.GET.get('code')
    state = request.GET.get('state')

    if not code or not state:
        messages.error(request, "Invalid response from Google.")
        return redirect('/login.html')

    if state != request.session.get('google_oauth_state'):
        messages.error(request, "State mismatch for Google OAuth.")
        return redirect('/login.html')

    # Exchange code for access token
    token_url = "https://oauth2.googleapis.com/token"
    redirect_uri = request.build_absolute_uri(reverse('account:google_callback'))

    data = {
        'code': code,
        'client_id': settings.GOOGLE_CLIENT_ID,
        'client_secret': settings.GOOGLE_CLIENT_SECRET,
        'redirect_uri': redirect_uri,
        'grant_type': 'authorization_code',
    }

    r = requests.post(token_url, data=data)
    if r.status_code != 200:
        messages.error(request, "Failed to exchange code for token.")
        return redirect('/login.html')

    token_data = r.json()
    access_token = token_data.get('access_token')
    if not access_token:
        messages.error(request, "No access token found in token response.")
        return redirect('/login.html')

    # Fetch user info
    userinfo_url = "https://www.googleapis.com/oauth2/v3/userinfo"
    headers = {'Authorization': f"Bearer {access_token}"}
    r2 = requests.get(userinfo_url, headers=headers)
    if r2.status_code != 200:
        messages.error(request, "Failed to fetch user info from Google.")
        return redirect('/login.html')

    userinfo = r2.json()
    google_email = userinfo.get('email')
    google_name = userinfo.get('name') or userinfo.get('given_name') or "GoogleUser"

    if not google_email:
        messages.error(request, "Google did not return an email.")
        return redirect('/login.html')

    # Create or get user
    account, created = Account.objects.get_or_create(
        email=google_email,
        defaults={
            'username': google_name,
            'password': make_password("google_oauth_random"),
        }
    )

    # JWT
    token = generate_jwt_token(account)
    request.session['jwt_token'] = token
    messages.success(request, "Logged in via Google!")
    return redirect('/dashboard.html')

########################################
# GitHub OAuth Start (GET /account/login/github/)
########################################
def github_login_start(request):
    state = get_random_string(16)
    request.session['github_oauth_state'] = state

    github_auth_url = "https://github.com/login/oauth/authorize"
    redirect_uri = request.build_absolute_uri(reverse('account:github_callback'))

    from urllib.parse import urlencode
    params = {
        'client_id': settings.GITHUB_CLIENT_ID,
        'redirect_uri': redirect_uri,
        'scope': 'user:email',
        'state': state,
        'allow_signup': 'true',
    }
    url = github_auth_url + "?" + urlencode(params)
    return redirect(url)

########################################
# GitHub OAuth Callback (/account/login/github/callback/)
########################################
def github_login_callback(request):
    code = request.GET.get('code')
    state = request.GET.get('state')

    if not code or not state:
        messages.error(request, "Invalid response from GitHub.")
        return redirect('/login.html')

    if state != request.session.get('github_oauth_state'):
        messages.error(request, "State mismatch for GitHub OAuth.")
        return redirect('/login.html')

    token_url = "https://github.com/login/oauth/access_token"
    redirect_uri = request.build_absolute_uri(reverse('account:github_callback'))

    data = {
        'client_id': settings.GITHUB_CLIENT_ID,
        'client_secret': settings.GITHUB_CLIENT_SECRET,
        'code': code,
        'redirect_uri': redirect_uri,
        'state': state,
    }

    headers = {'Accept': 'application/json'}
    r = requests.post(token_url, data=data, headers=headers)
    if r.status_code != 200:
        messages.error(request, "Failed to exchange code for token (GitHub).")
        return redirect('/login.html')

    token_data = r.json()
    access_token = token_data.get('access_token')
    if not access_token:
        messages.error(request, "No access token found in GitHub response.")
        return redirect('/login.html')

    # Fetch user info from GitHub
    userinfo_url = "https://api.github.com/user"
    headers = {'Authorization': f"token {access_token}"}
    r2 = requests.get(userinfo_url, headers=headers)
    if r2.status_code != 200:
        messages.error(request, "Failed to fetch user info from GitHub.")
        return redirect('/login.html')

    userinfo = r2.json()
    github_email = userinfo.get('email')
    github_username = userinfo.get('login') or "GitHubUser"

    # If user’s email is null, fetch from /user/emails
    if not github_email:
        r3 = requests.get("https://api.github.com/user/emails", headers=headers)
        if r3.status_code == 200:
            emails_info = r3.json()
            # find primary email
            for e in emails_info:
                if e.get('primary'):
                    github_email = e.get('email')
                    break

    if not github_email:
        messages.error(request, "Could not find an email from GitHub.")
        return redirect('/login.html')

    # Create or get user
    account, created = Account.objects.get_or_create(
        email=github_email,
        defaults={
            'username': github_username,
            'password': make_password("github_oauth_random"),
        }
    )

    token = generate_jwt_token(account)
    request.session['jwt_token'] = token
    messages.success(request, "Logged in via GitHub!")
    return redirect('/dashboard.html')


########################################
# Logout View
########################################
def logout_view(request):
    """
    Clears the JWT from the session, logging the user out.
    Redirects back to the login page.
    """
    # Remove token from session if present
    request.session.pop('jwt_token', None)
    # messages.success(request, "You have been logged out.")
    # Redirect to your login page (static .html)
    return redirect('/')