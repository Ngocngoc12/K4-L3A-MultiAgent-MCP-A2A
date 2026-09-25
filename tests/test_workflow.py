from __future__ import annotations

import asyncio
import json
from pathlib import Path
from unittest.mock import AsyncMock

from student_agent.contracts import Contracts
from student_agent.mcp_gateway import EvidenceGateway
from student_agent.trace import TraceWriter
from student_agent.workflow import solve_case


def test_solve_case_workflow_execution(tmp_path: Path) -> None:
    async def _run() -> None:
        root = Path(__file__).resolve().parents[1]
        contracts = Contracts(root / "contracts" / "schemas")
        trace_path = tmp_path / "traces" / "trace.jsonl"
        trace = TraceWriter(trace_path, contracts)

        # Mock gateway
        mock_gateway = AsyncMock(spec=EvidenceGateway)
        mock_gateway.list_tools.return_value = ["get_order", "get_payment", "get_shipment", "get_policy"]
        
        mock_gateway.call.side_effect = lambda tool_name, case_id, **kwargs: {
            "schema_version": "day09-mcp-evidence-v1",
            "evidence_ref": f"ev_test_{tool_name}_12345678901234567890",
            "result_hash": "sha256:" + "a" * 64,
            "domain": "order" if "order" in tool_name else ("payment" if "payment" in tool_name else ("shipment" if "shipment" in tool_name else "policy")),
            "data": {
                "order_id": kwargs.get("order_id", "ORD_100"),
                "order_status": "canceled",
                "payment_value": 150.50,
                "seller_id": "SEL_200",
                "shipment_id": "SHIP_300"
            }
        }

        sample_case = {
            "case_id": "L3A_CASE_TEST",
            "order_id": "ORD_100",
            "claims": [
                {"claim_id": "CLM_001", "order_id": "ORD_100", "description": "Order canceled but charged"}
            ]
        }

        output = await solve_case(sample_case, mock_gateway, trace)

        # Validate output contract
        contracts.validate_output(output, "outputs/L3A_CASE_TEST.json")
        assert output["case_id"] == "L3A_CASE_TEST"
        assert output["assessment"]["primary_issue"] == "canceled_order_paid"
        assert output["assessment"]["case_status"] == "action_required"
        assert len(output["evidence_refs"]) > 0

        # Validate trace events contract
        lines = trace_path.read_text(encoding="utf-8").splitlines()
        assert len(lines) >= 5
        for line in lines:
            event = json.loads(line)
            contracts.validate_trace(event, "trace event")

    asyncio.run(_run())
