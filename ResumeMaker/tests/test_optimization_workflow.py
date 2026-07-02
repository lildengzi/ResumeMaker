from __future__ import annotations

from copy import deepcopy

from agents.existing_resume_parser import ExistingResumeParserAgent
from agents.factory import AgentFactory
from agents.info_collector import InfoCollectorAgent
from agents.resume_writer import ResumeWriterAgent
from core.data import get_default_resume_data
from core.service import import_existing_resume, run_resume_workflow
from workflow.graph import ResumeWorkflow


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


def test_info_collector_extracts_uploaded_existing_resume_text_from_metadata():
    agent = InfoCollectorAgent()
    state = {
        "current_resume": get_default_resume_data(),
        "jd_text": "",
        "uploaded_files": [
            {
                "name": "resume.md",
                "type": "existing_resume",
                "path": "",
                "raw_text": "Python backend engineer with FastAPI project experience.",
            }
        ],
        "workflow_logs": [],
    }

    result = agent.run(state)

    context = result["collected_facts"]["uploaded_resume_context"]
    assert context["files"][0]["has_text"] is True
    assert "FastAPI project experience" in context["text"]
    assert result["collected_facts"]["optimization_goal"] == "general_resume_polish"
    assert result["collected_facts"]["sections_summary"]["skills_count"] == 0


def test_info_collector_parses_uploaded_existing_resume_file_when_path_is_present(monkeypatch):
    def fake_parse_uploaded_resume(file_path: str):
        assert file_path == "data/uploads/existing_resume.md"
        return {
            "file_type": "md",
            "file_name": "existing_resume.md",
            "raw_text": "Built payment APIs and improved latency.",
        }

    monkeypatch.setattr("agents.info_collector.parse_uploaded_resume", fake_parse_uploaded_resume)
    agent = InfoCollectorAgent()

    result = agent.run(
        {
            "current_resume": get_default_resume_data(),
            "jd_text": "Backend role",
            "uploaded_files": [
                {
                    "name": "existing_resume.md",
                    "type": "existing_resume",
                    "path": "data/uploads/existing_resume.md",
                }
            ],
            "workflow_logs": [],
        }
    )

    context = result["collected_facts"]["uploaded_resume_context"]
    assert "payment APIs" in context["text"]
    assert context["files"][0]["file_type"] == "md"
    assert result["collected_facts"]["optimization_goal"] == "jd_targeted"


def test_info_collector_handles_optional_jd_and_file_metadata_without_crashing(monkeypatch):
    def fake_parse_uploaded_resume(file_path: str):
        assert file_path == "data/uploads/broken.pdf"
        raise RuntimeError("cannot parse this upload")

    monkeypatch.setattr("agents.info_collector.parse_uploaded_resume", fake_parse_uploaded_resume)
    agent = InfoCollectorAgent()

    without_jd = agent.run(
        {
            "current_resume": {},
            "jd_text": "   ",
            "uploaded_files": [
                None,
                {"name": "notes.md", "type": "readme", "raw_text": "README text is not an existing resume."},
                {"name": "broken.pdf", "type": "existing_resume", "path": "data/uploads/broken.pdf"},
            ],
            "workflow_logs": [],
        }
    )

    facts = without_jd["collected_facts"]
    assert facts["has_jd"] is False
    assert facts["optimization_goal"] == "general_resume_polish"
    assert facts["uploaded_resume_context"]["files"][0]["name"] == "broken.pdf"
    assert facts["uploaded_resume_context"]["files"][0]["has_text"] is False
    assert facts["uploaded_resume_context"]["text"] == ""

    with_jd = agent.run(
        {
            "current_resume": {},
            "jd_text": "Need a backend engineer",
            "uploaded_files": [],
            "workflow_logs": [],
        }
    )

    assert with_jd["collected_facts"]["has_jd"] is True
    assert with_jd["collected_facts"]["optimization_goal"] == "jd_targeted"
    assert with_jd["workflow_logs"][-1]["message_key"] == "workflow.log.info_collector.no_uploads"


