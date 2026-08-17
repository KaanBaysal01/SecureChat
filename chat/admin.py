from django.contrib import admin
from .models import Conversation, Message


@admin.register(Conversation)
class ConversationAdmin(admin.ModelAdmin):
    list_display = ("id", "is_group", "created_at", "participant_list")
    list_filter = ("is_group",)
    filter_horizontal = ("participants",)

    def participant_list(self, obj):
        return ", ".join(u.username for u in obj.participants.all())

    participant_list.short_description = "Katılımcılar"


@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "conversation",
        "sender",
        "is_delivered",
        "is_read",
        "created_at",
    )
    list_filter = ("is_read", "is_delivered", "created_at")
    search_fields = ("sender__username",)
    readonly_fields = ("created_at",)
