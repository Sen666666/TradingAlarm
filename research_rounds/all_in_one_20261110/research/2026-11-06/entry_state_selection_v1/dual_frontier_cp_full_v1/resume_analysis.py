"""Resume only unfinished descriptive analysis from sealed qualification outputs.
Preserves replay, qualification, event counts, original analysis code, and all input files.
No account simulation, no signal re-execution, and no parameter change.
"""
from pathlib import Path
import sys,json,time,hashlib
import numpy as np,pandas as pd
O=Path(__file__).resolve().parent;R=O.parent
U=Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/universe-cp1-inputs-20261031')
D=R/'selection_entry_diagnosis_v1';L=D/'mobile_candidate_response_v1'
sys.path.insert(0,str(O));import replay_signals as r
START='2022-01-01';END='2026-05-15';start=time.monotonic()
protected=[p for p in O.iterdir() if p.is_file() and p.name not in ['resume_analysis.py','resume_analysis.log']]
before={str(p):r.sha(p) for p in protected}
original=(O/'analyze_signals.py').read_text()
assert r.sha(O/'EVENTS.parquet')==json.loads((O/'SIGNAL_SEAL.json').read_text())['events_hash']
assert r.sha(O/'replay_signals.py')==json.loads((O/'SIGNAL_SEAL.json').read_text())['code_hash']
ev=pd.read_parquet(O/'EVENTS_QUALIFIED.parquet')
roots=pd.read_parquet(O/'I_ROOTS.parquet')
counts=pd.read_csv(O/'EVENT_COUNTS.csv').to_dict('records')
lx=pd.read_parquet(O/'ORIGINAL_LEGAL_COMPARISON.parquet')
calendar=pd.DatetimeIndex(np.load('/Users/bytedance/Documents/ChatGPT/money/TradingAlarm/runtime/market/update-20261030-153010-c551af/prepared/h1.npz')['dates'])
calendar=calendar[calendar<=END];dates=[str(x.date()) for x in calendar];cpos={d:i for i,d in enumerate(dates)}
manifest={x['symbol']:x for x in json.loads((U/'STOCK_MANIFEST.json').read_text())}
meta=json.loads(Path('/Users/bytedance/Documents/ChatGPT/money/research_rounds/a-share-selection-e0-20261024/inputs-v1/metadata.json').read_text())
r.save('RESUME_FREEZE.json',dict(status='RESUME_ONLY_UNFINISHED_ANALYSIS',original_analysis_sha256=r.sha(O/'analyze_signals.py'),resume_code_sha256=r.sha(__file__),protected_hashes=before,signal_replay_rerun=False,qualification_rerun=False,account_backtest=False))
tail=original.split('# Descriptive paired dates using full-signal common receipts as true synchronization boundaries.',1)[1]
tail=tail.split("r.save('ANALYSIS_SEAL.json'",1)[0]
exec(compile(tail,str(O/'analyze_signals.py')+'::unfinished_tail','exec'),globals())
assert all(r.sha(p)==h for p,h in before.items())
r.save('ANALYSIS_SEAL.json',dict(status='COMPLETE_FROM_SEALED_QUALIFICATION',original_analysis_sha256=r.sha(O/'analyze_signals.py'),resume_code_sha256=r.sha(__file__),freeze_hash=r.sha(O/'ANALYSIS_FREEZE.json'),signal_hash_unchanged=True,all_existing_files_unchanged=True,missing_opportunity_events=int((~ev.opportunity_observed).sum()),old_legal=len(lx),old_legal_all_within_presize=True,original_first_mobile=len(ff),roots=len(rr),account_backtests=0,signal_reruns=0,qualification_reruns=0,seconds=time.monotonic()-start))
print('ROOTS');print(pd.DataFrame(rootcounts).to_string(index=False))
print('ROUNDS');print(pd.DataFrame(roundsum).to_string(index=False))
print('COMPLETE',time.monotonic()-start,flush=True)
