"""Frozen five-stock independent channel/amount market-state preflight. No economics."""
from pathlib import Path
import numpy as np,pandas as pd,json,hashlib
R=Path("/Users/bytedance/Documents/Codex/2026-11-06/entry_state_selection_v1")
O=Path(__file__).resolve().parent
U=Path("/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/universe-cp1-inputs-20261031")
H=Path("/Users/bytedance/Documents/ChatGPT/money/TradingAlarm/runtime/market/update-20261030-153010-c551af/prepared/h1.npz")
S={}
def src(p,expected=None):
 p=Path(p);v=hashlib.sha256(p.read_bytes()).hexdigest()
 if expected:assert v==expected,(p,v,expected)
 S[str(p)]=v;return p
manifest={m["symbol"]:m for m in json.loads(src(U/"STOCK_MANIFEST.json").read_text())}
with np.load(src(H),allow_pickle=False) as h:cal=pd.DatetimeIndex(h["dates"])
cal=cal[cal<="2026-06-30"]
windows={"300085.SZ":["2024-09-02","2024-10-31"],"002583.SZ":["2024-09-02","2024-10-31"],"300666.SZ":["2025-12-01","2026-02-27"],"600096.SH":["2022-02-07","2022-05-31"],"300529.SZ":["2022-09-01","2022-11-30"]}
protocol=dict(
 mathematics="At breakout F=ln(Ct/Ca), so Q>=ln(U/Ca) iff accumulated low-amount frontier discount D=F-Q <= ln(Ct/U). With every frontier amount>=B, this degenerates to pure20High. A strong one-day move can qualify; turnover alone without new frontier cannot. a is selected independently using only the current prefix and cannot revise any previously born root.",
 status="Frozen before the only market-state computation; five previously seen development cases, not OOS.",
 entry="U=max previous20 adjusted High; a=latest minimum previous20 close, restricted a>=last root failure day; B=median21 amounts strictly before a. From a+1 to t each new close frontier contributes min(1,sqrt(A_j/B))*delta log frontier. Birth if C_t>U and Q>=log(U/C_a), no E0/I/G/PVR gate.",
 protection="S_birth=min Low[a..t]. On later days first check C_t<=S_old. If not failed and original E0 target=1 with finite 0<E0floor<C, raise S=max(S_old,E0floor). Do not test a newly raised floor retroactively. No fixed profit target/cooldown.",
 renewal="Failure at t closes market root and suppresses same-bar birth. Subsequent birth uses new frontier evidence after failure; a cannot precede failure. No credit before that a reused. One birth per market root. This does not implement order/pending/actual fill identity; a real consumer must wait actual sell completion and cannot recycle the same signal.",
 unknown="Full common-date valid OHLC/amount/positive raw_volume and identical source_kind/source_path/segment required for prior20 range, a..t path and a-prior21 amount window. Missing/changed price source marks current root UNKNOWN, not a sale. New contiguous segment can later emit research roots, but cannot unlock an UNKNOWN trading account.",
 scope="No trade, budget, fee, holdings, returns, future-price outcome, labels, ranking or parameter scan. Original G/I/freshCP only comparison; PVR not read.",
 difference="Reuses DAP capped frontier credit but threshold is full observed20High resistance interval not sqrt5 volatility. Independent root admission differs from E1 actual buy gate, E0-gated LER, and E0-start channel ATR; new composite not claimed superior or globally original.",
 execution="Signal known t close. Market evidence is not an order fill. If bought at next OPEN, earliest sale is following common OPEN under T+1; a close failure on buy day can request that sale. Invalid/missing/limit-blocked next open must not be silently skipped or backfilled. Earliest immediate next common OPEN, only a price observation; conditional actual execution requires separately fixed sizing/permissions/source/market rules."
)
if (O/"RUN_ONCE.json").exists():raise RuntimeError("Refuse overwrite")
(O/"RUN_ONCE.json").write_text(json.dumps(dict(started=str(pd.Timestamp.now(tz="UTC")),script_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()),indent=2))
(O/"PROTOCOL.json").write_text(json.dumps(protocol,indent=2,ensure_ascii=False))
(O/"FIXED_WINDOWS.json").write_text(json.dumps(windows,indent=2))
src(Path(__file__))
def inputs(sid,cut=None):
 m=manifest[sid];path=next(p for p in m["source_sha256"] if p.endswith("/signal.parquet"))
 raw=pd.read_parquet(src(path,m["source_sha256"][path]))
 f=pd.read_parquet(src(m["refs"]["facts"],m["output_sha256"][m["refs"]["facts"]]))
 cp=pd.read_parquet(src(m["refs"]["CP1"],m["output_sha256"][m["refs"]["CP1"]]))
 dates=cal if cut is None else cal[cal<=cut]
 if cut is not None:raw=raw.loc[:cut];f=f.loc[:cut];cp=cp.loc[:cut]
 q=raw.reindex(dates).copy()
 for c in ["e0_target","e0_floor","e0_ready","i_target","i_buy","g_grade","g_ready"]:q[c]=pd.to_numeric(f[c].reindex(dates),errors="coerce").astype(float)
 q["CP"]=pd.to_numeric(cp.receipt.reindex(dates),errors="coerce").astype(float)
 q["valid"]=True
 for c in ["open","high","low","close","amount","raw_volume"]:q["valid"]&=np.isfinite(q[c])&q[c].gt(0)
 for c in ["price_eligible","volume_eligible","observed_bar","is_observed_bar"]:q["valid"]&=q[c].fillna(False).astype(bool)
 for c in ["source_invalid","synthetic_event_bar"]:q["valid"]&=~q[c].fillna(True).astype(bool)
 q["valid"]&=q.low.le(q.close)&q.close.le(q.high)
 q["identity"]=q.source_kind.astype("string")+"|"+q.source_path.astype("string")+"|"+q.segment_id.astype("string")
 q["valid"]&=q.identity.notna()
 # Coordinate/source alignment is knowledge validity, never a bullish gate.
 q["coordinate_valid"]=np.isfinite(q.adjustment_factor)&q.adjustment_factor.gt(0)
 for c in ["open","high","low","close"]:
  q["coordinate_valid"]&=np.isfinite(q["raw_"+c])&q["raw_"+c].gt(0)&np.isclose(q[c],q["raw_"+c]*q.adjustment_factor,rtol=1e-12,atol=1e-8)
 # Missing native E0 facts means no E0 takeover. Existing-but-mismatched facts are UNKNOWN.
 ff=f.reindex(dates);present=ff.close.notna()
 match=np.isclose(q.close,ff.close,rtol=1e-12,atol=1e-8)&np.isclose(q.adjustment_factor,ff.factor,rtol=1e-12,atol=1e-10)&q.segment_id.eq(ff.segment_id)&np.isclose(q.raw_close,ff.raw_close,rtol=1e-12,atol=1e-8)
 q["coordinate_valid"]&=(~present)|match
 q["valid"]&=q.coordinate_valid
 both=q.close.notna()&f.close.reindex(dates).notna()
 assert np.allclose(q.loc[both,"close"],f.close.reindex(dates)[both],rtol=0,atol=1e-8)
 return q
