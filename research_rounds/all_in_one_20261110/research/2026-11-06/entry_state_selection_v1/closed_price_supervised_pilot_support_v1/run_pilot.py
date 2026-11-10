"""Frozen PRICE-only static supervised pilot. prepare=features/ledger joins; fit=no economics."""
from pathlib import Path
import sys,json,hashlib,ast,time
import numpy as np,pandas as pd
O=Path(__file__).resolve().parent
R=O.parent
M=Path("/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/universe-cp1-inputs-20261031/STOCK_MANIFEST.json")
H=Path("/Users/bytedance/Documents/ChatGPT/money/TradingAlarm/runtime/market/update-20261030-153010-c551af/prepared/h1.npz")
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def clean(x):
 if isinstance(x,dict):return {str(k):clean(v) for k,v in x.items()}
 if isinstance(x,(list,tuple,np.ndarray)):return [clean(v) for v in x]
 if isinstance(x,(np.integer,)):return int(x)
 if isinstance(x,(np.bool_,)):return bool(x)
 if isinstance(x,(float,np.floating)):return float(x) if np.isfinite(x) else None
 if isinstance(x,pd.Timestamp):return str(x)
 return x
def dump(n,x):(O/n).write_text(json.dumps(clean(x),ensure_ascii=False,indent=2,allow_nan=False)+"\n")
def calendar():
 c=pd.DatetimeIndex(np.load(H,allow_pickle=False)["dates"])
 return c[(c>="2013-01-01")&(c<="2026-05-15")]
