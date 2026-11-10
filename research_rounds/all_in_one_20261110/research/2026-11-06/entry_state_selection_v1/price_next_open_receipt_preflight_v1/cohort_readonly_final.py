from pathlib import Path
import json,hashlib
import pandas as pd,numpy as np
R=Path('/Users/bytedance/Documents/Codex/2026-11-06/entry_state_selection_v1')
M=Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/universe-cp1-inputs-20261031/STOCK_MANIFEST.json')
H=Path('/Users/bytedance/Documents/ChatGPT/money/TradingAlarm/runtime/market/update-20261030-153010-c551af/prepared/h1.npz')
A=R/'price_round_path_attribution_v1/PRICE_ROUND_PATH_ATTRIBUTION.csv'
P=R/'independent_channel_full1709_preflight_v1/overlap/RECEIPT_CONDITIONAL_OVERLAP.parquet'
m={x['symbol']:x for x in json.loads(M.read_text())};cal=pd.DatetimeIndex(np.load(H,allow_pickle=False)['dates'])
a=pd.read_csv(A,parse_dates=['signal_day','entry_day'],float_precision='round_trip')
rec=pd.read_parquet(P,columns=['sid','day','C','U','root_day','born','receipt','active','valid','root_unknown','phase'])
rec=rec.rename(columns={'day':'signal_day'})
assert not rec.duplicated(['sid','signal_day']).any()
a=a.merge(rec,on=['sid','signal_day'],how='left',validate='one_to_one');assert len(a)==2862 and a.receipt.eq(True).all()
hashes={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in [M,H,A,P]};rows=[]
cols=['open','high','close','raw_open','raw_close','adjustment_factor','source_kind','source_path','segment_id','observed_bar','is_observed_bar','price_eligible','source_invalid','synthetic_event_bar']
for sid,g in a.groupby('sid'):
 sp=Path(next(p for p in m[sid]['source_sha256'] if p.endswith('/signal.parquet')))
 h=hashlib.sha256(sp.read_bytes()).hexdigest();assert h==m[sid]['source_sha256'][str(sp)];hashes[str(sp)]=h
 p=pd.read_parquet(sp,columns=cols).reindex(cal)
 for x in g.to_dict('records'):
  t=x['signal_day'];d=x['entry_day'];k=cal.get_loc(t);assert d==cal[k+1]
  s=p.loc[t];z=p.loc[d];rd=pd.Timestamp(x['root_day'])
  hist=p.iloc[k-20:k] if x['born'] else p.loc[rd:t].iloc[:-1]
  known=bool(len(hist) and np.isfinite(hist[['high','close']].to_numpy(float)).all() and np.isfinite(z.raw_open) and z.raw_open>0 and np.isfinite(z.adjustment_factor) and z.adjustment_factor>0)
  why=None
  if not known:why='COMPARISON_PRICE_UNKNOWN'
  elif not all(str(z[c])==str(s[c]) for c in ['source_kind','source_path','segment_id']):known=False;why='NEXT_OPEN_SOURCE_CHANGE'
  elif z.adjustment_factor!=s.adjustment_factor:known=False;why='NEXT_OPEN_FACTOR_BRIDGE_NOT_RECHECKED'
  assert np.isclose(z.raw_open,x['entry_open'],rtol=1e-12,atol=1e-10)
  J=float(x['U']) if x['born'] else float(hist.close.max())
  if known:
   assert bool(x['active']) and bool(x['valid']) and not bool(x['root_unknown'])
   assert all(hist[c].eq(True).all() for c in ['observed_bar','is_observed_bar','price_eligible'])
   assert all(hist[c].eq(False).all() for c in ['source_invalid','synthetic_event_bar'])
   assert all(hist[c].nunique()==1 and str(hist[c].iloc[-1])==str(s[c]) for c in ['source_kind','source_path','segment_id'])
   if x['born']:assert np.isclose(J,hist.high.max(),rtol=1e-12,atol=1e-8)
   assert s.close>J and np.isclose(s.close,x['C'],rtol=1e-12,atol=1e-8)
   assert np.isclose(s.close,s.raw_close*s.adjustment_factor,rtol=1e-12,atol=1e-8)
  on=float(z.raw_open*z.adjustment_factor) if known else None
  r=dict(round_id=x['round_id'],window=x['window'],sid=sid,name=x['name'],signal_day=str(t.date()),entry_day=str(d.date()),born=bool(x['born']),root_day=str(rd.date()),J_native=J,J_raw=J/float(s.adjustment_factor),signal_C=float(s.raw_close),next_open_raw=float(z.raw_open),next_open_native=on,known=known,unknown_reason=why,open_above_J=bool(on>J) if known else None,open_equal_J=bool(on==J) if known else None,edge_pct=(on/J-1)*100 if known else None,original_net=x['net_pnl'],original_W=x['net_pnl']>0,original_mfe=x['price_close_mfe'],original_mfe_lt5=x['price_close_mfe']<.05,PVR=x['PVR_score'])
  rows.append(r)