def simulate(q):
 rows=[];root=None;floor=np.nan;last_failure=None;segment_start=None;lastid=None
 for j,(d,r) in enumerate(q.iterrows()):
  valid=bool(r.valid);fresh_segment=valid and (segment_start is None or r.identity!=lastid)
  row=dict(day=d,valid=valid,C=float(r.close) if pd.notna(r.close) else np.nan,E0=r.e0_target,I=r.i_target,G=r.g_grade,i_buy=r.i_buy,CP=r.CP,
   born=False,failed=False,root_unknown=False,root_day=None,active=False,U20=np.nan,a_day=None,B_a=np.nan,price_span=np.nan,Q=np.nan,required_credit=np.nan,credit_coverage=np.nan,initial_floor=np.nan,old_floor=floor,new_floor=floor,e0_raised=False,blocked="NONE")
  if not valid or fresh_segment:
   if root is not None:row["root_unknown"]=True
   root=None;floor=np.nan;last_failure=None
   row["old_floor"]=np.nan;row["new_floor"]=np.nan
   segment_start=j if valid else None
  lastid=r.identity if valid else None
  if not valid:row["blocked"]="INVALID_PRICE_SOURCE";rows.append(row);continue
  if root is not None:
   row["root_day"]=q.index[root];row["active"]=True;row["old_floor"]=floor
   if r.close<=floor:
    row["failed"]=True;row["active"]=False;root=None;floor=np.nan;last_failure=j;row["blocked"]="CLOSE_FAILED_OLD_FLOOR"
   elif r.e0_ready==1 and r.e0_target==1 and np.isfinite(r.e0_floor) and 0<r.e0_floor<r.close:
    old=floor;floor=max(floor,float(r.e0_floor));row["e0_raised"]=floor>old
   row["new_floor"]=floor;rows.append(row);continue
  if j-segment_start<20:row["blocked"]="LESS_THAN20_CONTIGUOUS_PRIOR_BARS";rows.append(row);continue
  astart=max(j-20,last_failure if last_failure is not None else segment_start)
  hist=q.iloc[astart:j];vals=hist.close.to_numpy(float)
  a=astart+int(np.flatnonzero(vals==vals.min())[-1])
  U20=float(q.high.iloc[j-20:j].max());row["U20"]=U20;row["a_day"]=q.index[a]
  if a-segment_start<21:row["blocked"]="ANCHOR_PRIOR21_AMOUNT_UNKNOWN";rows.append(row);continue
  B=float(q.amount.iloc[a-21:a].median());ca=float(q.close.iloc[a])
  required=float(np.log(U20/ca));assert required>=-1e-12
  F=0.;Q=0.
  for k in range(a+1,j+1):
   v=float(np.log(q.close.iloc[k]/ca));delta=max(0.,v-F)
   Q+=min(1.,mathsqrt(float(q.amount.iloc[k])/B))*delta;F=max(F,v)
  assert -1e-12<=Q<=F+1e-12
  row.update(low_amount_discount=F-Q,breakout_excess=float(np.log(r.close/U20)),B_a=B,price_span=float(np.log(r.close/ca)),Q=Q,required_credit=required,credit_coverage=Q/required if required>0 else np.nan)
  if r.close>U20 and Q>=required:
   assert np.isclose(F,float(np.log(r.close/ca)),rtol=0,atol=1e-12)
   assert (F-Q<=float(np.log(r.close/U20))+1e-12)
   root=j;floor=float(q.low.iloc[a:j+1].min())
   row.update(born=True,active=True,root_day=d,initial_floor=floor,new_floor=floor,blocked="NEW_INDEPENDENT_CHANNEL_ROOT")
  elif r.close<=U20:row["blocked"]="NO20_HIGH_BREAK"
  else:row["blocked"]="PRICE_BREAK_AMOUNT_CREDIT_SHORT"
  rows.append(row)
 x=pd.DataFrame(rows).set_index("day")
 for c in ["root_day","a_day"]:x[c]=pd.to_datetime(x[c]).astype("datetime64[ns]")
 for c in ["low_amount_discount","breakout_excess"]:
  if c not in x:x[c]=np.nan
  x[c]=pd.to_numeric(x[c],errors="coerce").astype(float)
 return x
