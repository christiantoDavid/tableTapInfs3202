# account/urls.py
from django.urls import path
from django.views.generic import TemplateView
from .views import (
    register_view,
    login_view,
    logout_view,
    google_login_start,
    google_login_callback,
    github_login_start,
    github_login_callback,
)

app_name = 'account'

urlpatterns = [
    # registration & login
    path('register/', register_view, name='register'),
    path('login/', login_view, name='login'),
    path('logout/', logout_view, name='logout'),

    # Google OAuth
    path('login/google/', google_login_start, name='google_login_start'),
    path('login/google/callback/', google_login_callback, name='google_callback'),

    # GitHub OAuth
    path('login/github/', github_login_start, name='github_login_start'),
    path('login/github/callback/', github_login_callback, name='github_callback'),

    path('help/', TemplateView.as_view(template_name='help.html'),
         name='help'),
    path('faq/', TemplateView.as_view(template_name='faq.html'),
         name='faq'),
]
