"""Frozen bounded native monthly DMI experiment. No live orders."""
from pathlib import Path
from datetime import datetime,time as dtime,date
from decimal import Decimal as D
from types import MappingProxyType
import ast,sys,json,gzip,hashlib,pickle,copy,time,os,argparse,gc,traceback
import numpy as np,pandas as pd
O=Path(__file__).resolve().parent
R=O.parent; OLD=R/"act_only_ablation_continuous_v1"; BASE=OLD/"run"
sys.path.insert(0,str(OLD/"code"))
import run_act_only as E
C,A,N,J,L,IO,H=E.C,E.A,E.N,E.J,E.L,E.IO,E.H
Z=D(0);CAPITAL=D(1200000)
WINDOWS={"2022Jan":("2022-01-04","2022-01-28"),"2026Jan":("2026-01-05","2026-01-30")}
OUTPUT_LOGS=("daily","opportunities","funding","stage_events","balance_audit","rank_log","open_checks")
CHECKPOINT=BASE/"latest_checkpoint/checkpoint-2025-12-31.pkl"
ORIGINAL_FREEZE=json.loads((BASE/"RUNTIME_DEPENDENCY_FREEZE.json").read_text())
def sha(p):
 h=hashlib.sha256()
 with open(p,"rb") as f:
  for b in iter(lambda:f.read(8*1024*1024),b""):h.update(b)
 return h.hexdigest()
def read(p):return json.loads(Path(p).read_text())
def save(p,x):IO.write_json(p,E.canon(x))
def canon(x):return E.canon(x)
def rows(p):
 with gzip.open(p,"rt") as f:
  for l in f:yield json.loads(l)
def verify_original():
 for p,h in ORIGINAL_FREEZE.items():assert sha(p)==h,("ORIGINAL_SOURCE_DRIFT",p)
 for n,h in read(BASE/"OUTPUT_HASHES.json").items():
  p=Path(n) if Path(n).is_absolute() else BASE/n
  assert sha(p)==h,("ORIGINAL_OUTPUT_DRIFT",p)
def claim(path):
 fd=os.open(path,os.O_CREAT|os.O_EXCL|os.O_WRONLY)
 with os.fdopen(fd,"w") as f:json.dump(dict(pid=os.getpid(),UTC=datetime.now().astimezone().isoformat()),f)

def stream_digest(x):
 class Sink:
  def __init__(self):self.h=hashlib.sha256()
  def write(self,b):self.h.update(b);return len(b)
 s=Sink();pickle.Pickler(s,protocol=5).dump(x);return s.h.hexdigest()

def trim_logs(r):
 # Explicitly audited append/export-only fields, not account history.
 economic=lambda:dict(runner={k:v for k,v in E.payload(r)["runner"].items() if k not in OUTPUT_LOGS},accounts=E.payload(r)["accounts"])
 before=stream_digest(economic());logs={}
 for k in OUTPUT_LOGS:
  v=getattr(r,k,[])
  logs[k]=dict(count=len(v),stream_pickle_sha256=stream_digest(v))
  setattr(r,k,[])
 assert stream_digest(economic())==before
 return dict(economic_payload_unchanged=True,economic_sha256=before,removed_output_logs=logs)
def single_payload_restore(r,path):
 expected=IO.assert_checkpoint_identity(r,path)
 raw=path.read_bytes();p=pickle.loads(raw);del raw
 assert p["source_freeze"]==r.source_freeze
 assert p["runner"]["integration_policy"]==r.integration_policy
 assert p["runner"]["rank_scores_manifest_sha256"]==r.rank_scores_manifest_sha256
 assert p["runner"]["remove_confirmed60"]==r.remove_confirmed60
 assert set(p["accounts"])==set(r.accounts)=={"PVR","NOACT"}
 r.__dict__.update(p["runner"])
 for k,state in p["accounts"].items():r.accounts[k].__dict__.update(state)
 # Exact original PreparedRunner.restore assignments; identities additionally checked.
 assert IO.runner_identity(r)==expected
 r.assert_native_wiring()
 assert all(r.__dict__[k] is v for k,v in p["runner"].items())
 for k,state in p["accounts"].items():
  assert set(vars(r.accounts[k]))-{"market","facts"}==set(state)
  assert all(r.accounts[k].__dict__[f] is v for f,v in state.items())
 last=p["last_completed_event"];del p;gc.collect()
 return last
