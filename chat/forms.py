from django import forms
from django.contrib.auth import get_user_model

User = get_user_model()


class NewConversationForm(forms.Form):
    participants = forms.ModelMultipleChoiceField(
        queryset=User.objects.all(),
        widget=forms.CheckboxSelectMultiple,
        label='Katılımcılar',
    )
    name = forms.CharField(max_length=100, required=False)

    def __init__(self, *args, current_user=None, **kwargs):
        super().__init__(*args, **kwargs)
        if current_user:
            self.fields['participants'].queryset = User.objects.exclude(id=current_user.id)