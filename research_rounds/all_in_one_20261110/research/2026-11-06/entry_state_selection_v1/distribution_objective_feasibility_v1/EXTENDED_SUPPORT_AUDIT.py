"""Read saved cohort labels; exact old causal P/D/C; no economics and no fitting."""
from pathlib import Path
import argparse,ast,hashlib,json,sys,time,warnings
import numpy as np,pandas as pd
warnings.filterwarnings("ignore",category=FutureWarning)
R=Path("/Users/bytedance/Documents/Codex/2026-11-06/entry_state_selection_v1")
O=R/"distribution_objective_feasibility_v1"
E=R/"missing_price_cohort_feasibility_v1/execution_v1"
M=Path("/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/universe-cp1-inputs-20261031/STOCK_MANIFEST.json")
H=Path("/Users/bytedance/Documents/ChatGPT/money/TradingAlarm/runtime/market/update-20261030-153010-c551af/prepared/h1.npz")
TEMPLATE="ORIGINAL_2024_AB_PRICE_165_NET80_STRICT_UNKNOWN_V1"
CUTS=pd.to_datetime(["2024-09-02","2024-10-08","2024-11-01","2024-12-02"])
BN=["Y_le_minus1","Y_minus1_to_0","Y_0_to_1","Y_1_to_3","Y_gt_3"]
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def clean(x):
 if isinstance(x,dict):return {str(k):clean(v) for k,v in x.items()}
 if isinstance(x,(list,tuple,np.ndarray)):return [clean(v) for v in x]
 if isinstance(x,(np.integer,)):return int(x)
 if isinstance(x,(np.bool_,)):return bool(x)
 if isinstance(x,(float,np.floating)):return float(x) if np.isfinite(x) else None
 if isinstance(x,pd.Timestamp):return str(x)
 return x
def dump(name,x):
 p=O/name
 with p.open("x") as f:json.dump(clean(x),f,ensure_ascii=False,indent=2,allow_nan=False);f.write("\n")
def csv(name,x):
 p=O/name;assert not p.exists(),p;x.to_csv(p,index=False)
def parquet(name,x):
 p=O/name;assert not p.exists(),p;x.to_parquet(p,index=False)
def calendar():
 c=pd.DatetimeIndex(np.load(H,allow_pickle=False)["dates"])
 return c[(c>="2013-01-01")&(c<="2026-05-15")]
CAL=calendar()
def load_new(cohort):
 d=E/("economic_"+cohort)
 for n in ["COMPLETE.json","SOURCE_VERIFIED.json","PRICE_LABELS.csv","SUMMARY.json"]:assert (d/n).exists(),("COHORT_NOT_READY",str(d/n))
 x=pd.read_csv(d/"PRICE_LABELS.csv",float_precision="round_trip")
 assert x.owner_lane.eq("PRICE").all() and x.template_id.eq(TEMPLATE).all()
 assert not x.duplicated("decision_dedup_key").any()
 assert x.source_available_at.isna().all()
 for c in ["signal_day","signal_close","entry_day","exit_day","status_day","label_usable_proxy_at","financial_settlement_proxy_at"]:x[c]=pd.to_datetime(x[c],errors="coerce")
 x["ordinary"]=x.ordinary_label_mature
 x["ordinary_known_at"]=x.label_usable_proxy_at
 x["scenario_known_at"]=x.financial_settlement_proxy_at
 x["ordinary_value"]=x.label_net_cny
 x["scenario_value"]=x.financial_scenario_net_cny
 x["scenario_label_available"]=x.financial_settled_label_mature
 x["complete"]=x.status.eq("COMPLETE_CONDITIONAL_STOCK_ROUND")
 x["cohort_id"]=cohort
 x["feature_state"]="NOT_COMPUTED"
 x["t"]=CAL.get_indexer(x.signal_day)
 assert x.t.ge(0).all()
 paths=[d/n for n in ["COMPLETE.json","SOURCE_VERIFIED.json","PRICE_LABELS.csv","SUMMARY.json"]]+[E/"PROTOCOL.md",E/"label_export.py",H]
 return x,{str(p):sha(p) for p in paths}
def bins(values):
 return dict(zip(BN,pd.cut(values,[-np.inf,-3000,0,3000,9000,np.inf],right=True).value_counts(sort=False).astype(int).tolist()))
