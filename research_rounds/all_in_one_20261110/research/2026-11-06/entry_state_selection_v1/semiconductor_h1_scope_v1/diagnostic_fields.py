from pathlib import Path
import sys,json,importlib.util,hashlib
import pandas as pd,numpy as np
O=Path(__file__).resolve().parent;W=Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds');M=Path('/Users/bytedance/Documents/ChatGPT/money');P=Path(json.load(open(M/'TradingAlarm/runtime/market/current.json'))['path'])
spec=importlib.util.spec_from_file_location('dual_existing',O.parent/'dual_frontier_cp_full_v1/replay_signals.py');D=importlib.util.module_from_spec(spec);sys.modules[spec.name]=D;spec.loader.exec_module(D)
sm={x['symbol']:x for x in json.load(open(W/'universe-cp1-inputs-20261031/STOCK_MANIFEST.json'))};c=pd.read_csv(O/'COVERAGE.csv');parts=[];firstlast=[]
meta=json.load(open(M/'research_rounds/rs-h1-execution-20261025/inputs-v2/market-rules.json'))['security_metadata']
for sid in c.loc[c.H1_rows.gt(0),'sid']:
 q=pd.read_parquet(sm[sid]['refs']['CP1_input']).loc[:'2026-06-30'];pr=pd.read_parquet(P/'signals'/(sid+'.parquet')).reindex(q.index);old=pd.read_parquet(sm[sid]['refs']['CP1']).reindex(q.index);new=D.calc(q,pr,True);out=q.join(old.add_prefix('old_')).join(new.add_prefix('dual_'));out['sid']=sid;out['day']=out.index.strftime('%Y-%m-%d');out['name']=meta[sid]['name'];parts.append(out.loc['2025-12-01':].reset_index(drop=True))
 row=dict(sid=sid,name=meta[sid]['name'],last_observation_day=str(q.index[-1].date()),exact_H1_end=str(q.index[-1].date())=='2026-06-30')
 for k,z in [('old',old),('dual',new)]:
  ev=z.loc['2026-01-01':].query('receipt');row[k+'_first_H1']=str(ev.index[0].date()) if len(ev) else None;row[k+'_last_H1']=str(ev.index[-1].date()) if len(ev) else None;row[k+'_count_H1']=len(ev)
  for field in ['ready','phase','anchor','scale','credit']:
   v=z.iloc[-1][field];row[k+'_last_observation_used_'+field]=v
  row[k+'_last_observation_receipt']=bool(z.receipt.iloc[-1])
  if k=='old':
   for field in ['anchor','scale','credit','phase']:row[k+'_post_close_'+field]=z.iloc[-1]['next_'+field]
  else:
   consumed=bool(z.receipt.iloc[-1]);row[k+'_post_close_anchor']=z.next_anchor.iloc[-1];row[k+'_post_close_scale']=old.z.iloc[-1] if consumed else z.scale.iloc[-1];row[k+'_post_close_credit']=0. if consumed else z.credit.iloc[-1];row[k+'_post_close_phase']=2 if consumed else int(z.phase.iloc[-1])
 firstlast.append(row)
pd.concat(parts,ignore_index=True).to_parquet(O/'FULL_CP_DIAGNOSTICS.parquet',index=False);pd.DataFrame(firstlast).to_csv(O/'FIRST_LAST_AND_FINAL_CP_STATE.csv',index=False)
# Human display name repair only. Preserve original research snapshots unchanged.
s=pd.read_csv(O/'ALL_STOCK_TIMING_WITH_RETROSPECTIVE_TIERS.csv');s['name']=s.sid.map(lambda x:meta[x]['name']);s.to_csv(O/'ALL_120_NAMED_SIGNAL_TIMING.csv',index=False)
strict=s[s.exact_base&s.exact_end];rows=[]
for tier,g in strict.groupby('retrospective_price_tier'):
 rows.append(dict(retrospective_price_tier=tier,n=len(g),I_active_first_H1=int(g.I_active_first_H1.sum()),first_CP_by_Jan15=int(g.first_old_CP.le('2026-01-15').sum()),median_already_return=float(g.return_already_old_CP.median()),median_PVR_at_CP=float(g.PVR_at_old_CP.median())))
pd.DataFrame(rows).to_csv(O/'STRICT_112_RETROSPECTIVE_TIMING.csv',index=False)
print('Saved complete dual fields and first/last/final states for',len(firstlast),'stocks')
