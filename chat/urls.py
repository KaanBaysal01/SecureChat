from django.urls import path
from . import views

app_name = "chat"

urlpatterns = [
    path("", views.ConversationListView.as_view(), name="conversation_list"),
    path("new/", views.NewConversationView.as_view(), name="new_conversation"),
    path(
        "<int:conversation_id>/",
        views.ConversationDetailView.as_view(),
        name="conversation_detail",
    ),
]
