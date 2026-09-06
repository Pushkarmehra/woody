"""
Semantic Memory — Structured user preference profile and persistent memory.

User-editable JSON/Pydantic schema so preferences and stored memories are transparent,
recallable, and controllable, not a silent black box.

Stored at: ~/.Woody/preferences.json
"""
from __future__ import annotations

import datetime
import json
import uuid
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field
from woody.utils.logging import get_logger

log = get_logger(__name__)


class AppPreferences(BaseModel):
    browser: str = "chrome"
    editor: str = "vscode"
    terminal: str = "windows terminal"
    music: str = ""
    email: str = ""


class UserPreferences(BaseModel):
    """User preference profile — editable via Settings UI or directly in JSON."""
    name: str = ""
    tone: str = "concise"           # concise | verbose | friendly | technical
    tts_rate: float = 1.0
    tts_volume: float = 0.85
    tts_voice: str = "en_US-lessac-medium"
    preferred_apps: AppPreferences = Field(default_factory=AppPreferences)
    frequent_commands: list[str] = Field(default_factory=list)
    disallowed_apps: list[str] = Field(default_factory=list)    # Never open these
    time_format: str = "12h"        # 12h | 24h
    confirmation_required: list[str] = Field(default_factory=list)  # Always confirm these tools

    # Persistent Memory Extensions
    facts: dict[str, str] = Field(default_factory=dict)         # e.g. {"dog": "Charlie", "project": "Woody"}
    notes: list[dict[str, Any]] = Field(default_factory=list)   # e.g. [{"id": "...", "text": "...", "timestamp": "..."}]
    custom_memories: list[str] = Field(default_factory=list)   # Natural language memories e.g. "Likes dark mode"


