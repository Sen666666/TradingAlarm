"""Read-only ex ante attribution, frozen after results; no consumer or economics."""
from pathlib import Path
import json,hashlib,io
import numpy as np,pandas as pd
O=Path(__file__).resolve().parent;P=O.parent;L=P/"lifecycle_comparison_v1";R=P.parent
U=Path("/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/universe-cp1-inputs-20261031")
S={}
def sha(b):return hashlib.sha256(b).hexdigest()
def src(p):p=Path(p);b=p.read_bytes();S[str(p)]=sha(b);return b
def dump(n,x):(O/n).write_text(json.dumps(x,ensure_ascii=False,indent=2,allow_nan=False)+"\n")
seal=json.loads(src(L/"FEATURE_SEAL.json"))
for n,h in seal["files"].items():assert sha((L/n).read_bytes())==h,n
f=pd.read_excel(io.BytesIO(src(P/"CH3_factors_monthly_202608.xlsx")),sheet_name="Returnseries")
f.index=pd.to_datetime(f.pop("mnthdt").astype(str),format="%Y%m%d").dt.to_period("M")
known=pd.read_csv(io.BytesIO(src(L/"ALL_MARKET_STOCK_MONTH_FEATURES.csv")),float_precision="round_trip")
events=pd.read_csv(io.BytesIO(src(L/"ALL_MARKET_EVENT_KEYS.csv")))
mapping=events[["sid","sector"]].drop_duplicates();assert not mapping.sid.duplicated().any();mapping=mapping.set_index("sid").sector.to_dict()
sm={x["symbol"]:x for x in json.loads(src(U/"STOCK_MANIFEST.json"))}
im={x["series"]:x for x in json.loads(src(U/"INDUSTRY_MANIFEST.json"))}
hp=Path("/Users/bytedance/Documents/ChatGPT/money/TradingAlarm/runtime/market/update-20261030-153010-c551af/prepared/h1.npz")
with np.load(io.BytesIO(src(hp)),allow_pickle=False) as h:cal=pd.DatetimeIndex(sorted(pd.DatetimeIndex(h["dates"]).unique()))
lastday=pd.Series(cal,index=cal.to_period("M")).groupby(level=0).max()
ind={}
for sec in sorted(set(mapping.values())):
    m=im[sec];p=next(p for p in m["source_sha256"] if p.endswith("/signal.parquet"));b=src(p)
    assert sha(b)==m["source_sha256"][p];ind[sec]=pd.read_parquet(io.BytesIO(b)).sort_index()
def industry_returns(p,ix):
    a=p.reindex(ix)
    if a.close.isna().any():return "UNKNOWN_INDUSTRY_ENDPOINT",None
    vals=a[["close","raw_close","adjustment_factor"]].to_numpy(float)
    if not(np.isfinite(vals).all() and (vals>0).all()):return "UNKNOWN_INDUSTRY_PRICE",None
    for c in ["observed_bar","price_eligible"]:
        if not a[c].eq(True).all():return "UNKNOWN_INDUSTRY_"+c,None
    for c in ["source_invalid","synthetic_event_bar"]:
        if not a[c].eq(False).all():return "UNKNOWN_INDUSTRY_"+c,None
    if not np.allclose(a.close,a.raw_close*a.adjustment_factor,rtol=1e-9,atol=1e-9):return "UNKNOWN_INDUSTRY_COORDINATE",None
    span=p.loc[ix[0]:ix[-1]]
    if any(span[c].isna().any() or span[c].nunique()!=1 for c in ["source_kind","source_path","segment_id"]):return "UNKNOWN_INDUSTRY_SOURCE",None
    return "KNOWN",a.close.to_numpy()[1:]/a.close.to_numpy()[:-1]-1
