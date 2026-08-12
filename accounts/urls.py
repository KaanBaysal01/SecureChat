from django.urls import path
from django.contrib.auth import views as auth_views
from . import views
from .forms import BootstrapAuthenticationForm

app_name = 'accounts'

urlpatterns = [
    path('register/', views.register, name='register'),
    path('verify/', views.verify, name='verify'),
    path('resend-code/', views.resend_code, name='resend_code'),
    path('login/', auth_views.LoginView.as_view(
        template_name='accounts/login.html',
        authentication_form=BootstrapAuthenticationForm,
    ), name='login'),
    path('logout/', auth_views.LogoutView.as_view(), name='logout'),
]