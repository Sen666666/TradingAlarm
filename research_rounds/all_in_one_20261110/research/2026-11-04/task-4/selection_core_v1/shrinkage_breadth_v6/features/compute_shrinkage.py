"""Frozen kappa10 causal count shrinkage and one T substitution. No accounts."""
from pathlib import Path
from fractions import Fraction
from collections import Counter
import hashlib,importlib.util,json,time
import numpy as np
import pandas as pd
O=Path(__file__).resolve().parent;ROOT=O.parent;S=ROOT.parent
CONTRACT='ef3a651713fe696f816632c91a738fc1ab5a15e24de224430400b28b434c1f5d'
SNAP=['2022-01-24','2024-09-24','2026-01-15'];HASH={}
def bind(p,h=None):
 p=Path(p).resolve();z=hashlib.sha256(p.read_bytes()).hexdigest()
 if h is not None:assert z==h,(str(p),'source changed')
 HASH[str(p)]=z;return p
def clean(x):
 if x is pd.NA or x is pd.NaT:return None
 if isinstance(x,dict):return {str(k):clean(v)for k,v in x.items()}
 if isinstance(x,list):return [clean(v)for v in x]
 if hasattr(x,'item'):return clean(x.item())
 if isinstance(x,float)and not np.isfinite(x):return None
 return x
def save(n,x):(O/n).write_text(json.dumps(clean(x),ensure_ascii=False,indent=2,allow_nan=False)+'\n')
def midpoint(values):
 counts=Counter(v for v in values.values()if v is not None);N=sum(counts.values());less=0;p={}
 for v in sorted(counts):p[v]=Fraction(2*less+counts[v],2*N);less+=counts[v]
 return {i:p[v]if v is not None else None for i,v in values.items()}
def addfrac(g,name,values):
 g[name]=[float(values[i])if values[i]is not None else np.nan for i in g.index]
 g[name+'_exact']=[str(values[i])if values[i]is not None else None for i in g.index]
def module(p):
 sp=importlib.util.spec_from_file_location('v6_exact_queue',bind(p));m=importlib.util.module_from_spec(sp);sp.loader.exec_module(m);return m