def make_runner(shared,receipts,cp,states,ir,factors,window,out,physical=False):
 r=A.Runner(shared,receipts,stock_cp=cp,industry_states=states,industry_receipts=ir)
 a=r.accounts["B"]
 assert not a.positions and not a.trades and not a.buys and not a.exits and not a.budget.lots and not a.budget.orders
 a.available=a.initial_cash=a.current_nav=a.minimum_available=CAPITAL;a.budget.cash=float(CAPITAL)
 a.risk_state=dict(on=True,peak=CAPITAL,saw_off=False,previous_fast=False,episode=0)
 other=E.clone_account(a);a.label="PVR";other.label="NOACT";r.accounts={"PVR":a,"NOACT":other}
 # Own clock and original Facts cache. Immutable source frames are not modified.
 facts=r.facts
 # Each economic arm has its own process/context; retain the original self-bound row closure.
 m,f=E.attach(r.market,facts,factors,J.C.L);r.market=m;r.facts=f
 for x in r.accounts.values():x.market=m;x.facts=f
 r.open_checks=[];r.source_freeze=dict(ORIGINAL_FREEZE)
 return r,m
def initial(r,m,window,out):
 if window=="2026Jan":
  last=single_payload_restore(r,CHECKPOINT)
  assert str(last.date())=="2025-12-31"
  ds=next(x for x in reversed(r.daily) if x["account"]=="PVR")
  assert ds["nav"]==D("981630.1103182472630")
  assert len(ds["positions"])==68 and len(ds["layers"])==90
  assert len(r.accounts["PVR"].pending)==189
 else:
  last=J.M.N.iso("2022-01-01T00:00:00+08:00")
  ds=dict(account="PVR",at=last,nav=CAPITAL,available=CAPITAL,order_reserved=Z,settlement_locked=Z,payable=Z,sale_receivable=Z,dividend_receivable=Z,inventory=Z,fees_cny=Z,positions={},layers=[],pending_sells=(),pending_intents=0)
  a=r.accounts["PVR"];assert not a.positions and not a.budget.lots and a.current_nav==CAPITAL
  save(out/"TRUE_INITIAL_EMPTY_STATE.json",dict(initial_cash=CAPITAL,stock_positions=0,stock_orders=0,stock_trades=0,industry_states=canon(a.budget.sectors),origin="Exact original run_act_only initial construction; NOT a fabricated historical checkpoint",initial_payload_sha=E.digest(E.payload(r))))
 # Both original keys were restored and checked; discard the untouched NOACT branch.
 r.accounts={"PVR":r.accounts["PVR"]}
 trimmed=trim_logs(r)
 r.assert_native_wiring()
 save(out/"INITIAL_STATE.json",dict(window=window,last_completed=last,initial_daily=ds,original_checkpoint=str(CHECKPOINT) if window=="2026Jan" else None,restoration="single verified unpickle, exact original runner/account assignments" if window=="2026Jan" else "original actual initial empty account",trim=trimmed,account_payload_sha=E.digest(E.payload(r))))
 return last,ds
