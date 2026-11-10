"""Independent aggregation of saved labels/ranks; no native account or scores."""
from pathlib import Path
import json,gzip,hashlib,ast,textwrap,collections
import pandas as pd
import numpy as np
O=Path(__file__).resolve().parent;P=O.parent;W=P.parent;OLD=W/'opportunity-quality-ranking-20261031'
def read(p):return json.loads(Path(p).read_text())
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def rows(p):
 with gzip.open(p,'rt') as f:return [json.loads(x) for x in f]
checks=[]
def ok(name,v):assert v,name;checks.append(name)
fr=read(O/'GLOBAL_CONTRACT_FREEZE.json');rf=read(O/'GLOBAL_RANK_FREEZE.json');ok('global contract exact',sha(O/'GLOBAL_CONTRACT.txt')==fr['contract_sha256'])
for n,h in fr['protected_conditional'].items():ok('old conditional unchanged '+n,sha(P/n)==h)
ok('preserved actual initial rank producer',sha(O/'context-key-error-v1/analyze_once.py')==rf['code_sha256'])
def ft(p,name):
 s=Path(p).read_text();n=next(x for x in ast.walk(ast.parse(s)) if isinstance(x,ast.FunctionDef) and x.name==name);return textwrap.dedent('\n'.join(s.splitlines()[n.lineno-1:n.end_lineno]))+'\n'
for name in ['assign','days_pair','tail_capture','weighted_cdf','concentration','composition','conditional']:
 ok('statistics unchanged after context-key fix '+name,ft(O/'analyze_once.py',name)==ft(O/'context-key-error-v1/analyze_once.py',name))
