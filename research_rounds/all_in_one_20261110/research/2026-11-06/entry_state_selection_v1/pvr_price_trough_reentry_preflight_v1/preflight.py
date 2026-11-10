"""One frozen PVR/price trough sequence preflight. No new trading or payoff calculation."""
from pathlib import Path
import json,sys,hashlib,math
import numpy as np,pandas as pd
R=Path("/Users/bytedance/Documents/Codex/2026-11-06/entry_state_selection_v1")
O=Path(__file__).resolve().parent
U=Path("/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/universe-cp1-inputs-20261031")
F=Path("/Users/bytedance/Documents/Codex/2026-11-04/task-3/entry_quality/pvr_information_v1/feature_design")
H=Path("/Users/bytedance/Documents/ChatGPT/money/TradingAlarm/runtime/market/update-20261030-153010-c551af/prepared/h1.npz")
sys.path.insert(0,str(F));from features import original_pvr
S={}
if (O/"RUN_ONCE.json").exists():raise RuntimeError("Main run already started; do not overwrite.")
(O/"RUN_ONCE.json").write_text(json.dumps(dict(started_utc=str(pd.Timestamp.now(tz="UTC")),script_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()),indent=2))
def readpath(p,expected=None):
 p=Path(p);h=hashlib.sha256(p.read_bytes()).hexdigest()
 if expected is not None:assert h==expected,(p,h,expected)
 S[str(p)]=h
 return p
readpath(F/"features.py");readpath(Path(__file__))
sm={z["symbol"]:z for z in json.loads(readpath(U/"STOCK_MANIFEST.json").read_text())}
with np.load(readpath(H),allow_pickle=False) as h:cal=pd.DatetimeIndex(h["dates"])
cal=cal[cal<="2026-06-30"]
pairs=pd.read_csv(readpath(R/"peer_win_day_persistence_preflight_v1/PAIRED_FEATURES.csv"))
targets=[("2022-01-05","600339.SH"),("2022-05-06","002050.SZ"),("2022-05-12","300260.SZ"),("2022-11-03","000921.SZ")]
fixed=pd.concat([pairs[pairs.day.eq(d)&pairs.winner.eq(s)] for d,s in targets],ignore_index=True)
assert len(fixed)==4
windows={s:("2022-01-04","2022-12-30") for s in list(fixed.winner)+list(fixed.loser)}
windows.update({s:("2024-09-02","2024-10-31") for s in ["300085.SZ","002583.SZ"]})
windows.update({s:("2026-01-05","2026-06-30") for s in ["300623.SZ","300666.SZ","301611.SZ","603061.SH","688498.SH"]})
protocol=dict(
 scope="Exactly eight existing 2022 paired-case stocks for full 2022, plus two Sep-Oct2024 and five H1-2026 startup stocks; selected development cases, NOT independent OOS.",
 extrema="P_k strictly below both P_(k-1) and P_(k+1), known only at k+1 close. IEEE float comparisons on unchanged original PVR; exact ties do not create a trough, no epsilon/economic tolerance.",
 pair="Most recent two confirmed troughs a<b within a known native I root and uninterrupted source-valid common-date sequence. P_b<P_a AND min(C[a+1..b])>C_a.",
 issue="After b is confirmed, first t with C_t>max(C_(t-1),C_(t-2)), P_t>P_b, E0=I=1, Gready and Ggrade>=2, and finite 0<I_floor<C_t. One issue per (a,b), never backdated.",
 expiry="Next confirmed trough replaces setup whether or not its pair qualifies; C_t<=C_a, I/E0 off or UNKNOWN/source/common-date break kills setup. No arbitrary time expiry. An already issued token is not reissued.",
 clock="Market evidence at t close; only next immediate common OPEN can be considered. No simulated pending/fill or cash. Proposed consumer consumes identity on confirmed fill; NOFILL/expired one-day opportunity not replayed, needs a new b. Existing fast/CP/AB channels unchanged, so no original channel is blocked.",
 unknown="Invalid original PVR/price/source identity or missing common date clears pair. Root after a gap is UNKNOWN until an adjacent valid native I 0->1. Conservative extra knowledge restriction disclosed; does not change canonical PVR.",
 fit="No model fit, threshold scan, backwards pivot selection or new return labels. Existing economic rows joined only after feature outputs sealed.",
 evaluation="Counts and timing only. Existing per-stock realized core/FULL sums include every original round in the fixed birth window and retain UNKNOWN; neither new-strategy payoff nor shared-account return.",
 comparison="Original score exact check; original i_buy, CP receipt, E0/G/I, canonical sector M3/PVR3 alongside. PVR-only price-free divergence is NOT inferred to be supply absorption."
)
(O/"PROTOCOL.json").write_text(json.dumps(protocol,ensure_ascii=False,indent=2))
(O/"FIXED_PAIRS.csv").write_text(fixed.to_csv(index=False))
(O/"FIXED_WINDOWS.json").write_text(json.dumps(windows,indent=2))
canon=pd.read_parquet(readpath(R/"pvr_persistence_breadth_v1/STOCK_DAILY.parquet"))
broad=pd.read_parquet(readpath(R/"momentum_persistence_breadth_v1/canonical_mu3_comparison_v2/COMMON_K_COMPARISON.parquet"))
meta=pd.read_csv(readpath(R/"pvr_persistence_breadth_v1/FIXED_MEMBERSHIP.csv")).set_index("sid")
def make_input(sid,cut=None):
 m=sm[sid];sp=next(p for p in m["source_sha256"] if p.endswith("/signal.parquet"))
 raw=pd.read_parquet(readpath(sp,m["source_sha256"][sp]))
 f=pd.read_parquet(readpath(m["refs"]["facts"],m["output_sha256"].get(m["refs"]["facts"])))
 cp=pd.read_parquet(readpath(m["refs"]["CP1"],m["output_sha256"].get(m["refs"]["CP1"])))
 cc=cal if cut is None else cal[cal<=cut]
 if cut is not None:raw=raw.loc[:cut];f=f.loc[:cut];cp=cp.loc[:cut]
 p=original_pvr(raw)
 q=raw.reindex(cc).copy()
 for c in ["e0_target","i_target","i_floor","i_buy","g_grade","g_ready"]:q[c]=pd.to_numeric(f[c].reindex(cc),errors="coerce").astype(float)
 q["PVR"]=p.score.reindex(cc);q["CP"]=pd.to_numeric(cp.receipt.reindex(cc),errors="coerce").astype(float);q["CP_ready"]=pd.to_numeric(cp.ready.reindex(cc),errors="coerce").astype(float)
 q["valid"]=np.isfinite(q.PVR)&q.close.gt(0)&np.isfinite(q.close)&q.raw_volume.gt(0)
 for c in ["observed_bar","is_observed_bar","price_eligible","volume_eligible"]:q["valid"] &=q[c].fillna(False).astype(bool)
 for c in ["source_invalid","synthetic_event_bar"]:q["valid"] &=~q[c].fillna(True).astype(bool)
 q["identity"]=q.source_kind.astype("string")+"|"+q.source_path.astype("string")+"|"+q.segment_id.astype("string")
 q["valid"] &=q.identity.notna()&q.i_target.isin([0,1])&q.e0_target.isin([0,1])
 return q
