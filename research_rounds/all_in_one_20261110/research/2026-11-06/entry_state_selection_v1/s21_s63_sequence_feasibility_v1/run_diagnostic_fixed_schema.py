from pathlib import Path
import importlib.util,sys,json,hashlib,math,time
import numpy as np,pandas as pd
O=Path(__file__).resolve().parent;R=O.parent
MR=Path("/Users/bytedance/Documents/ChatGPT/money/research_rounds")
M=Path("/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/universe-cp1-inputs-20261031/STOCK_MANIFEST.json")
B4=MR/"pv-strength-b4-20261025/code/model.py";DU=MR/"pv-participation-response-20261020/code/data_utils.py";GG=MR/"b5-g1-20261025/code/grade.py"
sys.path.insert(0,str(DU.parent));from data_utils import eligible_prices
B5=MR/"pv-strength-b5-20261025/code";sys.path.insert(0,str(B5));from evidence import _event_facts
spg=importlib.util.spec_from_file_location("original_grade",GG);gm=importlib.util.module_from_spec(spg);spg.loader.exec_module(gm)
spec=importlib.util.spec_from_file_location("b4",B4);b4=importlib.util.module_from_spec(spec);spec.loader.exec_module(b4)
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def clean(x):
 if isinstance(x,dict):return {str(k):clean(v) for k,v in x.items()}
 if isinstance(x,(list,tuple,np.ndarray)):return [clean(v) for v in x]
 if isinstance(x,(pd.Timestamp,Path)):return str(x)
 if isinstance(x,(np.bool_,)):return bool(x)
 if isinstance(x,(np.integer,)):return int(x)
 if isinstance(x,(float,np.floating)):return float(x) if np.isfinite(x) else None
 return x
def dump(n,x):(O/n).write_text(json.dumps(clean(x),ensure_ascii=False,indent=2)+"\n")
def annotate(z,j):
 confirmations=[q for q in j if q["kind"]=="structure_confirmed"];last={21:None,63:None};out=[]
 for t,a in z.iterrows():
  ds=str(t.date());r=dict(day=t,ready=bool(np.isfinite(a.s)),S21=a.S21,S63=a.S63,mu5=a.mu5,mu21=a.mu21,acute_up=a.acute_up)
  for h in [21,63]:
   now=[q for q in confirmations if q["date"]==ds and q["horizon"]==h]
   for q in now:
    if q["direction"]==1:last[h]=q
   r["confirmed_up"+str(h)]=bool(now and now[0]["direction"]==1);r["confirmed_down"+str(h)]=bool(now and now[0]["direction"]==-1)
   for side in ["up","down"]:
    for k in ["active","anchor_date","anchor_price","scale_at_anchor","volume_reference","threshold","frontier","credit","x"]:r[side+str(h)+"_"+k]=a[f"{side}_{k}_{h}"]
    r[side+str(h)+"_progress"]=min(a[f"{side}_x_{h}"],a[f"{side}_credit_{h}"])/a[f"{side}_threshold_{h}"] if a[f"{side}_active_{h}"]==1 else np.nan
   r["last_up_date"+str(h)]=last[h]["date"] if last[h] else None
   r["last_up_anchor"+str(h)]=last[h]["receipt"]["anchor_date"] if last[h] else None
  # Lineage only. Do not treat this consumed short receipt as a live progress state.
  sr=None;short_source="NONE"
  if a.up_active_21==1:
   sr={k:a["up_"+k+"_21"] for k in ["anchor_date","anchor_price","scale_at_anchor","volume_reference"]};short_source="CURRENT_CANDIDATE"
  elif a.S21==1 and last[21]:
   sr=last[21]["receipt"];short_source="CONSUMED_CURRENT_UP_RECEIPT"
  r["short_up_lineage_source"]=short_source
  if sr is not None and a.up_active_63==1:
   r["same_up_lineage"]=all(sr[k]==a["up_"+k+"_63"] for k in ["anchor_date","anchor_price","scale_at_anchor","volume_reference"])
  else:r["same_up_lineage"]=None
  r["both_up_candidates"]=bool(a.up_active_21==1 and a.up_active_63==1)
  if r["both_up_candidates"] and r["same_up_lineage"]:
   np.testing.assert_allclose([a.up_frontier_21,a.up_credit_21,a.up_x_21],[a.up_frontier_63,a.up_credit_63,a.up_x_63],rtol=0,atol=1e-12)
   assert np.isclose(r["up21_progress"],math.sqrt(3)*r["up63_progress"],rtol=1e-12,atol=1e-12)
  anchor=a.up_anchor_date_63 if a.up_active_63==1 else None
  prior=[q for q in confirmations if q["horizon"]==21 and anchor is not None and anchor<q["date"]<=ds]
  r["S21_up_since_current_S63_up_anchor"]=sum(q["direction"]==1 for q in prior) if anchor else None
  r["S21_down_since_current_S63_up_anchor"]=sum(q["direction"]==-1 for q in prior) if anchor else None
  out.append(r)
 result=pd.DataFrame(out).set_index("day")
 for c in result:
  if c.endswith("_anchor_date") or c.startswith("last_up_date") or c.startswith("last_up_anchor") or c=="short_up_lineage_source":result[c]=result[c].astype("string")
  elif c=="same_up_lineage":result[c]=result[c].astype("boolean")
  elif c in ["ready","both_up_candidates"] or c.startswith("confirmed_"):result[c]=result[c].astype(bool)
  else:result[c]=pd.to_numeric(result[c]).astype(float)
 return result
