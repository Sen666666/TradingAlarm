"""One predeclared Keltner cap on fresh CP raises. Ten anchors; no accounts.
All price units adjusted native source; next OPEN is a reference, not a fill.
"""
from pathlib import Path
import sys,json,hashlib,math
import pandas as pd
import numpy as np
HERE=Path(__file__).resolve().parent
SHARED=Path("/Users/bytedance/Documents/Codex/2026-11-04/task-3/entry_quality/channel_atr_fsm_v1")
sys.path.insert(0,str(SHARED))
import engine,runner
CASES={"000620.SZ":["2022-01-07"],"002583.SZ":["2024-09-20"],"300085.SZ":["2024-09-12","2024-10-09"],"603061.SH":["2025-12-04"],"300623.SZ":["2026-01-09"],"000029.SZ":["2022-12-01"],"002385.SZ":["2022-03-04"],"300182.SZ":["2022-01-04"],"601607.SH":["2022-03-24"]}
def save(name,x):
    (HERE/name).write_text(json.dumps(engine.clean(x),ensure_ascii=False,indent=2,allow_nan=False)+"\n")
def indicators(p,f):
    rows=[];seg=None;cl=[];tr=[];ema=None;atr=None;prev=None;prevband=None;hi=[]
    for j,t in enumerate(p.index):
        s=f.source_key.iloc[j];valid=bool(f.valid_bar.iloc[j])
        if s!=seg or not valid:
            cl=[];tr=[];hi=[];ema=atr=prev=prevband=None
        seg=s
        row=dict(day=str(t.date()),source=s,valid=valid,TR=None,ATR10=None,EMA20=None,KC_lower=None,KC_lower_prior=prevband,U20=None,ATR10_prior=atr)
        if valid:
            h,l,c=map(float,(p.high.iloc[j],p.low.iloc[j],p.close.iloc[j]))
            row["U20"]=max(hi[-20:]) if len(hi)>=20 else None
            x=h-l if prev is None else max(h-l,abs(h-prev),abs(l-prev))
            cl.append(c);tr.append(x)
            if atr is None and len(tr)==10:atr=math.fsum(tr)/10
            elif atr is not None:atr=(9*atr+x)/10
            if ema is None and len(cl)==20:ema=math.fsum(cl)/20
            elif ema is not None:ema=ema+(2/21)*(c-ema)
            band=None if ema is None or atr is None else ema-2*atr
            row.update(TR=x,ATR10=atr,EMA20=ema,KC_lower=band)
            prev=c;prevband=band;hi.append(h)
        rows.append(row)
    return pd.DataFrame(rows,index=p.index)
