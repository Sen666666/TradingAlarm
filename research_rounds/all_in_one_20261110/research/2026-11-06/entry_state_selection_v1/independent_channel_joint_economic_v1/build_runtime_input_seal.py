"""Close declared runtime-module and local-audit inputs, without economics."""
from pathlib import Path
import json
import hashlib
from market_adapter import MarketAdapter

O=Path(__file__).resolve().parent


def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def main():
    p=O/'planned_inputs_v1/PLANNED_INPUT_SHA256.json'
    plan={str(Path(k).resolve()):v for k,v in json.loads(p.read_text()).items()}
    audit_inputs=[O/'PROTOCOL_DRAFT.md',O/'INDEPENDENT_CONTRACT_AUDIT.json',p,
                  O/'planned_inputs_v1/ABSENT_ACTION_SOURCES.json']
    for q in audit_inputs:plan[str(q.resolve())]=sha(q)
    # Environment code is not market data. Pin every Python source under the
    # one runtime dependency family actually discovered by the native loader.
    import pyarrow
    runtime_root=Path(pyarrow.__file__).resolve().parent
    runtime={str(q.resolve()):sha(q) for q in runtime_root.rglob('*.py')}
    plan.update(runtime)
    m=MarketAdapter(expected_sources=plan)
    m.qualification('300666.SZ','2025-12-15')
    m.open('002583.SZ','2024-09-23')
    m.close('002583.SZ','2024-09-23')
    actual=m.verify_sources()
    assert all(k in plan and plan[k]==v for k,v in actual.items())
    output=O/'PLANNED_EXECUTION_INPUT_SHA256.json'
    with output.open('x') as f:json.dump(plan,f,ensure_ascii=False,indent=2,sort_keys=True);f.write('\n')
    with (O/'EXECUTION_INPUT_QA.json').open('x') as f:
        json.dump(dict(files=len(plan),runtime_family='pyarrow',runtime_python_files=len(runtime),
            local_audit_inputs=len(audit_inputs),source_guard_actual_files=len(actual),all_actual_reads_planned=True,
            no_business_source_exemption=True,input_map_sha256=sha(output),new_economic_runs=0),f,indent=2);f.write('\n')
    print('EXECUTION_INPUT_GUARD_PASS',len(plan),len(actual),flush=True)


if __name__=='__main__':main()
