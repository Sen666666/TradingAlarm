"""Shared-capital adjusted-price research. Fractional units, no tradability certification."""
import json,hashlib
from pathlib import Path
import numpy as np
import pandas as pd
from monthly_ah_engine import run
from trend_slot_selection import TrendSlots
from sector_factors import expanded_assets
from strategy_signals import build_signals
OUT=Path('results/broad-shared-slots')

def main(first_cross=False,short_exit=False,short_half=False,restore=False,graded=False,linear=False):
 if linear:first_cross=True
 if graded:first_cross=True
 if restore:short_half=True
 if short_half:short_exit=True
 if short_exit:first_cross=True
 OUT=Path('results/broad-shared-linear' if linear else 'results/broad-shared-graded' if graded else 'results/broad-shared-short-restore' if restore else 'results/broad-shared-short-half' if short_half else 'results/broad-shared-short-exit' if short_exit else 'results/broad-shared-first-cross' if first_cross else 'results/broad-shared-slots')
 OUT.mkdir(parents=True,exist_ok=True)
 protocol=dict(slots=9,entry_fraction=.1,group_slots=3,seed=20261018,start='2024-01-02',end='2026-10-16',cases=['rank','random','group_gate','group_gate_cap'],scenarios=['base','cost2','delay1'],limits=['Selected surviving 485 A shares; all history development.','Adjusted-price fractional units rounded to 1e-6; 5 CNY minimum transaction fee retained; no actual corporate-action cash/tax/lot accounting.','Artificial ample execution volume on eligible bars; no liquidity or price-limit simulation.','Prior-close cached stock exposure; flat before cache begins. Gate uses prior-close sector ETF exposure, not future realized episodes.','Price-correlation association groups, not industry membership. Changing group can change concentration without a trade; group cap applies at admission only.','One seeded random priority is a mechanical comparator, not a statistical significance test.'])
 if first_cross:
  protocol.update(cases=['control_rank','rank','group_gate_cap'],admission='New admission only on an observed 0-to-1 exposure transition. Already admitted pending orders remain eligible until original cancellation conditions. No backfill when missed because gate/slots rejected. Flat before cache starts.',control='control_rank runs base only and must exactly match previous rank-base path and orders')
 if short_exit:
  protocol.update(cases=['control_group_gate_cap','group_gate_cap'],control='control_group_gate_cap base must exactly reproduce first-cross capped group baseline',short_exit='Existing fast5 <= 0 terminates long episode; cannot reenter before original zero exposure resets. Missing fast5 preserves original state. No changes to ETF gate or score ranking.')
 if short_half:
  protocol.pop('short_exit');protocol['short_half']='Preserve original trigger bar1; first later fast5<=0 changes state to0.5 until original exit. Target is half initial NAV allocation budget, capped at current quantity (no additions); not exact half of current shares. Held ticker retains slot. No restoration.'
 if restore:
  protocol['cases']=['control_group_gate_cap','control_half','group_gate_cap'];protocol['restore']='Same short_half state but fast5>0 restores1, missing preserves prior state. Targets retain engine no-add on reduction and no-trim on promotion guards. Repeated changes incur all costs. control_half matches latched half baseline exactly.'
 if graded:
  protocol.update(cases=['control_group_gate_cap','group_gate_cap'],control='Exact existing first-cross group-capped base account',graded='Existing graded_exposure unchanged. Full-history score/state then same2024 cache boundary as baseline; initial positive state can be half. First admission0-to-positive only, holdings may promote half-to-full without a new slot. Proxy gate remains original binary pairwise-volume.')
 if linear:
  protocol.update(cases=['control_group_gate_cap','group_gate_cap'],control='Exact original first-cross group-capped account',linear='Only stock score estimator changes to existing linear_geometry_price_volume_split_units. Use new score for stock ranking and original upper-entry/zero-exit rule. Full-history then same2024 cache convention. Proxy gates and mappings unchanged.')
 p=OUT/'protocol.json'
 if p.exists():assert json.loads(p.read_text())==protocol
 p.write_text(json.dumps(protocol,ensure_ascii=False,indent=2))
 root=Path('data/ths-refresh-20261018');manifest=json.loads((root/'validated-input-balanced-second500.json').read_text())
 cache_path=Path('results/broad-exit-disagreement/all-observed-signals.parquet');cache=pd.read_parquet(cache_path);assets={};signals={};strength={};hashes={};entry_events=set();short_signals={};half_signals={};graded_events=set();linear_events=set();linear_strength={}
 linear_cache=pd.read_parquet(OUT/'linear-signals.parquet') if linear else None
 graded_cache=pd.read_parquet(OUT/'graded-signals.parquet') if graded else None
 for rec in manifest['records']:
  s=rec['symbol'];p=root/f"{rec['ths_symbol']}-signal.parquet";h=hashlib.sha256(p.read_bytes()).hexdigest();assert h==rec['signal_sha256'];hashes[str(p)]=h
  f=pd.read_parquet(p);raw=f[['signal_open','signal_high','signal_low','signal_close']].rename(columns=lambda x:x.removeprefix('signal_')).copy()
  raw['volume']=np.where(f.bar_allows_trade & f.high.gt(f.low),1e18,0.)
  assets[s]=dict(raw=raw,signal=raw.copy(),currency='CNY',lot=1e-6,splits=[],dividends=[])
  z=cache[cache.symbol.eq(s)].set_index('date');signals[s]=z.zero.reindex(f.index,method='ffill').fillna(0);strength[s]=z.strength
  if short_exit:
   from short_reversal_state import short_reversal_state
   from short_half_state import short_half_state
   state_fn=short_half_state if short_half else short_reversal_state
   short_signals[s]=(short_half_state(z.zero,z.fast5,restore=True) if restore else state_fn(z.zero,z.fast5)).reindex(f.index,method='ffill').fillna(0)
   if restore:half_signals[s]=short_half_state(z.zero,z.fast5).reindex(f.index,method='ffill').fillna(0)
  if graded:
   gz=graded_cache[graded_cache.symbol.eq(s)].set_index('date');short_signals[s]=gz.graded.reindex(f.index,method='ffill').fillna(0)
   graded_events.update((d,s) for d in gz.index[gz.graded.gt(0)&gz.graded.shift(fill_value=0).eq(0)])
  if linear:
   lz=linear_cache[linear_cache.symbol.eq(s)].set_index('date');short_signals[s]=lz.exposure.reindex(f.index,method='ffill').fillna(0);linear_strength[s]=lz.strength
   linear_events.update((d,s) for d in lz.index[lz.exposure.gt(0)&lz.exposure.shift(fill_value=0).eq(0)])
  entry_events.update((d,s) for d in z.index[z.zero.gt(0)&z.zero.shift(fill_value=0).eq(0)])
 calendar=pd.DatetimeIndex(sorted(set().union(*(a['raw'].index for a in assets.values()))));fx=pd.Series(1.,index=calendar)
 mapping_path=Path('results/sector-stock-daily-mapping/assignments.parquet');mapping=pd.read_parquet(mapping_path).dropna(subset=['proxy']);groups={(r.date,r.symbol):r.proxy for r in mapping.itertuples()}
 proxies={s:a for s,a in expanded_assets().items() if a['kind']=='equity' and a['currency']=='CNY' and a['sector']!='broad_cn'}
 proxy_signals=build_signals(proxies,'pairwise_volume');gates={(d,s):bool(v) for s,f in proxy_signals.items() for d,v in f.items()}
 rng=np.random.default_rng(protocol['seed']);random_strength={s:pd.Series(rng.random(),index=strength[s].index) for s in sorted(strength)}
 reports=[]
 for case in protocol['cases']:
  for sc,cost,delay in [('base',15,0),('cost2',30,0),('delay1',15,1)]:
   if case.startswith('control_') and sc!='base':continue
   policy_case='group_gate_cap' if case=='control_half' else case.removeprefix('control_')
   admission_events=linear_events if linear and not case.startswith('control_') else graded_events if graded and not case.startswith('control_') else entry_events
   selector=TrendSlots(linear_strength if linear and not case.startswith('control_') else random_strength if case=='random' else strength,groups=groups if policy_case.startswith('group') else None,gates=gates if policy_case.startswith('group') else None,slots=9,group_slots=3 if policy_case=='group_gate_cap' else None,entry_events=admission_events if first_cross and case!='control_rank' else None)
   m,path,orders,decisions=run(assets,protocol['start'],protocol['end'],policy='score_change',signals=half_signals if case=='control_half' else short_signals if (short_exit or graded or linear) and not case.startswith('control_') else signals,cadence='daily',selection=selector,entry_fraction=.1,fx_override=fx,cost=cost,delay=delay)
   if case=='control_rank':
    ref=Path('results/broad-shared-slots');pd.testing.assert_frame_equal(path,pd.read_parquet(ref/'rank-base-path.parquet'),check_exact=True);assert orders==json.loads((ref/'rank-base-orders.json').read_text())
   if case=='control_group_gate_cap':
    ref=Path('results/broad-shared-first-cross');pd.testing.assert_frame_equal(path,pd.read_parquet(ref/'group_gate_cap-base-path.parquet'),check_exact=True);assert orders==json.loads((ref/'group_gate_cap-base-orders.json').read_text())
   if case=='control_half':
    ref=Path('results/broad-shared-short-half');pd.testing.assert_frame_equal(path,pd.read_parquet(ref/'group_gate_cap-base-path.parquet'),check_exact=True);assert orders==json.loads((ref/'group_gate_cap-base-orders.json').read_text())
   name=case+'-'+sc;path.to_parquet(OUT/(name+'-path.parquet'));(OUT/(name+'-orders.json')).write_text(json.dumps(orders))
   # Independent signed-order inventory/cash reconstruction against daily NAV.
   units=pd.DataFrame(0.,index=path.index,columns=sorted(assets));cash_change=pd.Series(0.,index=path.index)
   for o in orders:
    d=pd.Timestamp(o['date']);units.loc[d,o['symbol']]+=o['units'];cash_change.loc[d]-=o['units']*o['raw_open']+o['fee']
   units=units.cumsum();marks=pd.DataFrame({s:a['raw'].close.reindex(calendar).ffill().reindex(path.index) for s,a in assets.items()});cash=1e6+cash_change.cumsum();nav=cash+(units*marks).fillna(0).sum(axis=1)
   err=float((nav/1e6-path.nav).abs().max());assert err<1e-9
   assert (units.ge(-1e-8)).all().all();assert (units.gt(1e-8).sum(axis=1)<=9).all();assert cash.min()>=-1e-6
   m.update(case=case,scenario=sc,year2026=float(path.nav.iloc[-1]/path.nav.loc['2025-12-31']-1),ledger_error=err,max_positions=int(units.gt(1e-8).sum(axis=1).max()))
   reports.append(m);(OUT/'summary.json').write_text(json.dumps(reports,indent=2));print(name,json.dumps(m),flush=True)
 hashes.update({str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in [cache_path,mapping_path,Path(__file__),Path('monthly_ah_engine.py'),Path('trend_slot_selection.py')]})
 (OUT/'validation.json').write_text(json.dumps(dict(source_hashes=hashes,cases=len(reports),max_ledger_error=max(x['ledger_error'] for x in reports)),indent=2))
if __name__=='__main__':
 import argparse
 p=argparse.ArgumentParser();p.add_argument('--first-cross',action='store_true');p.add_argument('--short-exit',action='store_true');p.add_argument('--short-half',action='store_true');p.add_argument('--restore',action='store_true');p.add_argument('--graded',action='store_true');p.add_argument('--linear',action='store_true');a=p.parse_args();main(a.first_cross,a.short_exit,a.short_half,a.restore,a.graded,a.linear)
