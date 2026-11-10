import warnings; warnings.filterwarnings("ignore",category=FutureWarning)
from pathlib import Path
import numpy as np,pandas as pd,sys,json,hashlib,time
O=Path(__file__).resolve().parent; R=O.parent; END="2026-05-15"
M=Path("/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/universe-cp1-inputs-20261031/STOCK_MANIFEST.json")
F=Path("/Users/bytedance/Documents/Codex/2026-11-04/task-3/entry_quality/pvr_information_v1/feature_design")
Q=R/"selection_entry_diagnosis_v1/mobile_candidate_response_v1/LEGAL_EMPTY_MOBILE_CANDIDATES.parquet"
LAB=Q.parent/"FIXED_NATIVE_PRICE_LABELS.parquet"
H=Path("/Users/bytedance/Documents/ChatGPT/money/TradingAlarm/runtime/market/update-20261030-153010-c551af/prepared/h1.npz")
sys.path.insert(0,str(F));from features import original_pvr,original_observation_clock
METHODS=["PVR","L21","CMF21"]
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def dump(n,x):(O/n).write_text(json.dumps(x,ensure_ascii=False,indent=2,default=lambda a:a.item() if isinstance(a,np.generic) else str(a)))
def calc(p):
 v,b=original_observation_clock(p);raw=["raw_open","raw_high","raw_low","raw_close"];native=["open","high","low","close"]
 good=v&np.isfinite(p[raw+native]).all(axis=1)&p[raw+native].gt(0).all(axis=1)
 good &= p.raw_high.ge(p[raw].max(axis=1))&p.raw_low.le(p[raw].min(axis=1))&p.high.ge(p[native].max(axis=1))&p.low.le(p[native].min(axis=1))
 good &= p.high.gt(p.low)&p.raw_high.gt(p.raw_low)
 for c in ["observed_bar","is_observed_bar","price_eligible","volume_eligible"]:good &= p[c].notna()&p[c].eq(True)
 for c in ["source_invalid","synthetic_event_bar"]:good &= p[c].notna()&p[c].eq(False)
 good &= p.volume_unit.eq("shares")&p.amount_unit.eq("CNY")&np.isfinite(p.raw_volume)&p.raw_volume.gt(0)
 for c in ["volume_factor","adjustment_factor"]:good &= np.isfinite(p[c])&p[c].gt(0)
 for c in native:good &= (p["raw_"+c]*p.adjustment_factor-p[c]).abs().le(1e-10)
 av=p.amount/p.raw_volume;tol=.5/p.raw_volume+1e-8
 good &= np.isfinite(av)&av.ge(p.raw_low-tol)&av.le(p.raw_high+tol)
 clv=(2*p.close-p.high-p.low)/(p.high-p.low)
 rawclv=(2*p.raw_close-p.raw_high-p.raw_low)/(p.raw_high-p.raw_low)
 good &= (clv-rawclv).abs().le(1e-8)
 z=original_pvr(p);z["clv"]=clv.where(good);z["L21"]=np.nan;z["CMF21"]=np.nan
 for _,g in p[v].groupby(b[v],sort=False):
  ix=g.index;ok=good.loc[ix].rolling(21,min_periods=21).sum().eq(21)
  for c in ["source_kind","source_path"]:
   codes=pd.Series(pd.factorize(g[c])[0],index=ix)
   ok &= codes.rolling(21).min().eq(codes.rolling(21).max())&g[c].notna().rolling(21).sum().eq(21)&g[c].astype(str).str.len().gt(0).rolling(21).sum().eq(21)
  for c in ["volume_factor","adjustment_factor"]:ok &= g[c].rolling(21).min().eq(g[c].rolling(21).max())
  a=clv.loc[ix];vol=g.raw_volume;den=vol.rolling(21,min_periods=21).sum()
  z.loc[ix,"L21"]=a.rolling(21,min_periods=21).mean().where(ok)
  z.loc[ix,"CMF21"]=((a*vol).rolling(21,min_periods=21).sum()/den).where(ok&den.gt(0))
 z["volume_increment"]=z.CMF21-z.L21
 for k in ["L21","CMF21"]:
  z["score_"+k]=50+50*np.tanh(2*(z.E-z.E.clip(lower=0)*(-z[k]).clip(lower=0)))
 z["common_known"]=z[["score","score_L21","score_CMF21"]].notna().all(axis=1)
 return z
