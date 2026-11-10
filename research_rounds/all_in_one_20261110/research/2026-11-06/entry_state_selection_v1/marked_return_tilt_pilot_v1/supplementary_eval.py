"""Read sealed predictions only: no fitting, tuning, or economic replay."""
from pathlib import Path
import importlib.util,json
import numpy as np,pandas as pd
O=Path(__file__).resolve().parent
sp=importlib.util.spec_from_file_location('pilot',O/'run_pilot.py');p=importlib.util.module_from_spec(sp);sp.loader.exec_module(p)
seal=json.loads((O/'PREDICTION_SEAL.json').read_text());assert seal['predictions_sha256']==p.sha(O/'PREDICTIONS.parquet') and seal['models_sha256']==p.sha(O/'MONTHLY_MODELS.json')
x=pd.read_parquet(O/'PREDICTIONS_WITH_FINAL_DIAGNOSTICS.parquet');ob=pd.read_parquet(O/'ASOF_OBSERVATIONS.parquet');models=json.loads((O/'MONTHLY_MODELS.json').read_text());ages=[];nums=[];ks=[];slow=[]
for m in models:
 cut=pd.Timestamp(m['cut']);tr=ob[ob.cut.eq(cut)&ob.feature_known];sc=[np.array(v) for v in m['scaling']];X,_=p.design(tr,sc);eta=X[:,1:]@np.array(m['marked_beta']);z=x[x.cut.eq(cut)&x.feature_known];V,_=p.design(z,sc);ev=V[:,1:]@np.array(m['marked_beta']);maxe=0
 for g,bb in enumerate(m['baselines']):
  b={**bb,'Y':np.array(bb['Y']),'q':np.array(bb['q'])};_,_,_,prob=p.moments(eta,b,True);cp=prob/np.maximum(prob.sum(axis=1)[:,None],np.finfo(float).tiny);top=cp.max(axis=1);top5=np.sort(cp,axis=1)[:,-5:].sum(axis=1)
  maxe=max(maxe,float(np.max(abs(ev[:,None]*b['Y'][None,:]))))
  ages.append(dict(cut=str(cut.date()),age_group=g,ordinary_atoms=len(b['Y']),N=b['N'],train_projection_rows=len(tr),top1_min=top.min(),top1_p50=np.median(top),top1_p99=np.quantile(top,.99),top1_max=top.max(),top5_max=top5.max(),note='Conditional ordinary mark distribution within this age; includes121+, not H120 F. No refit.'))
 nums.append(dict(cut=str(cut.date()),iterations=m['marked_QA']['iterations'],gradient_max=m['marked_QA']['gradient_max'],hessian_eigen_min=min(m['marked_QA']['hessian_eigenvalues']),hessian_eigen_max=max(m['marked_QA']['hessian_eigenvalues']),train_all_age_max_abs_etaY=m['max_abs_etaY_training'],validation_H120_max_abs_etaY=m['max_abs_etaY_validation'],validation_all_age_max_abs_etaY=maxe,maxY_fixed_q_scaler_local_beta_delta_L2=m['influence']['delta_L2'],delta_over_beta_L2=m['influence']['delta_over_beta_L2']))
for month,g in [('ALL',x)]+list(x.groupby('month')):
 for arm in ['original','beta0','pvr','binary','marked']:
  z=g[g.ordinary&g.entered&g.Q.notna()&g['select_'+arm]];ks.append(dict(month=month,arm=arm,scope='SCORE_KNOWN_STRICT_ORDINARY',**p.outcome(z)))
  ordinary=g[g.ordinary&g.entered].copy();ages_=p.CAL.get_indexer(ordinary.exit_day)-p.CAL.get_indexer(ordinary.entry_day)+1;ordinary['exit_age']=ages_
  for label,mask in [('EXIT_BY_120',ordinary.exit_age<=120),('EXIT_AFTER_120',ordinary.exit_age>120)]:slow.append(dict(month=month,arm=arm,exit_age_scope=label,**p.outcome(ordinary[mask&ordinary['select_'+arm]])))
p.csv('ALL_AGE_ATOM_CONCENTRATION.csv',ages);p.csv('NUMERICAL_AND_INFLUENCE_SUMMARY.csv',nums);p.csv('KNOWN_SCORE_OUTCOMES.csv',ks);p.csv('EARLY_VS_LATE_TERMINAL_OUTCOMES.csv',slow)
assert seal['predictions_sha256']==p.sha(O/'PREDICTIONS.parquet') and seal['models_sha256']==p.sha(O/'MONTHLY_MODELS.json')
p.dump('SUPPLEMENTARY_QA.json',dict(refits=0,parameter_changes=0,economic_runs=0,predictions_unchanged=True,models_unchanged=True,clarification='Saved forecast top1/top5 and validation etaY stop atH120. This table exposes all five age groups. Global maximumY is121+ so itsH120 direct mass0 is not a robustness result.'))
print(pd.DataFrame(nums).to_string(index=False));print(pd.DataFrame(ages).query('age_group==4').to_string(index=False));print(pd.DataFrame(ks).query("month=='ALL'").to_string(index=False));print(pd.DataFrame(slow).query("month=='ALL' and arm in ['original','marked']").to_string(index=False))
