import asyncio
import httpx2

async def main():
    key = "sk-team-yhQE7ZEuWL2GaKL05tJ1NOYVDV1RQGlzhnamVvTZ4H4"
    urls = [
        "https://n7-competition.pages.dev/api/mcp",
        "https://n7-competition.pages.dev/mcp",
        "https://n7-competition.pages.dev/api/verify",
        "https://day09-competition.34-142-201-239.sslip.io/mcp",
        "https://day09-competition.34-142-201-239.sslip.io/api/mcp",
    ]

    headers = {
        "Authorization": f"Bearer {key}",
        "x-team-key": key,
    }

    async with httpx2.AsyncClient(headers=headers, timeout=10.0) as client:
        for url in urls:
            try:
                res = await client.get(url)
                print(f"GET {url} -> {res.status_code} {res.text[:200]}")
            except Exception as e:
                print(f"GET {url} ERROR: {e}")

if __name__ == "__main__":
    asyncio.run(main())