def features():
 claim(O/"FEATURE_BUILD_ONCE.lock")
 start=time.monotonic();M=C.U/"STOCK_MANIFEST.json";H1=J.M.P/"h1.npz"
 cal=pd.DatetimeIndex(np.load(H1,allow_pickle=False)["dates"]);cal=cal[(cal>="2013-01-01")&(cal<="2026-01-30")]
 target=cal[((cal>="2022-01-04")&(cal<="2022-01-28"))|((cal>="2026-01-05")&(cal<="2026-01-30"))]
 assert len(target)==39
 src=R/"dmi_boundary_migration_v1/experiment.py"
 env=dict(np=np,pd=pd,N=14);nodes=[n for n in ast.parse(src.read_text()).body if isinstance(n,ast.FunctionDef) and n.name in ("calc","rma")]
 exec(compile(ast.Module(body=nodes,type_ignores=[]),str(src)+":frozen_pure_math","exec"),env);calc=env["calc"]
 inp={str(p):sha(p) for p in [M,H1,src,O/"PROTOCOL.json",Path(__file__)]};records=[];prefix=0
 for no,mm in enumerate(read(M)):
  sid=mm["symbol"];p=next(p for p in mm["source_sha256"] if p.endswith("/signal.parquet"));assert sha(p)==mm["source_sha256"][p];inp[p]=mm["source_sha256"][p]
  raw=pd.read_parquet(p).loc[:"2026-01-30"].reindex(cal)
  cols=["open","high","low","close"];valid=np.isfinite(raw[cols]).all(axis=1)&raw[cols].gt(0).all(axis=1)&raw.high.ge(raw[cols].max(axis=1))&raw.low.le(raw[cols].min(axis=1))&raw.segment_id.notna()
  for col in ["price_eligible","observed_bar","is_observed_bar"]:valid &= raw[col].fillna(False).astype(bool)
  for col in ["source_invalid","synthetic_event_bar"]:valid &= ~raw[col].fillna(True).astype(bool)
  for _,g in raw[valid].groupby("segment_id"):
   assert g.source_kind.notna().all() and g.source_path.notna().all() and g.source_kind.nunique()==g.source_path.nunique()==1,(sid,"SOURCE_IDENTITY")
  z=calc(raw,cal)
  # Every stock checked at both first/last January 2022 prefixes; selected fixed 2026 prefixes.
  cuts=["2022-01-04","2022-01-28"]
  if sid in ["000001.SZ","000060.SZ","002583.SZ","300085.SZ","300666.SZ","301611.SZ","600219.SH","601949.SH","688362.SH","688661.SH"]:cuts+=["2026-01-05","2026-01-15"]
  for cut in cuts:
   cc=cal[cal<=cut];pd.testing.assert_frame_equal(calc(raw.loc[:cut],cc),z.loc[cc],check_exact=True);prefix+=1
  records.append(pd.DataFrame(dict(sid=sid,day=target.strftime("%Y-%m-%d"),d=z.loc[target,"d"].to_numpy())))
  if (no+1)%300==0:print("DMI_FEATURES",no+1,round(time.monotonic()-start,1),flush=True)
 allf=pd.concat(records,ignore_index=True);assert len(allf)==1709*39 and not allf.duplicated(["sid","day"]).any()
 allf.to_parquet(O/"ALL_WINDOW_DMI_FEATURES.parquet",index=False)
 save(O/"FEATURE_INPUT_SHA256.json",inp)
 save(O/"FEATURE_QA.json",dict(rows=len(allf),stocks=1709,days=39,known=int(allf.d.notna().sum()),UNKNOWN=int(allf.d.isna().sum()),physical_prefix_exact=prefix,thresholds_added=0,outcomes_read=False,seconds=time.monotonic()-start))
 save(O/"FEATURE_SEAL.json",{p.name:sha(p) for p in [O/"ALL_WINDOW_DMI_FEATURES.parquet",O/"FEATURE_INPUT_SHA256.json",O/"FEATURE_QA.json"]})
 print("FEATURES_DONE",len(allf),prefix,flush=True)
def reorder(r,at,feat,audit):
 a=r.accounts["PVR"];day=str(at.date());oldints=a.pending;by={}
 for i in oldints:by.setdefault(i["sid"],[]).append(i)
 old={sid:g[0]["rank"] for sid,g in by.items()}
 assert all(len({i["rank"] for i in g})==1 for g in by.values())
 assert len(set(old.values()))==len(old)
 keys=dict(old);groups={};vals={};mutable=set()
 for sid,g in by.items():
  assert (sid,day) in feat,("MISSING_CANDIDATE_FEATURE",sid,day)
  d=feat[(sid,day)];vals[sid]=d;pv=g[0].get("PVR_score");s=a.budget.sectors.get(a.sector_by_sid[sid])
  if not a.quantity(sid) and s and s.active and pv is not None and np.isfinite(pv) and np.isfinite(d):
   group=(a.sector_by_sid[sid],tuple(sorted(i["role"] for i in g)));groups.setdefault(group,[]).append(sid);mutable.add(sid)
 for group,ids in groups.items():
  slots=sorted(old[s] for s in ids);ranked=sorted(ids,key=lambda s:(-vals[s],-by[s][0]["PVR_score"],s))
  for k,sid in zip(slots,ranked):keys[sid]=k
 assert sorted(keys.values())==sorted(old.values())
 assert all(keys[sid]==old[sid] for sid in by if sid not in mutable)
 before=canon([{k:v for k,v in i.items() if k not in ("rank","priority_rank")} for i in oldints])
 for i in a.pending+a.decisions[-1]["intents"]:
  i["rank"]=i["priority_rank"]=keys[i["sid"]]
 after=canon([{k:v for k,v in i.items() if k not in ("rank","priority_rank")} for i in oldints]);assert before==after
 # Preserve original-PVR audit rows unmodified; separate DMI audit is authoritative for final rank.
 for sid,g in by.items():audit.append(dict(day=day,sid=sid,sector=a.sector_by_sid[sid],roles=sorted(i["role"] for i in g),held=bool(a.quantity(sid)),industry_active=bool(a.budget.sectors.get(a.sector_by_sid[sid]) and a.budget.sectors[a.sector_by_sid[sid]].active),original_PVR_rank=old[sid],rank=keys[sid],PVR=g[0].get("PVR_score"),d=float(vals[sid]) if np.isfinite(vals[sid]) else None,mutable=sid in mutable))
