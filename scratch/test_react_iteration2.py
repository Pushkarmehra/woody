import asyncio
from woody.utils.groq_client import GroqClient, Message
from woody.tools.tool_registry import init_registry, get_tool_schemas

async def main():
    init_registry()
    tools = get_tool_schemas()
    client = GroqClient()
    await client.__aenter__()
    goal = 'add a reminder in my calander of 15 sep about my birthday in google calender'
    messages = [
        Message(role='system', content='You are Woody, a desktop AI assistant.'),
        Message(role='user', content=goal),
        Message(role='assistant', content='', tool_calls=[{'id': 'call_1', 'type': 'function', 'function': {'name': 'open_url', 'arguments': '{"url": "https://calendar.google.com"}'}}]),
        Message(role='tool', tool_call_id='call_1', name='open_url', content='{"success": true, "message": "Opened https://calendar.google.com"}')
    ]
    resp = await client.chat(model='openai/gpt-oss-120b', messages=messages, tools=tools)
    print('ITERATION 2 TOOL CALLS:', resp.tool_calls)
    print('ITERATION 2 CONTENT:', resp.content)
    await client.__aexit__(None, None, None)

if __name__ == '__main__':
    asyncio.run(main())
