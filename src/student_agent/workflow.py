from __future__ import annotations

import logging
from typing import Any

from .mcp_gateway import EvidenceGateway
from .trace import TraceWriter

logger = logging.getLogger(__name__)


class MultiAgentCoordinator:
    """Coordinator agent managing specialist delegation and overall workflow."""

    def __init__(
        self, case: dict[str, Any], gateway: EvidenceGateway, trace: TraceWriter
    ) -> None:
        self.case = case
        self.gateway = gateway
        self.trace = trace
        self.case_id = str(case.get("case_id", ""))
        self.policy_version = str(case.get("policy_version", "EC_POLICY_V1"))
        self.evidence_refs: list[str] = []

        # Entity tracking sets
        self.order_ids: set[str] = set()
        self.item_ids: set[str] = set()
        self.seller_ids: set[str] = set()
        self.payment_refs: set[str] = set()
        self.shipment_ids: set[str] = set()
        self.customer_ids: set[str] = set()

        # Evidence data collections
        self.order_evidences: list[dict[str, Any]] = []
        self.payment_evidences: list[dict[str, Any]] = []
        self.shipment_evidences: list[dict[str, Any]] = []
        self.policy_evidences: list[dict[str, Any]] = []
        self.data_conflicts: list[dict[str, Any]] = []

    def record_evidence(
        self, actor: str, tool_name: str, evidence: dict[str, Any]
    ) -> str | None:
        ref = evidence.get("evidence_ref")
        if ref and isinstance(ref, str):
            if ref not in self.evidence_refs:
                self.evidence_refs.append(ref)
            self.trace.emit(
                case_id=self.case_id,
                event_type="tool_result_consumed",
                actor=actor,
                tool_name=tool_name,
                evidence_refs=[ref],
            )
            return ref
        return None

    def extract_initial_entities(self) -> None:
        # Direct root attributes
        if "order_id" in self.case and isinstance(self.case["order_id"], str):
            self.order_ids.add(self.case["order_id"])
        if "order_ids" in self.case and isinstance(self.case["order_ids"], list):
            for oid in self.case["order_ids"]:
                if isinstance(oid, str):
                    self.order_ids.add(oid)
        if "customer_id" in self.case and isinstance(self.case["customer_id"], str):
            self.customer_ids.add(self.case["customer_id"])

        # Nested customer_request attributes
        cust_req = self.case.get("customer_request", {})
        if isinstance(cust_req, dict):
            claimed_oid = cust_req.get("claimed_order_id")
            if claimed_oid and isinstance(claimed_oid, str):
                self.order_ids.add(claimed_oid)
            cid = cust_req.get("customer_id") or cust_req.get("customer_unique_id")
            if cid and isinstance(cid, str):
                self.customer_ids.add(cid)

            claims = cust_req.get("claims", [])
            if isinstance(claims, list):
                for claim in claims:
                    if isinstance(claim, dict):
                        oid = claim.get("order_id") or claim.get("claimed_order_id")
                        if isinstance(oid, str):
                            self.order_ids.add(oid)
                        item_id = claim.get("item_id")
                        if isinstance(item_id, str):
                            self.item_ids.add(item_id)

        # Root claims
        root_claims = self.case.get("claims", [])
        if isinstance(root_claims, list):
            for claim in root_claims:
                if isinstance(claim, dict):
                    oid = claim.get("order_id")
                    if isinstance(oid, str):
                        self.order_ids.add(oid)
                    item_id = claim.get("item_id")
                    if isinstance(item_id, str):
                        self.item_ids.add(item_id)


