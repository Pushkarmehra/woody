"""
Comprehensive tests for:
1. Fast Screen Vision & Perception
2. Calendar & Reminder tools and natural language parsing
3. Fix Text on Screen proofreader and rewriting
4. Planner routing and parameter extraction for new intents
"""
import asyncio
import os
import sys
import pytest

# Ensure project root is in path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from woody.tools.builtin.calendar_tools import (
    add_calendar_event, set_reminder, list_calendar_events, list_reminders,
    delete_reminder, delete_calendar_event, _parse_natural_datetime
)
from woody.tools.builtin.desktop_tools import fix_text_on_screen
from woody.planner.planner import Planner
from woody.agents.system_agent import SystemAgent
from woody.agents.desktop_agent import DesktopAgent
from woody.agents.vision_agent import VisionAgent


@pytest.mark.asyncio
async def test_calendar_event_creation_and_listing():
    print("\n--- TEST: Calendar Event Scheduling ---")
    res = add_calendar_event(
        title="Sprint Review Meeting",
        date_str="tomorrow",
        time_str="3pm",
        duration_minutes=45,
    )
    assert res["success"] is True, f"Failed to add calendar event: {res}"
    assert "Sprint Review Meeting" in res["message"]
    assert "event" in res
    event_id = res["event"]["id"]

    # List events
    events_res = list_calendar_events()
    assert events_res["success"] is True
    assert any(e["id"] == event_id for e in events_res["events"])

    # Delete event
    del_res = delete_calendar_event(event_id)
    assert del_res["success"] is True


@pytest.mark.asyncio
async def test_reminder_creation_and_listing():
    print("\n--- TEST: Reminders Subsystem ---")
    rem_res = set_reminder(
        text="Buy almond milk",
        time_str="in 10 minutes",
    )
    assert rem_res["success"] is True, f"Failed to set reminder: {rem_res}"
    assert "Buy almond milk" in rem_res["message"]
    rem_id = rem_res["reminder"]["id"]

    # List reminders
    list_res = list_reminders()
    assert list_res["success"] is True
    assert any(r["id"] == rem_id for r in list_res["reminders"])

    # Delete reminder
    del_res = delete_reminder(rem_id)
    assert del_res["success"] is True


@pytest.mark.asyncio
async def test_natural_datetime_parser():
    print("\n--- TEST: Natural DateTime Parsing ---")
    dt1 = _parse_natural_datetime(date_str="tomorrow", time_str="4pm")
    assert dt1.hour == 16
    assert dt1.minute == 0

    dt2 = _parse_natural_datetime(date_str="in 30 minutes")
    assert dt2 is not None

    dt3 = _parse_natural_datetime(date_str="Friday", time_str="10:30am")
    assert dt3.hour == 10
    assert dt3.minute == 30


@pytest.mark.asyncio
async def test_fix_text_on_screen_tool():
    print("\n--- TEST: Fix Text on Screen ---")
    sample_text = "this is an bad grammer sentence with speling mistakes"
    res = fix_text_on_screen(input_text=sample_text, mode="fix")
    assert res["success"] is True
    assert "fixed" in res
    assert len(res["fixed"]) > 0


