from django import forms
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from .models import User


class BootstrapFormMixin:
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            existing = field.widget.attrs.get('class', '')
            field.widget.attrs['class'] = (existing + ' form-control').strip()


class RegisterForm(BootstrapFormMixin, UserCreationForm):
    class Meta:
        model = User
        fields = ('username', 'email', 'profile_photo')


class VerificationForm(BootstrapFormMixin, forms.Form):
    code = forms.CharField(
        max_length=6,
        min_length=6,
        label='Doğrulama kodu',
        widget=forms.TextInput(attrs={
            'placeholder': '000000',
            'autocomplete': 'one-time-code',
            'inputmode': 'numeric',
        })
    )


class BootstrapAuthenticationForm(BootstrapFormMixin, AuthenticationForm):
    pass

class ProfileForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = User
        fields = ('email', 'profile_photo')