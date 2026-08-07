from django.contrib.auth.forms import UserCreationForm
from .models import User
from django import forms


class RegisterForm(UserCreationForm):
    class Meta:
        model = User
        fields = ('username', 'email', 'profile_photo')

class VerificationForm(forms.Form):
    code = forms.CharField(
        max_length = 6,
        min_length = 6,
        label='Doğrulama kodu',
        widget=forms.TextInput(attrs={
            'placeholder': '000000',
            'autocomplete': 'one-time-code',
            'inputmode': 'numeric',
        })
    )