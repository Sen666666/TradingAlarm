"""Validate original closeout then evaluate fixed dates without cash accounts."""
from pathlib import Path
from current_pool_bridge import load_bundle,load_prepared_states
from history_runner import FrozenMarket,iso
from sector_stock_admission import Clock
from current_fixed_pool import decide_current_pool
from build_inputs import HERE,read,write,ref,now
from run_first10 import validate

def main():
 package=read(HERE/'inputs-v2/package.json')
 validate(data_closeout=Path(package['data_closeout']['path']),economic_protocol_frozen=Path(package['economic_protocol_frozen']['path']),scope=Path(package['scope']['path']))
 b=load_bundle(HERE/'inputs-v2/input-manifest.json');load_prepared_states(b,HERE/'prepared-v2');assert b.signal_ready
 m=FrozenMarket(b,read(HERE/'inputs-v2/market-rules.json'),[],read(HERE/'inputs-v2/economic-protocol.json'))
 rows=[]
 for day in ['2015-01-05','2017-12-29','2020-12-31','2023-12-29','2026-10-22']:
  at=iso(day+'T15:10:00+08:00');clock=Clock(at,m.lag('A',at,1),at.date())
  inputs=b.at_decision(clock,market_buyable=m.market_buyable(at))
  for v in ['T0','T1','S0','S1']:
   d=decide_current_pool(evidence=inputs.evidence,lines=inputs.lines,historical=inputs.historical,sectors=inputs.sectors,clock=clock,variant=v,bootstrap=True).decision
   assert not d.ranking_fallbacks
   rows.append(dict(date=day,variant=v,selected=d.selected,eligible=sum(x.q is True for x in d.eligibility),unknown=sum(x.q is None for x in d.eligibility)))
 write(HERE/'audit/preflight.json',dict(passed=True,recorded_at=now(),fixed_date_decisions=rows,accounts=0,source_closeout_validated=True))
 print({'passed':True,'decisions':len(rows)},flush=True)
if __name__=='__main__':main()
