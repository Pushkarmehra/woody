import asyncio
from woody.planner.planner import Planner

queries = [
    "add a reminder in my calander of 15 sep about my birthday in google calender",
    "add reminder in my calendar of 15 sep about my birthday in google calender",
    "add a reminder on 15 sep for my birthday in google calendar",
    "set a reminder for birthday on 15 september in google calendar",
    "add my birthday on 15 sep in google calender",
    "remind me on 15 sep about my birthday in google calendar",
    "add birthday reminder on 15 sep in google calander",
    "schedule my birthday party on 15 sep in google calendar",
    "add a reminder in my calander of 15 sep about my birthday",
    "add event to calendar tomorrow at 3pm",
    "remind me to buy milk tomorrow at 5pm"
]

async def main():
    p = Planner(client=None)
    for q in queries:
        state = await p.plan(q)
        subtasks = state.get("subtasks", [])
        print(f"Q: {q}")
        print(f"   Subtasks count: {len(subtasks)}")
        for st in subtasks:
            agent = st.get("agent")
            action = st.get("action")
            params = st.get("params", {})
            title = params.get("title") or params.get("text")
            date = params.get("date_str")
            gcal = params.get("open_google_calendar")
            print(f"     -> {agent}.{action} | title: '{title}' | date: '{date}' | gcal: {gcal}")
        print()

if __name__ == "__main__":
    asyncio.run(main())
