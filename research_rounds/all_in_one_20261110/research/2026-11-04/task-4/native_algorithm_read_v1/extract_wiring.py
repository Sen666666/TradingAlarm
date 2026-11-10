"""Copy source text with line numbers; never imports strategy/market/account modules."""
from pathlib import Path
import hashlib
import json
import time

OUT = Path(__file__).resolve().parent
SPECS = [
    ('effective_No60_wiring', '/Users/bytedance/Documents/Codex/2026-11-04/task/pvr_pool_feasibility/native_adapter.py', [(1,40)]),
    ('derived_cap_variant_only', '/Users/bytedance/Documents/Codex/2026-11-04/task/pvr_pool_feasibility/component.py', [(17,34)]),
    ('actual_long_full_facts_and_scores_loader', '/Users/bytedance/Documents/Codex/2026-11-04/task-4/new_price_trend_v1/funding/input_loader.py', [(12,17),(21,73)]),
    ('OFF_original_planning_branch', '/Users/bytedance/Documents/Codex/2026-11-04/task-4/new_price_trend_v1/funding/entry_adapter.py', [(105,127)]),
    ('original_fact_to_S0_contract', '/Users/bytedance/Documents/ChatGPT/money/research_rounds/actual-risk-recovery-20261027/code/engine.py', [(25,47)]),
    ('S0_eligibility_used_before_roles', '/Users/bytedance/Documents/ChatGPT/money/research_rounds/rs-h1-execution-20261025/code/sector_stock_admission.py', [(185,220)]),
    ('CLOSE_protection_then_roles_then_frozen_intents', '/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/case-stage-ledger-20261031/v3/joint_v3.py', [(213,259)]),
    ('next_OPEN_sell_settle_reserve_then_execution_proxy', '/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/case-stage-ledger-20261031/v3/joint_v3.py', [(302,324)]),
    ('PVR_scores_and_unique_stock_slot_substitution', '/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/pvr-slot1-native-readiness-20261101/native_rank.py', [(25,45),(47,91),(115,120)]),
    ('original_CORE_size_and_OPEN_preview', '/Users/bytedance/Documents/ChatGPT/money/research_rounds/lot-risk-allocation-20261029/code/study.py', [(16,31),(42,66)]),
]

def main():
    started = time.monotonic()
    chunks = ['SOURCE TEXT ONLY. Original line numbers; no strategy code executed.\n']
    records = []
    for label, rawpath, ranges in SPECS:
        p = Path(rawpath)
        data = p.read_bytes()
        lines = data.decode().splitlines()
        digest = hashlib.sha256(data).hexdigest()
        chunks.append(f'\n[{label}]\nPATH {p}\nSHA256 {digest}\n')
        for first, last in ranges:
            assert 1 <= first <= last <= len(lines), (p,first,last,len(lines))
            chunks.append('\n'.join(f'{n:5d} {lines[n-1]}' for n in range(first,last+1))+'\n')
        records.append(dict(label=label,path=str(p),sha256=digest,ranges=ranges))
    (OUT/'NATIVE_WIRING_EXCERPTS.txt').write_text('\n'.join(chunks))
    (OUT/'NATIVE_WIRING_SOURCE_INDEX.json').write_text(json.dumps(records,ensure_ascii=False,indent=2)+'\n')
    result=dict(source_files=len(set(r['path'] for r in records)),ranges=sum(len(r['ranges']) for r in records),strategy_imports=0,new_models=0,new_accounts=0,new_backtests=0,seconds=time.monotonic()-started)
    (OUT/'WIRING_EXTRACTION_SCOPE.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result))

if __name__=='__main__':
    main()