rows=[];maxerr=0;prefixchecks=0;tested=set()
for j,(sid,g) in enumerate(known.groupby("sid",sort=True)):
    m=sm[sid];p=next(p for p in m["source_sha256"] if p.endswith("/signal.parquet"));b=src(p)
    assert sha(b)==m["source_sha256"][p];p=pd.read_parquet(io.BytesIO(b)).sort_index();sec=mapping[sid]
    for rr in g.to_dict("records"):
        out={k:rr[k] for k in ["sid","month","status","RM","RAW_MOM11","RAW_EXCESS_STANDARDIZED","alpha","beta_market","beta_size","beta_value","residual_sd"]}
        out["sector"]=sec
        if rr["status"]!="CALENDAR_COMPUTABLE_RELEASE_UNKNOWN":
            out["industry_status"]="STOCK_FEATURE_UNKNOWN";rows.append(out);continue
        mo=pd.Period(rr["month"]);ms=pd.period_range(mo-36,mo-1,freq="M")
        ix=pd.DatetimeIndex(lastday.reindex(pd.period_range(mo-37,mo-1,freq="M")).to_numpy())
        assert str(ix[-1].date())==rr["max_input_date"]
        a=p.reindex(ix);ret=a.close.to_numpy()[1:]/a.close.to_numpy()[:-1]-1
        fac=f.loc[ms];y=ret-fac.rf_mon.to_numpy();ys=y[24:35];sy=float(np.std(ys,ddof=1));se=rr["residual_sd"]
        assert sy>0
        beta=np.array([rr["beta_market"],rr["beta_size"],rr["beta_value"]])
        fm=fac[["mktrf","SMB","VMG"]].iloc[24:35].mean().to_numpy()
        mean=float(np.mean(ys));norm=mean*(1/se-1/sy);alpha=-rr["alpha"]/se;ct=-beta*fm/se
        reconstructed=mean/sy+norm+alpha+sum(ct)
        err=abs(reconstructed-rr["RM"]);maxerr=max(maxerr,err);assert err<1e-10
        assert abs(mean/sy-rr["RAW_EXCESS_STANDARDIZED"])<1e-10
        assert abs(np.prod(1+ret[24:35])-1-rr["RAW_MOM11"])<1e-10
        out.update(raw_vol36=float(np.std(ret,ddof=1)),raw_vol11=float(np.std(ret[24:35],ddof=1)),
            raw_excess_mean11=mean,raw_excess_sd11=sy,normalization_component=norm,alpha_component=alpha,
            market_component=float(ct[0]),size_component=float(ct[1]),value_component=float(ct[2]),
            score_minus_raw_standardized=rr["RM"]-mean/sy,score_identity_error=err,
            max_input_date=str(ix[-1].date()))
        status,ir=industry_returns(ind[sec],ix);out["industry_status"]=status
        if status=="KNOWN":
            iy=ir-fac.rf_mon.to_numpy();X=np.c_[np.ones(36),iy]
            coef,_,rank,_=np.linalg.lstsq(X,y,rcond=None)
            if rank==2:
                out.update(industry_beta36=float(coef[1]),industry_alpha36=float(coef[0]),
                    industry_vol36=float(np.std(ir,ddof=1)),industry_mom11=float(np.prod(1+ir[24:35])-1))
            else:out["industry_status"]="UNKNOWN_INDUSTRY_RANK"
        if rr["month"] not in tested:
            day=pd.Timestamp(rr["first_signal_day"])
            st,ip=industry_returns(ind[sec].loc[:day],ix)
            assert st==status and (ir is None or np.array_equal(ir,ip))
            altered=ind[sec].copy();altered.loc[altered.index>=day.to_period("M").start_time,"close"]*=19
            st,ip=industry_returns(altered,ix)
            assert st==status and (ir is None or np.array_equal(ir,ip))
            tested.add(rr["month"]);prefixchecks+=1
        rows.append(out)
    if (j+1)%400==0:print("ATTRIBUTION_STOCKS",j+1,flush=True)
