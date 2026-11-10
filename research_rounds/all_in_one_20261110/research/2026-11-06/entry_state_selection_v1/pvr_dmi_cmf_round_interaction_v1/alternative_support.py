"""Support-only alternatives requested after H120 U discovered. No model fitting."""
from pathlib import Path
import json,math,hashlib
import numpy as np,pandas as pd
O=Path(__file__).resolve().parent;R=O.parent
a=pd.read_csv(O/'ALL_ORIGINAL_ROUNDS_FEATURE_SUPPORT.csv');cal=pd.read_csv(R/'selection_entry_diagnosis_v1/entry_probability_signal_v1/MARKET_CLOCK.csv',index_col=0,parse_dates=True).index
out=[];elig=[]
for H in [120,240]:
 a['Hclosed']=a.closed&a.close_t.lt(a.entry_t+H);a['HW']=a.Hclosed&a.round_pnl.gt(0);a['HL']=a.Hclosed&a.round_pnl.le(0);a['HU']=~a.Hclosed
 for month in sorted(set(cal[cal.year>=2023].to_period('M').astype(str))):
  cut=next(i for i,d in enumerate(cal)if str(d.to_period('M'))==month);tr=a[(a.t>=cut-504)&(a.entry_t+H-1<cut)&a.known_for_fit].copy()
  s=dict(H=H,month=month,n=len(tr),W=int(tr.HW.sum()),L=int(tr.HL.sum()),U=int(tr.HU.sum()),dates=tr.signal_day.nunique(),stocks=tr.sid.nunique(),I_roots=tr.root.nunique(),matrix_rank=None,condition=None,robust_scale_valid=False)
  ok=len(tr)>=300 and tr.HW.sum()>=50 and tr.HL.sum()>=50 and tr.signal_day.nunique()>=60 and tr.sid.nunique()>=100 and tr.root.nunique()>=200
  for role in ['core','add']:
   z=tr[tr.first_kind.eq(role)];s.update({role+'_n':len(z),role+'_W':int(z.HW.sum()),role+'_L':int(z.HL.sum()),role+'_U':int(z.HU.sum()),role+'_dates':z.signal_day.nunique()});ok=ok and len(z)>=50 and z.HW.sum()>=10 and z.HL.sum()>=20 and z.signal_day.nunique()>=20
  if len(tr):
   X=tr[['P','D','C']].to_numpy();mu=np.median(X,axis=0);sc=(np.quantile(X,.75,axis=0)-np.quantile(X,.25,axis=0))/1.349
   if (sc>1e-12).all():
    z=np.clip((X-mu)/sc,-5,5);zz=z[:,[0]]*z[:,[1,2]];im=np.median(zz,axis=0);isc=(np.quantile(zz,.75,axis=0)-np.quantile(zz,.25,axis=0))/1.349
    if (isc>1e-12).all():
     X=np.c_[np.ones(len(tr)),tr.first_kind.eq('add'),z,np.clip((zz-im)/isc,-5,5)];s.update(matrix_rank=int(np.linalg.matrix_rank(X)),condition=float(np.linalg.cond(X)),robust_scale_valid=True)
  s['support']=bool(ok);s['binary_fit_possible']=bool(ok and s['U']==0 and s['matrix_rank']==7 and s['condition']<1e6);s['three_class_50_per_class']=bool(ok and s['U']>=50);out.append(s)
  test=a[a.signal_day.str.startswith(month)].copy();test['month_support']=s['support'];test['binary_fit_possible']=s['binary_fit_possible'];test['H']=H;test['matureH']=test.entry_t+H-1<len(cal);elig.append(test)
s=pd.DataFrame(out);e=pd.concat(elig);s.to_csv(O/'ALTERNATIVE_SUPPORT_NO_FIT.csv',index=False)
rows=[]
for (H,year),g in e.groupby(['H','year']):
 good=g.known_for_fit&g.binary_fit_possible;mat=g.entry_t+H-1<len(cal);resolved=g.closed&g.close_t.lt(g.entry_t+H);win=resolved&g.round_pnl.gt(0)
 rows.append(dict(H=H,year=year,births=len(g),feature_known=int(g.known_for_fit.sum()),scorable_months=int(good.sum()),all_mature=int(mat.sum()),feature_known_mature=int((mat&g.known_for_fit).sum()),eligible_evaluation=int((good&mat).sum()),evaluation_W=int((good&mat&win).sum()),evaluation_L=int((good&mat&resolved&~win).sum()),evaluation_U=int((good&mat&~resolved).sum()),earliest_evaluation=g.loc[good&mat,'signal_day'].min(),latest_evaluation=g.loc[good&mat,'signal_day'].max()))
rr=pd.DataFrame(rows);rr.to_csv(O/'ALTERNATIVE_EVALUATION_COVERAGE.csv',index=False)
coverage=[]
for role,g in a.groupby('first_kind'):
 coverage.append(dict(role=role,n=len(g),P_known=int(np.isfinite(g.P).sum()),D_known=int(np.isfinite(g.D).sum()),C_known=int(np.isfinite(g.C).sum()),all_features=int(g.feature_known.sum()),root_known=int(g.root_known.sum()),joint_known=int(g.known_for_fit.sum()),H_equal_L21=int(g.H_equal_L21.sum()),factor_change21=int(g.factor_change21.sum()),volume_factor_change21=int(g.volume_factor_change21.sum()),source_change21=int(g.source_change21.sum())))
pd.DataFrame(coverage).to_csv(O/'ROLE_FEATURE_COVERAGE.csv',index=False)
u=a[a.mature120&a.U];print('U later',u.groupby(['first_kind','feature_known','closed','final_win_known']).size().to_string())
print('COVERAGE',pd.DataFrame(coverage).to_string(index=False));print('ALT_MONTHS',s.to_string(index=False));print('EVALUATION',rr.to_string(index=False))
summary={}
for H,z in s.groupby('H'):
 summary[str(H)]={'support_months':int(z.support.sum()),'binary_eligible_months':int(z.binary_fit_possible.sum()),'first_support_month':z.loc[z.support,'month'].min(),'first_binary_month':z.loc[z.binary_fit_possible,'month'].min(),'U_range':[int(z.U.min()),int(z.U.max())],'threeclass_supported_months':int(z.three_class_50_per_class.sum()),'max_condition':float(z.condition.max())}
(O/'ALTERNATIVE_SUPPORT_SUMMARY.json').write_text(json.dumps(summary,indent=2));print('SUMMARY',json.dumps(summary))
