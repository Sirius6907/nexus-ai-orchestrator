import httpx, asyncio
async def test():
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.post('http://localhost:11434/api/chat', json={'model': 'gemma3:1b', 'messages': [{'role': 'user', 'content': 'hi', 'images': ['iVBORw0K']}]})
            print(resp.status_code)
            print(resp.text)
    except Exception as e:
        print(e)
asyncio.run(test())
