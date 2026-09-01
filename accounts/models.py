from django.contrib.auth.models import AbstractUser
from django.db import models
from datetime import timedelta
from django.conf import settings
from django.utils import timezone


class User(AbstractUser):
    profile_photo = models.ImageField(upload_to="profiles/", null=True, blank=True)
    last_seen = models.DateTimeField(null=True, blank=True)
    show_last_seen = models.BooleanField(default=True, verbose_name="Son görülme ve çevrimiçi durumumu göster",)

    def get_friends(self):
        sent = FriendRequest.objects.filter(
            from_user = self, status = "accepted"
        ).values_list("to_user_id",flat=True)

        received = FriendRequest.objects.filter(
            to_user = self, status = "accepted"
        ).values_list("from_user_id",flat=True)

        return User.objects.filter(id__in=set(sent) | set(received) )

    def get_related_ids(self):
        sent = FriendRequest.objects.filter(
            from_user=self, status__in=["pending", "accepted"]
        ).values_list("to_user_id", flat=True)

        received = FriendRequest.objects.filter(
            to_user=self, status__in=["pending", "accepted"]
        ).values_list("from_user_id", flat=True)

        return set(sent) | set(received)

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

class LoginAttempt(models.Model):
    username = models.CharField(max_length=150)
    created_at = models.DateTimeField(auto_now_add=True)

    MAX_ATTEMPTS = 5
    WINDOW_MINUTES = 15

    @classmethod
    def is_locked(cls, username):
        window_start = timezone.now() - timedelta(minutes=cls.WINDOW_MINUTES)
        return cls.objects.filter(
            username__iexact=username,
            created_at__gte=window_start,
        ).count() >= cls.MAX_ATTEMPTS

    @classmethod
    def record_failure(cls, username):
        cls.objects.create(username=username)

    @classmethod
    def clear(cls, username):
        cls.objects.filter(username__iexact=username).delete()

    def __str__(self):
        return f"{self.username} — {self.created_at}"