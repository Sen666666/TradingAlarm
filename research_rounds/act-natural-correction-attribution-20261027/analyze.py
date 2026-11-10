import json,gzip,pathlib,itertools,collections
import pandas as pd
P=pathlib.Path('research_rounds/portfolio-correction-20261027');O=pathlib.Path('research_rounds/act-natural-correction-attribution-20261027')
def rows(p):
 with gzip.open(p,'rt') as f:return [json.loads(x) for x in f]
out={}; events=[]; delta=[]; traces=[]
for c in ['S0','S1','S2']:
 root=P/c;ds=rows(root/'accounts-v2/daily.jsonl.gz');dec=rows(root/'accounts-v2/decisions.jsonl.gz');stocks=pd.read_csv(root/'analysis/stocks.csv');campaigns=pd.read_csv(root/'analysis/campaigns.csv');z={}
 for sc in ['base','delay1']:
  aa=[f'ACT{s}__S0_{sc}' for s in range(3)];maps=[{r['at']:r for r in ds if r['account']==a} for a in aa];times=sorted(maps[0]);comp=[]
  for t in times:
   sets=[set(m[t]['positions']) for m in maps];comp.append(dict(at=t,equal=sets[0]==sets[1]==sets[2],nonempty=bool(set.union(*sets)),stocks=[sorted(s) for s in sets],navs=[float(m[t]['nav']) for m in maps]))
  runs=[];start=0
  for i in range(1,len(comp)+1):
   if i==len(comp) or (comp[i]['equal'],comp[i]['nonempty'])!=(comp[start]['equal'],comp[start]['nonempty']):
    if comp[start]['equal']:runs.append(dict(start=comp[start]['at'],end=comp[i-1]['at'],n=i-start,nonempty=comp[start]['nonempty'],start_stocks=comp[start]['stocks'][0],nav_start=comp[start]['navs'],nav_end=comp[i-1]['navs']))
    start=i
  z[sc]={'equal_runs':runs,'initial':comp[5],'final':comp[-1]}
  for a in aa:
   obj=json.loads((root/'accounts-v2'/f'{a}.json').read_text());rs={r['order_id']:r for r in obj['audit_log'] if r['kind']=='reserve'};fs={r['order_id'] for r in obj['audit_log'] if r['kind']=='fill' and r['receipt']['side']=='buy'}
   for r in obj['audit_log']:
    if r['kind']=='risk_checkpoint' and r['event']:events.append({'cohort':c,'account':a,**r})
   z[a]={'zero_fill_expiries':sum(r['kind']=='buy_day_expiry' and r.get('order_id') not in fs for r in obj['audit_log']),'risk_events':[r for r in events if r['cohort']==c and r['account']==a]}
  # initial positions first campaigns
  z[sc]['initial_campaigns']=campaigns[(campaigns.account.isin(aa)) & (campaigns.entry_at.str[:10]<=comp[5]['at'][:10])][['account','symbol','name','entry_at','exit_at','net_pnl']].to_dict('records')
 for seed in range(3):
  a=stocks[stocks.account==f'ACT{seed}__S0_base'].set_index('symbol');b=stocks[stocks.account==f'ACT{seed}__S0_delay1'].set_index('symbol')
  for sid in a.index.union(b.index):
   x=float(a.loc[sid,'net_profit']) if sid in a.index else 0;y=float(b.loc[sid,'net_profit']) if sid in b.index else 0
   delta.append(dict(cohort=c,seed=seed,symbol=sid,name=(a if sid in a.index else b).loc[sid,'name'],base=x,delay=y,difference=y-x))
 for r in dec:
  if r['account'] in ['ACT0__S0_base','ACT0__S0_delay1'] and '2025-10-16'<=r['at'][:10]<='2025-10-31': traces.append({'cohort':c,**r})
 out[c]=z
(O/'convergence.json').write_text(json.dumps(out,ensure_ascii=False,indent=2));pd.DataFrame(delta).to_csv(O/'delay-stock-difference.csv',index=False);pd.DataFrame(events).to_csv(O/'risk-events.csv',index=False);(O/'october-decisions.json').write_text(json.dumps(traces,ensure_ascii=False,indent=2))
for c,z in out.items():
 print('\n',c,'BASE EQUAL RUNS',z['base']['equal_runs'][:12]);print('INITIAL CAMPAIGNS',z['base']['initial_campaigns']);print('RISK',[(a,[(r['at'][:10],r['event']) for r in v['risk_events']],v['zero_fill_expiries']) for a,v in z.items() if a.startswith('ACT')])
d=pd.DataFrame(delta);print('DELTA S0',d[(d.cohort=='S0')&(d.seed==0)].sort_values('difference').head(12).to_string(index=False))
