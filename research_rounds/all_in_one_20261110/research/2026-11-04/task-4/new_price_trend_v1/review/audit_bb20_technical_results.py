"""Read-only exact audit of already completed native technical paths."""
from pathlib import Path
from collections import Counter
import gzip,hashlib,json,pickle,time
import pandas as pd
O=Path(__file__).resolve().parents[1];F=O/'funding';T=F/'technical';R=Path(__file__).resolve().parent
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def j(p):return json.loads(Path(p).read_text())
def book(p):
    with gzip.open(p,'rt')as h:return json.load(h)
def lines(p,cut=None):
    out=[]
    with gzip.open(p,'rt')as h:
        for line in h:
            r=json.loads(line)
            if cut is not None and str(r.get('day',r.get('at','')))[:10]>cut:break
            out.append(r)
    return out
def pair_compare(a,b,cut=None,include_book=True):
    result={}
    if include_book:result['book']=book(a/'B.json.gz')==book(b/'B.json.gz')
    for n in ['daily','opportunities','funding','industry','balances','rank-policy']:
        av=lines(a/(n+'.jsonl.gz'),cut);bv=lines(b/(n+'.jsonl.gz'),cut)
        assert av==bv,(str(a),str(b),n)
        result[n]=dict(exact=True,rows=len(av))
    assert not include_book or result['book']
    return result
def main():
    begun=time.monotonic();gate=j(T/'GATE.json');assert gate['passed']and gate['full_accounts_executed']==0
    assert gate['compute_seconds']==j(T/'TIMING.json')['used_seconds']<180
    features=pickle.loads((O/'PRICE_FEATURES.pkl').read_bytes())
    baseline={'long':Path('/Users/bytedance/Documents/Codex/2026-11-04/task/ar6_native_feasibility/NEW_CYCLE_READINESS/2024_full/cycle2024/no60/run-2024/pair'),'strong':Path('/Users/bytedance/Documents/Codex/2026-11-04/task/pvr_pool_feasibility/runs/2025_26/pair')}
    proofs={};counts={};sources={str(T/'GATE.json'):sha(T/'GATE.json')}
    for w,cut in {'long':'2022-01-14','strong':'2025-07-15'}.items():
        native=T/(w+'_native')/'pair';off=T/(w+'_OFF')/'pair';on=T/(w+'_BB20_full_lookup')/'pair';physical=T/(w+'_BB20_physical')/'pair'
        proofs[w]=dict(native_off=pair_compare(native,off),old_prefix_off=pair_compare(baseline[w],off,cut,False),full_physical=pair_compare(on,physical))
        gates=lines(on/'entry-gate.jsonl.gz');assert gates==lines(physical/'entry-gate.jsonl.gz')
        opps={(r['day'],r['sid']):r for r in lines(on/'opportunities.jsonl.gz')}
        eligible={k:r for k,r in opps.items()if r['roles']and not r['barriers']}
        assert len(gates)==len(eligible)==len({(r['day'],r['sid'])for r in gates})
        decisions={r['at'][:10]:r for r in book(on/'B.json.gz')['decisions']}
        daily={r['at'][:10]:r for r in lines(on/'daily.jsonl.gz')}
        for r in gates:
            k=(r['day'],r['sid']);p=eligible[k]
            assert r['roles']==p['roles']and r['held']==p['held']
            assert r['held']==bool(daily[r['day']]['positions'].get(r['sid'],0))
            if r['held']:
                assert r['accepted']and r['known']is None and r['cross']is None and r['reason']=='held_ADD_unchanged'
                assert r['roles']==['mobile']
            else:
                z=features[r['sid']];d=pd.Timestamp(r['day']);known=d in z.index and bool(z.at[d,'bb20_cross_known']);cross=bool(z.at[d,'bb20_cross'])if known else None
                assert (r['known'],r['cross'],r['accepted'])==(known,cross,known and cross)
                assert r['source_segment']==str(z.at[d,'source_segment'])
                if not r['accepted']:assert all(i['sid']!=r['sid']for i in decisions[r['day']]['intents'])
        counts[w]=dict(rows=len(gates),reasons=dict(Counter(r['reason']for r in gates)))
        assert counts[w]==j(T/'ENTRY_GATE_COUNTS.json')[w]
        assert counts[w]['reasons']['BB20_cross']>0 and counts[w]['reasons']['BB20_no_cross']>0 and counts[w]['reasons']['held_ADD_unchanged']>0
        for tag in ['native','OFF','BB20_full_lookup','BB20_physical']:
            done=T/(w+'_'+tag)/'DONE.json';assert j(done)['completed'];sources[str(done)]=sha(done)
    out=dict(passed=True,status='PASS_TECHNICAL_RESULTS_WAIT_RESOURCE_REFREEZE',scope='Independent reads of eight completed technical paths, not new simulation',gate_sha256=sha(T/'GATE.json'),technical_source_freeze_sha256=gate['source_freeze_sha256'],compute_seconds=gate['compute_seconds'],limit_seconds=180,input_preparation_seconds=gate['input_preparation_seconds'],proofs=proofs,entry_gate_counts=counts,all_eligible_original_role_rows_covered=True,all_blocked_flat_absent_from_decision_intents=True,all_flat_feature_keys_and_source_segments_exact=True,full_paths_started=False,reviewer_accounts=0,reviewer_projections=0,resource_revision_conclusion='Allow pre-full 1200 to 2400 second aggregate budget correction only, preserving old sources/freezes and an explicit resource-only diff and technical-gate inheritance. Four unique full paths/windows/formula/rules remain unchanged. Full admission awaits new frozen source-diff review.',source_sha256=sources,seconds=time.monotonic()-begun)
    (R/'ENTRY_BB20_TECHNICAL_RESULT_REVIEW.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({k:v for k,v in out.items()if k not in ['proofs','source_sha256']},ensure_ascii=False,indent=2))
if __name__=='__main__':main()
