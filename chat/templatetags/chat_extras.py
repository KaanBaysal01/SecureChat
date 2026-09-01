import re
from django import template
from django.utils.html import escape
from django.utils.safestring import mark_safe

register = template.Library()

URL_RE = re.compile(r'(https?://[^\s<>"\']+)')


@register.filter
def linkify(text):
    if not text:
        return ""

    parts = URL_RE.split(text)
    html_parts = []

    for i, part in enumerate(parts):
        if i % 2 == 1:
            safe_url = escape(part)
            html_parts.append(
                f'<a href="{safe_url}" target="_blank" rel="noopener noreferrer">{safe_url}</a>'
            )
        else:
            html_parts.append(escape(part))

    return mark_safe("".join(html_parts))
