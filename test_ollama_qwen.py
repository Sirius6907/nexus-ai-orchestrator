import httpx, asyncio
async def test():
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.post('http://localhost:11434/api/chat', json={'model': 'qwen3.5:0.8b', 'messages': [{'role': 'user', 'content': 'hi'}]})
            print(resp.status_code)
            print(resp.text)
    except Exception as e:
        print(e)
asyncio.run(test())
