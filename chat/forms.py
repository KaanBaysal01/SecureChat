from django import forms
from django.contrib.auth import get_user_model
import os
import unicodedata
from django.conf import settings
from PIL import Image

User = get_user_model()


class NewConversationForm(forms.Form):
    participants = forms.ModelMultipleChoiceField(
        queryset=User.objects.all(),
        widget=forms.CheckboxSelectMultiple,
        label="Katılımcılar",
    )
    name = forms.CharField(max_length=100, required=False)

    def __init__(self, *args, current_user=None, **kwargs):
        super().__init__(*args, **kwargs)
        if current_user:
            self.fields["participants"].queryset = current_user.get_friends()

ALLOWED_IMAGE_FORMATS = {
    "JPEG": "image/jpeg",
    "PNG": "image/png",
    "GIF": "image/gif",
    "WEBP": "image/webp",
}


class FileUploadForm(forms.Form):
    file = forms.FileField()

    image_format = None

    def clean_file(self):
        f = self.cleaned_data["file"]

        if f.size == 0:
            raise forms.ValidationError("Dosya boş.")

        if f.size > settings.MAX_UPLOAD_SIZE:
            limit = settings.MAX_UPLOAD_SIZE // (1024 * 1024)
            raise forms.ValidationError(f"Dosya {limit} MB'tan büyük olamaz.")

        try:
            image = Image.open(f)
            image.verify()
            if image.format in ALLOWED_IMAGE_FORMATS:
                self.image_format = image.format
        except Exception:
            self.image_format = None
        finally:
            f.seek(0)

        return f

    @property
    def content_type(self):
        return ALLOWED_IMAGE_FORMATS.get(self.image_format, "application/octet-stream")

    @property
    def safe_name(self):
        name = os.path.basename(self.cleaned_data["file"].name)
        name = unicodedata.normalize("NFKC", name)
        name = "".join(
            c for c in name if c.isprintable() and c not in '\\/:*?"<>|'
        )
        return name[:255] or "dosya"