@pytest.mark.asyncio
async def test_planner_routing_calendar_and_reminders():
    print("\n--- TEST: Planner Routing for Calendar & Reminders ---")
    planner = Planner(client=None)

    # 1. Reminder commands
    q1 = "remind me to call mom in 10 minutes"
    state1 = await planner.plan(q1)
    assert len(state1["subtasks"]) == 1
    assert state1["subtasks"][0]["agent"] == "system_agent"
    assert state1["subtasks"][0]["action"] == "set_reminder"
    assert "mom" in state1["subtasks"][0]["params"].get("text", "").lower()

    # 2. Remember to command (reminder)
    q2 = "remember to take medicines at 8pm"
    state2 = await planner.plan(q2)
    assert len(state2["subtasks"]) == 1
    assert state2["subtasks"][0]["agent"] == "system_agent"
    assert state2["subtasks"][0]["action"] == "set_reminder"

    # 3. Add to calendar
    q3 = "add project sync to my calendar tomorrow at 4pm"
    state3 = await planner.plan(q3)
    assert len(state3["subtasks"]) == 1
    assert state3["subtasks"][0]["agent"] == "system_agent"
    assert state3["subtasks"][0]["action"] == "add_calendar_event"

    # 4. Show calendar
    q4 = "what's on my calendar"
    state4 = await planner.plan(q4)
    assert len(state4["subtasks"]) == 1
    assert state4["subtasks"][0]["agent"] == "system_agent"
    assert state4["subtasks"][0]["action"] == "list_calendar_events"

    # 6. User's exact prompt: 'add a reminder in my calander of 15 sep about my birthday in google calender'
    q6 = "add a reminder in my calander of 15 sep about my birthday in google calender"
    state6 = await planner.plan(q6)
    assert len(state6["subtasks"]) == 1
    assert state6["subtasks"][0]["agent"] == "system_agent"
    assert state6["subtasks"][0]["action"] == "add_calendar_event"
    assert state6["subtasks"][0]["params"]["title"] == "Birthday"
    assert "15 sep" in state6["subtasks"][0]["params"]["date_str"]
    assert state6["subtasks"][0]["params"].get("open_google_calendar") is True


@pytest.mark.asyncio
async def test_planner_routing_fix_text():
    print("\n--- TEST: Planner Routing for Fix Text on Screen ---")
    planner = Planner(client=None)

    q1 = "fix my text on screen"
    state1 = await planner.plan(q1)
    assert len(state1["subtasks"]) == 1
    assert state1["subtasks"][0]["agent"] == "desktop_agent"
    assert state1["subtasks"][0]["action"] == "fix_text_on_screen"

    q2 = "correct my grammar"
    state2 = await planner.plan(q2)
    assert len(state2["subtasks"]) == 1
    assert state2["subtasks"][0]["agent"] == "desktop_agent"
    assert state2["subtasks"][0]["action"] == "fix_text_on_screen"

    q3 = "rewrite this professionally"
    state3 = await planner.plan(q3)
    assert len(state3["subtasks"]) == 1
    assert state3["subtasks"][0]["agent"] == "desktop_agent"
    assert state3["subtasks"][0]["action"] == "fix_text_on_screen"


@pytest.mark.asyncio
async def test_system_and_desktop_agents_direct_execution():
    print("\n--- TEST: System & Desktop Agent Handlers ---")
    sys_agent = SystemAgent()
    dt_agent = DesktopAgent()

    # Test system agent calendar action
    res_cal = await sys_agent.execute_action(
        "add_calendar_event",
        {"title": "Test Event", "date": "tomorrow", "time": "2pm"},
        {},
    )
    assert res_cal.success is True

    # Test system agent reminder action
    res_rem = await sys_agent.execute_action(
        "set_reminder",
        {"text": "Test Reminder", "time": "in 5 minutes"},
        {},
    )
    assert res_rem.success is True

    # Test desktop agent fix_text_on_screen action
    res_fix = await dt_agent.execute_action(
        "fix_text_on_screen",
        {"text": "this is a test text to fix", "mode": "fix"},
        {},
    )
    assert res_fix.success is True


@pytest.mark.asyncio
async def test_screen_perception_speed():
    print("\n--- TEST: Screen Perception Turnaround Speed ---")
    import time
    from woody.tools.builtin.desktop_tools import analyze_screen
    t0 = time.perf_counter()
    analysis = analyze_screen(custom_prompt="What is currently active?")
    elapsed_ms = (time.perf_counter() - t0) * 1000
    print(f"analyze_screen completed in {elapsed_ms:.1f}ms")
    assert analysis["success"] is True
    assert "active_window" in analysis
    assert elapsed_ms < 2000, f"Expected sub-2s execution, took {elapsed_ms:.1f}ms"