def main():
 start=time.monotonic();bind(__file__);bind(ROOT/'FROZEN_CONTRACT.txt',CONTRACT)
 ranker=module(S/'continuous_rank_v3/ranking/rank_daily.py')
 cols=['date','sector_id_static','industry_static','N_U_t','N_above20_t','N_above20_tminus5','N_U_previous5','N_U_intersection_previous5','U_joiners5','U_leavers5','U_joiners1','U_leavers1','Nstatic','N25valid','Nobserved','B_lag5_ownU','B_now','dB5_paired','rs_ind5']
 f=pd.read_parquet(bind(S/'industry_selection/channels_v2/INDUSTRY_OPPORTUNITIES_DAILY.parquet'),columns=cols);assert len(f)==97650
 vc=['date','sector_id_static','p_R5','p_R5_referenceN','T_score','T_score_exact','T_order','T_selected','P_score','P_score_exact','P_order','P_mature','possible_states_before','possible_states_after','P_state_event','P_known_new_maturity','P_known_exit']
 v4=pd.read_parquet(bind(S/'separated_momentum_v4/ranking/STUDY_STATES_2022_2026.parquet'),columns=vc)
 v4=v4.rename(columns={k:'cached_'+k for k in ['T_score','T_score_exact','T_order','T_selected']});f=f.merge(v4,on=['date','sector_id_static'],validate='one_to_one')
 for k in ['N_U_t','N_above20_t','N_above20_tminus5','N_U_previous5']:
  assert f[k].notna().all()and f[k].map(lambda z:float(z).is_integer()).all();f[k]=f[k].astype(int)
 assert f.N_U_t.gt(0).all();assert f.groupby('date').size().eq(90).all()
 # Recover the unique integer old observable own-U numerator, never new warm B.
 oldup=[]
 for r in f.itertuples():
  n=r.N_U_previous5
  if n==0:assert pd.isna(r.B_lag5_ownU);oldup.append(0);continue
  assert pd.notna(r.B_lag5_ownU);u=round(r.B_lag5_ownU*n);assert 0<=u<=n and float(Fraction(u,n))==float(r.B_lag5_ownU)
  oldup.append(u)
 f['old_ownU_up_lag5_recovered']=oldup
 market={}
 for day,g in f.groupby('date'):
  market[day]={'up1':int(g.N_above20_t.sum()),'n1':int(g.N_U_t.sum()),'up0':int(g.old_ownU_up_lag5_recovered.sum()),'n0':int(g.N_U_previous5.sum())}
 days=sorted(market);daypos={d:i for i,d in enumerate(days)};lag_checks=[]
 for day in days[5:]:
  p=days[daypos[day]-5];a,b=market[day],market[p];assert a['up0']==b['up1']and a['n0']==b['n1'];lag_checks.append({'date':day,'lag5_date':p,'counts_exact':True})
 save('MARKET_LAG5_SOURCE_CHECK.json',{'first5_dates':days[:5],'first5_source':'unique integer recovered from original B_lag5_ownU*N_U_previous5 with exact ratio roundtrip','all_industry_ratio_roundtrips':len(f),'later_days_counts_exact':len(lag_checks),'new_warm_used':False})
 casepath=ROOT/'diagnostics/FROZEN_V5_CASE_MAPPING_168.csv';cases=pd.read_csv(bind(casepath));assert len(cases)==168
 case_dates=set(cases.date);order=SNAP+sorted(case_dates-set(SNAP))+[d for d in days if d not in case_dates and d not in SNAP]
 groups={d:g for d,g in f.groupby('date')};finished={};early_cases=False
 for day in order:
  g=groups[day].copy().reset_index(drop=True);m=market[day];m1=Fraction(m['up1'],m['n1']);m0=Fraction(m['up0'],m['n0']);dm=m1-m0
  for name,x in [('m1',m1),('m0',m0),('d_mkt',dm)]:g[name]=float(x);g[name+'_exact']=str(x)
  g['market_up1']=m['up1'];g['market_n1']=m['n1'];g['market_up0_ownU']=m['up0'];g['market_n0_ownU']=m['n0'];g['m0_source']='OLD_OWN_U_RATIO_INTEGER_ROUNDTRIP_FIRST5'if day in days[:5]else'OLD_OWN_U_INTEGER_COUNTS_EXACT_STORED_TMINUS5'
  values={k:{}for k in ['B_original','B1_shrunk','B0_paired_shrunk','D_original','D_shrunk','Self','Market']};pr5={}
  for i,r in g.iterrows():
   n,u1,u0=int(r.N_U_t),int(r.N_above20_t),int(r.N_above20_tminus5)
   if n==0:
    for x in values.values():x[i]=None
    pr5[i]=None;continue
   values['B_original'][i]=Fraction(u1,n);values['D_original'][i]=Fraction(u1-u0,n)
   values['B1_shrunk'][i]=(u1+10*m1)/(n+10);values['B0_paired_shrunk'][i]=(u0+10*m0)/(n+10)
   values['Self'][i]=Fraction(u1-u0,n+10);values['Market'][i]=10*dm/(n+10);values['D_shrunk'][i]=values['B1_shrunk'][i]-values['B0_paired_shrunk'][i]
   assert values['D_shrunk'][i]==values['Self'][i]+values['Market'][i]
   assert float(values['D_original'][i])==float(r.dB5_paired)and float(values['B_original'][i])==float(r.B_now)
   N=int(r.p_R5_referenceN);u=round(r.p_R5*2*N);pr5[i]=Fraction(u,2*N);assert float(pr5[i])==float(r.p_R5)
  for name,v in values.items():addfrac(g,name,v)
  perc={}
  for name in ['D_original','D_shrunk','B_original','B1_shrunk']:
   perc[name]=midpoint(values[name]);addfrac(g,'p_'+name,perc[name]);g['p_'+name+'_referenceN']=sum(x is not None for x in values[name].values());ranker.assign_exact_queue(g,name,values[name],None)
  for name,raw in [('T0','D_original'),('T10','D_shrunk')]:
   z={i:(pr5[i]+perc[raw][i])/2 if pr5[i]is not None and perc[raw][i]is not None else None for i in g.index};addfrac(g,name+'_score',z);ranker.assign_exact_queue(g,name,z,3)
  assert g.T0_score_exact.eq(g.cached_T_score_exact).all()and g.T0_order.eq(g.cached_T_order).all()and g.T0_selected.eq(g.cached_T_selected).all(),(day,'original T changed')
  g['du']=g.N_above20_t-g.N_above20_tminus5;g['n']=g.N_U_t;g['u1']=g.N_above20_t;g['u0']=g.N_above20_tminus5;g['kappa']=10;g['original_P_not_recomputed']=True;g['membership_PIT_verified']=False
  finished[day]=g
  if day in SNAP:
   g.to_parquet(O/('EARLY_ALL90_'+day+'.parquet'),index=False);focal=g[g.industry_static.isin(['半导体','软件开发','通信设备','房地产','厨卫电器'])]
   save('EARLY_'+day+'.json',{'date':day,'m1_exact':str(m1),'m0_exact':str(m0),'T0_top3':g.loc[g.T0_selected.eq(True)].sort_values('T0_order').industry_static.tolist(),'T10_top3':g.loc[g.T10_selected.eq(True)].sort_values('T10_order').industry_static.tolist(),'focal':focal.to_dict('records')});print(json.dumps({'early_date':day,'T0':g.loc[g.T0_selected.eq(True)].sort_values('T0_order').industry_static.tolist(),'T10':g.loc[g.T10_selected.eq(True)].sort_values('T10_order').industry_static.tolist()}),flush=True)
  if not early_cases and case_dates.issubset(finished):
   ef=pd.concat([finished[d]for d in sorted(case_dates)],ignore_index=True);ec=cases.merge(ef,on=['date','sector_id_static'],validate='many_to_one',suffixes=('_case',''));assert len(ec)==168;ec.to_parquet(O/'EARLY_FIXED_CASES_168.parquet',index=False);ec.to_csv(O/'EARLY_FIXED_CASES_168.csv',index=False);early_cases=True;print(json.dumps({'early_case_rows':168,'seconds':time.monotonic()-start}),flush=True)
 table=pd.concat([finished[d]for d in days],ignore_index=True).sort_values(['sector_id_static','date']).reset_index(drop=True);assert len(table)==97650
 table['n_lag5']=table.groupby('sector_id_static').n.shift(5);table['feature_lag5_date']=table.groupby('sector_id_static').date.shift(5)
 for current,out in [('D_original','a5_D_original'),('D_shrunk','a5_D_shrunk'),('Self','a5_Self'),('Market','a5_Market')]:
  lag=table.groupby('sector_id_static')[current+'_exact'].shift(5);v={i:Fraction(a)-Fraction(b)if pd.notna(a)and pd.notna(b)else None for i,(a,b)in enumerate(zip(table[current+'_exact'],lag))};addfrac(table,out,v)
 for r in table.loc[table.a5_D_shrunk_exact.notna(),['a5_D_shrunk_exact','a5_Self_exact','a5_Market_exact']].itertuples(index=False):assert Fraction(r[0])==Fraction(r[1])+Fraction(r[2])
 table=table.sort_values(['date','sector_id_static']);table.to_parquet(O/'DAILY_SHRINKAGE_FEATURES.parquet',index=False);table.to_csv(O/'DAILY_SHRINKAGE_FEATURES.csv',index=False)
 finalcases=cases.merge(table,on=['date','sector_id_static'],validate='many_to_one',suffixes=('_case',''));assert len(finalcases)==168;finalcases.to_parquet(O/'FIXED_CASES_168.parquet',index=False);finalcases.to_csv(O/'FIXED_CASES_168.csv',index=False)
 save('SCHEMA.json',{'status':'COMPLETE','key':['date','sector_id_static'],'rows':len(table),'fields':table.columns.tolist(),'T0_selected':'unchanged original T top3 exact checked all97650','T10_selected':'one fixed substitution .5pR5+.5pDshrunk top3','all_fraction_columns':'*_exact are rational source-count arithmetic; numeric copies in natural proportions/log RS','a5_first5_unknown':True,'P_state_recomputed':False,'static_pool_not_PIT':True})
 save('SUMMARY.json',{'complete':True,'rows':len(table),'sessions':len(days),'industries':90,'case_rows':len(finalcases),'T0_exact_all97650':True,'market_lag5_original_ratio_roundtrips':len(f),'market_lag5_actual_later_days_exact':len(lag_checks),'self_plus_market_exact_rows':len(table),'a5_decomposition_exact_rows':int(table.a5_D_shrunk_exact.notna().sum()),'a5_unknown_rows':int(table.a5_D_shrunk_exact.isna().sum()),'new_stock_reads':0,'new_rankings_only_fixed_contract':True,'new_labels':0,'new_accounts':0,'seconds':time.monotonic()-start})
 save('SOURCE_SHA256.json',HASH);save('OUTPUT_SHA256.json',{str(p.resolve()):hashlib.sha256(p.read_bytes()).hexdigest()for p in O.iterdir()if p.is_file()and p.name not in ['OUTPUT_SHA256.json','run.log']})
 print(json.dumps({'complete':True,'rows':len(table),'seconds':time.monotonic()-start}),flush=True)
if __name__=='__main__':main()