def test_resume_writer_prompt_includes_jd_and_uploaded_resume_context():
    resume = get_default_resume_data()
    resume["basics"]["name"] = "Candidate"
    optimized = deepcopy(resume)
    optimized["modules"][1]["content"]["items"] = ["Python", "FastAPI"]
    llm = CapturingLLM(content=f"{optimized}")
    llm.content = (
        '{"basics":{"name":"Candidate"},"modules":['
        '{"id":"skills_2","title":"Skills","type":"skills","visible":true,"order":2,'
        '"content":{"items":["Python","FastAPI"]}}],"style":{}}'
    )
    agent = ResumeWriterAgent(llm=llm)

    result = agent.run(
        {
            "current_resume": resume,
            "jd_text": "Need FastAPI backend developer.",
            "collected_facts": {
                "optimization_goal": "jd_targeted",
                "uploaded_resume_context": {"text": "Existing resume mentions FastAPI and APIs."},
            },
            "workflow_logs": [],
        }
    )

    prompt = llm.prompts[0]
    assert "Need FastAPI backend developer" in prompt
    assert "Existing resume mentions FastAPI" in prompt
    assert "Optimization mode: jd_targeted" in prompt
    assert "STAR rewrite contract" in prompt
    assert "Skills tag contract" in prompt
    assert "content.items must be short tag phrases, not full sentences" in prompt
    assert "conditional_suggestions" in prompt
    skills_module = next(module for module in result["final_resume"]["modules"] if module["type"] == "skills")
    assert skills_module["content"]["items"] == ["Python", "FastAPI"]
    assert result["workflow_logs"][-1]["details"] == [
        "mcp.snapshot.deep_copied",
        "mcp.schema.validated",
        "mcp.basics_style.preserved",
        "mcp.modules.accepted=1",
    ]


def test_resume_writer_prompt_includes_supplemental_materials_for_general_scenarios():
    resume = get_default_resume_data()
    llm = CapturingLLM(content='{"basics":{},"modules":[],"style":{}}')
    agent = ResumeWriterAgent(llm=llm, config={"workflow": {"fallback_to_local_draft": False}, "prompts": {}})

    agent.run(
        {
            "current_resume": resume,
            "jd_text": "家长希望了解数学家教能力、考试成绩和沟通耐心。",
            "collected_facts": {
                "optimization_goal": "jd_targeted",
                "supplemental_context": {
                    "text": "高考数学 130+，曾辅导初中学生整理错题并制定复习计划。"
                },
            },
            "workflow_logs": [],
        }
    )

    prompt = llm.prompts[0]
    assert "tutoring" in prompt
    assert "高考数学 130+" in prompt
    assert "teaching cases" in prompt


def test_resume_writer_accepts_conditional_suggestions_without_writing_them_into_resume():
    resume = get_default_resume_data()
    project_module = next(module for module in resume["modules"] if module["type"] == "projects")
    project_module["content"]["items"] = [
        {
            "name": "ResumeMaker",
            "role": "Backend Developer",
            "startDate": "2025.01",
            "endDate": "2025.03",
            "description": "Built resume preview.",
            "highlights": ["Built export flow"],
        }
    ]
    llm = CapturingLLM(
        content=(
            '{"basics":{},"modules":['
            '{"id":"projects_3","title":"Projects","type":"projects","visible":true,"order":3,'
            '"content":{"items":[{"name":"ResumeMaker","role":"Backend Developer",'
            '"startDate":"2025.01","endDate":"2025.03",'
            '"description":"For a resume generation workflow, owned preview and export reliability improvements.",'
            '"highlights":["Clarify exact latency or export success-rate improvement for stronger STAR results."]}]}}],'
            '"style":{},'
            '"conditional_suggestions":["补充 ResumeMaker 导出成功率、耗时或用户规模，便于强化 STAR 结果。"]}'
        )
    )
    agent = ResumeWriterAgent(llm=llm, config={"workflow": {"fallback_to_local_draft": False}, "prompts": {}})

    result = agent.run({"current_resume": resume, "jd_text": "", "workflow_logs": []})

    final_resume = result["final_resume"]
    project_module = next(module for module in final_resume["modules"] if module["type"] == "projects")
    project_text = str(project_module["content"]["items"])
    assert result["conditional_suggestions"] == ["补充 ResumeMaker 导出成功率、耗时或用户规模，便于强化 STAR 结果。"]
    assert "conditional_suggestions" not in final_resume
    assert "补充 ResumeMaker 导出成功率" not in project_text


