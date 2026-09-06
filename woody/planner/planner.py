"""
Planner — Task decomposition and intent routing.

The Planner runs a two-phase pipeline:
  Phase 1 (Router): Fast intent classification — is this simple or complex?
  Phase 2 (Decomposer): For complex tasks, decompose into ordered subtasks.

Simple commands ("open Notepad", "what time is it", "open youtube on edge",
"open edge and search iphone on youtube") skip the full planner
and route directly to the appropriate agent — keeping latency < 10ms.
"""
from __future__ import annotations

import json
import re
import uuid
from typing import Any

from woody.planner.prompts import (
    PLANNER_SYSTEM,
    PLANNER_USER_TEMPLATE,
    ROUTER_SYSTEM,
)
from woody.planner.working_memory import SubTask, WorkingMemoryState, make_initial_state
from woody.tools.builtin.browser_tools import BROWSER_EXE_MAP, WEB_PLATFORMS
from woody.utils.logging import get_logger
from woody.utils.groq_client import Message, GroqClient

log = get_logger(__name__)


class Planner:
    """
    Decomposes user requests into ordered subtask lists.
    """

    def __init__(
        self,
        client: GroqClient | Any,
        router_model: str = "openai/gpt-oss-20b",
        planner_model: str = "openai/gpt-oss-120b",
        session_id: str | None = None,
    ) -> None:
        self._client = client
        self._router_model = router_model
        self._planner_model = planner_model
        self._session_id = session_id or str(uuid.uuid4())[:8]

    async def plan(
        self,
        user_request: str,
        screen_context: str = "",
        clipboard_context: str = "",
        task_history: str = "",
        max_context_tokens: int = 8192,
    ) -> WorkingMemoryState:
        """
        Route and decompose a user request into a WorkingMemoryState with subtasks.
        Returns immediately for simple commands; runs full planner for complex ones.
        """
        request_id = str(uuid.uuid4())[:8]
        state = make_initial_state(
            user_request=user_request,
            session_id=self._session_id,
            request_id=request_id,
            screen_context=screen_context,
            clipboard_context=clipboard_context,
            task_history=task_history,
            max_context_tokens=max_context_tokens,
        )

        log.info("planner.plan_start", request=user_request[:60], request_id=request_id)

        # Phase 1: Route
        routing = await self._route(user_request)
        agent = routing.get("agent", "planner")
        direct_action = routing.get("direct_action")
        confidence = routing.get("confidence", 0.5)
        params = routing.get("params", {})

        log.info(
            "planner.routed",
            agent=agent,
            action=direct_action,
            confidence=confidence,
        )

        # 1. Compound Open + Type (e.g. 'open notepad and write hello')
        if agent == "compound_open_type":
            app_name = params.get("app_name", "notepad")
            text_to_type = params.get("text", "")
            state["is_simple"] = False
            state["intent"] = f"Open {app_name} and type '{text_to_type}'"
            state["subtasks"] = [
                SubTask(
                    id="t1",
                    agent="desktop_agent",
                    action="open_app",
                    params={"app_name": app_name},
                    depends_on=[],
                    description=f"Open {app_name}",
                    status="pending",
                    result=None,
                    error=None,
                    retries=0,
                ),
                SubTask(
                    id="t2",
                    agent="desktop_agent",
                    action="type_text",
                    params={"text": text_to_type},
                    depends_on=["t1"],
                    description=f"Type '{text_to_type}'",
                    status="pending",
                    result=None,
                    error=None,
                    retries=0,
                ),
            ]
            return state

        # 2. Compound Multi-App Launch (e.g. 'open notepad and calculator')
        if agent == "compound_multi_app":
            apps = params.get("apps", [])
            state["is_simple"] = False
            state["intent"] = f"Open {', '.join(apps)}"
            state["subtasks"] = [
                SubTask(
                    id=f"t{i+1}",
                    agent="desktop_agent",
                    action="open_app",
                    params={"app_name": app},
                    depends_on=[],
                    description=f"Open {app}",
                    status="pending",
                    result=None,
                    error=None,
                    retries=0,
                )
                for i, app in enumerate(apps)
            ]
            return state

        # 3. Direct Browser Search / Navigation
        if agent == "browser_agent" and direct_action in ("search_site", "navigate_to", "open_url", "search_web"):
            state["is_simple"] = True
            state["intent"] = user_request
            action_params = params if params else self._extract_simple_params(user_request, direct_action)
            desc = user_request
            if direct_action == "search_site":
                desc = f"Search '{action_params.get('query')}' on {action_params.get('site', 'web')}"
            elif direct_action in ("navigate_to", "open_url"):
                desc = f"Open {action_params.get('url', 'website')}"

            state["subtasks"] = [
                SubTask(
                    id="t1",
                    agent="browser_agent",
                    action=direct_action,
                    params=action_params,
                    depends_on=[],
                    description=desc,
                    status="pending",
                    result=None,
                    error=None,
                    retries=0,
                )
            ]
            return state

        # 4. Direct Memory Commands
        if agent == "memory_agent":
            state["is_simple"] = True
            state["intent"] = user_request
            action_params = params if params else self._extract_simple_params(user_request, direct_action or "recall")
            desc = user_request
            if direct_action == "remember_fact":
                desc = f"Remember {action_params.get('key')} is {action_params.get('value')}"
            elif direct_action == "save_note":
                desc = f"Save note: {action_params.get('text')}"
            elif direct_action == "remember":
                desc = f"Remember: {action_params.get('text')}"
            elif direct_action == "recall":
                desc = f"Recall memory for '{action_params.get('query', '')}'"
            elif direct_action == "forget":
                desc = f"Forget memory for '{action_params.get('target', '')}'"
            elif direct_action == "search_history":
                desc = f"Search history for '{action_params.get('query', '')}'"

            state["subtasks"] = [
                SubTask(
                    id="t1",
                    agent="memory_agent",
                    action=direct_action or "recall",
                    params=action_params,
                    depends_on=[],
                    description=desc,
                    status="pending",
                    result=None,
                    error=None,
                    retries=0,
                )
            ]
            return state

        if agent == "chat_agent":
            state["is_simple"] = True
            state["intent"] = user_request
            state["subtasks"] = [
                SubTask(
                    id="t1",
                    agent="chat_agent",
                    action="chat",
                    params={"message": user_request},
                    depends_on=[],
                    description=user_request,
                    status="pending",
                    result=None,
                    error=None,
                    retries=0,
                )
            ]
            return state

        if agent == "react_agent":
            state["is_simple"] = False
            state["intent"] = user_request
            state["subtasks"] = [
                SubTask(
                    id="t1",
                    agent="react_agent",
                    action="react_loop",
                    params={"goal": user_request},
                    depends_on=[],
                    description=user_request,
                    status="pending",
                    result=None,
                    error=None,
                    retries=0,
                )
            ]
            return state

        if agent != "planner" and direct_action and confidence >= 0.75:
            # Simple command — create a single subtask directly
            state["is_simple"] = True
            state["intent"] = user_request
            state["subtasks"] = [
                SubTask(
                    id="t1",
                    agent=agent,
                    action=direct_action,
                    params=params if params else self._extract_simple_params(user_request, direct_action),
                    depends_on=[],
                    description=user_request,
                    status="pending",
                    result=None,
                    error=None,
                    retries=0,
                )
            ]
            return state

        # Phase 2: Full decomposition
        return await self._decompose(state)

    # ── Pattern Parsers ───────────────────────────────────────────────────────

    def _clean_req(self, request: str) -> str:
        """Strip leading wake words and greetings."""
        return re.sub(
            r'^(hey|hi|hello|ok|okay)?\s*(woody|woodi|wodi|woodie)[,\s:]*\s*',
            '',
            request.strip(),
            flags=re.IGNORECASE,
        ).strip()

    def _normalize_app_name(self, name: str) -> str:
        """Normalize common app nicknames."""
        clean = re.sub(r'^(the|a|my)\s+', '', name.strip(), flags=re.IGNORECASE).strip().lower()
        if clean in ("notebook", "notes"):
            return "notepad"
        if clean in ("vs code", "vscode", "vs", "visual studio code"):
            return "vs code"
        if clean in ("calc",):
            return "calculator"
        if clean in ("ms edge", "microsoft edge"):
            return "edge"
        if clean in ("google chrome",):
            return "chrome"
        return clean

    def _parse_compound_open_and_type(self, request: str) -> dict | None:
        """Check for compound open-and-type commands like 'open notebook and write that \"i love pari \"'."""
        req_clean = self._clean_req(request)
        m = re.match(
            r'^(?:open|launch|start)\s+(.+?)\s+(?:and|then|to)\s+(?:write|type|say)\s+(?:that\s+)?["\']?(.+?)["\']?$',
            req_clean,
            flags=re.IGNORECASE,
        )
        if m:
            app_raw = self._normalize_app_name(m.group(1))
            text_raw = m.group(2).strip()
            return {"app_name": app_raw, "text": text_raw}
        return None

    def _parse_browser_and_site_commands(self, request: str) -> dict | None:
        """
        Check for browser, website, and platform search commands:
          1. "open youtube on edge and search there mrbeast" / "open youtube on edge and serch mrbeast"
          2. "open edge and search iphone on youtube"
          3. "open youtube and search mrbeast" / "open youtube and serch there mrbeast"
          4. "search mrbeast on youtube" / "serch for mrbeast on youtube"
          5. "play believer on youtube" / "play starboy on spotify"
          6. "open youtube on edge" / "open github in chrome"
          7. "open youtube" / "open github" / "open chatgpt"
        """
        req = self._clean_req(request)
        browser_names = r'(?:edge|msedge|ms\s+edge|microsoft\s+edge|chrome|google\s+chrome|brave|brave\s+browser|firefox|mozilla\s+firefox|opera|browser)'
        search_actions = r'(?:search|serch|serach|seach|shearch|find|look\s+up|play|listen\s+to)'
        fillers = r'(?:there\s+|for\s+|about\s+|that\s+|videos\s+of\s+|songs\s+by\s+)?'

        # 1. Pattern: open <site> on/in <browser> and (search/play/find) [there/for] <query>
        # e.g., "open youtube on edge and serch there mrbeast", "open youtube on edge and search mrbeast"
        m1 = re.match(
            rf'^(?:open|launch|start|go\s+to)\s+(.+?)\s+(?:on|in)\s+({browser_names})\s+(?:and|then)\s+{search_actions}\s+{fillers}(.+)$',
            req,
            flags=re.IGNORECASE,
        )
        if m1:
            raw_site = m1.group(1).strip().lower()
            raw_browser = m1.group(2).strip().lower()
            query = m1.group(3).strip().strip("'\"")
            norm_browser = "edge" if "edge" in raw_browser else ("chrome" if "chrome" in raw_browser else raw_browser)
            return {
                "agent": "browser_agent",
                "direct_action": "search_site",
                "confidence": 1.0,
                "params": {"query": query, "site": raw_site, "browser": norm_browser},
            }

        # 2. Pattern: open <browser> and (search/play) [there/for] <query> on/in <site>
        # e.g., "open edge and search iphone on youtube", "open edge and search there mrbeast on youtube"
        m2 = re.match(
            rf'^(?:open|launch|start)\s+({browser_names})\s+(?:and|then)\s+{search_actions}\s+{fillers}(.+?)\s+(?:on|in)\s+(\w+(?:\s+\w+)?)$',
            req,
            flags=re.IGNORECASE,
        )
        if m2:
            raw_browser = m2.group(1).strip().lower()
            query = m2.group(2).strip().strip("'\"")
            site = m2.group(3).strip().lower()
            norm_browser = "edge" if "edge" in raw_browser else ("chrome" if "chrome" in raw_browser else raw_browser)
            return {
                "agent": "browser_agent",
                "direct_action": "search_site",
                "confidence": 1.0,
                "params": {"query": query, "site": site, "browser": norm_browser},
            }

        # 3. Pattern: open <site> and (search/play) [there/for] <query>
        # e.g., "open youtube and search there mrbeast", "open google and search weather in tokyo"
        m3 = re.match(
            rf'^(?:open|launch|start|go\s+to)\s+(.+?)\s+(?:and|then)\s+{search_actions}\s+{fillers}(.+)$',
            req,
            flags=re.IGNORECASE,
        )
        if m3:
            raw_site = m3.group(1).strip().lower()
            query = m3.group(2).strip().strip("'\"")
            if raw_site in WEB_PLATFORMS or raw_site in ("youtube", "google", "reddit", "github", "amazon", "spotify", "wikipedia", "netflix", "bing"):
                return {
                    "agent": "browser_agent",
                    "direct_action": "search_site",
                    "confidence": 1.0,
                    "params": {"query": query, "site": raw_site, "browser": ""},
                }

        # 4. Pattern: open <browser> and (search/google) <query>
        # e.g., "open edge and search weather in tokyo"
        m4 = re.match(
            rf'^(?:open|launch|start)\s+({browser_names})\s+(?:and|then)\s+{search_actions}\s+{fillers}(.+)$',
            req,
            flags=re.IGNORECASE,
        )
        if m4:
            raw_browser = m4.group(1).strip().lower()
            query = m4.group(2).strip().strip("'\"")
            norm_browser = "edge" if "edge" in raw_browser else ("chrome" if "chrome" in raw_browser else raw_browser)
            return {
                "agent": "browser_agent",
                "direct_action": "search_site",
                "confidence": 1.0,
                "params": {"query": query, "site": "google", "browser": norm_browser},
            }

        # 5. Pattern: open <site> on/in <browser>
        # e.g., "open youtube on edge", "open github in chrome", "open chatgpt on edge"
        m5 = re.match(
            rf'^(?:open|launch|start|go\s+to)\s+(.+?)\s+(?:on|in)\s+({browser_names})$',
            req,
            flags=re.IGNORECASE,
        )
        if m5:
            raw_site = m5.group(1).strip().lower()
            raw_browser = m5.group(2).strip().lower()
            norm_browser = "edge" if "edge" in raw_browser else ("chrome" if "chrome" in raw_browser else raw_browser)
            target_url = WEB_PLATFORMS.get(raw_site, {}).get("base", raw_site)
            return {
                "agent": "browser_agent",
                "direct_action": "navigate_to",
                "confidence": 1.0,
                "params": {"url": target_url, "site": raw_site, "browser": norm_browser},
            }

        # 6. Pattern: (search/play/find) [there/for] <query> on/in <site>
        # e.g., "search iphone on youtube", "serch there mrbeast on youtube", "play believer on youtube"
        m6 = re.match(
            rf'^{search_actions}\s+{fillers}(.+?)\s+(?:on|in)\s+(\w+(?:\s+\w+)?)$',
            req,
            flags=re.IGNORECASE,
        )
        if m6:
            query = m6.group(1).strip().strip("'\"")
            site = m6.group(2).strip().lower()
            target_site = "spotify" if site == "spotify" else ("youtube" if site in ("youtube", "yt", "music") else site)
            return {
                "agent": "browser_agent",
                "direct_action": "search_site",
                "confidence": 1.0,
                "params": {"query": query, "site": target_site, "browser": ""},
            }

        # 7. Pattern: open <site> (where site is a known web platform or domain)
        # e.g., "open youtube", "open github", "open chatgpt", "open reddit"
        m7 = re.match(r'^(?:open|launch|start|go\s+to)\s+([a-zA-Z0-9_\-\.]+)$', req, flags=re.IGNORECASE)
        if m7:
            target = m7.group(1).strip().lower()
            if target in WEB_PLATFORMS:
                url = WEB_PLATFORMS[target]["base"]
                return {
                    "agent": "browser_agent",
                    "direct_action": "navigate_to",
                    "confidence": 1.0,
                    "params": {"url": url, "site": target},
                }
            elif target.endswith((".com", ".org", ".io", ".net", ".ai", ".tv", ".co", ".dev", ".app")):
                return {
                    "agent": "browser_agent",
                    "direct_action": "navigate_to",
                    "confidence": 1.0,
                    "params": {"url": target, "site": target},
                }

        return None

    def _parse_compound_multi_app(self, request: str) -> list[str] | None:
        """Check for compound app launches like 'open notepad and calculator' or 'open calculator, notepad and edge'."""
        req = self._clean_req(request)
        m = re.match(r'^(?:open|launch|start)\s+(.+)$', req, flags=re.IGNORECASE)
        if not m:
            return None
        rest = m.group(1).strip()
        # Don't match if it contains write, type, search, serch, on youtube, etc.
        if any(w in rest.lower() for w in ["write", "type", "search", "serch", "play", "http", "that", "saying", " on "]):
            return None
        # Split by comma, 'and', 'also', 'open'
        raw_tokens = re.split(r'[,;]|\s+(?:and|also)\s+(?:open|launch|start\s+)?|\s+(?:open|launch|start)\s+', rest, flags=re.IGNORECASE)
        cleaned = []
        for tok in raw_tokens:
            tok = tok.strip()
            if not tok:
                continue
            tok = re.sub(r'^(?:open|launch|start|the|a|my)\s+', '', tok, flags=re.IGNORECASE).strip()
            norm = self._normalize_app_name(tok)
            if norm and norm not in ("and", "also", "then"):
                cleaned.append(norm)
        if len(cleaned) >= 2:
            return cleaned
        return None

    def _parse_memory_commands(self, request: str) -> dict | None:
        """Parse explicit memory commands like 'remember that...', 'store note...', 'what is my...', etc."""
        req = self._clean_req(request).strip()
        req_lower = req.lower().strip("?!., \t")

        # 1. Notes: 'save note ...', 'take a note ...', 'add note ...', 'store [this] note: ...'
        note_patterns = [
            r'^(?:store\s+(?:this\s+)?note(?:\s*:\s*|\s+)|save\s+(?:a\s+)?note(?:\s*:\s*|\s+)|add\s+(?:a\s+)?note(?:\s*:\s*|\s+)|take\s+(?:a\s+)?note(?:\s*:\s*|\s+)|make\s+(?:a\s+)?note(?:\s*:\s*|\s+))(.*)$',
        ]
        for pat in note_patterns:
            m = re.match(pat, req, re.IGNORECASE)
            if m:
                text = m.group(1).strip().strip("'\"")
                if text:
                    return {
                        "agent": "memory_agent",
                        "confidence": 1.0,
                        "direct_action": "save_note",
                        "params": {"text": text},
                    }

        # 2. Remember facts / statements:
        # 'remember that my name is ...', 'remember my name is ...', 'remember that ...', 'remember ...'
        rem_m = re.match(r'^(?:remember\s+that\s+|remember\s+|store\s+that\s+|memorize\s+that\s+|memorize\s+)(.*)$', req, re.IGNORECASE)
        if rem_m:
            body = rem_m.group(1).strip()
            # Check if it's 'my <key> is <value>' or '<key> is <value>'
            fact_m = re.match(r'^(?:my\s+)?([a-zA-Z0-9\s_\-\'\"]+?)\s+(?:is|are|=|:)\s+(.*)$', body, re.IGNORECASE)
            if fact_m and not body.lower().startswith("to "):
                key = fact_m.group(1).strip()
                val = fact_m.group(2).strip().strip("'\"")
                return {
                    "agent": "memory_agent",
                    "confidence": 1.0,
                    "direct_action": "remember_fact",
                    "params": {"key": key, "value": val, "text": body},
                }
            return {
                "agent": "memory_agent",
                "confidence": 1.0,
                "direct_action": "remember",
                "params": {"text": body},
            }

        # 3. Forgetting / clearing:
        # 'forget that ...', 'forget ...', 'delete note ...', 'clear memories', 'forget all'
        if req_lower in ("clear memories", "clear all memories", "forget all", "forget everything"):
            return {
                "agent": "memory_agent",
                "confidence": 1.0,
                "direct_action": "forget",
                "params": {"target": "all"},
            }
        forget_m = re.match(r'^(?:forget\s+that\s+|forget\s+|delete\s+note\s+|remove\s+memory\s+)(.*)$', req, re.IGNORECASE)
        if forget_m:
            target = forget_m.group(1).strip()
            return {
                "agent": "memory_agent",
                "confidence": 1.0,
                "direct_action": "forget",
                "params": {"target": target},
            }

        # 4. Recalling / Memory queries:
        # 'what is my name', 'who am i', 'what do you remember about me', 'what are my notes', 'recall ...'
        if req_lower in ("who am i", "what's my name", "what is my name", "who am i?"):
            return {
                "agent": "memory_agent",
                "confidence": 1.0,
                "direct_action": "recall",
                "params": {"query": "name"},
            }
        if any(req_lower == k or req_lower.startswith(k + " ") for k in [
            "what do you remember about me", "what do you remember", "what are my memories",
            "show my memories", "list memories", "show memories", "what have you remembered"
        ]):
            return {
                "agent": "memory_agent",
                "confidence": 1.0,
                "direct_action": "recall",
                "params": {"query": ""},
            }
        if any(req_lower == k or req_lower.startswith(k + " ") for k in [
            "what are my notes", "show my notes", "read my notes", "list notes", "show notes", "what notes do i have"
        ]):
            return {
                "agent": "memory_agent",
                "confidence": 1.0,
                "direct_action": "recall",
                "params": {"query": "note"},
            }
        
        what_is_my = re.match(r'^(?:what\s+is\s+my|what\'s\s+my|tell\s+me\s+my)\s+([a-zA-Z\s_\-]+?)(?:\?)?$', req, re.IGNORECASE)
        if what_is_my:
            item = what_is_my.group(1).strip()
            if item not in ("time", "date", "ip", "system", "battery", "status", "screen"):
                return {
                    "agent": "memory_agent",
                    "confidence": 1.0,
                    "direct_action": "recall",
                    "params": {"query": item},
                }

        if req_lower.startswith("recall "):
            query = req[7:].strip()
            return {
                "agent": "memory_agent",
                "confidence": 1.0,
                "direct_action": "recall",
                "params": {"query": query},
            }

        # 5. History queries:
        # 'what did i ask earlier', 'what did we do before', 'search history for ...'
        if any(k in req_lower for k in [
            "what did i ask earlier", "what did i ask you", "what was my last request",
            "what did we do earlier", "what did we do before", "what was my previous question"
        ]):
            return {
                "agent": "memory_agent",
                "confidence": 1.0,
                "direct_action": "search_history",
                "params": {"query": "", "n": 5},
            }
        hist_m = re.match(r'^(?:search\s+history\s+for|search\s+past\s+tasks\s+for|find\s+in\s+history)\s+(.*)$', req, re.IGNORECASE)
        if hist_m:
            query = hist_m.group(1).strip()
            return {
                "agent": "memory_agent",
                "confidence": 1.0,
                "direct_action": "search_history",
                "params": {"query": query, "n": 5},
            }

        return None

    # ── Intent Routing ────────────────────────────────────────────────────────

    async def _route(self, user_request: str) -> dict:
        """Fast intent classification via rules or small model."""
        req = user_request.lower().strip()
        effective_req = self._clean_req(req)

        # 1. Direct Memory Commands (e.g. 'remember that my name is Pushkar', 'what is my name?')
        mem_cmd = self._parse_memory_commands(user_request)
        if mem_cmd:
            return mem_cmd

        # 2. Compound Browser & Site Commands (e.g. 'open edge and search iphone on youtube')
        browser_cmd = self._parse_browser_and_site_commands(user_request)
        if browser_cmd:
            return browser_cmd

        # 2. Compound Open + Type (e.g. 'open notebook and write hello')
        compound_type = self._parse_compound_open_and_type(user_request)
        if compound_type:
            return {"agent": "compound_open_type", "confidence": 1.0, "params": compound_type}

        # 3. Compound Multi-App Launch (e.g. 'open notepad and calculator')
        multi_app = self._parse_compound_multi_app(user_request)
        if multi_app:
            return {"agent": "compound_multi_app", "confidence": 1.0, "params": {"apps": multi_app}}

        # 4. Fast-path single app heuristics (< 1ms)
        _open_re = re.compile(r'^(open|launch|start)\s+\S')
        _close_re = re.compile(r'^(close|quit|exit)\s+\S')
        is_compound = any(w in effective_req for w in [" and ", " then ", " write ", " type ", " also ", " with "])

        if not is_compound and _open_re.match(effective_req):
            params = self._extract_simple_params(user_request, "open_app")
            if params.get("app_name"):
                return {"agent": "desktop_agent", "confidence": 1.0, "direct_action": "open_app", "params": params}

        if not is_compound and _close_re.match(effective_req):
            params = self._extract_simple_params(user_request, "close_app")
            if params.get("app_name"):
                return {"agent": "desktop_agent", "confidence": 1.0, "direct_action": "close_app", "params": params}

        # 5. System Controls Fast-paths
        if any(effective_req == k or effective_req.startswith(k + " ") for k in [
            "stop speaking", "stop talking", "be quiet", "shut up", "silence", "hush",
            "stop speech", "stop audio", "stop voice", "mute audio", "pause speech", "stop reading",
            "mute"
        ]) or effective_req in ["stop speaking", "stop talking", "be quiet", "shut up", "silence", "hush", "stop"]:
            return {"agent": "system_agent", "confidence": 1.0, "direct_action": "stop_speaking"}

        if any(k in effective_req for k in ["what time", "what's the time", "current time", "what date", "what's the date", "today's date"]):
            return {"agent": "system_agent", "confidence": 1.0, "direct_action": "get_time_date"}
        if any(k in effective_req for k in ["cpu usage", "ram usage", "system stats", "memory usage", "how much cpu", "how much ram"]):
            return {"agent": "system_agent", "confidence": 1.0, "direct_action": "get_system_stats"}
        if any(k in effective_req for k in ["battery", "power level", "how much battery"]):
            return {"agent": "system_agent", "confidence": 1.0, "direct_action": "get_battery"}
        if any(k in effective_req for k in ["clipboard", "show clipboard", "what's in my clipboard"]):
            return {"agent": "system_agent", "confidence": 1.0, "direct_action": "get_clipboard"}
        if any(k in effective_req for k in [
            "take screenshot", "take a screenshot", "screenshot", "take ss", "take a ss",
            "do ss", "take screen shot", "take a screen shot", "screen shot",
            "capture screen", "capture screenshot", "capture the screen", "save screenshot", "snap screen"
        ]) or effective_req == "ss":
            return {"agent": "desktop_agent", "confidence": 1.0, "direct_action": "take_screenshot"}

        # 6. Window Management Fast-paths
        if any(effective_req == k or effective_req.startswith(k + " ") for k in ["maximize window", "maximize", "fullscreen", "full screen"]):
            return {"agent": "desktop_agent", "confidence": 1.0, "direct_action": "maximize_window"}
        if any(effective_req == k or effective_req.startswith(k + " ") for k in ["minimize window", "minimize", "hide window"]):
            return {"agent": "desktop_agent", "confidence": 1.0, "direct_action": "minimize_window"}
        if any(k in effective_req for k in ["show desktop", "go to desktop"]):
            return {"agent": "desktop_agent", "confidence": 1.0, "direct_action": "hotkey", "params": {"keys": "win+d"}}
        if "scroll down" in effective_req:
            return {"agent": "desktop_agent", "confidence": 1.0, "direct_action": "scroll", "params": {"direction": "down"}}
        if "scroll up" in effective_req:
            return {"agent": "desktop_agent", "confidence": 1.0, "direct_action": "scroll", "params": {"direction": "up"}}

        # 7. Screen perception & Vision fast-path
        if any(k in effective_req for k in [
            "one my screen", "on my screen", "in my screen", "on screen", "one screen", "in screen",
            "on my display", "on display",
            "see my screen", "look at my screen", "read my screen", "scan my screen",
            "analyze screen", "analyze my screen", "describe my screen", "describe the screen",
            "explain what's on my screen", "explain this error", "what do you see",
            "check my screen", "view my screen", "what am i looking at", "what is open"
        ]):
            return {"agent": "vision_agent", "confidence": 1.0, "direct_action": "analyze_screen"}

        # 8. Web search fast-path
        if any(effective_req.startswith(p) for p in [
            "search for ", "search the web for ", "search the web", "search online for ", "search online",
            "search ", "google ", "look up ", "find info on ", "find information on "
        ]) or any(k in effective_req for k in ["search the internet", "search the web", "search online"]):
            return {"agent": "browser_agent", "confidence": 1.0, "direct_action": "search_web"}

        # 9. Conversational messages -> chat_agent
        _CHAT_GREETINGS = {
            "hi", "hello", "hey", "yo", "sup", "howdy",
            "hi woody", "hello woody", "hey woody", "woody",
            "thanks", "thank you", "ok", "okay", "cool", "great",
            "bye", "goodbye", "stop", "quit",
        }
        if req in _CHAT_GREETINGS or not effective_req or (len(req.split()) <= 6 and not any(
            c in req for c in ["open", "close", "run", "search", "find", "make", "create", "delete", "download", "type", "write", "screen"]
        )):
            return {"agent": "chat_agent", "confidence": 1.0, "direct_action": "chat"}

        # Fallback to Router LLM
        try:
            if not self._client:
                return {"agent": "react_agent"}
            messages = [
                Message(role="system", content=ROUTER_SYSTEM),
                Message(role="user", content=user_request),
            ]
            resp = await self._client.chat(
                model=self._router_model,
                messages=messages,
                temperature=0.0,
                max_tokens=64,
            )
            return self._parse_json(resp.content, default={"agent": "react_agent"})
        except Exception as e:
            log.warning("planner.route_error", error=str(e), fallback="react_agent")
            return {"agent": "react_agent"}

    async def _decompose(self, state: WorkingMemoryState) -> WorkingMemoryState:
        """Full LLM-based task decomposition."""
        if not self._client:
            return state

        prompt = PLANNER_USER_TEMPLATE.format(
            user_request=state["user_request"],
            screen_context=state["screen_context"] or "Not available",
            clipboard_context=state["clipboard_context"] or "Empty",
            task_history=state["task_history"] or "No recent history",
        )
        messages = [
            Message(role="system", content=PLANNER_SYSTEM),
            Message(role="user", content=prompt),
        ]
        try:
            resp = await self._client.chat(
                model=self._planner_model,
                messages=messages,
                temperature=0.1,
                max_tokens=1024,
            )
            state["planner_tokens_used"] = resp.prompt_tokens + resp.completion_tokens
            plan = self._parse_json(resp.content, default={})

            state["intent"] = plan.get("intent", state["user_request"])
            state["is_simple"] = bool(plan.get("is_simple", False))
            raw_subtasks = plan.get("subtasks", [])

            state["subtasks"] = [
                SubTask(
                    id=t.get("id", f"t{i+1}"),
                    agent=t.get("agent", "system_agent"),
                    action=t.get("action", "unknown"),
                    params=t.get("params", {}),
                    depends_on=t.get("depends_on", []),
                    description=t.get("description", ""),
                    status="pending",
                    result=None,
                    error=None,
                    retries=0,
                )
                for i, t in enumerate(raw_subtasks)
            ]

            log.info(
                "planner.decomposed",
                intent=state["intent"][:60],
                n_subtasks=len(state["subtasks"]),
            )
        except Exception as e:
            log.error("planner.decompose_error", error=str(e))
            state["subtasks"] = [
                SubTask(
                    id="t1",
                    agent="system_agent",
                    action="clarify",
                    params={"message": f"I couldn't fully understand: '{state['user_request']}'. Could you rephrase?"},
                    depends_on=[],
                    description="Clarification needed",
                    status="pending",
                    result=None,
                    error=None,
                    retries=0,
                )
            ]
        return state

    def _extract_simple_params(self, request: str, action: str) -> dict:
        """Extract parameters from simple requests."""
        request_lower = request.lower()
        params: dict[str, Any] = {}
        _ARTICLES = {"the", "a", "an", "my"}
        _TRAILING = {"please", "thanks", "now"}

        if action == "open_app":
            for kw in ["open ", "launch ", "start "]:
                if kw in request_lower:
                    idx = request_lower.find(kw) + len(kw)
                    words = request[idx:].strip().split()
                    while words and words[0].lower() in _ARTICLES:
                        words = words[1:]
                    while words and words[-1].lower() in _TRAILING:
                        words = words[:-1]
                    stop_idx = len(words)
                    for i, w in enumerate(words):
                        if w.lower() in ("and", "then", "with", "write", "type", "to", "also", "saying", "on", "in"):
                            stop_idx = i
                            break
                    app_words = words[:stop_idx]
                    if app_words:
                        clean_app = self._normalize_app_name(" ".join(app_words).strip().strip("'\""))
                        params["app_name"] = clean_app
                    break

        elif action == "close_app":
            for kw in ["close ", "quit ", "exit "]:
                if kw in request_lower:
                    idx = request_lower.find(kw) + len(kw)
                    words = request[idx:].strip().split()
                    while words and words[0].lower() in _ARTICLES:
                        words = words[1:]
                    while words and words[-1].lower() in _TRAILING:
                        words = words[:-1]
                    stop_idx = len(words)
                    for i, w in enumerate(words):
                        if w.lower() in ("and", "then", "with", "also"):
                            stop_idx = i
                            break
                    app_words = words[:stop_idx]
                    if app_words:
                        clean_app = self._normalize_app_name(" ".join(app_words).strip().strip("'\""))
                        params["app_name"] = clean_app
                    break

        elif action == "search_site":
            # Extract query and site
            parsed = self._parse_browser_and_site_commands(request)
            if parsed and parsed.get("params"):
                return parsed["params"]
            params["query"] = request.strip()
            params["site"] = "youtube"

        elif action in ("navigate_to", "open_url"):
            parsed = self._parse_browser_and_site_commands(request)
            if parsed and parsed.get("params"):
                return parsed["params"]
            params["url"] = request.strip()

        elif action == "search_web":
            for kw in [
                "search the web for ", "search the web ", "search online for ", "search online ",
                "search for ", "search ", "google for ", "google ", "look up ",
                "find information on ", "find info on ", "find out about ", "find "
            ]:
                if kw in request_lower:
                    idx = request_lower.find(kw) + len(kw)
                    params["query"] = request[idx:].strip()
                    break
            if not params.get("query"):
                params["query"] = request.strip()

        elif action == "analyze_screen":
            params["custom_prompt"] = request.strip()

        elif action == "scroll":
            params["direction"] = "up" if "up" in request_lower else "down"
            params["clicks"] = 5

        elif action == "hotkey":
            if "desktop" in request_lower:
                params["keys"] = "win+d"

        elif action in ("remember", "remember_fact"):
            rem_m = re.match(r'^(?:remember\s+that\s+|remember\s+)(.*)$', request, re.IGNORECASE)
            body = rem_m.group(1).strip() if rem_m else request.strip()
            fact_m = re.match(r'^(?:my\s+)?([a-zA-Z\s_\-]+?)\s+(?:is|are|=|:)\s+(.*)$', body, re.IGNORECASE)
            if fact_m:
                params["key"] = fact_m.group(1).strip()
                params["value"] = fact_m.group(2).strip().strip("'\"")
            params["text"] = body

        elif action == "save_note":
            note_m = re.match(r'^(?:store\s+(?:this\s+)?note(?:\s*:\s*|\s+)|save\s+note(?:\s*:\s*|\s+)|take\s+note(?:\s*:\s*|\s+))(.*)$', request, re.IGNORECASE)
            params["text"] = note_m.group(1).strip().strip("'\"") if note_m else request.strip()

        elif action in ("recall", "forget", "search_history"):
            params["query"] = request.strip()
            params["target"] = request.strip()

        elif action == "chat":
            params["message"] = request.strip()

        return params

    @staticmethod
    def _parse_json(text: str, default: dict) -> dict:
        """Parse JSON from LLM output, stripping markdown fences."""
        text = text.strip()
        if "```" in text:
            lines = text.splitlines()
            text = "\n".join(
                l for l in lines if not l.strip().startswith("```")
            )
        start = text.find("{")
        end = text.rfind("}") + 1
        if start >= 0 and end > start:
            try:
                return json.loads(text[start:end])
            except json.JSONDecodeError:
                pass
        return default
