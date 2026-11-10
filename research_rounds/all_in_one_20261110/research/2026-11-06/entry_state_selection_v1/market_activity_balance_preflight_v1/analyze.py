"""One fixed daily cross-sectional activity diagnostic. No economic replay."""
from pathlib import Path
import json,time,hashlib,datetime,math
import pandas as pd
import numpy as np
R=Path("/Users/bytedance/Documents/Codex/2026-11-06/entry_state_selection_v1")
O=Path(__file__).resolve().parent
U=Path("/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/universe-cp1-inputs-20261031")
H=Path("/Users/bytedance/Documents/ChatGPT/money/TradingAlarm/runtime/market/update-20261030-153010-c551af/prepared/h1.npz")
SM=U/"STOCK_MANIFEST.json"; MEM=R/"pvr_persistence_breadth_v1/FIXED_MEMBERSHIP.csv"
A=R/"lagged_amount_order_preflight_v1/FIXED_CASE_IDENTITIES.csv";B=R/"cross_window_entry_mechanism_v1/FIXED_CASES.csv"
START=time.monotonic(); HASHES={}
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def source(p,expected=None):
 h=sha(p)
 if expected is not None:assert h==expected,(str(p),"source drift")
 HASHES[str(p)]=h;return Path(p)
def clean(x):
 if isinstance(x,dict):return {str(k):clean(v) for k,v in x.items()}
 if isinstance(x,(list,tuple)):return [clean(v) for v in x]
 if isinstance(x,np.generic):return clean(x.item())
 if isinstance(x,(pd.Timestamp,Path)):return str(x)
 if isinstance(x,float) and not math.isfinite(x):return None
 if x is pd.NA or x is pd.NaT:return None
 return x
def save(n,v):
 with (O/n).open("x") as f:json.dump(clean(v),f,ensure_ascii=False,indent=2,allow_nan=False)
