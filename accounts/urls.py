from django.urls import path
from django.contrib.auth import views as auth_views
from . import views
from .forms import BootstrapAuthenticationForm

app_name = 'accounts'

urlpatterns = [
    path('register/', views.RegisterView.as_view(), name='register'),
    path('verify/', views.VerifyView.as_view(), name='verify'),
    path('resend-code/', views.ResendCodeView.as_view(), name='resend_code'),
    path('profile/', views.ProfileView.as_view(), name='profile'),
        path('login/', auth_views.LoginView.as_view(
        template_name='accounts/login.html',
        authentication_form=BootstrapAuthenticationForm,
    ), name='login'),
    path('users/', views.UserListView.as_view(), name='user_list'),
    path('friend-requests/', views.FriendRequestView.as_view(), name='friend_requests'),
    path('send-request/<int:user_id>/', views.SendFriendRequestView.as_view(), name='send_friend_request'),
    path('accept-request/<int:request_id>/', views.AcceptFriendRequestView.as_view(), name='accept_friend_request'),
    path('reject-request/<int:request_id>/', views.RejectFriendRequestView.as_view(), name='reject_friend_request'),
    path('friends/', views.FriendListView.as_view(), name='friend_list'),
    path('remove-friend/<int:user_id>/', views.RemoveFriendView.as_view(), name='remove_friend'),
    path('logout/', auth_views.LogoutView.as_view(), name='logout'),
]