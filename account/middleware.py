# account/middleware.py
import jwt
from django.conf import settings
from django.shortcuts import redirect
from django.contrib import messages

class AuthRequiredMiddleware:
    """
    Middleware to ensure the user is logged in for protected pages.
    Only the URLs explicitly allowed in the whitelist are accessible without login.
    """
    def __init__(self, get_response):
        self.get_response = get_response
        # Whitelist URLs that do not require login, both with and without trailing slash
        self.whitelist = [
            '/',                    # home
            '/login.html',
            '/register.html',
            # help & faq (with and without trailing slash)
            '/account/help/',
            '/application/faq',
            # allow anything under /account/ (e.g. oauth callbacks, logout)
            '/account/',
        ]

    def __call__(self, request):
        path = request.path

        # if the request path is in whitelist (exact match) or starts with one:
        if not any(path == p or path.startswith(p) for p in self.whitelist):
            token = request.session.get('jwt_token')
            try:
                # will raise if missing/invalid/expired
                jwt.decode(token, settings.SECRET_KEY, algorithms=['HS256'])
            except jwt.ExpiredSignatureError:
                messages.error(request, "Your session has expired.")
                return redirect('/')
            except Exception:  # covers DecodeError and None token
                messages.error(request, "You must be logged in.")
                return redirect('/')

        return self.get_response(request)