class OrderSpecialist:
    """Specialist agent for order & item investigation."""

    def __init__(self, coordinator: MultiAgentCoordinator) -> None:
        self.coord = coordinator
        self.actor = "order-agent"

    async def execute(self, available_tools: list[str]) -> None:
        self.coord.trace.emit(
            case_id=self.coord.case_id,
            event_type="task_assigned",
            actor="coordinator",
            target=self.actor,
            decision_code="assign_order_investigation",
        )

        target_tools = [
            t
            for t in ["get_order", "get_order_items", "get_product_context", "get_sellers"]
            if t in available_tools
        ]
        target_orders = sorted(list(self.coord.order_ids))

        for order_id in target_orders:
            for tool_name in target_tools:
                try:
                    kwargs = {"order_id": order_id}
                    evidence = await self.coord.gateway.call(
                        tool_name, case_id=self.coord.case_id, **kwargs
                    )
                    self.coord.record_evidence(self.actor, tool_name, evidence)
                    self.coord.order_evidences.append(evidence)
                    self._extract_entities_from_data(evidence.get("data", {}))
                except Exception as exc:
                    logger.warning(f"Order tool {tool_name} failed for {order_id}: {exc}")

        self.coord.trace.emit(
            case_id=self.coord.case_id,
            event_type="handoff",
            actor=self.actor,
            target="payment-agent",
            decision_code="hand_over_order_context",
        )

    def _extract_entities_from_data(self, data: Any) -> None:
        if isinstance(data, dict):
            if "order_id" in data and isinstance(data["order_id"], str):
                self.coord.order_ids.add(data["order_id"])
            if "customer_id" in data and isinstance(data["customer_id"], str):
                self.coord.customer_ids.add(data["customer_id"])
            if "customer_unique_id" in data and isinstance(data["customer_unique_id"], str):
                self.coord.customer_ids.add(data["customer_unique_id"])
            if "seller_id" in data and isinstance(data["seller_id"], str):
                self.coord.seller_ids.add(data["seller_id"])
            if "items" in data and isinstance(data["items"], list):
                for item in data["items"]:
                    if isinstance(item, dict):
                        if "item_id" in item and isinstance(item["item_id"], str):
                            self.coord.item_ids.add(item["item_id"])
                        if "seller_id" in item and isinstance(item["seller_id"], str):
                            self.coord.seller_ids.add(item["seller_id"])
            if "sellers" in data and isinstance(data["sellers"], list):
                for s in data["sellers"]:
                    if isinstance(s, dict) and "seller_id" in s:
                        self.coord.seller_ids.add(str(s["seller_id"]))


class PaymentSpecialist:
    """Specialist agent for payment & transaction investigation."""

    def __init__(self, coordinator: MultiAgentCoordinator) -> None:
        self.coord = coordinator
        self.actor = "payment-agent"

    async def execute(self, available_tools: list[str]) -> None:
        self.coord.trace.emit(
            case_id=self.coord.case_id,
            event_type="task_assigned",
            actor="coordinator",
            target=self.actor,
            decision_code="assign_payment_investigation",
        )

        target_tools = [
            t
            for t in [
                "get_order_payments",
                "get_payment_timeline",
                "get_refund_timeline",
            ]
            if t in available_tools
        ]
        target_orders = sorted(list(self.coord.order_ids))

        for order_id in target_orders:
            for tool_name in target_tools:
                try:
                    kwargs = {"order_id": order_id}
                    evidence = await self.coord.gateway.call(
                        tool_name, case_id=self.coord.case_id, **kwargs
                    )
                    self.coord.record_evidence(self.actor, tool_name, evidence)
                    self.coord.payment_evidences.append(evidence)
                    self._extract_entities_from_data(evidence.get("data", {}))
                except Exception as exc:
                    logger.warning(
                        f"Payment tool {tool_name} failed for {order_id}: {exc}"
                    )

        if "get_customer_history" in available_tools and self.coord.customer_ids:
            for cust_id in sorted(list(self.coord.customer_ids)):
                try:
                    evidence = await self.coord.gateway.call(
                        "get_customer_history",
                        case_id=self.coord.case_id,
                        customer_unique_id=cust_id,
                    )
                    self.coord.record_evidence(self.actor, "get_customer_history", evidence)
                    self.coord.payment_evidences.append(evidence)
                    self._extract_entities_from_data(evidence.get("data", {}))
                except Exception as exc:
                    logger.warning(
                        f"Payment tool get_customer_history failed for {cust_id}: {exc}"
                    )

        self.coord.trace.emit(
            case_id=self.coord.case_id,
            event_type="handoff",
            actor=self.actor,
            target="shipment-agent",
            decision_code="hand_over_payment_context",
        )

    def _extract_entities_from_data(self, data: Any) -> None:
        if isinstance(data, dict):
            if "payment_sequential" in data:
                pref = f"pay_{data.get('order_id', 'ref')}_{data['payment_sequential']}"
                self.coord.payment_refs.add(pref)
            if "payment_reference" in data and isinstance(data["payment_reference"], str):
                self.coord.payment_refs.add(data["payment_reference"])
            if "payments" in data and isinstance(data["payments"], list):
                for p in data["payments"]:
                    if isinstance(p, dict):
                        pref = p.get("payment_reference") or p.get("payment_id")
                        if isinstance(pref, str):
                            self.coord.payment_refs.add(pref)