def simulate(q):
 out=[];root=None;low=None;setup=None;emitted=False;lastvalid=False;lastid=None;lastI=None
 for j,(d,r) in enumerate(q.iterrows()):
  valid=bool(r.valid);same=valid and lastvalid and r.identity==lastid
  if not same:root=None;low=None;setup=None;emitted=False
  if valid and same and lastI==0 and r.i_target==1:root=j;low=None;setup=None;emitted=False
  if not valid or r.i_target!=1 or r.e0_target!=1:root=None;low=None;setup=None;emitted=False
  rec=dict(day=d,root_day=q.index[root] if root is not None else None,root_known=root is not None,knowledge_valid=valid,
   PVR=float(r.PVR) if pd.notna(r.PVR) else None,close=float(r.close) if pd.notna(r.close) else None,
   i_buy=r.i_buy,CP=r.CP,CP_ready=r.CP_ready,E0=r.e0_target,I=r.i_target,G=r.g_grade,Gready=r.g_ready,
   trough_confirmed=False,pair_condition=False,setup_live=False,issued=False,reason="NO_SETUP",
   a_day=None,b_day=None,known_day=None,P_a=None,P_b=None,C_a=None,C_b=None,minC_a1_b=None,age_since_b=None)
  if root is not None and j>=root+2:
   p=q.PVR.iloc
   if p[j-2]>p[j-1] and p[j]>p[j-1]:
    k=j-1;rec["trough_confirmed"]=True
    setup=None;emitted=False
    if low is not None:
     a=low;b=k;mn=float(q.close.iloc[a+1:b+1].min())
     if p[b]<p[a] and mn>q.close.iloc[a]:
      setup=dict(a=a,b=b,minC_a1_b=mn);rec["pair_condition"]=True
    low=k
   if setup is not None:
    a,b=setup["a"],setup["b"]
    rec.update(a_day=q.index[a],b_day=q.index[b],known_day=q.index[b+1],P_a=float(p[a]),P_b=float(p[b]),C_a=float(q.close.iloc[a]),C_b=float(q.close.iloc[b]),minC_a1_b=setup["minC_a1_b"],age_since_b=j-b)
    if r.close<=q.close.iloc[a]:setup=None;rec["reason"]="PRICE_ANCHOR_FAILED"
    else:
     rec["setup_live"]=True;rec["reason"]="ALREADY_ISSUED" if emitted else "WAIT_PRICE_AND_NATIVE_G"
     qualified=bool(r.g_ready==True and np.isfinite(r.g_grade) and r.g_grade>=2 and np.isfinite(r.i_floor) and 0<r.i_floor<r.close)
     if not emitted and qualified and r.close>max(q.close.iloc[j-1],q.close.iloc[j-2]) and r.PVR>p[b]:
      rec["issued"]=True;emitted=True;rec["reason"]="ONE_TIME_MARKET_EVIDENCE"
   if rec["trough_confirmed"] and setup is None and rec["reason"]=="NO_SETUP":rec["reason"]="NEW_TROUGH_PAIR_NOT_QUALIFIED"
  out.append(rec);lastvalid=valid;lastid=r.identity if valid else None;lastI=r.i_target if valid else None
 result=pd.DataFrame(out).set_index("day")
 for c in ["root_day","a_day","b_day","known_day"]:result[c]=pd.to_datetime(result[c]).astype("datetime64[ns]")
 for c in ["PVR","close","P_a","P_b","C_a","C_b","minC_a1_b","age_since_b"]:result[c]=pd.to_numeric(result[c],errors="coerce").astype(float)
 return result
