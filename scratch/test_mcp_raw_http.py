import asyncio
import json
import httpx2

async def main():
    api_key = "sk-team-yhQE7ZEuWL2GaKL05tJ1NOYVDV1RQGlzhnamVvTZ4H4"
    mcp_url = "https://day09-competition.34-142-201-239.sslip.io/mcp"
    
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }

    # JSON-RPC request for MCP
    payload_list = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/list",
        "params": {}
    }

    payload_call = {
        "jsonrpc": "2.0",
        "id": 2,
        "method": "tools/call",
        "params": {
            "name": "get_order",
            "arguments": {
                "case_id": "L3A_CASE_001",
                "order_id": "e2a03ccf5ea816036608b2d8c3ab8e60"
            }
        }
    }

    async with httpx2.AsyncClient(headers=headers, timeout=30.0) as client:
        print("--- Testing POST tools/list ---")
        try:
            r1 = await client.post(mcp_url, json=payload_list)
            print("Status:", r1.status_code)
            print("Body:", r1.text[:500])
        except Exception as e:
            print("Error:", e)

        print("\n--- Testing POST tools/call ---")
        try:
            r2 = await client.post(mcp_url, json=payload_call)
            print("Status:", r2.status_code)
            print("Body:", r2.text[:1000])
        except Exception as e:
            print("Error:", e)

if __name__ == "__main__":
    asyncio.run(main())
