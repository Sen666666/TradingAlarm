"""Describe existing equity-covered baseline and existing signal context. No new score, fit, selection or economics."""
from pathlib import Path
import pandas as pd,numpy as np,json,hashlib
O=Path(__file__).resolve().parent;R=O.parent;E=R/'m3_stock_birth_during_sector_v1';S={}
def src(p):p=Path(p);S[str(p)]=hashlib.sha256(p.read_bytes()).hexdigest();return p
p22=E/'relative_priority_equity_run_2022_v1/report/CORE_AND_FULL_ROUNDS.csv';p24=E/'cash_equity_baseline_2024_v1/report/CORE_AND_FULL_ROUNDS.csv'
a=pd.read_csv(src(p22),low_memory=False);a=a[a.arm.eq('A_UNION_B')].copy();b=pd.read_csv(src(p24),low_memory=False);assert len(a)==2732 and len(b)==1354
z=pd.concat([a,b],ignore_index=True);z['sample']=np.where(z.window.astype(str).eq('2022'),'2022','2024_924');assert z.round_id.is_unique and z.event_id.is_unique
birth=pd.read_csv(src(E/'SEALED_ALL_BIRTH_EVENTS.csv'),low_memory=False);assert birth.event_id.is_unique
cols=[c for c in birth if c not in z or c=='event_id'];z=z.merge(birth[cols],on='event_id',how='left',validate='one_to_one',indicator='event_merge');assert z.event_merge.eq('both').all()
z['day']=pd.to_datetime(z.signal_day)
panel=pd.read_parquet(src(R/'momentum_persistence_breadth_v1/canonical_mu3_comparison_v2/COMMON_K_COMPARISON.parquet'));assert not panel.duplicated(['sector','day']).any();cols=[c for c in panel if c not in z or c in ['sector','day']];z=z.merge(panel[cols],on=['sector','day'],validate='many_to_one')
market=panel.groupby('day').agg(fixed_N=('N','sum'),known_K=('K','sum'),M3_positive=('M3_n','sum'),sector_true=('M3_candidate',lambda x:x.eq(1).sum()),sector_false=('M3_candidate',lambda x:x.eq(0).sum()),sector_unknown=('M3_candidate',lambda x:x.eq(-1).sum()),industry_E0_true=('sector_E0_valid','sum'))
market['market_fixed_M3_lower']=market.M3_positive/market.fixed_N;market['market_fixed_M3_upper']=(market.M3_positive+market.fixed_N-market.known_K)/market.fixed_N;market['market_known_M3_fraction']=market.M3_positive/market.known_K;market=market.reset_index();assert market.fixed_N.eq(1709).all();z=z.merge(market,on='day',validate='many_to_one')
z['quarter']=z.day.dt.to_period('Q').astype(str);z['month']=z.day.dt.to_period('M').astype(str)
z.to_csv(O/'BASELINE_EXISTING_CONTEXT.csv',index=False);market.to_csv(O/'EXISTING_MARKET_CONTEXT.csv',index=False)
def stat(g):
 c=g[g.evidence_usable_closed];closed=g[g.status.eq('COMPLETE_CONDITIONAL_STOCK_ROUND')];w=c[c.core_net>0];l=c[c.core_net<=0]
 return dict(permits=len(g),confirmed_fill=int(g.entry_status.eq('CONDITIONAL_OPEN_PROXY').sum()),conditional_closed=len(closed),execution_unknown=int(g.status.str.contains('UNKNOWN').sum()),nofill=int(g.status.str.contains('NOFILL').sum()),closed_financial_unknown=len(closed)-len(c),usable=len(c),initial_wins=len(w),initial_win_rate=float(c.core_net.gt(0).mean()) if len(c) else None,initial_net=float(c.core_net.sum()),initial_mean_net=float(c.core_net.mean()) if len(c) else None,initial_mean_return=float(c.core_return.mean()) if len(c) else None,average_win=float(w.core_net.mean()) if len(w) else None,average_loss=float(l.core_net.mean()) if len(l) else None,tail30=int(c.core_return.ge(.3).sum()),tail50=int(c.core_return.ge(.5).sum()),full_wins=int(c.net_pnl.gt(0).sum()),full_net=float(c.net_pnl.sum()),full_mean_return=float(c.net_return_on_buy_cash.mean()) if len(c) else None,signal_days=pd.to_datetime(g.signal_day).nunique(),industries=g.sector.nunique())
res=[]
for sample,g in z.groupby('sample'):
 res.append(dict(sample=sample,field='TOTAL',value='ALL',**stat(g)))
 for field in ['event_type','i_buy','g_grade','g_fresh_up','original_sector_authorization','sector_E0_valid','sector_stage','quarter','month']:
  for value,h in g.groupby(field,dropna=False):res.append(dict(sample=sample,field=field,value=str(value),**stat(h)))
pd.DataFrame(res).to_csv(O/'BASELINE_EXISTING_STRATA.csv',index=False)
# These are descriptive current-sample moments, not thresholds to select, train, or run.
ctx=[]
for (sample,category),g in z.assign(category=np.where(~z.evidence_usable_closed,'UNRESOLVED_OR_NOFILL',np.where(z.core_return.ge(.5),'TAIL50',np.where(z.core_net>0,'POSITIVE_UNDER50','NONPOSITIVE')))).groupby(['sample','category']):
 rr=dict(sample=sample,category=category,n=len(g))
 for c in ['PVR_score','g_grade','sector_M3_n','sector_N','sector_run_age','sector_delta3','market_known_M3_fraction','sector_true','sector_unknown']:
  v=pd.to_numeric(g[c],errors='coerce');rr[c+'_known']=int(v.notna().sum());rr[c+'_median']=v.median();rr[c+'_mean']=v.mean()
 ctx.append(rr)
pd.DataFrame(ctx).to_csv(O/'BASELINE_CONTEXT_MOMENTS.csv',index=False)
unknown=z[~z.evidence_usable_closed].copy();unknown.to_csv(O/'BASELINE_UNRESOLVED_AND_NOFILL.csv',index=False)
# Total matches published source reports, not old 1913/1165 closure numbers.
assert (stat(a)['usable'],stat(a)['initial_wins'])==(2616,834)
assert (stat(b)['usable'],stat(b)['initial_wins'])==(1312,530)
source=src(Path(__file__));(O/'BASELINE_SOURCE_HASHES.json').write_text(json.dumps(S,indent=2));print(pd.DataFrame(res).query("field=='TOTAL'").to_string(index=False));print(pd.DataFrame(res).query("field in ['event_type','i_buy','original_sector_authorization']").to_string(index=False))
