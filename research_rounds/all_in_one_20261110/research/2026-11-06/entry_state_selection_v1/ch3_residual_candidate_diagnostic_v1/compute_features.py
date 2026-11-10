"""Frozen CH3 candidate-only retrospective diagnostic. No payoff labels or economic engine."""
from pathlib import Path
import io,sys,subprocess,hashlib,json,datetime
import numpy as np
import pandas as pd
O=Path(__file__).resolve().parent
R=O.parent
E=R/"m3_stock_birth_during_sector_v1"
S={}
def sha(b):return hashlib.sha256(b).hexdigest()
def source(p):
    p=Path(p);b=p.read_bytes();S[str(p)]=sha(b);return b
def dump(name,obj):
    (O/name).write_text(json.dumps(obj,ensure_ascii=False,indent=2,allow_nan=False)+"\n")
spec=json.loads(source(O/"SPECIFICATION_FREEZE.json"))
url=spec["factor"]["url"]
fpath=O/"CH3_factors_monthly_202608.xlsx"
if fpath.exists():b=fpath.read_bytes()
else:
    b=subprocess.check_output(["/usr/bin/curl","--fail","--connect-timeout","10","--max-time","60","-sSL",url])
    assert sha(b)==spec["factor"]["sha256"]
    fpath.write_bytes(b)
