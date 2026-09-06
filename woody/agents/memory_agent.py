"""
Memory Agent — Persistent memory, facts, notes, and session history management.

Handles storing user facts, saving notes, recalling information, and searching
past episodic sessions.
"""
from __future__ import annotations

from typing import Any

from woody.agents.base_agent import AgentResult, BaseAgent
from woody.memory.semantic import SemanticMemory
from woody.memory.episodic import EpisodicMemory
from woody.tools.builtin.memory_tools import (
    remember_fact,
    save_note,
    remember_text,
    recall,
    forget,
    search_history,
)
from woody.utils.logging import get_logger

log = get_logger(__name__)


class MemoryAgent(BaseAgent):
    AGENT_NAME = "memory_agent"
    ALLOWED_ACTIONS = {
        "remember",
        "remember_fact",
        "save_note",
        "recall",
        "forget",
        "search_history",
        "list_memories",
    }

    def __init__(
        self,
        semantic_memory: SemanticMemory | None = None,
        episodic_memory: EpisodicMemory | None = None,
        confirm_callback: Any | None = None,
    ) -> None:
        super().__init__(max_retries=1, confirm_callback=confirm_callback)
        self._semantic = semantic_memory
        self._episodic = episodic_memory

    async def execute_action(self, action: str, params: dict, context: dict) -> AgentResult:
        handlers = {
            "remember": self._remember,
            "remember_fact": self._remember_fact,
            "save_note": self._save_note,
            "recall": self._recall,
            "list_memories": self._recall,
            "forget": self._forget,
            "search_history": self._search_history,
        }
        handler = handlers.get(action)
        if not handler:
            return AgentResult(success=False, output=None, error=f"Unknown memory action: {action}")
        return await handler(params, context)

    async def _remember(self, params: dict, context: dict) -> AgentResult:
        key = params.get("key")
        value = params.get("value")
        text = params.get("text") or params.get("content") or context.get("user_request") or ""

        if key and value:
            res = remember_fact(key=key, value=value, semantic=self._semantic)
            return AgentResult(success=True, output=res)
        
        # If text is provided, store as natural language memory
        res = remember_text(text=text, semantic=self._semantic)
        return AgentResult(success=True, output=res)

    async def _remember_fact(self, params: dict, context: dict) -> AgentResult:
        key = params.get("key", "")
        value = params.get("value", "")
        if not key or not value:
            # Try to parse from text
            text = params.get("text") or context.get("user_request") or ""
            res = remember_text(text=text, semantic=self._semantic)
            return AgentResult(success=True, output=res)

        res = remember_fact(key=key, value=value, semantic=self._semantic)
        return AgentResult(success=True, output=res)

    async def _save_note(self, params: dict, context: dict) -> AgentResult:
        text = params.get("text") or params.get("note") or params.get("content") or ""
        if not text:
            return AgentResult(success=False, output=None, error="No note text provided.")
        res = save_note(text=text, semantic=self._semantic)
        return AgentResult(success=True, output=res)

    async def _recall(self, params: dict, context: dict) -> AgentResult:
        query = params.get("query") or params.get("key") or ""
        res = recall(query=query, semantic=self._semantic)
        return AgentResult(success=True, output=res)

    async def _forget(self, params: dict, context: dict) -> AgentResult:
        target = params.get("target") or params.get("key") or params.get("text") or ""
        if not target:
            return AgentResult(success=False, output=None, error="No memory target specified to forget.")
        res = forget(target=target, semantic=self._semantic)
        return AgentResult(success=res.get("success", True), output=res)

    async def _search_history(self, params: dict, context: dict) -> AgentResult:
        query = params.get("query") or params.get("text") or ""
        n = params.get("n", 5)
        res = search_history(query=query, episodic=self._episodic, n=n)
        return AgentResult(success=True, output=res)
