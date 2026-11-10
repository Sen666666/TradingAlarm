"""Fixed three-slot prior-close stock/ETF selection with raw-share cash accounting."""
import json,hashlib
from pathlib import Path
import pandas as pd
from hk_extension import load_extended
from hk_in_kind_campaign import load_assets
from campaign_claims import CampaignClaims
from strategy_signals import build_signals,period_metrics
from pairwise_trend_strength import pairwise_frame
from volume_units import split_consistent_volume
from monthly_ah_engine import run
from trend_slot_selection import TrendSlots
from monthly_claim_ledger_audit import reconcile as reconcile_claims
from campaign_completion_ledger_audit import reconcile as reconcile_cash
OUT=Path('results/trend-slot-workbench')
def main():
 OUT.mkdir(exist_ok=True,parents=True)
 protocol=dict(strategies=['pairwise_volume','symmetric_pairwise_volume'],modes=['equal_capital','rank_slots'],slots=3,entry_fraction=.3,scenarios=['base','cost2','delay1'],period=['2022-01-01','2026-10-16'],hypothesis='Fixed3slots30%entry targets as concentration stress,not riskoptimized. Priorclose strength ranks candidates; held andpending reserve slots. Do not resize ongoingpositions justbecause rank changes. Original scores/exits fixed. No sectorfilteryet.',limits='Existing selected17ETF/7HKstock pools; reuseddevelopment history.30%entrytargetnot hardmarkedcap; no20%MDDguarantee. ETFpoolincludes gold/bonds,notpurestockstrategy. Delayedordersmaycancel,not identicaltrades merely shifted.')
 p=OUT/'protocol.json'
 if p.exists():assert json.loads(p.read_text())==protocol
 p.write_text(json.dumps(protocol,indent=2));etf,_=load_extended();hk,_=load_assets();hk={s:dict(a,lot=400 if s=='HK00005' else 100) for s,a in hk.items()};results=[];controls=0
 for group,assets in [('etf17',etf),('hk7',hk)]:
  strength={}
  for s,a in assets.items():
   valid=a['raw'].index[a['raw'].volume.gt(0)].intersection(a['signal'].index);v=split_consistent_volume(a['raw'].volume,a.get('splits',[])).reindex(valid);strength[s]=pairwise_frame(a['signal'].close.reindex(valid),v).strength
  for model in protocol['strategies']:
   signals=build_signals(assets,model)
   for mode in protocol['modes']:
    for sc,cost,fx,delay in [('base',15,10,0),('cost2',30,20,0),('delay1',15,10,1)]:
     recipients={s:hk[s] for s in ['HK09618','HK03690']};claims=CampaignClaims(assets,recipients) if group=='hk7' else None
     selector=TrendSlots(strength,slots=3) if mode=='rank_slots' else None
     metrics,path,orders,decisions=run(assets,*protocol['period'],policy='score_change',cost=cost,fx_cost=fx,delay=delay,security_claims=claims,signals=signals,cadence='daily',selection=selector,entry_fraction=.3 if selector else None)
     if mode=='equal_capital':
      ref=Path('results/strength-symmetric-exit')/f'{group}-{model}-daily-{sc}';pd.testing.assert_frame_equal(path,pd.read_parquet(str(ref)+'-path.parquet'),check_exact=True);assert orders==json.loads(Path(str(ref)+'-orders.json').read_text());controls+=1
     ledger=reconcile_claims(assets,path,orders,cost,fx,recipients) if claims else reconcile_cash(assets,path,orders,cost,fx)
     case=f'{group}-{model}-{mode}-{sc}';path.to_parquet(OUT/f'{case}-path.parquet');(OUT/f'{case}-orders.json').write_text(json.dumps(orders));(OUT/f'{case}-decisions.json').write_text(json.dumps(decisions))
     # Claims may retain distributed securities after parent slots close.
     max_parent_positions=int(path.filter(like='w_').gt(1e-12).sum(axis=1).max())
     if selector:assert max_parent_positions<=3
     results.append(dict(case=case,group=group,strategy=model,mode=mode,scenario=sc,**metrics,year2026=period_metrics(path,'2026-01-01','2026-10-16'),ledger=ledger,max_parent_positions=max_parent_positions));print(case,metrics['total_return'],metrics['max_drawdown'],flush=True)
 OUT.joinpath('results.json').write_text(json.dumps(results,indent=2));OUT.joinpath('validation.json').write_text(json.dumps(dict(exact_existing_controls=controls,new_ledgers=len(results),max_ledger_error=max(max(r['ledger'].values()) for r in results),source_hashes={f:hashlib.sha256(Path(f).read_bytes()).hexdigest() for f in ['monthly_ah_engine.py','trend_slot_selection.py','trend_slot_workbench.py']}),indent=2))
if __name__=='__main__':main()