def synthetic():
 ix=pd.bdate_range("2020-01-01",periods=120);p=pd.DataFrame(index=ix)
 for c,x in dict(open=100.,high=101.,low=99.,close=100.,raw_volume=100.,amount=10000.,volume_factor=1.,adjustment_factor=1.,segment_id=0,source_kind="test",source_path="test",volume_unit="shares",amount_unit="CNY",observed_bar=True,is_observed_bar=True,price_eligible=True,volume_eligible=True,source_invalid=False,synthetic_event_bar=False).items():p[c]=x
 for c in ["open","high","low","close"]:p["raw_"+c]=p[c]
 tests={}
 z=calc(p);tests["midpoint_zero"]=bool(z.CMF21.iloc[-1]==0 and z.L21.iloc[-1]==0)
 p1=p.copy();p1["close"]=p1["raw_close"]=101.;z1=calc(p1);tests["all_high_plus1"]=bool(z1.CMF21.iloc[-1]==1)
 p2=p.copy();p2["close"]=p2["raw_close"]=99.;tests["all_low_minus1"]=bool(calc(p2).CMF21.iloc[-1]==-1)
 p3=p1.copy();p3["raw_volume"]*=7;p3["amount"]*=7;tests["uniform_volume_scale_invariant"]=bool(calc(p3).CMF21.equals(z1.CMF21))
 for name,col,val in [("zero_volume","raw_volume",0.),("zero_amount","amount",0.),("share_factor_change","volume_factor",2.),("adjustment_factor_change","adjustment_factor",2.),("source_path_change","source_path","new"),("source_kind_change","source_kind","new")]:
  q=p.copy();q.loc[ix[-10],col]=val;tests[name+"_unknown"]=bool(calc(q).CMF21.iloc[-1]!=calc(q).CMF21.iloc[-1])
 q=p.copy()
 for c in ["open","high","low","close","raw_open","raw_high","raw_low","raw_close"]:q.loc[ix[-10],c]=100.
 zz=calc(q);tests["one_zero_range_invalidates_full_window"]=bool(zz.CMF21.iloc[-1]!=zz.CMF21.iloc[-1])
 q=p.copy()
 for c,val in [("open",91.),("high",92.),("low",88.),("close",92.)]:q.loc[ix[-1],c]=q.loc[ix[-1],"raw_"+c]=val
 q.loc[ix[-1],"amount"]=9000.;zz=calc(q);tests["gap_down_positive_clv"]=bool(q.close.iloc[-1]<q.close.iloc[-2] and zz.clv.iloc[-1]==1 and zz.CMF21.iloc[-1]>0)
 q=p.copy();q["close"]=q["raw_close"]=np.tile([99.5,100.5],60);q["raw_volume"]=np.tile([1.,3.],60);q["amount"]=q.raw_volume*100
 zz=calc(q);a=zz.clv.tail(21);v=q.raw_volume.tail(21);cov=((a-a.mean())*(v-v.mean())).mean()
 tests["volume_covariance_identity"]=bool(abs(zz.volume_increment.iloc[-1]-cov/v.mean())<1e-12)
 q=p.copy()
 for c,shift in [("open",0.),("high",1.),("low",-.25),("close",0.)]:q[c]=q["raw_"+c]=100.-np.arange(len(q))*.01+shift
 q["amount"]=q.close*q.raw_volume;zz=calc(q);neg=zz[zz.E.lt(0)&zz.common_known]
 tests["negative_E_unchanged"]=bool(len(neg)>0 and (neg.score_CMF21-neg.score).abs().max()<1e-12)
 tests["constant_volume_equal_unweighted"]=bool((z1.CMF21-z1.L21).dropna().eq(0).all())
 assert all(tests.values()),tests;dump("SYNTHETIC_QA.json",tests);print("SYNTHETIC",tests,flush=True)
