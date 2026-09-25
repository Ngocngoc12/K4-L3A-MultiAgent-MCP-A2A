import asyncio
import json
from pathlib import Path
from student_agent.config import Settings
from student_agent.contracts import Contracts
from student_agent.mcp_gateway import connect_gateway

async def main():
    root = Path(".")
    settings = Settings.load(root)
    contracts = Contracts(root / "contracts" / "schemas")
    async with connect_gateway(settings.mcp_endpoint, settings.team_api_key, contracts) as gateway:
        tools = await gateway.list_tools()
        print("Tools:", tools)
        
        # Test case 1
        case_id = "L3A_CASE_001"
        order_id = "e2a03ccf5ea816036608b2d8c3ab8e60"
        
        print("\n--- Testing get_order ---")
        try:
            ev = await gateway.call("get_order", case_id=case_id, order_id=order_id)
            print(json.dumps(ev, indent=2))
        except Exception as e:
            print("Error get_order:", e)

        print("\n--- Testing get_order_payments ---")
        try:
            ev = await gateway.call("get_order_payments", case_id=case_id, order_id=order_id)
            print(json.dumps(ev, indent=2))
        except Exception as e:
            print("Error get_order_payments:", e)

        print("\n--- Testing get_payment_timeline ---")
        try:
            ev = await gateway.call("get_payment_timeline", case_id=case_id, order_id=order_id)
            print(json.dumps(ev, indent=2))
        except Exception as e:
            print("Error get_payment_timeline:", e)

        print("\n--- Testing get_refund_timeline ---")
        try:
            ev = await gateway.call("get_refund_timeline", case_id=case_id, order_id=order_id)
            print(json.dumps(ev, indent=2))
        except Exception as e:
            print("Error get_refund_timeline:", e)

        print("\n--- Testing get_shipment_summary ---")
        try:
            ev = await gateway.call("get_shipment_summary", case_id=case_id, order_id=order_id)
            print(json.dumps(ev, indent=2))
        except Exception as e:
            print("Error get_shipment_summary:", e)

        print("\n--- Testing get_policy ---")
        try:
            ev = await gateway.call("get_policy", case_id=case_id, policy_version="EC_POLICY_V1")
            print(json.dumps(ev, indent=2))
        except Exception as e:
            print("Error get_policy:", e)

if __name__ == "__main__":
    asyncio.run(main())
