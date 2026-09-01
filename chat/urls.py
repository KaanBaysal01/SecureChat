from django.urls import path
from . import views

app_name = "chat"

urlpatterns = [
    path("", views.ConversationListView.as_view(), name="conversation_list"),
    path("new/", views.NewConversationView.as_view(), name="new_conversation"),
    path("<int:conversation_id>/delete/", views.DeleteConversationView.as_view(), name="delete_conversation"),
    path("<int:conversation_id>/settings/", views.GroupSettingsView.as_view(), name="group_settings"),
    path("<int:conversation_id>/make-admin/<int:user_id>/", views.MakeAdminView.as_view(), name="make_admin"),
    path("<int:conversation_id>/add-member/<int:user_id>/", views.AddMemberView.as_view(), name="add_member"),
    path("<int:conversation_id>/remove-member/<int:user_id>/", views.RemoveMemberView.as_view(), name="remove_member"),
    path("<int:conversation_id>/leave/", views.LeaveGroupView.as_view(), name="leave_group"),
    path("<int:conversation_id>/upload/", views.FileUploadView.as_view(), name="upload"),
    path("file/<int:message_id>/", views.ChatFileView.as_view(), name="file"),
    path("join/<str:token>/", views.JoinGroupView.as_view(), name="join_group"),
    path("<int:conversation_id>/regenerate-invite/", views.RegenerateInviteView.as_view(), name="regenerate_invite"),
    path("<int:conversation_id>/", views.ConversationDetailView.as_view(), name="conversation_detail"),
]