"""Frozen dual-frontier CP signal replay. No account imports, orders or parameter search."""
from pathlib import Path
import sys,json,time,hashlib,math,collections
import numpy as np,pandas as pd
O=Path(__file__).resolve().parent; R=O.parent
M=Path("/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/universe-cp1-inputs-20261031/STOCK_MANIFEST.json")
NATIVE=Path("/Users/bytedance/Documents/ChatGPT/money/research_rounds/continuous-protection-lines-20261028/code/model.py")
sys.path.insert(0,str(NATIVE.parent));import model
END="2026-05-15"; START="2022-01-01"
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def clean(x):
 if isinstance(x,dict):return {str(k):clean(v) for k,v in x.items()}
 if isinstance(x,(list,tuple)):return [clean(v) for v in x]
 if isinstance(x,(np.integer,)):return int(x)
 if isinstance(x,(np.bool_,)):return bool(x)
 if isinstance(x,(float,np.floating)):return float(x) if np.isfinite(x) else None
 if isinstance(x,(pd.Timestamp,Path)):return str(x)
 return x
def save(n,x):(O/n).write_text(json.dumps(clean(x),ensure_ascii=False,indent=2))
def calc(f,pr,meanmode,z=None):
 if z is None:z=model.features(f)
 n=len(f);p=np.log(f.close.to_numpy());rseg=f.segment_id.to_numpy();valid=f.e0_valid.to_numpy(bool);down=f.e0_down.to_numpy(bool)
 rawv=pr.raw_volume.to_numpy(float);amt=pr.amount.to_numpy(float);lo=pr.raw_low.to_numpy(float);hi=pr.raw_high.to_numpy(float)
 factor=pr.adjustment_factor.to_numpy(float);rawq=np.divide(amt,rawv,out=np.full(n,np.nan),where=rawv>0)
 tol=np.divide(.5,rawv,out=np.zeros(n),where=rawv>0)+1e-8
 qok=(np.isfinite(rawq)&(rawq>0)&np.isfinite(factor)&(factor>0)&(rawq>=lo-tol)&(rawq<=hi+tol)&pr.volume_unit.eq("shares").to_numpy()&pr.amount_unit.eq("CNY").to_numpy()&pr.observed_bar.to_numpy(bool)&pr.price_eligible.to_numpy(bool)&pr.volume_eligible.to_numpy(bool)&~pr.source_invalid.to_numpy(bool)&~pr.synthetic_event_bar.to_numpy(bool))
 q=np.where(qok,np.clip(rawq,lo,hi)*factor,np.nan);x=np.minimum(p,np.log(q)) if meanmode else p
 zscale=z.z.to_numpy(float);mult=z.m.to_numpy(float);close=f.close.to_numpy(float)
 ready=np.isfinite(zscale)&(qok if meanmode else True);receipt=np.zeros(n,bool)
 fields={c:np.full(n,np.nan) for c in ["anchor","scale","credit","mean_frontier","displacement","delta_frontier","candidate","next_anchor"]}
 phases=np.zeros(n,np.int8);reset=np.zeros(n,np.int8)
 phase=0;a=hc=hq=s=np.nan;k=0.;seg=None
 for j in range(n):
  fresh=dq=0.;disp=np.nan;why=0
  if rseg[j]!=seg:phase=0;seg=rseg[j];why=1
  if not ready[j] or not valid[j]:
   phase=0;a=hc=hq=s=np.nan;k=0.;why=2 if not ready[j] else 3
  elif phase==0 or down[j]:
   phase=1;a=hc=hq=p[j];k=0.;s=zscale[j];why=4 if down[j] else 5
  elif phase==1 and model.gt(a,p[j]):
   a=hc=hq=p[j];k=0.;s=zscale[j];why=6
  else:
   fresh=p[j]-hc if model.gt(p[j],hc) else 0.
   if fresh:hc=p[j]
   dq=x[j]-hq if model.gt(x[j],hq) else 0.
   if dq:hq=x[j];k=math.fsum((k,dq*mult[j]))
   disp=hc-a
   receipt[j]=bool(fresh and model.ge(disp,math.sqrt(5)*s) and model.ge(k,math.sqrt(5)*s))
   if receipt[j]:fields["candidate"][j]=close[j]*math.exp(-math.sqrt(21)*s)
  phases[j]=phase
  for key,value in [("anchor",a),("scale",s),("credit",k),("mean_frontier",hq),("displacement",disp),("delta_frontier",fresh)]:fields[key][j]=value
  if receipt[j]:phase=2;a=hc=hq=p[j];k=0.;s=zscale[j];why=7
  fields["next_anchor"][j]=a;reset[j]=why
 out=pd.DataFrame(fields,index=f.index);out["ready"]=ready;out["receipt"]=receipt;out["phase"]=phases;out["reset"]=reset;out["qok"]=qok;out["q"]=q;out["q_raw"]=rawq
 return out

