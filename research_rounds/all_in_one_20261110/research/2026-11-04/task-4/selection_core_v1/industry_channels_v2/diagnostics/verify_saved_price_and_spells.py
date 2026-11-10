"""Independent fixed-date source arithmetic and partition audit, no full rerun."""
from pathlib import Path
import json,math
import numpy as np
import pandas as pd
O=Path(__file__).resolve().parent
d=pd.read_parquet(O/'DAILY_STATES_WITH_PRICE_LABELS.parquet');s=pd.read_parquet(O/'SPELLS_AND_FIRST_DAY_PRICE_LABELS.parquet')
bind=json.loads((O/'PRICE_SOURCE_BINDINGS_AND_COORDINATE_CHECKS.json').read_text());sources={r['sector']:r['prepared_source'] for r in bind['source']}
mp=Path('/Users/bytedance/repos/TradingAlarm/TradingAlarm/TradingAlarm/research/data/ths-index-history-20261018/canonical/USHI1B0300.csv');m=pd.read_csv(mp,parse_dates=['date']).set_index('date')
cases=[('URFI881121','2022-01-24'),('URFI881121','2024-09-24'),('URFI881121','2026-01-15'),('URFI881153','2022-01-24')]
result=[]
for sec,date in cases:
 r=d[(d.sector_id_static==sec)&(d.date==date)].iloc[0];f=pd.read_parquet(sources[sec]).loc[:'2026-10-22'];t=pd.Timestamp(date);pos=m.index.get_loc(t)
 for h in [5,20]:
  ds=m.index[pos+1:pos+h+1];assert len(ds)==h
  qa=[math.log(float(f.at[q,'close'])/float(f.at[t,'close'])) for q in ds]
  qr=[a-math.log(float(m.at[q,'close'])/float(m.at[t,'close'])) for a,q in zip(qa,ds)]
  independently={}
  for tag,vec in [('abs',qa),('rel',qr)]:
   independently.update({f'final{h}_{tag}_log':vec[-1],f'mfe{h}_{tag}_log':max([0.]+vec),f'mae{h}_{tag}_log':min([0.]+vec)})
  err={k:float(r[k])-v for k,v in independently.items()};assert max(abs(v) for v in err.values())<1e-12
  result.append({'sector':sec,'date':date,'horizon':h,'label_end':str(ds[-1].date()),'independent_labels':independently,'stored_minus_independent':err,'future_dates':[str(q.date()) for q in ds]})
part=[]
for (win,ch),g in s.groupby(['study_window','channel']):
 true_days=int(d.loc[d.study_window.eq(win),ch].eq(True).sum());covered=int(g.active_common_sessions.sum());assert true_days==covered
 known_stops=0
 for _,z in d[d.study_window.eq(win)].groupby('sector_id_static'):
  z=z.sort_values('date');known_stops+=int((z[ch].shift().eq(True)&z[ch].eq(False)).sum())
 assert known_stops==int((~g.right_censored).sum())
 part.append({'study_window':win,'channel':ch,'true_days':true_days,'spell_covered_days':covered,'within_window_known_exits':known_stops})
assert d.UNION.equals(d.CONT|d.START)
for h in [5,20]:
 ends=m.index.get_indexer(pd.to_datetime(d[f'label_end{h}']));starts=m.index.get_indexer(pd.to_datetime(d.date));assert np.all(ends-starts==h)
 for tag in ['abs','rel']:
  v=d[d[f'label_valid{h}']];assert v[f'mfe{h}_{tag}_log'].ge(0).all() and v[f'mae{h}_{tag}_log'].le(0).all()
  assert (v[f'final{h}_{tag}_log']<=v[f'mfe{h}_{tag}_log']+1e-15).all() and (v[f'final{h}_{tag}_log']>=v[f'mae{h}_{tag}_log']-1e-15).all()
summary={'fixed_case_horizon_checks':len(result),'maximum_abs_label_difference':max(abs(v) for r in result for v in r['stored_minus_independent'].values()),
 'all_spell_partitions_exact':True,'all_union_OR_exact':True,'all_future5_20_common_session_alignment_exact':True,'all_mfe_mae_bounds_exact':True,
 'partition_checks':part,'fixed_cases':result,'new_full_analysis_or_threshold_variant':0}
(O/'INDEPENDENT_ARITHMETIC_AND_PARTITION_CHECKS.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n');print(json.dumps({k:v for k,v in summary.items() if k not in ['partition_checks','fixed_cases']},indent=2))