def cases():
 print("FROZEN", (O/"PROTOCOL.json").read_text(),flush=True);synthetic()
 mp={m["symbol"]:m for m in json.loads(M.read_text())}
 cases=json.loads((R/"obv_pvr_mechanism_v1/FIXED_CASES.json").read_text())
 print("CASE_SCHEMA",str(cases)[:400],flush=True)
 if not isinstance(cases,list):raise ValueError("Unexpected cases format")
 rows=[];prefix=[];sources={}
 for sid in sorted({x["sid"] for x in cases}):
  m=mp[sid];path=next(p for p in m["source_sha256"] if p.endswith("/signal.parquet"));assert sha(path)==m["source_sha256"][path];sources[path]=sha(path)
  p=pd.read_parquet(path).loc[:END];z=calc(p)
  for x in [a for a in cases if a["sid"]==sid]:
   day=x["day"];r=z.loc[pd.Timestamp(day)].to_dict();rows.append({**x,**r})
   pd.testing.assert_frame_equal(calc(p.loc[:day]),z.loc[:day],check_exact=True);prefix.append(dict(sid=sid,day=day,exact=True))
 c=pd.DataFrame(rows);c.to_csv(O/"FIXED_CASES.csv",index=False)
 dump("CASE_PREFIX_QA.json",prefix);dump("CASE_SOURCE_HASHES.json",sources);assert all(sha(p)==h for p,h in sources.items())
 print("FIXED_CASES",c[["sid","day","selection","original_round_pnl","score","clv","L21","CMF21","score_L21","score_CMF21","common_known"]].to_json(orient="records"),flush=True)
 print("CASE_COUNTS",len(c),int(c.common_known.sum()),int((c.E.gt(0)&c.CMF21.lt(0)).sum()),flush=True)
def features():
 assert not (O/"SEALED_PICKS.parquet").exists()
 mp={m["symbol"]:m for m in json.loads(M.read_text())};q=pd.read_parquet(Q);q=q[q.account.eq("PVR")].reset_index(drop=True);assert len(q)==53121
 source={str(p):sha(p) for p in [M,Q,H,O/"PROTOCOL.json",Path(__file__)]};parts=[];aud=[];t=time.monotonic()
 for no,(sid,g) in enumerate(q.groupby("sid",sort=True)):
  m=mp[sid];path=next(p for p in m["source_sha256"] if p.endswith("/signal.parquet"));assert sha(path)==m["source_sha256"][path];source[path]=sha(path)
  p=pd.read_parquet(path).loc[:END];z=calc(p);a=z.reindex(pd.DatetimeIndex(g.day)).reset_index(drop=True);a["sid"]=sid;a["day"]=g.day.to_numpy();parts.append(a)
  aud.append(dict(sid=sid,rows=len(g),known=int(a.common_known.sum()),factor_change21_unknown=int((p.adjustment_factor.rolling(21).min()!=p.adjustment_factor.rolling(21).max()).reindex(pd.DatetimeIndex(g.day)).sum())))
  if (no+1)%300==0:print("PROGRESS",no+1,round(time.monotonic()-t,1),flush=True)
 c=q.merge(pd.concat(parts,ignore_index=True),on=["sid","day"],validate="one_to_one");c["row"]=np.arange(len(c))
 assert ((c.original_PVR-c.score).abs().max()<1e-10);assert c.original_PVR.notna().equals(c.score.notna())
 affected=int((c.E.gt(0)&c.CMF21.lt(0)&c.common_known).sum())
 gate=bool(c.common_known.mean()>=.5 and affected/len(c)>=.01)
 c.to_parquet(O/"FEATURES.parquet",index=False);pd.DataFrame(aud).to_csv(O/"SOURCE_AUDIT.csv",index=False);dump("INPUT_HASHES.json",source)
 coverage=dict(opportunities=len(c),stocks=c.sid.nunique(),dates=c.day.nunique(),known=int(c.common_known.sum()),CMF_affected=affected,L21_affected=int((c.E.gt(0)&c.L21.lt(0)&c.common_known).sum()),volume_increment_nonzero=int((c.volume_increment.abs().gt(1e-12)&c.common_known).sum()),pvr_max_error=float((c.original_PVR-c.score).abs().max()),feasibility_pass=gate)
 dump("FEATURE_COVERAGE.json",coverage);print("FEATURE_COVERAGE",coverage,flush=True)
 if not gate:return
 picks=[];queues=[];moves=[]
 for day,g in c.groupby("day",sort=True):
  base=g.sort_values(["original_priority_rank","sid"]);K=min(20,len(base));bi=set(base.head(K).index);ks=base.head(K).groupby("sector").size().to_dict()
  for method in METHODS:
   chosen=[]
   for sector,gs in base.groupby("sector",sort=False):
    k=int(ks.get(sector,0));order=list(gs.index)
    if method!="PVR":
     good=gs.common_known;ranked=gs[good].sort_values(["score_"+method,"original_priority_rank","sid"],ascending=[False,True,True]);it=iter(ranked.index);order=[next(it) if good.loc[j] else j for j in gs.index]
     assert all(order[pos]==j for pos,j in enumerate(gs.index) if not good.loc[j]) and set(order)==set(gs.index)
    chosen+=order[:k];moves.extend(dict(row=int(j),method=method,sector_rank=rank+1,selected=rank<k) for rank,j in enumerate(order))
   assert len(chosen)==K and c.loc[chosen].groupby("sector").size().to_dict()==ks
   picks.extend(dict(row=int(j),day=day,method=method) for j in chosen);queues.append(dict(day=day,method=method,N=len(g),K=K,known=int(g.common_known.sum()),changed=len(set(chosen)-bi)))
 pd.DataFrame(picks).to_parquet(O/"SEALED_PICKS.parquet",index=False);pd.DataFrame(moves).to_parquet(O/"RANK_MOVES.parquet",index=False);pd.DataFrame(queues).to_csv(O/"QUEUE_AUDIT.csv",index=False)
 hs={n:sha(O/n) for n in ["FEATURES.parquet","SEALED_PICKS.parquet","RANK_MOVES.parquet","PROTOCOL.json","experiment.py"]}
 assert all(sha(p)==h for p,h in source.items());dump("RANK_SEAL.json",dict(hashes=hs,future_labels_read=False,**coverage))
 print("SEALED_QUEUE",pd.DataFrame(queues).groupby("method")[["K","changed"]].sum().to_json(),flush=True)
