"""Read-only feasibility: rank candidates, hash inputs, load frozen engine. No replay."""
from pathlib import Path
import json, hashlib, time, math, sys, importlib.util
import pandas as pd

ROOT = Path('/Users/bytedance/Documents/ChatGPT/money')
OLD = ROOT/'research_rounds/pvr-act-comparison-20261027'
PV = ROOT/'research_rounds/pvr-incremental-order-20261029'
OUT = Path(sys.argv[1]); OUT.mkdir(parents=True, exist_ok=True)
timings = {}; t0 = time.monotonic()
def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def save(name, obj):
    (OUT/name).write_text(json.dumps(obj, ensure_ascii=False, indent=2, allow_nan=False))
def ready(r):
    return bool(r['feature_ready']) and all(math.isfinite(float(r[k])) for k in ['h1','age','runup','scale','pvr']) and r['scale']>0
def order(rows, neutral=False):
    remaining = sorted(rows, key=lambda r: (-r['h1'], r['symbol']))
    result = []; steps = []
    while remaining:
        head = remaining[0]
        peers = [head]
        if ready(head):
            peers = [r for r in remaining if ready(r) and abs(r['h1']-head['h1'])<=1 and abs(r['age']-head['age'])<=5 and abs(r['runup']-head['runup'])<=max(r['scale'],head['scale'])]
        chosen = min(peers, key=lambda r: (0 if neutral else -r['pvr'], -r['h1'], r['symbol'])) if ready(head) else head
        steps.append(dict(head=head['symbol'], chosen=chosen['symbol'], eligible_peers=len(peers), changed=chosen['symbol']!=head['symbol'], head_missing=not ready(head), chosen_rank=len(result)+1, head_h1=head['h1'], chosen_h1=chosen['h1'], head_pvr=head['pvr'] if ready(head) else None, chosen_pvr=chosen['pvr'] if ready(chosen) else None, age_gap=abs(chosen['age']-head['age']), runup_gap=abs(chosen['runup']-head['runup']), scale_max=max(chosen['scale'],head['scale']) if ready(head) else None))
        result.append(chosen['symbol']); remaining = [r for r in remaining if r['symbol']!=chosen['symbol']]
    return result, steps

risk = pd.read_parquet(PV/'risk-set.parquet')
assert len(risk)==32899 and not risk.duplicated(['date','symbol']).any()
timings['read_features_seconds'] = time.monotonic()-t0
t=time.monotonic(); allsteps=[]; queues=[]; heads=[]; lookup={}
for (day,sector), g in risk.groupby(['date','sector'], sort=True):
    rows=g.to_dict('records'); ids=[r['symbol'] for r in sorted(rows,key=lambda r:(-r['h1'],r['symbol']))]
    ranked, steps=order(rows)
    assert len(set(ranked))==len(ids) and set(ranked)==set(ids)
    neutral,_=order(rows,True); assert neutral==ids
    reverse,_=order(list(reversed(rows))); assert reverse==ranked
    # Greedy remove-and-repeat is consistent when its already selected prefix leaves the pool.
    for k in range(min(3,len(ranked))):
        suffix,_=order([r for r in rows if r['symbol'] not in set(ranked[:k])]); assert suffix==ranked[k:]
    key=(str(day.date()),sector); lookup[key]=ranked
    for s in steps: s.update(date=key[0],sector=sector); allsteps.append(s)
    heads.append(dict(date=key[0],sector=sector,candidates=len(ids),head=ids[0],chosen=ranked[0],changed=ids[0]!=ranked[0],changed_positions=sum(a!=b for a,b in zip(ids,ranked))))
    for n,sid in enumerate(ranked): queues.append(dict(date=key[0],sector=sector,position=n+1,symbol=sid,original_position=ids.index(sid)+1))
prefixes=[]
for cut in ['2024-12-31','2025-12-31','2026-06-30']:
    count=0
    for (day,sector), g in risk[risk.date.le(cut)].groupby(['date','sector'],sort=True):
        ranked,_=order(g.to_dict('records')); assert ranked==lookup[(str(day.date()),sector)]; count+=1
    prefixes.append(dict(cutoff=cut,industry_days=count,exact=True))
