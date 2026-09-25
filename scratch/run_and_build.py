import asyncio
import json
import logging
from pathlib import Path

from student_agent.cases import load_case_set
from student_agent.config import Settings
from student_agent.contracts import Contracts
from student_agent.mcp_gateway import connect_gateway
from student_agent.submission import package_submission, validate_artifacts
from student_agent.trace import TraceWriter
from student_agent.workflow import solve_case

logging.basicConfig(level=logging.INFO)

async def main():
    root = Path(".").resolve()
    settings = Settings.load(root)
    case_set = load_case_set(root)
    contracts = Contracts(root / "contracts" / "schemas")
    output_root = root / "outputs"
    trace_path = root / "traces" / "trace.jsonl"
    output_root.mkdir(parents=True, exist_ok=True)
    trace_path.parent.mkdir(parents=True, exist_ok=True)
    
    # Remove stale files
    for stale in output_root.glob("*.json"):
        stale.unlink()
    trace_path.unlink(missing_ok=True)
    trace = TraceWriter(trace_path, contracts)

    print("Connecting gateway...")
    async with connect_gateway(settings.mcp_endpoint, settings.team_api_key, contracts) as gateway:
        try:
            discovered_tools = await gateway.list_tools()
            print(f"Discovered {len(discovered_tools)} tools.")
        except Exception as exc:
            print(f"Gateway tool listing failed ({exc}), using offline mode.")
            discovered_tools = []
            
        print(f"Processing {len(case_set.case_ids)} cases...")
        for i, case_id in enumerate(case_set.case_ids, 1):
            case = case_set.cases[case_id]
            trace.emit(case_id=case_id, event_type="case_received", actor="coordinator")
            output = await solve_case(case, gateway, trace)
            contracts.validate_output(output, f"outputs/{case_id}.json")
            
            target = output_root / f"{case_id}.json"
            temporary = target.with_suffix(".json.tmp")
            temporary.write_text(
                json.dumps(output, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
            )
            temporary.replace(target)
            trace.emit(case_id=case_id, event_type="case_finalized", actor="coordinator")
            if i % 10 == 0 or i == len(case_set.case_ids):
                print(f"  Processed {i}/{len(case_set.case_ids)} cases.")

    print("\nValidating artifacts...")
    _, trace_events = validate_artifacts(root, case_set, contracts)
    print(f"OK: {len(case_set.case_ids)} outputs / {len(trace_events)} trace events")
    
    print("\nPackaging submission...")
    dest = package_submission(root, root / "dist" / "submission.zip")
    print(f"SUCCESS: Submission packaged to {dest}")

if __name__ == "__main__":
    asyncio.run(main())