frames=[];prefix=[];inputcache={}
for sid,(start,end) in windows.items():
 q=make_input(sid);inputcache[sid]=q;a=simulate(q)
 cached=canon[canon.sid.eq(sid)].set_index("day").score
 actual=cached.reindex(q.index)
 ci=q.index.intersection(cached.index)
 assert q.loc[ci,"PVR"].notna().equals(actual.loc[ci].notna()),(sid,"canonical finite-mask difference")
 ix=a.PVR.notna()&actual.notna()
 err=float((a.loc[ix,"PVR"]-actual[ix]).abs().max())
 assert err<1e-10,(sid,err)
 canonical_input=q.copy();canonical_input.loc[ci,"PVR"]=actual.loc[ci]
 ac=simulate(canonical_input)
 semantic=["root_day","root_known","trough_confirmed","pair_condition","setup_live","issued","reason","a_day","b_day","known_day","age_since_b"]
 pd.testing.assert_frame_equal(a.loc[ci,semantic],ac.loc[ci,semantic],check_exact=True)
 exact_mismatch=int((q.loc[ix,"PVR"]!=actual[ix]).sum())
 assert a.PVR.dropna().between(0,100).all()
 # Two raw-input truncations, not merely truncating computed PVR.
 for cut in [start,end]:
  short=simulate(make_input(sid,pd.Timestamp(cut)))
  pd.testing.assert_frame_equal(a.loc[short.index],short,check_exact=True)
  prefix.append(dict(sid=sid,cut=cut,rows=len(short),passed=True,canonical_pvr_maxerror=err,canonical_float_exact_mismatches=exact_mismatch,canonical_state_comparisons_identical=True))
 z=a.loc[start:end].reset_index();z["sid"]=sid;z["sector"]=meta.loc[sid,"sector_id"];z["window_start"]=start;z["window_end"]=end
 frames.append(z)
x=pd.concat(frames,ignore_index=True)
bc=["day","sector","N","K","M3_n","M3_candidate","M3_right_fixed_lower","M3_right_fixed_upper","PVR3_n","PVR3_candidate","sector_E0_valid","sector_stage","sector_authorization_usable","sector_receipt"]
x=x.merge(broad[bc],on=["day","sector"],how="left",validate="many_to_one")
x.to_csv(O/"FIXED_DAILY_PRELABEL.csv",index=False)
x[x.issued].to_csv(O/"SIGNAL_EVENTS_PRELABEL.csv",index=False)
x[x.trough_confirmed].to_csv(O/"TROUGH_CONFIRMATIONS_PRELABEL.csv",index=False)
s=[]
for sid,g in x.groupby("sid"):
 ev=g[g.issued]
 s.append(dict(sid=sid,days=len(g),valid=int(g.knowledge_valid.sum()),I_on=int(g.I.eq(1).sum()),known_I_root_days=int(g.root_known.sum()),troughs=int(g.trough_confirmed.sum()),pairs=int(g.pair_condition.sum()),issued=len(ev),with_i_buy=int(ev.i_buy.eq(True).sum()),with_CP=int(ev.CP.eq(True).sum()),neither_known=int((ev.i_buy.eq(False)&ev.CP.eq(False)&ev.CP_ready.eq(True)).sum()),CP_unknown=int((ev.CP.isna()|~ev.CP_ready.eq(True)).sum()),price_or_G_wait_days=int((g.setup_live&g.reason.eq("WAIT_PRICE_AND_NATIVE_G")).sum()),old_i_buy=int(g.i_buy.eq(True).sum()),old_CP=int(g.CP.eq(True).sum()),first_signal=str(ev.day.min()) if len(ev) else None,max_live_wait_days=int(g.loc[g.setup_live,"age_since_b"].max()) if g.setup_live.any() else None,unissued_live_at_end=bool(g.iloc[-1].setup_live and g.iloc[-1].reason=="WAIT_PRICE_AND_NATIVE_G")))
