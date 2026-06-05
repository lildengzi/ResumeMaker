from __future__ import annotations

from core.data import get_default_resume_data
from core.service import build_resume_discussion_prompt, discuss_resume_with_ai


class FakeResponse:
    def __init__(self, content: str) -> None:
        self.content = content


class CapturingLLM:
    def __init__(self, content: str) -> None:
        self.content = content
        self.prompts: list[str] = []

    def invoke(self, prompt: str) -> FakeResponse:
        self.prompts.append(prompt)
        return FakeResponse(self.content)


def test_build_resume_discussion_prompt_includes_user_materials_and_guardrails():
    resume = get_default_resume_data()
    resume["basics"]["name"] = "候选人甲"
    uploaded_files = [
        {
            "name": "teaching-notes.md",
            "type": "readme",
            "raw_text": "数学竞赛成绩、带五年级学生复习小数乘除法、家长反馈耐心。",
        }
    ]

    prompt = build_resume_discussion_prompt(
        question="投这个家教单是不是还会太技术化？",
        current_resume=resume,
        target_context="五年级数学语文家教，家长要求有方法、有耐心。",
        uploaded_files=uploaded_files,
        chat_history=[{"role": "assistant", "content": "建议隐藏无关技术项目。"}],
    )

    assert "五年级数学语文家教" in prompt
    assert "数学竞赛成绩" in prompt
    assert "候选人甲" in prompt
    assert "隐藏无关技术项目" in prompt
    assert "不要编造不存在的成绩" in prompt
    assert "家长看家教简历时，不要细讲技术实现" in prompt
    assert "投这个家教单是不是还会太技术化" in prompt


def test_discuss_resume_with_ai_returns_model_answer_and_prompt():
    llm = CapturingLLM("结论：应隐藏技术项目，改写为教学表达能力。")

    result = discuss_resume_with_ai(
        question="怎么改得更适合家长？",
        current_resume=get_default_resume_data(),
        target_context="小学数学家教",
        uploaded_files=[{"name": "notes.md", "type": "readme", "raw_text": "高考数学 130+"}],
        llm=llm,
    )

    assert result["error"] is None
    assert result["answer"] == "结论：应隐藏技术项目，改写为教学表达能力。"
    assert "小学数学家教" in result["prompt"]
    assert "高考数学 130+" in llm.prompts[0]


def test_discuss_resume_with_ai_handles_empty_question_without_llm_call():
    llm = CapturingLLM("should not be used")

    result = discuss_resume_with_ai(
        question="  ",
        current_resume=get_default_resume_data(),
        llm=llm,
    )

    assert result == {"answer": "请先输入你想讨论的问题。", "error": None}
    assert llm.prompts == []

