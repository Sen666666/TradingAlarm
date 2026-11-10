"""Bounded public history acquisition only. No strategy/account."""
from pathlib import Path
from datetime import datetime,timezone
import json,hashlib,time,socket
import numpy as np,pandas as pd
import baostock as bs
R=Path(__file__).resolve().parent.parent;O=Path(__file__).resolve().parent
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def save(p,x):p.write_text(json.dumps(x,ensure_ascii=False,indent=2,default=str,allow_nan=False))
def now():return datetime.now(timezone.utc).isoformat()
def prepare():
 C=R/"opening_range_first_probe_preflight_v1/FROZEN_CASES.json"
 H=Path("/Users/bytedance/Documents/ChatGPT/money/TradingAlarm/runtime/market/update-20261030-153010-c551af/prepared/h1.npz")
 cases=json.loads(C.read_text());cal=pd.DatetimeIndex(np.load(H,allow_pickle=False)["dates"])
 assert cal.is_unique and cal.is_monotonic_increasing
 windows=[]
 for sid,day in sorted({(r["sid"],r["entry_day"]) for r in cases}):
  assert pd.Timestamp(day) in cal
  prior=[str(x.date()) for x in cal[cal<pd.Timestamp(day)][-20:]]
  assert len(prior)==20 and prior[-1]<day
  windows.append(dict(sid=sid,anchor_entry_day=day,prior_common_days=prior,start=prior[0],end=prior[-1],case_ids=[r["case_id"] for r in cases if r["sid"]==sid and r["entry_day"]==day]))
 assert len(windows)==32
 union={(w["sid"],d) for w in windows for d in w["prior_common_days"]}
 protocol=dict(scope="Exactly32 old entry-day anchors, each previous20 common sessions. Original33 contracts remain separate.",source="Existing BaoStock0.9.4 public anonymous historical endpoint, adjustflag3, unchanged fields. No paid registration or new installation.",request_budget=dict(windows=32,nominal_history_slots=640,unique_stock_days=len(union),queries=64,frequency5="960 expected labels per fully trading20-day window",daily_pairs=True,automatic_retries=0),clock="Query start/finish/retrieved UTC are current acquisition times only. Original historical available_at, period completion, auction attribution remain UNKNOWN.",calendar=dict(path=str(H),sha256=sha(H),definition="Original shared trading calendar; no per-stock replacement of suspension/missing dates."),diagnostics=dict(current_prefix="Old cached first4 provider labels through09:50 only",same_clock="For each of4 fixed labels, current reported shares / median of20 strictly earlier same-clock reported shares",prefix="Current first4 total volume / median of prior20 first4 totals",decay="(current V4/V1)/(median(V4 prior)/median(V1 prior)); diagnostic clock-profile ratio, not an entry condition",distribution="All20 raw past observations, quartiles, median, min/max and current empirical percentile retained. No threshold/sign/window chosen to separate labels."),quality="Count actual bars and provider daily tradestatus; absence does not imply suspension. Exact perbar OHLCVA checks; minute aggregates vs same-source daily and native raw separately. Nominal reported-volume and full-volume-reconciled coverage separately; no missing-as-zero or choosing19good days. Current full-day QA never used for decision-time coverage.",pit="Historical source and share-capital status are not PIT-certified. Raw shares are not shares outstanding; no assertion of turnover, aggressor flow or independent demand.",evaluation="Old labeled cases only, NOACT14 and PRICE19 separate by year. Descriptive distribution overlap only, no new returns/wins, no fitted classifier, no rule, no economic or account run.",failure="First API/error/timeout saves response/log and stops. No route changes, registration, payment or auto retry.")
 save(O/"PROTOCOL.json",protocol);save(O/"FROZEN_WINDOWS.json",windows);save(O/"INPUT_HASHES.json",{str(C):sha(C),str(H):sha(H),str(Path(__file__)):sha(Path(__file__))})
 print("PREPARED",len(windows),len(union),flush=True)
def fetch():
 assert not (O/"FETCH_ONCE.json").exists()
 save(O/"FETCH_ONCE.json",dict(started=now(),queries_max=64))
 socket.setdefaulttimeout(25);start=time.monotonic();windows=json.loads((O/"FROZEN_WINDOWS.json").read_text());log=[]
 r=bs.login();save(O/"ANONYMOUS_CONNECTION.json",dict(error_code=r.error_code,error_msg=r.error_msg,at=now()))
 if r.error_code!="0":raise RuntimeError(r.error_msg)
 try:
  for w in windows:
   sid=w["sid"];code=sid.split(".")[1].lower()+"."+sid.split(".")[0]
   for freq,fields in [("5","date,time,code,open,high,low,close,volume,amount,adjustflag"),("d","date,code,open,high,low,close,preclose,volume,amount,adjustflag,tradestatus,isST")]:
    p=O/"raw"/(sid+"_"+w["anchor_entry_day"]+"_"+freq+".json");assert not p.exists()
    started=now();clock=time.monotonic();rows=[];q=None
    try:
     q=bs.query_history_k_data_plus(code,fields,start_date=w["start"],end_date=w["end"],frequency=freq,adjustflag="3")
     while q.error_code=="0" and q.next():rows.append(q.get_row_data())
     err=q.error_code;msg=q.error_msg;names=q.fields
    except BaseException as e:err="EXCEPTION";msg=repr(e);names=fields.split(",")
    blob=dict(provider="BaoStock public anonymous existing0.9.4 SDK",sid=sid,anchor_entry_day=w["anchor_entry_day"],request_start_date=w["start"],request_end_date=w["end"],prior_common_days=w["prior_common_days"],frequency=freq,adjustflag="3",request_started_at=started,request_finished_at=now(),retrieved_at=now(),historical_available_at="UNKNOWN",error_code=err,error_msg=msg,fields=names,rows=rows)
    save(p,blob);rec=dict(sid=sid,anchor_entry_day=w["anchor_entry_day"],freq=freq,n=len(rows),start=w["start"],end=w["end"],error_code=err,path=str(p),sha256=sha(p),bytes=p.stat().st_size,seconds=time.monotonic()-clock)
    log.append(rec);save(O/"FETCH_LOG.json",log);print("FETCH",json.dumps(rec),flush=True)
    if err!="0":raise RuntimeError((sid,w["anchor_entry_day"],freq,err,msg))
    time.sleep(.2)
 finally:bs.logout()
 save(O/"FETCH_DONE.json",dict(completed=True,requests=len(log),minutes_rows=sum(x["n"] for x in log if x["freq"]=="5"),daily_rows=sum(x["n"] for x in log if x["freq"]=="d"),bytes=sum(x["bytes"] for x in log),seconds=time.monotonic()-start,ended=now(),paid=False,new_software=False,queries_after_anchor=0))
 print("FETCH_DONE",json.dumps(json.loads((O/"FETCH_DONE.json").read_text())),flush=True)
if __name__=="__main__":
 import sys
 if sys.argv[1]=="prepare":prepare()
 else:fetch()
