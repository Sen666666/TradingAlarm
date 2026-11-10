
import pandas as pd,numpy as np,json,hashlib,math,warnings
from pathlib import Path
warnings.filterwarnings("ignore")
R=Path("/Users/bytedance/Documents/Codex/2026-11-06/entry_state_selection_v1")
M=Path("/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/universe-cp1-inputs-20261031/STOCK_MANIFEST.json")
H=Path("/Users/bytedance/Documents/ChatGPT/money/TradingAlarm/runtime/market/update-20261030-153010-c551af/prepared/h1.npz")
OV=R/"independent_channel_full1709_preflight_v1/overlap/RECEIPT_CONDITIONAL_OVERLAP.parquet"
F=R/"price_dmi_priority_dynamic_v1/features/ALL_PRICE_RECEIPT_FEATURES.parquet"
E=R/"price_entry_mechanism_comparison_v1/ENTRY_FACTS.csv"
source_hash={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in [M,H,OV,F,E]}
manifest={x["symbol"]:x for x in json.loads(M.read_text())}
cal=pd.DatetimeIndex(np.load(H,allow_pickle=False)["dates"]);cal=cal[(cal>="2013-01-01")&(cal<="2026-05-15")]
ov=pd.read_parquet(OV,columns=["sid","day","window","born","C","S_new","root_day"])
ov=ov[ov.window.isin(["2022","2024_924"])].copy()
dm=pd.read_parquet(F,columns=["sid","day","d","dclose","raw_plus_dm","raw_minus_dm"])
entry=pd.read_csv(E,usecols=["sid","signal_day","year","common","actual_buy","born","round_id"],parse_dates=["signal_day"]).rename(columns={"signal_day":"day"})
casekeys=[("000977.SZ","2022-01-05"),("605118.SH","2022-08-22"),("605020.SH","2022-07-15"),("002174.SZ","2022-11-08"),("002031.SZ","2022-06-13"),("688660.SH","2024-09-25"),("600396.SH","2024-10-28"),("605488.SH","2024-09-30"),("002241.SZ","2024-09-30"),("600126.SH","2024-12-11"),("605099.SH","2024-12-11"),("002126.SZ","2024-12-25"),("002583.SZ","2024-09-25"),("300666.SZ","2025-12-15"),("300666.SZ","2025-12-17"),("300666.SZ","2026-01-30"),("300666.SZ","2026-02-02"),("300666.SZ","2026-02-05")]
case=pd.DataFrame(casekeys,columns=["sid","day"]);case.day=pd.to_datetime(case.day)
req=pd.concat([ov[["sid","day"]],case]).drop_duplicates()
def calc(raw):
 q=raw.reindex(cal)
 valid=np.isfinite(q[["open","high","low","close"]]).all(axis=1)&q[["open","high","low","close"]].gt(0).all(axis=1)&q.high.ge(q[["open","high","low","close"]].max(axis=1))&q.low.le(q[["open","high","low","close"]].min(axis=1))
 for c in ["price_eligible","observed_bar","is_observed_bar"]:valid &= q[c].fillna(False).astype(bool)
 for c in ["source_invalid","synthetic_event_bar"]:valid &= ~q[c].fillna(True).astype(bool)
 identity=q[["source_kind","source_path","segment_id"]];same=identity.eq(identity.shift()).all(axis=1)&identity.notna().all(axis=1)
 pair=valid&valid.shift(fill_value=False)&same
 a=(q.high-q.high.shift()).where(pair);b=(q.low.shift()-q.low).where(pair)
 tr=pd.concat([q.high-q.low,(q.high-q.close.shift()).abs(),(q.low-q.close.shift()).abs()],axis=1).max(axis=1).where(pair)
 atr=np.full(len(q),np.nan);buf=[];v=np.nan
 for i,x in enumerate(tr.to_numpy()):
  if not np.isfinite(x):buf=[];v=np.nan;continue
  if len(buf)<14:
   buf.append(x)
   if len(buf)==14:v=float(np.mean(buf));atr[i]=v
  else:v=(13*v+x)/14;atr[i]=v
 prior=pd.Series(atr,index=q.index).shift().where(pair)
 out=pd.DataFrame(dict(a=a,b=b,TR=tr,ATR_prior=prior,H=q.high,L=q.low,C_bar=q.close,raw_C=q.raw_close,raw_H=q.raw_high,raw_L=q.raw_low,factor=q.adjustment_factor,prev_H=q.high.shift().where(pair),prev_L=q.low.shift().where(pair)))
 out["outside"]=np.where(pair,(a>0)&(b>0),np.nan)
 out["B2"]=np.minimum(a.clip(lower=0),b.clip(lower=0))
 out["B2_ATR"]=out.B2/prior;out["B2_TR"]=out.B2/tr;out["TR_ATR"]=tr/prior
 out["side"]=np.where(~pair,"UNKNOWN",np.where(a>b,"HIGH",np.where(a<b,"LOW","TIE")))
 return out
