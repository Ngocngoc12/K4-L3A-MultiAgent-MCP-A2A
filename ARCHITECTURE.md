# L3A Architecture Record

## 1. System overview

Luồng xử lý từ `inputs/<case_id>.json` qua các specialist agent, gọi MCP Gateway, đến Verifier và tạo ra `outputs/<case_id>.json` cùng `traces/trace.jsonl`:

```text
Input → Coordinator ──► Order Agent ──► Payment Agent ──► Shipment Agent ──► Policy Agent ──► Verifier ──► Output
             │              │                │                 │                │               │
             └──────────────┴────────────────┴─────────────────┴────────────────┴───────────────┼──► Trace
                                             │
                                    MCP Evidence Gateway
```

## 2. Agent ownership

| Actor | Input | Trách nhiệm | Output/handoff |
| --- | --- | --- | --- |
| `coordinator` | `case` dict (`case_id`, `order_ids`, `claims`) | Tiếp nhận case, trích xuất entity ban đầu, gán nhiệm vụ cho các specialist agent | Emit `task_assigned`, chuyển ngữ cảnh tới `order-agent` |
| `order-agent` | Order IDs, MCP tool discovery | Truy vấn thông tin order, items, sellers qua MCP Gateway | Record evidence, emit `tool_result_consumed`, handoff tới `payment-agent` |
| `payment-agent` | Order/Payment IDs, MCP tool discovery | Truy vấn giao dịch thanh toán, kiểm tra trùng lặp/mismatch/refund status | Record evidence, emit `tool_result_consumed`, handoff tới `shipment-agent` |
| `shipment-agent` | Order/Shipment IDs, MCP tool discovery | Truy vấn vận chuyển, lịch trình giao hàng, xác định SLA & nguyên nhân trễ | Record evidence, emit `tool_result_consumed`, handoff tới `policy-agent` |
| `policy-agent` | Tổng hợp evidence từ các specialist | Đánh giá nguyên nhân gốc (`primary_issue`), quy trách nhiệm, tính refund BRL | Emit `policy_decided`, handoff tới `verifier` |
| `verifier` | Kết quả từ `policy-agent` & evidence gathered | Kiểm tra invariants (schema, evidence ownership, financial bounds, confidence) | Emit `verification_completed`, trả về output V2 |

Quyền gọi MCP Tool:
- `order-agent`: chỉ truy vấn order/item tools (`get_order`, `get_order_items`).
- `payment-agent`: chỉ truy vấn payment/refund tools (`get_payment`, `get_payments`).
- `shipment-agent`: chỉ truy vấn shipment/logistics tools (`get_shipment`, `get_delivery`).
- `policy-agent`: chỉ truy vấn policy tools (`get_policy`, `get_refund_policy`).

## 3. A2A protocol

- **Correlation**: Mọi message envelope và event đều mang `case_id` làm correlation key.
- **Message Envelope**: Sử dụng `TraceWriter.emit` chuẩn hóa theo schema `day09-trace-event-v1`.
- **Handoff Condition**: Chuyển giao tuần tự qua các event `handoff` với `decision_code` rõ ràng.
- **Loop Prevention**: Workflow chạy theo đường ống đơn hướng (DAG): `coordinator -> order -> payment -> shipment -> policy -> verifier`. Không có vòng lặp ngược.
- **Observable Events Only**: Chỉ emit các sự kiện quan sát được (`case_received`, `task_assigned`, `tool_result_consumed`, `handoff`, `policy_decided`, `verification_completed`, `case_finalized`).

## 4. Evidence lifecycle

1. **Query & Retrieval**: Agent thực thi qua `EvidenceGateway.call(tool_name, case_id=..., ...)`.
2. **Schema Validation**: Mọi MCP response được kiểm tra tự động qua contract `mcp-evidence-response-v1.schema.json`.
3. **Reference Storage**: Trích xuất `evidence_ref` duy nhất dạng `ev_...` và lưu trữ trong `coordinator.evidence_refs`.
4. **Consumption Trace**: Emit ngay lập tức event `tool_result_consumed` với `actor`, `tool_name` và `evidence_refs`.
5. **Output Mapping**: Chỉ các `evidence_ref` thực sự được thu thập từ MCP mới được đính kèm vào field `evidence_refs` của output JSON và `claim_assessments`. Không sử dụng hay chia sẻ evidence giữa các case khác nhau.

## 5. Failure policy

| Failure | Retry? | Fallback | Trace event/code |
| --- | --- | --- | --- |
| MCP timeout | 2 retries (idempotent, exponential backoff) | Đánh giá dựa trên thông tin case sẵn có, gắn mark `insufficient_evidence` nếu thiếu dữ liệu cốt lõi | `tool_result_consumed` / `timeout_fallback` |
| Not found | không retry | Bỏ qua tool đó, không tạo `evidence_ref` giả, ghi nhận thông tin thiếu trong assessment | `policy_decided` / `data_not_found` |
| Source conflict | không retry | Lưu thông tin mâu thuẫn vào `data_conflicts`, ưu tiên nguồn authoritative hơn | `policy_decided` / `conflict_logged` |
| Invalid specialist result | 1 retry | Chuyển trạng thái case thành `needs_investigation` với confidence thấp hơn | `verification_completed` / `specialist_invalid` |

## 6. Verification invariants

Trước khi xuất kết quả cuối cùng, `verifier` đảm bảo tuân thủ các quy tắc:
1. **Schema Integrity**: Validate toàn bộ output object dựa theo `day09-l3a-output-v2.schema.json`.
2. **Entity Scope**: Các mảng `order_ids`, `item_ids`, `seller_ids`, `payment_references`, `shipment_ids` phải được deduplicate, đúng định dạng string.
3. **Evidence Ownership**: Field `evidence_refs` chỉ chứa các `evidence_ref` hợp lệ đã thu thập trong chính case này.
4. **Claim Linkage**: Tất cả `claim_id` từ input case được đánh giá tương ứng trong `claim_assessments`.
5. **Money Totals**: Currency luôn là `BRL`, `recommended_refund_brl` >= 0, tổng các dòng `refund_lines` khớp với tiền hoàn trả đề xuất.
6. **Responsibility Consistency**: `party_type` và `cause_code` phải nhất quán với `primary_issue`. `cause_code` khớp regex `^[A-Z][A-Z0-9_]{2,79}$`.
7. **Confidence Bounds**: Score `confidence` trong khoảng `[0.0, 1.0]`.

## 7. Reproducibility

- **Python Version**: 3.11+
- **Dependencies**: Pinned trong `pyproject.toml` (`mcp`, `httpx2`, `jsonschema`, `referencing`, `python-dotenv`, `pytest`).
- **Concurrency & Limits**: Maximum 1 MB per file, max 12 MB total zip size for submission package.
- **Execution Command**: `python -m student_agent.cli run`
- **Validation Command**: `python -m student_agent.cli validate`
