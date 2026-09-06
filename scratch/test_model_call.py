import asyncio
from woody.utils.groq_client import GroqClient, Message

async def test():
    client = GroqClient()
    for model_name in ["llama-3.1-8b-instant", "llama-3.3-70b-versatile", "openai/gpt-oss-120b", "openai/gpt-oss-20b"]:
        try:
            resp = await client.chat(model=model_name, messages=[Message(role="user", content="hi")])
            print(f"Model '{model_name}' -> SUCCESS ({resp.model})")
        except Exception as e:
            print(f"Model '{model_name}' -> FAILED: {e}")

asyncio.run(test())