parts=[];prefix_count=0
for n,(sid,g) in enumerate(req.groupby("sid",sort=True)):
 p=Path(next(k for k in manifest[sid]["source_sha256"] if k.endswith("/signal.parquet")))
 hh=hashlib.sha256(p.read_bytes()).hexdigest();assert hh==manifest[sid]["source_sha256"][str(p)];source_hash[str(p)]=hh
 raw=pd.read_parquet(p)
 z=calc(raw);part=z.reindex(g.day).reset_index(names="day");part["sid"]=sid;parts.append(part)
 cut=g.day.sort_values().iloc[len(g)//2];zp=calc(raw.loc[:cut]);pd.testing.assert_frame_equal(zp.loc[:cut],z.loc[:cut],check_exact=True);prefix_count+=1
 if (n+1)%400==0:print("READ_ONLY_PROGRESS",n+1,flush=True)
features=pd.concat(parts,ignore_index=True)
x=ov.merge(features,on=["sid","day"],validate="one_to_one").merge(dm,on=["sid","day"],validate="one_to_one")
assert len(x)==37456
assert np.allclose(x.C,x.C_bar)
x["Sdistance_ATR"]=(x.C-x.S_new)/x.ATR_prior
x["LminusS_ATR"]=(x.L-x.S_new)/x.ATR_prior
e=entry.merge(x,on=["sid","day"],suffixes=("_saved",""),how="left",validate="many_to_one")
assert e.window.notna().all()
def desc(z):
 v=z[np.isfinite(z)]
 return {"known":len(v),"p10":v.quantile(.1),"median":v.median(),"p90":v.quantile(.9)}
def group(g):
 out=g[g.outside.eq(1)];notout=g[g.outside.eq(0)]
 return dict(n=len(g),geometry_known=int(g.outside.notna().sum()),ATR_known=int(g.ATR_prior.notna().sum()),outside=len(out),outside_highwin=int(out.side.eq("HIGH").sum()),outside_lowwin=int(out.side.eq("LOW").sum()),outside_tie=int(out.side.eq("TIE").sum()),outside_dpositive=int(out.d.gt(0).sum()),outside_dclosepositive=int(out.dclose.gt(0).sum()),outside_S_at_or_above_L=int(out.LminusS_ATR.le(0).sum()),outside_stats={k:desc(out[k]) for k in ["B2_ATR","B2_TR","TR_ATR","Sdistance_ATR","LminusS_ATR"]},nonoutside_stats={k:desc(notout[k]) for k in ["TR_ATR","Sdistance_ATR","LminusS_ATR"]})
summaries=[]
for label,frame in [("ALL_RECEIPTS",x),("REGISTERED",e),("ACTUAL_BUY",e[e.actual_buy]),("COMMON_BUY",e[e.actual_buy&e.common])]:
 for w,g in frame.groupby("window"):
  summaries.append(dict(scope=label,window=w,**group(g)))
  for born,bg in g.groupby("born"):summaries.append(dict(scope=label,window=w,born=bool(born),**group(bg)))
print("SUMMARIES",json.dumps(summaries,default=str,ensure_ascii=False),flush=True)
c=case.merge(features,on=["sid","day"],validate="one_to_one").merge(ov[["sid","day","S_new","born","root_day"]],on=["sid","day"],how="left",validate="one_to_one").merge(dm,on=["sid","day"],how="left",validate="one_to_one")
c["Sdistance_ATR"]=(c.C_bar-c.S_new)/c.ATR_prior;c["LminusS_ATR"]=(c.L-c.S_new)/c.ATR_prior
cols=["sid","day","raw_C","raw_H","raw_L","outside","side","a","b","B2_ATR","B2_TR","TR_ATR","Sdistance_ATR","LminusS_ATR","d","dclose","born","root_day"]
print("CASES",c[cols].to_json(orient="records",date_format="iso",force_ascii=False),flush=True)
changed=[p for p,h in source_hash.items() if hashlib.sha256(Path(p).read_bytes()).hexdigest()!=h]
assert not changed
print("QA",json.dumps(dict(receipts=len(x),entry_rows=len(e),prefix_stock_checks=prefix_count,source_files=len(source_hash),all_source_hashes_unchanged=True,pnl_columns_loaded=False,economic_runs=0,writes=0)),flush=True)
