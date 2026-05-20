import markdown


MARKDOWN_EXTENSIONS = [
    "fenced_code",
    "tables",
    "nl2br",
    "sane_lists",
]


def render_llm_markdown(value: str) -> str:
    text = (value or "").strip()
    return markdown.markdown(
        text,
        extensions=MARKDOWN_EXTENSIONS,
        output_format="html5",
    )
