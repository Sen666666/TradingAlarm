
from pathlib import Path
import numpy as np,pandas as pd,pyarrow as pa,pyarrow.dataset as ds,json,hashlib,time
O=Path("/Users/bytedance/Documents/Codex/2026-11-06/h1_failure_mechanism_v1");O.mkdir(exist_ok=True)
root=Path("/Users/bytedance/Documents/Codex/2026-11-04/task-3/entry_quality/daily_signal_cache_pilot20_v1/full_universe_v1")
M=json.loads((root/"CACHE_DATASET.json").read_text());files=[str(root/k)for k in M["files"]];D=ds.dataset(files,format="parquet")
days=pd.to_datetime(["2024-09-19","2024-09-24","2024-10-08","2026-01-05","2026-01-15","2026-01-20"])
freeze={"dates":[str(x.date())for x in days],"universe":"Frozen canonical5517, all five positive finite endpoints at lags0,63,126,189,252; current E0 and G1 ready for i_buy subset. Missing inner observations not filled. Not PIT.","baseline":"H=mid-percentile of mature252 H1 raw in same complete-endpoint pool","A":"max(H, mid-percentile(log(C_t/C_t-20))) when R20>0 and R20>same-pool median(R20), otherwise H","B":"max(H,min(mid-percentile(R20),mid-percentile(Q20))) only when A return gate true, all last22 closes observed, and min(C_t,C_t-1)>max(C_t-21..C_t-2); Q20=sum(log returns last20)/sqrt(sum(log returns squared last20)), zero quadratic variation yields missing","comparison_pool":"Current cached E0ready=1,Gready=True,I_target=1,i_buy=True and complete mature252 H1. This is research i_buy, not S0/pending/fill.","tie_rule":"score descending then sid ascending","K":[20,100],"labels":"C_t+20/C_t-1; future20 common-date closes min/max versus signal close; any missing among future20 marks label UNKNOWN, no backfill or replacement. Descriptive close labels, not attainable returns.","status":"Frozen before code reads future outcomes; dates/known stories already consumed, not independent out-of-sample validation.","parameter_search":"None"}
(O/"SIX_DATE_PILOT_FREEZE.json").write_text(json.dumps(freeze,ensure_ascii=False,indent=2)+"\n")
start=time.time();df=D.to_table(columns=["sid","day","price__close"]).to_pandas();P=df.pivot(index="day",columns="sid",values="price__close").sort_index();del df
signals=D.to_table(columns=["sid","day","native__e0_ready","native__g_ready","native__i_target","native__i_buy"],filter=ds.field("day").isin(pa.array(days))).to_pandas()
z=np.load("/Users/bytedance/Documents/ChatGPT/money/TradingAlarm/runtime/market/update-20261030-153010-c551af/prepared/h1.npz");oldset=set(s for s in z["symbols"].astype(str)if not s.startswith("URFI"))
C=P.to_numpy();ids=P.columns.to_numpy();legacy=np.array([s in oldset for s in ids]);named=["002583.SZ","300085.SZ","300666.SZ","301611.SZ","603061.SH"];namedrows=[];selected=[];cover=[];allranks=[]
pct=lambda a:pd.Series(a).rank(method="average",na_option="keep").to_numpy() # transform below to midpoint
def mp(a):
 out=np.full(len(a),np.nan);k=np.isfinite(a);n=k.sum()
 out[k]=100*(pd.Series(a[k]).rank(method="average").to_numpy()-.5)/n
 return out
