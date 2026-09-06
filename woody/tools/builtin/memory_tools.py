"""
Memory Tools — Direct interface to Woody's persistent memory systems.

Provides functions to store facts, save notes, recall knowledge, forget items,
and search episodic history.
"""
from __future__ import annotations

from typing import Any
from woody.memory.semantic import SemanticMemory
from woody.memory.episodic import EpisodicMemory
from woody.utils.logging import get_logger

log = get_logger(__name__)

# Global singletons for memory tools
_semantic_instance: SemanticMemory | None = None
_episodic_instance: EpisodicMemory | None = None


def get_semantic_memory() -> SemanticMemory:
    global _semantic_instance
    if _semantic_instance is None:
        _semantic_instance = SemanticMemory()
    return _semantic_instance


def get_episodic_memory() -> EpisodicMemory:
    global _episodic_instance
    if _episodic_instance is None:
        _episodic_instance = EpisodicMemory()
        _episodic_instance.open()
    return _episodic_instance


def remember_fact(key: str, value: str, semantic: SemanticMemory | None = None) -> dict[str, Any]:
    """Store a key-value fact into persistent memory."""
    mem = semantic or get_semantic_memory()
    mem.remember_fact(key, value)
    return {
        "success": True,
        "action": "remember_fact",
        "key": key,
        "value": value,
        "message": f"I've remembered that {key} is {value}.",
    }


def save_note(text: str, semantic: SemanticMemory | None = None) -> dict[str, Any]:
    """Save a timestamped note into persistent memory."""
    mem = semantic or get_semantic_memory()
    note = mem.remember_note(text)
    return {
        "success": True,
        "action": "save_note",
        "note": note,
        "message": f"I've saved your note: '{text}'.",
    }


def remember_text(text: str, semantic: SemanticMemory | None = None) -> dict[str, Any]:
    """Store a general natural language memory or statement."""
    mem = semantic or get_semantic_memory()
    saved = mem.remember_text(text)
    return {
        "success": True,
        "action": "remember",
        "memory": saved,
        "message": f"I've committed that to memory: '{saved}'.",
    }


def recall(query: str = "", semantic: SemanticMemory | None = None) -> dict[str, Any]:
    """Recall facts, notes, and custom memories from persistent storage."""
    mem = semantic or get_semantic_memory()
    data = mem.recall_memory(query)
    
    # Build a concise friendly summary
    items = []
    if data.get("name"):
        items.append(f"Name: {data['name']}")
    for k, v in data.get("facts", {}).items():
        items.append(f"{k}: {v}")
    for n in data.get("notes", []):
        items.append(f"Note: {n.get('text', '')}")
    for m in data.get("custom_memories", []):
        items.append(m)

    summary = "; ".join(items) if items else "I don't have any matching memories stored yet."
    return {
        "success": True,
        "action": "recall",
        "query": query,
        "data": data,
        "summary": summary,
    }


def forget(target: str, semantic: SemanticMemory | None = None) -> dict[str, Any]:
    """Remove a fact, note, or memory matching target."""
    mem = semantic or get_semantic_memory()
    if target.lower() in ("all", "everything", "all memories", "clear"):
        mem.clear_memories()
        return {
            "success": True,
            "action": "forget_all",
            "message": "I've cleared all custom facts, notes, and memories.",
        }
    
    found = mem.forget(target)
    if found:
        return {
            "success": True,
            "action": "forget",
            "target": target,
            "message": f"I've forgotten '{target}' from memory.",
        }
    return {
        "success": False,
        "action": "forget",
        "target": target,
        "message": f"I couldn't find any memory matching '{target}'.",
    }


def search_history(query: str = "", episodic: EpisodicMemory | None = None, n: int = 5) -> dict[str, Any]:
    """Search past episodic session history."""
    mem = episodic or get_episodic_memory()
    sessions = mem.search(query=query, n=n)
    return {
        "success": True,
        "action": "search_history",
        "query": query,
        "sessions": sessions,
        "count": len(sessions),
    }