assert not (O/"FEATURE_SEAL.json").exists()
with (O/"RUN_ONCE.lock").open("x") as f:f.write(datetime.datetime.now(datetime.timezone.utc).isoformat())
source(__file__)
ca=pd.read_csv(source(A)).rename(columns={"signal_day":"day","scope":"origin"})
cb=pd.read_csv(source(B)).assign(origin=lambda d:"prior25:"+d.role)[["sid","day","origin"]]
cases=pd.concat([ca[["sid","day","origin"]],cb],ignore_index=True).groupby(["sid","day"],sort=True).origin.agg("|".join).reset_index()
cases.day=pd.to_datetime(cases.day);cases.to_csv(O/"FIXED_CASE_IDENTITIES.csv",index=False)
with np.load(source(H),allow_pickle=False) as z:cal=pd.DatetimeIndex(z["dates"])
cal=cal[cal<=pd.Timestamp("2026-06-30")]
dates=pd.DatetimeIndex(sorted(cases.day.unique()));at={d:cal.get_loc(d) for d in dates}
mem=pd.read_csv(source(MEM));sm={x["symbol"]:x for x in json.loads(source(SM).read_text())}
assert len(mem)==1709 and set(mem.sid)==set(sm)
protocol={"status":"FROZEN_BEFORE_NEW_FEATURES_PREVIOUSLY_SEEN_DEVELOPMENT_CASES_NOT_OOS",
"created_utc":datetime.datetime.now(datetime.timezone.utc).isoformat(),"fixed_cases":len(cases),"fixed_dates":len(dates),"universe_N":1709,
"formula":"r_i=log(Ct/Ct-1); a_i=log(A_t/median(A_t-21..t-1)); m_i=1+0.5*tanh(a_i). D=mean(m|r<0)-mean(m|r>0). Flat known names excluded from both groups. No target exclusion or within-sector ranking.",
"scope":"Same-day market-context hypothesis for unchanged M3 A/B entries. Not classic TRIN itself, not net aggressive flows, no fitted coefficients, smoothing, parameter scan, new ranking or account.",
"hypothesis":"When sector M3 is true but the declining-stock group has greater per-name activity relative to its own prior amount base, positive breadth may coexist with wider market fragility. This is a falsifiable conjecture, not causal demand/supply identification or a bull/bear forecast.",
"unknown_bounds":"For each known group n>0,S=sum(m), total missing M, lo=(S+.5M)/(n+M),hi=(S+1.5M)/(n+M). D_L=lo_down-hi_up;D_U=hi_down-lo_up. Outer bound independently assigns all missing to each side, conservative. Any known direction empty => UNKNOWN. PRESSURE if D_L>0;NO_PRESSURE if D_U<=0;otherwise UNKNOWN. UNKNOWN preserves original initial opportunity, never treated false.",
"consumer_not_implemented":"The sole candidate would withhold new initial risk only on certified PRESSURE dates and re-evaluate every new original legal ticket, with no permanent ban or cooldown. Original small probe, profits-only ADD and exits unchanged. No fills, dates, quantities or economic outputs generated here.",
"data":"22 exact immediate common observations ending at t, positive/eligible observed raw and adjusted prices, positive raw volume/amount with CNY/shares units, no synthetic/invalid; same source kind/path/segment and constant factor throughout; raw_close*factor matches close. Missing or warmup failures => unknown member. Current full day amount known only after t close, earliest effect next common OPEN.",
"limitations":"Current fixed1709 universe and industry mapping are NON-PIT and not full A market. Unknown bounds only address members of this fixed sample, not missing historical listings, survivor bias or retrospective vendor adjustment versions. Cases selected and labels seen in old studies, no prevalence or OOS inference.",
"old_work":"Not repeated: single-day positive credit deletion; group J rank/record event; sector total amount share*diffusion; OBV; whole-path U/V retest; r and r log(amount) next-return kernel. New organization is cross-stock current-sign-conditioned own-baseline activity means. This does not add raw information or prove incremental predictability.",
"source_links":["https://chartschool.stockcharts.com/table-of-contents/market-indicators/arms-index-trin","https://www.fidelity.com/learning-center/trading-investing/technical-analysis/technical-indicator-guide/trin"],
"stop":"Report every old fixed case, group sizes and unknowns. No direction flip, period/normalization changes, early-winner exception or alternative filter based on outcomes. Serious false rejection of early tails or no useful discrimination ends this candidate.",
"initial_hashes":dict(HASHES)}
save("PROTOCOL.json",protocol)
cols=["close","raw_close","raw_open","raw_high","raw_low","raw_volume","amount","adjustment_factor","segment_id","source_kind","source_path","price_eligible","volume_eligible","source_invalid","observed_bar","is_observed_bar","synthetic_event_bar","volume_unit","amount_unit"]
def feature(raw,day):
 k=at[day];idx=cal[k-21:k+1];q=raw.reindex(idx)
 out={"known":False,"reason":"","direction":None,"r":np.nan,"amount":np.nan,"amount_ref21":np.nan,"a":np.nan,"m":np.nan}
 if len(q)!=22 or q.close.isna().any():out["reason"]="MISSING_COMMON_PRICE_OR_WARMUP";return out
 if not all(c in q for c in cols):out["reason"]="FIELD_MISSING";return out
 for c in ["close","raw_close","raw_open","raw_high","raw_low","raw_volume","amount","adjustment_factor"]:
  if not np.isfinite(q[c]).all() or not q[c].gt(0).all():out["reason"]="INVALID_NONPOSITIVE_"+c;return out
 for c in ["price_eligible","volume_eligible","observed_bar","is_observed_bar"]:
  if not q[c].fillna(False).astype(bool).all():out["reason"]="OBSERVATION_FLAG_"+c;return out
 for c in ["source_invalid","synthetic_event_bar"]:
  if q[c].fillna(True).astype(bool).any():out["reason"]="INVALID_FLAG_"+c;return out
 for c in ["source_kind","source_path","segment_id"]:
  if q[c].isna().any() or q[c].nunique()!=1:out["reason"]="SOURCE_SEGMENT_CHANGE";return out
 if not q.volume_unit.eq("shares").all() or not q.amount_unit.eq("CNY").all():out["reason"]="UNIT_UNKNOWN";return out
 if not np.isclose(q.adjustment_factor,q.adjustment_factor.iloc[-1],rtol=1e-11,atol=0).all():out["reason"]="FACTOR_CHANGE_WITHIN22";return out
 if not np.isclose(q.raw_close*q.adjustment_factor,q.close,rtol=1e-10,atol=1e-10).all():out["reason"]="RAW_ADJUSTED_MISMATCH";return out
 r=float(np.log(q.close.iloc[-1]/q.close.iloc[-2]));ref=float(q.amount.iloc[:-1].median());amt=float(q.amount.iloc[-1]);a=math.log(amt)-math.log(ref);m=1+.5*math.tanh(a)
 out.update(known=True,reason="KNOWN",direction=1 if r>0 else -1 if r<0 else 0,r=r,amount=amt,amount_ref21=ref,a=a,m=m)
 return out