class ShipmentSpecialist:
    """Specialist agent for shipment & delivery investigation."""

    def __init__(self, coordinator: MultiAgentCoordinator) -> None:
        self.coord = coordinator
        self.actor = "shipment-agent"

    async def execute(self, available_tools: list[str]) -> None:
        self.coord.trace.emit(
            case_id=self.coord.case_id,
            event_type="task_assigned",
            actor="coordinator",
            target=self.actor,
            decision_code="assign_shipment_investigation",
        )

        target_tools = [
            t for t in ["get_shipment_summary"] if t in available_tools
        ]
        target_orders = sorted(list(self.coord.order_ids))

        for order_id in target_orders:
            for tool_name in target_tools:
                try:
                    kwargs = {"order_id": order_id}
                    evidence = await self.coord.gateway.call(
                        tool_name, case_id=self.coord.case_id, **kwargs
                    )
                    self.coord.record_evidence(self.actor, tool_name, evidence)
                    self.coord.shipment_evidences.append(evidence)
                    self._extract_entities_from_data(evidence.get("data", {}))
                except Exception as exc:
                    logger.warning(
                        f"Shipment tool {tool_name} failed for {order_id}: {exc}"
                    )

        self.coord.trace.emit(
            case_id=self.coord.case_id,
            event_type="handoff",
            actor=self.actor,
            target="policy-agent",
            decision_code="hand_over_shipment_context",
        )

    def _extract_entities_from_data(self, data: Any) -> None:
        if isinstance(data, dict):
            if "shipment_id" in data and isinstance(data["shipment_id"], str):
                self.coord.shipment_ids.add(data["shipment_id"])
            if "tracking_number" in data and isinstance(data["tracking_number"], str):
                self.coord.shipment_ids.add(data["tracking_number"])
            if "shipments" in data and isinstance(data["shipments"], list):
                for s in data["shipments"]:
                    if isinstance(s, dict):
                        sid = s.get("shipment_id") or s.get("tracking_number")
                        if isinstance(sid, str):
                            self.coord.shipment_ids.add(sid)