assert sha(b)==spec["factor"]["sha256"]
S[str(fpath)]=sha(b)
f=pd.read_excel(io.BytesIO(b),sheet_name="Returnseries")
f.index=pd.to_datetime(f.pop("mnthdt").astype(str),format="%Y%m%d").dt.to_period("M")
f=f.apply(pd.to_numeric).sort_index()
assert f.index.equals(pd.period_range("2000-01","2026-08",freq="M"))
assert f.index.is_unique and np.isfinite(f.to_numpy()).all()
f.to_csv(O/"OFFICIAL_CH3_DECIMAL.csv",index_label="month")
dpaths=[E/"relative_priority_equity_run_2022_v1/dynamic/DECISIONS.csv",E/"cash_equity_baseline_2024_v1/economic/DECISIONS.csv"]
d=pd.concat([pd.read_csv(io.BytesIO(source(p)),low_memory=False) for p in dpaths],ignore_index=True)
q=d[d.arm.eq("A_UNION_B")&d.window.astype(str).isin(["2022","2024_924"])&d.decision.isin(["SELECTED_PENDING","PASS_NOT_TOP2"])].copy()
q["window"]=q.window.astype(str)
q=q.sort_values(["window","day","sector","queue_rank","sid"]).reset_index(drop=True)
assert len(q)==9233 and q.close_check.eq("PASS").all() and q.I_qualified.all() and q.PVR_known.all()
assert not q.duplicated(["window","event_id"]).any()
assert q.groupby("window").size().to_dict()=={"2022":5728,"2024_924":3505}
assert q.groupby("window").selected.sum().to_dict()=={"2022":2732,"2024_924":1354}
assert q.stock_state_before.eq("FLAT").all()
q["month"]=pd.to_datetime(q.day).dt.to_period("M").astype(str)
q["source_queue_rank"]=q.queue_rank.astype(int)
q["old_rank"]=q.groupby(["window","day","sector"],sort=False).cumcount()+1
q["old_selected"]=q.selected.astype(bool)
q.to_csv(O/"ORIGINAL_LEGAL_CANDIDATES_PRELABEL.csv",index=False)
mp=Path("/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/universe-cp1-inputs-20261031/STOCK_MANIFEST.json")
manifest={x["symbol"]:x for x in json.loads(source(mp))}
hp=Path("/Users/bytedance/Documents/ChatGPT/money/TradingAlarm/runtime/market/update-20261030-153010-c551af/prepared/h1.npz")
with np.load(io.BytesIO(source(hp)),allow_pickle=False) as h:cal=pd.DatetimeIndex(h["dates"])
cal=pd.DatetimeIndex(sorted(cal.unique()))
lastday=pd.Series(cal,index=cal.to_period("M")).groupby(level=0).max()
def calc(p,ff,day):
    month=pd.Period(day,freq="M")
    months=pd.period_range(month-36,month-1,freq="M")
    epmonths=pd.period_range(month-37,month-1,freq="M")
    r={"fit_first":str(months[0]),"fit_last":str(months[-1]),"formation_first":str(month-12),"formation_last":str(month-2),
       "historical_release_known":False,"fit_n_required":36}
    endpoints=lastday.reindex(epmonths)
    if endpoints.isna().any():return dict(r,status="UNKNOWN_CALENDAR")
    if not months.isin(ff.index).all():return dict(r,status="UNKNOWN_FACTOR_MONTH")
    ix=pd.DatetimeIndex(endpoints.to_numpy());a=p.reindex(ix)
    r.update(endpoint_first=str(ix[0].date()),endpoint_last=str(ix[-1].date()),missing_endpoint_count=int(a.close.isna().sum()))
    if a.close.isna().any():return dict(r,status="UNKNOWN_MONTH_END_PRICE")
    vals=a[["close","raw_close","adjustment_factor"]].to_numpy(float)
    if not (np.isfinite(vals).all() and (vals>0).all()):return dict(r,status="UNKNOWN_PRICE_OR_FACTOR")
    for col in ["observed_bar","price_eligible"]:
        if not a[col].eq(True).all():return dict(r,status="UNKNOWN_ENDPOINT_"+col)
    for col in ["source_invalid","synthetic_event_bar"]:
        if not a[col].eq(False).all():return dict(r,status="UNKNOWN_ENDPOINT_"+col)
    if not np.allclose(a.raw_close*a.adjustment_factor,a.close,rtol=1e-9,atol=1e-9):return dict(r,status="UNKNOWN_COORDINATE")
    span=p.loc[ix[0]:ix[-1]]
    for col in ["source_kind","source_path","segment_id"]:
        if a[col].isna().any() or span[col].isna().any() or span[col].nunique()!=1:return dict(r,status="UNKNOWN_SOURCE_SEGMENT")
    returns=a.close.to_numpy()[1:]/a.close.to_numpy()[:-1]-1
    fm=ff.loc[months];X=np.column_stack([np.ones(36),fm[["mktrf","SMB","VMG"]].to_numpy()])
    y=returns-fm.rf_mon.to_numpy()
    coef,_,rank,_=np.linalg.lstsq(X,y,rcond=None)
    if rank!=4:return dict(r,status="UNKNOWN_RANK")
    eps=y-X@coef;at=(months>=month-12)&(months<=month-2);assert at.sum()==11
    er=eps[at];sd=float(np.std(er,ddof=1))
    numeric_tol=float(np.finfo(float).eps*max(X.shape)*(np.linalg.norm(y)+np.linalg.norm(X)*np.linalg.norm(coef)))
    r["residual_numerical_tolerance"]=numeric_tol
    if not np.isfinite(sd) or sd<=numeric_tol:return dict(r,status="UNKNOWN_NUMERICAL_RESIDUAL_SCALE")
    raw=returns[at];excess=y[at];esd=float(np.std(excess,ddof=1))
    r.update(status="CALENDAR_COMPUTABLE_RELEASE_UNKNOWN",RM=float(np.mean(er)/sd),
        RAW_MOM11=float(np.prod(1+raw)-1),RAW_EXCESS_STANDARDIZED=float(np.mean(excess)/esd) if esd>0 else None,
        fit_n=36,formation_n=11,alpha=float(coef[0]),beta_market=float(coef[1]),beta_size=float(coef[2]),beta_value=float(coef[3]),
        residual_mean=float(np.mean(er)),residual_sd=sd,design_condition=float(np.linalg.cond(X)),max_input_date=str(ix[-1].date()))
    return r