records=[];checks=[];prefix=[];target=set(cases.sid);rawcache={}
for j,sid in enumerate(sorted(sm)):
 md=sm[sid];paths=[p for p in md.get("source_sha256",{}) if p.endswith("/signal.parquet") and "prepared" in p]
 if len(paths)!=1:
  for day in dates:records.append(dict(sid=sid,day=day,known=False,reason="NATIVE_SOURCE_UNAVAILABLE",direction=None,r=np.nan,amount=np.nan,amount_ref21=np.nan,a=np.nan,m=np.nan))
  checks.append(dict(sid=sid,status=md["status"],native_available=False))
  continue
 p=source(paths[0],md["source_sha256"][paths[0]])
 raw=pd.read_parquet(p,columns=cols)
 assert raw.index.is_unique and raw.index.is_monotonic_increasing
 checks.append(dict(sid=sid,status=md["status"],native_available=True,path=str(p),sha256=HASHES[str(p)]))
 if sid in target:rawcache[sid]=raw
 for day in dates:
  val=feature(raw,day);records.append(dict(sid=sid,day=day,**val))
  if sid in target and ((cases.sid.eq(sid))&(cases.day.eq(day))).any():
   cut=feature(raw.loc[:day],day)
   same=clean(val)==clean(cut);assert same,(sid,day,"prefix mismatch")
   prefix.append(dict(sid=sid,day=day,equal=same))
 if (j+1)%300==0:print("stocks",j+1,"/",len(sm),"seconds",round(time.monotonic()-START,2),flush=True)
rr=pd.DataFrame(records);rr.to_parquet(O/"MEMBER_FEATURES.parquet",index=False)
pd.DataFrame(checks).to_csv(O/"SOURCE_CHECKS.csv",index=False);pd.DataFrame(prefix).to_csv(O/"PREFIX_CHECKS.csv",index=False)
def context(g,missing_extra=0):
 N=len(g)+missing_extra;known=g[g.known];M=N-len(known);up=known[known.direction.eq(1)];dn=known[known.direction.eq(-1)];flat=known[known.direction.eq(0)]
 nu=len(up);nd=len(dn);su=float(up.m.sum());sd=float(dn.m.sum())
 z=dict(N=N,K=len(known),M=M,n_up=nu,n_down=nd,n_flat=len(flat),sum_up=su,sum_down=sd,known_up_fraction=nu/(nu+nd) if nu+nd else np.nan,
        mean_up=su/nu if nu else np.nan,mean_down=sd/nd if nd else np.nan,D=np.nan,D_L=np.nan,D_U=np.nan,state="UNKNOWN",reason="EMPTY_KNOWN_DIRECTION")
 if nu and nd:
  ul=(su+.5*M)/(nu+M);uh=(su+1.5*M)/(nu+M);dl=(sd+.5*M)/(nd+M);dh=(sd+1.5*M)/(nd+M)
  l=dl-uh;u=dh-ul
  z.update(D=sd/nd-su/nu,D_L=l,D_U=u,mean_up_L=ul,mean_up_U=uh,mean_down_L=dl,mean_down_U=dh,state="PRESSURE" if l>0 else "NO_PRESSURE" if u<=0 else "UNKNOWN",reason="BOUNDED")
 return z
