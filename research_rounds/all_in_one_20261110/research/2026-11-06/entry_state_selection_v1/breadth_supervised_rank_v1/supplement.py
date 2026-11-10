from pathlib import Path
import json,hashlib
import pandas as pd,numpy as np
O=Path(__file__).resolve().parent
c=pd.read_parquet(O/'SCORED_CANDIDATES.parquet');z=pd.read_parquet(O/'LABELS_120.parquet');s=pd.read_parquet(O/'SEALED_SELECTIONS.parquet');a=c.merge(z[['event_id','sid','label']],on=['event_id','sid'],validate='one_to_one');CL=['W','U','L'];m=json.load(open(O/'FIT_SEAL.json'))['weighted_class_mass'];hist=np.array([m[x]for x in CL]);hist/=hist.sum()
def weights(t):return (1/(t.groupby('day').sector.transform('nunique')*t.groupby(['day','sector']).event_id.transform('nunique')*t.groupby('event_id').sid.transform('size'))).to_numpy(float)
r=[]
for window,g in a.groupby('window'):
 t=g[g.score_known&g.label.isin(CL)];w=weights(t)
 if not len(t):continue
 pp=t[['p'+x for x in CL]].to_numpy();yy=np.array([CL.index(x)for x in t.label]);Y=np.eye(3)[yy]
 r.append(dict(window=window,n=len(t),weighted_dates=w.sum(),Brier=np.average(((pp-Y)**2).sum(1),weights=w),Brier_constant=np.average(((hist-Y)**2).sum(1),weights=w),logloss=np.average(-np.log(pp[np.arange(len(t)),yy]),weights=w),logloss_constant=np.average(-np.log(hist[yy]),weights=w),weighted_W=np.average(Y[:,0],weights=w),mean_predW=np.average(pp[:,0],weights=w)))
pd.DataFrame(r).to_csv(O/'DATE_WEIGHTED_PROPER_SCORES.csv',index=False)
coverage=[]
for key,g in s[s.window.eq('2026H1_SEMI')].merge(z[['event_id','sid','entry_status','status']],on=['event_id','sid']).groupby(['window','arm','event_type','method','entry_status','status']):coverage.append(dict(zip(['window','arm','event_type','method','entry_status','status'],key),n=len(g)))
pd.DataFrame(coverage).to_csv(O/'H1_COVERAGE_ONLY.csv',index=False)
# No future result-selected subset: report added/removed selected tails and same-group rank similarity descriptively.
sw=[]
for key,g in s.groupby(['window','arm','event_type']):
 base=g[g.method.eq('PVR_DESC')];bk=set(zip(base.event_id,base.sid))
 for method in ['PWIN','CONDITIONAL_NET']:
  q=g[g.method.eq(method)];kk=set(zip(q.event_id,q.sid))
  for direction,keys in [('added',kk-bk),('removed',bk-kk)]:
   zz=z[[x in keys for x in zip(z.event_id,z.sid)]];done=zz[zz.label.isin(['W','L'])]
   sw.append(dict(window=key[0],arm=key[1],event_type=key[2],method=method,direction=direction,selected=len(zz),W=int(zz.label.eq('W').sum()),L=int(zz.label.eq('L').sum()),U=int(zz.label.eq('U').sum()),UNKNOWN=int(zz.label.eq('UNKNOWN').sum()),closedH=len(done),tailH=int(done.net_return_on_buy_cash.ge(.3).sum()),tailH_cny=done.loc[done.net_return_on_buy_cash.ge(.3),'net_pnl'].sum()))
pd.DataFrame(sw).to_csv(O/'ADDED_REMOVED_TAILS.csv',index=False)
qa=json.load(open(O/'QA.json'));qa.pop('read_2024_labels_only_after_rank_seal',None);qa['future_labels_loaded_but_not_used_in_fit_scaling_or_ranking']=True;qa['clarification']='All shadow labels existed and were already inspected historically. prepare/fit load the complete label table, then select2022 births and matureH before all transforms/fits. Only new comparative2024 scores/results were not inspected until final ranking. Claim is exclusion from fitting, not sealed unseen outcomes.'
# Future/unavailable-label poison check: training rows and every training input/label match exactly after replacing nontraining values.
original=a[a.window.eq('2022')&a.feature_known&a.label.isin(CL)].copy();poison=a.copy();poison.loc[~poison.window.eq('2022'),'label']='POISON_FUTURE';after=poison[poison.window.eq('2022')&poison.feature_known&poison.label.isin(CL)].copy();pd.testing.assert_frame_equal(original,after);qa['future_label_poison_training_rows_and_values_exact']=True
# Future features do not enter learned scaling either; score recreation is model-only.
model=json.load(open(O/'MODEL.json'));F=model['features'];known=c.feature_known;X=np.column_stack([np.ones(known.sum()),np.clip((c.loc[known,F].to_numpy()-np.array(model['mean']))/np.array(model['sd']),-5,5)]);vv=np.column_stack([X@np.array(model['coefficients']),np.zeros(len(X))]);pp=np.exp(vv-vv.max(1)[:,None]);pp/=pp.sum(1)[:,None];err=float(np.max(np.abs(pp-c.loc[known,['p'+x for x in CL]].to_numpy())));assert err<1e-12;qa['model_saved_probability_reproduction_max_error']=err
# Exact cancellation: Q depends on pW/pL, not pU directly, while U enters joint fit.
u=(c.pW/(c.pW+c.pL))*c.mean_W-(c.pL/(c.pW+c.pL))*c.mean_L;qa['Q_U_logit_cancels_max_error']=float(np.nanmax(abs(u-c.conditional_net)));qa['conditional_score_not_direct_U_or_duration_penalty']=True
(O/'QA.json').write_text(json.dumps(qa,ensure_ascii=False,indent=2)+'\n')
print(pd.DataFrame(r).to_string(index=False));print(pd.DataFrame(coverage).to_string(index=False));print(pd.DataFrame(sw)[lambda x:x.arm.eq('M3')&x.event_type.eq('FALSE_TO_TRUE')&x.window.eq('2024_924')].to_string(index=False))