def prepare():
 assert not (O/"ALL_ORIGINAL_PRICE_ROWS.parquet").exists()
 sources={str(p):sha(p) for p in [M,H,O/"PROTOCOL.json",Path(__file__),R/"cmf_pvr_component_v1/experiment.py",R/"pvr_dmi_cmf_round_interaction_v1/preflight.py"]}
 sys.path.insert(0,"/Users/bytedance/Documents/Codex/2026-11-04/task-3/entry_quality/pvr_information_v1/feature_design")
 from features import original_pvr,original_observation_clock
 global fullcal
 fullcal=calendar();env=dict(np=np,pd=pd,fullcal=fullcal,original_pvr=original_pvr,original_observation_clock=original_observation_clock)
 import features
 sources[str(Path(features.__file__))]=sha(features.__file__)
 for path,names in [(R/"cmf_pvr_component_v1/experiment.py",["calc"]),(R/"pvr_dmi_cmf_round_interaction_v1/preflight.py",["dcalc"])]:
  tree=ast.parse(path.read_text());exec(compile(ast.Module(body=[n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name in names],type_ignores=[]),str(path),"exec"),env)
 calc,dcalc=env["calc"],env["dcalc"]
 mp={m["symbol"]:m for m in json.loads(M.read_text())};parts=[];ledgerqa=[]
 for w in ("2022","2024"):
  E=R/f"independent_channel_joint_economic_v1/economic_{w}";J=E/"joint"
  files=[E/"COMPARISON_REPORT_RECOVERED.json"]+[J/n for n in ["ROUNDS.csv","ACTIONS.csv","CLAIMS.json","CLAIM_LEDGER.csv","BRIDGES.json","REGISTRATIONS.csv","LEDGER_QA.json"]]
  for p in files:sources[str(p)]=sha(p)
  r=pd.read_csv(J/"ROUNDS.csv",float_precision="round_trip");r=r[r.owner_lane.eq("PRICE")].copy();r["window_label"]=w
  rep=json.loads((E/"COMPARISON_REPORT_RECOVERED.json").read_text())
  cov=pd.DataFrame(rep["round_coverage"]);cov=cov[cov.arm.eq("joint")][["round_id","financial_covered","reason"]].rename(columns={"reason":"financial_reason"})
  r=r.merge(cov,on="round_id",how="left",validate="one_to_one")
  claims=json.loads((J/"CLAIMS.json").read_text());bridges=json.loads((J/"BRIDGES.json").read_text())
  cl=pd.read_csv(J/"CLAIM_LEDGER.csv");regs=pd.read_csv(J/"REGISTRATIONS.csv")
  touched=set(x.get("owner_round_id") for x in claims)|set(x.get("round_id") for x in bridges)|set(cl.round_id)|set(regs.owner_round_id)
  r["rights_touched"]=r.round_id.isin(touched)
  r["has_claim"]=r.round_id.isin([x.get("owner_round_id") for x in claims])
  r["has_bridge"]=r.round_id.isin([x.get("round_id") for x in bridges])
  qa=pd.DataFrame(json.loads((J/"LEDGER_QA.json").read_text())).set_index("round_id")
  acts=pd.read_csv(J/"ACTIONS.csv",float_precision="round_trip");acts["day"]=pd.to_datetime(acts.day)
  acts["cash"]=np.where(acts.side.str.startswith("buy"),-acts.q*acts.price-acts.fee,acts.q*acts.price-acts.fee)
  acts["dq"]=np.where(acts.side.str.startswith("buy"),acts.q,-acts.q)
  ag=acts.groupby("round_id").agg(action_cash=("cash","sum"),action_qty=("dq","sum"),action_fees=("fee","sum"),first_action=("day","min"),last_action=("day","max"))
  r=r.merge(ag,left_on="round_id",right_index=True,how="left",validate="one_to_one")
  r["entered"]=r.round_id.isin(acts[acts.side.eq("buy_core")&acts.q.gt(0)].round_id)
  for col in ["signal_day","entry_day","exit_day"]:r[col]=pd.to_datetime(r[col])
  r["complete"]=r.status.eq("COMPLETE_CONDITIONAL_STOCK_ROUND")
  r["ordinary"]=r.complete&r.financial_covered.eq(True)&r.financial_reason.eq("LOCAL_NO_ACTION_EVIDENCE")&~r.rights_touched
  for col in ["core_qty","add_qty","dividend_at_termination","receivable_at_termination","receivable_after_payouts","dividend_net80_total","dividend_net80_paid"]:
   r["ordinary"] &= r[col].eq(0)
  r["ordinary"] &= r.action_qty.eq(0)&r.first_action.eq(r.entry_day)&r.last_action.eq(r.exit_day)
  r["ordinary"] &= (r.action_cash-r.net_pnl).abs().lt(1e-7)&(r.action_cash-r.cashflow_to_date).abs().lt(1e-7)&(r.action_cash-r.cash_after_payouts).abs().lt(1e-7)
  r["ordinary"] &= r.round_id.map(qa.reconciled).eq(True)&r.round_id.map(qa.qty).eq(0)&r.round_id.map(qa.paid).eq(0)&r.round_id.map(qa.receivable).eq(0)
  r["ordinary"] &= (r.action_cash-r.round_id.map(qa.trade_cash)).abs().lt(1e-7)&(r.action_fees-r.round_id.map(qa.fees)).abs().lt(1e-7)
  r["eval_financial_known"]=r.complete&r.financial_covered.eq(True)&r.round_id.map(qa.reconciled).eq(True)&r.core_qty.eq(0)&r.add_qty.eq(0)&np.isfinite(r.net_pnl)
  r["label_known_at_proxy"]=r.exit_day.where(r.ordinary)+pd.Timedelta(hours=15)
  assert int(r.ordinary.sum())=={"2022":1882,"2024":1032}[w]
  ledgerqa.append(dict(window=w,registered=len(r),entered=int(r.entered.sum()),complete=int(r.complete.sum()),ordinary=int(r.ordinary.sum()),ordinary_cash_error=float((r.loc[r.ordinary,"action_cash"]-r.loc[r.ordinary,"net_pnl"]).abs().max()),rights_touched=int(r.rights_touched.sum())))
  parts.append(r)
 r=pd.concat(parts,ignore_index=True);r["window"]=r.window.astype(str);out=[];prefix=[];start=time.time()
 for no,(sid,g) in enumerate(r.groupby("sid",sort=True)):
  m=mp[sid];path=next(p for p in m["source_sha256"] if p.endswith("/signal.parquet"));h=sha(path);assert h==m["source_sha256"][path];sources[path]=h
  p=pd.read_parquet(path).loc[:g.signal_day.max()]
  z=calc(p);d,age=dcalc(p)
  for idx,row in g.iterrows():
   day=row.signal_day;P=z.loc[day,"score"] if day in z.index else np.nan;C=z.loc[day,"CMF21"] if day in z.index else np.nan;D=d.loc[day] if day in d.index else np.nan
   err=abs(P-row.PVR_score)
   out.append(dict(idx=idx,P=row.PVR_score,D=D,C=C,feature_known=bool(np.isfinite(row.PVR_score) and np.isfinite(D) and np.isfinite(C) and err<1e-8),pvr_error=err))
  if no%125==0:
   day=g.signal_day.min();zz=calc(p.loc[:day]);dd,_=dcalc(p.loc[:day])
   assert np.allclose([zz.loc[day,"score"],zz.loc[day,"CMF21"],dd.loc[day]],[z.loc[day,"score"],z.loc[day,"CMF21"],d.loc[day]],equal_nan=True,atol=1e-12,rtol=0)
   prefix.append(dict(sid=sid,day=str(day.date()),passed=True))
  if (no+1)%300==0:print("FEATURE_PROGRESS",no+1,round(time.time()-start,1),flush=True)
 f=pd.DataFrame(out).set_index("idx").sort_index();r=r.join(f);r["t"]=fullcal.get_indexer(r.signal_day)
 r["root_known"]=r.price_root.notna()&~r.price_root.astype(str).str.contains("None|nan",regex=True)
 r["feature_known"] &= r.root_known
 assert not r.round_id.duplicated().any()
 assert int((r.ordinary&r.feature_known&r.window_label.eq("2022")).sum())==1642
 assert int((r.ordinary&r.feature_known&r.window_label.eq("2024")).sum())==951
 r.to_parquet(O/"ALL_ORIGINAL_PRICE_ROWS.parquet",index=False)
 dump("PREPARE_QA.json",dict(ledger=ledgerqa,prefix=prefix,rows=len(r),stocks=r.sid.nunique(),max_PVR_error=r.pvr_error.max(),economic_runs=0,model_fits=0,feature_serialization_note="Identical frozen features re-evaluated once to persist rows after initial stdout-only support calculation; no feature variants."))
 assert all(sha(p)==h for p,h in sources.items())
 dump("INPUT_HASHES.json",sources);dump("PREPARE_SEAL.json",dict(table_sha256=sha(O/"ALL_ORIGINAL_PRICE_ROWS.parquet"),protocol_sha256=sha(O/"PROTOCOL.json"),script_sha256=sha(__file__)))
 print("PREPARE_DONE",json.dumps(clean(ledgerqa)),flush=True)