def mathsqrt(v):return float(np.sqrt(v))
parts=[];prefix=[];all_births=[]
for sid,(a,b) in windows.items():
 q=inputs(sid);x=simulate(q)
 for cut in [a,b]:
  xx=simulate(inputs(sid,pd.Timestamp(cut)))
  pd.testing.assert_frame_equal(x.loc[xx.index],xx,check_exact=True)
  prefix.append(dict(sid=sid,cut=cut,pass_prefix=True,rows=len(xx)))
 z=x.loc[a:b].reset_index();z["sid"]=sid;z["window_start"]=a;z["window_end"]=b
 parts.append(z)
 h=x[x.born].reset_index();h["sid"]=sid;all_births.append(h)
x=pd.concat(parts,ignore_index=True);x.to_csv(O/"FIXED_DAILY.csv",index=False)
events=x[x.born|x.failed|x.root_unknown].copy();events.to_csv(O/"FIXED_MARKET_EVENTS.csv",index=False)
pd.concat(all_births,ignore_index=True).to_csv(O/"FULL_PREFIX_BIRTHS.csv",index=False)
summary=[]
for sid,g in x.groupby("sid"):
 e=g[g.born]
 summary.append(dict(sid=sid,days=len(g),births=len(e),failures=int(g.failed.sum()),unknown_roots=int(g.root_unknown.sum()),active_days=int(g.active.sum()),birth_E0_false=int(e.E0.eq(0).sum()),birth_I_false=int(e.I.eq(0).sum()),birth_i_buy_false=int(e.i_buy.eq(0).sum()),birth_CP_false=int(e.CP.eq(0).sum()),credit_short_bars=int(g.blocked.eq("PRICE_BREAK_AMOUNT_CREDIT_SHORT").sum()),E0_raise_days=int(g.e0_raised.sum()),carried_root_at_start=bool(g.iloc[0].active and not g.iloc[0].born),first_birth=str(e.day.min()) if len(e) else None))
pd.DataFrame(summary).to_csv(O/"SUMMARY.csv",index=False)
pd.DataFrame(prefix).to_csv(O/"PREFIX_QA.csv",index=False)
(O/"SOURCE_HASHES.json").write_text(json.dumps(S,indent=2))
qa=dict(stocks=5,days=len(x),prefixes=len(prefix),new_lifecycles=0,new_economic_returns=0,new_account_runs=0,raw_fact_coordinate_mismatch_is_UNKNOWN=True,source_hashes_unchanged=all(hashlib.sha256(Path(p).read_bytes()).hexdigest()==h for p,h in S.items()),original_source_chain_not_recomputed=True)
assert qa["source_hashes_unchanged"]
(O/"QA.json").write_text(json.dumps(qa,indent=2))
print(pd.DataFrame(summary).to_string(index=False))
print(events[["sid","day","born","failed","root_day","E0","I","G","i_buy","CP","U20","a_day","B_a","Q","required_credit","credit_coverage","initial_floor","old_floor","new_floor","C"]].to_string(index=False))