def test_resume_writer_preserves_basics_while_allowing_experience_rewrite():
    resume = get_default_resume_data()
    resume["basics"]["name"] = "Candidate"
    resume["basics"]["email"] = "candidate@example.com"
    project_module = next(module for module in resume["modules"] if module["type"] == "projects")
    project_module["content"]["items"] = [
        {
            "name": "ResumeMaker",
            "role": "Backend Developer",
            "startDate": "2025.01",
            "endDate": "2025.03",
            "description": "Built export flow.",
            "highlights": ["Supported markdown export"],
        }
    ]
    llm = CapturingLLM(
        content=(
            '{"basics":{"name":"Invented","email":"other@example.com"},"modules":['
            '{"id":"projects_3","title":"Projects","type":"projects","visible":true,"order":3,'
            '"content":{"items":[{"name":"Invented Project","role":"Tech Lead",'
            '"startDate":"2026.01","endDate":"2026.12","description":"Built reliable export flow.",'
            '"highlights":["Improved export reliability"]}]}}],"style":{"theme_color":"#000000"}}'
        )
    )
    agent = ResumeWriterAgent(llm=llm, config={"workflow": {"fallback_to_local_draft": False}, "prompts": {}})

    result = agent.run({"current_resume": resume, "jd_text": "Need backend export work.", "workflow_logs": []})

    final_resume = result["final_resume"]
    assert final_resume["basics"]["name"] == "Candidate"
    assert final_resume["basics"]["email"] == "candidate@example.com"
    guarded_project = next(module for module in final_resume["modules"] if module["type"] == "projects")
    item = guarded_project["content"]["items"][0]
    assert item["name"] == "Invented Project"
    assert item["role"] == "Tech Lead"
    assert item["startDate"] == "2026.01"
    assert item["endDate"] == "2026.12"
    assert item["description"] == "Built reliable export flow."
    assert item["highlights"] == ["Improved export reliability"]


def test_resume_writer_rejects_invented_module_and_falls_back_to_current_resume():
    resume = get_default_resume_data()
    llm = CapturingLLM(
        content=(
            '{"basics":{},"modules":['
            '{"id":"invented_99","title":"Awards","type":"custom","visible":true,"order":99,'
            '"content":{"fields":[{"label":"Award","value":"Invented award"}],"description":"","highlights":[]}}],'
            '"style":{}}'
        )
    )
    agent = ResumeWriterAgent(llm=llm, config={"workflow": {"fallback_to_local_draft": False}, "prompts": {}})

    result = agent.run({"current_resume": resume, "jd_text": "", "workflow_logs": []})

    assert result["error"]
    assert "unknown module" in result["error"]
    assert len(result["final_resume"]["modules"]) == len(resume["modules"])
    assert result["workflow_logs"][-1]["details"][0].startswith("LLM output rejected:")


def test_resume_writer_allows_custom_fields_to_be_rewritten_for_target_audience():
    resume = get_default_resume_data()
    resume["modules"] = [
        {
            "id": "custom_1",
            "title": "Awards",
            "type": "custom",
            "visible": True,
            "order": 1,
            "content": {
                "fields": [{"label": "Award", "value": "Hackathon finalist"}],
                "description": "Made prototype.",
                "highlights": ["Team collaboration"],
            },
        }
    ]
    llm = CapturingLLM(
        content=(
            '{"basics":{},"modules":['
            '{"id":"custom_1","title":"Awards","type":"custom","visible":true,"order":1,'
            '"content":{"fields":[{"label":"Award","value":"Invented winner"}],'
            '"description":"Delivered a functional prototype under time constraints.",'
            '"highlights":["Cross-functional collaboration"]}}],"style":{}}'
        )
    )
    agent = ResumeWriterAgent(llm=llm, config={"workflow": {"fallback_to_local_draft": False}, "prompts": {}})

    result = agent.run({"current_resume": resume, "jd_text": "", "workflow_logs": []})

    custom_module = result["final_resume"]["modules"][0]
    assert custom_module["content"]["fields"] == [{"label": "General subfield", "value": "Invented winner"}]
    assert custom_module["content"]["description"] == "Delivered a functional prototype under time constraints."
    assert custom_module["content"]["highlights"] == ["Cross-functional collaboration"]


def test_agent_factory_creates_existing_resume_parser():
    agent = AgentFactory.create("existing_resume_parser")

    assert isinstance(agent, ExistingResumeParserAgent)


