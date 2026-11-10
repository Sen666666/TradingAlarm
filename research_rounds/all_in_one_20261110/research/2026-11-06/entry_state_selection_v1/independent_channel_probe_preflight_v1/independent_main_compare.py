
import ast,json,hashlib
from pathlib import Path
import numpy as np,pandas as pd
root=Path("/Users/bytedance/Documents/Codex/2026-11-06/entry_state_selection_v1")
u=Path("/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/universe-cp1-inputs-20261031")
manifest={m["symbol"]:m for m in json.loads((u/"STOCK_MANIFEST.json").read_text())}
S={}
with np.load("/Users/bytedance/Documents/ChatGPT/money/TradingAlarm/runtime/market/update-20261030-153010-c551af/prepared/h1.npz",allow_pickle=False) as h:cal=pd.DatetimeIndex(h["dates"])
cal=cal[cal<="2026-06-30"]
tree=ast.parse((root/"independent_channel_amount_preflight_v1/preflight.py").read_text())
exec(compile(ast.Module(body=[n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name in ("src","inputs")],type_ignores=[]),"<selected-read-only-functions>","exec"))
wins={"300085.SZ":["2024-09-02","2024-10-31"],"002583.SZ":["2024-09-02","2024-10-31"],"300666.SZ":["2025-12-01","2026-02-27"],"600096.SH":["2022-02-07","2022-05-31"],"300529.SZ":["2022-09-01","2022-11-30"]}
def independently(q):
    root=None;floor=np.nan;lastfailure=None;segmentstart=None;lastid=None;out=[]
    for j,(d,r) in enumerate(q.iterrows()):
        valid=bool(r.valid);fresh=valid and (segmentstart is None or r.identity!=lastid)
        if not valid or fresh:
            if root is not None:out.append(dict(day=str(d.date()),event="UNKNOWN"))
            root=None;floor=np.nan;lastfailure=None;segmentstart=j if valid else None
        lastid=r.identity if valid else None
        if not valid:continue
        if root is not None:
            if r.close<=floor:
                out.append(dict(day=str(d.date()),event="FAILURE",root=root["day"],C_raw=r.raw_close,oldS_raw=floor/r.adjustment_factor))
                root=None;floor=np.nan;lastfailure=j
            else:
                if r.e0_ready==1 and r.e0_target==1 and np.isfinite(r.e0_floor) and 0<r.e0_floor<r.close:floor=max(floor,r.e0_floor)
                closeF=float(np.log(r.close/root["ca"]))
                delta=max(0,closeF-root["F"])
                if delta>0:
                    root["F"]=closeF
                    if not bool(r.amount_valid):root["Q"]=np.nan
                    else:root["Q"]+=min(1,np.sqrt(r.amount/root["B"]))*delta
                    oldconf=root["confirmed"]
                    root["confirmed"]=bool(root["Q"]>=root["R"])
                    out.append(dict(day=str(d.date()),event="RECEIPT",root=root["day"],C_raw=r.raw_close,Q=root["Q"],R=root["R"],confirmed=root["confirmed"],became_confirmed=root["confirmed"] and not oldconf,E0=r.e0_target,I=r.i_target,S_raw=floor/r.adjustment_factor))
            continue
        if j-segmentstart<20:continue
        U=float(q.high.iloc[j-20:j].max())
        if r.close<=U:continue
        start=max(j-20,lastfailure if lastfailure is not None else segmentstart)
        hist=q.close.iloc[start:j].to_numpy(float);a=start+np.flatnonzero(hist==hist.min())[-1]
        B=float(q.amount.iloc[a-21:a].median()) if a-segmentstart>=21 and q.amount_valid.iloc[a-21:a].all() else np.nan
        ca=float(q.close.iloc[a]);R=float(np.log(U/ca));F=0.;Q=0. if np.isfinite(B) else np.nan
        for k in range(a+1,j+1):
            v=float(np.log(q.close.iloc[k]/ca));delta=max(0,v-F)
            if delta>0:
                if not bool(q.amount_valid.iloc[k]):Q=np.nan
                else:Q+=min(1,np.sqrt(q.amount.iloc[k]/B))*delta
                F=v
        floor=float(q.low.iloc[a:j+1].min())
        root=dict(day=str(d.date()),a=str(q.index[a].date()),ca=ca,B=B,F=F,Q=Q,R=R,confirmed=bool(Q>=R))
        out.append(dict(day=str(d.date()),event="BIRTH",root=root["day"],a=root["a"],C_raw=r.raw_close,U_raw=U/r.adjustment_factor,Q=Q,R=R,confirmed=root["confirmed"],E0=r.e0_target,I=r.i_target,S_raw=floor/r.adjustment_factor))
    return out

