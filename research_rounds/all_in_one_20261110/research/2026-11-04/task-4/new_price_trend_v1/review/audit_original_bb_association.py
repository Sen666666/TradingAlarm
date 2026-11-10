"""Audit original actual-layer joins; not counterfactual strategy economics."""
from pathlib import Path
from collections import Counter
from decimal import Decimal as D
import gzip,hashlib,json,pickle,time
import pandas as pd
O=Path(__file__).resolve().parents[1];T=O.parent.parent/'task';R=Path(__file__).resolve().parent
def read(p):return json.loads(Path(p).read_text())
def gz(p):
    with gzip.open(p,'rt')as h:return list(map(json.loads,h))
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def group(rs):
    return dict(events=len(rs),stocks=len({r['sid']for r in rs}),original_cost=str(sum((D(r['original_cost'])for r in rs),D(0))),original_cutoff_net=str(sum((D(r['original_cutoff_net'])for r in rs),D(0))),original_cutoff_positive=sum(D(r['original_cutoff_net'])>0 for r in rs),original_cutoff_negative=sum(D(r['original_cutoff_net'])<0 for r in rs),by_role=dict(Counter(r['role']for r in rs)),by_original_action=dict(Counter(r['original_action']for r in rs)))
def main():
    start=time.monotonic();rows=read(O/'ALL3436_ORIGINAL_ENTRY_BB_ASSOCIATION.json');summary=read(O/'ORIGINAL_ENTRY_BB_COHORT_SUMMARY.json');source=read(O/'ORIGINAL_ENTRY_BB_SOURCE_SHA256.json')
    assert len(rows)==3436 and len({(r['window'],r['layer'])for r in rows})==3436
    assert all(sha(p)==h for p,h in source.items())
    feat=pickle.loads((O/'PRICE_FEATURES.pkl').read_bytes())
    paths={
      'long':(T/'ar6_native_feasibility/NEW_CYCLE_READINESS/2024_full/cycle2024/no60/run-2024/pair/daily.jsonl.gz',T/'risk_constraints/continuation2024_finance/analysis/2022_2024/PVR_NO_CONFIRMED60/LAYERS.json',T/'loss_correction/continuation2024_layers/PVR_NO60-ENTRY_ACTIONS.json'),
      'strong':(T/'pvr_pool_feasibility/runs/2025_26/pair/daily.jsonl.gz',T/'loss_correction/pvr_no60_2025_26/analysis/2025_26/PVR_NO60/LAYERS.json',T/'loss_correction/pvr_no60_2025_26/PVR_NO60-ENTRY_ACTIONS.json')}
    result={};unknown=0
    for w,ps in paths.items():
        raw=gz(ps[0]);assert {r['account']for r in raw}=={'B'}
        days={r['at'][:10]:r for r in raw};assert len(days)==len(raw)
        layers={r['layer']:r for r in read(ps[1])};actions={r['layer']:r for r in read(ps[2])}
        rs=[r for r in rows if r['window']==w];assert len(rs)==len(layers)==(2265 if w=='long'else 1171)
        for r in rs:
            a=layers[r['layer']];assert (r['sid'],r['signal_day'],r['opened'],r['original_cost'],r['original_cutoff_net'])==(a['sid'],a['signal_day'],a['opened'],a['cost'],a['net'])
            assert r['original_action']==actions[r['layer']]['action']
            held=days[a['signal_day']]['positions'].get(a['sid'],0)>0
            assert r['actual_signal_CLOSE_held']==held
            assert held==(r['original_action']=='add_to_existing_stock')
            assert not held or r['role']=='mobile'
            f=feat[a['sid']];d=pd.Timestamp(a['signal_day']);known=d in f.index and bool(f.at[d,'bb20_cross_known']);cross=bool(f.at[d,'bb20_cross'])if known else None
            assert (r['BB_known'],r['BB_cross'],r['plugin_would_accept_on_original_state'])==(known,cross,held or known and cross)
            assert r['original_tail30_label']==(D(a['net'])>=D('.3')*D(a['cost']))
            unknown+=not known
        result[w]=dict(events=len(rs),flat_kept=sum(not r['actual_signal_CLOSE_held']and r['plugin_would_accept_on_original_state']for r in rs),flat_filtered=sum(not r['actual_signal_CLOSE_held']and not r['plugin_would_accept_on_original_state']for r in rs),held_ADD=sum(r['actual_signal_CLOSE_held']for r in rs))
    for key,ss in summary.items():
        w=key.split('_',1)[0];suffix=key[len(w)+1:];rs=[r for r in rows if r['window']==w]
        if suffix.isdigit():rs=[r for r in rs if r['signal_day'][:4]==suffix]
        elif suffix=='after_924':rs=[r for r in rs if r['signal_day']>='2024-09-24']
        elif suffix=='strict_Oct9_new_fill':rs=[r for r in rs if r['opened'][:10]>='2024-10-09']
        elif suffix=='semiconductor_2026H1':rs=[r for r in rs if r['industry']=='半导体'and r['opened'][:10]>='2026-01-01']
        else:assert suffix=='all'
        groups={'all':rs,'held_ADD_unchanged':[r for r in rs if r['actual_signal_CLOSE_held']],'flat_kept':[r for r in rs if not r['actual_signal_CLOSE_held']and r['plugin_would_accept_on_original_state']],'flat_filtered':[r for r in rs if not r['actual_signal_CLOSE_held']and not r['plugin_would_accept_on_original_state']],'old_tail30':[r for r in rs if r['original_tail30_label']],'old_tail30_filtered':[r for r in rs if r['original_tail30_label']and not r['plugin_would_accept_on_original_state']]}
        for name,sub in groups.items():
            expected=group(sub);actual=ss[name]
            for field,value in expected.items():
                if field in ['original_cost','original_cutoff_net']:assert D(actual[field])==D(value),(key,name,field)
                else:assert actual[field]==value,(key,name,field)
        assert len(groups['flat_kept'])+len(groups['flat_filtered'])+len(groups['held_ADD_unchanged'])==len(rs)
    out=dict(status='PASS_ORIGINAL_COHORT_JOIN_ONLY',rows=3436,unique_window_layer_keys=True,all_source_sha256=True,all_row_original_daily_held_and_feature_exact=True,all_summary_groups_exact=True,unknown_bb_features=unknown,windows=result,accounts=0,projection_runs=0,seconds=time.monotonic()-start,scope='These are original actual filled layers and original signal-CLOSE state. Original future lifecycle net and tail30 labels are evaluation diagnostics, never avoidable losses/new policy PnL. This review does not veto frozen full account comparison or change BB parameters.')
    (R/'ORIGINAL_BB_ASSOCIATION_AUDIT.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n');print(json.dumps(out,ensure_ascii=False))
if __name__=='__main__':main()
