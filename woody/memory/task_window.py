"""
Task & Conversation Memory Window — Multi-turn context resolution engine.

Maintains a persistent sliding window of:
  - Recent user requests and intents
  - Subtasks executed by Woody agents
  - Questions and clarifications asked by Woody
  - Pending parameters awaiting user completion
  - Contextual resolution for follow-ups (e.g. answering date for a reminder)

Persisted to ~/.Woody/task_memory_window.json so GUI and Kernel share identical state.
"""
from __future__ import annotations

import json
import os
import re
import time
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any

from woody.utils.logging import get_logger

log = get_logger(__name__)

WINDOW_STORAGE_FILE = Path("~/.Woody/task_memory_window.json").expanduser()


@dataclass
class WindowTurn:
    id: str
    user_request: str
    intent: str
    agent: str
    action: str
    params: dict
    assistant_response: str = ""
    question_asked: str = ""
    context_resolved: bool = False
    timestamp: float = field(default_factory=time.time)
    status: str = "done"


class TaskMemoryWindow:
    """
    Sliding window holding active multi-turn conversational context.
    Resolves follow-ups and parameter answers into previous tasks.
    """

    def __init__(self, max_turns: int = 20, storage_path: Path | None = None) -> None:
        self.max_turns = max_turns
        self.storage_path = storage_path or WINDOW_STORAGE_FILE
        self.turns: list[dict] = []
        self.pending_action: str | None = None
        self.pending_params: dict = {}
        self.last_question: str = ""
        self._load()

    def _ensure_dir(self) -> None:
        try:
            self.storage_path.parent.mkdir(parents=True, exist_ok=True)
        except Exception:
            pass

    def _load(self) -> None:
        """Load persisted window state from disk."""
        if self.storage_path.exists():
            try:
                with open(self.storage_path, encoding="utf-8") as f:
                    data = json.load(f)
                    self.turns = data.get("turns", [])[-self.max_turns:]
                    self.pending_action = data.get("pending_action")
                    self.pending_params = data.get("pending_params", {})
                    self.last_question = data.get("last_question", "")
            except Exception as e:
                log.debug("task_window.load_error", error=str(e))

    def save(self) -> None:
        """Persist window state to disk."""
        self._ensure_dir()
        try:
            data = {
                "turns": self.turns[-self.max_turns:],
                "pending_action": self.pending_action,
                "pending_params": self.pending_params,
                "last_question": self.last_question,
                "updated_at": time.time(),
            }
            with open(self.storage_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            log.debug("task_window.save_error", error=str(e))

    def record_turn(
        self,
        user_request: str,
        intent: str,
        agent: str,
        action: str,
        params: dict,
        assistant_response: str = "",
        question_asked: str = "",
        status: str = "done",
    ) -> None:
        """Record an executed turn into the sliding memory window."""
        turn_id = f"turn_{int(time.time() * 1000)}"
        turn = {
            "id": turn_id,
            "user_request": user_request,
            "intent": intent,
            "agent": agent,
            "action": action,
            "params": params,
            "assistant_response": assistant_response,
            "question_asked": question_asked,
            "status": status,
            "timestamp": time.time(),
            "time_str": time.strftime("%Y-%m-%d %H:%M:%S"),
        }
        self.turns.append(turn)
        if len(self.turns) > self.max_turns:
            self.turns = self.turns[-self.max_turns:]

        # If this turn asked a question or has missing parameters, set pending
        if question_asked or any(w in assistant_response.lower() for w in ["what date", "what time", "which app", "should i", "do you want me to"]):
            self.pending_action = action
            self.pending_params = dict(params)
            self.last_question = question_asked or assistant_response
        elif action not in ("chat", "get_previous_task", "open_memory_window"):
            self.pending_action = action
            self.pending_params = dict(params)
            self.last_question = ""

        self.save()

    def set_last_question(self, question: str) -> None:
        self.last_question = question.strip()
        self.save()

    def clear(self) -> None:
        """Reset the active memory window."""
        self.turns.clear()
        self.pending_action = None
        self.pending_params = {}
        self.last_question = ""
        self.save()

    def get_last_task(self) -> dict | None:
        """Get the most recent non-conversational task."""
        for t in reversed(self.turns):
            if t.get("action") not in ("chat", "get_previous_task", "open_memory_window", "stop_speaking"):
                return t
        return self.turns[-1] if self.turns else None

    def resolve_turn_with_window(self, user_request: str) -> dict | None:
        """
        Check if user's input is a continuation, follow-up, or answer to a recent question.
        Returns a routed action dictionary with merged parameters if resolved.
        """
        req = user_request.strip().lower().strip("?!., \t")
        last_task = self.get_last_task()

        # ── 1. Explicit Memory Window GUI Request ──
        if req in (
            "open memory window", "show memory window", "view memory window",
            "open memories", "show memories", "memory window", "open task window",
            "show my memory window", "show active memory", "open memory"
        ):
            return {
                "agent": "system_agent",
                "confidence": 1.0,
                "direct_action": "open_memory_window",
                "params": {},
                "context_resolved": True,
            }

        # ── 2. Explicit Inquiry About Previous Task ──
        if any(k in req for k in [
            "what was my previous task", "what was my last task", "what is my previous task",
            "what did i just ask", "what did we do earlier", "what was my last request",
            "show previous task", "repeat previous task"
        ]):
            task_desc = "No previous task recorded in active memory."
            if last_task:
                act = last_task.get("action", "")
                params = last_task.get("params", {})
                item = params.get("title") or params.get("text") or params.get("app_name") or params.get("query") or act
                task_desc = f"Your last task was '{last_task.get('user_request', act)}' ({act}: {item})."

            return {
                "agent": "system_agent",
                "confidence": 1.0,
                "direct_action": "get_previous_task",
                "params": {"summary": task_desc, "last_task": last_task},
                "context_resolved": True,
            }

        # ── 3. Confirmation Answers ("yes", "sure", "do it", "cancel") ──
        if req in ("yes", "yeah", "yep", "sure", "do it", "please do", "confirm", "proceed", "ok", "okay"):
            if self.pending_action and self.pending_params:
                return {
                    "agent": "system_agent",
                    "confidence": 1.0,
                    "direct_action": self.pending_action,
                    "params": self.pending_params,
                    "context_resolved": True,
                }

        if req in ("no", "don't", "cancel", "nevermind", "abort", "stop that"):
            self.pending_action = None
            self.pending_params = {}
            self.last_question = ""
            self.save()
            return {
                "agent": "system_agent",
                "confidence": 1.0,
                "direct_action": "chat",
                "params": {"message": "Cancelled the pending task."},
                "context_resolved": True,
            }

        # ── 4. Date / Time Answer to Calendar or Reminder Task ──
        months = r'(?:january|jan|february|feb|march|mar|april|apr|may|june|jun|july|jul|august|aug|september|sept|sep|october|oct|november|nov|december|dec)'
        date_patterns = [
            rf'\b(?:of|on|for|at|in)?\s*(\d{{1,2}}(?:st|nd|rd|th)?\s+(?:of\s+)?{months}(?:\s+at\s+\S+)?)\b',
            rf'\b(?:of|on|for|at|in)?\s*({months}\s+\d{{1,2}}(?:st|nd|rd|th)?(?:\s+at\s+\S+)?)\b',
            rf'\b(?:of|on|for|at|in)?\s*(\d{{1,2}}[/-]\d{{1,2}}(?:[/-]\d{{2,4}})?(?:\s+at\s+\S+)?)\b',
            r'\b(?:of|on|for|at|in)?\s*((?:tomorrow|today|tonight)(?:\s+at\s+\S+)?)\b',
            r'\b(?:of|on|for|at|in)?\s*((?:next\s+\w+|(?:mon|tues|wed|wednes|thu|thur|thurs|fri|sat|satur|sun)day)(?:\s+at\s+\S+)?)\b',
            r'\b(in\s+\d+\s*(?:min|minute|minutes|hr|hour|hours))\b',
            r'\b(?:at|on)\s+(\d{1,2}(?::\d{2})?\s*(?:am|pm)?)\b',
        ]

        found_date: str | None = None
        for p in date_patterns:
            m = re.search(p, req, re.IGNORECASE)
            if m:
                found_date = m.group(1).strip()
                break

        # Check if the user is providing a date/time to complete an active/recent calendar or reminder task
        is_short_answer = len(req.split()) <= 6
        target_task = None
        if self.pending_action in ("add_calendar_event", "set_reminder"):
            target_task = {"action": self.pending_action, "params": self.pending_params}
        elif last_task and last_task.get("action") in ("add_calendar_event", "set_reminder"):
            target_task = last_task

        if found_date and is_short_answer and target_task:
            action = target_task.get("action", "add_calendar_event")
            old_params = dict(target_task.get("params", {}))
            old_params["date_str"] = found_date
            if "google" in req:
                old_params["open_google_calendar"] = True

            # If title is missing or generic, retain previous title
            title = old_params.get("title") or old_params.get("text") or "Reminder"
            if action == "add_calendar_event":
                old_params["title"] = title
            else:
                old_params["text"] = title

            log.info("task_window.resolved_date", action=action, title=title, date=found_date)
            return {
                "agent": "system_agent",
                "confidence": 1.0,
                "direct_action": action,
                "params": old_params,
                "context_resolved": True,
            }

        # ── 5. Site Search Continuation (e.g. previously opened YouTube, user says "search mrbeast") ──
        if last_task and last_task.get("action") in ("search_site", "open_url", "navigate_to"):
            last_site = last_task.get("params", {}).get("site", "")
            if not last_site:
                p_str = str(last_task.get("params", {})).lower()
                for known in ("youtube", "spotify", "google", "github", "reddit", "amazon", "twitter", "wikipedia"):
                    if known in p_str:
                        last_site = known
                        break

            search_m = re.match(r'^(?:search\s+for|search|play|find)\s+(.+)$', req, re.IGNORECASE)
            if search_m and last_site and "on " not in req:
                query = search_m.group(1).strip()
                return {
                    "agent": "browser_agent",
                    "confidence": 1.0,
                    "direct_action": "search_site",
                    "params": {"site": last_site, "query": query},
                    "context_resolved": True,
                }

        return None
