from pathlib import Path
import json,hashlib
import pandas as pd,numpy as np
R=Path('/Users/bytedance/Documents/Codex/2026-11-06/entry_state_selection_v1')
M=Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/universe-cp1-inputs-20261031/STOCK_MANIFEST.json')
H=Path('/Users/bytedance/Documents/ChatGPT/money/TradingAlarm/runtime/market/update-20261030-153010-c551af/prepared/h1.npz')
F=R/'frontier_volume_bound_preflight_v1/FIXED_CASE_RESULTS_COMPLETE.json'
cases=json.loads(F.read_text());assert len(cases)==19
manifest={x['symbol']:x for x in json.loads(M.read_text())}
cal=pd.DatetimeIndex(np.load(H,allow_pickle=False)['dates'])
rr=pd.read_parquet(R/'independent_channel_full1709_preflight_v1/overlap/RECEIPT_CONDITIONAL_OVERLAP.parquet',filters=[('sid','in',sorted({x['sid'] for x in cases}))])
sup=pd.read_csv(R/'independent_channel_probe_preflight_v1/FIXED_DAILY.csv',parse_dates=['day','root_day'],float_precision='round_trip')
hashes={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in [M,H,F]}
sources={};out=[]
for x in cases:
 sid=x['sid'];d=pd.Timestamp(x['day']);m=manifest[sid]
 if sid not in sources:
  sp=Path(next(p for p in m['source_sha256'] if p.endswith('/signal.parquet')));h=hashlib.sha256(sp.read_bytes()).hexdigest();assert h==m['source_sha256'][str(sp)];hashes[str(sp)]=h;sources[sid]=pd.read_parquet(sp).reindex(cal)
 p=sources[sid];k=cal.get_loc(d);nd=cal[k+1]
 match=rr[rr.sid.eq(sid)&rr.day.eq(d)]
 if len(match)==0:match=sup[sup.sid.eq(sid)&sup.day.eq(d)]
 assert len(match)==1
 rec=match.iloc[0];assert bool(rec.receipt) and bool(rec.active)
 prior=p.iloc[k-20:k] if rec.born else p.loc[pd.Timestamp(rec.root_day):d].iloc[:-1]
 J=float(rec.U) if rec.born else float(prior.close.max())
 if rec.born:assert J==prior.high.max()
 assert np.isclose(J/p.loc[d,'adjustment_factor'],x['boundary_raw'],rtol=1e-12,atol=1e-10)
 prefix=p.loc[:d]
 J2=float(prefix.iloc[-21:-1].high.max()) if rec.born else float(prefix.loc[pd.Timestamp(rec.root_day):].iloc[:-1].close.max())
 assert J==J2
 z=p.loc[nd];s=p.loc[d]
 known=np.isfinite(z.raw_open) and z.raw_open>0 and np.isfinite(z.adjustment_factor) and all(str(z[c])==str(s[c]) for c in ['source_kind','source_path','segment_id']) and z.adjustment_factor==s.adjustment_factor
 O=float(z.raw_open)*float(z.adjustment_factor) if known else None
 out.append(dict(sid=sid,day=x['day'],role=x['role'],root_day=str(rec.root_day),born=bool(rec.born),J_native=J,J_raw=J/float(s.adjustment_factor),signal_C=float(s.raw_close),next_day=str(nd.date()),next_open_raw=float(z.raw_open) if np.isfinite(z.raw_open) else None,next_open_native=O,open_above_J=bool(O>J) if known else None,open_equal_J=bool(O==J) if known else None,open_edge_pct=(O/J-1)*100 if known else None,known=bool(known),phase=x['phase'],E0=x['E0'],I=x['I'],prefix_exact=True))
assert all(hashlib.sha256(Path(p).read_bytes()).hexdigest()==h for p,h in hashes.items())
result=dict(frozen_rule='Original PRICE PASS and native nextOPEN > frozen per-receipt J; born J=prior20High, continuing J=previous root maxClose; no target if false, original new receipts can reenter, ADD unchanged. NOT a real fill proof.',cases=out,qa=dict(points=19,prefix_exact=19,sources_unchanged=True,new_economics=0,threshold_sweeps=0,known=sum(x['known'] for x in out),passed=sum(x['open_above_J'] is True for x in out),blocked=sum(x['open_above_J'] is False for x in out)),source_hashes=hashes)
print(json.dumps(result,ensure_ascii=False,allow_nan=False))
