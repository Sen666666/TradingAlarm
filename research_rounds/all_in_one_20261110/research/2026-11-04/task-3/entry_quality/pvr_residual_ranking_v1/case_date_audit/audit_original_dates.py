"""Read saved candidate/feature/book records only. No score/model/account run."""
from pathlib import Path
from collections import Counter
import gzip,hashlib,json,math
import pandas as pd
import numpy as np

OUT=Path(__file__).resolve().parent
ROOT=OUT.parents[1]
P=ROOT/'pvr_information_v1'
B=ROOT/'trend_exit_controls_v1/runs/BASELINE'
STRONG={'300666.SZ','603061.SH','301611.SZ'}
inputs={}
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def clean(x):
    if isinstance(x,dict):return {str(k):clean(v)for k,v in x.items()}
    if isinstance(x,(list,tuple)):return [clean(v)for v in x]
    if x is None or x is pd.NA or x is pd.NaT:return None
    if isinstance(x,pd.Timestamp):return str(x)
    if isinstance(x,np.generic):x=x.item()
    return None if isinstance(x,float)and not math.isfinite(x)else x
def save(n,x):(OUT/n).write_text(json.dumps(clean(x),ensure_ascii=False,indent=2,allow_nan=False)+'\n')
def stream(p,gz=False):
    p=Path(p);inputs[str(p.resolve())]=sha(p)
    with (gzip.open(p,'rt')if gz else p.open())as f:
        for line in f:yield json.loads(line)

logs=[]
for window in ['2022_2024','strong']:
    for row in stream(B/window/'pair/rank-policy.jsonl.gz',True):logs.append(dict(window=window,**row))
assert len(logs)==133713
L=pd.DataFrame(logs)
assert not L.duplicated(['window','day','sid']).any()
L['round12']=L.PVR.map(lambda x:None if pd.isna(x)else round(float(x),12))
L['PVR_candidate_ordinal_1based']=L.final_slot+1
L['H1_candidate_ordinal_1based']=L.original_slot+1

def target(r):
    return (r['window']=='strong'and r['sid']in STRONG)or(r['window']=='2022_2024'and r['sid']=='000620.SZ')or(r['window']=='2022_2024'and r['sid']=='300085.SZ'and'2024-09-01'<=r['day']<='2024-10-09')
T=L[L.apply(target,axis=1)].copy()
selected_days=set(zip(T.window,T.day))
competition=L[[tuple(x)in selected_days for x in L[['window','day']].to_numpy()]].copy()
fpath=P/'export/features.parquet';inputs[str(fpath.resolve())]=sha(fpath)
feature_columns=['sid','day','window','sector','r','scale','u','b','e','E','score','pvr_status',
 'pvr_valid_observation','return5','return5_status','return20','return20_status',
 'sign_persistence21_w09','sign_persistence21_w09_status','logreturn_std20',
 'close_gap_prior_high20','breakout_prior_high20','sector_return20','relative_return20','relative_return20_status']
F=pd.read_parquet(fpath,columns=feature_columns,filters=[('day','in',sorted({d for _,d in selected_days}))])
assert not F.duplicated(['window','day','sid']).any()
C=competition.merge(F,on=['window','day','sid'],how='left',validate='one_to_one',indicator=True)
assert (C._merge=='both').all()
known=C.PVR_ready
assert np.max(np.abs(C.loc[known,'PVR']-C.loc[known,'score']))<1e-10
assert np.max(np.abs(C.loc[known,'PVR']-(50+50*np.tanh(2*C.loc[known,'E']))))<1e-10
assert C.loc[known,'PVR'].notna().all()
C['lag20_log_momentum']=np.log1p(C.return20)
C['same_day_candidate_count']=C.groupby(['window','day']).sid.transform('count')
C['same_day_return20_pct_rank_average']=C.groupby(['window','day']).return20.rank(method='average',pct=True)
C['same_day_E_pct_rank_average']=C.groupby(['window','day']).E.rank(method='average',pct=True)
C['same_day_round12_tie_n']=C.groupby(['window','day','round12']).sid.transform('count')
CT=C[C.apply(target,axis=1)].copy();assert len(CT)==len(T)
save('ALL_TARGET_ORIGINAL_CANDIDATE_DATES.json',CT.drop(columns=['_merge']).to_dict('records'))
C.drop(columns=['_merge']).to_parquet(OUT/'ALL_TARGET_DATES_SAME_DAY_COMPETITORS.parquet',index=False)
CT.drop(columns=['_merge']).to_csv(OUT/'ALL_TARGET_ORIGINAL_CANDIDATE_DATES.csv',index=False)

# Verify PRIMARY inventory identity and preserve original causal event fields.
primary=[]
for r in stream(P/'universe_audit/PRIMARY_CANDIDATES.jsonl'):
    if (r['window'],r['day'])in selected_days:primary.append(r)
assert len(primary)==len(C)
assert {(r['window'],r['day'],r['sid'])for r in primary}==set(C[['window','day','sid']].itertuples(index=False,name=None))
save('ORIGINAL_PRIMARY_CANDIDATE_ROWS_ON_SELECTED_DATES.json',primary)

