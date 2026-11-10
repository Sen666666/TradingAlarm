"""Account-level seeded priority falsification; seeds never select live rules."""
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
OUT=Path('results/trend-slot-priority-control')
def priority(seed,symbol,date):
 return int.from_bytes(hashlib.sha256(f'{seed}|{symbol}|{date.date()}'.encode()).digest()[:8],'big')/2**64

def main():
 OUT.mkdir(parents=True,exist_ok=True)
 protocol=dict(model='symmetric_pairwise_volume',seeds=list(range(17300,17320)),slots=3,entry_fraction=.3,cost=15,fx_cost=10,delay=0,period=['2022-01-01','2026-10-16'],randomization='Hash seed,symbol,date into reproducible priority; replace only candidateranking, keep originalsignals,retainedholdings,pendingorders,feesandclaims. No futuredata inpriority.',interpretation='20seeddistribution isconditionalorder sensitivity,not independentmarkets orsignificance test. Do not choosebestseed. BothETF17andHK7 retained.')
 p=OUT/'protocol.json'
 if p.exists():assert json.loads(p.read_text())==protocol
 p.write_text(json.dumps(protocol,indent=2));etf,_=load_extended();hk,_=load_assets();hk={s:dict(a,lot=400 if s=='HK00005' else 100) for s,a in hk.items()};results=[];controls=0
 for group,assets in [('etf17',etf),('hk7',hk)]:
  signals=build_signals(assets,protocol['model']);strength={}
  for s,a in assets.items():
   valid=a['raw'].index[a['raw'].volume.gt(0)].intersection(a['signal'].index);v=split_consistent_volume(a['raw'].volume,a.get('splits',[])).reindex(valid);strength[s]=pairwise_frame(a['signal'].close.reindex(valid),v).strength
  for seed in [None]+protocol['seeds']:
   chosen=strength if seed is None else {s:pd.Series([priority(seed,s,d) for d in series.index],index=series.index).where(series.notna()) for s,series in strength.items()}
   recipients={s:hk[s] for s in ['HK09618','HK03690']};claims=CampaignClaims(assets,recipients) if group=='hk7' else None
   m,path,orders,_=run(assets,*protocol['period'],policy='score_change',signals=signals,cadence='daily',selection=TrendSlots(chosen,slots=3),entry_fraction=.3,security_claims=claims)
   if seed is None:
    ref=Path('results/trend-slot-workbench')/f'{group}-symmetric_pairwise_volume-rank_slots-base';pd.testing.assert_frame_equal(path,pd.read_parquet(str(ref)+'-path.parquet'),check_exact=True);assert orders==json.loads(Path(str(ref)+'-orders.json').read_text());controls+=1
   check=reconcile_claims(assets,path,orders,15,10,recipients) if claims else reconcile_cash(assets,path,orders,15,10)
   case=f'{group}-seed{seed}';path.to_parquet(OUT/f'{case}-path.parquet');(OUT/f'{case}-orders.json').write_text(json.dumps(orders));results.append(dict(group=group,seed=seed,**m,return2026=period_metrics(path,'2026-01-01','2026-10-16')['return_fraction'],ledger=check));print(group,seed,m['total_return'],flush=True)
 f=pd.DataFrame(results);summary=[]
 for group,g in f.groupby('group'):
  a=g.loc[g.seed.isna()].iloc[0];r=g.loc[g.seed.notna()];summary.append(dict(group=group,ranked_return=float(a.total_return),random_median=float(r.total_return.median()),random_min=float(r.total_return.min()),random_max=float(r.total_return.max()),fraction_random_beats_rank=float(r.total_return.gt(a.total_return).mean()),ranked_mdd=float(a.max_drawdown),random_median_mdd=float(r.max_drawdown.median()),ranked2026=float(a.return2026),random_median2026=float(r.return2026.median()),random_positive_fraction=float(r.total_return.gt(0).mean())))
 (OUT/'results.json').write_text(json.dumps(results,indent=2));(OUT/'summary.json').write_text(json.dumps(summary,indent=2));(OUT/'validation.json').write_text(json.dumps(dict(exact_controls=controls,account_ledgers=len(results),max_ledger_error=max(max(r['ledger'].values()) for r in results)),indent=2));print(json.dumps(summary,indent=2))
if __name__=='__main__':main()
