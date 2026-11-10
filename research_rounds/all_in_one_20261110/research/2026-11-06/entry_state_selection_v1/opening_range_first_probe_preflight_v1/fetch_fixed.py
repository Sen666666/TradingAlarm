import os,json,socket,time,hashlib,datetime
from pathlib import Path
import pandas as pd
import baostock as bs
socket.setdefaulttimeout(20)
R=Path("/Users/bytedance/Documents/Codex/2026-11-06/entry_state_selection_v1")
O=Path("/Users/bytedance/Documents/Codex/2026-11-06/entry_state_selection_v1/opening_range_first_probe_preflight_v1")
raw=O/"raw";raw.mkdir(exist_ok=True)
a=pd.read_csv(R/"mobile_first_probe_protection_v1/case_trace/CASE_SUMMARY.csv")
cases=[]
for x in a.to_dict("records"):
 cases.append(dict(case_id="NOACT|"+str(x["round_id"]),contract="NOACT_ORIGINAL_MOBILE",sid=x["sid"],name=x["name"],signal_day=x["signal_day"],entry_day=x["entry_day"],old_raw_open=float(x["buy_raw_open"]),old_pnl=float(x["first_layer_net_pnl"]),tag=x["tag"],original_initial_floor_raw=float(x["buy_price"])-float(x["entry_price_to_initial_effective_floor_per_share"])))
b=json.loads((R/"price_next_open_receipt_preflight_v1/FIXED19_INPUT_RESULT.json").read_text())["cases"]
for x in b:
 cases.append(dict(case_id="PRICE|"+x["sid"]+"|"+x["day"],contract="PRICE_FIXED_INPUT",sid=x["sid"],name=x["role"],signal_day=x["day"],entry_day=x["next_day"],old_raw_open=x["next_open_raw"],old_pnl=None,tag=x["role"],original_initial_floor_raw=None))
(O/"FROZEN_CASES.json").write_text(json.dumps(cases,ensure_ascii=False,indent=2))
pd.DataFrame(cases).to_csv(O/"FROZEN_CASES.csv",index=False)
keys=sorted({(x["sid"],x["entry_day"]) for x in cases})
log=[]
r=bs.login();print("LOGIN",r.error_code,r.error_msg,flush=True)
if r.error_code!="0": raise RuntimeError(r.error_msg)
try:
 for sid,day in keys:
  code=sid.split(".")[1].lower()+"."+sid.split(".")[0]
  for freq,fields in [("5","date,time,code,open,high,low,close,volume,amount,adjustflag"),("d","date,code,open,high,low,close,preclose,volume,amount,adjustflag,tradestatus,isST")]:
   path=raw/(sid+"_"+day+"_"+freq+".json")
   if path.exists():raise RuntimeError("Refuse duplicate fetch "+str(path))
   q=bs.query_history_k_data_plus(code,fields,start_date=day,end_date=day,frequency=freq,adjustflag="3")
   rows=[]
   while q.error_code=="0" and q.next(): rows.append(q.get_row_data())
   blob=dict(provider="BaoStock public anonymous existing SDK 0.9.4",sid=sid,day=day,frequency=freq,adjustflag="3",retrieved_at=datetime.datetime.now(datetime.timezone.utc).isoformat(),error_code=q.error_code,error_msg=q.error_msg,fields=q.fields,rows=rows)
   path.write_text(json.dumps(blob,ensure_ascii=False,indent=2))
   rec=dict(sid=sid,day=day,freq=freq,n=len(rows),error_code=q.error_code,error_msg=q.error_msg,path=str(path),sha256=hashlib.sha256(path.read_bytes()).hexdigest())
   log.append(rec); print(json.dumps(rec,ensure_ascii=False),flush=True)
   (O/"FETCH_LOG.json").write_text(json.dumps(log,ensure_ascii=False,indent=2))
   time.sleep(.15)
finally:bs.logout()
print("DONE",len(keys),len(cases),flush=True)
