# account/middleware.py
import jwt
from django.conf import settings
from django.shortcuts import redirect
from django.contrib import messages

class AuthRequiredMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response
        self.whitelist = [
            '/',
            '/login.html',
            '/register.html',
            '/account/help/',
            '/application/faq',
            '/account/',
        ]

    def __call__(self, request):
        path = request.path

        # if the request path is in whitelist
        if not any(path == p or path.startswith(p) for p in self.whitelist):
            token = request.session.get('jwt_token')
            try:
                # will raise if missing/invalid/expired
                jwt.decode(token, settings.SECRET_KEY, algorithms=['HS256'])
            except jwt.ExpiredSignatureError:
                messages.error(request, "Your session has expired.")
                return redirect('/')
            except Exception:
                messages.error(request, "You must be logged in.")
                return redirect('/')

        return self.get_response(request)
