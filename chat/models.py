from django.db import models
from django.conf import settings
from .crypto import decrypt_message


class Conversation(models.Model):
    participants = models.ManyToManyField(settings.AUTH_USER_MODEL, related_name='conversations')
    is_group = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    name = models.CharField(max_length=100, null=True, blank=True)


    def __str__(self):
        if self.name:
            return self.name
        return f"Conversation {self.id}"


class Message(models.Model):
    conversation = models.ForeignKey(Conversation, on_delete=models.CASCADE, related_name='messages')
    sender = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='sent_messages')
    encrypted_content = models.TextField()
    is_delivered = models.BooleanField(default=False)
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    client_message_id = models.CharField(max_length=64, null=True, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['conversation', 'client_message_id'],
                name='unique_client_message_per_conversation',
            )
        ]
        indexes = [
            models.Index(fields=['conversation', '-created_at']),
        ]
    
    @property
    def content(self):
        return decrypt_message(self.encrypted_content)

    @property
    def read_count(self):
        return self.read_statuses.count()

    def __str__(self):
        return f"Message {self.id} from {self.sender}"



class MessageReadStatus(models.Model):
    message = models.ForeignKey(Message, on_delete=models.CASCADE, related_name='read_statuses')
    user = models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.CASCADE,related_name='read_messages')
    read_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields = ['message','user'],
                name = 'unique_read_status_per_user'
            )
        ]
    
    def __str__(self):
        return f"{self.user} read message {self.message_id}"
    