"""Frozen PRICE entry-generation gate. Event identity only; no economics."""
from pathlib import Path
import json,hashlib,warnings
import pandas as pd,numpy as np
warnings.filterwarnings("ignore")
R=Path("/Users/bytedance/Documents/Codex/2026-11-06/entry_state_selection_v1")
O=Path(__file__).resolve().parent
M=Path("/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/universe-cp1-inputs-20261031/STOCK_MANIFEST.json")
H=Path("/Users/bytedance/Documents/ChatGPT/money/TradingAlarm/runtime/market/update-20261030-153010-c551af/prepared/h1.npz")
OV=R/"independent_channel_full1709_preflight_v1/overlap/RECEIPT_CONDITIONAL_OVERLAP.parquet"
E=R/"price_entry_mechanism_comparison_v1/ENTRY_FACTS.csv"
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def save(name,x):(O/name).write_text(json.dumps(x,ensure_ascii=False,indent=2,default=str,allow_nan=False)+"\n")
if (O/"RUN_STARTED.json").exists():raise RuntimeError("No overwrite or repeat; inspect existing run first.")
frozen=json.loads((O/"FREEZE.json").read_text())
assert frozen["code_sha256"]==sha(__file__) and frozen["protocol_sha256"]==sha(O/"PROTOCOL.md")
save("RUN_STARTED.json",dict(code_sha256=sha(__file__),protocol_sha256=sha(O/"PROTOCOL.md"),economics=0))
sources={str(p):sha(p) for p in [M,H,OV,E]}
manifest={z["symbol"]:z for z in json.loads(M.read_text())}
cal=pd.DatetimeIndex(np.load(H,allow_pickle=False)["dates"]);cal=cal[(cal>="2013-01-01")&(cal<="2026-05-15")]
cols=["sid","day","window","born","root_day","U","C","S_old","S_new","e0_raised","e0_floor","phase","confirmed_now","old_i_buy","old_e0_target","old_i_target","old_cp_fresh","old_sector_up"]
ov=pd.read_parquet(OV,columns=cols);ov=ov[ov.window.isin(["2022","2024_924"])].copy()
entrycols=["round_id","sid","signal_day","common","actual_buy","participation","stock_gate","ticket","phase","entry_cell"]
entry=pd.read_csv(E,usecols=entrycols,parse_dates=["signal_day"]).rename(columns={"signal_day":"day"})
casekeys=[("000977.SZ","2022-01-05"),("605118.SH","2022-08-22"),("605020.SH","2022-07-15"),("002174.SZ","2022-11-08"),("002031.SZ","2022-06-13"),("688660.SH","2024-09-25"),("600396.SH","2024-10-28"),("605488.SH","2024-09-30"),("002241.SZ","2024-09-30"),("600126.SH","2024-12-11"),("605099.SH","2024-12-11"),("002126.SZ","2024-12-25"),("002583.SZ","2024-09-25")]
def run_root(c,hi,valid,ident,b,end,rootu,dates):
    active=True;u=float(rootu);gen=1;birth=b;ever=False;first=None;lastretired=None;out=[]
    assert valid[b] and np.isfinite(hi[b]) and c[b]>hi[b]
    assert np.isclose(rootu,hi[b],rtol=1e-12,atol=1e-12)
    for i in range(b,end+1):
        event="ORIGINAL_BIRTH" if i==b else "NONE"
        if not valid[i] or ident[i]!=ident[b]:raise RuntimeError("Original live root includes invalid/source-discontinuous bar")
        if i>b:
            if c[i]<=rootu:
                ever=True
                if first is None:first=dates[i]
            if active:
                if c[i]<=u:active=False;lastretired=dates[i];event="ENTRY_GENERATION_RETIRED"
            elif np.isfinite(hi[i]) and c[i]>hi[i]:
                active=True;gen+=1;u=float(hi[i]);birth=i;event="NEW_ENTRY_GENERATION"
        out.append(dict(day=dates[i],generation=gen,generation_birth=dates[birth],entry_U=u,entry_active=active,gate_status="ALLOW" if active else "DENY_ENTRY_GENERATION_INACTIVE",event=event,ever_returned_to_root_U=ever,first_return_to_root_U=first,last_generation_retired=lastretired,contemporary_prior20_high=float(hi[i]),current20_high_break=bool(c[i]>hi[i])))
    return out