def test_existing_resume_parser_fills_blank_basics_and_skills_from_uploaded_text():
    resume = get_default_resume_data()
    agent = ExistingResumeParserAgent()

    result = agent.run(
        {
            "current_resume": resume,
            "collected_facts": {
                "uploaded_resume_context": {
                    "text": (
                        "Alice Zhang\n"
                        "alice@example.com | +86 138 0000 0000\n"
                        "https://github.com/alice\n"
                        "Backend projects with Python, FastAPI, MySQL, Docker and React."
                    )
                }
            },
            "uploaded_files": [],
            "workflow_logs": [],
        }
    )

    basics = result["current_resume"]["basics"]
    skills_module = next(module for module in result["current_resume"]["modules"] if module["type"] == "skills")
    assert basics["email"] == "alice@example.com"
    assert basics["phone"] == "+86 138 0000 0000"
    assert basics["website"] == "https://github.com/alice"
    assert skills_module["content"]["items"] == ["Python", "FastAPI", "MySQL", "Docker", "React"]
    assert set(result["parsed_resume_changes"]) == {
        "basics.name",
        "basics.email",
        "basics.phone",
        "basics.website",
        "skills+=5",
    }


def test_existing_resume_parser_preserves_existing_user_filled_basics_and_dedupes_skills():
    resume = get_default_resume_data()
    resume["basics"]["email"] = "current@example.com"
    resume["basics"]["phone"] = "12345678"
    skills_module = next(module for module in resume["modules"] if module["type"] == "skills")
    skills_module["content"]["items"] = ["Python"]
    agent = ExistingResumeParserAgent()

    result = agent.run(
        {
            "current_resume": resume,
            "collected_facts": {
                "uploaded_resume_context": {
                    "text": "new@example.com 18888888888 Python FastAPI PostgreSQL"
                }
            },
            "workflow_logs": [],
        }
    )

    basics = result["current_resume"]["basics"]
    skills_module = next(module for module in result["current_resume"]["modules"] if module["type"] == "skills")
    assert basics["email"] == "current@example.com"
    assert basics["phone"] == "12345678"
    assert skills_module["content"]["items"] == ["Python", "FastAPI", "PostgreSQL"]
    assert result["parsed_resume_changes"] == ["skills+=2"]


def test_existing_resume_parser_uses_llm_structured_extraction_before_rule_fallback():
    resume = get_default_resume_data()
    llm = CapturingLLM(
        content=(
            '{"basics":{"name":"Candidate One","headline":"Backend Intern","phone":"2025.01-2025.03",'
            '"email":"candidate.one@example.com"},"modules":['
            '{"type":"projects","content":{"items":[{"name":"TinyWebServer","role":"C++ Backend",'
            '"startDate":"2026.01","endDate":"2026.04","description":"Built an HTTP server.",'
            '"highlights":["Implemented epoll ET networking"]}]}},'
            '{"type":"skills","content":{"items":["C++","Docker"]}}]}'
        )
    )
    agent = ExistingResumeParserAgent(llm=llm)

    result = agent.run(
        {
            "current_resume": resume,
            "collected_facts": {
                "uploaded_resume_context": {
                    "text": "候选人甲\nTinyWebServer 2026.01-2026.04\nC++ Docker"
                }
            },
            "workflow_logs": [],
        }
    )

    basics = result["current_resume"]["basics"]
    project_module = next(module for module in result["current_resume"]["modules"] if module["type"] == "projects")
    skills_module = next(module for module in result["current_resume"]["modules"] if module["type"] == "skills")

    assert basics["name"] == "Candidate One"
    assert basics["headline"] == "Backend Intern"
    assert basics["email"] == "candidate.one@example.com"
    assert basics["phone"] == ""
    assert project_module["content"]["items"][0]["name"] == "TinyWebServer"
    assert project_module["content"]["items"][0]["highlights"] == ["Implemented epoll ET networking"]
    assert skills_module["content"]["items"] == ["C++", "Docker"]
    assert "llm.projects+=1" in result["parsed_resume_changes"]
    assert "llm.skills+=2" in result["parsed_resume_changes"]


