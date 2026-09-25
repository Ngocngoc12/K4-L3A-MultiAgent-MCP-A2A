import asyncio
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path("src").resolve()))

import httpx2
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client

from student_agent.config import Settings
from student_agent.contracts import Contracts

async def test_header(header_dict, name):
    root = Path(".").resolve()
    settings = Settings.load(root)
    contracts = Contracts(root / "contracts" / "schemas")
    
    timeout = httpx2.Timeout(300.0, connect=30.0, write=30.0, pool=30.0)
    try:
        async with (
            httpx2.AsyncClient(headers=header_dict, timeout=timeout) as http_client,
            streamable_http_client(settings.mcp_endpoint, http_client=http_client) as (read_stream, write_stream),
            ClientSession(read_stream, write_stream) as session,
        ):
            await session.initialize()
            res = await session.call_tool("get_policy", arguments={"case_id": "L3A_CASE_001", "policy_version": "EC_POLICY_V1"})
            is_err = getattr(res, "isError", getattr(res, "is_error", False))
            text = [b.text for b in res.content if hasattr(b, "text")]
            print(f"Header test '{name}': isError={is_err}, content={text}")
            if not is_err:
                sc = getattr(res, "structuredContent", getattr(res, "structured_content", None))
                print(f"SUCCESS '{name}' structuredContent:", sc)
    except Exception as e:
        print(f"Header test '{name}' exception:", e)

async def main():
    root = Path(".").resolve()
    settings = Settings.load(root)
    key = settings.team_api_key

    await test_header({"Authorization": f"Bearer {key}"}, "Bearer Key")
    await test_header({"Authorization": key}, "Direct Key")
    await test_header({"x-team-key": key}, "x-team-key")
    await test_header({"x-api-key": key}, "x-api-key")

if __name__ == "__main__":
    asyncio.run(main())
