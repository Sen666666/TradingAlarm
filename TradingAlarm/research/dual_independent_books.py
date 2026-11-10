"""Two separately funded21/63trend accounts; combine wealth, never averaged target shares."""
import json
from pathlib import Path
import pandas as pd
from hk_extension import load_extended
from hk_in_kind_campaign import load_assets
from campaign_claims import CampaignClaims
from monthly_ah_engine import run
from strategy_signals import build_signals,period_metrics
from monthly_claim_ledger_audit import reconcile as reconcile_claims
from campaign_completion_ledger_audit import reconcile as reconcile_cash
OUT=Path('results/dual-independent-books')
def main():
 OUT.mkdir(parents=True,exist_ok=True);protocol=dict(capital_per_book=500000,models=['short21','medium63'],participation_per_book=.005,period=['2022-01-01','2026-10-16'],rule='Eachbook ownsitscash/shares/receipts/claims with90%equalnameallocation andnativebinarytrend. Nointerbooktransfer or resizingotherbook whenonesignalchanges. Aggregatewealth. PartitionADV1%into0.5%each; separatefeeschargedwithoutnetting.',limits='Conservativepartitioncanleavecapacityunused; twoseparateaccounts incurmoreminimumfees than nettedbrokerorders. Samepreviouslyreviewedsurvivorpool; no freshholdout ornewsignal.')
 (OUT/'protocol.json').write_text(json.dumps(protocol,indent=2));etf,_=load_extended();hk,_=load_assets();hk={s:dict(a,lot=400 if s=='HK00005' else 100) for s,a in hk.items()};results=[];checks=[];controls=0
 for group,assets in [('etf17',etf),('hk7',hk)]:
  recipients={s:hk[s] for s in ['HK09618','HK03690']};signals={name:build_signals(assets,name) for name in protocol['models']}
  for name in protocol['models']:
   claims=CampaignClaims(assets,recipients) if group=='hk7' else None
   _,p,o,_=run(assets,*protocol['period'],policy='score_change',signals=signals[name],cadence='daily',security_claims=claims);ref=Path('results/trend-workbench-v1')/f'{group}-{name}-daily-base';pd.testing.assert_frame_equal(p,pd.read_parquet(str(ref)+'-path.parquet'),check_exact=True);assert o==json.loads(Path(str(ref)+'-orders.json').read_text());controls+=1
  for scenario,cost,fx,delay in [('base',15,10,0),('cost2',30,20,0),('delay1',15,10,1)]:
   paths=[];total_orders=0
   for name in protocol['models']:
    claims=CampaignClaims(assets,recipients) if group=='hk7' else None
    _,p,o,_=run(assets,*protocol['period'],policy='score_change',signals=signals[name],cadence='daily',security_claims=claims,cost=cost,fx_cost=fx,delay=delay,initial_capital=500000,participation=.005)
    check=reconcile_claims(assets,p,o,cost,fx,recipients,initial_capital=500000) if claims else reconcile_cash(assets,p,o,cost,fx,initial_capital=500000);checks.append(check);case=f'{group}-{name}-{scenario}';p.to_parquet(OUT/f'{case}-path.parquet');(OUT/f'{case}-orders.json').write_text(json.dumps(o));paths.append(p);total_orders+=len(o)
   a,b=paths;assert a.index.equals(b.index);combo=pd.DataFrame(index=a.index);combo['nav']=(a.nav+b.nav)/2;combo['cash']=a.cash+b.cash;combo['fees']=a.fees+b.fees;combo['return_daily']=combo.nav/ combo.nav.shift(fill_value=1)-1;combo['drawdown']=combo.nav/combo.nav.cummax().clip(lower=1)-1
   for col in a.filter(like='w_'):combo[col]=(a[col]*a.nav+b[col]*b.nav)/(a.nav+b.nav)
   assert abs(combo.nav.iloc[-1]*1e6-(a.nav.iloc[-1]+b.nav.iloc[-1])*500000)<1e-6
   combo.to_parquet(OUT/f'{group}-{scenario}-path.parquet');results.append(dict(group=group,scenario=scenario,total_return=float(combo.nav.iloc[-1]-1),max_drawdown=float(combo.drawdown.min()),fees=float(combo.fees.sum()),orders=total_orders,year2026=period_metrics(combo,'2026-01-01','2026-10-16')));print(results[-1],flush=True)
 (OUT/'results.json').write_text(json.dumps(results,indent=2));(OUT/'validation.json').write_text(json.dumps(dict(exact_existing_controls=controls,subaccount_ledgers=len(checks),max_ledger_error=max(max(x.values()) for x in checks),aggregate_wealth_checks=len(results)),indent=2))
if __name__=='__main__':main()