def test_existing_resume_parser_llm_prompt_matches_resume_json_contract():
    prompt = ExistingResumeParserAgent._build_llm_parse_prompt("Alice\nProject text")

    required_terms = [
        '"basics"',
        '"modules"',
        '"name"',
        '"headline"',
        '"age"',
        '"gender"',
        '"city"',
        '"phone"',
        '"email"',
        '"website"',
        '"portfolio"',
        '"type": "education"',
        '"type": "skills"',
        '"type": "projects"',
        '"type": "companyExperience"',
        '"type": "campusExperience"',
        '"type": "selfEvaluation"',
        '"school"',
        '"degree"',
        '"major"',
        '"startDate"',
        '"endDate"',
        '"details"',
        '"items"',
        '"name"',
        '"role"',
        '"description"',
        '"highlights"',
        '"company"',
        '"organization"',
    ]
    for term in required_terms:
        assert term in prompt

    assert "Do not output style, id, title, visible, order, photo_path" in prompt
    assert "Return one valid JSON object only" in prompt
    assert "Alice\nProject text" in prompt


def test_existing_resume_parser_llm_does_not_overwrite_existing_user_facts():
    resume = get_default_resume_data()
    resume["basics"]["name"] = "Current Name"
    llm = CapturingLLM(content='{"basics":{"name":"Other Name","email":"new@example.com"},"modules":[]}')
    agent = ExistingResumeParserAgent(llm=llm)

    result = agent.run(
        {
            "current_resume": resume,
            "collected_facts": {"uploaded_resume_context": {"text": "Other Name new@example.com"}},
            "workflow_logs": [],
        }
    )

    basics = result["current_resume"]["basics"]
    assert basics["name"] == "Current Name"
    assert basics["email"] == "new@example.com"


def test_existing_resume_parser_without_uploaded_text_leaves_resume_unchanged():
    resume = get_default_resume_data()
    agent = ExistingResumeParserAgent()

    result = agent.run({"current_resume": resume, "collected_facts": {}, "workflow_logs": []})

    assert result["current_resume"] == resume
    assert result["parsed_resume_changes"] == []
    assert result["workflow_logs"][-1]["message_key"] == "workflow.log.existing_resume_parser.skipped"
    assert result["workflow_logs"][-1]["details"] == []


def test_existing_resume_parser_handles_real_chinese_sections_and_avoids_date_as_phone():
    resume = get_default_resume_data()
    agent = ExistingResumeParserAgent()

    result = agent.run(
        {
            "current_resume": resume,
            "collected_facts": {
                "uploaded_resume_context": {
                    "text": """
张三
Python 后端开发工程师
zhangsan@example.com

项目经历
ResumeMaker | 后端开发 | 2025.01-2025.03
- 使用 Python、Streamlit 和 Playwright 构建简历生成流程
- 支持 JD 输入、Markdown 导出和自动化测试

教育经历
清华大学 本科 计算机科学 2020.09-2024.06

自我评价
具备 Python 后端开发经验，重视工程质量。
能够根据 JD 快速梳理简历重点并落地交付。
"""
                }
            },
            "workflow_logs": [],
        }
    )

    basics = result["current_resume"]["basics"]
    project_module = next(module for module in result["current_resume"]["modules"] if module["type"] == "projects")
    education_module = next(module for module in result["current_resume"]["modules"] if module["type"] == "education")
    self_eval_module = next(
        module for module in result["current_resume"]["modules"] if module["type"] == "selfEvaluation"
    )

    assert basics["name"] == "张三"
    assert basics["headline"] == "Python 后端开发工程师"
    assert basics["email"] == "zhangsan@example.com"
    assert basics["phone"] == ""
    project = project_module["content"]["items"][0]
    assert project["name"] == "ResumeMaker"
    assert project["role"] == "后端开发"
    assert project["startDate"] == "2025.01"
    assert project["endDate"] == "2025.03"
    assert "Streamlit" in project["description"]
    assert project["highlights"] == ["支持 JD 输入、Markdown 导出和自动化测试"]
    education = education_module["content"]["items"][0]
    assert education["school"] == "清华大学"
    assert education["degree"] == "本科"
    assert education["major"] == "计算机科学"
    assert education["startDate"] == "2020.09"
    assert education["endDate"] == "2024.06"
    assert self_eval_module["content"]["items"] == [
        "具备 Python 后端开发经验，重视工程质量。",
        "能够根据 JD 快速梳理简历重点并落地交付。",
    ]
    assert "basics.phone" not in result["parsed_resume_changes"]
    assert "projects+=1" in result["parsed_resume_changes"]
    assert "education+=1" in result["parsed_resume_changes"]
    assert "selfEvaluation+=2" in result["parsed_resume_changes"]