for name in ['stats','paired']:ok('original stats source '+name,(O/f'original_{name}_function.py').read_text()==ft(OLD/'label_and_summarize.py',name))
comparisons=[];na={}
for win in ['2022','2025_26']:
 rank=pd.read_parquet(O/win/'COMMON_RANKS.parquet');ok('rank frozen '+win,sha(O/win/'COMMON_RANKS.parquet')==rf['ranks_sha256'][win]);events=pd.read_parquet(O/win/'LABEL_EVENTS_USED.parquet');label={}
 for r in rows(OLD/win/'PRICE_LABELS.jsonl.gz'):
  for h,z in r['labels'].items():label[r['sid'],r['day'],r['receipt'],int(h)]=z
 for r in events.itertuples():
  z=label[r.sid,r.day,r.receipt,r.horizon]
  assert r.valid==z['valid']
  for key in ['return_pct','MAE_pct','MFE_pct']:assert getattr(r,key)==z[key],(win,r.sid,r.day,key)
 ok('all original label values exact '+win,True)
 source=rows(OLD/win/'CANDIDATES.jsonl.gz');lookup={(r['sid'],r['day'],r['receipt']):r for r in source};keys=set(zip(rank.sid,rank.day,rank.receipt));n=[r for r in source if (r['sid'],r['day'],r['receipt']) not in keys]
 na[win]=dict(unranked_PVR_NA=len(n),ACT_paused=sum(r['B_diag']['ACT_paused'] for r in n),actual_confirmed_fill_receipts=sum(r['B_diag']['selected'] for r in n),actual_probe_fill_receipts=sum(r['B_diag']['probe_mobile_funded'] for r in n),same_stock_core_fill=sum(r['B_diag']['same_stock_core_funded'] for r in n),actual_confirmed_buy_cash=sum(float(r['B_diag']['selected_cash']) for r in n),reasons='PVR85-observation/input ready only, not age/I inheritance')
 for day,g in rank.groupby('day'):
  for m,col in [('H1','H1'),('PVR','PVR')]:
   g=g.sort_values([col,'sid'],ascending=[False,True]);assert list(g['rank_'+m])==list(range(1,len(g)+1))
   qq=np.concatenate([np.full(len(x),q) for q,x in enumerate(np.array_split(np.arange(len(g)),5),1)]);assert np.array_equal(qq,g['Q_'+m].to_numpy())
 ok('both global ranks/array_split exact '+win,True)
 for h in [21,63]:
  full=events[events.horizon.eq(h)].copy()
  for variant,flag in [('all_events',None),('first_stock_attempt_within_window','first_stock_attempt_in_window'),('attempt_started_in_window_first','first_complete_attempt')]:
   g=full if flag is None else full[full[flag]];s=read(O/win/variant/f'SUMMARY_{h}.json');daily={}
   for m in ['H1','PVR']:
    daily[m]=g.groupby(['day','Q_'+m]).return_pct.agg(['count','mean']);ds=set(daily[m].groupby(level=0).size().loc[lambda a:a.eq(5)].index)
    if m=='H1':D=ds
    else:D&=ds
   ok('all-five comparison dates '+str((win,h,variant)),len(D)==s['all_five_common_dates'])
   means={}
   for m in ['H1','PVR']:
    means[m]={}
    for q in range(1,6):
     v=daily[m].xs(q,level=1).reindex(sorted(D))['mean'];mu=float(v.mean()) if len(D) else None;means[m][q]=mu;stored=s['five_band_curves'][m][str(q)]['date_equal_mean'];assert mu is None and stored is None or abs(mu-stored)<1e-10
    t=g[g.day.isin(D)];tailbase=t.groupby('day').right_tail_MFE30.sum();tailtop=t[t['Q_'+m].eq(1)].groupby('day').right_tail_MFE30.sum().reindex(tailbase.index,fill_value=0);valid=tailbase.gt(0);cap=float((tailtop[valid]/tailbase[valid]).mean()) if valid.any() else None;stored=s['top_tail_capture'][m]['date_equal_capture_on_tail_dates'];assert cap is None and stored is None or abs(cap-stored)<1e-10
   delta=means['PVR'][1]-means['H1'][1] if D else None;stored=s['PVR_minus_H1_by_band']['1']['mean_same_day_difference_pct'];assert delta is None and stored is None or abs(delta-stored)<1e-10
   a=g[g.Q_PVR.eq(1)&g.Q_H1.ne(1)&g.day.isin(D)].groupby('day').return_pct.mean();b=g[g.Q_H1.eq(1)&g.Q_PVR.ne(1)&g.day.isin(D)].groupby('day').return_pct.mean();dd=a.index.intersection(b.index);ex=float((a[dd]-b[dd]).mean()) if len(dd) else None;stored=s['PVR_only_minus_H1_only']['mean_same_day_difference_pct'];assert ex is None and stored is None or abs(ex-stored)<1e-10
   cdf=pd.read_parquet(O/win/variant/f'CDF_{h}.parquet')
   if len(cdf):
    for (m,q,field),x in cdf.groupby(['ranking','quintile','field'],sort=False):
     w=np.diff(np.r_[0.,x.cumulative_weight.to_numpy()]);assert w.min()>-1e-12 and abs(w.sum()-1)<1e-9;mu=float((x.value.to_numpy()*w).sum());base=g[g['Q_'+m].eq(q)&g.day.isin(D)].groupby('day')[field].mean().mean();assert abs(mu-base)<1e-8
   comparisons.append(dict(window=win,horizon=h,variant=variant,Q1_delta=delta,exclusive_delta=ex,all_five_days=len(D)))
   ok('fivebands/exclusive/tail/CDF '+str((win,h,variant)),True)
 # Registered conditional analysis has unchanged IDs and equal-pair/date weighting.
 cp=pd.read_parquet(P/win/'PAIRS_PRE_OUTCOMES.parquet');cf=pd.read_parquet(P/win/'FEATURES.parquet');keys2={(r.symbol,str(r.date.date())):(r.symbol,str(r.date.date()),r.receipt) for r in cf.itertuples()};cs=read(O/win/'CONDITIONAL_SEPARATE.json')
 for h in [21,63]:
  a=[]
  for r in cp.itertuples():
   hh=keys2[r.h1_symbol,r.date];pp=keys2[r.pvr_choice_symbol,r.date];a.append(dict(day=r.date,kind=r.pair_kind,delta=label[*pp,h]['return_pct']-label[*hh,h]['return_pct']))
  q=pd.DataFrame(a)
  for name,v in [('all_registered',q),('conflicts',q[q.kind.eq('conflict')])]:
   z=cs[str(h)][name];assert len(v)==z['pairs'] and abs(v.delta.mean()-z['pair_equal_delta'])<1e-10 and abs(v.groupby('day').delta.mean().mean()-z['date_equal_delta'])<1e-10
 ok('conditional registered weights exact '+win,True)
save=dict(passed=True,checks=len(checks),check_names=checks,independent_aggregations=comparisons,label_rows_verified=sum(len(pd.read_parquet(O/w/'LABEL_EVENTS_USED.parquet')) for w in ['2022','2025_26']),economic_paths=0,not_an_independent_agent_audit=True)
(O/'VERIFICATION.json').write_text(json.dumps(save,ensure_ascii=False,indent=2)+'\n');(O/'NA_EXISTING_CAPITAL_CONTEXT.json').write_text(json.dumps(na,ensure_ascii=False,indent=2)+'\n');print('VERIFY_GLOBAL',len(checks),'PASS label rows',save['label_rows_verified'])
