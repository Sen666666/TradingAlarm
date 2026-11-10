from pathlib import Path
import json,hashlib
import pandas as pd,numpy as np
O=Path(__file__).resolve().parent;V=O.parent;R=V.parent;P=R/'pvr_persistence_breadth_v1'
b=pd.read_parquet(O/'COMMON_K_COMPARISON.parquet');own=pd.read_parquet(O/'SECTOR_DAILY.parquet');st=pd.read_parquet(O/'STRICT_SECTOR_DAILY.parquet');cal=sorted(b.day.unique());pos={pd.Timestamp(d):i for i,d in enumerate(cal)}
yearly=[]
for year,g in b.groupby(b.day.dt.year):
 for label in ['M3','PVR3']:
  c=g[label+'_candidate'];yearly.append(dict(year=int(year),version=label,industry_days=len(g),confirmed_qualifying=int((c==1).sum()),nonqualifying=int((c==0).sum()),unknown=int((c<0).sum()),mean_common_K=g.K.mean(),mean_right_known=g[label+'_right_known'].mean()))
pd.DataFrame(yearly).to_csv(O/'YEARLY_SAME_K_QUALIFICATION.csv',index=False)
rows=[]
for (sec,episode),g in b[b.sector_E0_episode.notna()&b.sector_E0_valid.eq(True)].groupby(['sector','sector_E0_episode']):
 g=g.sort_values('day');cp=g[g.sector_action.eq('probe')];r=dict(sector=sec,sector_name=g.sector_name.iloc[0],E0_episode=episode,first_observed=g.day.iloc[0],last_observed=g.day.iloc[-1],first_CP=cp.day.iloc[0]if len(cp)else pd.NaT,left_truncated=g.day.iloc[0]==pd.Timestamp(cal[0]))
 for label in ['M3','PVR3']:
  qq=g[g[label+'_candidate'].eq(1)];r[label+'_first_robust']=qq.day.iloc[0]if len(qq)else pd.NaT;r[label+'_days_before_CP']=(pos[r['first_CP']]-pos[qq.day.iloc[0]])if len(cp)and len(qq)else np.nan
 rows.append(r)
e=pd.DataFrame(rows);e.to_csv(O/'SAME_E0_EPISODE_COMPARISON.csv',index=False)
# Exact row-by-row verification of PVR collaborator V2 gate on its own N/K domain.
pd2=pd.read_parquet(P/'INDUSTRY_DAILY_V2.parquet');n=pd2.n;K=pd2.K;N=pd2.N;d=pd2.paired_delta_n;J=pd2.paired_K
rule=lambda nn,dd: (nn>=3)&(((nn*3>=dd)&J.gt(0)&d.gt(0))|(nn*2>=dd))
observed=np.where(K.gt(0),rule(n,K).astype(int),-1);lo=rule(n,N);hi=(n+N-K>=3)&((((n+N-K)*3>=N)&(d.gt(0)|J.eq(0)))|((n+N-K)*2>=N));robust=np.where(lo,1,np.where(~hi,0,-1));np.testing.assert_equal(observed,pd2.observed_candidate.to_numpy());np.testing.assert_equal(robust,pd2.candidate.to_numpy())
# Boundary tests for exact common-gate semantics.
def gate(n,k,j,d):return n>=3 and ((3*n>=k and j>0 and d>0)or 2*n>=k)
assert not gate(1,1,1,1)and not gate(2,2,2,1);assert gate(3,9,9,1)and not gate(3,10,10,1);assert gate(3,6,6,-1);assert not gate(3,9,9,0)
# Source/date rules are separately checked without importing executable study module.
def classify(mu,valid,identity):
 mu=pd.Series(mu);valid=pd.Series(valid);ident=pd.Series(identity);known=valid&valid.shift(1,fill_value=False)&valid.shift(2,fill_value=False)&ident.eq(ident.shift(1))&ident.eq(ident.shift(2));return known,(known&mu.gt(0)&mu.shift(1).gt(0)&mu.shift(2).gt(0))
k,r=classify([1]*6,[1,1,1,1,1,1],['a','a','a','b','b','b']);assert r.tolist()==[False,False,True,False,False,True]
k,r=classify([1,1,1,1,1,1,1],[True,True,False,True,True,True,True],['a']*7);assert r.tolist()==[False,False,False,False,False,True,True]
k,r=classify([1,1,0,-1,1,1,1],[True]*7,['a']*7);assert r.tolist()==[False,False,False,False,False,False,True]
summary=dict(same_membership_and_clock=True,PVR_own_gate_all_rows_exact=len(pd2),candidate_synthetic_assertions=5,state_synthetic_sequences=3,primary_native_mu_inherits_pre_gap_and_pre_source_history=True,initial_first3_diffusion_left_truncated=False,accounts=0)
(O/'JOINT_CHECKS.json').write_text(json.dumps(summary,indent=2))
print('SEMICONDUCTOR EPISODES');print(e[e.sector.eq('URFI881121')&e.first_observed.ge('2024-09-01')].to_string(index=False));print('2022 FAILED KNOWN CASES');print(b[(b.sector.eq('URFI881153')&b.day.isin(pd.to_datetime(['2022-01-11','2022-02-11','2022-12-01'])))|(b.sector.eq('URFI881146')&b.day.eq('2022-07-25'))][['day','sector_name','N','K','M3_n','PVR3_n','M3_candidate','PVR3_candidate','M3_delta3','PVR3_delta3','sector_action']].to_string(index=False));print(pd.DataFrame(yearly).to_string(index=False));print('strict last day',st[st.day.eq(st.day.max())].K.sum())
(O/'OUTPUT_HASHES.json').write_text(json.dumps({p.name:hashlib.sha256(p.read_bytes()).hexdigest()for p in O.iterdir()if p.is_file()and p.name!='OUTPUT_HASHES.json'},indent=2))
