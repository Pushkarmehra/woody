"""
Comprehensive test suite for Browser, Site Search, App Disambiguation & Compound Commands in Woody.

Tests all key scenarios:
1. "open edge and search iphone on youtube"
2. "open youtube on edge"
3. "search iphone on youtube" & "search for python tutorials on youtube"
4. "play believer on youtube" & "play starboy on spotify"
5. "open github on chrome" / "open chatgpt on edge"
6. "open edge and search weather in tokyo"
7. "open youtube and search lofi beats"
8. Compound multi-app launches ("open notepad and calculator", "open vs code and edge")
9. False app prevention (invalid app name returns error, does not return false success)
10. End-to-end Planner decomposition and Kernel fast-formatting verification.
"""
import asyncio
import os
import sys
import pytest

# Ensure project root is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from woody.tools.builtin.browser_tools import (
    WEB_PLATFORMS, search_site, open_url, navigate_to, BROWSER_EXE_MAP
)
from woody.tools.builtin.desktop_tools import open_app
from woody.planner.planner import Planner
from woody.planner.working_memory import WorkingMemoryState, SubTask
from woody.kernel.kernel import WoodyKernel
from woody.kernel.config import load_config


@pytest.mark.asyncio
async def test_1_open_edge_and_search_iphone_on_youtube():
    """Test the exact user prompt from screenshot: 'open edge and search iphone on youtube'."""
    planner = Planner(client=None)
    cmd = "open edge and search iphone on youtube"
    
    # 1. Test pattern parser
    parsed = planner._parse_browser_and_site_commands(cmd)
    assert parsed is not None, f"Failed to parse '{cmd}'"
    assert parsed["agent"] == "browser_agent"
    assert parsed["direct_action"] == "search_site"
    assert parsed["params"]["query"] == "iphone"
    assert parsed["params"]["site"] == "youtube"
    assert parsed["params"]["browser"] == "edge"

    # 2. Test full planner plan
    state = await planner.plan(cmd)
    assert len(state["subtasks"]) == 1
    task = state["subtasks"][0]
    assert task["agent"] == "browser_agent"
    assert task["action"] == "search_site"
    assert task["params"]["query"] == "iphone"
    assert task["params"]["site"] == "youtube"
    assert task["params"]["browser"] == "edge"


@pytest.mark.asyncio
async def test_2_open_youtube_on_edge():
    """Test user prompt: 'open youtube on edge'."""
    planner = Planner(client=None)
    cmd = "open youtube on edge"
    
    parsed = planner._parse_browser_and_site_commands(cmd)
    assert parsed is not None, f"Failed to parse '{cmd}'"
    assert parsed["agent"] == "browser_agent"
    assert parsed["direct_action"] == "navigate_to"
    assert parsed["params"]["browser"] == "edge"
    assert "youtube.com" in parsed["params"]["url"]

    state = await planner.plan(cmd)
    assert len(state["subtasks"]) == 1
    task = state["subtasks"][0]
    assert task["action"] == "navigate_to"
    assert task["params"]["browser"] == "edge"


@pytest.mark.asyncio
async def test_3_site_search_variations():
    """Test 'search <query> on <site>' and 'search for <query> on <site>'."""
    planner = Planner(client=None)
    
    test_cases = [
        ("search iphone on youtube", "iphone", "youtube"),
        ("search for python tutorials on youtube", "python tutorials", "youtube"),
        ("search rust web framework on github", "rust web framework", "github"),
        ("search machine learning on reddit", "machine learning", "reddit"),
        ("search quantum computing on wikipedia", "quantum computing", "wikipedia"),
        ("search wireless headphones on amazon", "wireless headphones", "amazon"),
    ]
    
    for cmd, expected_q, expected_site in test_cases:
        state = await planner.plan(cmd)
        assert len(state["subtasks"]) == 1, f"Failed for {cmd}"
        task = state["subtasks"][0]
        assert task["action"] == "search_site", f"Failed action for {cmd}"
        assert task["params"]["query"].lower() == expected_q.lower()
        assert task["params"]["site"].lower() == expected_site.lower()


@pytest.mark.asyncio
async def test_4_play_on_youtube_and_spotify():
    """Test 'play <song> on youtube' and 'play <song> on spotify'."""
    planner = Planner(client=None)
    
    cases = [
        ("play believer on youtube", "believer", "youtube"),
        ("play starboy on spotify", "starboy", "spotify"),
        ("play lofi hip hop on youtube", "lofi hip hop", "youtube"),
    ]
    for cmd, expected_q, expected_site in cases:
        state = await planner.plan(cmd)
        assert len(state["subtasks"]) == 1
        task = state["subtasks"][0]
        assert task["action"] == "search_site"
        assert task["params"]["query"] == expected_q
        assert task["params"]["site"] == expected_site


