import secrets
from django.core.mail import send_mail
from django.conf import settings
from .models import VerificationCode


def generate_code():
    return f"{secrets.randbelow(1000000):06d}"


def create_and_send_code(user):
    code = generate_code()

    VerificationCode.objects.create(user=user, code=code)

    send_mail(
        subject="SecureChat — doğrulama kodunuz",
        message=f"Doğrulama kodunuz: {code}\n\nBu kod 10 dakika geçerlidir.",
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[user.email],
        fail_silently=False,
    )

    return code