rows=[];supp=[];prefix_checks=0;roots=0
sids=set(ov.sid)|{"300666.SZ"}
for no,sid in enumerate(sorted(sids)):
    p=Path(next(k for k in manifest[sid]["source_sha256"] if k.endswith("/signal.parquet")))
    assert sha(p)==manifest[sid]["source_sha256"][str(p)];sources[str(p)]=sha(p)
    q=pd.read_parquet(p).reindex(cal)
    valid=np.isfinite(q[["open","high","low","close"]]).all(axis=1)&q[["open","high","low","close"]].gt(0).all(axis=1)&q.high.ge(q[["open","high","low","close"]].max(axis=1))&q.low.le(q[["open","high","low","close"]].min(axis=1))
    for key in ["price_eligible","observed_bar","is_observed_bar"]:valid &= q[key].fillna(False).astype(bool)
    for key in ["source_invalid","synthetic_event_bar"]:valid &= ~q[key].fillna(True).astype(bool)
    ids=q[["source_kind","source_path","segment_id"]]
    idsok=ids.notna().all(axis=1);valid &= idsok
    ident=(ids.source_kind.astype(str)+"|"+ids.source_path.astype(str)+"|"+ids.segment_id.astype(str)).to_numpy()
    contiguous=(~valid|~valid.shift(fill_value=False)|~ids.eq(ids.shift()).all(axis=1)).cumsum()
    age=valid.groupby(contiguous).cumcount()
    high=q.high.rolling(20,min_periods=20).max().shift(1).where(valid&age.ge(20))
    c=q.close.to_numpy();hi=high.to_numpy();va=valid.to_numpy();dates=cal.strftime("%Y-%m-%d").to_numpy()
    for rootday,g in ov[ov.sid.eq(sid)].groupby("root_day"):
        assert g.U.nunique()==1
        b=cal.get_loc(rootday);end=cal.get_loc(g.day.max());rootu=float(g.U.iloc[0])
        rr=run_root(c,hi,va,ident,b,end,rootu,dates);z=pd.DataFrame(rr);z["sid"]=sid;z["root_day"]=rootday
        want=set(g.day.dt.strftime("%Y-%m-%d"));rows.extend(z[z.day.isin(want)].to_dict("records"));roots+=1
        cut=(b+end)//2;pre=run_root(c[:cut+1],hi[:cut+1],va[:cut+1],ident[:cut+1],b,cut,rootu,dates[:cut+1])
        assert pre==rr[:len(pre)];prefix_checks+=1
    if sid=="300666.SZ":
        b=cal.get_loc(pd.Timestamp("2025-12-15"));end=cal.get_loc(pd.Timestamp("2025-12-17"))
        rr=run_root(c,hi,va,ident,b,end,hi[b],dates)
        for z in rr:
            if z["day"] in ["2025-12-15","2025-12-17"]:supp.append(dict(sid=sid,original_root_day="2025-12-15",original_root_evidence="previously established native PRICE case, not new economic input",**z))
        for day in ["2026-01-30","2026-02-02","2026-02-05"]:
            i=cal.get_loc(pd.Timestamp(day));supp.append(dict(sid=sid,day=day,gate_status="UNKNOWN_MISSING_SOURCE" if not va[i] else "NOT_TESTED_NO_PARENT_CONTEXT",source_valid=bool(va[i])))
    if (no+1)%400==0:print("READ_ONLY_STOCKS",no+1,flush=True)
