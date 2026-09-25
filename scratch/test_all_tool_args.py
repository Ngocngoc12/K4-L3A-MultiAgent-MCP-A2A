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
    case_id = case_1["case_id"]
    claimed_order_id = case_1["customer_request"]["claimed_order_id"]

    async with connect_gateway(settings.mcp_endpoint, settings.team_api_key, contracts) as gateway:
        print("Testing get_order argument variations...")
        arg_variations = [
            {"case_id": case_id, "order_id": claimed_order_id},
            {"case_id": case_id, "id": claimed_order_id},
            {"case_id": case_id, "order": claimed_order_id},
            {"case_id": case_id, "claimed_order_id": claimed_order_id},
            {"order_id": claimed_order_id},
            {"case_id": case_id},
        ]
        for args in arg_variations:
            try:
                res = await gateway._session.call_tool("get_order", arguments=args)
                is_err = getattr(res, "isError", getattr(res, "is_error", False))
                content = [b.text for b in res.content if hasattr(b, "text")]
                print(f"args={args} -> isError={is_err}, content={content}")
                if not is_err:
                    print("SUCCESS:", getattr(res, "structuredContent", getattr(res, "structured_content", None)))
            except Exception as e:
                print(f"args={args} EXCEPTION:", e)

        print("\nTesting get_policy argument variations...")
        pol_variations = [
            {"case_id": case_id, "policy_version": "EC_POLICY_V1"},
            {"case_id": case_id, "version": "EC_POLICY_V1"},
            {"case_id": case_id, "policy": "EC_POLICY_V1"},
            {"policy_version": "EC_POLICY_V1"},
            {"case_id": case_id},
        ]
        for args in pol_variations:
            try:
                res = await gateway._session.call_tool("get_policy", arguments=args)
                is_err = getattr(res, "isError", getattr(res, "is_error", False))
                content = [b.text for b in res.content if hasattr(b, "text")]
                print(f"args={args} -> isError={is_err}, content={content}")
                if not is_err:
                    print("SUCCESS:", getattr(res, "structuredContent", getattr(res, "structured_content", None)))
            except Exception as e:
                print(f"args={args} EXCEPTION:", e)

if __name__ == "__main__":
    asyncio.run(main())
