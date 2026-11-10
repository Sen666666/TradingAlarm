"""Same-universe passive-account benchmark; do not select winners after observing returns."""
import json,hashlib
from pathlib import Path
import pandas as pd
from hk_extension import load_extended
from hk_in_kind_campaign import load_assets
from campaign_claims import CampaignClaims
from monthly_ah_engine import run
from strategy_signals import build_signals,period_metrics
from monthly_claim_ledger_audit import reconcile as reconcile_claims
from campaign_completion_ledger_audit import reconcile as reconcile_cash
OUT=Path('results/trend-pool-benchmark')
def main():
 OUT.mkdir(exist_ok=True,parents=True)
 protocol=dict(period=['2022-01-01','2026-10-16'],allocation='90%initialtarget divided equallyacrossallassets; constant1signal, daily score_change prevents resizing. Pendingordersmaintained. Dividendsstaycash,distributedsharesretained. No rebalance andno beststockselection.',groups=['etf17','hk7'],scenarios=['base','cost2','delay1'],reference='Samepool all-name symmetrictrend andthree-slot symmetrictrend fromtrend-slot-workbench; sameperiod/accountcosts',limits='Selectedsurvivingtinyuniverses; benchmarksnot representativebroadmarket. Exposures andturnoverdiffer; difference not causalalpha. Endpositionsmarktomarketnotliquidated. No predeclared80%marketcycle here.')
 p=OUT/'protocol.json'
 if p.exists():assert json.loads(p.read_text())==protocol
 p.write_text(json.dumps(protocol,indent=2));etf,_=load_extended();hk,_=load_assets();hk={s:dict(a,lot=400 if s=='HK00005' else 100) for s,a in hk.items()};rows=[];controls=0
 for group,assets in [('etf17',etf),('hk7',hk)]:
  recipients={s:hk[s] for s in ['HK09618','HK03690']}
  # Existing all-name trend verifies account bridge before introducing passive signals.
  signals=build_signals(assets,'symmetric_pairwise_volume');claims=CampaignClaims(assets,recipients) if group=='hk7' else None
  _,path,orders,_=run(assets,*protocol['period'],policy='score_change',signals=signals,cadence='daily',security_claims=claims)
  ref=Path('results/trend-slot-workbench')/f'{group}-symmetric_pairwise_volume-equal_capital-base';pd.testing.assert_frame_equal(path,pd.read_parquet(str(ref)+'-path.parquet'),check_exact=True);assert orders==json.loads(Path(str(ref)+'-orders.json').read_text());controls+=1
  signals={s:pd.Series(1.,index=a['signal'].index) for s,a in assets.items()}
  for scenario,cost,fx,delay in [('base',15,10,0),('cost2',30,20,0),('delay1',15,10,1)]:
   claims=CampaignClaims(assets,recipients) if group=='hk7' else None
   metrics,path,orders,_=run(assets,*protocol['period'],policy='score_change',signals=signals,cadence='daily',security_claims=claims,cost=cost,fx_cost=fx,delay=delay)
   assert all(o['units']>0 for o in orders)
   ledger=reconcile_claims(assets,path,orders,cost,fx,recipients) if claims else reconcile_cash(assets,path,orders,cost,fx)
   case=f'{group}-passive-{scenario}';path.to_parquet(OUT/f'{case}-path.parquet');(OUT/f'{case}-orders.json').write_text(json.dumps(orders));rows.append(dict(case=case,group=group,scenario=scenario,**metrics,year2026=period_metrics(path,'2026-01-01','2026-10-16'),annual_returns={str(y):float((1+g.return_daily).prod()-1) for y,g in path.groupby(path.index.year)},ledger=ledger));print(case,metrics,flush=True)
 (OUT/'results.json').write_text(json.dumps(rows,indent=2));(OUT/'validation.json').write_text(json.dumps(dict(exact_controls=controls,passive_ledgers=len(rows),max_ledger_error=max(max(r['ledger'].values()) for r in rows),only_buy_orders=True,source_hashes={f:hashlib.sha256(Path(f).read_bytes()).hexdigest() for f in ['trend_pool_benchmark.py','monthly_ah_engine.py']}),indent=2))
if __name__=='__main__':main()