def test_existing_resume_parser_keeps_project_detail_lines_under_three_projects():
    resume = get_default_resume_data()
    agent = ExistingResumeParserAgent()
    resume_text = """
项目经历
TinyWebServer – 简单 HTTP 服务器（C++ 后端） 2026.01-2026.04
线程池：基于 mutex + condition_variable 的生产者-消费者模型，支持任务提交与异步结果获取。
并发控制：使用 std::atomic CAS 原子操作保证连接状态安全，避免死锁。
网络模型：epoll ET 边缘触发 + 非阻塞 I/O。
工程实践：RAII 管理资源；双缓冲异步日志；HTTP 请求解析与响应构造。
性能测试：wrk 实测 QPS 约 2.5w（8线程/1024连接）。
Chat Server - 云原生聊天（Go后端） 2025.11-2026.03
技术栈：Go + gorilla/websocket + PostgreSQL + Redis + Docker Compose。
核心功能：用户注册登录（JWT 鉴权）、WebSocket 长连接、单聊消息实时投递。
跨实例支持：Redis 维护在线状态 + Pub/Sub 实现多实例消息广播。
离线消息：PostgreSQL 存储离线消息，上线后自动拉取。
部署：编写 Docker Compose 编排服务及依赖组件，学习云服务器部署流程。
基于 Multi\x11Agent 的微服务故障诊断系统（AIInfra开发） 2025.11-2026.06
设计多智能体协作协议，自主编排 ReAct+RAG 工作流。
通过超时控制、任务状态持久化与结构化日志，提升了系统的容错能力和可观测性。
"""

    result = agent.run(
        {
            "current_resume": resume,
            "collected_facts": {"uploaded_resume_context": {"text": resume_text}},
            "workflow_logs": [],
        }
    )

    project_module = next(module for module in result["current_resume"]["modules"] if module["type"] == "projects")
    projects = project_module["content"]["items"]

    assert [project["name"] for project in projects] == [
        "TinyWebServer",
        "Chat Server",
        "基于 Multi-Agent 的微服务故障诊断系统（AIInfra开发）",
    ]
    assert projects[0]["description"].startswith("线程池：")
    assert len(projects[0]["highlights"]) == 4
    assert projects[1]["description"].startswith("技术栈：")
    assert len(projects[1]["highlights"]) == 4
    assert projects[2]["role"] == "AIInfra开发"
    assert projects[2]["description"].startswith("设计多智能体协作协议")
    assert "projects+=3" in result["parsed_resume_changes"]


def test_existing_resume_parser_joins_pdf_wrapped_self_evaluation_line():
    resume = get_default_resume_data()
    agent = ExistingResumeParserAgent()

    result = agent.run(
        {
            "current_resume": resume,
            "collected_facts": {
                "uploaded_resume_context": {
                    "text": """
自我评价
善用ai,亲手实现多智能体编排，熟悉当前ai协作范式如Multi Agent+RAG+React和SDD驱动的Harness Engineerin
g方法。
抗压能力强，认同终身学习。
"""
                }
            },
            "workflow_logs": [],
        }
    )

    self_eval_module = next(
        module for module in result["current_resume"]["modules"] if module["type"] == "selfEvaluation"
    )
    items = self_eval_module["content"]["items"]

    assert items[0].endswith("Harness Engineering方法。")
    assert "g方法。" not in items
    assert items[1] == "抗压能力强，认同终身学习。"