def clock_events(m,window):
 lo,hi=WINDOWS[window];lower=J.M.N.iso(lo+"T00:00:00+08:00");upper=J.M.N.iso(hi+"T15:10:00+08:00")
 opens={x for x in m.sessions["A"] if lower<=x<=upper};closes={x for x in m.cutoffs if lower<=x<=upper}
 return opens,closes,lower,upper
def execute_event(r,m,at,opens,closes,arm,feat,audit):
 E.event(r,m,at,opens,closes,None)
 if at in closes and arm=="DMI":reorder(r,at,feat,audit)
def restore_private(r,blob):
 p=pickle.loads(blob)
 immutable={"bundle","market","facts","accounts","cp","pv","matrix","matrix_days","industry_rows","industry_cp","receipts","actions_by_date"}
 keep={k:v for k,v in vars(r).items() if k in immutable}
 r.__dict__=dict(p["runner"],**keep)
 for k,state in p["accounts"].items():
  a=r.accounts[k];market,facts=a.market,a.facts
  a.__dict__=dict(state,market=market,facts=facts)
def open_engineering_gate(r,m,at,opens,closes,arm,feat,out):
 # Repeated single event on an isolated saved state is an engineering gate,
 # not an additional retained economic path.
 blob=pickle.dumps(E.payload(r),protocol=5);before=E.digest(E.payload(r));n=len(m.exec_rows);counts=copy.copy(m.exec_counts)
 ids=set(r.accounts["PVR"].positions)|set(r.accounts["PVR"].exits)|{i["sid"] for i in r.accounts["PVR"].pending}
 if not ids:return dict(skipped="empty first OPEN; gate deferred")
 execute_event(r,m,at,opens,closes,arm,feat,[]);expected=E.digest(E.payload(r))
 restore_private(r,blob);m.exec_rows=m.exec_rows[:n];m.exec_counts=copy.copy(counts)
 backup=E.poison_future(m,at,ids);day=pd.Timestamp(at.date()).value//86400000000000
 for sid in ids:
  ar=m.arr[sid];k=np.searchsorted(ar["days"],day)
  for field in ("positive","good"):
   old=ar[field];backup.append(("array",ar,field,old));ar[field]=old[old<k].copy()
 try:
  execute_event(r,m,at,opens,closes,arm,feat,[]);assert E.digest(E.payload(r))==expected,("OPEN_FUTURE_POISON_CHANGED_STATE",at)
  assert list(m.raw[sorted(ids)[0]].columns)==["open"]
  for name,args in [("row",(sorted(ids)[0],at)),("floor",(sorted(ids)[0],at,"I")),("packet",(at,"I"))]:
   try:getattr(r.facts,name)(*args)
   except AssertionError:pass
   else:raise AssertionError(("OPEN_FUTURE_API_ALLOWED",name))
 finally:E.unpoison(backup)
 restore_private(r,blob);m.exec_rows=m.exec_rows[:n];m.exec_counts=copy.copy(counts)
 assert E.digest(E.payload(r))==before
 save(out/"OPEN_RESTART_POISON_GATE.json",dict(passed=True,at=at,stocks=len(ids),before_sha=before,event_sha=expected,official_event_not_yet_run=True,original_sources_not_written=True,engineering_repeats=2))
 return dict(passed=True)
