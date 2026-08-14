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
    path('users/', views.user_list, name='user_list'),
    path('friend-requests/', views.friend_requests, name='friend_requests'),
    path('send-request/<int:user_id>/', views.send_friend_request, name='send_friend_request'),
    path('accept-request/<int:request_id>/', views.accept_friend_request, name='accept_friend_request'),
    path('reject-request/<int:request_id>/', views.reject_friend_request, name='reject_friend_request'),
    path('friends/', views.friend_list, name='friend_list'),
    path('remove-friend/<int:user_id>/', views.remove_friend, name='remove_friend'),
    path('logout/', auth_views.LogoutView.as_view(), name='logout'),
]