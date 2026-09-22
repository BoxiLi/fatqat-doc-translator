"""Add the translation disclosure to every Chinese documentation page."""

NOTICE = (
    '<aside class="admonition note" aria-label="翻译说明">'
    '<p>本页由大语言模型从英文翻译，可能存在翻译错误。'
    '<a href="https://github.com/BoxiLi/fatqat-doc-translator/issues">'
    '反馈翻译问题</a></p></aside>\n'
)


def on_page_content(html, **kwargs):
    return NOTICE + html
