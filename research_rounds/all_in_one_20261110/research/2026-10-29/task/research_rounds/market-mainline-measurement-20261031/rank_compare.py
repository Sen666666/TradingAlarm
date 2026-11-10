"""Cached-only, matched stock-count budget comparison. No new signals/accounts."""
from pathlib import Path
import json,time,signal,hashlib
import pandas as pd,numpy as np
O=Path(__file__).resolve().parent;OUT=O/'rank-comparison';OUT.mkdir(exist_ok=False);START=time.monotonic()
def save(p,x):Path(p).write_text(json.dumps(x,ensure_ascii=False,indent=2,default=str,allow_nan=False))
def main():
 signal.signal(signal.SIGALRM,lambda *_:(_ for _ in ()).throw(TimeoutError('30s cached-only ranking comparison')));signal.alarm(30)
 m=pd.read_parquet(O/'FEATURE_MATRIX_90.parquet');lab=np.load(O/'STOCK_PRICE_LABELS.npz');mask=np.load(O/'STOCK_DATA_MASKS.npz');op=pd.read_csv(O/'OPPORTUNITIES_WITH_BOUNDARIES.csv');days=sorted(m.day.unique());sectors=sorted(m.sector.unique());G=len(sectors);T=len(days);dmap={d:i for i,d in enumerate(days)};sids=[str(s) for s in lab['symbols']];smap={s:i for i,s in enumerate(sids)};gmap={g:i for i,g in enumerate(sectors)};sg=np.array([gmap[str(g)] for g in lab['sector']]);known=mask['current_price_known'];assert known.shape==(T,len(sids));n=np.column_stack([known[:,sg==g].sum(axis=1) for g in range(G)])
 def field(k):return m.pivot(index='day',columns='sector',values=k).loc[days,sectors].to_numpy()
 P=field('price_qualified').astype(bool);scores={'R21':field('relative_R21'),'H1':field('H1_original'),'attention':field('attention_ratio')};common=P.copy()
 for s in scores.values():common&=np.isfinite(s)
 excluded=int((n*(P&~common)).sum());assert excluded==0,'Unexpected unequal score availability; report before comparing'
 denom=(n*common).sum(axis=1);A=field('price_and_attention').astype(bool)&common;targetA=(n*A).sum(axis=1);fullstock=int(known.sum());opgroups={'ALL':np.ones(len(op),bool),'internal':(~op.left_boundary_censored&~op.right_boundary_open).to_numpy(),'left_only':(op.left_boundary_censored&~op.right_boundary_open).to_numpy(),'right_only':(~op.left_boundary_censored&op.right_boundary_open).to_numpy(),'both_boundaries':(op.left_boundary_censored&op.right_boundary_open).to_numpy()};anchors=[]
 for r in op.itertuples():
  j=smap[r.stock];lo=dmap[r.first_anchor];hi=dmap[r.last_anchor];ts=np.flatnonzero(lab['main_tail'][lo:hi+1,j])+lo;anchors.append((ts,sg[j],lo))
 curve=[];readouts=[];costs={}
 def evaluate(method,bound,cost,budget,label):
  selected=(cost<=budget[:,None]) if bound=='under' else (cost<budget[:,None]);selected&=common
  if bound=='over':selected[budget<=0]=False
  anycov=[];first=[];delay=[]
  for ts,g,lo in anchors:
   yes=ts[selected[ts,g]];anycov.append(bool(len(yes)));first.append(bool(selected[lo,g]));delay.append(int(yes[0]-lo) if len(yes) else np.nan)
  anycov=np.array(anycov);first=np.array(first);delay=np.array(delay);kept=int((n*selected).sum());r=dict(readout=label,method=method,bound=bound,requested_stock_days=float(budget.sum()),actual_stock_days=kept,actual_fraction_full=kept/fullstock,actual_fraction_P=kept/denom.sum(),budget_gap_stock_days=float(kept-budget.sum()),daily_max_abs_budget_gap=float(np.max(np.abs((n*selected).sum(axis=1)-budget))),covered=int(anycov.sum()),first=int(first.sum()),delay_median=float(np.nanmedian(delay)) if np.isfinite(delay).any() else None,delay_p90=float(np.nanquantile(delay,.9)) if np.isfinite(delay).any() else None)
  for name,gm in opgroups.items():r[name+'_n']=int(gm.sum());r[name+'_covered']=int((gm&anycov).sum());r[name+'_first']=int((gm&first).sum())
  if label=='actual_attention_daily_budget':np.savez_compressed(OUT/f'{method}-{bound}-actual-budget.npz',covered=anycov,first=first,delay=delay)
  return r
 for method,score in scores.items():
  after=np.full((T,G),np.inf);before=after.copy()
  for t in range(T):
   gs=np.flatnonzero(common[t]&n[t].astype(bool));gs=gs[np.lexsort((gs,-score[t,gs]))];cum=np.cumsum(n[t,gs]);after[t,gs]=cum;before[t,gs]=cum-n[t,gs]
  costs[method]=(after,before)
  for bound,cost in [('under',after),('over',before)]:
   threshold=cost/denom[:,None];anyreq=np.array([np.min(threshold[ts,g]) for ts,g,lo in anchors]);firstreq=np.array([threshold[lo,g] for ts,g,lo in anchors]);weights=n[common];values=threshold[common];order=np.argsort(values);values=values[order];cumweights=np.r_[0,np.cumsum(weights[order])];side='right' if bound=='under' else 'left'
   for fraction in np.linspace(0,1,101):
    kept=int(cumweights[np.searchsorted(values,fraction,side=side)]);cov=(anyreq<=fraction) if bound=='under' else (anyreq<fraction);first=(firstreq<=fraction) if bound=='under' else (firstreq<fraction)
    if fraction==0:kept=0;cov[:]=False;first[:]=False
    row=dict(method=method,bound=bound,budget_fraction_P=fraction,actual_stock_days=kept,actual_fraction_full=kept/fullstock,actual_fraction_P=kept/denom.sum(),requested_stock_days=float(fraction*denom.sum()),budget_gap_stock_days=float(kept-fraction*denom.sum()))
    for name,gm in opgroups.items():row[name+'_covered']=int((gm&cov).sum());row[name+'_first']=int((gm&first).sum())
    curve.append(row)
   for fraction in [.2,.4,.6,.8,1.]:readouts.append(evaluate(method,bound,cost,denom*fraction,f'P_fraction_{fraction:.1f}'))
   readouts.append(evaluate(method,bound,cost,targetA.astype(float),'actual_attention_daily_budget'))
 pd.DataFrame(curve).to_csv(OUT/'COVERAGE_COMPRESSION_CURVE_1PCT.csv',index=False);pd.DataFrame(readouts).to_csv(OUT/'FIXED_READOUTS.csv',index=False);np.savez_compressed(OUT/'EXACT_DAILY_PREFIX_BUDGETS.npz',dates=np.array(days),sectors=np.array(sectors),stock_count=n,P_common=common,actual_attention_budget=targetA,**{k+'_'+b:v for k,(a,z) in costs.items() for b,v in [('after',a),('before',z)]})
 # All-P and the actual threshold budget provide exact prior-result controls.
 for r in readouts:
  if r['readout']=='P_fraction_1.0':assert r['actual_stock_days']==166403 and r['covered']==1368 and r['first']==763
 r=[r for r in readouts if r['readout']=='actual_attention_daily_budget' and r['method']=='attention' and r['bound']=='over'][0];assert r['actual_stock_days']==99738 and r['covered']==1260 and r['first']==436
 save(OUT/'VERIFICATION.json',dict(passed=True,elapsed_seconds=time.monotonic()-START,new_indicators=0,new_economic_paths=0,common_unknown_stock_days=excluded,P_stock_days=int(denom.sum()),full_price_known_stock_days=fullstock,actual_attention_stock_days=int(targetA.sum()),groups={k:int(v.sum()) for k,v in opgroups.items()},whole_industries_only=True,under_and_over_budget_brackets=True,curves='0..100% every1%; exact daily staircase breakpoints saved separately',future_labels_reused_not_recomputed=True))
 print(pd.DataFrame(readouts).query("readout=='actual_attention_daily_budget'")[['method','bound','actual_stock_days','actual_fraction_P','budget_gap_stock_days','covered','first','delay_median','internal_covered','internal_first']].to_string(index=False),flush=True);print('SECONDS',time.monotonic()-START,flush=True)
if __name__=='__main__':
 try:main()
 finally:signal.alarm(0)
