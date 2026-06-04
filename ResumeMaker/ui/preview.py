from __future__ import annotations

import html
from typing import Any, Dict, List

import streamlit as st
import streamlit.components.v1 as components

from renderers import build_full_preview_document, build_style_params
from ui.i18n import t


def render_resume_preview(
    resume_data: Dict[str, Any],
    style_params: Dict[str, Any],
    preview_version: int,
    workflow_logs: List[Dict[str, Any]] | None = None,
    preview_html: str | None = None,
    conditional_suggestions: List[str] | None = None,
) -> None:
    full_preview_html = preview_html or build_full_preview_document(resume_data, style_params=style_params)
    resolved_style = build_style_params(style_params)
    components.html(
        full_preview_html,
        height=int(resolved_style.get("sidebar_preview_height", 1320)),
        scrolling=True,
    )

    suggestions_html = render_conditional_suggestions_html(conditional_suggestions or [])
    if suggestions_html:
        st.markdown(suggestions_html, unsafe_allow_html=True)

    if workflow_logs:
        with st.expander(f"查看工作流日志（预览版本 v{preview_version}）", expanded=False):
            for log in workflow_logs:
                st.write(f"- [{log.get('agent', 'unknown')}] {_format_workflow_log_message(log)}")
                for detail in _format_workflow_log_details(log):
                    st.caption(f"  - {detail}")


def _format_workflow_log_message(log: Dict[str, Any]) -> str:
    message_key = str(log.get("message_key", "") or "")
    message_args = log.get("message_args", {})
    if message_key:
        if not isinstance(message_args, dict):
            message_args = {}
        return t(message_key, **message_args)
    return str(log.get("message", "") or "")


def _format_workflow_log_details(log: Dict[str, Any]) -> List[str]:
    details = log.get("details", [])
    if isinstance(details, str):
        details = [details]
    if not isinstance(details, list):
        return []
    result = [str(item).strip() for item in details if str(item).strip()]
    if any("timed out" in item.lower() or "timeout" in item.lower() for item in result):
        result.append(t("workflow.detail.timeout_hint"))
    return result


def render_conditional_suggestions_html(suggestions: List[str]) -> str:
    clean_items = [str(item or "").strip() for item in suggestions if str(item or "").strip()]
    if not clean_items:
        return ""

    rows = "\n".join(
        f'<div class="suggestion-row"><span class="suggestion-text">{html.escape(item)}</span></div>'
        for item in clean_items[:8]
    )
    return f"""
<style>
.conditional-suggestions {{
  margin-top: 16px;
  padding: 16px 18px;
  border: 1px solid rgba(148, 163, 184, 0.38);
  border-radius: 8px;
  background: #ffffff;
  color: #1f2937;
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
}}
.conditional-suggestions h3 {{
  margin: 0 0 10px;
  font-size: 16px;
  line-height: 1.35;
  font-weight: 650;
  color: #111827;
}}
.suggestion-row {{
  padding: 8px 0;
  border-top: 1px solid rgba(226, 232, 240, 0.9);
}}
.suggestion-row:first-of-type {{
  border-top: 0;
}}
.suggestion-text {{
  display: block;
  font-size: 14px;
  line-height: 1.65;
  color: #374151;
  word-break: break-word;
}}
</style>
<div class="conditional-suggestions">
  <h3>条件补充建议</h3>
  {rows}
</div>
""".strip()


def render_preview_tips() -> None:
    with st.container(border=True):
        st.markdown("#### 预览优化说明")
        st.write(
            "- 模板已支持现代蓝 / 雅致灰 / 翡翠专业三套视觉风格。\n"
            "- 技能区改为标签化展示，项目与经历区改为卡片时间线样式。\n"
            "- 顶部信息区支持头像、职位徽章、联系信息分层展示。"
        )