def sigmoid(z):return 1/(1+np.exp(-np.clip(z,-35,35)))
def scale(x):
 med=np.median(x,axis=0);s=(np.quantile(x,.75,axis=0)-np.quantile(x,.25,axis=0))/1.349
 if not np.isfinite(s).all() or (s<=0).any():raise ValueError("ZERO_OR_INVALID_ROBUST_SCALE")
 return med,s
def design(g,sc=None):
 x=g[["P","D","C"]].to_numpy(float)
 if sc is None:
  med,s=scale(x);z=np.clip((x-med)/s,-5,5);v=np.column_stack([z[:,0]*z[:,1],z[:,0]*z[:,2]]);im,is_=scale(v);sc=[med,s,im,is_]
 else:
  med,s,im,is_=sc;z=np.clip((x-med)/s,-5,5);v=np.column_stack([z[:,0]*z[:,1],z[:,0]*z[:,2]])
 iz=np.clip((v-im)/is_,-5,5);return np.column_stack([np.ones(len(g)),z,iz]),sc
def fit_logit(X,y,pen):
 b=np.zeros(X.shape[1]);b[0]=np.log((y.sum()+.5)/(len(y)-y.sum()+.5))
 def obj(bb):
  z=X@bb;return np.sum(np.logaddexp(0,z)-y*z)+.5*np.sum(pen*bb*bb)
 for it in range(100):
  p=sigmoid(X@b);grad=X.T@(p-y)+pen*b
  if np.max(abs(grad))<1e-6:break
  h=X.T@((p*(1-p))[:,None]*X)+np.diag(pen)
  step=np.linalg.solve(h,grad);a=1.;old=obj(b)
  while a>1e-12 and obj(b-a*step)>old+1e-10:a*=.5
  b-=a*step
 grad=X.T@(sigmoid(X@b)-y)+pen*b
 if np.max(abs(grad))>=1e-6:raise ValueError("GRADIENT_NOT_CONVERGED")
 return b,dict(iterations=it+1,gradient_max=float(np.max(abs(grad))),objective=float(obj(b)))
