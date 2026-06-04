from __future__ import annotations

import re
from copy import deepcopy
from typing import Any, Dict, List, Match, Set

from agents.base_agent import BaseResumeAgent, WorkflowState
from core.data import ensure_resume_shape
from core.llm import extract_json_block


MAX_PARSE_TEXT_CHARS = 50000

MODULE_TYPES = {
    "education",
    "skills",
    "projects",
    "companyExperience",
    "campusExperience",
    "selfEvaluation",
}

ITEM_KEYS_BY_TYPE = {
    "education": ["school", "degree", "major", "startDate", "endDate", "details"],
    "projects": ["name", "role", "startDate", "endDate", "description", "highlights"],
    "companyExperience": ["company", "role", "startDate", "endDate", "description", "highlights"],
    "campusExperience": ["organization", "role", "startDate", "endDate", "description", "highlights"],
}

TITLE_KEY_BY_TYPE = {
    "education": "school",
    "projects": "name",
    "companyExperience": "company",
    "campusExperience": "organization",
}

SECTION_ALIASES = {
    "education": {"教育经历", "教育背景", "学历背景", "education", "academic background"},
    "skills": {"技能", "专业技能", "技能栈", "技术栈", "技术能力", "skills", "technical skills"},
    "projects": {"项目经历", "项目经验", "项目实践", "projects", "project experience"},
    "companyExperience": {"工作经历", "工作经验", "实习经历", "实习经验", "work experience", "internship"},
    "campusExperience": {"校园经历", "社团经历", "学生工作", "活动经历", "campus experience", "activities"},
    "selfEvaluation": {"自我评价", "个人总结", "个人简介", "个人优势", "summary", "profile"},
}

INLINE_DETAIL_LABELS = {
    "技术栈",
    "核心功能",
    "跨实例支持",
    "离线消息",
    "部署",
    "线程池",
    "并发控制",
    "网络模型",
    "工程实践",
    "性能测试",
    "主修",
    "职责",
    "成果",
    "亮点",
}

SKILL_CANDIDATES = [
    "C++",
    "Golang",
    "Go",
    "Python",
    "FastAPI",
    "Flask",
    "Django",
    "Java",
    "Spring Boot",
    "MySQL",
    "PostgreSQL",
    "Redis",
    "Docker",
    "Kubernetes",
    "Git",
    "JavaScript",
    "TypeScript",
    "React",
    "Vue",
    "HTML",
    "CSS",
    "Linux",
    "RESTful API",
    "Node.js",
    "Express",
    "Next.js",
    "Tailwind CSS",
    "MongoDB",
    "SQLite",
    "SQL",
    "Pandas",
    "NumPy",
    "PyTorch",
    "TensorFlow",
    "OpenAI",
    "LangChain",
    "LangGraph",
    "Playwright",
    "CI/CD",
    "Nginx",
    "AWS",
    "Azure",
    "GCP",
]

RESUME_PARSE_OUTPUT_SCHEMA = """{
  "basics": {
    "name": "",
    "headline": "",
    "age": "",
    "gender": "",
    "city": "",
    "phone": "",
    "email": "",
    "website": "",
    "portfolio": ""
  },
  "modules": [
    {"type": "education", "content": {"items": [{"school": "", "degree": "", "major": "", "startDate": "", "endDate": "", "details": ""}]}},
    {"type": "skills", "content": {"items": []}},
    {"type": "projects", "content": {"items": [{"name": "", "role": "", "startDate": "", "endDate": "", "description": "", "highlights": []}]}},
    {"type": "companyExperience", "content": {"items": [{"company": "", "role": "", "startDate": "", "endDate": "", "description": "", "highlights": []}]}},
    {"type": "campusExperience", "content": {"items": [{"organization": "", "role": "", "startDate": "", "endDate": "", "description": "", "highlights": []}]}},
    {"type": "selfEvaluation", "content": {"items": []}}
  ]
}"""

