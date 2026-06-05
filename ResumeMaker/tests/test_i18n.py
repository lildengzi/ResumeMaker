from __future__ import annotations

from ui.i18n import DEFAULT_LANGUAGE, LANGUAGE_LABELS, LANGUAGE_OPTIONS, TEXT


def test_i18n_has_supported_language_entries_for_all_keys():
    default_keys = set(TEXT[DEFAULT_LANGUAGE])

    assert DEFAULT_LANGUAGE == "zh"
    assert LANGUAGE_OPTIONS == ("zh", "en")
    assert default_keys
    for language in LANGUAGE_OPTIONS:
        assert set(TEXT[language]) == default_keys


def test_i18n_keys_are_ascii_and_translations_are_real_utf8():
    for translations in TEXT.values():
        assert all(key.isascii() for key in translations)

    assert LANGUAGE_LABELS == {"zh": "中文", "en": "English"}
    assert TEXT["zh"]["language.label"] == "界面语言"
    assert TEXT["zh"]["sidebar.title"] == "简历编辑器"
    assert TEXT["zh"]["module.title"] == "模块标题"
    assert TEXT["zh"]["custom.highlights"] == "亮点（每行一条）"


def test_important_sidebar_and_jd_labels_are_bilingual():
    assert TEXT["zh"]["sidebar.generate"] == "✨ 智能生成简历"
    assert TEXT["en"]["sidebar.generate"] == "✨ Generate resume"
    assert TEXT["zh"]["advisor.section"] == "AI 讨论与材料顾问"
    assert TEXT["en"]["advisor.section"] == "AI discussion and material advisor"
    assert TEXT["zh"]["jd.source"] == "JD 来源"
    assert TEXT["en"]["jd.source"] == "JD source"
    assert TEXT["zh"]["jd.manual_input"] == "手动输入"
    assert TEXT["en"]["jd.manual_input"] == "Manual input"
    assert TEXT["zh"]["jd.run_ocr"] == "识别 JD 图片"
    assert TEXT["en"]["jd.run_ocr"] == "Run OCR"
    assert TEXT["zh"]["jd.fetch_url"] == "抓取 JD 网页"
    assert TEXT["en"]["jd.fetch_url"] == "Fetch URL"
    assert TEXT["zh"]["file.existing_resume"] == "已有简历 / 个人材料 (PDF/Markdown)"
    assert TEXT["en"]["file.existing_resume"] == "Existing resume / personal materials (PDF/Markdown)"


def test_module_editor_labels_are_bilingual():
    assert TEXT["en"]["module.title"] == "Module title"
    assert TEXT["zh"]["module.simple_list"] == "自定义内容（每行一条）"
    assert TEXT["en"]["module.simple_list"] == "Custom content (one item per line)"
    assert TEXT["zh"]["custom.add_field"] == "添加字段"
    assert TEXT["en"]["custom.add_field"] == "Add field"
    assert TEXT["zh"]["custom.general_subfield"] == "通用字段"
    assert TEXT["en"]["custom.general_subfield"] == "General field"


def test_style_control_labels_are_bilingual():
    assert TEXT["zh"]["style.section"] == "🎨 样式微调"
    assert TEXT["en"]["style.section"] == "🎨 Style"
    assert TEXT["zh"]["style.reset"] == "重置为推荐样式"
    assert TEXT["en"]["style.reset"] == "Reset recommended style"


def test_user_visible_language_text_is_complete_for_safe_novice_flows():
    required_keys = [
        "ai.error.missing_api_key",
        "ai.minimum_info_warning",
        "ai.info.generic_optimization",
        "ai.info.analyzing_jd",
        "file.existing_resume",
        "file.existing_resume_saved",
        "jd.paste_text",
        "jd.paste_after_fetch",
        "custom.general_subfield",
        "custom.value_placeholder",
        "style.template",
        "style.show_photo",
    ]

    for language in LANGUAGE_OPTIONS:
        for key in required_keys:
            value = TEXT[language][key]
            assert isinstance(value, str)
            assert value.strip()
            assert value != key