def periods():return [("ALL",None,None)]+[(str(y),str(y)+"-01-01",str(y)+"-12-31") for y in range(2022,2027)]+[("2024_924","2024-09-24","2024-10-31"),("2026Q1","2026-01-01","2026-03-31")]
def subset(x,a,b):return x if a is None else x[x.day.between(a,b)]
def evaluate():
 seal=json.loads((O/"RANK_SEAL.json").read_text());assert all(sha(O/n)==h for n,h in seal["hashes"].items())
 c=pd.read_parquet(O/"FEATURES.parquet");sel=pd.read_parquet(O/"SEALED_PICKS.parquet");lab=pd.read_parquet(LAB)
 c=c.merge(lab,on=["sid","day"],validate="one_to_one");s=sel.merge(c,on=["row","day"],validate="many_to_one")
 cal=pd.DatetimeIndex(np.load(H,allow_pickle=False)["dates"]);cal=cal[(cal>="2013-01-01")&(cal<=END)];pos={str(d.date()):i for i,d in enumerate(cal)}
 results=[];deltas=[];coverage=[];blocks=[]
 for h in [5,20,60]:
  co="complete"+str(h);ret="ret"+str(h);gd=s.groupby("day")[co].all();whole=s[s.day.isin(gd[gd].index)]
  for per,a,b in periods():
   x=subset(whole,a,b);coverage.append(dict(period=per,H=h,dates=x.day.nunique(),slots_each=len(x)//3))
   if x.empty:continue
   means=x.groupby(["day","method"])[ret].mean().unstack("method")
   for method,g in x.groupby("method"):
    results.append(dict(period=per,H=h,method=method,N=len(g),days=g.day.nunique(),mean_day=float(g.groupby("day")[ret].mean().mean()),mean_event=float(g[ret].mean()),positive_price=float(g[ret].gt(0).mean()),positive_40bp=float(g[ret].gt(.004).mean()),mae=float(g["mae"+str(h)].mean()),mfe=float(g["mfe"+str(h)].mean())))
   for aa,bb in [("CMF21","PVR"),("L21","PVR"),("CMF21","L21")]:
    d=means[aa]-means[bb];block=pd.DataFrame(dict(value=d,block=[pos[str(day)]//60 for day in d.index])).groupby("block").value.agg(["sum","count","mean"]);de=dict(period=per,H=h,comparison=aa+"-"+bb,days=len(d),delta=float(d.mean()),blocks=len(block),positive_blocks=int(block["mean"].gt(0).sum()),negative_blocks=int(block["mean"].lt(0).sum()),leave_best_day=float(d.drop(d.idxmax()).mean()),lo=None,hi=None)
    if len(block)>=5:
     rng=np.random.default_rng(20261106);ix=rng.integers(0,len(block),(2000,len(block)));bs=block["sum"].to_numpy()[ix].sum(1)/block["count"].to_numpy()[ix].sum(1);de.update(lo=float(np.quantile(bs,.025)),hi=float(np.quantile(bs,.975)),leave_best_block=float((block["sum"].sum()-block.loc[block["mean"].idxmax(),"sum"])/(block["count"].sum()-block.loc[block["mean"].idxmax(),"count"])))
    deltas.append(de)
    if per=="ALL":blocks.extend(dict(H=h,comparison=aa+"-"+bb,block=int(k),**r.to_dict()) for k,r in block.iterrows())
 pd.DataFrame(results).to_csv(O/"SAME_DATE_SECTOR_K_RESULTS.csv",index=False);pd.DataFrame(deltas).to_csv(O/"PAIRED_60SESSION_BLOCKS.csv",index=False);pd.DataFrame(coverage).to_csv(O/"EVALUATION_COVERAGE.csv",index=False);pd.DataFrame(blocks).to_csv(O/"BLOCK_DETAILS.csv",index=False)
 members={m:set(g.row) for m,g in sel.groupby("method")};roots=[]
 c["calendar_t"]=[pos[d] for d in c.day]
 for (sid,epoch),g in c.groupby(["sid","epoch"],dropna=False):
  g=g.sort_values("calendar_t");b=g.iloc[0];early=set(g.loc[g.calendar_t.le(b.calendar_t+5),"row"]);known=str(epoch) not in ["None","nan","[None, None]"]
  roots.append(dict(sid=sid,epoch=str(epoch),epoch_known=known,day=b.day,complete60=bool(b.complete60),big60=bool(b.big60_posthoc),**{m:bool(early&v) for m,v in members.items()}))
 rr=pd.DataFrame(roots);rr.to_csv(O/"ROOT_COVERAGE.csv",index=False);rs=[]
 for per,a,b in periods():
  for scope in ["ALL_ROOTS","KNOWN_EPOCH"]:
   x=subset(rr,a,b);x=x if scope=="ALL_ROOTS" else x[x.epoch_known];big=x[x.big60]
   for m in METHODS:rs.append(dict(period=per,scope=scope,method=m,roots=len(x),complete=int(x.complete60.sum()),big=len(big),caught=int(big[m].sum()),lost_vs_PVR=int((big.PVR&~big[m]).sum()),added_vs_PVR=int((~big.PVR&big[m]).sum())))
 pd.DataFrame(rs).to_csv(O/"ROOT_COVERAGE_SUMMARY.csv",index=False)
 fixed=pd.read_csv(O/"FIXED_CASES.csv");moves=pd.read_parquet(O/"RANK_MOVES.parquet");fixedq=fixed[["sid","day"]].merge(c,on=["sid","day"],how="left",validate="one_to_one").merge(moves,on="row",how="left");fixedq.to_csv(O/"FIXED_CASE_QUEUE.csv",index=False)
 s.to_parquet(O/"SELECTED_WITH_LABELS.parquet",index=False);source=json.loads((O/"INPUT_HASHES.json").read_text());assert all(sha(p)==h for p,h in source.items());assert all(sha(O/n)==h for n,h in seal["hashes"].items())
 dump("COMPLETION.json",dict(status="ONE_FROZEN_CMF_CLV_PVR_COMPARISON_COMPLETE",original_sources_unchanged=True,seal_unchanged=True,accounts=0,parameter_searches=0,through=END,not_oos=True,label_sha256=sha(LAB)))
 print("DELTAS",pd.DataFrame(deltas).query("H in [20,60]").to_json(orient="records"),flush=True)
 print("ROOTS",pd.DataFrame(rs).query("scope=='KNOWN_EPOCH'").to_json(orient="records"),flush=True)
if __name__=="__main__":{"cases":cases,"features":features,"evaluate":evaluate}[sys.argv[1]]()
