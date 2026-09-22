"""Add the translation disclosure to the Chinese site's Material footer."""

NOTICE = (
    '本文由大语言模型翻译，可能有误。'
    '<a class="translation-feedback" href="https://github.com/BoxiLi/fatqat-doc-translator/issues">'
    '发现翻译问题？点此反馈</a>'
)


def on_config(config, **kwargs):
    copyright = config.get("copyright", "")
    config["copyright"] = f"{copyright}<br>{NOTICE}" if copyright else NOTICE
    return config