for day in days:
 t=P.index.get_loc(day);ep=C[t-np.arange(5)*63];known=np.isfinite(ep).all(axis=0)&(ep>0).all(axis=0);raw=np.sum((ep[:-1]/ep[1:]-1)*np.array([.4,.2,.2,.2])[:,None],axis=0);raw=np.round(raw,12);raw[~known]=np.nan
 h=mp(raw);ohl=raw.copy();ohl[~legacy]=np.nan;hold=mp(ohl)
 p22=C[t-21:t+1];r=np.diff(np.log(C[t-20:t+1]),axis=0);r20=np.log(C[t]/C[t-20]);q=np.divide(r.sum(axis=0),np.sqrt((r*r).sum(axis=0)),out=np.full(len(ids),np.nan),where=(r*r).sum(axis=0)>0)
 complete=np.isfinite(p22).all(axis=0)&(p22>0).all(axis=0);r20[~known]=np.nan;q[~known]=np.nan;nr=mp(r20);nq=mp(q);gate=np.isfinite(r20)&(r20>0)&(r20>np.nanmedian(r20));confirm=complete&(np.minimum(C[t],C[t-1])>np.max(C[t-21:t-1],axis=0));n=np.minimum(nr,nq);a=np.where(gate,np.fmax(h,nr),h);b=np.where(gate&confirm,np.fmax(h,n),h)
 sig=signals[signals.day.eq(day)].set_index("sid").reindex(ids);eligible=(sig.native__e0_ready.eq(1)&sig.native__g_ready.eq(True)&sig.native__i_target.eq(1)&sig.native__i_buy.eq(True)).to_numpy()&known
 row=pd.DataFrame({"day":str(day.date()),"sid":ids,"canonical_mature_H1_raw":raw,"full_H1_percentile":h,"legacy_intersection_H1_percentile":hold,"legacy_member":legacy,"R20_log":r20,"Q20_shape":q,"R20_percentile":nr,"Q20_percentile":nq,"recent_positive_relative_gate":gate,"two_close_breakout":confirm,"A_score":a,"B_score":b,"eligible_cached_i_buy":eligible})
 for strategy,sc in [("H1",h),("A_recent",a),("B_confirmed",b)]:
  idx=np.flatnonzero(eligible&np.isfinite(sc));idx=idx[np.lexsort((ids[idx],-sc[idx]))];row[strategy+"_eligible_rank"]=pd.Series(np.arange(1,len(idx)+1),index=idx).reindex(row.index)
  for k in [20,100]:
   take=idx[:k]
   for j in take:selected.append({"day":str(day.date()),"sid":ids[j],"strategy":strategy,"K":k,"rank":int(np.where(idx==j)[0][0]+1),"score":float(sc[j]),"index_t":t,"index_j":int(j)})
 row["full_H1_ordinal"]=row.canonical_mature_H1_raw.rank(method="first",ascending=False)
 for s in named:
  j=np.where(ids==s)[0][0];namedrows.append(row.iloc[j].to_dict())
 allranks.append(row)
 cover.append({"day":str(day.date()),"five_endpoint_known":int(known.sum()),"legacy_intersection_known":int((known&legacy).sum()),"research_i_buy_known":int(eligible.sum()),"research_i_buy_legacy":int((eligible&legacy).sum()),"new_channel_confirmation_and_positive":int((eligible&gate&confirm).sum())})
ranks=pd.concat(allranks,ignore_index=True);ranks.to_csv(O/"SIX_DATE_ALL_CANONICAL_RANKS.csv",index=False);pd.DataFrame(namedrows).to_csv(O/"SIX_DATE_NAMED_ROWS.csv",index=False);pd.DataFrame(cover).to_csv(O/"SIX_DATE_POOL_COVERAGE.csv",index=False)
sel=pd.DataFrame(selected);sel.to_csv(O/"SIX_DATE_SELECTIONS_BEFORE_LABELS.csv",index=False)
receipt={"selection_sha256":hashlib.sha256((O/"SIX_DATE_SELECTIONS_BEFORE_LABELS.csv").read_bytes()).hexdigest(),"ranks_sha256":hashlib.sha256((O/"SIX_DATE_ALL_CANONICAL_RANKS.csv").read_bytes()).hexdigest(),"source_cache_identity":"b0af9a5b8a8f6d1f8da1b56577cee3270c7ef2a20e2bd48edd","time_seconds_before_outcomes":time.time()-start}
(O/"SIX_DATE_RANK_FREEZE_RECEIPT.json").write_text(json.dumps(receipt,indent=2)+"\n")
outcomes=[]
for x in selected:
 t=x["index_t"];j=x["index_j"];future=C[t+1:t+21,j];ok=len(future)==20 and np.isfinite(future).all() and (future>0).all()
 y=x.copy();y["complete20"]=ok;y["end20"]=float(future[-1]/C[t,j]-1)if ok else None;y["mae20"]=float(min(0,np.min(future/C[t,j]-1)))if ok else None;y["mfe20"]=float(max(0,np.max(future/C[t,j]-1)))if ok else None;outcomes.append(y)
oo=pd.DataFrame(outcomes);oo.to_csv(O/"SIX_DATE_SELECTED_DESCRIPTIVE_LABELS.csv",index=False)
summary=[]
for key,g in oo.groupby(["day","K","strategy"],sort=False):
 qg=g[g.complete20];summary.append({"day":key[0],"K":key[1],"strategy":key[2],"selected":len(g),"complete20":len(qg),"mean_end20":qg.end20.mean(),"median_end20":qg.end20.median(),"positive_fraction":qg.end20.gt(0).mean(),"mean_mae20":qg.mae20.mean(),"mean_mfe20":qg.mfe20.mean(),"overlap_with_H1":len(set(g.sid)&set(oo[(oo.day==key[0])&(oo.K==key[1])&(oo.strategy=="H1")].sid))})
ss=pd.DataFrame(summary);ss.to_csv(O/"SIX_DATE_PILOT_SUMMARY.csv",index=False)
print("COVERAGE");print(pd.DataFrame(cover).to_string(index=False));print("NAMED");print(pd.DataFrame(namedrows)[["day","sid","canonical_mature_H1_raw","full_H1_percentile","legacy_intersection_H1_percentile","eligible_cached_i_buy","two_close_breakout","H1_eligible_rank","A_recent_eligible_rank","B_confirmed_eligible_rank"]].to_string(index=False));print("SUMMARY");print(ss.to_string(index=False));print("SECONDS",time.time()-start)
