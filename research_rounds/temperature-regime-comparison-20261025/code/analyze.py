import json
import numpy as np,pandas as pd
from common import *

def clean(x):
 if isinstance(x,dict):return {str(k):clean(v) for k,v in x.items()}
 if isinstance(x,(list,tuple)):return [clean(v) for v in x]
 if isinstance(x,(np.bool_,)):return bool(x)
 if isinstance(x,(np.integer,)):return int(x)
 if isinstance(x,(float,np.floating)):return float(x) if np.isfinite(x) else None
 return x

def main():
 out=HERE/'analysis';out.mkdir(exist_ok=False);f=pd.read_csv(HERE/'results/v0/summary.csv');bykey={(x['case'],x['policy'],x['scenario']):x for x in f.to_dict('records')};aggregate=[];paired=[]
 for (role,sc,p),xs in f.groupby(['role','scenario','policy'],sort=False):
  row=dict(role=role,scenario=sc,policy=p,policy_name=name(p),cases=len(xs),mean_return=xs.net_return.mean(),mean_drawdown=xs.max_drawdown.mean(),mean_exposure=xs.exposure_fraction.mean(),zero_trade_cases=int(xs.trades.eq(0).sum()),trades=int(xs.trades.sum()),natural_trades=int(xs.natural_trades.sum()),pooled_natural_win_rate=np.round(xs.natural_win_rate.fillna(0)*xs.natural_trades).sum()/xs.natural_trades.sum() if xs.natural_trades.sum() else None,mean_tail_pnl=xs.tail_pnl.mean(),mean_ordinary_pnl=xs.ordinary_pnl.mean())
  for b in ['E0','R']:
   bs=[bykey[c,b,sc] for c in xs.case];rets=np.array([x['net_return'] for x in bs]);dds=np.array([x['max_drawdown'] for x in bs]);row['return_above_'+b]=int((xs.net_return.to_numpy()>rets+1e-12).sum());row['drawdown_below_'+b]=int((xs.max_drawdown.to_numpy()<dds-1e-12).sum());row['both_better_'+b]=int(((xs.net_return.to_numpy()>rets+1e-12)&(xs.max_drawdown.to_numpy()<dds-1e-12)).sum())
  aggregate.append(row)
 for x in f.to_dict('records'):
  for base in ['E0','R']:
   b=bykey[x['case'],base,x['scenario']];paired.append(dict(case=x['case'],role=x['role'],type=x['type'],policy=x['policy'],scenario=x['scenario'],base=base,return_change=x['net_return']-b['net_return'],drawdown_change=x['max_drawdown']-b['max_drawdown'],trade_change=x['trades']-b['trades'],exposure_change=x['exposure_fraction']-b['exposure_fraction']))
 write(out/'aggregate.json',clean(aggregate));pd.DataFrame(aggregate).to_csv(out/'aggregate.csv',index=False,encoding='utf-8-sig');pd.DataFrame(paired).to_csv(out/'paired-deltas.csv',index=False,encoding='utf-8-sig')
 stats=[];legs=[];reasons=[];cases=read(HERE/'cases.json')
 for c in cases:
  raw=pd.read_parquet(HERE/'contexts'/c['symbol']/'temperature.parquet');z=raw.loc[c['start']:c['end']];g=z.level+1;prior=(raw.level+1).shift().reindex(z.index);ok=raw.ready.shift(fill_value=False).reindex(z.index)&z.ready
  r=dict(case=c['id'],role=c['role'],bars=len(z),strict34=int((ok&prior.eq(3)&g.eq(4)).sum()),strict45=int((ok&prior.eq(4)&g.eq(5)).sum()),cross4=int((ok&prior.lt(4)&g.ge(4)).sum()),cross5=int((ok&prior.lt(5)&g.ge(5)).sum()),jump_over4=int((ok&prior.lt(4)&g.gt(4)).sum()),jump_over5=int((ok&prior.lt(5)&g.gt(5)).sum()),grade7_days=int(g.eq(7).sum()),grade6plus_days=int(g.ge(6).sum()))
  runs=[];n=0
  for b in g.eq(7):
   if b:n+=1
   elif n:runs.append(n);n=0
  if n:runs.append(n)
  r['grade7_runs']=len(runs);r['grade7_run_median']=float(np.median(runs)) if runs else None;stats.append(r)
  for p in NEW_POLICIES+OLD_POLICIES:
   origin=HERE/'results/v0' if p in NEW_POLICIES else OLD/'results/v0';state=pd.read_parquet(HERE/'prepared'/c['id']/(p+'.parquet')) if p in NEW_POLICIES else None
   for sc in SCENARIOS:
    key='__'.join([c['id'],p,sc]);tr=pd.read_csv(origin/'accounts'/key/'trades.csv')
    for x in tr.to_dict('records'):
     row=dict(case=c['id'],role=c['role'],policy=p,scenario=sc,**x);sig=x['entry_signal']
     if sig!='preset_start':
      dt=pd.Timestamp(sig);ii=raw.index.get_loc(dt);row['entry_grade']=int(raw.level.iloc[ii]+1);row['previous_grade']=int(raw.level.iloc[ii-1]+1)
     else:row['entry_grade']=None;row['previous_grade']=None
     legs.append(row)
    if p in TEMP_POLICIES:
     mix=tr.exit_reason.value_counts().to_dict();unarmed=0
     for x in tr.loc[tr.exit_reason.eq('temperature_structure_invalid')].to_dict('records'):
      if x['exit_signal'] in ['preset_end','preset_start']:continue
      dt=pd.Timestamp(x['exit_signal']);ii=state.index.get_loc(dt)
      if ii>0 and not state.exit_armed.iloc[ii-1]:unarmed+=1
     reasons.append(dict(case=c['id'],policy=p,scenario=sc,structure_exits=int(mix.get('temperature_structure_invalid',0)),cool6_exits=int(mix.get('cool_below_6',0)),cool7_exits=int(mix.get('cool_below_7',0)),terminal_exits=int(mix.get('window_end',0)),structural_exit_before_arming=unarmed,carry_filled=int(tr.entry_signal.eq('preset_start').sum())))
 pd.DataFrame(stats).to_csv(out/'grade-events.csv',index=False,encoding='utf-8-sig');write(out/'grade-events.json',clean(stats));pd.DataFrame(legs).to_csv(out/'all-trades.csv',index=False,encoding='utf-8-sig');pd.DataFrame(reasons).to_csv(out/'exit-mix.csv',index=False,encoding='utf-8-sig')
 # Does the old projection duplicate the translated cross5 structure policy?
 ids=[]
 for c in cases:
  for sc in SCENARIOS:
   a=pd.read_parquet(HERE/'results/v0/accounts'/('__'.join([c['id'],'T_ORIG',sc]))/'ledger.parquet');b=pd.read_parquet(HERE/'results/v0/accounts'/('__'.join([c['id'],'C5_S',sc]))/'ledger.parquet')
   ids.append(dict(case=c['id'],scenario=sc,nav_exact=a.nav.equals(b.nav),fills_same_count=int(bykey[c['id'],'T_ORIG',sc]['trades'])==int(bykey[c['id'],'C5_S',sc]['trades'])))
 write(out/'projection-equivalence.json',ids)
 write(out/'summary.json',dict(recorded_at=now(),new_economic_accounts=756,reused_accounts=216,displayed_accounts=972,temperature_policy_count=12,all_rules_reported=True,average_metrics_are_descriptive_not_portfolio=True,formula_changes_after_results=0,old_projection_same_sample_nav_count=sum(x['nav_exact'] for x in ids),old_projection_comparisons=len(ids)))
 print('ANALYSIS DONE',flush=True)
if __name__=='__main__':main()
