from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict, Optional

from langchain_openai import ChatOpenAI


WorkflowState = Dict[str, Any]


class BaseResumeAgent(ABC):
    def __init__(self, name: str, llm: Optional[ChatOpenAI] = None, config: Optional[Dict[str, Any]] = None) -> None:
        self.name = name
        self.llm = llm
        self.config = config or {}

    @abstractmethod
    def run(self, state: WorkflowState) -> WorkflowState:
        raise NotImplementedError

    def require_llm(self) -> ChatOpenAI:
        if self.llm is None:
            raise ValueError(f"Agent '{self.name}' 运行需要可用的 LLM，但当前未配置。")
        return self.llm
