from django.contrib.auth.models import AbstractUser
from django.db import models
from datetime import timedelta
from django.conf import settings
from django.utils import timezone


class User(AbstractUser):
    profile_photo = models.ImageField(upload_to="profiles/", null=True, blank=True)

    def __str__(self):
        return self.username


class VerificationCode(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="verification_codes",
    )
    code = models.CharField(max_length=6)
    created_at = models.DateTimeField(auto_now_add=True)
    is_used = models.BooleanField(default=False)
    attempt_count = models.PositiveSmallIntegerField(default=0)

    def is_expired(self):
        return timezone.now() > self.created_at + timedelta(minutes=10)

    def is_valid(self):
        return not self.is_used and not self.is_expired() and self.attempt_count < 5

    def __str__(self):
        return f"{self.user.username} — {self.code}"


class FriendRequest(models.Model):
    from_user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="sent_request"
    )
    to_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="received_request",
    )
    STATUS_CHOICES = [
        ("pending", "Bekliyor"),
        ("accepted", "Kabul edildi"),
        ("rejected", "Reddedildi"),
    ]

    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default="pending")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["from_user", "to_user"],
                name="unique_friend_request",
            )
        ]

    def __str__(self):
        return f"{self.from_user} → {self.to_user} ({self.status})"
