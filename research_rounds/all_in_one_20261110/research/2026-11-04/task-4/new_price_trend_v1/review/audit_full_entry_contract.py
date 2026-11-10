"""Read-only final four-path output/source, gate and execution-clock audit."""
from pathlib import Path
from collections import Counter
from datetime import datetime
from bisect import bisect_right
import gzip,hashlib,json,pickle,time
import pandas as pd
O=Path(__file__).resolve().parents[1];F=O/'funding';R=Path(__file__).resolve().parent
def j(p):return json.loads(Path(p).read_text())
def gz(p,lines=False):
    with gzip.open(p,'rt')as h:return list(map(json.loads,h))if lines else json.load(h)
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def main():
    start=time.monotonic();complete=j(F/'runs/COMPLETE.json');assert complete['passed']and complete['paths']==4
    timing=j(F/'runs/TIMING.json');assert complete['compute_seconds']==timing['used_seconds']<timing['limit_seconds']==2400
    freeze=j(F/'SOURCE_FREEZE.json');assert sha(F/'SOURCE_FREEZE.json')==complete['source_freeze_sha256'];assert all(sha(p)==h for p,h in freeze['sources'].items())
    outputs=j(F/'FULL_OUTPUT_SHA256.json');assert len(outputs)==59 and all(sha(p)==h for p,h in outputs.items())
    auth=j(F/'FULL_AUTHORIZATION.json');assert auth['approved']and auth['scope']=='ENTRY_BB20_four_full_paths'and auth['source_freeze_sha256']==sha(F/'SOURCE_FREEZE.json')
    assert sha(auth['independent_admission_path'])==auth['independent_admission_sha256'];assert sha(auth['technical_review_path'])==auth['technical_review_sha256']
    features=pickle.loads((O/'PRICE_FEATURES.pkl').read_bytes());summary=j(F/'FULL_NATIVE_COMPLETION_SUMMARY.json');rules=j('/Users/bytedance/Documents/ChatGPT/money/research_rounds/pvr-act-comparison-20261027/execution-rules-v2.json');opens=[datetime.fromisoformat(x)for x in rules['calendars']['A']];engine=None;proofs={}
    for w,startday,end,closes in [('long','2022-01-01','2024-12-31',726),('strong','2025-07-01','2026-06-30',242)]:
        for mode in ['OFF','BB20']:
            name=w+'_'+mode;root=F/'runs'/name;done=j(root/'DONE.json');assert done['completed'];fresh=j(F/'runs'/(name+'_FRESH.json'));assert fresh==dict(cash=1000000,positions=0,orders=0,account_imports=0)
            prov=j(root/'checkpoint.provenance.json');assert prov['last_completed_event']==end+' 15:10:00+08:00';e=prov['engine_identity']
            if engine is None:engine=e
            else:assert e==engine
            for cls in [e['runtime_class'],e['trading_class']]+[v['defining_class']for v in e['functions'].values()]:assert sha(cls['module_path'])==cls['module_sha256']
            book=gz(root/'pair/B.json.gz');daily=gz(root/'pair/daily.jsonl.gz',True);assert len(daily)==closes;assert daily[0]['nav']=='1000000'and not daily[0]['positions'];byday={r['at'][:10]:r for r in daily};decisions={r['at'][:10]:r for r in book['decisions']};gates=gz(root/'pair/entry-gate.jsonl.gz',True)
            assert done['ending_NAV']['B']==book['ending_NAV']==daily[-1]['nav'];assert Counter(t['side']for t in book['trades'])==summary['paths'][name]['trade_fills_by_side']
            gate={(r['day'],r['sid']):r for r in gates};assert len(gate)==len(gates)
            if mode=='OFF':assert not gate and j(root/'ORIGINAL_IDENTITY.json')['passed']
            else:
                expected=0
                with gzip.open(root/'pair/opportunities.jsonl.gz','rt')as h:
                    for line in h:
                        p=json.loads(line);key=(p['day'],p['sid'])
                        if p['roles']and not p['barriers']:
                            r=gate[key];expected+=1;assert r['roles']==p['roles']and r['held']==p['held']
                        else:assert key not in gate
                assert expected==len(gate)
                for (day,sid),r in gate.items():
                    assert isinstance(r['accepted'],bool)and isinstance(r['held'],bool);assert r['held']==bool(byday[day]['positions'].get(sid,0))
                    if r['held']:assert r['roles']==['mobile']and r['accepted']and r['known']is None and r['reason']=='held_ADD_unchanged'
                    else:
                        f=features[sid];d=pd.Timestamp(day);known=d in f.index and bool(f.at[d,'bb20_cross_known']);cross=bool(f.at[d,'bb20_cross'])if known else None
                        assert (r['known'],r['cross'],r['accepted'])==(known,cross,known and cross);assert r['source_segment']==str(f.at[d,'source_segment'])
                        if not r['accepted']:assert all(i['sid']!=sid for i in decisions[day]['intents'])
                assert dict(Counter(r['reason']for r in gates))==summary['paths'][name]['entry_gate']['reasons']
            for t in book['trades']:
                if t['side']!='buy':continue
                signal=datetime.fromisoformat(t['signal_at']);fill=datetime.fromisoformat(t['at']);assert signal.hour==15 and signal.minute==10;assert fill==opens[bisect_right(opens,signal)]
                if mode=='BB20':assert gate[(str(signal.date()),t['security_id'])]['accepted']
            proofs[name]=dict(fresh_initial_state=True,complete_closes=closes,engine_and_source_identity_exact=True,gate_rows=len(gates),all_gate_rows_original_qualification_and_exact_day=True,all_actual_buy_fills_next_original_OPEN=True,entry_reasons=dict(Counter(r['reason']for r in gates)))
    result=dict(passed=True,status='PASS_FOUR_COMPLETED_PATHS_SOURCE_CLOCK_AND_ENTRY_CONTRACT',paths=4,compute_seconds=complete['compute_seconds'],limit_seconds=2400,source_freeze_sha256=sha(F/'SOURCE_FREEZE.json'),direct_source_hashes=len(freeze['sources']),final_output_hashes=len(outputs),same_engine_identity_all_four=True,all_defining_module_hashes_current=True,proofs=proofs,reviewer_new_accounts=0,reviewer_projections=0,seconds=time.monotonic()-start,scope='Execution completion, exact frozen flat gate mother/clock and unchanged native engine only. Financial reader must honor original stale ex-action valuation; this artifact does not replace financial result or sector participation audit.')
    (R/'FULL_ENTRY_CONTRACT_RESULT_REVIEW.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n');print(json.dumps(result,ensure_ascii=False,indent=2))
if __name__=='__main__':main()