def support(x,feature_scope):
 results=[];late=[];states=[];asof=[]
 for cut in CUTS:
  t=CAL.get_loc(cut);p=x[x.t.ge(t-504)&x.t.lt(t)].copy()
  enter=p.entered&p.entry_day.lt(cut);cl=p.complete&p.exit_day.lt(cut)
  u=p.status.str.contains("UNKNOWN")&p.status_day.lt(cut)
  noentry=~p.entered&p.status_day.lt(cut)
  q0=noentry&p.status.eq("PRECHECK_Q0_NO_SUBMIT")
  nosub=noentry&~u&~q0
  active=enter&~cl&~u
  known=p.ordinary&p.ordinary_known_at.lt(cut)
  scenario=p.scenario_label_available&p.scenario_known_at.lt(cut)
  if feature_scope=="PDC_KNOWN":elig=p.feature_known
  else:elig=pd.Series(True,index=p.index)
  for scope,flag,val in [("STRICT_ORDINARY",known,"ordinary_value"),("FINANCIAL_SETTLED_ALL",scenario,"scenario_value"),("FINANCIAL_SETTLED_NONORDINARY",scenario&~p.ordinary,"scenario_value")]:
   g=p[flag&elig];v=g[val]
   results.append(dict(cohort=p.cohort_id.iloc[0] if len(p) else x.cohort_id.iloc[0],template_id=x.template_id.iloc[0],cut=str(cut.date()),window_start=str(CAL[t-504].date()),feature_scope=feature_scope,label_scope=scope,n=len(g),W=int(v.gt(0).sum()),L_nonpositive=int(v.le(0).sum()),stocks=g.sid.nunique(),signal_dates=g.signal_day.nunique(),roots=g.price_root.nunique(),right_tail_stocks=g.loc[v.gt(9000),"sid"].nunique(),right_tail_dates=g.loc[v.gt(9000),"signal_day"].nunique(),**bins(v),source_domain="NON_PIT_PROXY"))
  g=p[p.ordinary&~known&elig]
  late.append(dict(cohort=x.cohort_id.iloc[0],template_id=x.template_id.iloc[0],cut=str(cut.date()),feature_scope=feature_scope,purpose="RETROSPECTIVE_ONLY_NOT_KNOWN_AT_CUT",late_ordinary_n=len(g),late_W=int(g.ordinary_value.gt(0).sum()),**bins(g.ordinary_value)))
  st=dict(cohort=x.cohort_id.iloc[0],template_id=x.template_id.iloc[0],cut=str(cut.date()),registered=len(p),entered_asof=int(enter.sum()),ordinary_mature=int(known.sum()),financial_settled_all_mature=int(scenario.sum()),closed_mark_pending_strict=int((cl&~known).sum()),closed_mark_pending_financial=int((cl&~scenario).sum()),held_UNKNOWN=int((enter&u).sum()),active_held=int(active.sum()),q0=int(q0.sum()),no_entry_unknown=int((noentry&u).sum()),known_no_submit_other=int(nosub.sum()),pending_entry=int((~enter&~noentry).sum()))
  assert len(p)==int(known.sum())+int((cl&~known).sum())+st["held_UNKNOWN"]+st["active_held"]+st["q0"]+st["no_entry_unknown"]+st["known_no_submit_other"]+st["pending_entry"]
  states.append(st)
  zz=p[["cohort_id","template_id","round_id","sid","signal_day","price_root","decision_dedup_key"]].copy()
  zz["cut"]=cut
  zz["entry_day_asof"]=p.entry_day.where(enter)
  zz["state_asof"]=np.select([known,cl&~known,enter&u,q0,noentry&u,nosub,active],["ORDINARY_MATURE","EXITED_MARK_PENDING_STRICT","HELD_UNKNOWN","KNOWN_Q0_NO_ENTRY","ENTRY_UNKNOWN","KNOWN_OTHER_NO_SUBMIT","ACTIVE_HELD"],default="ENTRY_PENDING")
  zz["ordinary_label_net_at_cut"]=p.ordinary_value.where(known)
  zz["ordinary_label_known_at"]=p.ordinary_known_at.where(known)
  zz["financial_scenario_net_at_cut"]=p.scenario_value.where(scenario)
  zz["financial_scenario_known_at"]=p.scenario_known_at.where(scenario)
  if "feature_known" in p:zz["feature_known"]=p.feature_known
  asof.append(zz)
 return pd.DataFrame(results),pd.DataFrame(late),pd.DataFrame(states),pd.concat(asof,ignore_index=True)