features=pd.DataFrame(rows);features.day=pd.to_datetime(features.day)
x=ov.merge(features,on=["sid","day","root_day"],how="left",validate="one_to_one")
assert len(x)==37456 and x.gate_status.notna().all()
assert x.loc[x.born,"entry_active"].all()
assert not x.loc[x.current20_high_break,"entry_active"].eq(False).any()
e=entry.merge(x,on=["sid","day"],how="left",validate="many_to_one",suffixes=("_entry",""))
assert e.gate_status.notna().all()
def counts(z):
    return dict(n=len(z),allow=int(z.entry_active.sum()),deny=int((~z.entry_active).sum()),unknown=int(z.entry_active.isna().sum()),ever_root_U_return=int(z.ever_returned_to_root_U.sum()),ever_return_but_allowed=int((z.ever_returned_to_root_U&z.entry_active).sum()),new_generation=int(z.generation.gt(1).sum()),current20break=int(z.current20_high_break.sum()),allowed_without_current20break=int((z.entry_active&~z.current20_high_break).sum()),original_birth=int(z.born.sum()),e0_raised=int(z.e0_raised.sum()),deny_e0_raised=int((~z.entry_active&z.e0_raised).sum()),deny_i_buy=int((~z.entry_active&z.old_i_buy).sum()),deny_cp_fresh=int((~z.entry_active&z.old_cp_fresh).sum()))
summary=[];inter=[]
for scope,frame in [("ALL_RECEIPTS",x),("REGISTERED",e),("ACTUAL_BUY",e[e.actual_buy]),("COMMON_BUY",e[e.actual_buy&e.common])]:
    for window,g in frame.groupby("window"):
        summary.append(dict(scope=scope,window=window,**counts(g)))
        for born,gg in g.groupby("born"):inter.append(dict(scope=scope,window=window,field="born",value=bool(born),**counts(gg)))
        if scope=="COMMON_BUY":
            for field in ["participation","stock_gate","phase","entry_cell"]:
                for k,gg in g.groupby(field):inter.append(dict(scope=scope,window=window,field=field,value=k,**counts(gg)))
cases=x.merge(pd.DataFrame(casekeys,columns=["sid","day"]).assign(day=lambda z:pd.to_datetime(z.day)),on=["sid","day"],validate="one_to_one")
x.to_parquet(O/"RECEIPT_GATE_FACTS.parquet",index=False)
e.to_csv(O/"REGISTERED_ENTRY_GATE_FACTS.csv",index=False)
cases.to_csv(O/"FIXED_CASES.csv",index=False)
save("SUPPLEMENT_2025_2026_CASES.json",supp);save("SUMMARY.json",summary);save("INTERSECTIONS.json",inter)
for p,h in sources.items():assert sha(p)==h,("SOURCE_CHANGED",p)
save("SOURCE_HASHES.json",sources)
save("QA.json",dict(receipts=len(x),registered=len(e),stocks=len(sids),root_prefix_checks=prefix_checks,original_roots=roots,source_files=len(sources),original_births_all_allowed=True,current20break_all_allowed=True,old_inputs_unchanged=True,pnl_or_future_outcome_columns_loaded=False,economic_runs=0,parameter_sweeps=0,only_entry_gate_observed=True))
save("OUTPUT_HASHES.json",{p.name:sha(p) for p in O.iterdir() if p.is_file() and p.name!="OUTPUT_HASHES.json"})
print("SUMMARY",json.dumps(summary,ensure_ascii=False),flush=True)
print("CASES",cases[["sid","day","root_day","C","U","S_old","S_new","e0_raised","entry_active","generation","generation_birth","entry_U","ever_returned_to_root_U","first_return_to_root_U","last_generation_retired","current20_high_break"]].to_json(orient="records",date_format="iso"),flush=True)
print("SUPPLEMENT",json.dumps(supp,ensure_ascii=False,default=str),flush=True)
print("QA",json.dumps(json.loads((O/"QA.json").read_text())),flush=True)