def test_existing_resume_parser_can_create_structured_items_from_uploaded_resume_sections():
    resume = get_default_resume_data()
    agent = ExistingResumeParserAgent()

    result = agent.run(
        {
            "current_resume": resume,
            "collected_facts": {
                "uploaded_resume_context": {
                    "text": """
项目经历
ResumeMaker  后端开发  2025.01-2025.03
- 使用 Python、Streamlit 和 Playwright 构建简历生成与预览流程
- 支持 JD 输入、Markdown 导出和自动化测试

自我评价
具备 Python 后端开发经验，重视工程质量和测试验证。
能够根据 JD 快速梳理简历重点并落地交付。
"""
                }
            },
            "workflow_logs": [],
        }
    )

    project_module = next(module for module in result["current_resume"]["modules"] if module["type"] == "projects")
    self_eval_module = next(
        module for module in result["current_resume"]["modules"] if module["type"] == "selfEvaluation"
    )
    project = project_module["content"]["items"][0]
    assert project["name"] == "ResumeMaker"
    assert project["role"] == "后端开发"
    assert project["startDate"] == "2025.01"
    assert project["endDate"] == "2025.03"
    assert "Streamlit" in project["description"]
    assert project["highlights"] == ["支持 JD 输入、Markdown 导出和自动化测试"]
    assert self_eval_module["content"]["items"] == [
        "具备 Python 后端开发经验，重视工程质量和测试验证。",
        "能够根据 JD 快速梳理简历重点并落地交付。",
    ]
    assert "projects+=1" in result["parsed_resume_changes"]
    assert "selfEvaluation+=2" in result["parsed_resume_changes"]


def test_workflow_runs_existing_resume_parser_before_writer(monkeypatch):
    monkeypatch.setattr("workflow.graph.create_llm", lambda: (_ for _ in ()).throw(ValueError("missing api key")))
    workflow = ResumeWorkflow(config={"workflow": {"fallback_to_local_draft": False}, "prompts": {}, "resume": {}})
    resume = get_default_resume_data()

    result = workflow.run(
        workflow.build_initial_state(
            jd_text="",
            current_resume=resume,
            uploaded_files=[
                {
                    "name": "resume.md",
                    "type": "existing_resume",
                    "raw_text": "candidate@example.com 18888888888 Python FastAPI",
                }
            ],
        )
    )

    agents = [entry["agent"] for entry in result["workflow_logs"]]
    final_resume = workflow.get_final_resume(result)
    skills_module = next(module for module in final_resume["modules"] if module["type"] == "skills")
    assert agents == ["info_collector", "existing_resume_parser", "resume_writer"]
    assert final_resume["basics"]["email"] == "candidate@example.com"
    assert final_resume["basics"]["phone"] == "18888888888"
    assert skills_module["content"]["items"] == ["Python", "FastAPI"]


def test_service_returns_workflow_metadata_and_parsed_resume_changes(monkeypatch):
    monkeypatch.setattr("workflow.graph.create_llm", lambda: (_ for _ in ()).throw(ValueError("missing api key")))
    resume = get_default_resume_data()

    result = run_resume_workflow(
        jd_text="",
        current_resume=resume,
        uploaded_files=[
            {
                "name": "resume.md",
                "type": "existing_resume",
                "raw_text": "项目经历\nResumeMaker 后端开发 2025.01-2025.03\n- 使用 Python 构建简历生成流程",
            }
        ],
        style_params={},
    )

    project_module = next(module for module in result["final_resume"]["modules"] if module["type"] == "projects")
    assert project_module["content"]["items"][0]["name"] == "ResumeMaker"
    assert project_module["content"]["items"][0]["role"] == "后端开发"
    assert result["workflow_logs"]
    assert any(entry["agent"] == "existing_resume_parser" for entry in result["workflow_logs"])
    assert result["parsed_resume_changes"]
    assert result["conditional_suggestions"] == []


def test_import_existing_resume_service_parses_without_writer(monkeypatch):
    monkeypatch.setattr("core.service.create_llm", lambda: (_ for _ in ()).throw(ValueError("missing api key")))
    resume = get_default_resume_data()

    result = import_existing_resume(
        current_resume=resume,
        uploaded_files=[
            {
                "name": "resume.md",
                "type": "existing_resume",
                "raw_text": (
                    "候选人甲\n"
                    "实习生（base深圳）\n"
                    "21岁 | 男 | 示例城市\n"
                    "candidate@example.com +86 138 0000 0000 https://github.com/example-user\n"
                    "项目经历\n"
                    "TinyWebServer – 简单 HTTP 服务器（C++ 后端） 2026.01-2026.04\n"
                    "线程池：基于 mutex + condition_variable 的生产者-消费者模型。\n"
                ),
            }
        ],
    )

    agents = [entry["agent"] for entry in result["workflow_logs"]]
    basics = result["final_resume"]["basics"]
    projects = next(module for module in result["final_resume"]["modules"] if module["type"] == "projects")

    assert agents == ["info_collector", "existing_resume_parser"]
    assert basics["name"] == "候选人甲"
    assert basics["city"] == "示例城市"
    assert basics["phone"] == "+86 138 0000 0000"
    assert projects["content"]["items"][0]["name"] == "TinyWebServer"
    assert result["parsed_resume_changes"]