RESUME_PARSE_PROMPT_CONTRACT = """You are ExistingResumeParserAgent, a factual resume import agent.

Return one valid JSON object only. Top-level keys must be exactly basics and modules.
Do not output style, id, title, visible, order, photo_path, runtime, exports, inputs, logs, confidence, or any extra key.
Do not invent, polish, translate names, or infer missing facts. Keep original language and wording when practical.
Use empty strings for unknown scalar fields and empty arrays for unknown list fields.
Do not treat project dates, education dates, QQ numbers, IDs, or email prefixes as phone numbers.

Project boundary contract:
- A project item starts at a line that contains a project name plus a date range.
- All following technical detail lines belong to that same project until the next project-name-plus-date-range line.
- Do not turn detail labels such as 技术栈, 核心功能, 线程池, 并发控制, 网络模型, 工程实践, 性能测试, 部署, 离线消息 into new modules or new projects.
- Put the project name in name, responsibility/title in role, summary in description, and concrete details in highlights.

JSON contract:
{schema}
"""

DATE_RANGE_RE = re.compile(
    r"(?P<start>(?:19|20)\d{2}[./-]?(?:0?[1-9]|1[0-2])?)\s*(?:-|–|—|~|至|到)\s*"
    r"(?P<end>(?:19|20)\d{2}[./-]?(?:0?[1-9]|1[0-2])?|至今|现在|present|current)",
    flags=re.IGNORECASE,
)
EMAIL_RE = re.compile(r"(?i)\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b")
PHONE_RE = re.compile(r"(?<!\w)(?:\+?\d[\d\s().-]{7,}\d)(?!\w)")
URL_RE = re.compile(r"https?://[^\s)>\]]+")
BULLET_RE = re.compile(r"^(?:[-*•·●]|[0-9]+[.)、])\s+")
SPLIT_RE = re.compile(r"\s{2,}|[|｜/／,，;；、]")


