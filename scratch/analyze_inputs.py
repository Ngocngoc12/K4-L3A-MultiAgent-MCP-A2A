import json
from pathlib import Path
from collections import Counter

def analyze():
    inputs_dir = Path("inputs")
    topics = Counter()
    case_count = 0
    topic_examples = {}
    
    for p in sorted(inputs_dir.glob("L3A_CASE_*.json")):
        case_count += 1
        data = json.loads(p.read_text(encoding="utf-8"))
        cust_req = data.get("customer_request", {})
        claims = cust_req.get("claims", [])
        for c in claims:
            t = c.get("topic")
            topics[t] += 1
            if t not in topic_examples:
                topic_examples[t] = (p.name, cust_req.get("message"), c)
                
    print(f"Total cases: {case_count}")
    print("Topics count:")
    for t, count in topics.most_common():
        print(f"  {t}: {count}")
        print(f"    Example: {topic_examples[t]}")

if __name__ == "__main__":
    analyze()
