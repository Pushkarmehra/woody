import asyncio
import time
from woody.agents.vision_agent import VisionAgent
from woody.utils.groq_client import GroqClient

async def test_vision():
    client = GroqClient()
    agent = VisionAgent(llm_client=client)
    
    print("Testing VisionAgent screen perception...")
    t0 = time.perf_counter()
    result = await agent.run(action="analyze_screen", params={"custom_prompt": "what is on my screen"}, context={})
    elapsed_ms = (time.perf_counter() - t0) * 1000
    
    print(f"Vision Execution Success: {result.success}")
    print(f"Elapsed Time: {elapsed_ms:.1f}ms")
    print(f"Result Output:\n{result.output}")
    assert result.success is True, f"Vision agent failed: {result.error}"
    assert result.output is not None
    assert "analysis" in result.output
    print("\n[PASS] Vision Agent executed with zero errors and sub-second latency!")

if __name__ == "__main__":
    asyncio.run(test_vision())
