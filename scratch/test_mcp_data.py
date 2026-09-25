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

    results = {}
    async with connect_gateway(settings.mcp_endpoint, settings.team_api_key, contracts) as gateway:
        case_id = case_1["case_id"]
        order_id = case_1["customer_request"]["claimed_order_id"]
        policy_version = case_1.get("policy_version", "EC_POLICY_V1")

        results["case"] = case_1

        try:
            results["get_order"] = await gateway.call("get_order", case_id=case_id, order_id=order_id)
        except Exception as e:
            results["get_order_error"] = str(e)

        try:
            results["get_order_items"] = await gateway.call("get_order_items", case_id=case_id, order_id=order_id)
        except Exception as e:
            results["get_order_items_error"] = str(e)

        try:
            results["get_order_payments"] = await gateway.call("get_order_payments", case_id=case_id, order_id=order_id)
        except Exception as e:
            results["get_order_payments_error"] = str(e)

        try:
            results["get_shipment_summary"] = await gateway.call("get_shipment_summary", case_id=case_id, order_id=order_id)
        except Exception as e:
            results["get_shipment_summary_error"] = str(e)

        try:
            results["get_policy"] = await gateway.call("get_policy", case_id=case_id, policy_version=policy_version)
        except Exception as e:
            results["get_policy_error"] = str(e)

    (root / "scratch" / "mcp_dump.json").write_text(json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8")

if __name__ == "__main__":
    asyncio.run(main())
