"""Read-only fixed-label comparison after the new stage/rank artifact is frozen."""
from pathlib import Path
import hashlib,json,math
import numpy as np
import pandas as pd

B=Path(__file__).resolve().parent;E=B.parent
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def clean(v):
    if isinstance(v,dict):return {str(k):clean(x)for k,x in v.items()}
    if isinstance(v,list):return [clean(x)for x in v]
    if isinstance(v,np.generic):v=v.item()
    return None if isinstance(v,float)and not np.isfinite(v)else v
receipt=json.loads((B/'RANK_FREEZE_RECEIPT.json').read_text())
assert sha(B/'STAGED_PRIOR_RANKS.parquet')==receipt['stage_rank_sha256']
ranks=pd.read_parquet(B/'STAGED_PRIOR_RANKS.parquet');labeled=[];inputs={}
for day,q in ranks.groupby('day'):
    root=E/'pvr_924_discrimination_v1'if day=='2024-09-24'else E/'full_local_signal_two_dates_v1'/day
    p=root/'paths/HORIZON_PATHS.parquet';x=pd.read_parquet(p)
    assert set(x.sid)==set(q.sid) and x.sid.is_unique
    fields=['sid']+[n for n in x.columns if n.startswith(('h5_','h20_'))]
    m=q.merge(x[fields],on='sid',how='left',validate='one_to_one')
    assert len(m)==len(q) and m[['h5_complete','h20_complete']].notna().all().all() and m.h5_complete.all()and m.h20_complete.all()
    labeled.append(m);inputs[day]=dict(path=str(p),sha256=sha(p))
x=pd.concat(labeled,ignore_index=True)
stats=[];composition=[];changes=[];tails=[]
for day,g in x.groupby('day'):
    n=len(g)
    for phase,f in g.groupby('phase'):
        composition.append(dict(day=day,phase=phase,N=len(f),known_PVR=int(f.score.notna().sum()),
            original_top20=int(f.rank_ALL_LOCAL_I_BUY.le(20).sum()),new_top20=int(f.rank_STAGE_PVR.le(20).sum()),
            original_top100=int(f.rank_ALL_LOCAL_I_BUY.le(100).sum()),new_top100=int(f.rank_STAGE_PVR.le(100).sum()),
            no_reference=int(f.no_confirmed_peak_reference.sum())))
    for h in [5,20]:
        tailsets={p:set(g.sort_values([f'h{h}_return','sid'],ascending=[False,True]).head(math.ceil(n*p/100)).sid)for p in [1,5]}
        for scheme,col in [('ORIGINAL_PVR','rank_ALL_LOCAL_I_BUY'),('STAGE_PVR','rank_STAGE_PVR')]:
            groups={'ALL':g,'RANKABLE':g.loc[g[col].notna()]}
            groups.update({f'PHASE_{p}':f for p,f in g.groupby('phase')})
            for k in [20,100]:
                groups[f'TOP{k}']=g.loc[g[col].le(k)]
                groups[f'REST{k}']=g.loc[g[col].gt(k)]
            for band,f in groups.items():
                ret=f[f'h{h}_return']
                stats.append(dict(day=day,h=h,scheme=scheme,band=band,N=len(f),
                    terminal_mean=ret.mean(),terminal_median=ret.median(),positive_fraction=ret.gt(0).mean()if len(f)else np.nan,
                    MFE_mean=f[f'h{h}_max_up'].mean(),MAE_mean=f[f'h{h}_max_adverse'].mean(),
                    top1pct_hit=len(set(f.sid)&tailsets[1]),top1pct_denominator=len(tailsets[1]),
                    top5pct_hit=len(set(f.sid)&tailsets[5]),top5pct_denominator=len(tailsets[5])))
        for p,ss in tailsets.items():
            for sid in sorted(ss):tails.append(dict(day=day,h=h,tail_percent=p,sid=sid))
    for k in [20,100]:
        a=set(g.loc[g.rank_ALL_LOCAL_I_BUY.le(k),'sid']);b=set(g.loc[g.rank_STAGE_PVR.le(k),'sid'])
        for kind,ss in [('DROPPED',a-b),('ADDED',b-a),('KEPT',a&b)]:
            f=g.loc[g.sid.isin(ss)].copy();f['comparison_topK']=k;f['change']=kind;changes.append(f)