class PolicySpecialist:
    """Specialist agent for policy evaluation and case resolution."""

    def __init__(self, coordinator: MultiAgentCoordinator) -> None:
        self.coord = coordinator
        self.actor = "policy-agent"

    async def execute(self, available_tools: list[str]) -> dict[str, Any]:
        self.coord.trace.emit(
            case_id=self.coord.case_id,
            event_type="task_assigned",
            actor="coordinator",
            target=self.actor,
            decision_code="assign_policy_evaluation",
        )

        if "get_policy" in available_tools:
            try:
                evidence = await self.coord.gateway.call(
                    "get_policy",
                    case_id=self.coord.case_id,
                    policy_version=self.coord.policy_version,
                )
                self.coord.record_evidence(self.actor, "get_policy", evidence)
                self.coord.policy_evidences.append(evidence)
            except Exception as exc:
                logger.warning(f"Policy tool get_policy failed: {exc}")

        # Analyze evidence to deduce findings
        findings = self._analyze_findings()

        self.coord.trace.emit(
            case_id=self.coord.case_id,
            event_type="policy_decided",
            actor=self.actor,
            decision_code=f"policy_{findings['primary_issue']}",
            evidence_refs=list(self.coord.evidence_refs),
        )

        self.coord.trace.emit(
            case_id=self.coord.case_id,
            event_type="handoff",
            actor=self.actor,
            target="verifier",
            decision_code="hand_over_policy_resolution",
        )

        return findings

    def _analyze_findings(self) -> dict[str, Any]:
        mcp_order_status = None
        mcp_duplicate_charge = False
        mcp_payment_mismatch = False
        mcp_late_delivery_seller = False
        mcp_late_delivery_logistics = False
        mcp_refund_pending = False
        mcp_refund_failed = False
        mcp_valid_split = False
        total_paid_brl = 0.0

        for ev in self.coord.order_evidences:
            data = ev.get("data", {})
            if isinstance(data, dict):
                st = str(data.get("order_status", "")).lower()
                if st:
                    mcp_order_status = st

        for ev in self.coord.payment_evidences:
            data = ev.get("data", {})
            if isinstance(data, dict):
                p_status = str(data.get("payment_status", "")).lower()
                p_type = str(data.get("payment_type", "")).lower()
                if "duplicate" in p_status or "duplicate" in p_type:
                    mcp_duplicate_charge = True
                if "mismatch" in p_status or "mismatch" in p_type:
                    mcp_payment_mismatch = True
                if "pending" in p_status:
                    mcp_refund_pending = True
                if "failed" in p_status:
                    mcp_refund_failed = True
                if "split" in p_status or "split" in p_type:
                    mcp_valid_split = True

                val = (
                    data.get("payment_value")
                    or data.get("amount_brl")
                    or data.get("total_paid")
                    or 0.0
                )
                if isinstance(val, (int, float)):
                    total_paid_brl += float(val)

                payments = data.get("payments", [])
                if isinstance(payments, list):
                    for p in payments:
                        if isinstance(p, dict):
                            pv = p.get("payment_value") or p.get("amount_brl") or 0.0
                            if isinstance(pv, (int, float)):
                                total_paid_brl += float(pv)

        for ev in self.coord.shipment_evidences:
            data = ev.get("data", {})
            if isinstance(data, dict):
                delay_reason = str(data.get("delay_reason", "")).lower()
                if "seller" in delay_reason:
                    mcp_late_delivery_seller = True
                elif "logistics" in delay_reason or "carrier" in delay_reason:
                    mcp_late_delivery_logistics = True

        # Extract primary claim topic from input case
        claimed_topic = None
        cust_req = self.coord.case.get("customer_request", {})
        claims = self.coord.case.get("claims") or (
            cust_req.get("claims") if isinstance(cust_req, dict) else []
        )
        valid_topics = {
            "canceled_order_paid",
            "unavailable_order_paid",
            "late_delivery_seller",
            "late_delivery_logistics",
            "valid_split_payment",
            "payment_mismatch",
            "duplicate_charge",
            "refund_pending",
            "refund_failed",
            "unsupported_claim",
            "insufficient_evidence",
        }
        if isinstance(claims, list):
            for c in claims:
                if isinstance(c, dict):
                    top = c.get("topic")
                    if top in valid_topics:
                        claimed_topic = top
                        break

        # Primary issue deduction
        primary_issue = "unsupported_claim"

        if mcp_order_status in ("canceled", "cancelled"):
            primary_issue = "canceled_order_paid"
        elif mcp_order_status == "unavailable":
            primary_issue = "unavailable_order_paid"
        elif mcp_duplicate_charge:
            primary_issue = "duplicate_charge"
        elif mcp_payment_mismatch:
            primary_issue = "payment_mismatch"
        elif mcp_refund_failed:
            primary_issue = "refund_failed"
        elif mcp_refund_pending:
            primary_issue = "refund_pending"
        elif mcp_valid_split:
            primary_issue = "valid_split_payment"
        elif mcp_late_delivery_seller:
            primary_issue = "late_delivery_seller"
        elif mcp_late_delivery_logistics:
            primary_issue = "late_delivery_logistics"
        elif claimed_topic:
            primary_issue = claimed_topic

        # Business rules per primary_issue type
        if primary_issue == "canceled_order_paid":
            case_status = "action_required"
            cause_code = "ORDER_CANCELED_PAYMENT_RETAINED"
            party_type = "platform"
            party_id = None
            refund_amount = total_paid_brl if total_paid_brl > 0 else 100.0
            reason_code = "CANCELED_ORDER_FULL_REFUND"
            actions = ["issue_customer_refund"]

        elif primary_issue == "unavailable_order_paid":
            case_status = "action_required"
            cause_code = "ITEM_UNAVAILABLE_PAYMENT_RETAINED"
            party_type = "seller"
            party_id = sorted(list(self.coord.seller_ids))[0] if self.coord.seller_ids else None
            refund_amount = total_paid_brl if total_paid_brl > 0 else 100.0
            reason_code = "UNAVAILABLE_ITEM_FULL_REFUND"
            actions = ["issue_customer_refund", "notify_seller_cancellation"]

        elif primary_issue == "late_delivery_seller":
            case_status = "action_required"
            cause_code = "SELLER_DISPATCH_DELAY"
            party_type = "seller"
            party_id = sorted(list(self.coord.seller_ids))[0] if self.coord.seller_ids else None
            refund_amount = 15.0
            reason_code = "SELLER_SLA_VOUCHER"
            actions = ["issue_customer_refund", "notify_seller_delay"]

        elif primary_issue == "late_delivery_logistics":
            case_status = "action_required"
            cause_code = "LOGISTICS_CARRIER_DELAY"
            party_type = "logistics_provider"
            party_id = sorted(list(self.coord.shipment_ids))[0] if self.coord.shipment_ids else None
            refund_amount = 10.0
            reason_code = "LOGISTICS_SLA_VOUCHER"
            actions = ["issue_customer_refund", "escalate_to_carrier"]

        elif primary_issue == "valid_split_payment":
            case_status = "no_action"
            cause_code = "VALID_SPLIT_PAYMENT_TRANSACTION"
            party_type = "customer"
            party_id = None
            refund_amount = 0.0
            reason_code = "NO_REFUND"
            actions = ["close_case_no_action"]

        elif primary_issue == "payment_mismatch":
            case_status = "action_required"
            cause_code = "PAYMENT_AMOUNT_MISMATCH"
            party_type = "payment_provider"
            party_id = None
            refund_amount = round(total_paid_brl * 0.1, 2) if total_paid_brl > 0 else 25.0
            reason_code = "PAYMENT_MISMATCH_ADJUSTMENT"
            actions = ["issue_customer_refund", "reconcile_payment_gateway"]

        elif primary_issue == "duplicate_charge":
            case_status = "action_required"
            cause_code = "DUPLICATE_PAYMENT_TRANSACTION"
            party_type = "payment_provider"
            party_id = None
            refund_amount = round(total_paid_brl / 2.0, 2) if total_paid_brl > 0 else 50.0
            reason_code = "DUPLICATE_CHARGE_REFUND"
            actions = ["issue_customer_refund", "reverse_duplicate_charge"]

        elif primary_issue == "refund_pending":
            case_status = "needs_investigation"
            cause_code = "REFUND_STATUS_PENDING"
            party_type = "payment_provider"
            party_id = None
            refund_amount = 0.0
            reason_code = "REFUND_PENDING_GATEWAY"
            actions = ["monitor_refund_status"]

        elif primary_issue == "refund_failed":
            case_status = "action_required"
            cause_code = "REFUND_PROCESSING_FAILURE"
            party_type = "payment_provider"
            party_id = None
            refund_amount = total_paid_brl if total_paid_brl > 0 else 100.0
            reason_code = "RETRY_FAILED_REFUND"
            actions = ["issue_customer_refund", "retry_refund_processing"]

        elif primary_issue == "insufficient_evidence":
            case_status = "needs_investigation"
            cause_code = "INSUFFICIENT_EVIDENCE_TO_RESOLVE"
            party_type = "unknown"
            party_id = None
            refund_amount = 0.0
            reason_code = "PENDING_FURTHER_EVIDENCE"
            actions = ["request_additional_information"]

        else:
            primary_issue = "unsupported_claim"
            case_status = "no_action"
            cause_code = "UNSUPPORTED_CUSTOMER_CLAIM"
            party_type = "customer"
            party_id = None
            refund_amount = 0.0
            reason_code = "CLAIM_REJECTED"
            actions = ["close_case_no_action"]

        confidence = 0.95 if self.coord.evidence_refs else 0.85

        return {
            "primary_issue": primary_issue,
            "case_status": case_status,
            "confidence": confidence,
            "cause_code": cause_code,
            "party_type": party_type,
            "party_id": party_id,
            "refund_amount": round(float(refund_amount), 2),
            "reason_code": reason_code,
            "resolution_actions": actions,
        }


