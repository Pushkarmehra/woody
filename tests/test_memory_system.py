"""
Comprehensive test suite for Woody's Persistent Memory Subsystem.

Tests:
1. SemanticMemory facts, notes, natural language knowledge, recall, forget, prompt formatting.
2. EpisodicMemory database logging, search by keyword, recent session summaries.
3. MemoryTools & MemoryAgent action execution.
4. Planner fast-path intent classification for memory commands.
5. End-to-end DispatchBus execution of memory tasks.
"""
import os
import sys
import tempfile
import pytest

# Ensure project root is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from woody.memory.semantic import SemanticMemory, UserPreferences
from woody.memory.episodic import EpisodicMemory
from woody.tools.builtin.memory_tools import (
    remember_fact,
    save_note,
    remember_text,
    recall,
    forget,
    search_history,
)
from woody.agents.memory_agent import MemoryAgent
from woody.planner.planner import Planner
from woody.kernel.dispatch import build_dispatch_bus
from woody.kernel.config import load_config


def test_semantic_memory_facts_and_notes():
    with tempfile.TemporaryDirectory() as tmpdir:
        json_path = os.path.join(tmpdir, "preferences.json")
        mem = SemanticMemory(path=json_path)

        # 1. Remember facts
        mem.remember_fact("name", "Pushkar")
        mem.remember_fact("dog_name", "Charlie")
        mem.remember_fact("favorite_editor", "VS Code")

        prefs = mem.get()
        assert prefs.name == "Pushkar"
        assert prefs.facts["dog_name"] == "Charlie"
        assert prefs.facts["favorite_editor"] == "VS Code"

        # 2. Save notes
        n1 = mem.remember_note("Buy groceries tomorrow")
        n2 = mem.remember_note("Meeting with team at 4pm")
        assert len(prefs.notes) == 2
        assert n1["text"] == "Buy groceries tomorrow"

        # 3. Custom text memories
        mem.remember_text("User likes dark mode")
        assert "User likes dark mode" in prefs.custom_memories

        # 4. Recall
        res = mem.recall_memory("dog")
        assert "dog_name" in res["facts"]
        assert res["facts"]["dog_name"] == "Charlie"

        res_notes = mem.recall_memory("groceries")
        assert len(res_notes["notes"]) == 1

        # 5. Format for prompt
        prompt_str = mem.format_for_prompt()
        assert "User Name: Pushkar" in prompt_str
        assert "dog_name: Charlie" in prompt_str
        assert "Buy groceries tomorrow" in prompt_str

        # 6. Forget
        forgot = mem.forget("dog")
        assert forgot is True
        assert "dog_name" not in mem.get().facts

        # 7. Clear all
        mem.clear_memories()
        assert len(mem.get().facts) == 0
        assert len(mem.get().notes) == 0
        assert len(mem.get().custom_memories) == 0


def test_episodic_memory_search():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "episodic.db")
        ep = EpisodicMemory(db_path=db_path)
        ep.open()

        ep.log_session(
            session_id="s1",
            user_request="open youtube on edge and search mrbeast",
            intent="Search YouTube for mrbeast",
            result_summary="Opened Edge and searched for mrbeast on YouTube.",
            success=True,
            duration_ms=45.0,
        )
        ep.log_session(
            session_id="s2",
            user_request="what is the weather in tokyo",
            intent="Get weather",
            result_summary="Tokyo weather is 22 degrees.",
            success=True,
            duration_ms=20.0,
        )

        assert ep.get_session_count() == 2

        # Search for mrbeast
        res1 = ep.search("mrbeast")
        assert len(res1) == 1
        assert "youtube" in res1[0]["request"].lower()

        # Search for tokyo
        res2 = ep.search("tokyo")
        assert len(res2) == 1
        assert "weather" in res2[0]["request"].lower()

        # Recent summary
        recent = ep.get_recent_summary(n=2)
        assert len(recent) == 2

        ep.close()