def exact_baseline(r,out,window):
 lo,hi=WINDOWS[window];check={}
 with gzip.open(BASE/"pair/PVR.json.gz","rt") as f:old=json.load(f)
 a=r.accounts["PVR"]
 for name in ("trades","decisions","audit","journal"):
  aa=canon([x for x in getattr(a,"audit_log" if name=="audit" else name) if lo<=str(x.get("at"))[:10]<=hi])
  bb=[x for x in old[name] if lo<=x.get("at","")[:10]<=hi]
  diff=H.first_difference(aa,bb)
  if diff:save(out/"BASELINE_MISMATCH.json",dict(scope=name,diff=diff));raise AssertionError(("BASELINE_MISMATCH",name,diff))
  check[name]=len(aa)
 for file,attr,dt in [("daily","daily","at"),("opportunities","opportunities","day"),("funding","funding","at"),("industry","stage_events","day"),("balances","balance_audit","at"),("rank-policy","rank_log","day")]:
  aa=canon(getattr(r,attr));bb=[x for x in rows(BASE/"pair"/(file+".jsonl.gz")) if x["account"]=="PVR" and lo<=x[dt][:10]<=hi]
  diff=H.first_difference(aa,bb)
  if diff:save(out/"BASELINE_MISMATCH.json",dict(scope=file,diff=diff));raise AssertionError(("BASELINE_MISMATCH",file,diff))
  check[file]=len(aa)
 save(out/"BASELINE_EXACT.json",dict(passed=True,numeric_tolerance=0,IDs_unmodified=True,counts=check))
 return check

def verify_study(arm,full=True):
 frozen=read(O/"STUDY_FREEZE.json");seal=sha(O/"STUDY_FREEZE.json")
 for p,h in frozen.items():
  if full or p in [str(Path(__file__)),str(O/"PROTOCOL.json"),str(O/"ALL_WINDOW_DMI_FEATURES.parquet")]:assert sha(p)==h,("STUDY_SOURCE_CHANGED",p)
 pre=read(O/"PRELAUNCH_AUDIT.json");assert pre["passed"] and pre["study_freeze_sha256"]==seal
 if arm=="DMI":
  q=read(O/"DMI_RELEASE_AUDIT.json");assert q["passed"] and q["study_freeze_sha256"]==seal
  for w in WINDOWS:
   b=O/(w+"_PVR");assert read(b/"DONE.json")["study_freeze_sha256"]==seal
   assert q["baseline_output_seals"][w]==sha(b/"OUTPUT_SHA256.json")
  assert q["close_prefix_qa_sha256"]==sha(O/"CLOSE_PHYSICAL_PREFIX_QA.json")
 return seal

