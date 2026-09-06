import asyncio
import os
import httpx
from woody.utils.groq_client import GroqClient, Message
from woody.tools.tool_registry import get_tool_schemas

async def main():
    client = GroqClient()
    print("API Key exists:", bool(client.api_key))
    models = await client.list_models()
    print("Available Groq models:", models)

    # Test basic chat with default model
    try:
        resp = await client.chat(model=client.default_model, messages=[Message(role="user", content="hello")])
        print("Chat response with default model:", resp.content[:100])
    except Exception as e:
        print("Chat error default model:", e)

    # Test with tools
    tools = get_tool_schemas()
    print(f"Total tools: {len(tools)}")
    try:
        resp = await client.chat(model=client.default_model, messages=[Message(role="user", content="open notepad")], tools=tools)
        print("Tool chat response:", resp)
    except Exception as e:
        print("Tool chat error:", e)

if __name__ == "__main__":
    asyncio.run(main())
