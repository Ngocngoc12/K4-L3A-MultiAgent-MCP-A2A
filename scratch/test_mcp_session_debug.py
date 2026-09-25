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

    async with connect_gateway(settings.mcp_endpoint, settings.team_api_key, contracts) as gateway:
        print("Initialized session successfully!")
        
        # Test get_policy for various versions
        for ver in ["EC_POLICY_V1", "v1", "V1", "policy_v1"]:
            try:
                res = await gateway._session.call_tool("get_policy", arguments={"case_id": "L3A_CASE_001", "policy_version": ver})
                is_err = getattr(res, "isError", getattr(res, "is_error", False))
                print(f"get_policy(ver={ver}): isErr={is_err}, content={[b.text for b in res.content]}")
                if not is_err:
                    print("SUCCESS:", getattr(res, "structuredContent", getattr(res, "structured_content", None)))
            except Exception as e:
                print(f"get_policy(ver={ver}) EXCEPTION:", e)

        # Test get_order for various case_ids / order_ids across cases 1 to 20
        for i in range(1, 21):
            cid = f"L3A_CASE_{i:03d}"
            case_file = root / "inputs" / f"{cid}.json"
            if not case_file.exists():
                continue
            with case_file.open("r", encoding="utf-8") as f:
                cdata = json.load(f)
            oid = cdata.get("customer_request", {}).get("claimed_order_id")
            
            try:
                res = await gateway._session.call_tool("get_order", arguments={"case_id": cid, "order_id": oid})
                is_err = getattr(res, "isError", getattr(res, "is_error", False))
                if not is_err:
                    print(f"get_order SUCCESS for {cid} (order_id={oid}):")
                    print(getattr(res, "structuredContent", getattr(res, "structured_content", None)))
                else:
                    err_msg = [b.text for b in res.content if hasattr(b, "text")]
                    print(f"get_order {cid} ({oid}): isErr=True -> {err_msg}")
            except Exception as e:
                print(f"get_order {cid} EXCEPTION:", e)

if __name__ == "__main__":
    asyncio.run(main())
