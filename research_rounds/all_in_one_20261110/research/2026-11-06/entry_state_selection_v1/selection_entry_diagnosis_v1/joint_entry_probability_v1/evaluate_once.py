from pathlib import Path
import json,hashlib,math,time
import numpy as np,pandas as pd
from scipy.stats import t as tdist
O=Path(__file__).resolve().parent
def clean(x):
 if isinstance(x,dict):return {str(k):clean(v) for k,v in x.items()}
 if isinstance(x,(list,tuple)):return [clean(v) for v in x]
 if isinstance(x,np.ndarray):return clean(x.tolist())
 if isinstance(x,np.integer):return int(x)
 if isinstance(x,np.bool_):return bool(x)
 if isinstance(x,(float,np.floating)):return float(x) if np.isfinite(x) else None
 return x
def dump(n,x):(O/n).write_text(json.dumps(clean(x),ensure_ascii=False,indent=2))
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def cluster(point,influence,g):
 N=len(g);z=np.asarray(influence,float)/N;blocks=(g.entry_t//20).astype(str).to_numpy();stocks=g.sid.astype(str).to_numpy();pairs=np.char.add(np.char.add(blocks,"|"),stocks)
 def vv(keys):
  u,inv=np.unique(keys,return_inverse=True);G=len(u)
  if G<2:return np.nan,G
  sums=np.bincount(inv,weights=z);return G/(G-1)*float(sums@sums),G
 vb,nb=vv(blocks);vs,ns=vv(stocks);vi,ni=vv(pairs);vt=max(0,vb+vs-vi);var=max(vb,vs,vt);df=min(nb,ns)-1;se=math.sqrt(var);rad=float(tdist.ppf(.975,df))*se
 return dict(point=point,se=se,lower=point-rad,upper=point+rad,date_blocks=nb,stocks=ns,intersection_clusters=ni,df=df,date_variance=vb,stock_variance=vs,two_way_variance=vt,n=N)
def auc_if(y,s):
 y=np.asarray(y,int);s=np.asarray(s,float);pos=y==1;neg=~pos;n1=pos.sum();n0=neg.sum();N=len(y)
 if min(n1,n0)==0:return np.nan,np.full(N,np.nan)
 pn=np.sort(s[neg]);pp=np.sort(s[pos]);l=np.searchsorted(pn,s[pos],"left");r=np.searchsorted(pn,s[pos],"right");vp=(l+.5*(r-l))/n0
 l=np.searchsorted(pp,s[neg],"left");r=np.searchsorted(pp,s[neg],"right");vn=(n1-r+.5*(r-l))/n1
 a=float(vp.mean());inf=np.empty(N);inf[pos]=N/n1*(vp-a);inf[neg]=N/n0*(vn-a);assert abs(inf.mean())<1e-10
 return a,inf
def stats_round(g):
 z=g[g.closed];w=z[z.round_pnl>0];l=z[z.round_pnl<=0];N=len(g);ret=z.round_return_on_cumulative_cost
 q=float(ret.quantile(.05)) if len(z) else np.nan
 return dict(n=N,closed=len(z),open=N-len(z),wins=len(w),losses=len(l),closed_winrate=len(w)/len(z) if len(z) else np.nan,all_birth_win_lower=len(w)/N if N else np.nan,all_birth_win_upper=(len(w)+N-len(z))/N if N else np.nan,original_net_cny=z.round_pnl.sum(),positive_net_cny=w.round_pnl.sum(),nonpositive_net_cny=l.round_pnl.sum(),mean_win_cny=w.round_pnl.mean(),mean_loss_cny=l.round_pnl.mean(),original_profit_factor=w.round_pnl.sum()/abs(l.round_pnl.sum()) if l.round_pnl.sum()!=0 else np.nan,mean_return=ret.mean(),mean_win_return=w.round_return_on_cumulative_cost.mean(),mean_loss_return=l.round_return_on_cumulative_cost.mean(),return_payoff_ratio=w.round_return_on_cumulative_cost.mean()/abs(l.round_return_on_cumulative_cost.mean()) if len(l) and l.round_return_on_cumulative_cost.mean()!=0 else np.nan,return_q05=q,return_tail_mean=ret[ret<=q].mean() if len(z) else np.nan,median_holding_sessions=z.holding_sessions.median())
def main():
 start=time.monotonic();assert not (O/"EVALUATION_STARTED.json").exists()
 inf=json.loads((O/"INFERENCE_SUMMARY.json").read_text());assert inf["status"]=="ONE_FROZEN_FORWARD_INFERENCE_COMPLETE"
 source=O/"ORIGINAL_MOBILE_FORWARD_PREDICTIONS.csv";dump("EVALUATION_STARTED.json",dict(source_sha256=sha(source),script_sha256=sha(Path(__file__)),freeze_sha256=sha(O/"FREEZE.json")))
 a=pd.read_csv(source);models=["constant","speed","joint"];assert len(a)==1814 and not a.duplicated(["sid","first_layer","entry_day"]).any()
 for m in models:
  p=a.loc[a.score_known,[m+"_W",m+"_L",m+"_U"]].to_numpy();assert np.isfinite(p).all() and (p>0).all() and np.max(abs(p.sum(1)-1))<1e-10
 aa,ii=auc_if([0,1,0,1],[.1,.4,.4,.8]);assert abs(aa-.875)<1e-12
 cohorts=[]
 for name,g in [("ALL_2022_2026",a),("2023_2025",a[a.signal_year.between(2023,2025)])]+[(str(y),g) for y,g in a.groupby("signal_year")]:
  for context,gg in [("ALL",g),("NORMAL",g[g.context=="NORMAL"])]:
   cohorts.append(dict(cohort=name,context=context,predicted=int(gg.score_known.sum()),mature_H=int(gg.potential_H.sum()),paired_mature_H=int((gg.score_known&gg.potential_H).sum()),stocks=gg.sid.nunique(),signal_dates=gg.signal_day.nunique(),**stats_round(gg)))
 pd.DataFrame(cohorts).to_csv(O/"COHORT_COVERAGE_AND_ACTUAL_ROUNDS.csv",index=False)
 a.groupby(["signal_year","unknown_reason"],dropna=False).size().reset_index(name="n").to_csv(O/"UNKNOWN_PREDICTION_REASONS.csv",index=False)
 primary=a[a.score_known&a.potential_H&a.signal_year.between(2023,2025)].copy()
 proper=[];paired=[];aucs=[];auc_pairs=[];same_date=[];cal=[];resid=[];scoregroups=[];probround=[]
 sets=[("2023_2025",primary)]+[(str(y),primary[primary.signal_year==y]) for y in [2023,2024,2025]]
 for cohort,g0 in sets:
  for context,g in [("ALL",g0),("NORMAL",g0[g0.context=="NORMAL"])]:
   if len(g)==0:continue
   yy=g.y_H.to_numpy(int);hot=np.eye(3)[yy];cache={};acache={}
   for m in models:
    p=g[[m+"_W",m+"_L",m+"_U"]].to_numpy();brier=np.sum((p-hot)**2,axis=1);ll=-np.log(p[np.arange(len(g)),yy]);cache[m]=dict(brier=brier,logloss=ll)
    aw,iw=auc_if((yy==0).astype(int),p[:,0]);acache[m]=(aw,iw);u=p[:,2]
    proper.append(dict(cohort=cohort,context=context,model=m,n=len(g),W=int((yy==0).sum()),L=int((yy==1).sum()),U=int((yy==2).sum()),brier=brier.mean(),logloss=ll.mean(),mean_pW=p[:,0].mean(),mean_pL=p[:,1].mean(),mean_pU=u.mean(),observed_W=np.mean(yy==0),observed_L=np.mean(yy==1),observed_U=np.mean(yy==2)))
    if np.isfinite(aw):aucs.append(dict(cohort=cohort,context=context,model=m,target="positive_complete_exit_by120",**cluster(aw,iw,g)))
    for c,ci in [("W",0),("L",1),("U",2)]:
     bins=np.array([0,.1,.2,.3,.4,.5,1]);bi=np.searchsorted(bins[1:],p[:,ci],side="right")
     for k in range(len(bins)-1):
      mask=bi==k;n=int(mask.sum());cal.append(dict(cohort=cohort,context=context,model=m,outcome=c,bin_lo=bins[k],bin_hi=bins[k+1],n=n,mean_prediction=p[mask,ci].mean() if n else np.nan,observed_fraction=np.mean(yy[mask]==ci) if n else np.nan))
    resid.append(dict(cohort=cohort,context=context,model=m,n=len(g),mean_identification_lower=p[:,0].mean(),mean_identification_upper=(p[:,0]+u).mean(),mean_unresolved=u.mean(),median_unresolved=np.median(u),p90_unresolved=np.quantile(u,.9),max_unresolved=u.max(),observed_U=np.mean(yy==2),mean_posterior_q05_lower=g[m+"_W_q05"].mean(),mean_posterior_q95_upper=g[m+"_upper_q95"].mean()))
    dates=[]
    for day,dd in g.groupby("signal_day"):
     ax,ix=auc_if((dd.y_H==0).astype(int),dd[m+"_W"].to_numpy())
     if np.isfinite(ax):dates.append((day,len(dd),ax))
    same_date.append(dict(cohort=cohort,context=context,model=m,eligible_dates=len(dates),eligible_rows=sum(x[1] for x in dates),all_signal_dates=g.signal_day.nunique(),mean_same_date_auc=np.mean([x[2] for x in dates]) if dates else np.nan))
    if m!="constant":
     for k in range(1,6):
      gg=g[g[m+"_train_group"]==k];scoregroups.append(dict(cohort=cohort,context=context,model=m,training_quintile=k,mean_pW=gg[m+"_W"].mean(),mean_pU=gg[m+"_U"].mean(),known_H_W=int((gg.y_H==0).sum()),known_H_L=int((gg.y_H==1).sum()),unresolved_H=int((gg.y_H==2).sum()),**stats_round(gg)))
    # Fixed probability bins are descriptions, never an adopted entry gate.
    bins=[0,.1,.2,.3,.4,.5,1]
    for lo,hi in zip(bins[:-1],bins[1:]):
     gg=g[(g[m+"_W"]>=lo)&((g[m+"_W"]<hi)|(hi==1))]
     probround.append(dict(cohort=cohort,context=context,model=m,bin_lo=lo,bin_hi=hi,mean_pW=gg[m+"_W"].mean(),mean_pU=gg[m+"_U"].mean(),**stats_round(gg)))
   for m0,m1 in [("joint","constant"),("joint","speed"),("speed","constant")]:
    for metric in ["brier","logloss"]:
     d=cache[m0][metric]-cache[m1][metric];paired.append(dict(cohort=cohort,context=context,comparison=m0+" minus "+m1,metric=metric,**cluster(float(d.mean()),d-d.mean(),g)))
    va,ia=acache[m0];vb,ib=acache[m1]
    if np.isfinite(va) and np.isfinite(vb):auc_pairs.append(dict(cohort=cohort,context=context,comparison=m0+" minus "+m1,target="positive_complete_exit_by120",**cluster(va-vb,ia-ib,g)))
 for name,rows in [("PROPER_SCORES.csv",proper),("PAIRED_CLUSTER_PROPER_SCORES.csv",paired),("AUC_CLUSTER_RESULTS.csv",aucs),("PAIRED_AUC_CLUSTER_RESULTS.csv",auc_pairs),("SAME_DATE_AUC.csv",same_date),("PROBABILITY_CALIBRATION.csv",cal),("UNRESOLVED_PROBABILITY_BOUNDS.csv",resid),("TRAINING_QUINTILE_ACTUAL_OUTCOMES.csv",scoregroups),("FIXED_PROBABILITY_BIN_ACTUAL_OUTCOMES.csv",probround)]:
  pd.DataFrame(rows).to_csv(O/name,index=False)
 # Full-round diagnostic uses original terminal labels only where observed.
 # It is not the same target as W by120 and never treats open rounds as losers.
 finalaucs=[];finalpairs=[];finalsummary=[]
 fsets=[("PRIMARY_H_MATURE",primary),("ALL_SCORED_2023_2025",a[a.score_known&a.signal_year.between(2023,2025)]),("2026_PARTIAL",a[a.score_known&(a.signal_year==2026)])]
 for scope,g0 in fsets:
  for cohort,g in [("ALL",g0)]+[(str(y),z) for y,z in g0.groupby("signal_year")]:
   finalsummary.append(dict(scope=scope,cohort=cohort,**stats_round(g)));gg=g[g.closed];yy=(gg.round_pnl>0).astype(int).to_numpy();cache={}
   if len(gg)==0:continue
   for m in models:
    av,iv=auc_if(yy,gg[m+"_W"].to_numpy());cache[m]=(av,iv)
    if np.isfinite(av):finalaucs.append(dict(scope=scope,cohort=cohort,model=m,score="pW_by120_not_ultimate_point_probability",target="observed_final_original_net_positive",**cluster(av,iv,gg)))
   for m0,m1 in [("joint","constant"),("joint","speed")]:
    aa,ia=cache[m0];bb,ib=cache[m1]
    if np.isfinite(aa) and np.isfinite(bb):finalpairs.append(dict(scope=scope,cohort=cohort,comparison=m0+" minus "+m1,**cluster(aa-bb,ia-ib,gg)))
 pd.DataFrame(finalsummary).to_csv(O/"ACTUAL_FINAL_ROUND_SUMMARY.csv",index=False);pd.DataFrame(finalaucs).to_csv(O/"ACTUAL_FINAL_ROUND_AUC.csv",index=False);pd.DataFrame(finalpairs).to_csv(O/"ACTUAL_FINAL_ROUND_PAIRED_AUC.csv",index=False)
 # Readable predeclared audit cases, no cherry-picking new successes.
 cases=a[((a.sid=="002385.SZ")&(a.signal_day=="2022-03-04"))|((a.sid=="600606.SH")&(a.signal_day=="2022-03-22"))]
 cases.to_csv(O/"TWO_PREDECLARED_CASES.csv",index=False)
 summary=dict(status="ONE_FIXED_DIAGNOSTIC_COMPLETE_NO_POLICY_PROMOTION",births=len(a),scored=int(a.score_known.sum()),primary_mature_H=len(primary),primary_W=int((primary.y_H==0).sum()),primary_L=int((primary.y_H==1).sum()),primary_U=int((primary.y_H==2).sum()),primary_stocks=primary.sid.nunique(),primary_dates=primary.signal_day.nunique(),account_runs=0,parameter_searches=0,new_candidate_reorders=0,new_model_specifications=1,comparison_models=2,first_prediction=a.loc[a.score_known,"signal_day"].min(),history="Repeatedly researched history, not untouched OOS",ultimate_probability="Partially identified interval only; pW is not final win probability",seconds=time.monotonic()-start)
 dump("SUMMARY.json",summary)
 hashes={p.name:sha(p) for p in O.glob("*") if p.is_file() and p.name not in ["OUTPUT_SHA256.json"]}
 dump("OUTPUT_SHA256.json",hashes)
 print(json.dumps(clean(summary),ensure_ascii=False))
 print(pd.DataFrame(proper).query("cohort == \"2023_2025\" and context == \"ALL\"").to_string(index=False))
 print(pd.DataFrame(paired).query("cohort == \"2023_2025\" and context == \"ALL\"").to_string(index=False))
 print(pd.DataFrame(aucs).query("cohort == \"2023_2025\" and context == \"ALL\"").to_string(index=False))
 print(pd.DataFrame(finalaucs).query("scope == \"PRIMARY_H_MATURE\" and cohort == \"ALL\"").to_string(index=False))
if __name__=="__main__":main()