def shadow(pair,p,f,n,cp,ind,kind,cut=None):
    a=p.index.get_loc(pd.Timestamp(pair["anchor_day"]))
    stop=p.index.get_loc(pd.Timestamp(pair["common_end_day"]))
    if cut is not None:stop=min(stop,cut-1)
    start=p.index.get_loc(pd.Timestamp(pair["entry_reference"]["next_observation_day"]))
    E=float(pair["entry_reference"]["OPEN"]);P=float(pair["P0"]);source=f.source_key.iloc[a]
    steps=[];reason=None;exit_day=None;unknown=None;exitj=None
    for j in range(start,stop+1):
        day=str(p.index[j].date());C=float(p.close.iloc[j]);oldP=P;Q=None;cap_used=False;cand=None
        valid=bool(f.close_valid.iloc[j]);I=engine.bit(n.i_target.iloc[j]);IF=n.i_floor.iloc[j]
        fresh=engine.flag(cp.receipt.iloc[j]) is True;band=ind.KC_lower_prior.iloc[j]
        if f.source_key.iloc[j]!=source:unknown="SOURCE_INCOMPARABLE"
        elif I==0:reason="ORIGINAL_I_INVALID"
        elif valid and engine.ge(P,C):reason="EXIT_STORED_LINE"
        elif not valid:unknown="UNKNOWN_CLOSE"
        elif not bool(f.valid_bar.iloc[j]):unknown="UNKNOWN_HLC"
        elif I is None or not engine.positive(IF):unknown="UNKNOWN_I"
        else:
            Q=max(P,float(IF))
            if fresh:
                cand=cp.candidate.iloc[j]
                if not engine.positive(cand):unknown="UNKNOWN_CP_CANDIDATE"
                else:
                    effective=float(cand)
                    if kind=="KC_CAP" and C>E:
                        if engine.finite(band):
                            effective=min(effective,float(band));cap_used=effective<float(cand)
                        else:unknown="UNKNOWN_KELTNER"
                    if unknown is None:Q=max(Q,effective)
            if unknown is None:
                if engine.ge(Q,C):reason="EXIT_NEW_CP_OR_I_PROPOSAL"
                else:P=Q
        factor=float(p.close.iloc[j]/p.raw_close.iloc[j])
        step=dict(day=day,C=C,raw_C=float(p.raw_close.iloc[j]),E=E,positive_close_vs_entry=C>E,I=I,I_floor=IF,CP_receipt=fresh,CP_candidate=cand,KC_lower_prior=band,P_old=oldP,Q=Q,P_next=P if reason is None else None,cap_used=cap_used,exit_reason=reason,unknown=unknown,raw_P_old=oldP/factor,raw_Q=None if Q is None else Q/factor,raw_CP_candidate=None if cand is None else float(cand)/factor,raw_KC_lower_prior=None if not engine.finite(band) else float(band)/factor)
        steps.append(step)
        if reason:exit_day=day;exitj=j;break
        if unknown:break
    quote=None
    if exitj is not None and exitj+1<len(p):
        j=exitj+1
        if bool(f.valid_bar.iloc[j]) and f.source_key.iloc[j]==source and engine.positive(p.open.iloc[j]):
            quote=dict(day=str(p.index[j].date()),raw_OPEN=float(p.raw_open.iloc[j]),OPEN=float(p.open.iloc[j]),status="REFERENCE_ONLY_NOT_EXECUTABLE_FILL")
    return dict(sid=pair["sid"],anchor=pair["anchor_day"],kind=kind,E=E,P0=pair["P0"],exit_day=exit_day,exit_reason=reason,next_OPEN=quote,outcome="EXIT_SIGNAL" if reason else "UNKNOWN" if unknown else "RIGHT_CENSORED",steps=steps,unknown=unknown)