class ExistingResumeParserAgent(BaseResumeAgent):
    """Import uploaded resume text into the in-memory resume JSON."""

    def __init__(self, llm=None, config: Dict[str, Any] | None = None) -> None:
        super().__init__(name="existing_resume_parser", llm=llm, config=config)

    def run(self, state: WorkflowState) -> WorkflowState:
        next_state = deepcopy(state)
        resume = ensure_resume_shape(next_state.get("current_resume", {}))
        source_text = self._collect_source_text(next_state)
        changes: List[str] = []

        if source_text:
            if self.llm is not None:
                try:
                    changes.extend(
                        self._merge_extracted_resume(resume, self._extract_resume_with_llm(source_text), "llm.")
                    )
                except Exception as exc:
                    next_state["existing_resume_parser_error"] = str(exc)
            changes.extend(self._merge_extracted_resume(resume, self._parse_with_rules(source_text)))

        next_state["current_resume"] = ensure_resume_shape(resume)
        next_state["parsed_resume"] = next_state["current_resume"]
        next_state["parsed_resume_changes"] = changes
        skipped = not bool(source_text.strip())
        next_state["workflow_logs"] = [
            *(next_state.get("workflow_logs", []) or []),
            {
                "agent": self.name,
                "message_key": (
                    "workflow.log.existing_resume_parser.skipped"
                    if skipped
                    else "workflow.log.existing_resume_parser"
                ),
                "message_args": {"change_count": len(changes)},
                "message": "Parsed uploaded existing resume into current resume JSON.",
                "details": [] if skipped else (changes or ["no high-confidence resume facts parsed"]),
            },
        ]
        return next_state

    @staticmethod
    def _build_llm_parse_prompt(source_text: str) -> str:
        return (
            RESUME_PARSE_PROMPT_CONTRACT.format(schema=RESUME_PARSE_OUTPUT_SCHEMA).strip()
            + "\n\nUploaded resume text:\n"
            + source_text[:MAX_PARSE_TEXT_CHARS]
        )

    def _extract_resume_with_llm(self, source_text: str) -> Dict[str, Any]:
        response = self.require_llm().invoke(self._build_llm_parse_prompt(source_text))
        raw_content = response.content if hasattr(response, "content") else response
        return extract_json_block(raw_content if isinstance(raw_content, str) else str(raw_content))

    @staticmethod
    def _collect_source_text(state: WorkflowState) -> str:
        text_parts: List[str] = []
        facts = state.get("collected_facts", {})
        has_collected_context = False
        if isinstance(facts, dict):
            context = facts.get("uploaded_resume_context", {})
            if isinstance(context, dict):
                context_text = str(context.get("text", "") or "")
                if context_text.strip():
                    text_parts.append(context_text)
                    has_collected_context = True

        if has_collected_context:
            return "\n".join(part.strip() for part in text_parts if part and part.strip())[:MAX_PARSE_TEXT_CHARS]

        for file_meta in state.get("uploaded_files", []) or []:
            if not isinstance(file_meta, dict) or str(file_meta.get("type", "") or "") != "existing_resume":
                continue
            text_parts.append(str(file_meta.get("raw_text", "") or ""))
            personal_info = (file_meta.get("metadata", {}) or {}).get("personal_info", {})
            if isinstance(personal_info, dict):
                text_parts.extend(str(item) for item in personal_info.get("emails", []) or [])
                text_parts.extend(str(item) for item in personal_info.get("phones", []) or [])
                text_parts.extend(str(item) for item in personal_info.get("urls", []) or [])

        return "\n".join(part.strip() for part in text_parts if part and part.strip())[:MAX_PARSE_TEXT_CHARS]

    def _parse_with_rules(self, text: str) -> Dict[str, Any]:
        lines = self._join_pdf_wrapped_lines([self._clean_line(line) for line in text.splitlines()])
        lines = [line for line in lines if line]
        sections = self._split_sections(lines)

        return {
            "basics": self._extract_basics(lines, text),
            "modules": [
                {"type": "education", "content": {"items": self._parse_education(sections.get("education", []))}},
                {"type": "skills", "content": {"items": self._extract_skills(text)}},
                {"type": "projects", "content": {"items": self._parse_experience(sections.get("projects", []), "name")}},
                {
                    "type": "companyExperience",
                    "content": {"items": self._parse_experience(sections.get("companyExperience", []), "company")},
                },
                {
                    "type": "campusExperience",
                    "content": {"items": self._parse_experience(sections.get("campusExperience", []), "organization")},
                },
                {"type": "selfEvaluation", "content": {"items": self._parse_self_evaluation(sections.get("selfEvaluation", []))}},
            ],
        }

    @classmethod
    def _join_pdf_wrapped_lines(cls, lines: List[str]) -> List[str]:
        joined: List[str] = []
        for line in lines:
            if not line:
                continue
            if joined and cls._should_join_wrapped_line(joined[-1], line):
                joined[-1] = joined[-1] + line
            else:
                joined.append(line)
        return joined

    @staticmethod
    def _should_join_wrapped_line(previous: str, current: str) -> bool:
        if len(current) > 20:
            return False
        if re.search(r"[:：。！？；;]$", previous):
            return False
        return bool(re.search(r"[A-Za-z]$", previous) and re.match(r"^[A-Za-z]{1,12}[\u4e00-\u9fff]", current))

    @staticmethod
    def _parse_self_evaluation(lines: List[str]) -> List[str]:
        return [line for line in lines if line.strip()][:3]

    @classmethod
    def _split_sections(cls, lines: List[str]) -> Dict[str, List[str]]:
        sections: Dict[str, List[str]] = {key: [] for key in SECTION_ALIASES}
        current = ""
        for line in lines:
            heading = cls._match_section(line)
            if heading and current and cls._is_inline_detail(line):
                heading = ""
            if heading:
                current = heading
                remainder = cls._strip_section_prefix(line)
                if remainder:
                    sections[current].append(remainder)
                continue
            if current:
                sections[current].append(line)
        return sections

    @staticmethod
    def _match_section(line: str) -> str:
        normalized = line.strip(" #：:").lower()
        for section, aliases in SECTION_ALIASES.items():
            for alias in aliases:
                alias_lower = alias.lower()
                if normalized == alias_lower or normalized.startswith(f"{alias_lower}:") or normalized.startswith(f"{alias_lower}："):
                    return section
        return ""

    @staticmethod
    def _strip_section_prefix(line: str) -> str:
        for aliases in SECTION_ALIASES.values():
            for alias in aliases:
                match = re.match(rf"^\s*{re.escape(alias)}\s*[:：]\s*(.+)$", line, flags=re.IGNORECASE)
                if match:
                    return match.group(1).strip()
        return ""

    @staticmethod
    def _is_inline_detail(line: str) -> bool:
        label = re.split(r"[:：]", line, maxsplit=1)[0].strip()
        return bool(label in INLINE_DETAIL_LABELS and len(line) > len(label) + 1)

    @classmethod
    def _extract_basics(cls, lines: List[str], text: str) -> Dict[str, str]:
        emails = EMAIL_RE.findall(text)
        phones = [match.group(0).strip() for match in PHONE_RE.finditer(text) if cls._is_phone(text, match)]
        urls = [url.rstrip(".,;。；") for url in URL_RE.findall(text)]
        github_urls = [url for url in urls if "github.com" in url.lower()]
        non_github_urls = [url for url in urls if "github.com" not in url.lower()]

        return {
            "name": cls._first_name_like_line(lines),
            "headline": cls._first_headline_like_line(lines),
            "age": cls._extract_first(r"(?<!\d)(\d{2})\s*岁", text),
            "gender": cls._extract_first(r"(男|女)", text),
            "city": cls._extract_city(lines),
            "phone": phones[0] if phones else "",
            "email": emails[0].strip() if emails else "",
            "website": github_urls[0] if github_urls else (urls[0] if urls else ""),
            "portfolio": non_github_urls[0] if non_github_urls else "",
        }

    @staticmethod
    def _extract_first(pattern: str, text: str) -> str:
        match = re.search(pattern, text)
        return match.group(1).strip() if match else ""

    @classmethod
    def _first_name_like_line(cls, lines: List[str]) -> str:
        for line in lines[:10]:
            if cls._match_section(line) or EMAIL_RE.search(line) or PHONE_RE.search(line) or URL_RE.search(line):
                continue
            if re.search(r"\d|[,，|｜:：/]", line):
                continue
            if any(word in line for word in ("工程师", "开发", "实习", "经理", "运营", "产品", "设计")):
                continue
            if 2 <= len(re.findall(r"[\u4e00-\u9fff]", line)) <= 6 and len(line) <= 12:
                return line
            if re.fullmatch(r"[A-Za-z][A-Za-z .'-]{1,58}", line):
                return line
        return ""

    @classmethod
    def _first_headline_like_line(cls, lines: List[str]) -> str:
        for line in lines[:15]:
            if cls._match_section(line) or EMAIL_RE.search(line) or PHONE_RE.search(line) or URL_RE.search(line):
                continue
            if any(word in line for word in ("工程师", "开发", "实习", "后端", "前端", "算法", "运营", "产品")):
                return re.split(r"[|｜,，]", line)[0].strip()
        return ""

    @staticmethod
    def _extract_city(lines: List[str]) -> str:
        for line in lines[:8]:
            if "|" not in line and "｜" not in line:
                continue
            parts = [part.strip() for part in re.split(r"[|｜]", line) if part.strip()]
            for part in parts:
                if re.search(r"省|市|北京|上海|深圳|广州|惠州|杭州|成都|武汉|西安", part) and not re.search(
                    r"实习|base|岗位|工程师|开发", part,
                    flags=re.IGNORECASE,
                ):
                    return part
        return ""

    @staticmethod
    def _is_phone(text: str, match: Match[str]) -> bool:
        value = match.group(0)
        compact = re.sub(r"\D", "", value)
        if len(compact) < 10 or len(compact) > 15:
            return False
        if DATE_RANGE_RE.search(value) or len(re.findall(r"(?:19|20)\d{2}", value)) >= 2:
            return False
        before = text[max(0, match.start() - 1) : match.start()]
        after = text[match.end() : match.end() + 1]
        return before not in {"@", "."} and after not in {"@", "."}

    @staticmethod
    def _extract_skills(text: str) -> List[str]:
        found: List[str] = []
        seen: Set[str] = set()
        for skill in SKILL_CANDIDATES:
            if re.search(rf"(?<![A-Za-z0-9+#]){re.escape(skill)}(?![A-Za-z0-9+#])", text, re.IGNORECASE):
                key = skill.lower()
                if key not in seen:
                    found.append(skill)
                    seen.add(key)
        return found

    @classmethod
    def _parse_education(cls, lines: List[str]) -> List[Dict[str, Any]]:
        items: List[Dict[str, Any]] = []
        current: Dict[str, Any] | None = None
        pending_school = ""

        for line in lines:
            start, end = cls._date_range(line)
            if not start:
                if current:
                    detail = cls._strip_detail_label(line)
                    current["details"] = "；".join(part for part in [current.get("details", ""), detail] if part)[:240]
                elif not pending_school:
                    pending_school = cls._strip_detail_label(line)
                continue

            rest_line = DATE_RANGE_RE.sub("", line).strip(" :：;；|-")
            parts = cls._split_parts(rest_line)
            if pending_school:
                school, rest = pending_school, parts
                pending_school = ""
            else:
                school, rest = (parts[0] if parts else rest_line), parts[1:]
            if not school:
                continue

            degree = next((part for part in rest if cls._is_degree(part)), "")
            major = next((part for part in rest if part != degree), "")
            details = [part for part in rest if part not in {degree, major}]
            current = {
                "school": school[:80],
                "degree": degree[:40],
                "major": major[:60],
                "startDate": start,
                "endDate": end,
                "details": "；".join(details)[:240],
            }
            items.append(current)
        return items[:5]

    @classmethod
    def _parse_experience(cls, lines: List[str], title_key: str) -> List[Dict[str, Any]]:
        items: List[Dict[str, Any]] = []
        current: Dict[str, Any] | None = None

        for line in lines:
            if cls._starts_experience_item(line, current):
                if current:
                    items.append(cls._finish_experience(current, title_key))
                current = cls._new_experience(line, title_key)
                continue
            if current:
                detail = cls._strip_bullet(line)
                if detail:
                    current.setdefault("highlights", []).append(detail[:260])

        if current:
            items.append(cls._finish_experience(current, title_key))
        return [item for item in items if str(item.get(title_key, "")).strip()][:5]

    @classmethod
    def _starts_experience_item(cls, line: str, current: Dict[str, Any] | None) -> bool:
        if current is None:
            return True
        if not DATE_RANGE_RE.search(line):
            return False
        return True

    @classmethod
    def _new_experience(cls, line: str, title_key: str) -> Dict[str, Any]:
        start, end = cls._date_range(line)
        header = DATE_RANGE_RE.sub("", line).strip(" :：;；|-")
        parts = cls._split_header(header)
        title = parts[0] if parts else header
        role = parts[1] if len(parts) > 1 else cls._parenthetical_role(title)
        return {
            title_key: title[:100],
            "role": role[:80],
            "startDate": start,
            "endDate": end,
            "description": "；".join(parts[2:])[:500] if len(parts) > 2 else "",
            "highlights": [],
        }

    @staticmethod
    def _finish_experience(item: Dict[str, Any], title_key: str) -> Dict[str, Any]:
        highlights = [str(value).strip() for value in item.get("highlights", []) if str(value).strip()]
        if not item.get("description") and highlights:
            item["description"] = highlights[0]
            highlights = highlights[1:]
        item["highlights"] = highlights[:6]
        item[title_key] = str(item.get(title_key, "") or "").strip()
        return item

    def _merge_extracted_resume(
        self,
        resume: Dict[str, Any],
        extracted: Dict[str, Any],
        prefix: str = "",
    ) -> List[str]:
        if not isinstance(extracted, dict):
            return []
        changes: List[str] = []
        changes.extend(self._merge_basics(resume, extracted.get("basics", {}), prefix))
        modules = extracted.get("modules", [])
        if isinstance(modules, list):
            for module in modules:
                if not isinstance(module, dict):
                    continue
                change = self._merge_module(
                    resume,
                    str(module.get("type", "") or ""),
                    module.get("content", {}) if isinstance(module.get("content"), dict) else {},
                    prefix,
                )
                if change:
                    changes.append(change)
        return changes

    def _merge_basics(self, resume: Dict[str, Any], basics: Any, prefix: str = "") -> List[str]:
        if not isinstance(basics, dict):
            return []
        target = resume.setdefault("basics", {})
        changes: List[str] = []
        for field in ["name", "headline", "age", "gender", "city", "phone", "email", "website", "portfolio"]:
            value = str(basics.get(field, "") or "").strip()
            if not value or str(target.get(field, "") or "").strip():
                continue
            if field == "email" and not EMAIL_RE.fullmatch(value):
                continue
            if field == "phone" and not self._is_phone(value, re.match(r".+", value)):  # type: ignore[arg-type]
                continue
            target[field] = value
            changes.append(f"{prefix}basics.{field}")
        return changes

    def _merge_module(self, resume: Dict[str, Any], module_type: str, content: Dict[str, Any], prefix: str = "") -> str:
        if module_type not in MODULE_TYPES:
            return ""
        target = self._find_module(resume, module_type)
        if not target:
            return ""

        if module_type in {"skills", "selfEvaluation"}:
            incoming = [str(item).strip() for item in content.get("items", []) if isinstance(item, str) and item.strip()]
            if not incoming:
                return ""
            existing = target.setdefault("content", {}).setdefault("items", [])
            if module_type == "selfEvaluation" and any(str(item).strip() for item in existing):
                return ""
            added = self._append_unique(existing, incoming)
            return f"{prefix}{module_type}+={added}" if added else ""

        incoming_items = self._sanitize_items(module_type, content.get("items", []))
        if not incoming_items:
            return ""
        target_content = target.setdefault("content", {})
        existing_items = target_content.setdefault("items", [])
        if self._has_meaningful_items(existing_items):
            filled = self._fill_blank_items(module_type, existing_items, incoming_items)
            return f"{prefix}{module_type}.filled={filled}" if filled else ""
        target_content["items"] = incoming_items[:5]
        return f"{prefix}{module_type}+={len(target_content['items'])}"

    @staticmethod
    def _append_unique(existing: List[Any], incoming: List[str]) -> int:
        seen = {str(item).strip().lower() for item in existing if str(item).strip()}
        added = 0
        for item in incoming:
            key = item.lower()
            if key in seen:
                continue
            existing.append(item)
            seen.add(key)
            added += 1
        return added

    @staticmethod
    def _sanitize_items(module_type: str, items: Any) -> List[Dict[str, Any]]:
        if module_type not in ITEM_KEYS_BY_TYPE or not isinstance(items, list):
            return []
        result: List[Dict[str, Any]] = []
        for item in items:
            if not isinstance(item, dict):
                continue
            normalized: Dict[str, Any] = {}
            for key in ITEM_KEYS_BY_TYPE[module_type]:
                if key == "highlights":
                    highlights = item.get("highlights", [])
                    normalized[key] = [
                        str(value).strip()[:260]
                        for value in highlights
                        if isinstance(value, str) and value.strip()
                    ][:6] if isinstance(highlights, list) else []
                else:
                    normalized[key] = str(item.get(key, "") or "").strip()
            if normalized.get(TITLE_KEY_BY_TYPE[module_type]):
                result.append(normalized)
        return result

    @staticmethod
    def _has_meaningful_items(items: Any) -> bool:
        if not isinstance(items, list):
            return False
        for item in items:
            if isinstance(item, dict):
                if any(isinstance(value, str) and value.strip() for value in item.values()):
                    return True
                if any(isinstance(value, list) and any(str(entry).strip() for entry in value) for value in item.values()):
                    return True
            elif str(item).strip():
                return True
        return False

    @staticmethod
    def _fill_blank_items(module_type: str, existing_items: List[Any], incoming_items: List[Dict[str, Any]]) -> int:
        title_key = TITLE_KEY_BY_TYPE[module_type]
        filled = 0
        for existing, incoming in zip(existing_items, incoming_items):
            if not isinstance(existing, dict) or str(existing.get(title_key, "") or "").strip():
                continue
            for key, value in incoming.items():
                if key in existing and not str(existing.get(key, "") or "").strip():
                    existing[key] = deepcopy(value)
            filled += 1
        return filled

    @staticmethod
    def _date_range(line: str) -> tuple[str, str]:
        match = DATE_RANGE_RE.search(line)
        if not match:
            return "", ""
        return match.group("start").replace("-", ".").replace("/", "."), match.group("end").replace("-", ".").replace("/", ".")

    @staticmethod
    def _clean_line(line: str) -> str:
        cleaned = re.sub(r"[\x00-\x08\x0b-\x1f\x7f]", "-", str(line))
        return re.sub(r"\s+", " ", cleaned.strip().strip("|")).strip()

    @staticmethod
    def _strip_bullet(line: str) -> str:
        return BULLET_RE.sub("", line).strip()

    @staticmethod
    def _strip_detail_label(line: str) -> str:
        return re.sub(r"^\s*[^:：]{1,12}[:：]\s*", "", line).strip()

    @staticmethod
    def _split_parts(value: str) -> List[str]:
        parts = [part.strip() for part in SPLIT_RE.split(value) if part.strip()]
        return parts if len(parts) > 1 else [part.strip() for part in value.split() if part.strip()]

    @staticmethod
    def _split_header(value: str) -> List[str]:
        dash_parts = [part.strip() for part in re.split(r"\s+[-–—]\s+", value, maxsplit=1) if part.strip()]
        if len(dash_parts) == 2:
            return dash_parts
        parts = [part.strip() for part in SPLIT_RE.split(value) if part.strip()]
        if len(parts) > 1:
            return parts
        role_match = re.match(r"^(.+?)\s+([^()\s]{2,12}(?:开发|运营|记者|负责人|工程师|实习生))$", value)
        if role_match:
            return [role_match.group(1).strip(), role_match.group(2).strip()]
        return [value.strip()]

    @staticmethod
    def _is_degree(value: str) -> bool:
        return any(keyword in value for keyword in ("本科", "硕士", "博士", "大专", "学士", "Master", "Bachelor", "PhD"))

    @staticmethod
    def _parenthetical_role(value: str) -> str:
        match = re.search(r"[（(]([^（）()]{2,30})[）)]", value)
        return match.group(1).strip() if match else ""

    @staticmethod
    def _find_module(resume: Dict[str, Any], module_type: str) -> Dict[str, Any] | None:
        for module in resume.get("modules", []) or []:
            if isinstance(module, dict) and str(module.get("type", "") or "") == module_type:
                return module
        return None
