import json
from pathlib import Path

def main():
    root = Path(".")
    inputs_dir = root / "inputs"
    valid_primary_issues = {
        "canceled_order_paid", "unavailable_order_paid", "late_delivery_seller",
        "late_delivery_logistics", "valid_split_payment", "payment_mismatch",
        "duplicate_charge", "refund_pending", "refund_failed",
        "unsupported_claim", "insufficient_evidence"
    }
    
    missing_topic = []
    topics_found = {}
    
    for p in sorted(inputs_dir.glob("L3A_CASE_*.json")):
        data = json.loads(p.read_text(encoding="utf-8"))
        case_id = data["case_id"]
        cust_req = data.get("customer_request", {})
        claims = cust_req.get("claims", [])
        found = False
        for claim in claims:
            t = claim.get("topic")
            if t in valid_primary_issues:
                found = True
                topics_found[case_id] = t
                break
        if not found:
            missing_topic.append((case_id, claims))
            
    print(f"Total cases inspected: {len(list(inputs_dir.glob('L3A_CASE_*.json')))}")
    print(f"Cases with valid primary_issue topic in claims: {len(topics_found)}")
    print(f"Cases missing primary_issue topic: {len(missing_topic)}")
    if missing_topic:
        print("Missing topics detail:", missing_topic[:10])

if __name__ == "__main__":
    main()
