from django import template
from django.utils.safestring import mark_safe
import markdown as md
import re
import bleach

register = template.Library()

ALLOWED_TAGS = bleach.sanitizer.ALLOWED_TAGS.union({
    "p", "h1", "h2", "h3", "h4", "h5", "h6", "pre", "code", "br", "hr",
    "table", "thead", "tbody", "tfoot", "tr", "th", "td", "caption",
    "colgroup", "col", "span", "details", "summary"
})

ALLOWED_ATTRIBUTES = {
    **bleach.sanitizer.ALLOWED_ATTRIBUTES,
    "a": ["href", "title", "target", "rel"],
    "th": ["scope", "colspan", "rowspan"],
    "td": ["colspan", "rowspan"],
    "col": ["span"],
    "code": ["class"],
    "span": ["class"],
    "details": ["open"],
}

@register.filter(name="markdown")
def markdown_filter(value):
    val = value or ""
    val = re.sub(r'<details(?![^>]*markdown)[^>]*>', lambda m: m.group(0)[:-1] + ' markdown="1">', val, flags=re.IGNORECASE)
    val = re.sub(r'<summary(?![^>]*markdown)[^>]*>', lambda m: m.group(0)[:-1] + ' markdown="1">', val, flags=re.IGNORECASE)
    html = md.markdown(
        val,
        extensions=["extra", "nl2br", "fenced_code", "md_in_html"],
    )
    clean = bleach.clean(html, tags=ALLOWED_TAGS, attributes=ALLOWED_ATTRIBUTES)
    return mark_safe(clean)