pd.DataFrame(s).to_csv(O/"SIGNAL_COUNTS_PRELABEL.csv",index=False)
pd.DataFrame(prefix).to_csv(O/"PREFIX_QA.csv",index=False)
(O/"FEATURE_SEAL.json").write_text(json.dumps({p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in O.glob("*PRELABEL.csv")},indent=2))
# Only now attach unchanged existing economics. No future path or outcome in the signal builder.
E=R/"m3_stock_birth_during_sector_v1"
rr=pd.concat([pd.read_csv(readpath(E/"relative_priority_equity_run_2022_v1/report/CORE_AND_FULL_ROUNDS.csv"),low_memory=False),pd.read_csv(readpath(E/"cash_equity_baseline_2024_v1/report/CORE_AND_FULL_ROUNDS.csv"),low_memory=False)],ignore_index=True)
rr=rr[rr.arm.eq("A_UNION_B")]
selected=[]
for sid,(start,end) in windows.items():
 g=rr[rr.sid.eq(sid)&rr.signal_day.between(start,end)].copy()
 if len(g):selected.append(g)
z=pd.concat(selected,ignore_index=True)
z.to_csv(O/"ALL_EXISTING_ROUNDS_IN_FIXED_WINDOWS.csv",index=False)
stats=[]
for sid,g in z.groupby("sid"):
 c=g[g.evidence_usable_closed.eq(True)];u=g[~g.evidence_usable_closed.eq(True)]
 stats.append(dict(sid=sid,original_permits=len(g),known_closed=len(c),other=len(u),core_wins=int(c.core_net.gt(0).sum()),core_sum=float(c.core_net.sum()),full_wins=int(c.net_pnl.gt(0).sum()),full_sum=float(c.net_pnl.sum()),all_fees_known_closed=float(c.all_fees.sum()),core_buy_cash_sum=float(c.core_buy_cash.sum()),full_buy_cash_sum=float(c.total_buy_cash.sum()),note="Original independent-round aggregate, not new strategy or shared account; all original permits retained"))
pd.DataFrame(stats).to_csv(O/"EXISTING_PARTICIPATION_SUMMARY.csv",index=False)
snaps=[]
for r in fixed.itertuples():
 for role,sid in [("winner",r.winner),("loser",r.loser)]:
  row=x[x.sid.eq(sid)&x.day.eq(pd.Timestamp(r.day))].iloc[0].to_dict()
  row.update(role=role,existing_original_core_return=r.wret if role=="winner" else r.lret)
  snaps.append(row)
pd.DataFrame(snaps).to_csv(O/"FIXED_PAIR_DAY_SNAPSHOTS.csv",index=False)
(O/"SOURCE_HASHES.json").write_text(json.dumps(S,indent=2))
qa=dict(stocks=len(windows),daily_rows=len(x),prefix_checks=len(prefix),pvr_range=[float(x.PVR.min()),float(x.PVR.max())],new_economic_runs=0,new_accounts=0,new_parameters_scanned=0,baseline_channels_modified=0,features_prior_to_label_join=True,all_source_hashes_still_match=all(hashlib.sha256(Path(p).read_bytes()).hexdigest()==h for p,h in S.items()))
assert qa["all_source_hashes_still_match"]
(O/"QA.json").write_text(json.dumps(qa,indent=2))
print(pd.DataFrame(s).to_string(index=False));print(pd.DataFrame(stats).to_string(index=False));print(x[x.issued][["sid","day","a_day","b_day","P_a","P_b","C_a","C_b","PVR","close","i_buy","CP","G","M3_candidate","PVR3_candidate"]].to_string(index=False));print(json.dumps(qa))