@pytest.mark.asyncio
async def test_memory_agent_actions():
    with tempfile.TemporaryDirectory() as tmpdir:
        sem = SemanticMemory(path=os.path.join(tmpdir, "prefs.json"))
        ep = EpisodicMemory(db_path=os.path.join(tmpdir, "ep.db"))
        ep.open()
        agent = MemoryAgent(semantic_memory=sem, episodic_memory=ep)

        # 1. remember_fact
        r1 = await agent.run(
            action="remember_fact",
            params={"key": "project", "value": "Woody v4.0"},
            context={},
        )
        assert r1.success is True
        assert sem.get().facts["project"] == "Woody v4.0"

        # 2. save_note
        r2 = await agent.run(
            action="save_note",
            params={"text": "Review architecture doc tonight"},
            context={},
        )
        assert r2.success is True
        assert len(sem.get().notes) == 1

        # 3. recall
        r3 = await agent.run(
            action="recall",
            params={"query": "project"},
            context={},
        )
        assert r3.success is True
        assert r3.output["data"]["facts"]["project"] == "Woody v4.0"

        # 4. forget
        r4 = await agent.run(
            action="forget",
            params={"target": "project"},
            context={},
        )
        assert r4.success is True
        assert "project" not in sem.get().facts

        ep.close()


@pytest.mark.asyncio
async def test_planner_memory_intent_routing():
    planner = Planner(client=None)

    queries = [
        ("remember that my name is Pushkar", "remember_fact", "memory_agent"),
        ("remember my dog's name is Charlie", "remember_fact", "memory_agent"),
        ("remember that my preferred browser is Edge", "remember_fact", "memory_agent"),
        ("store this note: buy groceries tomorrow", "save_note", "memory_agent"),
        ("save note: call doctor at 3pm", "save_note", "memory_agent"),
        ("what is my name?", "recall", "memory_agent"),
        ("who am I?", "recall", "memory_agent"),
        ("what are my notes?", "recall", "memory_agent"),
        ("what do you remember about me?", "recall", "memory_agent"),
        ("forget that my dog is Charlie", "forget", "memory_agent"),
        ("clear memories", "forget", "memory_agent"),
        ("what did I ask earlier?", "search_history", "memory_agent"),
    ]

    for q, expected_action, expected_agent in queries:
        state = await planner.plan(q)
        assert len(state["subtasks"]) == 1, f"Failed on query: {q}"
        task = state["subtasks"][0]
        assert task["agent"] == expected_agent, f"Wrong agent for '{q}': got {task['agent']}"
        assert task["action"] == expected_action, f"Wrong action for '{q}': got {task['action']}"


@pytest.mark.asyncio
async def test_end_to_end_dispatch_bus_memory():
    with tempfile.TemporaryDirectory() as tmpdir:
        sem = SemanticMemory(path=os.path.join(tmpdir, "prefs.json"))
        ep = EpisodicMemory(db_path=os.path.join(tmpdir, "ep.db"))
        ep.open()
        try:
            cfg = load_config()

            bus = build_dispatch_bus(
                config=cfg,
                semantic_memory=sem,
                episodic_memory=ep,
            )

            planner = Planner(client=None)
            
            # 1. Plan and execute "remember that my name is Pushkar"
            state1 = await planner.plan("remember that my name is Pushkar")
            res1 = await bus.execute(state1)
            assert res1["subtasks"][0]["status"] == "done"
            assert sem.get().name == "Pushkar"

            # 2. Plan and execute "what is my name?"
            state2 = await planner.plan("what is my name?")
            res2 = await bus.execute(state2)
            assert res2["subtasks"][0]["status"] == "done"
            out = res2["subtasks"][0]["result"]
            assert out["data"]["profile"]["name"] == "Pushkar" or out["data"]["name"] == "Pushkar"
        finally:
            ep.close()