class SemanticMemory:
    """
    Reads and writes the user preference profile and persistent memories.

    Usage:
        mem = SemanticMemory(path="~/.Woody/preferences.json")
        prefs = mem.load()
        mem.remember_fact("dog_name", "Charlie")
        mem.remember_note("Buy groceries on Friday")
        facts = mem.recall_memory("dog")
    """

    def __init__(self, path: str | Path = "~/.Woody/preferences.json") -> None:
        self._path = Path(path).expanduser()
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._prefs: UserPreferences | None = None

    def load(self) -> UserPreferences:
        if self._path.exists():
            try:
                with open(self._path, encoding="utf-8") as f:
                    data = json.load(f)
                self._prefs = UserPreferences(**data)
                log.debug("semantic.loaded", path=str(self._path))
                return self._prefs
            except Exception as e:
                log.warning("semantic.load_error", error=str(e), fallback="defaults")
        self._prefs = UserPreferences()
        return self._prefs

    def save(self, prefs: UserPreferences | None = None) -> None:
        p = prefs or self._prefs
        if p is None:
            return
        self._prefs = p
        with open(self._path, "w", encoding="utf-8") as f:
            json.dump(p.model_dump(), f, indent=2)
        log.debug("semantic.saved", path=str(self._path))

    def get(self) -> UserPreferences:
        if self._prefs is None:
            return self.load()
        return self._prefs

    def update(self, **kwargs: object) -> UserPreferences:
        prefs = self.get()
        for key, val in kwargs.items():
            if hasattr(prefs, key):
                setattr(prefs, key, val)
        self.save(prefs)
        return prefs

    def remember_fact(self, key: str, value: str) -> None:
        """Store a structured key-value fact in persistent memory."""
        prefs = self.get()
        clean_key = key.strip().lower().replace("'", "").replace(" ", "_")
        clean_val = value.strip()
        if clean_key in ("name", "user_name", "username", "my_name", "dogs_name", "dog_name"):
            if "name" in clean_key and clean_key != "dogs_name" and clean_key != "dog_name":
                prefs.name = clean_val
        if clean_key in ("browser", "preferred_browser"):
            prefs.preferred_apps.browser = clean_val
        elif clean_key in ("editor", "preferred_editor", "ide"):
            prefs.preferred_apps.editor = clean_val
        elif clean_key in ("terminal", "preferred_terminal"):
            prefs.preferred_apps.terminal = clean_val
        
        prefs.facts[clean_key] = clean_val
        self.save(prefs)
        log.info("semantic.remember_fact", key=clean_key, value=clean_val)

    def remember_note(self, text: str) -> dict[str, Any]:
        """Save a timestamped note in persistent memory."""
        prefs = self.get()
        note = {
            "id": str(uuid.uuid4())[:8],
            "text": text.strip(),
            "created_at": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }
        prefs.notes.append(note)
        self.save(prefs)
        log.info("semantic.remember_note", note_id=note["id"], text=text[:50])
        return note

    def remember_text(self, text: str) -> str:
        """Store a general natural language memory or statement."""
        prefs = self.get()
        clean = text.strip()
        if clean and clean not in prefs.custom_memories:
            prefs.custom_memories.append(clean)
            self.save(prefs)
            log.info("semantic.remember_text", memory=clean[:50])
        return clean

    def recall_memory(self, query: str | None = None) -> dict[str, Any]:
        """
        Recall facts, notes, and custom memories.
        If query is given, filters relevant items; otherwise returns all.
        """
        prefs = self.get()
        if not query or not query.strip():
            return {
                "name": prefs.name,
                "facts": prefs.facts,
                "notes": prefs.notes,
                "custom_memories": prefs.custom_memories,
                "preferred_apps": prefs.preferred_apps.model_dump(),
            }

        q = query.strip().lower()
        matched_facts = {
            k: v for k, v in prefs.facts.items()
            if q in k.lower() or q in str(v).lower()
        }
        matched_notes = [
            n for n in prefs.notes
            if q in n.get("text", "").lower()
        ]
        matched_custom = [
            m for m in prefs.custom_memories
            if q in m.lower()
        ]

        # Check name or preferred apps
        matched_profile = {}
        if prefs.name and (q in ("name", "user", "who") or q in prefs.name.lower() or "name" in q):
            matched_profile["name"] = prefs.name
        for app_k, app_v in prefs.preferred_apps.model_dump().items():
            if app_v and (q in app_k.lower() or q in str(app_v).lower()):
                matched_profile[f"preferred_{app_k}"] = app_v

        return {
            "name": prefs.name,
            "query": query,
            "profile": matched_profile,
            "facts": matched_facts,
            "notes": matched_notes,
            "custom_memories": matched_custom,
        }

    def forget(self, target: str) -> bool:
        """Remove a fact, note, or memory matching target."""
        prefs = self.get()
        t = target.strip().lower()
        found = False

        # 1. Check facts
        to_del = [k for k in prefs.facts if t in k.lower() or t in prefs.facts[k].lower()]
        for k in to_del:
            del prefs.facts[k]
            found = True

        # 2. Check notes
        orig_len = len(prefs.notes)
        prefs.notes = [n for n in prefs.notes if t not in n.get("text", "").lower() and n.get("id") != t]
        if len(prefs.notes) < orig_len:
            found = True

        # 3. Check custom memories
        orig_cust = len(prefs.custom_memories)
        prefs.custom_memories = [m for m in prefs.custom_memories if t not in m.lower()]
        if len(prefs.custom_memories) < orig_cust:
            found = True

        if found:
            self.save(prefs)
            log.info("semantic.forgot", target=target)
        return found

    def clear_memories(self) -> None:
        """Clear all custom facts, notes, and memories while keeping base settings."""
        prefs = self.get()
        prefs.facts.clear()
        prefs.notes.clear()
        prefs.custom_memories.clear()
        self.save(prefs)
        log.info("semantic.cleared_all")

    def format_for_prompt(self) -> str:
        """Format preferences, profile, facts, and notes for LLM prompts."""
        p = self.get()
        lines = []
        if p.name:
            lines.append(f"User Name: {p.name}")
        lines.append(f"Preferred tone: {p.tone}")
        
        pref_apps_list = [f"{k}={v}" for k, v in p.preferred_apps.model_dump().items() if v]
        if pref_apps_list:
            lines.append(f"Preferred apps: {', '.join(pref_apps_list)}")
            
        if p.facts:
            facts_str = ", ".join(f"{k}: {v}" for k, v in list(p.facts.items())[:8])
            lines.append(f"Stored Facts: {facts_str}")
            
        if p.notes:
            recent_notes = [f"[{n.get('created_at', '')[:10]}] {n.get('text', '')}" for n in p.notes[-3:]]
            lines.append(f"Recent Notes: {'; '.join(recent_notes)}")
            
        if p.custom_memories:
            lines.append(f"User Knowledge: {'; '.join(p.custom_memories[-3:])}")

        return "\n".join(lines)