def save_support(cohort,x,hashes,feature_scope):
 out=support(x,feature_scope);tag=cohort+"_"+feature_scope
 for suffix,d in zip(["MATURE_SUPPORT","LATE_DIAGNOSTIC_ONLY","ASOF_STATES"],out[:3]):csv("EXTENDED_"+tag+"_"+suffix+".csv",d)
 parquet("EXTENDED_"+tag+"_ASOF_LABELS.parquet",out[3])
 assert all(sha(p)==h for p,h in hashes.items())
 dump("EXTENDED_"+tag+"_QA.json",dict(cohort=cohort,source_hashes=hashes,features=feature_scope,source_unchanged=True,models_fit=0,economic_runs=0,rows=len(x),unique_decisions=x.decision_dedup_key.nunique(),source_available_at_unverified=True,no_2022_backfill=True,independent_start_flat_not_account=True))
 print(out[0][out[0].label_scope.eq("STRICT_ORDINARY")].to_csv(index=False),flush=True)
 print(out[2].to_csv(index=False),flush=True)
def features(cohort,x,hashes):
 sys.path.insert(0,"/Users/bytedance/Documents/Codex/2026-11-04/task-3/entry_quality/pvr_information_v1/feature_design")
 from features import original_pvr,original_observation_clock
 import features as feature_module
 env=dict(np=np,pd=pd,fullcal=CAL,original_pvr=original_pvr,original_observation_clock=original_observation_clock)
 for path,names in [(R/"cmf_pvr_component_v1/experiment.py",["calc"]),(R/"pvr_dmi_cmf_round_interaction_v1/preflight.py",["dcalc"])]:
  hashes[str(path)]=sha(path);tree=ast.parse(path.read_text());exec(compile(ast.Module(body=[n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name in names],type_ignores=[]),str(path),"exec"),env)
 hashes[str(M)]=sha(M);hashes[str(Path(feature_module.__file__))]=sha(feature_module.__file__)
 mp={m["symbol"]:m for m in json.loads(M.read_text())};rows=[];prefix=[];start=time.monotonic()
 for no,(sid,g) in enumerate(x.groupby("sid",sort=True)):
  m=mp[sid];path=next(p for p in m["source_sha256"] if p.endswith("/signal.parquet"));h=sha(path);assert h==m["source_sha256"][path];hashes[path]=h
  p=pd.read_parquet(path).loc[:g.signal_day.max()]
  z=env["calc"](p);d,age=env["dcalc"](p)
  for _,r in g.iterrows():
   day=r.signal_day;P=r.PVR_score;D=d.loc[day] if day in d.index else np.nan;C=z.loc[day,"CMF21"] if day in z.index else np.nan;recon=z.loc[day,"score"] if day in z.index else np.nan;err=abs(recon-P)
   rk=pd.notna(r.price_root) and not any(s in str(r.price_root) for s in ["None","nan"])
   known=bool(np.isfinite(P) and np.isfinite(D) and np.isfinite(C) and np.isfinite(err) and err<1e-8 and rk)
   rows.append(dict(cohort_id=cohort,round_id=r.round_id,sid=sid,signal_day=day,P=P,D=D,C=C,pvr_error=err,root_known=rk,feature_known=known))
  if no%125==0:
   day=g.signal_day.min();zz=env["calc"](p.loc[:day]);dd,_=env["dcalc"](p.loc[:day])
   assert np.allclose([zz.loc[day,"score"],zz.loc[day,"CMF21"],dd.loc[day]],[z.loc[day,"score"],z.loc[day,"CMF21"],d.loc[day]],equal_nan=True,atol=1e-12,rtol=0)
   prefix.append(dict(sid=sid,cut=str(day.date()),passed=True))
  if (no+1)%300==0:print("FEATURE_PROGRESS",cohort,no+1,round(time.monotonic()-start,1),flush=True)
 f=pd.DataFrame(rows);assert len(f)==len(x) and f.round_id.is_unique
 assert all(sha(p)==h for p,h in hashes.items())
 parquet("EXTENDED_"+cohort+"_PDC_FEATURES.parquet",f)
 dump("EXTENDED_"+cohort+"_PDC_FEATURE_QA.json",dict(prefix_checks=prefix,rows=len(f),features_known=int(f.feature_known.sum()),max_finite_PVR_error=float(f.pvr_error.max()),source_hashes=hashes,exact_old_functions_reused=True,models_fit=0,economic_runs=0))
 return x.merge(f[["round_id","P","D","C","root_known","feature_known","pvr_error"]],on="round_id",how="left",validate="one_to_one"),hashes
def main():
 ap=argparse.ArgumentParser();ap.add_argument("--cohort",required=True,choices=["2023","2024JanAug"]);ap.add_argument("--phase",required=True,choices=["all_labels","features"]);args=ap.parse_args()
 x,h=load_new(args.cohort)
 if args.phase=="all_labels":save_support(args.cohort,x,h,"ALL_LABELS")
 else:
  x,h=features(args.cohort,x,h);save_support(args.cohort,x,h,"PDC_KNOWN")
if __name__=="__main__":main()
