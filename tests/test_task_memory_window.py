import pytest
import pytest_asyncio
import tempfile
from pathlib import Path
from woody.memory.task_window import TaskMemoryWindow
from woody.planner.planner import Planner

@pytest.mark.asyncio
async def test_multi_turn_date_follow_up():
    """Verify that when a user follows up with a date like '15 sep', it merges into the previous task."""
    with tempfile.TemporaryDirectory() as tmpdir:
        store = Path(tmpdir) / "test_window.json"
        planner = Planner(client=None)
        planner.task_window = TaskMemoryWindow(storage_path=store)

        # Turn 1: Add birthday reminder in google calendar (no date yet)
        q1 = "add a reminder in my calander about my birthday in google calender"
        state1 = await planner.plan(q1)
        assert len(state1["subtasks"]) == 1
        assert state1["subtasks"][0]["action"] == "add_calendar_event"
        assert state1["subtasks"][0]["params"]["title"] == "Birthday"
        assert state1["subtasks"][0]["params"].get("open_google_calendar") is True

        # Turn 2: User simply responds "15 sep"
        q2 = "15 sep"
        state2 = await planner.plan(q2)
        assert len(state2["subtasks"]) == 1
        st = state2["subtasks"][0]
        assert st["agent"] == "system_agent"
        assert st["action"] == "add_calendar_event"
        assert st["params"]["title"] == "Birthday"
        assert "15 sep" in st["params"]["date_str"]
        assert st["params"].get("open_google_calendar") is True


@pytest.mark.asyncio
async def test_multi_turn_site_continuation():
    """Verify that follow-up 'search mrbeast' searches on the recently opened YouTube site."""
    with tempfile.TemporaryDirectory() as tmpdir:
        store = Path(tmpdir) / "test_window.json"
        planner = Planner(client=None)
        planner.task_window = TaskMemoryWindow(storage_path=store)

        # Turn 1: Open YouTube
        q1 = "open youtube on edge"
        state1 = await planner.plan(q1)
        assert len(state1["subtasks"]) >= 1

        # Turn 2: User says "search mrbeast"
        q2 = "search mrbeast"
        state2 = await planner.plan(q2)
        assert len(state2["subtasks"]) == 1
        st = state2["subtasks"][0]
        assert st["agent"] == "browser_agent"
        assert st["action"] == "search_site"
        assert st["params"]["site"] == "youtube"
        assert "mrbeast" in st["params"]["query"]


@pytest.mark.asyncio
async def test_inquiry_about_previous_task():
    """Verify that 'what was my previous task' retrieves previous task from memory window."""
    with tempfile.TemporaryDirectory() as tmpdir:
        store = Path(tmpdir) / "test_window.json"
        planner = Planner(client=None)
        planner.task_window = TaskMemoryWindow(storage_path=store)

        # Turn 1: Set reminder
        await planner.plan("remind me to call mom tomorrow at 5pm")

        # Turn 2: Ask what was my previous task
        state2 = await planner.plan("what was my previous task")
        assert len(state2["subtasks"]) == 1
        st = state2["subtasks"][0]
        assert st["agent"] == "system_agent"
        assert st["action"] == "get_previous_task"
        assert "call mom" in st["params"]["summary"].lower()


@pytest.mark.asyncio
async def test_open_memory_window_routing():
    """Verify that 'open memory window' routes directly to system_agent.open_memory_window."""
    planner = Planner(client=None)

    for q in ["open memory window", "show memory window", "memory window", "show my memory window"]:
        state = await planner.plan(q)
        assert len(state["subtasks"]) == 1
        assert state["subtasks"][0]["agent"] == "system_agent"
        assert state["subtasks"][0]["action"] == "open_memory_window"


def test_task_memory_window_persistence():
    """Verify that TaskMemoryWindow saves and reloads turns from disk."""
    with tempfile.TemporaryDirectory() as tmpdir:
        store = Path(tmpdir) / "test_window.json"
        win1 = TaskMemoryWindow(storage_path=store)
        win1.record_turn(
            user_request="take a screenshot",
            intent="take screenshot",
            agent="desktop_agent",
            action="take_screenshot",
            params={},
        )
        assert len(win1.turns) == 1

        # Reload in new instance
        win2 = TaskMemoryWindow(storage_path=store)
        assert len(win2.turns) == 1
        assert win2.turns[0]["action"] == "take_screenshot"
