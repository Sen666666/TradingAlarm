"""Finalize manifests after distinguishing amended derived outputs from immutable inputs."""
from pathlib import Path
import json,hashlib,shutil
import pandas as pd
from decimal import Decimal as D
O=Path(__file__).resolve().parent;R=O.parents[1];A=R/'act_only_ablation_continuous_v1'
P=Path('/Users/bytedance/Documents/ChatGPT/money/TradingAlarm/runtime/market/update-20261030-153010-c551af/prepared')
failure=O/'failure_02_derived_output_hash_check'
assert not failure.exists();failure.mkdir()
shutil.copy2(O/'verify_and_correct.py',failure/'verify_and_correct.py')
(failure/'FAILURE.txt').write_text("Final immutable-input check included derived SUMMARY.json that the same script intentionally amended. It therefore stopped on the expected changed derived output, after producing corrected reports. Original immutable sources were not implicated. Exact error: AssertionError: ('source changed', '"+str(O/'SUMMARY.json')+"'). No re-execution of the analysis or verification loop was made; this bounded finalizer separates original inputs and amended deliverables.\n")
src={}
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def freeze(p,expected=None):
 h=sha(p)
 if expected:assert h==expected,('immutable source changed',p)
 src[str(p)]={'sha256':h,'expected_sha256':expected,'verified':True}
 return h
old=json.loads((O/'SOURCE_HASHES.json').read_text())
for p,x in old.items():freeze(p,x['sha256'])
runtime=json.loads((A/'run/RUNTIME_DEPENDENCY_FREEZE.json').read_text())
mp=P/'manifest.json';freeze(mp,runtime.get(str(mp)));mk={r['series_id']:r for r in json.loads(mp.read_text())['series']}
cases=json.loads((O/'CASE_SUMMARY.json').read_text());assert len(cases)==14
for c in cases:
 r=mk[c['sid']]
 freeze(r['raw']['path'],r['raw']['sha256']);freeze(r['adjustment']['actions']['path'],r['adjustment']['actions']['sha256'])
win=A/'run/SHARED_WINDOW_AUDIT.jsonl.gz';freeze(win,json.loads((A/'run/OUTPUT_HASHES.json').read_text())['SHARED_WINDOW_AUDIT.jsonl.gz'])
for p in [O/'verify_and_correct.py',Path(__file__),Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/cp1-evidence-trace-20261031/trace.py')]:freeze(p)
cps=json.loads((O/'CP_ADVANCE_VERIFICATION.json').read_text());rs=[x for x in cps if x['purpose']=='FLOOR_RAISE']
assert all(x['all_new_advances_after_fill']and x['entry_receipt_advance_overlap_count']==0 for x in rs)
gree=next(x for x in cps if x['round_id']==1542 and x['purpose']=='FLOOR_RAISE')
assert gree['new_advance_days']==['2024-01-10','2024-01-15','2024-01-16']
p=pd.read_csv(O/'POST_EXIT_20_COMMON_CLOSES.csv');assert len(p)==294 and p.common_close_number_after_exit.gt(0).sum()==280
assert p.groupby('round_id').size().eq(21).all()
assert sum(len(json.loads(x))for x in p.actual_later_buys_at_this_OPEN)==0
assert 'original_OPEN_funding'in p and 'original_CLOSE_sizing'in p
w=pd.read_csv(O/'PENDING_EXIT_WINDOW_DAILY.csv');assert len(w)==19 and (~w.same_day_native_raw_bar_exists).sum()==5
assert set(w[~w.same_day_native_raw_bar_exists].round_id)=={2897}
for x in json.loads((O/'LOSS_BRIDGE.json').read_text()):assert abs(D(x['residual']))<D('1e-8')
s=json.loads((O/'SUMMARY.json').read_text())
assert s['initial_CP_dominant_cases']==13 and s['all_fast_failures_initial_CP_dominant']
assert 'Anchor-before-fill is not proof'in s['critical_result']
v=json.loads((O/'FINAL_VERIFICATION.json').read_text())
v.update(passed=True,final_immutable_source_hash_pass=True,original_immutable_source_count=len(old),final_verified_source_count=len(src),derived_output_hash_failure_resolved='Only intentionally amended SUMMARY/CASE_SUMMARY triggered old broad source check. Immutable sources reverified separately; no rerun.',no_analysis_or_account_rerun_in_finalizer=True,all_produced_files_readable=True)
(O/'FINAL_VERIFICATION.json').write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n')
(O/'VERIFICATION_SOURCE_HASHES.json').write_text(json.dumps(src,ensure_ascii=False,indent=2)+'\n')
with(O/'READOUT.md').open('a')as f:f.write('\n- failure_02_derived_output_hash_check preserves the verification-bookkeeping failure: its immutable-source loop accidentally included intentionally amended derived summaries. Finalizer rechecked all original inputs separately and verified all corrected tables without rerunning the analysis or an account.\n')
# Final manifest is authoritative; initial OUTPUT_HASHES describes its preserved primary snapshot.
final={str(p.relative_to(O)):sha(p)for p in sorted(O.rglob('*'))if p.is_file()and p.name!='FINAL_OUTPUT_HASHES.json'}
out=O/'FINAL_OUTPUT_HASHES.json';assert not out.exists();out.write_text(json.dumps(final,ensure_ascii=False,indent=2)+'\n')
for p,h in final.items():assert sha(O/p)==h
print(json.dumps({'PASS':True,'original_sources':len(old),'final_sources':len(src),'bound_files':len(final),'CP_raise_receipts':len(rs),'new_advance_observations':len(pd.read_csv(O/'CP_ADVANCE_DATES.csv')),'pending_OPEN_rows':len(w),'all_14_windows_20_common_closes':True,'account_runs':0}))