audit_dir=root/"independent_channel_probe_preflight_v1"
main=pd.read_csv(audit_dir/"FIXED_DAILY.csv",parse_dates=["day","root_day","a_day","confirmed_at"])
allchecks=[]
for sid,(a,b) in wins.items():
    q=inputs(sid)
    q["amount_valid"]=np.isfinite(q.amount)&q.amount.gt(0)&np.isfinite(q.raw_volume)&q.raw_volume.gt(0)&q.volume_eligible.fillna(False).astype(bool)
    q["valid"]=q.coordinate_valid.copy()
    for c in ["open","high","low","close"]:q["valid"]&=np.isfinite(q[c])&q[c].gt(0)
    for c in ["price_eligible","observed_bar","is_observed_bar"]:q["valid"]&=q[c].fillna(False).astype(bool)
    for c in ["source_invalid","synthetic_event_bar"]:q["valid"]&=~q[c].fillna(True).astype(bool)
    q["valid"]&=q.low.le(q.close)&q.close.le(q.high)&q.identity.notna()
    allref=independently(q);ref=[v for v in allref if a<=v["day"]<=b]
    x=main[main.sid==sid].set_index("day")
    observed=x[x.born|x.receipt|x.failed|x.root_unknown]
    assert len(ref)==len(observed)
    for ev,(d,v) in zip(ref,observed.iterrows()):
        assert ev["day"]==str(d.date())
        typ="BIRTH" if v.born else "RECEIPT" if v.receipt else "FAILURE" if v.failed else "UNKNOWN"
        assert ev["event"]==typ
        if typ=="UNKNOWN":continue
        assert ev["root"]==str(v.root_day.date())
        fac=float(q.loc[d,"adjustment_factor"])
        if typ=="FAILURE":assert np.isclose(ev["oldS_raw"],v.S_old/fac,rtol=0,atol=1e-12)
        else:
            assert np.isclose(ev["Q"],v.Q,rtol=0,atol=1e-12,equal_nan=True)
            assert np.isclose(ev["R"],v.R,rtol=0,atol=1e-12,equal_nan=True)
            assert ev["confirmed"]==(v.phase=="CONFIRMED")
            assert np.isclose(ev["S_raw"],v.S_new/fac,rtol=0,atol=1e-12)
    births={ev["day"]:ev for ev in allref if ev["event"]=="BIRTH"}
    Sref=np.nan;lastid=None;dailychecked=0
    for d,r in q.iterrows():
        old=Sref;raised=False;failed=False
        if not r.valid or (lastid is not None and r.identity!=lastid):Sref=np.nan
        elif np.isfinite(Sref):
            if r.close<=Sref:failed=True;Sref=np.nan
            elif r.e0_ready==1 and r.e0_target==1 and np.isfinite(r.e0_floor) and 0<r.e0_floor<r.close:
                Sref=max(Sref,float(r.e0_floor));raised=Sref>old
        lastid=r.identity if r.valid else None
        e=births.get(str(d.date()))
        if e is not None:Sref=float(q.low.loc[e["a"]:e["day"]].min())
        if d in x.index:
            z=x.loc[d]
            assert np.isclose(Sref,z.S_new,rtol=0,atol=1e-12,equal_nan=True),(sid,d,Sref,z.S_new)
            assert raised==bool(z.e0_raised),(sid,d,raised,z.e0_raised)
            assert failed==bool(z.failed)
            dailychecked+=1
    allchecks.append(dict(sid=sid,main_events_match=len(ref),all_daily_protection_values_match=dailychecked,births=int(x.born.sum()),receipts=int(x.receipt.sum()),failed=int(x.failed.sum()),unknown=int(x.root_unknown.sum())))
frozen=json.loads((audit_dir/"SOURCE_HASHES.json").read_text())
assert all(hashlib.sha256(Path(p).read_bytes()).hexdigest()==h for p,h in frozen.items())
run=json.loads((audit_dir/"RUN_ONCE.json").read_text())
assert all(hashlib.sha256(Path(p).read_bytes()).hexdigest()==h for p,h in run["precompute_sources"].items())
print(json.dumps({"checks":allchecks,"total_daily_rows":len(main),"frozen_sources":len(frozen),"all_frozen_source_hashes_match":True,"precompute_source_hashes_match":True,"core_sha256":hashlib.sha256((audit_dir/"core.py").read_bytes()).hexdigest()}))
