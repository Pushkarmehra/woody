import asyncio
from woody.utils.groq_client import GroqClient, Message

code_text = """
1 #include <iostream>
2
3 using namespace std
4
5 int main()
6 {
7    int number = 10
8    cout << "The number is: " << number << endl
9
10   if (number > 5)
11      cout << "Number is greater than 5" << endl;
12   else
13      cout << "Number is 5 or less" << endl
14
15   return 0
16 }
"""

synth_prompt = f"""Active Focused Window: 'Online C++ Compiler - Programiz - Microsoft Edge'
Visible Screen / Code Text:
{code_text}

User Intent: whats wrong with this code on my screen

Instructions:
The user is asking what is wrong with the code on their screen. Carefully inspect the visible code, identify any syntax errors, missing semicolons, or bugs, explain what is wrong clearly, and provide the corrected code snippet.
"""

async def test():
    client = GroqClient()
    resp = await client.chat(
        messages=[
            Message(role="system", content="You are Woody, an intelligent operating system assistant with real-time screen awareness."),
            Message(role="user", content=synth_prompt),
        ],
        temperature=0.2,
    )
    import sys
    print("Tokens:", resp.prompt_tokens, resp.completion_tokens)
    sys.stdout.buffer.write(resp.content.encode("utf-8"))
    sys.stdout.buffer.write(b"\n")

if __name__ == "__main__":
    asyncio.run(test())
