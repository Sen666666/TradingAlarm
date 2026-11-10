import argparse,json,hashlib
from pathlib import Path
import numpy as np,pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from trend_price_region import region_frame
from run_competing_state import assets,volume,run,CampaignClaims,cash_check,claims_check,audit_episodes,manifest,write


def draw(f,path,title):
    fig,ax=plt.subplots(4,1,figsize=(11,8),sharex=True)
    ax[0].plot(f.index,f.close,color="black",label="signal close")
    for col in ["recent_q25","recent_q50","structure_floor"]:
        ax[0].plot(f.index,np.exp(f[col]),label=col,alpha=.75)
    ax[0].set_yscale("log");ax[0].set_title(title);ax[0].legend(fontsize=8,ncol=4)
    ax[1].bar(f.index,f.volume,color="gray")
    ax[2].plot(f.index,f.advance,label="region advance");ax[2].plot(f.index,f.entry_score,label="entry score",alpha=.6)
    ax[2].axhline(1,color="black",ls=":");ax[2].axhline(0,color="black",lw=.6);ax[2].legend()
    for col in ["target","price_target","momentum_target"]:
        ax[3].step(f.index,f[col],where="post",label=col,alpha=.7)
    ax[3].legend(ncol=3,fontsize=8);fig.tight_layout();fig.savefig(path,dpi=110);plt.close(fig)


def enriched(c,v):
    f=region_frame(c,v);f["close"]=c;f["volume"]=v
    f["price_target"]=region_frame(c,v,joint=False).target
    f["momentum_target"]=region_frame(c,v,momentum_exit=True).target
    return f


def trajectories(root,out):
    assert not (out/"validation.json").exists()
    ix=pd.bdate_range("2020-01-01",periods=230);warm=.001*np.sin(np.arange(100)*2*np.pi/10)
    common=np.r_[warm,np.arange(40)*.002,np.linspace(.078,.048,10)]
    paths={"drift":np.r_[warm,np.arange(130)*.002],"range":np.r_[warm,.03*np.sin(np.arange(130)*2*np.pi/10)],
           "jump_flat":np.r_[warm,np.full(130,.08)],"one_bar_shock":np.r_[warm,.08,np.zeros(129)],
           "recover":np.r_[common,np.linspace(.051,.20,80)],"reverse":np.r_[common,np.linspace(.045,-.15,80)],
           "drift_flat":np.r_[warm,np.arange(40)*.002,np.full(90,.078)]}
    stored={};syn=[]
    for name,y in paths.items():
        c=pd.Series(np.exp(y),index=ix);v=pd.Series(100.,index=ix);v.iloc[100:105]=800.
        a=region_frame(c,v);pd.testing.assert_frame_equal(region_frame(c.iloc[:150],v.iloc[:150]),a.iloc[:150])
        b=region_frame(c*10,v*100);np.testing.assert_allclose(a[["advance","entry_score","target"]],b[["advance","entry_score","target"]],rtol=1e-7,atol=1e-7,equal_nan=True)
        np.testing.assert_allclose(a.structure_floor+np.log(10),b.structure_floor,rtol=1e-7,atol=1e-7,equal_nan=True)
        stored[name]=a;f=enriched(c,v);f.to_csv(out/f"synthetic-{name}.csv",index_label="date");draw(f,out/f"synthetic-{name}.png",name)
        syn.append(dict(case=name,entries=int(a.entered.iloc[100:].sum()),exits=int(a.exited.iloc[100:].sum()),held=int(a.target.iloc[100:].sum()),momentum_held=int(f.momentum_target.iloc[100:].sum())))
    pd.testing.assert_frame_equal(stored["recover"].iloc[:150],stored["reverse"].iloc[:150])
    groups,_=assets();pool={s:(a["signal"].close,volume(a)) for items in groups.values() for s,a in items.items()}
    extra=root/"results/behavior-coverage-20261020"
    for key in ["S3","C3","C5"]:
        z=pd.read_csv(extra/f"{key}-full-history.csv",index_col="date",parse_dates=True)
        sym={"S3":"600919.SH","C3":"600059.SH","C5":"600917.SH"}[key];pool[sym]=(z.close,z.volume)
    panel=json.loads((root/"results/trend-behavior-panel-20261020/protocol.json").read_text())["cases"]
    panel += [dict(id=k,symbol=s,start="2024-01-01",end="2024-12-31") for k,s in [("S3","600919.SH"),("C3","600059.SH"),("C5","600917.SH")]]
    checks=[]
    for s,(c,v) in pool.items():
        f=enriched(c,v);a=region_frame(c,v);cut=len(c)//2
        pd.testing.assert_frame_equal(region_frame(c.iloc[:cut],v.iloc[:cut]),a.iloc[:cut])
        # Each surviving state's floor must never move down; an exit may record the final floor.
        seq=a.entered.cumsum()
        for _,chunk in a.loc[a.target.eq(1)].groupby(seq):
            assert chunk.structure_floor.diff().dropna().ge(-1e-12).all()
        f.to_csv(out/f"{s}-signals.csv",index_label="date")
        for case in panel:
            if case["symbol"]==s:draw(f.loc[case["start"]:case["end"]],out/f"{case['id']}-trajectory.png",case["id"]+" "+s)
        checks.append(dict(symbol=s,prefix=True,entries=int(a.entered.sum()),volume_different_days=int(f.target.ne(f.price_target).sum())))
        print("trajectory",s,flush=True)
    write(out/"validation.json",dict(synthetic=syn,real=checks,synthetic_prefix=7,real_prefix=len(checks),scale_invariance=True,common_prefix=True,floor_monotone=True))
    manifest(out,"trajectory");print(syn,flush=True)