def run(window,arm):
 assert arm in ("PVR","DMI")
 study_seal=verify_study(arm)
 out=O/(window+"_"+arm);out.mkdir(exist_ok=False);claim(out/"RUN_ONCE.lock")
 start=time.monotonic();r=None;last=None;retained=0
 try:
  for n,h in read(O/"FEATURE_SEAL.json").items():assert sha(O/n)==h
  assert read(O/"PRELAUNCH_AUDIT.json")["passed"]
  if arm=="DMI":
   for w in WINDOWS:assert read(O/(w+"_PVR")/"BASELINE_EXACT.json")["passed"]
   assert read(O/"DMI_RELEASE_AUDIT.json")["passed"]
  verify_original()
  shared,receipts,cp,states,ir,identity=C.inputs()
  original_market=shared[1]
  timelines={sid:E.OpenFactorTimeline(raw,original_market.actions.get(sid,[]),method=shared[0].series[sid].record["adjustment"]["method"],end=C.END) for sid,raw in original_market.raw.items() if not raw.empty}
  factors=E.FactorSource(timelines)
  r,m=make_runner(shared,receipts,cp,states,ir,factors,window,out)
  f=pd.read_parquet(O/"ALL_WINDOW_DMI_FEATURES.parquet");feat={(x.sid,x.day):x.d for x in f.itertuples(index=False)}
  audit=[];r.source_freeze=dict(ORIGINAL_FREEZE)
  with IO.atomic_runner_outputs(r,L,out,canonicalize=canon):
   last,initial_daily=initial(r,m,window,out)
   # Own starting payload frozen after verified restoration and audited output trim.
   start_payload_sha=E.digest(E.payload(r));save(out/"STARTING_PAYLOAD_SHA.json",dict(sha256=start_payload_sha))
   if arm=="DMI":assert start_payload_sha==read(O/(window+"_PVR")/"STARTING_PAYLOAD_SHA.json")["sha256"],"ARMS_INITIAL_PAYLOAD_DIFFER"
   J.M.E.risk_policy.RECOVERY=pd.read_csv(J.M.O/"recovery.csv",index_col=0,parse_dates=True).loc[:WINDOWS[window][1]]
   opens,closes,lo,hi=clock_events(m,window)
   acts={datetime.combine(datetime.fromisoformat(d).date(),dtime.min,J.M.N.TZ) for d in r.actions_by_date}
   action_lo=J.M.N.iso("2022-01-01T00:00:00+08:00") if window=="2022Jan" else last
   events=sorted(opens|closes|{x for x in acts if (action_lo<=x if window=="2022Jan" else action_lo<x) and x<=hi})
   gate=False
   for at in events:
    verify_study(arm,full=False)
    if at in opens and not gate:
     gate_result=open_engineering_gate(r,m,at,opens,closes,arm,feat,out);gate=gate_result.get("passed",False)
    execute_event(r,m,at,opens,closes,arm,feat,audit);last=at;retained+=1
    if at in closes:print("CLOSE",window,arm,str(at.date()),str(r.accounts["PVR"].current_nav),flush=True)
   assert gate and len(r.daily)==(19 if window=="2022Jan" else 20)
   baseline=exact_baseline(r,out,window) if arm=="PVR" else None
   assert verify_study(arm)==study_seal
   r.source_freeze.update({str(p):sha(p) for p in [Path(__file__),O/"PROTOCOL.json",O/"ALL_WINDOW_DMI_FEATURES.parquet",O/"PRELAUNCH_AUDIT.json"]})
   r.checkpoint(out/"final_checkpoint",last);r.dump_joint(out/"pair")
   IO.write_gzip_jsonl(out/"DMI_RANK_AUDIT.jsonl.gz",audit,encoder=J.C.encoded)
   IO.write_gzip_jsonl(out/"OPEN_CASH_CHECKS.jsonl.gz",r.open_checks,encoder=J.C.encoded)
   IO.write_gzip_jsonl(out/"SHARED_WINDOW_AUDIT.jsonl.gz",m.exec_rows,encoder=J.C.encoded)
   end=r.daily[-1];a=r.accounts["PVR"];monthtr=[t for t in a.trades if WINDOWS[window][0]<=str(t["at"].date())<=WINDOWS[window][1]]
   save(out/"DONE.json",dict(completed=True,study_freeze_sha256=study_seal,window=window,arm=arm,last_event=last,retained_events=retained,starting_payload_sha=start_payload_sha,initial_NAV=initial_daily["nav"],ending_NAV=end["nav"],initial_fees=initial_daily["fees_cny"],final_fees=end["fees_cny"],month_fees=end["fees_cny"]-initial_daily["fees_cny"],buy_fills=sum(t["side"]=="buy" for t in monthtr),sell_fills=sum(t["side"]=="sell" for t in monthtr),days=len(r.daily),pending_end=len(a.pending),inherited_positions=len(initial_daily["positions"]),baseline=baseline,rank_rows=len(audit),seconds=time.monotonic()-start,real_orders=False,complete_round_analysis_pending=True,fixed_future_NONPIT=True,tradability_UNKNOWN=True))
  save(out/"OUTPUT_SHA256.json",{str(p.relative_to(out)):sha(p) for p in out.rglob("*") if p.is_file() and p.name!="OUTPUT_SHA256.json"})
  print("DONE",window,arm,round(time.monotonic()-start,1),flush=True)
 except BaseException as e:
  save(out/"FAILURE_NO_AUTO_RETRY.json",dict(error=repr(e),traceback=traceback.format_exc(),last_event=last,retained_events=retained,account_initialized=r is not None,no_automatic_economic_rerun=True))
  if r is not None:
   try:IO.write_pickle(out/"PARTIAL_DIAGNOSTIC_NOT_CHECKPOINT.pkl",E.payload(r))
   except BaseException:pass
  raise
def main():
 p=argparse.ArgumentParser();p.add_argument("phase",choices=["features","run"]);p.add_argument("--window",choices=list(WINDOWS));p.add_argument("--arm",choices=["PVR","DMI"]);x=p.parse_args()
 if x.phase=="features":features()
 else:assert x.window and x.arm;run(x.window,x.arm)
if __name__=="__main__":main()
