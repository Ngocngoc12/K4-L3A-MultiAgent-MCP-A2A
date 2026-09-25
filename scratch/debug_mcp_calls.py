import asyncio
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path("src").resolve()))

from student_agent.config import Settings
from student_agent.contracts import Contracts
from student_agent.mcp_gateway import connect_gateway

async def main():
    root = Path(".").resolve()
    settings = Settings.load(root)
    contracts = Contracts(root / "contracts" / "schemas")
    
    with (root / "inputs" / "L3A_CASE_001.json").open("r", encoding="utf-8") as f:
        case_1 = json.load(f)

    with (root / "inputs" / "L3A_CASE_005.json").open("r", encoding="utf-8") as f:
        case_5 = json.load(f)

    async with connect_gateway(settings.mcp_endpoint, settings.team_api_key, contracts) as gateway:
        print("Tools list:")
        tools = await gateway.list_tools()
        print(tools)

        # Test tool call with raw session to get raw response
        try:
            res_raw = await gateway._session.call_tool("get_order", arguments={"case_id": "L3A_CASE_001", "order_id": case_1["customer_request"]["claimed_order_id"]})
            print("Raw get_order Case 1:")
            print("isError:", getattr(res_raw, "isError", getattr(res_raw, "is_error", False)))
            print("content:", res_raw.content)
        except Exception as e:
            print("Exception get_order Case 1:", e)

        try:
            res_raw5 = await gateway._session.call_tool("get_order", arguments={"case_id": "L3A_CASE_005", "order_id": case_5["customer_request"]["claimed_order_id"]})
            print("Raw get_order Case 5:")
            print("isError:", getattr(res_raw5, "isError", getattr(res_raw5, "is_error", False)))
            print("content:", res_raw5.content)
        except Exception as e:
            print("Exception get_order Case 5:", e)

        try:
            res_pol = await gateway._session.call_tool("get_policy", arguments={"case_id": "L3A_CASE_001", "policy_version": "EC_POLICY_V1"})
            print("Raw get_policy Case 1:")
            print("isError:", getattr(res_pol, "isError", getattr(res_pol, "is_error", False)))
            print("content:", res_pol.content)
        except Exception as e:
            print("Exception get_policy Case 1:", e)

if __name__ == "__main__":
    asyncio.run(main())
