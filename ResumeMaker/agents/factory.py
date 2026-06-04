from __future__ import annotations

from typing import Any, Dict, Optional, Type

from langchain_openai import ChatOpenAI

from agents.base_agent import BaseResumeAgent
from agents.existing_resume_parser import ExistingResumeParserAgent
from agents.info_collector import InfoCollectorAgent
from agents.resume_writer import ResumeWriterAgent


class AgentFactory:
    _registry: Dict[str, Type[BaseResumeAgent]] = {
        "info_collector": InfoCollectorAgent,
        "existing_resume_parser": ExistingResumeParserAgent,
        "resume_writer": ResumeWriterAgent,
    }

    @classmethod
    def create(
        cls,
        agent_type: str,
        llm: Optional[ChatOpenAI] = None,
        config: Optional[Dict[str, Any]] = None,
    ) -> BaseResumeAgent:
        if agent_type not in cls._registry:
            raise ValueError(f"未注册的智能体类型：{agent_type}")
        agent_class = cls._registry[agent_type]
        return agent_class(llm=llm, config=config)

    @classmethod
    def register(cls, agent_type: str, agent_class: Type[BaseResumeAgent]) -> None:
        cls._registry[agent_type] = agent_class

    @classmethod
    def available_agents(cls) -> Dict[str, Type[BaseResumeAgent]]:
        return dict(cls._registry)