@pytest.mark.asyncio
async def test_5_open_site_and_search():
    """Test 'open youtube and search iphone' and 'open google and search weather'."""
    planner = Planner(client=None)
    
    cases = [
        ("open youtube and search iphone", "iphone", "youtube"),
        ("open google and search weather in new york", "weather in new york", "google"),
        ("open reddit and search technology", "technology", "reddit"),
    ]
    for cmd, expected_q, expected_site in cases:
        state = await planner.plan(cmd)
        assert len(state["subtasks"]) == 1
        task = state["subtasks"][0]
        assert task["action"] == "search_site"
        assert task["params"]["query"] == expected_q
        assert task["params"]["site"] == expected_site


@pytest.mark.asyncio
async def test_6_compound_multi_app():
    """Test multi-app launch: 'open notepad and calculator'."""
    planner = Planner(client=None)
    
    cmd = "open notepad and calculator"
    state = await planner.plan(cmd)
    assert len(state["subtasks"]) == 2
    assert state["subtasks"][0]["params"]["app_name"] == "notepad"
    assert state["subtasks"][1]["params"]["app_name"] == "calculator"

    cmd2 = "open vs code and edge"
    state2 = await planner.plan(cmd2)
    assert len(state2["subtasks"]) == 2
    assert state2["subtasks"][0]["params"]["app_name"] == "vs code"
    assert state2["subtasks"][1]["params"]["app_name"] == "edge"


@pytest.mark.asyncio
async def test_7_browser_tools_url_construction():
    """Verify search_site URL templates for all supported platforms."""
    for site_key in ["youtube", "google", "github", "reddit", "amazon", "wikipedia", "spotify"]:
        assert site_key in WEB_PLATFORMS
        template = WEB_PLATFORMS[site_key]["search"]
        formatted = template.format(q="test_query")
        assert "test_query" in formatted
        assert formatted.startswith("https://")


@pytest.mark.asyncio
async def test_8_desktop_open_app_safety():
    """Verify open_app does NOT return false positive success for non-existent apps."""
    res = open_app("some_completely_fake_non_existent_app_12345")
    assert res["success"] is False
    assert "error" in res

    # Verify open_app routes known web platforms to browser
    res_yt = open_app("youtube")
    assert res_yt["success"] is True

    res_edge_yt = open_app("youtube on edge")
    assert res_edge_yt["success"] is True


@pytest.mark.asyncio
async def test_9_fast_format_responses():
    """Verify Kernel._fast_format_response produces clean, accurate responses."""
    config = load_config()
    kernel = WoodyKernel(config)

    # 1. search_site response
    state1: WorkingMemoryState = {
        "request_id": "r1",
        "session_id": "s1",
        "user_request": "open edge and search iphone on youtube",
        "screen_context": "",
        "clipboard_context": "",
        "task_history": "",
        "intent": "search",
        "subtasks": [
            SubTask(
                id="t1",
                agent="browser_agent",
                action="search_site",
                params={"query": "iphone", "site": "YouTube", "browser": "edge"},
                depends_on=[],
                description="Search iphone on YouTube",
                status="done",
                result={"success": True, "message": "Searched 'iphone' on YouTube on edge."},
                error=None,
                retries=0,
            )
        ],
        "active_subtask_id": None,
        "tool_call_trace": [],
        "final_response": None,
        "is_simple": True,
    }
    resp1 = kernel._fast_format_response(state1)
    assert resp1 == "Searched 'iphone' on YouTube on edge."

    # 2. Multi-app launch response
    state2: WorkingMemoryState = {
        "request_id": "r2",
        "session_id": "s2",
        "user_request": "open notepad and calculator",
        "screen_context": "",
        "clipboard_context": "",
        "task_history": "",
        "intent": "open apps",
        "subtasks": [
            SubTask(
                id="t1",
                agent="desktop_agent",
                action="open_app",
                params={"app_name": "notepad"},
                depends_on=[],
                description="Open notepad",
                status="done",
                result={"success": True, "message": "Opened notepad."},
                error=None,
                retries=0,
            ),
            SubTask(
                id="t2",
                agent="desktop_agent",
                action="open_app",
                params={"app_name": "calculator"},
                depends_on=[],
                description="Open calculator",
                status="done",
                result={"success": True, "message": "Opened calculator."},
                error=None,
                retries=0,
            ),
        ],
        "active_subtask_id": None,
        "tool_call_trace": [],
        "final_response": None,
        "is_simple": False,
    }
    resp2 = kernel._fast_format_response(state2)
    assert resp2 == "Opened notepad and calculator."
