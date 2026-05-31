from django import template
from django.utils.safestring import mark_safe
import markdown as md
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
    html = md.markdown(
        value or "",
        extensions=["extra", "nl2br", "fenced_code"],
    )
    clean = bleach.clean(html, tags=ALLOWED_TAGS, attributes=ALLOWED_ATTRIBUTES)
    return mark_safe(clean)