if __name__=="__main__":
    rows=[];prefix=[];paths={}
    for j,(sid,g) in enumerate(q.groupby("sid",sort=True)):
        m=manifest[sid];sp=next(p for p in m["source_sha256"] if p.endswith("/signal.parquet"))
        bb=source(sp);assert sha(bb)==m["source_sha256"][sp];paths[sid]=sp
        p=pd.read_parquet(io.BytesIO(bb)).sort_index()
        for month,mm in g.groupby("month",sort=True):
            day=pd.Timestamp(mm.day.min());r=calc(p,f,day)
            pre=calc(p.loc[p.index<=day],f.loc[f.index<day.to_period("M")],day)
            assert r==pre,(sid,month,"prefix")
            altered=p.copy();altered.loc[altered.index>day,"close"]*=17
            ff=f.copy();ff.loc[ff.index>=day.to_period("M"),:]=999
            assert r==calc(altered,ff,day),(sid,month,"future")
            rows.append(dict(sid=sid,month=month,first_signal_day=str(day.date()),**r))
            prefix.append(dict(sid=sid,month=month,first_signal_day=str(day.date()),prefix_equal=True,future_perturbation_equal=True))
        if (j+1)%200==0:print("STOCKS",j+1,"STOCK_MONTHS",len(rows),flush=True)
    feat=pd.DataFrame(rows)
    assert not feat.duplicated(["sid","month"]).any()
    feat.to_csv(O/"STOCK_MONTH_FEATURES_PRELABEL.csv",index=False)
    pd.DataFrame(prefix).to_csv(O/"PREFIX_AND_PERTURBATION_QA.csv",index=False)
    out=q.merge(feat,on=["sid","month"],how="left",validate="many_to_one")
    assert len(out)==len(q) and out.status.notna().all()
    out["known"]=out.status.eq("CALENDAR_COMPUTABLE_RELEASE_UNKNOWN")
    queues=[]
    for key,g in out.groupby(["window","day","sector"],sort=True):
        g=g.sort_values("old_rank")
        assert g.old_rank.tolist()==list(range(1,len(g)+1))
        K=int(g.old_selected.sum());assert K==min(2,len(g))
        assert g.old_selected.equals(g.old_rank.le(K))
        assert g.sort_values(["PVR_score","sid"],ascending=[False,True]).sid.tolist()==g.sid.tolist()
        pos=g.loc[g.known,"old_rank"].tolist()
        for name in ["RM","RAW_MOM11"]:
            ranked=g.loc[g.known].sort_values([name,"PVR_score","sid"],ascending=[False,False,True])
            mapping=dict(zip(ranked.sid,pos))
            nr=pd.Series([mapping.get(sid,rank) for sid,rank in zip(g.sid,g.old_rank)],index=g.index)
            sel=nr.le(K)
            out.loc[g.index,name+"_rank"]=nr
            out.loc[g.index,name+"_selected"]=sel
            assert nr[~g.known].equals(g.loc[~g.known,"old_rank"])
            assert sel.sum()==K
        a=set(g.loc[g.old_selected,"sid"])
        b=set(out.loc[g.index].loc[out.loc[g.index,"RM_selected"].eq(True),"sid"])
        c=set(out.loc[g.index].loc[out.loc[g.index,"RAW_MOM11_selected"].eq(True),"sid"])
        queues.append(dict(window=key[0],day=key[1],sector=key[2],industry=g.industry.iloc[0],N=len(g),K=K,
            known=int(g.known.sum()),unknown=int((~g.known).sum()),competing=len(g)>K,
            RM_replacements=len(b-a),RAW_MOM11_replacements=len(c-a),RM_vs_RAW_different_members=len(b-c),
            RM_unique_new_vs_PVR_and_RAW=len(b-a-c),original_picks="|".join(sorted(a)),RM_picks="|".join(sorted(b)),RAW_MOM11_picks="|".join(sorted(c))))
    oq=pd.DataFrame(queues)
    out.to_csv(O/"CANDIDATE_RANKS_PRELABEL.csv",index=False)
    out.to_parquet(O/"CANDIDATE_RANKS_PRELABEL.parquet",index=False)
    oq.to_csv(O/"QUEUE_CHANGES_PRELABEL.csv",index=False)
    sums=[]
    for w,g in out.groupby("window",sort=True):
        qq=oq[oq.window.eq(w)];k=g[g.known]
        def corr(a,b):return float(k[a].rank().corr(k[b].rank())) if len(k)>1 else None
        sums.append(dict(window=w,candidates=len(g),stocks=g.sid.nunique(),stock_months=len(g[["sid","month"]].drop_duplicates()),
            selected=int(g.old_selected.sum()),known=int(g.known.sum()),unknown=int((~g.known).sum()),
            selected_known=int((g.old_selected&g.known).sum()),selected_unknown=int((g.old_selected&~g.known).sum()),
            queues=len(qq),competing_queues=int(qq.competing.sum()),queues_with_2plus_known=int(qq.known.ge(2).sum()),
            RM_changed_queues=int(qq.RM_replacements.gt(0).sum()),RM_replaced_slots=int(qq.RM_replacements.sum()),
            RAW_changed_queues=int(qq.RAW_MOM11_replacements.gt(0).sum()),RAW_replaced_slots=int(qq.RAW_MOM11_replacements.sum()),
            RM_vs_RAW_changed_queues=int(qq.RM_vs_RAW_different_members.gt(0).sum()),RM_vs_RAW_different_slots=int(qq.RM_vs_RAW_different_members.sum()),
            RM_unique_new_vs_both=int(qq.RM_unique_new_vs_PVR_and_RAW.sum()),
            spearman_RM_RAW_MOM11=corr("RM","RAW_MOM11"),spearman_RM_PVR=corr("RM","PVR_score"),
            spearman_RM_RAW_standardized=corr("RM","RAW_EXCESS_STANDARDIZED"),
            status_counts=g.status.value_counts().to_dict()))
    dump("COVERAGE_AND_QUEUE_SUMMARY_PRELABEL.json",sums)
    out.groupby(["window","month","status"]).agg(candidates=("sid","size"),selected=("old_selected","sum")).reset_index().to_csv(O/"MONTHLY_COVERAGE_PRELABEL.csv",index=False)
    # Preserve deterministic named examples for later independent physical prefix review.
    audit=[]
    for w,g in out.groupby("window",sort=True):
        for known,h in g.groupby("known",sort=True):
            audit.extend(h.sort_values(["day","sid"]).drop_duplicates("sid").head(3)[["window","day","sid","month","status"]].to_dict("records"))
    pd.DataFrame(audit).to_csv(O/"DETERMINISTIC_AUDIT_CASES.csv",index=False)
    dump("STOCK_SOURCE_PATHS.json",paths)
    source(Path(__file__))
    dump("SOURCE_HASHES_PRELABEL.json",S)
    dump("QA_PRELABEL.json",dict(factor_sha256=sha(fpath.read_bytes()),factor_months=len(f),factor_start=str(f.index.min()),factor_end=str(f.index.max()),
        candidates=len(out),queues=len(oq),stock_month_features=len(feat),prefix_checks=len(prefix),future_perturbation_checks=len(prefix),
        original_slots_kept=True,unknown_slots_kept=True,same_K=True,all_original_selected_are_top_K=True,
        no_payoff_labels_loaded=True,no_economic_engine_called=True,no_orders=True,no_fast_rows=True,not_PIT=True,
        native_close_proxy_not_certified_total_return=True,source_files_verified=len(paths)))
    seal={}
    for p in sorted(O.iterdir()):
        if p.is_file() and p.name!="FEATURE_SEAL.json":seal[p.name]=sha(p.read_bytes())
    dump("FEATURE_SEAL.json",dict(sealed_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),files=seal))
    print(json.dumps(sums,ensure_ascii=False,indent=2))
