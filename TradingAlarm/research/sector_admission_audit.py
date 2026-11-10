"""Replay frozen shared account; audit each first-cross admission without changing selection."""
import json,hashlib,math
from pathlib import Path
import numpy as np
import pandas as pd
from monthly_ah_engine import run
from trend_slot_selection import TrendSlots
from sector_factors import expanded_assets
from strategy_signals import build_signals
OUT=Path('results/sector-admission-audit')
class AuditedSlots(TrendSlots):
 def __init__(self,*args,**kwargs):super().__init__(*args,**kwargs);self.audit=[]
 def __call__(self,date,scores,qty,pending):
  selected=super().__call__(date,scores,qty,pending)
  for d,s in self.events_by_date.get(date,[]):
   group=self.groups.get((date,s));past=self.strength[s].loc[:date]
   if qty[s]>0:reason='already_held'
   elif s in pending and pending[s]['target']>0:reason='pending_entry'
   elif scores[s]<=0:reason='inactive_on_decision'
   elif group is None:reason='missing_group'
   elif not self.gates.get((date,group),False):reason='group_gate_closed'
   elif not len(past) or not math.isfinite(float(past.iloc[-1])):reason='missing_strength'
   elif selected[s]>0:reason='selected'
   else:reason='slot_constraints_or_ranking'
   self.audit.append(dict(date=str(date.date()),symbol=s,group=group,reason=reason))
  return selected

def load_context():
 root=Path('data/ths-refresh-20261018');manifest=json.loads((root/'validated-input-balanced-second500.json').read_text());cache_path=Path('results/broad-exit-disagreement/all-observed-signals.parquet');cache=pd.read_parquet(cache_path);assets={};signals={};strength={};events=set()
 for rec in manifest['records']:
  s=rec['symbol'];p=root/f"{rec['ths_symbol']}-signal.parquet";assert hashlib.sha256(p.read_bytes()).hexdigest()==rec['signal_sha256'];f=pd.read_parquet(p)
  raw=f[['signal_open','signal_high','signal_low','signal_close']].rename(columns=lambda x:x.removeprefix('signal_')).copy();raw['volume']=np.where(f.bar_allows_trade&f.high.gt(f.low),1e18,0.)
  assets[s]=dict(raw=raw,signal=raw.copy(),currency='CNY',lot=1e-6,splits=[],dividends=[])
  z=cache[cache.symbol.eq(s)].set_index('date');signals[s]=z.zero.reindex(f.index,method='ffill').fillna(0);strength[s]=z.strength;events.update((d,s) for d in z.index[z.zero.gt(0)&z.zero.shift(fill_value=0).eq(0)])
 calendar=pd.DatetimeIndex(sorted(set().union(*(a['raw'].index for a in assets.values()))));mapping=pd.read_parquet('results/sector-stock-daily-mapping/assignments.parquet').dropna(subset=['proxy']);groups={(r.date,r.symbol):r.proxy for r in mapping.itertuples()}
 proxies={s:a for s,a in expanded_assets().items() if a['kind']=='equity' and a['currency']=='CNY' and a['sector']!='broad_cn'};ps=build_signals(proxies,'pairwise_volume');gates={(d,s):bool(v) for s,f in ps.items() for d,v in f.items()}
 return assets,signals,strength,events,calendar,groups,gates,manifest

def main():
 OUT.mkdir(exist_ok=True)
 assets,signals,strength,events,calendar,groups,gates,manifest=load_context()
 selector=AuditedSlots(strength,groups=groups,gates=gates,slots=9,group_slots=3,entry_events=events);selector.events_by_date={}
 for event in events:selector.events_by_date.setdefault(event[0],[]).append(event)
 m,path,orders,_=run(assets,'2024-01-02','2026-10-16',policy='score_change',signals=signals,cadence='daily',selection=selector,entry_fraction=.1,fx_override=pd.Series(1.,index=calendar),cost=15,delay=0)
 ref=Path('results/broad-shared-first-cross');pd.testing.assert_frame_equal(path,pd.read_parquet(ref/'group_gate_cap-base-path.parquet'),check_exact=True);assert orders==json.loads((ref/'group_gate_cap-base-orders.json').read_text())
 f=pd.DataFrame(selector.audit);assert not f.duplicated(['date','symbol']).any();f['year']=pd.to_datetime(f.date).dt.year;f.to_csv(OUT/'events.csv',index=False)
 summary=f.groupby(['year','reason']).size().rename('count').reset_index();summary.to_csv(OUT/'summary.csv',index=False)
 buys={(o['signal_date'],o['symbol']) for o in orders if o['units']>0} if orders and 'signal_date' in orders[0] else None
 review={'status':'frozen_account_exact_replay','input_hash_checks':len(manifest['records']),'events':len(f),'summary':summary.to_dict('records'),'exact_path':True,'exact_orders':True,'limits':['Association groups from price correlations, not historical industry constituents.','Selected admission does not imply immediate fill; no unverified fill reasons assigned.','Blocked slots/ranking combined, no invented attribution between total and per-group constraints.','Synthetic adjusted fractional units and artificial ample liquidity; research only.','Cache-start positive states count as initial entry opportunities; not all are fresh historical crossings.'],'source_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
 (OUT/'review.json').write_text(json.dumps(review,ensure_ascii=False,indent=2)+'\n');print(summary.to_string(index=False));print('events',len(f),'orders',len(orders))
if __name__=='__main__':main()
