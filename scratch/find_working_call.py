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
    
    input_files = list((root / "inputs").glob("*.json"))
    
    async with connect_gateway(settings.mcp_endpoint, settings.team_api_key, contracts) as gateway:
        print("Testing tool calls across first 10 cases...")
        for p in input_files[:10]:
            with p.open("r", encoding="utf-8") as f:
                c = json.load(f)
            case_id = c["case_id"]
            cust_req = c.get("customer_request", {})
            oid = cust_req.get("claimed_order_id") or c.get("order_id")
            
            print(f"\n--- Case {case_id} (order_id={oid}) ---")
            
            # Test get_order
            try:
                res = await gateway.call("get_order", case_id=case_id, order_id=oid)
                print(f"  get_order SUCCESS! ref={res.get('evidence_ref')}")
                print(f"  data={json.dumps(res.get('data'), ensure_ascii=False)}")
            except Exception as e:
                print(f"  get_order FAILED: {e}")

            # Test get_policy
            try:
                pol = c.get("policy_version", "EC_POLICY_V1")
                res = await gateway.call("get_policy", case_id=case_id, policy_version=pol)
                print(f"  get_policy SUCCESS! ref={res.get('evidence_ref')}")
                print(f"  data={json.dumps(res.get('data'), ensure_ascii=False)}")
            except Exception as e:
                print(f"  get_policy FAILED: {e}")

if __name__ == "__main__":
    asyncio.run(main())