def fit():
 assert not (O/"PREDICTIONS.parquet").exists()
 assert not (O/"FIT_STARTED.json").exists()
 seal=json.loads((O/"PREPARE_SEAL.json").read_text())
 assert sha(O/"ALL_ORIGINAL_PRICE_ROWS.parquet")==seal["table_sha256"]
 assert sha(O/"PROTOCOL.json")==seal["protocol_sha256"]
 assert sha(__file__)==seal["script_sha256"]
 for p,h in json.loads((O/"INPUT_HASHES.json").read_text()).items():assert sha(p)==h,(p,"SOURCE_DRIFT")
 dump("FIT_STARTED.json",dict(utc=str(pd.Timestamp.now(tz="UTC")),protocol_sha256=sha(O/"PROTOCOL.json"),script_sha256=sha(__file__),prediction_variants=2,parameter_scan=False))
 r=pd.read_parquet(O/"ALL_ORIGINAL_PRICE_ROWS.parquet");cal=calendar()
 test=r[(r.window_label.eq("2022")&r.signal_day.ge("2022-07-01"))|r.window_label.eq("2024")].copy()
 test["p_interaction"]=np.nan;test["p_pvr"]=np.nan;test["p0"]=np.nan;test["model_cut"]=pd.NaT;test["model_reason"]="NOT_FIT"
 models=[];trainids=[];delay=[];poison=[]
 for mo in sorted(test.signal_day.dt.to_period("M").astype(str).unique()):
  day=cal[cal.to_period("M").astype(str)==mo][0];cut=cal.get_loc(day)
  prior=r[r.t.ge(cut-504)&r.t.lt(cut)]
  tr=prior[prior.ordinary&prior.feature_known&prior.exit_day.lt(day)]
  y=tr.net_pnl.gt(0).astype(float).to_numpy()
  n=len(tr);W=int(y.sum());L=n-W
  rec=dict(month=mo,cut=str(day.date()),window_start=str(cal[max(0,cut-504)].date()),n=n,W=W,L=L,dates=tr.signal_day.nunique(),stocks=tr.sid.nunique(),roots=tr.price_root.nunique(),p0=float(y.mean()) if n else None)
  ok=n>=300 and W>=50 and L>=50 and rec["dates"]>=60 and rec["stocks"]>=100 and rec["roots"]>=200
  ids=test.index[test.signal_day.dt.to_period("M").astype(str).eq(mo)];knownids=ids[test.loc[ids,"feature_known"].to_numpy(bool)]
  rec["support_ok"]=bool(ok);reason="SUPPORT_UNKNOWN"
  if ok:
   try:
    X,sc=design(tr);rank=np.linalg.matrix_rank(X);cond=np.linalg.cond(X)
    rec.update(rank=int(rank),condition=float(cond))
    if rank!=6 or not np.isfinite(cond) or cond>=1e6:raise ValueError("DESIGN_RANK_OR_CONDITION")
    bi,qi=fit_logit(X,y,np.array([0,4,4,4,16,16.]))
    bp,qp=fit_logit(X[:,:2],y,np.array([0,4.]))
    T,_=design(test.loc[knownids],sc)
    rec.update(interaction_beta=bi.tolist(),pvr_beta=bp.tolist(),scaling=[a.tolist() for a in sc],interaction_QA=qi,pvr_QA=qp)
    # Poison every unavailable final label; exact train identities and fitted coefficients must remain.
    poisoned=r.copy();unavailable=~(r.ordinary&r.feature_known&r.exit_day.lt(day)&r.t.ge(cut-504)&r.t.lt(cut))
    poisoned.loc[unavailable,"net_pnl"]=1e100
    pt=poisoned[~unavailable];PX,psc=design(pt);py=pt.net_pnl.gt(0).astype(float).to_numpy()
    b2,_=fit_logit(PX,py,np.array([0,4,4,4,16,16.]))
    assert tr.round_id.tolist()==pt.round_id.tolist() and np.array_equal(bi,b2)
    poison.append(dict(month=mo,unavailable_labels_poisoned=int(unavailable.sum()),coefficients_exact=True))
    test.loc[knownids,"p_interaction"]=sigmoid(T@bi);test.loc[knownids,"p_pvr"]=sigmoid(T[:,:2]@bp)
    test.loc[ids,"p0"]=y.mean();test.loc[ids,"model_cut"]=day
    reason="KNOWN"
   except (ValueError,np.linalg.LinAlgError) as ex:reason=str(ex);rec["failure"]=reason
  test.loc[ids,"model_reason"]=reason
  rec["known_predictions"]=int(test.loc[ids,"p_interaction"].notna().sum());models.append(rec)
  trainids.extend(dict(month=mo,round_id=x) for x in tr.round_id)
  # Descriptive delayed-label audit only, not model inputs or p0.
  late=prior[prior.entered&~(prior.ordinary&prior.exit_day.lt(day))]
  lateordinary=late[late.ordinary&late.feature_known]
  delay.append(dict(month=mo,prior_registered=len(prior),prior_entered=int(prior.entered.sum()),ordinary_features_available=n,all_unavailable=int(len(late)),later_ordinary_features=len(lateordinary),later_ordinary_W=int(lateordinary.net_pnl.gt(0).sum()),later_ordinary_L=int(lateordinary.net_pnl.le(0).sum()),never_known_financial_at_source=int((~late.eval_financial_known).sum())))
  print("MONTH",json.dumps(clean(rec)),flush=True)
 test["select_original"]=True
 for model,col in [("pvr","p_pvr"),("interaction","p_interaction")]:
  test["select_"+model]=test[col].isna()|test[col].ge(test.p0)
 test.to_parquet(O/"PREDICTIONS.parquet",index=False)
 pd.DataFrame(trainids).to_csv(O/"TRAINING_IDENTITIES.csv",index=False)
 pd.DataFrame(delay).to_csv(O/"DELAYED_LABEL_AUDIT.csv",index=False)
 dump("MONTHLY_MODELS.json",models);dump("FUTURE_LABEL_POISON_QA.json",poison)
 dump("PREDICTION_SEAL.json",dict(predictions_sha256=sha(O/"PREDICTIONS.parquet"),models_sha256=sha(O/"MONTHLY_MODELS.json"),training_ids_sha256=sha(O/"TRAINING_IDENTITIES.csv"),all_predictions_saved_before_outcome_reports=True,script_sha256=sha(__file__),protocol_sha256=sha(O/"PROTOCOL.json")))
 print("FIT_DONE",len(models),flush=True)