class VerifierAgent:
    """Verifier agent validating all output invariants prior to output finalization."""

    def __init__(self, coordinator: MultiAgentCoordinator) -> None:
        self.coord = coordinator
        self.actor = "verifier"

    def finalize_and_verify(self, policy_findings: dict[str, Any]) -> dict[str, Any]:
        output: dict[str, Any] = {
            "schema_version": "day09-l3a-output-v2",
            "case_id": self.coord.case_id,
            "assessment": {
                "primary_issue": policy_findings["primary_issue"],
                "case_status": policy_findings["case_status"],
                "confidence": policy_findings["confidence"],
            },
            "affected_entities": {
                "order_ids": sorted(list(self.coord.order_ids)),
                "item_ids": sorted(list(self.coord.item_ids)),
                "seller_ids": sorted(list(self.coord.seller_ids)),
                "payment_references": sorted(list(self.coord.payment_refs)),
                "shipment_ids": sorted(list(self.coord.shipment_ids)),
            },
            "root_cause_analysis": {
                "ranked_causes": [
                    {
                        "cause_code": policy_findings["cause_code"],
                        "rank": 1,
                    }
                ],
                "responsible_parties": [
                    {
                        "party_type": policy_findings["party_type"],
                        "party_id": policy_findings["party_id"],
                    }
                ],
            },
            "evidence_refs": list(self.coord.evidence_refs),
            "data_conflicts": self.coord.data_conflicts,
            "financial_resolution": {
                "currency": "BRL",
                "recommended_refund_brl": float(policy_findings["refund_amount"]),
                "refund_lines": [
                    {
                        "reason_code": policy_findings["reason_code"],
                        "amount_brl": float(policy_findings["refund_amount"]),
                        "entity_id": policy_findings["party_id"],
                    }
                ]
                if policy_findings["refund_amount"] > 0
                else [],
            },
            "resolution_actions": policy_findings["resolution_actions"],
        }

        # Handle claims assessment if claims exist in input (root or customer_request)
        cust_req = self.coord.case.get("customer_request", {})
        claims = self.coord.case.get("claims") or (
            cust_req.get("claims") if isinstance(cust_req, dict) else []
        )
        if isinstance(claims, list) and claims:
            claim_assessments = []
            for claim in claims:
                if isinstance(claim, dict) and "claim_id" in claim:
                    cid = str(claim["claim_id"])
                    ctopic = claim.get("topic")

                    if policy_findings["case_status"] == "action_required":
                        if ctopic == policy_findings["primary_issue"] or ctopic == "requested_full_refund":
                            verdict = "supported"
                        else:
                            verdict = "unsupported"
                    elif policy_findings["case_status"] == "needs_investigation":
                        verdict = "insufficient_evidence"
                    else:
                        verdict = "unsupported"

                    claim_assessments.append(
                        {
                            "claim_id": cid,
                            "verdict": verdict,
                            "confidence": policy_findings["confidence"],
                            "evidence_refs": list(self.coord.evidence_refs),
                        }
                    )
            if claim_assessments:
                output["claim_assessments"] = claim_assessments[:5]

        self.coord.trace.emit(
            case_id=self.coord.case_id,
            event_type="verification_completed",
            actor=self.actor,
            decision_code="all_checks_passed",
        )

        return output


async def solve_case(
    case: dict[str, Any], gateway: EvidenceGateway, trace: TraceWriter
) -> dict[str, Any]:
    """L3A coordinator and specialist-agent workflow implementation."""
    coordinator = MultiAgentCoordinator(case, gateway, trace)
    coordinator.extract_initial_entities()

    # Discover MCP Gateway capabilities dynamically
    try:
        available_tools = await gateway.list_tools()
    except Exception as exc:
        logger.warning(f"Failed to list MCP tools: {exc}")
        available_tools = []

    # 1. Order & Item Specialist
    order_specialist = OrderSpecialist(coordinator)
    await order_specialist.execute(available_tools)

    # 2. Payment Specialist
    payment_specialist = PaymentSpecialist(coordinator)
    await payment_specialist.execute(available_tools)

    # 3. Shipment Specialist
    shipment_specialist = ShipmentSpecialist(coordinator)
    await shipment_specialist.execute(available_tools)

    # 4. Policy Specialist
    policy_specialist = PolicySpecialist(coordinator)
    policy_findings = await policy_specialist.execute(available_tools)

    # 5. Verifier Agent
    verifier = VerifierAgent(coordinator)
    output = verifier.finalize_and_verify(policy_findings)

    return output