steps=pd.DataFrame(allsteps); heads=pd.DataFrame(heads); queues=pd.DataFrame(queues)
heads.to_csv(OUT/'potential-industry-heads.csv',index=False)
queues.to_csv(OUT/'potential-queues.csv',index=False)
steps.to_csv(OUT/'potential-selection-steps.csv',index=False)
timings['ranking_validation_seconds']=time.monotonic()-t
identity={}; mismatches=[]; t=time.monotonic()
for p,expected in json.loads((OLD/'freeze.json').read_text())['sha256'].items():
    actual=sha(p); identity[p]=actual
    if actual!=expected: mismatches.append(dict(path=p,expected=expected,actual=actual))
pv_identity=json.loads((PV/'input-identity.json').read_text())['sha256']; pv_mismatches=[]
for p,expected in pv_identity.items():
    actual=sha(p); identity[p]=actual
    if actual!=expected: pv_mismatches.append(dict(path=p,expected=expected,actual=actual))
identity[str(PV/'risk-set.parquet')]=sha(PV/'risk-set.parquet')
baseline=json.loads((OLD/'RS/accounts-v2/provenance.json').read_text())
baseline_files=[p for p in (OLD/'RS/accounts-v2').iterdir() if p.is_file()]
for p in baseline_files: identity[str(p)]=sha(p)
timings['input_hash_seconds']=time.monotonic()-t
save('INPUT_IDENTITY.json',dict(sha256=identity,old_freeze_mismatches=mismatches,local_PVR_inputs_mismatches=pv_mismatches))
t=time.monotonic()
spec=importlib.util.spec_from_file_location('pvr_old_for_read_only_probe',OLD/'code/experiment.py'); p=importlib.util.module_from_spec(spec); spec.loader.exec_module(p)
original=p.setup('RS'); bundle,market=p.R.context(); facts=p.E.Facts(bundle,market); p.R.context=original
timings['frozen_context_and_facts_load_seconds']=time.monotonic()-t
cov=dict(no_new_economic_path=True,description='Potential ranking of complete original legal I snapshots, before account occupancy/cash/ACT. Repeated daily eligibility is NOT independent evidence.',legal_snapshots=len(risk),dates=int(risk.date.nunique()),stocks=int(risk.symbol.nunique()),industries=int(risk.sector.nunique()),industry_days=len(heads),multi_candidate_industry_days=int(heads.candidates.ge(2).sum()),industry_days_any_position_changed=int(heads.changed_positions.gt(0).sum()),industry_head_switches=int(heads.changed.sum()),head_switch_dates=int(heads.loc[heads.changed,'date'].nunique()),head_switch_industries=int(heads.loc[heads.changed,'sector'].nunique()),all_recursive_head_promotions=int(steps.changed.sum()),changed_selection_max_h1_gap=float((steps.loc[steps.changed,'head_h1']-steps.loc[steps.changed,'chosen_h1']).abs().max()),changed_selection_max_age_gap=int(steps.loc[steps.changed,'age_gap'].max()),missing_feature_snapshots=int((~risk.feature_ready).sum()),missing_head_fallback_steps=int(steps.head_missing.sum()),sample_head_switches=heads[heads.changed].head(6).to_dict('records'),candidate_set_preserved=True,constant_PVR_recovers_H1=True,iteration_order_invariant=True,selected_prefix_removal_consistent=True,prefixes=prefixes,baseline_replay_seconds_historical=baseline['seconds'],baseline_replay_scenarios=3,baseline_load_rows=dict(stocks=len(bundle.lines),series=len(bundle.series),facts=len(facts.f)),old_freeze_files=len(json.loads((OLD/'freeze.json').read_text())['sha256']),old_freeze_mismatches=mismatches,local_PVR_inputs_files=len(pv_identity),local_PVR_inputs_mismatches=pv_mismatches,current_live_pointer=json.loads((ROOT/'TradingAlarm/runtime/market/current.json').read_text()),frozen_snapshot=json.loads((OLD/'input.json').read_text())['snapshot']['path'],timings=timings,total_seconds=time.monotonic()-t0)
save('PREFLIGHT.json',cov); print(json.dumps(cov,ensure_ascii=False,allow_nan=False),flush=True)