def run():
 start=time.monotonic(); manifest=json.loads(M.read_text());(O/"states").mkdir(exist_ok=True)
 case=json.loads((R/"lifecycle_ordered_damage_v1/FIXED_CASES_BEFORE_COMPUTE.json").read_text())
 for sid in ["300666.SZ","688603.SH","301611.SZ"]:case.append(dict(sid=sid,day="2026-01-15"))
 case.append(dict(sid="300085.SZ",day="2024-09-24"))
 freeze=dict(status="FULL_SIGNAL_REPLAY_FROZEN_BEFORE_FULLPOOL_OUTCOMES_SEEN_HISTORY",end=END,original_pool=1709,
 formula="p=logC; original price frontier hC/D retained. hq starts at each OWN anchor a. q=(CNY amount/raw_shares)*native factor; x=min(logC,logq); dq=max(x-hq,0); hq=max(hq,x); K+=dq*original_m. Receipt only when current price makes fresh hC and D,K>=sqrt5*frozen_scale. OWN receipt consumes and sets both frontiers=logC, K=0, scale=current original z.",
 resets="Original I.valid/native-down/SEEK-lower-anchor/source reset rules. q invalid or source/price/volume/synthetic flags invalid outputs UNKNOWN and clears new state; next valid observation starts SEEK. No original receipt borrowed.",
 q="Declared shares/CNY and observed/price_eligible/volume_eligible/not source_invalid/not synthetic. Raw mean must lie within raw L/H with fixed numerical tolerance 0.5 CNY/raw_shares + 1e-8 yuan; only within that rounding tolerance clip to raw interval. No price-unit or volume-unit fitting.",
 clock="Native original observed index and source segments exactly as original CP; common-calendar completeness only used for evaluation labels. No extra waiting or missing-session rule inserted into CP.",
 timing="Same-day both/old-only/new-only authoritative. Shifted event pairing descriptive only: exact common receipts delimit synchronization blocks within original I root, then unmatched chronological order one-to-one, excess unpaired. Root-level first events separately. Never assume two paired events are same evidence.",
 domains="Original full I signal domain; original-account-conditioned pre-size EMPTY/MOBILE Q/ACT and pending barriers plus industry permission; original 53121 legal MOBILE pending rows retained as separate old-defined domain. No fabricated new pending or executed fills.",
 outcomes="No account run. Existing original first rounds association only; original CORE entry not removed merely because CP changes. Price labels from next common OPEN to 5/20/60 completed closes, same source and no missing common session; fixed big60 MFE>=30%, terminal>=20%. Original root epoch and native I root both named, not silently interchanged.",
 periods=["2022","2023","2024","2025","2026 through May15","2024-09-24..2024-10-31","2026-01-01..2026-03-31"],
 prefixes="Every nonempty stock prefix through2024-09-24; named cases all query-date prefixes; first10 nonempty stocks also2022-12-30 and2026-01-15; exact full-prefix comparison after feature recomputation.",
 no_accounts=True,no_parameters=True,source_hash=sha(M),native_model_hash=sha(NATIVE),code_hash=sha(__file__))
 save("FREEZE.json",freeze)
 audits=[];prefixes=[];ev=[];annual=[];sources={str(M):sha(M),str(NATIVE):sha(NATIVE)};errors=[]
 for no,r in enumerate(manifest):
  sid=r["symbol"];pp=next(p for p in r["source_sha256"] if p.endswith("/signal.parquet"));paths=[pp,r["refs"]["CP1_input"],r["refs"]["CP1"],r["refs"]["facts"]]
  before={p:sha(p) for p in paths};sources.update(before)
  expected={**r.get("source_sha256",{}),**r.get("output_sha256",{})}
  badhash=[p for p in paths if p in expected and expected[p]!=before[p]]
  if badhash:raise ValueError(("manifest_source_hash_mismatch",sid,badhash))
  f=pd.read_parquet(paths[1]).loc[:END];pr=pd.read_parquet(pp).reindex(f.index);old=pd.read_parquet(paths[2]).reindex(f.index);facts=pd.read_parquet(paths[3]).reindex(f.index)
  if f.empty:
   audits.append(dict(sid=sid,status="NO_OBSERVATION_BY_CUTOFF",n=0));continue
  np.testing.assert_allclose(pr.close,f.close,rtol=0,atol=1e-10)
  assert pr.symbol.eq(sid).all() and pr.segment_id.eq(f.segment_id).all()
  z=model.features(f);base=calc(f,pr,False,z);new=calc(f,pr,True,z)
  assert base.receipt.equals(old.receipt),(sid,"baseline_receipt")
  maxerr=0.
  for col in ["anchor","scale","credit","displacement","delta_frontier","candidate","next_anchor"]:
   np.testing.assert_allclose(base[col],old[col],rtol=0,atol=1e-12,equal_nan=True,err_msg=sid+col)
   if base[col].notna().any():maxerr=max(maxerr,float((base[col]-old[col]).abs().max()))
  assert base.ready.equals(old.ready)
  cuts={"2024-09-24"}|{c["day"] for c in case if c["sid"]==sid}
  if no<10:cuts|={"2022-12-30","2026-01-15"}
  for cut in sorted(cuts):
   sub=f.loc[:cut]
   if sub.empty:continue
   zz=calc(sub,pr.loc[sub.index],True)
   pd.testing.assert_frame_equal(zz,new.loc[sub.index],check_exact=True)
   prefixes.append(dict(sid=sid,cutoff=cut,n=len(sub),passed=True))
  active=f.e0_valid.astype(bool);birth=active&(~active.shift(fill_value=False)|f.segment_id.ne(f.segment_id.shift()))
  rootdate=pd.Series(pd.NaT,index=f.index);rootdate.loc[birth]=f.index[birth];rootdate=rootdate.ffill().where(active)
  out=pd.DataFrame(dict(sid=sid,day=f.index.strftime("%Y-%m-%d"),segment=f.segment_id.to_numpy(),I_active=active.to_numpy(),I_root=rootdate.dt.strftime("%Y-%m-%d").to_numpy(),native_down=f.e0_down.to_numpy(),i_buy=facts.i_buy.to_numpy(),g_ready=facts.g_ready.to_numpy(),e0_ready=facts.e0_ready.to_numpy(),i_floor=f.i_floor.to_numpy(),close=f.close.to_numpy(),raw_close=pr.raw_close.to_numpy(),raw_open=pr.raw_open.to_numpy(),raw_high=pr.raw_high.to_numpy(),raw_low=pr.raw_low.to_numpy(),amount=pr.amount.to_numpy(),raw_volume=pr.raw_volume.to_numpy(),volume_factor=pr.volume_factor.to_numpy(),factor=pr.adjustment_factor.to_numpy(),q=new.q.to_numpy(),q_raw=new.q_raw.to_numpy(),qok=new.qok.to_numpy(),old_receipt=old.receipt.to_numpy(),new_receipt=new.receipt.to_numpy(),old_ready=old.ready.to_numpy(),new_ready=new.ready.to_numpy(),old_candidate=old.candidate.to_numpy(),new_candidate=new.candidate.to_numpy(),old_anchor=old.anchor.to_numpy(),new_anchor=new.anchor.to_numpy(),old_scale=old.scale.to_numpy(),new_scale=new.scale.to_numpy(),old_credit=old.credit.to_numpy(),new_credit=new.credit.to_numpy(),new_mean_frontier=new.mean_frontier.to_numpy(),new_phase=new.phase.to_numpy(),new_reset=new.reset.to_numpy()))
  out=out[out.day>=START].copy();out["year"]=out.day.str[:4].astype(int)
  out.to_parquet(O/"states"/(sid+".parquet"),index=False)
  ee=out[out.old_receipt|out.new_receipt];ev.append(ee)
  for y,g in out.groupby("year"):
   annual.append(dict(sid=sid,year=int(y),observed=len(g),I_active=int(g.I_active.sum()),q_known=int(g.qok.sum()),q_known_active=int((g.qok&g.I_active).sum()),old_receipts=int(g.old_receipt.sum()),new_receipts=int(g.new_receipt.sum()),both=int((g.old_receipt&g.new_receipt).sum()),old_only=int((g.old_receipt&~g.new_receipt).sum()),new_only=int((~g.old_receipt&g.new_receipt).sum())))
  unchanged=all(sha(p)==v for p,v in before.items());assert unchanged
  audits.append(dict(sid=sid,status="PASS",n=len(f),n_evaluation=len(out),source_kind=";".join(sorted(pr.source_kind.unique())),baseline_receipt_exact=True,baseline_numeric_maxerr=maxerr,q_unknown=int((~new.qok).sum()),q_unknown_active=int((~new.qok&active).sum()),inputs_unchanged=unchanged))
  if (no+1)%100==0:print("STOCKS",no+1,"SECONDS",round(time.monotonic()-start,1),flush=True)
 pd.concat(ev,ignore_index=True).to_parquet(O/"EVENTS.parquet",index=False)
 pd.DataFrame(audits).to_csv(O/"SOURCE_AND_BASELINE_AUDIT.csv",index=False)
 pd.DataFrame(prefixes).to_csv(O/"PREFIX_AUDIT.csv",index=False)
 pd.DataFrame(annual).to_csv(O/"STOCK_YEAR_EVENTS.csv",index=False)
 af=pd.DataFrame(annual).groupby("year").sum(numeric_only=True);af.to_csv(O/"ANNUAL_SIGNAL_COUNTS.csv")
 save("INPUT_SHA256.json",sources)
 save("SIGNAL_SEAL.json",dict(status="SIGNALS_COMPLETE_BEFORE_EVALUATION",code_hash=sha(__file__),freeze_hash=sha(O/"FREEZE.json"),events_hash=sha(O/"EVENTS.parquet"),n_events=sum(len(x) for x in ev),stocks=len(audits),prefixes=len(prefixes),seconds=time.monotonic()-start))
 print("ANNUAL",af.to_string());print("COMPLETE",time.monotonic()-start,flush=True)
if __name__=="__main__":run()
