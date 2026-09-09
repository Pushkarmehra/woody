import pytest
import pytest_asyncio
from woody.planner.planner import Planner
from woody.agents.vision_agent import VisionAgent
from woody.tools.builtin.desktop_tools import analyze_screen, extract_screen_text

@pytest.mark.asyncio
async def test_planner_routing_code_on_screen():
    planner = Planner(client=None)

    queries = [
        "whats wrong with this code on my screen",
        "what's wrong with this code on my screen",
        "whats wrong on my screen",
        "what is wrong with this code",
        "check this code on screen",
        "bug in this code",
        "debug this code on screen",
    ]

    for q in queries:
        state = await planner.plan(q)
        assert len(state["subtasks"]) >= 1, f"Failed on query: {q}"
        task = state["subtasks"][0]
        assert task["agent"] == "vision_agent", f"Expected vision_agent for '{q}', got {task['agent']}"
        assert task["action"] == "analyze_screen", f"Expected analyze_screen for '{q}', got {task['action']}"


def test_analyze_screen_tool_with_ocr():
    res = analyze_screen(custom_prompt="whats wrong with this code on my screen")
    assert res.get("success") is True
    assert "active_window" in res
    assert "open_windows" in res
    assert "screenshot_path" in res
    assert "analysis" in res


@pytest.mark.asyncio
async def test_vision_agent_code_analysis():
    class DummyGroqClient:
        async def chat(self, messages, temperature=0.2, max_tokens=250):
            class Resp:
                content = "The code is missing semicolons on lines 3, 7, 8, and 13. Add ';' at the end of each statement."
            return Resp()

    agent = VisionAgent(llm_client=DummyGroqClient())
    result = await agent.execute_action(
        action="analyze_screen",
        params={"custom_prompt": "whats wrong with this code on my screen"},
        context={"user_request": "whats wrong with this code on my screen"},
    )
    assert result.success is True
    assert "analysis" in result.output
    assert "missing semicolons" in result.output["analysis"].lower()
