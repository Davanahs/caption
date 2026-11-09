
import asyncio
import httpx
import sys

async def main():
    async with httpx.AsyncClient() as client:
        # Create 10 dummy jobs via API if there's an endpoint for it, or just hit health/jobs
        tasks = []
        for _ in range(25):
            tasks.append(client.get("http://localhost:8111/api/health"))
            tasks.append(client.get("http://localhost:8111/api/videos"))
        res = await asyncio.gather(*tasks, return_exceptions=True)
        errors = [r for r in res if isinstance(r, Exception)]
        print(f"Completed {len(res)} concurrent requests. {len(errors)} errors.")
asyncio.run(main())
        