actual=[];intent_rows=[]
for window in ['2022_2024','strong']:
    path=B/window/'pair/B.json.gz';inputs[str(path.resolve())]=sha(path)
    with gzip.open(path,'rt')as f:book=json.load(f)
    for t in book['trades']:
        r=dict(window=window,sid=t['security_id'],day=t.get('signal_at','')[:10])
        if t['side']=='buy'and target(r):actual.append(dict(window=window,**t))
    for decision in book['decisions']:
        day=decision['at'][:10]
        if (window,day)not in selected_days:continue
        for intent in decision['intents']:
            if target(dict(window=window,day=day,sid=intent['sid'])):
                intent_rows.append(dict(window=window,day=day,**intent))
save('ACTUAL_TARGET_BUYS_ORIGINAL_BOOK.json',actual)
save('TARGET_ORIGINAL_INTENT_FIELDS.json',intent_rows)

# Reconstruct the actual native slot mapping, not a new candidate score.
reconstruction=Counter();tie_groups=[]
for(window,day),g in L.groupby(['window','day'],sort=False):
    g=g.sort_values('original_slot');assert g.original_slot.tolist()==list(range(len(g)))
    records=g.to_dict('records');ready=[r for r in records if r['PVR_ready']]
    ready.sort(key=lambda r:(-round(float(r['PVR']),12),r['original_slot']))
    it=iter(ready);final=[r if not r['PVR_ready']else next(it)for r in records]
    slots=[r['original_H1_rank']for r in records]
    for pos,r in enumerate(final):
        assert r['final_slot']==pos and r['priority_rank']==slots[pos]
        reconstruction[window]+=1
    for value,t in g[g.PVR_ready].groupby('round12'):
        if len(t)>1:tie_groups.append(dict(window=window,day=day,score_round12=value,n=len(t),members=t.to_dict('records')))
save('ALL_NATIVE_ROUND12_TIE_GROUPS.json',tie_groups)
ties_by=Counter();rows_by=Counter()
for r in tie_groups:ties_by[r['window']]+=1;rows_by[r['window']]+=r['n']

actual_keys={(x['window'],x['signal_at'][:10],x['security_id'])for x in actual}
strong_actual=CT[CT.apply(lambda r:(r['window'],r['day'],r['sid'])in actual_keys,axis=1)&(CT.window=='strong')]
save('STRONG_THREE_STOCK_ACTUAL_SIGNAL_FEATURES.json',strong_actual.drop(columns=['_merge']).to_dict('records'))
special=[]
for(window,day),g in C.groupby(['window','day'],sort=True):
    targets=g[g.apply(target,axis=1)]
    if not any((window,day,r.sid)in actual_keys and window=='strong'for r in targets.itertuples())and not(window=='2022_2024'and((targets.sid=='000620.SZ')&(targets.final_slot==1)).any())and not(window=='2022_2024'and day in ['2024-09-12','2024-09-24','2024-09-25','2024-09-27']):continue
    special.append(dict(window=window,day=day,n=len(g),targets=targets.drop(columns=['_merge']).to_dict('records'),
        original_PVR_first10=g.sort_values('final_slot').head(10).drop(columns=['_merge']).to_dict('records'),
        original_H1_first10=g.sort_values('original_slot').head(10).drop(columns=['_merge']).to_dict('records')))
save('KEY_SAME_DAY_COMPETITION_GROUPS.json',special)
summary=dict(status='READ_ONLY_ORIGINAL_RANK_CASE_AUDIT_COMPLETE',
    rank_log_rows=len(L),rank_rows_by_window=L.groupby('window').size().to_dict(),
    all_target_candidate_dates_n=len(CT),strong_target_counts=CT[CT.window=='strong'].groupby('sid').size().to_dict(),
    all_selected_day_groups=len(selected_days),same_day_competitor_rows=len(C),
    original_slot_policy_reconstructed_rows=dict(reconstruction),
    original_PVR_round12_tie_groups=dict(ties_by),original_PVR_tied_candidate_rows=dict(rows_by),
    score100_n=int((L.PVR==100).sum()),score_range_by_window=L.groupby('window').PVR.agg(['min','max']).to_dict('index'),
    selected_groups_u_exact_abs1_n=int((C.u.abs()==1).sum()),selected_groups_scope_for_u=len(C),
    x000620_numeric_priority_key1_dates=CT[(CT.sid=='000620.SZ')&(CT.priority_rank==1)].day.tolist(),
    x000620_candidate_ordinal2_dates=CT[(CT.sid=='000620.SZ')&(CT.final_slot==1)].day.tolist(),
    strong_actual_buys=len(strong_actual),new_accounts=0,new_scores=0,new_residuals=0,new_model_runs=0,
    rank_interpretation='priority_rank reuses original H1 numeric keys with gaps after sorting ONLY original pending unique-stock candidates by PVR; it is not global PVR rank. final_slot+1 is candidate ordinal.',
    tie_policy='descending round(PVR,12), then original H1 pending order; UNKNOWN retains original slot; within same stock CORE before MOBILE unchanged',
    source_sha256=inputs)
assert all(sha(p)==h for p,h in inputs.items())
save('AUDIT_SUMMARY.json',summary)
print(json.dumps(clean({k:v for k,v in summary.items()if k!='source_sha256'}),ensure_ascii=False))
