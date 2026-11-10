"""Fixed45%initialcapital passive risk comparator; no outcome-fitted risk scaling."""
import json
from pathlib import Path
import pandas as pd
from hk_extension import load_extended
from hk_in_kind_campaign import load_assets
from campaign_claims import CampaignClaims
from monthly_ah_engine import run
from strategy_signals import period_metrics
from monthly_claim_ledger_audit import reconcile as reconcile_claims
from campaign_completion_ledger_audit import reconcile as reconcile_cash
OUT=Path('results/passive-half-benchmark')
def main():
 OUT.mkdir(exist_ok=True,parents=True);protocol=dict(initial_target=.45,rule='Constant0.5exposure withoriginal90%equalassetweights; no rebalancing or cashreinvestment. Fixedhalf comparator not optimized to realizedvolatility.',period=['2022-01-01','2026-10-16'],purpose='Compare passive riskreduction versus trading; not a strategyrecommendation. Same selectedsurvivorpools.')
 (OUT/'protocol.json').write_text(json.dumps(protocol,indent=2));etf,_=load_extended();hk,_=load_assets();hk={s:dict(a,lot=400 if s=='HK00005' else 100) for s,a in hk.items()};rows=[]
 for group,assets in [('etf17',etf),('hk7',hk)]:
  signals={s:pd.Series(.5,index=a['signal'].index) for s,a in assets.items()};recipients={s:hk[s] for s in ['HK09618','HK03690']}
  for sc,cost,fx,delay in [('base',15,10,0),('cost2',30,20,0),('delay1',15,10,1)]:
   claims=CampaignClaims(assets,recipients) if group=='hk7' else None;m,p,o,_=run(assets,*protocol['period'],policy='score_change',signals=signals,cadence='daily',security_claims=claims,cost=cost,fx_cost=fx,delay=delay);assert all(x['units']>0 for x in o)
   check=reconcile_claims(assets,p,o,cost,fx,recipients) if claims else reconcile_cash(assets,p,o,cost,fx);case=f'{group}-{sc}';p.to_parquet(OUT/f'{case}-path.parquet');(OUT/f'{case}-orders.json').write_text(json.dumps(o));rows.append(dict(group=group,scenario=sc,**m,year2026=period_metrics(p,'2026-01-01','2026-10-16'),ledger=check))
 (OUT/'results.json').write_text(json.dumps(rows,indent=2));(OUT/'validation.json').write_text(json.dumps(dict(ledgers=len(rows),max_error=max(max(r['ledger'].values()) for r in rows)),indent=2));print([(r['group'],r['scenario'],r['total_return'],r['max_drawdown']) for r in rows])
if __name__=='__main__':main()