def accounts(root,out):
    assert (out/"pre-account-review.md").exists();assert not (out/"accounts.json").exists()
    groups,_=assets();rows=[]
    for group,items in groups.items():
        for name,col in [("pv","target"),("price","price_target"),("momentum","momentum_target")]:
            signals={}
            for s,a in items.items():
                f=pd.read_csv(out/f"{s}-signals.csv",index_col="date",parse_dates=True)
                np.testing.assert_allclose(f.close,a["signal"].close,rtol=1e-12,atol=1e-12,equal_nan=True)
                signals[s]=f[col]
            scenarios=[("base",15,10,0)]+([("cost2",30,20,0),("delay1",15,10,1)] if name=="pv" else [])
            for sc,cost,fx,delay in scenarios:
                case=f"{group}-{name}-{sc}";recipients={s:groups["hk7"][s] for s in ["HK09618","HK03690"]}
                claims=CampaignClaims(items,recipients) if group=="hk7" else None
                m,path,orders,decisions=run(items,"2022-01-01","2026-10-16","score_change",cost,fx,delay,signals=signals,cadence="daily",security_claims=claims)
                check=claims_check(items,path,orders,cost,fx,recipients) if claims else cash_check(items,path,orders,cost,fx)
                ep,daily,shape=audit_episodes(items,path,orders,fx)
                assert max(check.values())<1e-6 and shape["max_daily_error"]<1e-6
                assert all(o["signal_date"]<o["date"] for o in orders)
                path.to_parquet(out/f"{case}-path.parquet")
                for suffix,content in [("orders",orders),("decisions",decisions),("episodes",ep)]:write(out/f"{case}-{suffix}.json",content)
                pd.DataFrame(daily).to_csv(out/f"{case}-daily-episodes.csv",index=False)
                rows.append(dict(case=case,**m,ledger=check,episodes=shape));write(out/"accounts.json",rows);print(case,m["total_return"],flush=True)
    manifest(out,"account")


if __name__=="__main__":
    p=argparse.ArgumentParser();p.add_argument("--root",type=Path,required=True);p.add_argument("--out",type=Path,required=True);p.add_argument("--phase",choices=["trajectories","accounts"],required=True);a=p.parse_args()
    protocol=json.loads((a.out/"protocol.json").read_text())
    assert hashlib.sha256((a.out/"protocol.json").read_bytes()).hexdigest()==json.loads((a.out/"freeze.json").read_text())["sha256"]
    for name,value in protocol["source_sha256"].items():assert hashlib.sha256(Path(__file__).with_name(name).read_bytes()).hexdigest()==value
    globals()[a.phase](a.root,a.out)