def main():
 assert not (O/"POINTS_PRELABEL.csv").exists()
 sourcecase=R/"direction_change_channel_preflight_v1/PROTOCOL.json";cases=json.loads(sourcecase.read_text())["cases"];mp={r["symbol"]:r for r in json.loads(M.read_text())};rows=[];daily=[];sources={str(p):sha(p) for p in [M,B4,DU,GG,B5/"evidence.py",B5/"arithmetic.py",R/"e0_frontier_confirmation_preflight_v1/FIXED_WINDOWS_DAILY_PRELABEL.parquet",sourcecase,O/"PROTOCOL.json",Path(__file__)]};qa=[];start=time.perf_counter()
 for sid in sorted(set(x[0] for x in cases)):
  rec=mp[sid];sp=next(p for p in rec["source_sha256"] if p.endswith("/signal.parquet"));assert sha(sp)==rec["source_sha256"][sp];sources[sp]=sha(sp);sources[rec["refs"]["facts"]]=sha(rec["refs"]["facts"])
  f=eligible_prices(pd.read_parquet(sp));windows={}
  for _,ds,_ in [x for x in cases if x[0]==sid]:
   pos=f.index.get_loc(pd.Timestamp(ds));windows[ds]=f.index[max(0,pos-63):min(len(f),pos+22)]
  f=f.loc[:max(v[-1] for v in windows.values())].copy();f["valid_strength_observation"]=np.isfinite(f.volume)&f.volume.gt(0)
  z,j=b4.strength_frame(f,joint=True);ann=annotate(z,j);ff=pd.read_parquet(rec["refs"]["facts"]).reindex(f.index)
  # Rebuild unchanged G on original full E0 event history to verify B4 inputs.
  ee=f[["close","segment_id","valid_strength_observation"]].copy();ee["event"]=0.
  for seg,part in f.groupby("segment_id",sort=False):ee.loc[part.index,"event"]=_event_facts(part)[0].event
  ee=ee.join(z.add_prefix("strength_"));gg,_=gm.classify(ee)
  for name,col in [("grade","g_grade"),("fresh_up","g_fresh_up"),("ready","g_ready")]:
   np.testing.assert_allclose(gg[name].astype(float),ff[col].astype(float),rtol=0,atol=0,equal_nan=True)
  # Existing fixed windows are context and index coverage, not new labels.
  previous=pd.read_parquet(R/"e0_frontier_confirmation_preflight_v1/FIXED_WINDOWS_DAILY_PRELABEL.parquet");old=previous[previous.sid.eq(sid)].set_index("day")
  assert old.index.isin(f.index).all()
  for ds,win in windows.items():
   t=pd.Timestamp(ds);xp,jp=b4.strength_frame(f.loc[:t],joint=True);ap=annotate(xp,jp);pd.testing.assert_frame_equal(ap,ann.loc[:t],check_exact=True)
   a=ann.loc[t].to_dict();a.update(sid=sid,day=ds,original_i_buy=bool(ff.loc[t,"i_buy"]),original_G=ff.loc[t,"g_grade"],original_I=ff.loc[t,"i_target"]);rows.append(a);qa.append(dict(sid=sid,day=ds,prefix_exact=True))
  want=sorted(set(d for win in windows.values() for d in win));sub=ann.loc[want].copy();sub["sid"]=sid;sub["day"]=sub.index;daily.append(sub.reset_index(drop=True))
  print("stock",sid,round(time.perf_counter()-start,2),flush=True)
 p=pd.DataFrame(rows);d=pd.concat(daily);p.to_csv(O/"POINTS_PRELABEL.csv",index=False);d.to_parquet(O/"WINDOWS_PRELABEL.parquet",index=False);dump("FEATURE_SEAL.json",{n:sha(O/n) for n in ["POINTS_PRELABEL.csv","WINDOWS_PRELABEL.parquet"]})
 ctx=R/"price_wide_structure_preflight_v1/FIXED_CASES_WITH_CONTEXT.csv";sources[str(ctx)]=sha(ctx);labels=pd.read_csv(ctx)[["sid","day","name","old_price_net","old_price_status"]];p=p.merge(labels,on=["sid","day"],how="left",validate="one_to_one");p.to_csv(O/"POINTS_WITH_CONTEXT.csv",index=False)
 dump("PREFIX_QA.json",qa);assert all(sha(p)==h for p,h in sources.items());dump("SOURCE_HASHES.json",sources)
 out=dict(points=len(p),stocks=d.sid.nunique(),window_rows=len(d),ready=int(d.ready.sum()),both_up_candidates=int(d.both_up_candidates.sum()),both_up_same_lineage=int((d.both_up_candidates&d.same_up_lineage.eq(True)).sum()),both_up_different_lineage=int((d.both_up_candidates&d.same_up_lineage.eq(False)).sum()),same_lineage_identity_checked=True,new_rules=0,economic_runs=0)
 dump("QA.json",out);dump("OUTPUT_HASHES.json",{p.name:sha(p) for p in O.iterdir() if p.is_file() and p.name!="OUTPUT_HASHES.json"})
 print(json.dumps(out,ensure_ascii=False));print(p[["sid","day","name","S21","S63","up21_progress","up63_progress","same_up_lineage","short_up_lineage_source","S21_up_since_current_S63_up_anchor","S21_down_since_current_S63_up_anchor","last_up_date21","last_up_date63","old_price_net"]].to_string(index=False))
if __name__=="__main__":main()
