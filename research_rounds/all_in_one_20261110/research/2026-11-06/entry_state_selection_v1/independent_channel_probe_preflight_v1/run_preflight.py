"""One frozen same-five-window decomposition preflight. No new accounts or returns."""
from pathlib import Path
import numpy as np,pandas as pd,json,hashlib,ast
from core import simulate
O=Path(__file__).resolve().parent;P=O.parent/"independent_channel_amount_preflight_v1"
U=Path("/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/universe-cp1-inputs-20261031")
H=Path("/Users/bytedance/Documents/ChatGPT/money/TradingAlarm/runtime/market/update-20261030-153010-c551af/prepared/h1.npz")
S={}
def src(p,expected=None):
 p=Path(p);h=hashlib.sha256(p.read_bytes()).hexdigest()
 if expected:assert h==expected
 S[str(p)]=h;return p
if (O/"RUN_ONCE.json").exists():raise RuntimeError("Refuse rerun")
for p in [Path(__file__),O/"core.py",O/"PROTOCOL.md"]:src(p)
(O/"RUN_ONCE.json").write_text(json.dumps(dict(started=str(pd.Timestamp.now(tz="UTC")),precompute_sources=S.copy()),indent=2))
manifest={m["symbol"]:m for m in json.loads(src(U/"STOCK_MANIFEST.json").read_text())}
with np.load(src(H),allow_pickle=False) as h:cal=pd.DatetimeIndex(h["dates"])
cal=cal[cal<="2026-06-30"]
windows=json.loads(src(P/"FIXED_WINDOWS.json").read_text())
tree=ast.parse(src(P/"preflight.py").read_text())
node=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=="inputs")
exec(compile(ast.Module(body=[node],type_ignores=[]),str(P/"preflight.py")+":inputs_only","exec"),globals())
def data(sid,cut=None):
 q=inputs(sid,cut)
 q["price_valid"]=q.coordinate_valid.copy()
 for c in ["open","high","low","close"]:q["price_valid"]&=np.isfinite(q[c])&q[c].gt(0)
 for c in ["price_eligible","observed_bar","is_observed_bar"]:q["price_valid"]&=q[c].fillna(False).astype(bool)
 for c in ["source_invalid","synthetic_event_bar"]:q["price_valid"]&=~q[c].fillna(True).astype(bool)
 q["price_valid"]&=q.identity.notna()&q.low.le(q.close)&q.close.le(q.high)
 q["amount_valid"]=np.isfinite(q.amount)&q.amount.gt(0)&np.isfinite(q.raw_volume)&q.raw_volume.gt(0)&q.volume_eligible.fillna(False).astype(bool)
 return q
parts=[];prefix=[];all_births=[];nexts=[]
for sid,(a,b) in windows.items():
 q=data(sid);x=simulate(q)
 for cut in [a,b]:
  xx=simulate(data(sid,pd.Timestamp(cut)));pd.testing.assert_frame_equal(x.loc[xx.index],xx,check_exact=True)
  prefix.append(dict(sid=sid,cut=cut,pass_prefix=True))
 z=x.loc[a:b].reset_index();z["sid"]=sid;parts.append(z)
 bb=x[x.born].reset_index();bb["sid"]=sid;all_births.append(bb)
 for ev in z[z.receipt].itertuples():
  j=cal.get_loc(ev.day);nd=cal[j+1] if j+1<len(cal) else None
  rr=q.loc[nd] if nd is not None else None;sig=q.loc[ev.day]
  nexts.append(dict(sid=sid,day=ev.day,root_day=ev.root_day,receipt_id=sid+"|"+ev.receipt_id,born=ev.born,phase=ev.phase,next_common_open_day=nd,next_raw_open=rr.raw_open if rr is not None else np.nan,all_day_one_price=bool(rr.raw_open==rr.raw_high==rr.raw_low==rr.raw_close) if rr is not None and rr.price_valid else None,source_factor_match=bool(rr.identity==sig.identity and np.isclose(rr.adjustment_factor,sig.adjustment_factor,rtol=1e-11)) if rr is not None and rr.price_valid else False,next_open_above_signal_floor=bool(rr.open>ev.S_new) if rr is not None and rr.price_valid else None,historical_fill="UNKNOWN_NOT_SIMULATED"))
x=pd.concat(parts,ignore_index=True);x["receipt_id"]=x.apply(lambda r:r.sid+"|"+r.receipt_id if pd.notna(r.receipt_id) else None,axis=1)
x.to_csv(O/"FIXED_DAILY.csv",index=False)
x[x.born|x.failed|x.root_unknown|x.confirmed_now|x.receipt|x.e0_raised].to_csv(O/"MARKET_EVENTS.csv",index=False)
pd.concat(all_births,ignore_index=True).to_csv(O/"FULL_PREFIX_BIRTHS.csv",index=False)
pd.DataFrame(nexts).to_csv(O/"NEXT_OPEN_OBSERVATIONS.csv",index=False)
pd.DataFrame(prefix).to_csv(O/"PREFIX_QA.csv",index=False)
summary=[]
for sid,g in x.groupby("sid"):
 bb=g[g.born];rr=g[g.receipt]
 summary.append(dict(sid=sid,days=len(g),births=len(bb),birth_E0_off=int(bb.E0.eq(0).sum()),birth_I_off=int(bb.I.eq(0).sum()),birth_i_buy_false=int(bb.i_buy.eq(0).sum()),birth_CP_false=int(bb.CP.eq(0).sum()),birth_probe=int(bb.phase.eq("PROBE").sum()),confirmations=int(g.confirmed_now.sum()),receipts=len(rr),failures=int(g.failed.sum()),unknown_roots=int(g.root_unknown.sum()),active_days=int(g.active.sum())))
pd.DataFrame(summary).to_csv(O/"SUMMARY.csv",index=False)
(O/"SOURCE_HASHES.json").write_text(json.dumps(S,indent=2))
assert all(hashlib.sha256(Path(p).read_bytes()).hexdigest()==h for p,h in S.items())
(O/"QA.json").write_text(json.dumps(dict(stocks=5,days=len(x),prefix_checks=10,new_accounts=0,new_returns=0,new_order_fills=0,source_hashes_unchanged=True,upstream_PIT_not_reaudited=True),indent=2))
print(pd.DataFrame(summary).to_string(index=False))
print(x[x.born|x.failed|x.root_unknown|x.confirmed_now][["sid","day","born","phase","root_day","a_day","U","B","Q","R","F","S_old","S_new","E0","I","G","i_buy","CP","failed","root_unknown"]].to_string(index=False))
