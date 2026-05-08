"""Template filters for the audit log UI."""
import json

from django import template
from django.utils.html import escape
from django.utils.safestring import mark_safe

register = template.Library()


@register.filter(name='to_json')
def to_json(value):
    """
    Encode a Python value as valid JSON for safe insertion into an HTML data
    attribute. Returns SafeString so Django does not double-escape the result.

    Without this filter, `{{ dict|escape }}` emits the Python repr (single
    quotes, Python booleans), which JSON.parse cannot consume. This filter
    emits valid JSON, then HTML-escapes the double quotes so the value is
    safe inside a data-* attribute. The browser decodes the entities back
    to JSON when reading `element.dataset.<name>`.

    None becomes the empty object so JSON.parse always succeeds downstream.
    """
    # escape() HTML-encodes all special chars before mark_safe — output is safe
    if value is None:
        return mark_safe(escape('{}'))  # nosec
    return mark_safe(escape(json.dumps(value)))  # nosec