ctx=pd.DataFrame([dict(day=day,**context(g)) for day,g in rr.groupby("day")])
ctx.to_csv(O/"DATE_CONTEXT.csv",index=False)
rr.groupby(["day","known","reason"],dropna=False).size().rename("members").reset_index().to_csv(O/"UNKNOWN_REASONS.csv",index=False)
fc=cases.merge(ctx,on="day",validate="many_to_one").merge(mem[["sid","name","industry","sector_id"]],on="sid",validate="many_to_one")
fc=fc.merge(rr.rename(columns={c:"target_"+c for c in ["known","reason","direction","r","amount","amount_ref21","a","m"]}),on=["sid","day"],validate="one_to_one")
fc["earliest_next_common_open"]=[str(cal[at[d]+1].date()) for d in fc.day]
fc.to_csv(O/"FEATURES_PRELABEL.csv",index=False)
# Mechanical checks, not alternative fitted hypotheses.
def imbalance(u,d):return float(np.mean(d)-np.mean(u))
qa={"m_bounds":bool(rr.loc[rr.known,"m"].between(.5,1.5).all()),"known_inside_outer_bounds":bool((ctx.D>=ctx.D_L-1e-14).all() and (ctx.D<=ctx.D_U+1e-14).all()),"prefix_rows":len(prefix),
"equal_activity_every_name_D":imbalance([1,1,1],[1,1]),
"same_direction_counts_changed_activity_D":[imbalance([1.2,1.2],[.8,.8]),imbalance([.8,.8],[1.2,1.2])],
"price_sign_not_magnitude":"r magnitudes ignored once sign is known; any arbitrarily small nonzero move switches group. Same-day zero-price ticks excluded.",
"m_formula_quantity":"Relative CNY amount, not share turnover/free float or actual aggressive buy/sell volume."}
# Exhaustive missing-member extreme assignments validates conservative mean-difference bounds.
import itertools
boundtests=0
for ups,downs in [([.7],[1.2]),([.7,1.4],[.9]),([.5],[1.5])]:
 for M in range(4):
  nu,nd=len(ups),len(downs);su,sd=sum(ups),sum(downs)
  lo=(sd+.5*M)/(nd+M)-(su+1.5*M)/(nu+M);hi=(sd+1.5*M)/(nd+M)-(su+.5*M)/(nu+M)
  for assign in itertools.product([(0,.5),(0,1.5),(1,.5),(1,1.5),(-1,.5),(-1,1.5)],repeat=M):
   u=ups+[m for sign,m in assign if sign==1];d=downs+[m for sign,m in assign if sign==-1];v=imbalance(u,d)
   assert lo-1e-12<=v<=hi+1e-12
   boundtests+=1
qa["missing_completion_tests"]=boundtests
save("FEATURE_QA.json",qa)
save("SOURCE_HASHES.json",HASHES)
for p,h in HASHES.items():assert sha(p)==h,(p,"end source drift")
save("FEATURE_SEAL.json",{p.name:sha(p) for p in O.iterdir() if p.is_file()})
print(json.dumps({"status":"FEATURES_SEALED_NO_ECONOMICS","cases":len(cases),"dates":len(dates),"stocks":len(sm),"member_rows":len(rr),"date_states":ctx.state.value_counts().to_dict(),"case_states":fc.state.value_counts().to_dict(),"seconds":time.monotonic()-START,"K_range":[int(ctx.K.min()),int(ctx.K.max())]},ensure_ascii=False),flush=True)
