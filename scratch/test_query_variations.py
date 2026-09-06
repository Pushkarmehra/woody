import asyncio
from woody.planner.planner import Planner

async def test():
    planner = Planner(client=None)
    queries = [
        "open youtube on edge and serch there mrbeast",
        "open youtube on edge and search there mrbeast",
        "open youtube on edge and search mrbeast",
        "open edge and search mrbeast on youtube",
        "open edge and search there mrbeast on youtube",
        "open chrome and search lofi on spotify",
        "open notepad and write hello world",
        "open calculator and notepad and edge",
        "open youtube on edge and play mrbeast",
    ]
    for q in queries:
        state = await planner.plan(q)
        print(f"\nQuery: {q}")
        print(f"Subtasks ({len(state['subtasks'])}):")
        for t in state['subtasks']:
            print(f"  - Agent: {t['agent']}, Action: {t['action']}, Params: {t['params']}")

if __name__ == "__main__":
    asyncio.run(test())