def test_import_existing_resume_replaces_existing_content_with_uploaded_resume(monkeypatch):
    monkeypatch.setattr("core.service.create_llm", lambda: (_ for _ in ()).throw(ValueError("missing api key")))
    resume = get_default_resume_data()
    resume["basics"]["name"] = "Old Name"
    resume["basics"]["photo_path"] = "data/uploads/profile_photo.jpeg"
    resume["style"]["theme_color"] = "#123456"
    project_module = next(module for module in resume["modules"] if module["type"] == "projects")
    project_module["content"]["items"] = [
        {
            "name": "Old Project",
            "role": "Old Role",
            "startDate": "2020.01",
            "endDate": "2020.02",
            "description": "Old description",
            "highlights": ["Old highlight"],
        }
    ]

    result = import_existing_resume(
        current_resume=resume,
        uploaded_files=[
            {
                "name": "resume.md",
                "type": "existing_resume",
                "raw_text": (
                    "New Candidate\n"
                    "Python 后端开发工程师\n"
                    "new@example.com\n"
                    "项目经历\n"
                    "New Project - 后端开发 2024.01-2024.03\n"
                    "负责接口设计与数据库建模。\n"
                ),
            }
        ],
    )

    final_resume = result["final_resume"]
    projects = next(module for module in final_resume["modules"] if module["type"] == "projects")

    assert final_resume["basics"]["name"] == "New Candidate"
    assert final_resume["basics"]["photo_path"].endswith("data\\uploads\\profile_photo.jpeg") or final_resume["basics"][
        "photo_path"
    ].endswith("data/uploads/profile_photo.jpeg")
    assert final_resume["style"]["theme_color"] == "#123456"
    assert projects["content"]["items"][0]["name"] == "New Project"
    assert "Old Project" not in str(projects["content"]["items"])


def test_workflow_without_llm_keeps_local_fallback_behavior():
    workflow = ResumeWorkflow()
    resume = get_default_resume_data()
    resume["basics"]["name"] = "Candidate"
    resume["basics"]["headline"] = "Python 后端开发"
    initial_state = workflow.build_initial_state(
        jd_text="",
        current_resume=resume,
        uploaded_files=[
            {
                "name": "resume.md",
                "type": "existing_resume",
                "path": "",
                "raw_text": "Existing resume text should not break local fallback.",
            }
        ],
        style_params={},
    )

    result = workflow.run(initial_state)

    final_resume = workflow.get_final_resume(result)
    skills_module = next(module for module in final_resume["modules"] if module["type"] == "skills")
    assert skills_module["content"]["items"]
    assert result["error"]
    assert result["collected_facts"]["uploaded_resume_context"]["text"]


def test_missing_api_key_path_still_returns_user_safe_local_resume(monkeypatch):
    monkeypatch.setattr("workflow.graph.create_llm", lambda: (_ for _ in ()).throw(ValueError("missing api key")))

    workflow = ResumeWorkflow()
    resume = get_default_resume_data()
    resume["basics"]["name"] = "Novice User"
    resume["basics"]["headline"] = "Python backend engineer"

    result = workflow.run(
        workflow.build_initial_state(
            jd_text="Need FastAPI, MySQL, and API delivery.",
            current_resume=resume,
            uploaded_files=[{"name": "resume.md", "type": "existing_resume", "raw_text": "Built an API demo."}],
            style_params={"template": "modern_blue"},
        )
    )

    final_resume = workflow.get_final_resume(result)
    skills_module = next(module for module in final_resume["modules"] if module["type"] == "skills")
    self_eval_module = next(module for module in final_resume["modules"] if module["type"] == "selfEvaluation")

    assert result["error"]
    assert result["llm_error"] == "missing api key"
    assert any("missing api key" in str(detail) for log in result["workflow_logs"] for detail in log.get("details", []))
    assert final_resume["basics"]["name"] == "Novice User"
    assert skills_module["content"]["items"]
    assert self_eval_module["content"]["items"]
    assert result["collected_facts"]["has_jd"] is True

