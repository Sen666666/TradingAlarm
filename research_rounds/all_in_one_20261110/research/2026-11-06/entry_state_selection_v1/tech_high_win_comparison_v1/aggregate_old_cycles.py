import csv,json,statistics,collections
from pathlib import Path
r=Path('/Users/bytedance/Documents/ChatGPT/money/research_rounds')
def agg(rows):
 p=[float(x['net_pnl']) for x in rows];w=[v for v in p if v>0];l=[v for v in p if v<0]
 return dict(n=len(p),w=len(w),wr=len(w)/len(p) if p else None,meanwin=statistics.mean(w) if w else None,meanloss=-statistics.mean(l) if l else None,payoff=statistics.mean(w)/-statistics.mean(l) if w and l else None,net=sum(p),tail30=sum(float(x['net_return'])>=.3 for x in rows))
for cohort in ['TECH','DRUG']:
 ds=list(csv.DictReader((r/f'cp1-cross-sector-20261028/{cohort}/analysis/campaigns.csv').open()))
 for pol in ['ACT','S','SF','SW3F','SAMT']:
  b=[x for x in ds if x['policy']==pol and x['scenario']=='base']
  closed=[x for x in b if x['closed']=='True']
  cut=[x for x in closed if x['exit_at'][:10]<='2026-05-15']
  bcut=[x for x in b if x['entry_at'][:10]<='2026-05-15']
  print(cohort,pol,'FULL',json.dumps(agg(closed)),'EXIT_CUT',json.dumps({**agg(cut),'entered_by_cut':len(bcut),'not_exit_by_cut':len(bcut)-len(cut)}))
 print('columns',list(ds[0]))