feat=pd.DataFrame(rows);assert len(feat)==14635
feat.to_csv(O/"EXANTE_ALL_STOCK_MONTH_FEATURES.csv",index=False)
metrics=["RAW_MOM11","RAW_EXCESS_STANDARDIZED","RM","beta_market","beta_size","beta_value","raw_vol36","raw_vol11","residual_sd","industry_beta36","industry_vol36","industry_mom11","normalization_component","alpha_component","market_component","size_component","value_component"]
# Identical original queues, all exclusive-pick differences, no outcomes used to select these groups.
q=pd.read_csv(io.BytesIO(src(P/"CANDIDATE_RANKS_PRELABEL.csv")),low_memory=False)
newcols=[c for c in feat if c not in q]+["sid","month"]
q=q.merge(feat[newcols],on=["sid","month"],validate="many_to_one")
swaps=[]
for key,g in q.groupby(["window","day","sector"],sort=True):
    a=g[g.RM_selected&~g.RAW_MOM11_selected];b=g[g.RAW_MOM11_selected&~g.RM_selected]
    if not len(a):assert not len(b);continue
    assert len(a)==len(b) and a.known.all() and b.known.all()
    row=dict(window=key[0],day=key[1],sector=key[2],slots=len(a),CH3_exclusive="|".join(a.sid),RAW_exclusive="|".join(b.sid))
    for c in metrics:
        row[c+"_CH3"]=float(a[c].mean());row[c+"_RAW"]=float(b[c].mean());row[c+"_delta"]=row[c+"_CH3"]-row[c+"_RAW"]
        row[c+"_nCH3"]=int(a[c].notna().sum());row[c+"_nRAW"]=int(b[c].notna().sum())
    swaps.append(row)
sw=pd.DataFrame(swaps);sw.to_csv(O/"EXANTE_FIXED_QUEUE_CH3_RAW_SWAPS.csv",index=False)
summ=[]
for w,g in sw.groupby("window",sort=True):
    for c in metrics:
        v=g[c+"_delta"];daily=g.groupby("day")[c+"_delta"].mean()
        summ.append(dict(window=w,metric=c,queues=len(g),known_queues=int(v.notna().sum()),slots=int(g.slots.sum()),
            queue_mean_delta=float(v.mean()),date_equal_mean_delta=float(daily.mean()),median_delta=float(v.median()),
            positive=int(v.gt(0).sum()),negative=int(v.lt(0).sum()),zero=int(v.eq(0).sum())))
pd.DataFrame(summ).to_csv(O/"EXANTE_FIXED_QUEUE_SUMMARY.csv",index=False)
z=pd.read_csv(io.BytesIO(src(L/"report/CORE_AND_FULL_ROUNDS.csv")),float_precision="round_trip",low_memory=False)
cols=[c for c in feat if c not in z]+["sid","month"]
z=z.merge(feat[cols],on=["sid","month"],validate="many_to_one")
actual=[]
for key,g in z.groupby(["window","arm"],sort=True):
    for c in metrics:
        v=pd.to_numeric(g[c],errors="coerce")
        actual.append(dict(window=key[0],arm=key[1],metric=c,admissions=len(g),known=int(v.notna().sum()),unknown=int(v.isna().sum()),mean=float(v.mean()),median=float(v.median())))
pd.DataFrame(actual).to_csv(O/"EXANTE_ALL_ADMISSION_SUMMARY.csv",index=False)
z.to_csv(O/"EXANTE_ALL_ACTUAL_ROUNDS.csv",index=False)
src(Path(__file__));src(O/"EXANTE_ATTRIBUTION_FREEZE.json")
dump("EXANTE_SOURCE_HASHES.json",S)
dump("EXANTE_QA.json",dict(stock_months=len(feat),known=int(feat.status.eq("CALENDAR_COMPUTABLE_RELEASE_UNKNOWN").sum()),
    max_score_identity_error=maxerr,industry_status_counts=feat.industry_status.value_counts().to_dict(),industry_prefix_and_future_tests=prefixchecks,
    fixed_disagreement_queues=len(sw),actual_rounds=len(z),new_economic_runs=0,new_filters=0,post_result_attribution=True,
    industry_beta_not_market_neutral=True,score_components_not_profit_attribution=True))
print(pd.DataFrame(summ).query("metric in ['beta_market','industry_beta36','raw_vol36','RAW_MOM11','normalization_component','alpha_component','market_component','size_component','value_component']").to_string(index=False))