def outcomes(g):
 p=g.net_pnl;w=p[p>0];l=p[p<0];ret=g.net_return_on_buy_cash
 return dict(n=len(g),stocks=g.sid.nunique(),W=len(w),L_nonpositive=int(p.le(0).sum()),loss_negative=len(l),Z=int(p.eq(0).sum()),winrate=float(p.gt(0).mean()) if len(g) else None,old_net_sum=float(p.sum()),mean_net=float(p.mean()) if len(g) else None,mean_win=float(w.mean()) if len(w) else None,mean_loss=float(l.mean()) if len(l) else None,payoff=float(w.mean()/abs(l.mean())) if len(w) and len(l) else None,profit_factor=float(w.sum()/abs(l.sum())) if len(l) else None,mean_return=float(ret.mean()) if len(g) else None,tail30=int(ret.ge(.3).sum()),tail30_old_net=float(g.loc[ret.ge(.3),"net_pnl"].sum()))
def auc(y,p):
 y=np.asarray(y,dtype=bool);p=pd.Series(np.asarray(p))
 return float((p.rank(method="average")[y].sum()-y.sum()*(y.sum()+1)/2)/(y.sum()*(len(y)-y.sum()))) if y.any() and (~y).any() else None
def evaluate():
 seal=json.loads((O/"PREDICTION_SEAL.json").read_text());assert sha(O/"PREDICTIONS.parquet")==seal["predictions_sha256"]
 r=pd.read_parquet(O/"PREDICTIONS.parquet");rows=[];coverage=[];quality=[];tails=[]
 for window,g in r.groupby("window_label"):
  for model in ["original","pvr","interaction"]:
   s=g[g["select_"+model]]
   cov=dict(window=window,model=model,registered=len(g),selected_registered=len(s),registered_select_rate=len(s)/len(g),filled=int(g.entered.sum()),selected_filled=int(s.entered.sum()),filled_select_rate=float(s.entered.sum()/g.entered.sum()),known_score=int(g.p_interaction.notna().sum()),unknown_score=int(g.p_interaction.isna().sum()),unknown_fallback_filled=int((s.entered&s.p_interaction.isna()).sum()),selected_closed=int((s.entered&s.complete).sum()),selected_financial_unknown_closed=int((s.entered&s.complete&~s.eval_financial_known).sum()),selected_path_unknown_or_unclosed=int((s.entered&~s.complete).sum()),selected_not_entered=int((~s.entered).sum()))
   coverage.append(cov)
   for scope,mask in [("ORDINARY_SETTLED",g.ordinary),("ALL_FINANCIAL_KNOWN_CLOSED",g.eval_financial_known)]:
    z=g[mask&g.entered&g["select_"+model]];rows.append(dict(window=window,model=model,scope=scope,**outcomes(z)))
    removed=g[mask&g.entered&~g["select_"+model]];base=g[mask&g.entered]
    tails.append(dict(window=window,model=model,scope=scope,baseline_W=int(base.net_pnl.gt(0).sum()),lost_W=int(removed.net_pnl.gt(0).sum()),lost_old_positive_cash=float(removed.loc[removed.net_pnl.gt(0),"net_pnl"].sum()),lost_L=int(removed.net_pnl.lt(0).sum()),lost_old_negative_cash=float(removed.loc[removed.net_pnl.lt(0),"net_pnl"].sum()),baseline_tail30=int(base.net_return_on_buy_cash.ge(.3).sum()),lost_tail30=int(removed.net_return_on_buy_cash.ge(.3).sum())))
  for scope,mask in [("ORDINARY_SETTLED",g.ordinary),("ALL_FINANCIAL_KNOWN_CLOSED",g.eval_financial_known)]:
   z=g[mask&g.entered&g.p_interaction.notna()&g.p_pvr.notna()&g.p0.notna()]
   y=z.net_pnl.gt(0).astype(float).to_numpy()
   for name,col in [("constant","p0"),("pvr","p_pvr"),("interaction","p_interaction")]:
    p=np.clip(z[col].to_numpy(),1e-12,1-1e-12)
    same=[auc(x.net_pnl.gt(0),x[col]) for _,x in z.groupby("signal_day")]
    same=[x for x in same if x is not None]
    quality.append(dict(window=window,scope=scope,model=name,n=len(z),auc=auc(y,p),same_date_auc_mean=float(np.mean(same)) if same else None,same_date_eligible_dates=len(same),brier=float(np.mean((p-y)**2)),logloss=float(np.mean(-y*np.log(p)-(1-y)*np.log(1-p))),mean_p=float(np.mean(p)),actual_winrate=float(np.mean(y))))
 pd.DataFrame(rows).to_csv(O/"OUTCOMES.csv",index=False);pd.DataFrame(coverage).to_csv(O/"COVERAGE.csv",index=False);pd.DataFrame(tails).to_csv(O/"LOST_WINNERS_AND_TAILS.csv",index=False);pd.DataFrame(quality).to_csv(O/"PROBABILITY_QUALITY.csv",index=False)
 r[r.entered&~r.select_interaction].to_csv(O/"REJECTED_ORIGINAL_FILLED_RECORDS.csv",index=False)
 dump("RESULT_SUMMARY.json",dict(outcomes=rows,coverage=coverage,quality=quality,tails=tails,model_specs=2,baseline_constants=10,parameter_scans=0,economic_runs=0,account_runs=0))
 print("RESULT",json.dumps(clean(dict(outcomes=rows,coverage=coverage,quality=quality,tails=tails))),flush=True)
if __name__=="__main__":
 {"prepare":prepare,"fit":fit,"evaluate":evaluate}[sys.argv[1]]()
