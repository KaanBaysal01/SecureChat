from django.db import models
from django.conf import settings
from .crypto import decrypt_message,encrypt_message
from pathlib import Path
from django.db.models.signals import post_delete
from django.dispatch import receiver 


class Conversation(models.Model):
    participants = models.ManyToManyField(
        settings.AUTH_USER_MODEL, related_name="conversations"
    )
    admins = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        related_name="admin_of",
        blank=True,
    )
    is_group = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    name = models.CharField(max_length=100, null=True, blank=True)
    pinned_message = models.ForeignKey(
        "Message",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="pinned_in",
    )
    pinned_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="pinned_conversations",
    )
    invite_version = models.PositiveIntegerField(default=1)
    

    def is_admin(self, user):
        return self.admins.filter(id=user.id).exists()
    
    def log_event(self, actor, text):
        return Message.objects.create(
            conversation=self,
            sender=actor,
            encrypted_content=encrypt_message(text),
            message_type="system",
        )

    def can_unpin(self, user):
        if self.pinned_message_id is None:
            return False

        return self.pinned_by_id == user.id or (
            self.is_group and self.is_admin(user)
        )

    def __str__(self):
        if self.name:
            return self.name
        return f"Conversation {self.id}"


class Message(models.Model):
    conversation = models.ForeignKey(
        Conversation, on_delete=models.CASCADE, related_name="messages"
    )
    sender = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="sent_messages"
    )
    encrypted_content = models.TextField(blank=True, default="")
    is_delivered = models.BooleanField(default=False)
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    client_message_id = models.CharField(max_length=64, null=True, blank=True)
    message_type = models.CharField(
        max_length=10,
        choices=[("text", "Metin"), ("system", "Sistem")],
        default="text",
    )
    file_name = models.CharField(max_length=255, blank=True)
    file_size = models.PositiveIntegerField(null=True, blank=True)
    file_type = models.CharField(max_length=100, blank=True)
    file_path = models.CharField(max_length=255, blank=True)
    file_key = models.BinaryField(null=True, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["conversation", "client_message_id"],
                name="unique_client_message_per_conversation",
            )
        ]
        indexes = [
            models.Index(fields=["conversation", "-created_at"]),
        ]

    @property
    def content(self):
        if not self.encrypted_content:
            return ""
        return decrypt_message(self.encrypted_content)
    
    @property
    def has_file(self):
        return bool(self.file_path)

    @property
    def is_image(self):
        return self.file_type.startswith("image/")

    @property
    def is_system(self):
        return self.message_type == "system"

    @property
    def read_count(self):
        return self.read_statuses.count()

    def __str__(self):
        return f"Message {self.id} from {self.sender}"


class MessageReadStatus(models.Model):
    message = models.ForeignKey(
        Message, on_delete=models.CASCADE, related_name="read_statuses"
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="read_messages"
    )
    read_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["message", "user"], name="unique_read_status_per_user"
            )
        ]

    def __str__(self):
        return f"{self.user} read message {self.message_id}"

@receiver(post_delete, sender=Message)
def delete_encrypted_blob(sender, instance, **kwargs):
    if not instance.file_path:
        return
    path = Path(settings.SECURE_FILE_ROOT) / instance.file_path
    path.unlink(missing_ok=True)