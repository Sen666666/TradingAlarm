from pathlib import Path
import json,hashlib
import pandas as pd
R=Path("/Users/bytedance/Documents/Codex/2026-11-06/entry_state_selection_v1");O=R/"price_wide_structure_preflight_v1"
P=R/"independent_channel_full1709_preflight_v1/overlap/RECEIPT_CONDITIONAL_OVERLAP.parquet";W=O/"WIDE_STATES.parquet"
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
h={str(p):sha(p) for p in [P,W,O/"full2862_static_v1/PROTOCOL.json",Path(__file__)]}
cols=["day","receipt","born","failed","root_day","active","phase","S_old","S_new"]
old=pd.read_parquet(P,columns=["sid"]+cols)
w=pd.read_parquet(W);out=[];q=[]
for sid,s in [("002174.SZ","2022-06-06"),("605118.SH","2022-08-22"),("605099.SH","2024-12-11")]:
 p=R/"price_entry_generation_dynamic_v1/market_tape"/(sid+".parquet");h[str(p)]=sha(p);d=pd.read_parquet(p,columns=cols);d["day"]=pd.to_datetime(d.day)
 check=old[old.sid.eq(sid)].drop(columns="sid").merge(d,on="day",suffixes=("_receipt","_tape"),validate="one_to_one")
 for c in ["receipt","born","failed","root_day","active","phase"]:
  a=check[c+"_receipt"];b=check[c+"_tape"];assert (a.eq(b)|(a.isna()&b.isna())).all(),(sid,c)
 d=d[d.day.ge(s)]
 z=d.merge(w[w.sid.eq(sid)][["day","ready","target","birth"]],on="day",how="left",validate="one_to_one")
 assert z.iloc[0].day==pd.Timestamp(s) and z.iloc[0].receipt
 fail=z[z.failed].head(1);end=fail.day.iloc[0] if len(fail) else z.day.max();v=z[z.day.le(end)&(z.receipt|z.failed)].copy();v["sid"]=sid;v["initial_rejected_signal"]=s;v["scope"]="SAVED_MARKET_EVENTS_NOT_NEW_POLICY_ORDERS";out.append(v)
 q.append(dict(sid=sid,shared_original_receipt_rows_checked=len(check),initial_signal=s,first_original_root_failure=str(end.date()),later_same_root_wide_pass=str(v.loc[v.receipt&v.ready&v.target,"day"].min().date()) if (v.receipt&v.ready&v.target).any() else None))
pd.concat(out).to_csv(O/"THREE_REJECTED_RECEIPT_CONTINUATIONS.csv",index=False)
assert all(sha(p)==v for p,v in h.items())
(O/"CONTINUATION_QA.json").write_text(json.dumps({"scope":"Original market receipts until first root failure; no new path order, fill or PnL","checks":q,"source_hashes":h},ensure_ascii=False,indent=2)+"\n")
print(json.dumps(q,ensure_ascii=False))