def main():
    freeze=HERE/"FREEZE.json";assert freeze.exists()
    code_hash=runner.sha(Path(__file__));freeze_hash=runner.sha(freeze)
    metas={x["symbol"]:x for x in json.loads(runner.MANIFEST.read_text())}
    sources={str(runner.MANIFEST):runner.sha(runner.MANIFEST)};summ=[];allshadow=[];rows=[];checks=[];casepairs=[]
    for sid,days in CASES.items():
        d,bind=runner.read_symbol(metas[sid]);sources.update(bind);p=d["price"];f=engine.features(p);n=d["facts"].reindex(p.index);cp=d["CP1"].reindex(p.index);ind=indicators(p,f)
        mask=p.index.isin(pd.to_datetime(days));pairs=engine.protection_pairs(sid,p,f,n,cp,mask,"KC_CAP_FIXED_10")
        assert len(pairs)==len(days)
        for pair in pairs:
            casepairs.append(pair)
            if pair["status"]!="PAIRED_SHADOWS":
                summ.append(dict(sid=sid,anchor=pair["anchor_day"],status=pair["status"]));continue
            a=p.index.get_loc(pd.Timestamp(pair["anchor_day"]))
            assert engine.flag(cp.receipt.iloc[a]) is True
            control=shadow(pair,p,f,n,cp,ind,"CP")
            new=shadow(pair,p,f,n,cp,ind,"KC_CAP")
            assert control["exit_day"]==pair["CP"]["exit_day"]
            assert control["exit_reason"]==pair["CP"]["exit_reason"]
            # Exact complete prefix: indicator state and shadow steps.
            for count in sorted(set([a+2,p.index.get_loc(pd.Timestamp(pair["common_end_day"]))+1])):
                short=indicators(p.iloc[:count],f.iloc[:count])
                pd.testing.assert_frame_equal(short,ind.iloc[:count],check_exact=True)
                replay=shadow(pair,p,f,n,cp,short,"KC_CAP",cut=count)
                expected=[x for x in new["steps"] if x["day"]<=str(p.index[count-1].date())]
                assert json.dumps(engine.clean(replay["steps"]),sort_keys=True)==json.dumps(engine.clean(expected),sort_keys=True)
                checks.append(dict(sid=sid,anchor=pair["anchor_day"],cut=str(p.index[count-1].date()),indicator_and_shadow_prefix_exact=True))
            for b in [control,new]:
                for step in b["steps"]:
                    assert step["P_next"] is None or step["P_next"]>=step["P_old"]
            cmap={x["day"]:x for x in control["steps"]}
            shared=[(x,cmap[x["day"]]) for x in new["steps"] if x["day"] in cmap]
            assert all(x["P_old"]<=y["P_old"]+1e-10 for x,y in shared)
            if control["exit_day"] and new["exit_day"]:assert new["exit_day"]>=control["exit_day"]
            capdays=[x["day"] for x in new["steps"] if x["cap_used"]]
            diffdays=[x["day"] for x,y in shared if x["P_old"]!=y["P_old"]]
            summ.append(dict(sid=sid,anchor=pair["anchor_day"],status=pair["status"],entry_ref=pair["entry_reference"],CP_exit=control["exit_day"],KC_exit=new["exit_day"],CP_next_OPEN=control["next_OPEN"],KC_next_OPEN=new["next_OPEN"],CP_observations=len(control["steps"]),KC_observations=len(new["steps"]),cap_days=len(capdays),first_cap_day=capdays[0] if capdays else None,first_different_oldP=diffdays[0] if diffdays else None,KC_reason=new["exit_reason"]))
            allshadow.extend([control,new])
            for b in [control,new]:
                rows.extend([dict(sid=sid,anchor=pair["anchor_day"],kind=b["kind"],**x) for x in b["steps"]])
        # Fixed display windows, not truth-selected events.
        for day in days:
            a=p.index.get_loc(pd.Timestamp(day));ix=range(max(0,a-3),min(len(p),a+16))
            out=p.iloc[list(ix)][["raw_open","raw_high","raw_low","raw_close","close"]].join(ind.iloc[list(ix)].drop(columns=["day"]))
            out.insert(0,"sid",sid);out.insert(1,"anchor",day)
            out.to_csv(HERE/(sid.replace(".","_")+"_"+day+"_INDICATORS.csv"))
    assert all(runner.sha(Path(k))==h for k,h in sources.items())
    assert code_hash==runner.sha(Path(__file__)) and freeze_hash==runner.sha(freeze)
    save("SUMMARY.json",summ);save("SHADOWS.json",allshadow);save("ORIGINAL_CP_PAIRS.json",casepairs)
    pd.DataFrame(rows).to_csv(HERE/"DAILY_SHADOWS.csv",index=False)
    save("CHECKS.json",dict(cases=sum(map(len,CASES.values())),sources=len(CASES),prefix_checks=checks,control_matches_original_CP=True,protection_monotone=True,cap_never_earlier_than_CP_on_identical_inputs=True,new_accounts=0,new_orders=0,new_quantities=0,new_returns=0,original_E0_I_CP_reruns=0,source_sha256=sources,code_sha256=code_hash,freeze_sha256=freeze_hash))
    print(json.dumps(engine.clean(summ),ensure_ascii=False))
if __name__=="__main__":main()