d=pd.DataFrame(rows);sums=[]
for win,g in d.groupby('window'):
 r=dict(window=win,N=len(g),known=int(g.known.sum()),UNKNOWN=int((~g.known).sum()),blocked=int(g.open_above_J.eq(False).sum()),equal=int(g.open_equal_J.eq(True).sum()),groups=[])
 for name,q in [('original_winners',g[g.original_W]),('original_losers',g[~g.original_W]),('original_mfe_lt5_losers',g[(~g.original_W)&g.original_mfe_lt5]),('original_mfe_ge10_winners',g[g.original_W&g.original_mfe.ge(.10)])]:
  b=q[q.open_above_J.eq(False)]
  r['groups'].append(dict(group=name,N=len(q),known=int(q.known.sum()),blocked=len(b),blocked_pct=100*len(b)/len(q) if len(q) else None,original_amount=sum(abs(q.original_net)),blocked_original_amount=sum(abs(b.original_net)),blocked_original_amount_pct=100*sum(abs(b.original_net))/sum(abs(q.original_net)) if len(q) else None))
 sums.append(r)
assert all(hashlib.sha256(Path(p).read_bytes()).hexdigest()==h for p,h in hashes.items())
# Fixed extraction rule, not choosing the most favorable examples.
examples=[]
for win in d.window.unique():
 for label,mask in [('blocked_winner',d.original_W&d.open_above_J.eq(False)),('blocked_loser',~d.original_W&d.open_above_J.eq(False))]:
  q=d[d.window.eq(win)&mask].sort_values(['signal_day','sid']).head(3);examples.extend([dict(example_group=label,**r) for r in q.to_dict('records')])
# Return all rows losslessly; no new lifecycle, sorting, fill or PnL.
out=dict(summary=sums,examples=examples,rows=rows,qa=dict(actual_original_common_closed_rounds=2862,original_entry_OPEN_matches=True,source_hashes_unchanged=True,new_economic_runs=0,ranking_runs=0,rule_unchanged_from_19_fixed_cases=True,next_open_factor_bridge_not_assumed=True),source_hashes=hashes)

def clean(v):
 if isinstance(v,dict):return {str(k):clean(x) for k,x in v.items()}
 if isinstance(v,(list,tuple)):return [clean(x) for x in v]
 if isinstance(v,(np.bool_,)):return bool(v)
 if isinstance(v,(np.integer,)):return int(v)
 if isinstance(v,(float,np.floating)):return float(v) if np.isfinite(v) else None
 return v
print('SUMMARY:'+json.dumps(clean(sums),ensure_ascii=False,allow_nan=False))
print('EXAMPLES:'+json.dumps(clean(examples),ensure_ascii=False,allow_nan=False))
import gzip,base64
print('DATA:'+base64.b64encode(gzip.compress(json.dumps(clean(out),ensure_ascii=False,allow_nan=False).encode(),mtime=0)).decode())