summary=pd.DataFrame(stats);comp=pd.DataFrame(composition);chg=pd.concat(changes,ignore_index=True)
x.to_parquet(B/'STAGE_RANKS_WITH_EXISTING_PRICE_LABELS.parquet',index=False)
summary.to_csv(B/'GROUP_COMPARISONS.csv',index=False);comp.to_csv(B/'PHASE_COMPOSITION.csv',index=False)
chg.to_csv(B/'TOPK_MEMBERSHIP_CHANGES.csv',index=False)
pd.DataFrame(tails).to_csv(B/'EXPOST_TAIL_LABELS_ONLY.csv',index=False)
cases=json.loads((B/'FREEZE.json').read_text())['cases']
snap=pd.read_parquet(B/'ALL_REQUEST_STAGE_SNAPSHOTS.parquet')
case=snap.loc[snap.sid.isin(cases)].copy()
case=case.merge(x[['sid','day','current_name','score','rank_ALL_LOCAL_I_BUY','rank_STAGE_PVR','rank_WITHIN_PHASE','h5_return','h20_return','h20_max_up','h20_max_adverse']],on=['sid','day'],how='left',validate='one_to_one')
cohort_keys=set(zip(x.day,x.sid))
case['original_i_buy_member']=[(d,s)in cohort_keys for d,s in zip(case.day,case.sid)]
original=[]
for day in sorted(case.day.unique()):
    rawpath=E/'full_local_signal_20240924_v1/signals/ALL_SIGNALS.parquet'if day=='2024-09-24'else E/'full_local_signal_two_dates_v1'/day/'signals/ALL_SIGNALS.parquet'
    raw=pd.read_parquet(rawpath)[['sid','day','signal_status','e0_ready','g_ready','i_target','i_buy']]
    original.append(raw)
case=case.merge(pd.concat(original,ignore_index=True),on=['sid','day'],how='left',validate='one_to_one')
case.to_csv(B/'PREDECLARED_CASE_STAGE_AND_RANK.csv',index=False)
examples=[]
for (day,k,kind),g in chg.loc[chg.change.ne('KEPT')].groupby(['day','comparison_topK','change']):
    f=g.sort_values(['h20_return','sid'],ascending=[kind=='ADDED',True]).head(5)
    examples.append(f)
pd.concat(examples,ignore_index=True).to_csv(B/'EXPOST_REPLACEMENT_COUNTEREXAMPLES.csv',index=False)
out=dict(status='COMPLETE_FIXED_STAGE_PRIORITY_DIAGNOSTIC_NOT_ACCOUNT',cohort_rows=len(x),
    by_date={d:len(g)for d,g in x.groupby('day')},frozen_stage_rank_sha256=receipt['stage_rank_sha256'],
    outcome_inputs_read_only=inputs,ranking_changed_from_outcomes=False,accounts=0,
    limits=['Lexicographic phase priority can exclude all START from finite topK;all-cohort retention is not protection from this cost.',
    'Historical local pool and corporate action/ST/halt/trading-eligibility nonPIT remain.','Fixed20close tails are not long-term strategy tail profits;overlapping correlated dates not IID.'])
(B/'DIAGNOSTIC_RECEIPT.json').write_text(json.dumps(clean(out),ensure_ascii=False,indent=2)+'\n')
print(summary.loc[summary.band.isin(['TOP20','TOP100'])][['day','h','scheme','band','N','terminal_mean','top1pct_hit']].to_string(index=False))
print(comp.to_string(index=False))
