import asyncio
from woody.utils.groq_client import GroqClient, Message
from woody.tools.tool_registry import init_registry, get_tool_schemas

async def main():
    init_registry()
    tools = get_tool_schemas()
    client = GroqClient()
    await client.__aenter__()
    goal = 'Open Google Calendar in a web browser, sign in if necessary, create a new event on September 15 titled "Birthday" with a reminder, and save it.'
    resp = await client.chat(model='openai/gpt-oss-120b', messages=[Message(role='user', content=goal)], tools=tools)
    print('TOOL_CALLS:', resp.tool_calls)
    await client.__aexit__(None, None, None)

if __name__ == '__main__':
    asyncio.run(main())
