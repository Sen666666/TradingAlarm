"""Fixed v7 Fraction identities and leave-industry-out sensitivity; no accounts."""
from pathlib import Path
from fractions import Fraction
import hashlib,importlib.util,json,time
import pandas as pd
import numpy as np
O=Path(__file__).resolve().parent;ROOT=O.parent;S=ROOT.parent
CONTRACT='294657619ccf6bda110abe33cbd081895c8d2808defe598e5247b5dd36bc6312'
V6SHA='171b33ae50680b4453a6c99ff1145405c12d20635ea4ccfc6346e7bd67a9cd38';HASH={}
EARLY=['2024-09-24','2026-01-05','2026-01-15','2022-01-24','2024-10-08','2022-02-10','2024-01-03','2025-01-20','2025-02-26']
def bind(p,h=None):
 p=Path(p).resolve();z=hashlib.sha256(p.read_bytes()).hexdigest()
 if h is not None:assert z==h,(str(p),'source changed')
 HASH[str(p)]=z;return p
def loadmodule(name,p):
 sp=importlib.util.spec_from_file_location(name,bind(p));m=importlib.util.module_from_spec(sp);sp.loader.exec_module(m);return m
def main():
 start=time.monotonic();bind(__file__);bind(ROOT/'FROZEN_CONTRACT.txt',CONTRACT)
 v6=loadmodule('v7_pure_fraction_helpers',S/'shrinkage_breadth_v6/features/compute_shrinkage.py');ranker=loadmodule('v7_exact_queue',S/'continuous_rank_v3/ranking/rank_daily.py')
 def save(name,obj):(O/name).write_text(json.dumps(v6.clean(obj),ensure_ascii=False,indent=2,allow_nan=False)+'\n')
 f=pd.read_parquet(bind(S/'shrinkage_breadth_v6/features/DAILY_SHRINKAGE_FEATURES.parquet',V6SHA));assert len(f)==97650
 cases=pd.read_csv(bind(S/'shrinkage_breadth_v6/diagnostics/FROZEN_V5_CASE_MAPPING_168.csv'));assert len(cases)==168
 days=sorted(f.date.unique());case_dates=set(cases.date);priority=EARLY+sorted(case_dates-set(EARLY));order=priority+[d for d in days if d not in priority]
 groups={d:g for d,g in f.groupby('date')};done={};earlycase=False;loo_unknown=0
 for day in order:
  g=groups[day].copy().reset_index(drop=True);assert len(g)==90 and g.d_mkt_exact.nunique()==1
  centered={};excl={};pr5={};m1s={};m0s={};dms={};num1s=[];den1s=[];num0s=[];den0s=[]
  for i,r in g.iterrows():
   n,u1,u0=int(r.n),int(r.u1),int(r.u0);dm=Fraction(r.d_mkt_exact);du=u1-u0
   if n<=0:raise AssertionError('Frozen batch expected observed n>0; prior-only must not be ranked')
   centered[i]=(du-n*dm)/(n+10)
   assert centered[i]==Fraction(r.D_shrunk_exact)-dm==Fraction(n,n+10)*(Fraction(r.D_original_exact)-dm)
   den1=int(r.market_n1)-n;num1=int(r.market_up1)-u1
   den0=int(r.market_n0_ownU)-int(r.N_U_previous5);num0=int(r.market_up0_ownU)-int(r.old_ownU_up_lag5_recovered)
   num1s.append(num1);den1s.append(den1);num0s.append(num0);den0s.append(den0)
   if den1<=0 or den0<=0 or not 0<=num1<=den1 or not 0<=num0<=den0:
    m1s[i]=m0s[i]=dms[i]=excl[i]=None;loo_unknown+=1
   else:
    m1s[i]=Fraction(num1,den1);m0s[i]=Fraction(num0,den0);dms[i]=m1s[i]-m0s[i];excl[i]=Fraction(n,n+10)*(Fraction(r.D_original_exact)-dms[i])
   N=int(r.p_R5_referenceN);pr5[i]=Fraction(round(float(r.p_R5)*2*N),2*N);assert float(pr5[i])==float(r.p_R5)
  g['loo_market_up1']=num1s;g['loo_market_n1']=den1s;g['loo_market_up0_ownU']=num0s;g['loo_market_n0_ownU']=den0s
  for name,z in [('D_center',centered),('m1_excl',m1s),('m0_excl',m0s),('d_mkt_excl',dms),('D_center_excl',excl)]:v6.addfrac(g,name,z)
  for name,z,queue in [('D_center',centered,'Tcenter'),('D_center_excl',excl,'Tcenter_excl')]:
   p=v6.midpoint(z);v6.addfrac(g,'p_'+name,p);g['p_'+name+'_referenceN']=sum(v is not None for v in z.values());ranker.assign_exact_queue(g,name,z,None)
   scores={i:(pr5[i]+p[i])/2 if p[i]is not None else None for i in g.index};v6.addfrac(g,queue+'_score',scores);ranker.assign_exact_queue(g,queue,scores,3)
  # Common dm subtraction changes absolute values, never any within-day ordering.
  for a,b in [('p_D_center_exact','p_D_shrunk_exact'),('D_center_order','D_shrunk_order'),('D_center_score_tie_count','D_shrunk_score_tie_count'),('D_center_mathematical_rank_min','D_shrunk_mathematical_rank_min'),('Tcenter_score_exact','T10_score_exact'),('Tcenter_order','T10_order'),('Tcenter_selected','T10_selected')]:assert g[a].eq(g[b]).all(),(day,a,b)
  g['centered_is_5session_relative_change_not_acceleration']=True;g['main_centered_ranking_identical_v6_T10']=True;g['LOO_is_sensitivity_only']=True;g['original_P_not_recomputed']=True
  done[day]=g
  if day in EARLY:
   g.to_parquet(O/('EARLY_ALL90_'+day+'.parquet'),index=False)
   focal=g[g.industry_static.isin(['软件开发','厨卫电器','半导体','通信设备','房地产','油气开采及服务','旅游及酒店','影视院线','风电设备'])]
   save('EARLY_'+day+'.json',{'date':day,'main_translation_rank_identity_exact':True,'T0':g.loc[g.T0_selected.eq(True)].sort_values('T0_order').industry_static.tolist(),'T10_Tcenter':g.loc[g.Tcenter_selected.eq(True)].sort_values('Tcenter_order').industry_static.tolist(),'Tcenter_excl':g.loc[g.Tcenter_excl_selected.eq(True)].sort_values('Tcenter_excl_order').industry_static.tolist(),'focal':focal.to_dict('records')})
   print(json.dumps({'early_date':day,'main_rank_identity':True,'Tcenter':g.loc[g.Tcenter_selected.eq(True)].sort_values('Tcenter_order').industry_static.tolist(),'Tcenter_excl':g.loc[g.Tcenter_excl_selected.eq(True)].sort_values('Tcenter_excl_order').industry_static.tolist()}),flush=True)
  if not earlycase and case_dates.issubset(done):
   c=cases.merge(pd.concat([done[d]for d in sorted(case_dates)],ignore_index=True),on=['date','sector_id_static'],validate='many_to_one',suffixes=('_case',''));assert len(c)==168;c.to_parquet(O/'EARLY_FIXED_CASES_168.parquet',index=False);earlycase=True
 table=pd.concat([done[d]for d in days],ignore_index=True).sort_values(['date','sector_id_static']);table.to_parquet(O/'DAILY_CENTERED_FEATURES.parquet',index=False);table.to_csv(O/'DAILY_CENTERED_FEATURES.csv',index=False)
 c=cases.merge(table,on=['date','sector_id_static'],validate='many_to_one',suffixes=('_case',''));assert len(c)==168;c.to_parquet(O/'FIXED_CASES_168.parquet',index=False);c.to_csv(O/'FIXED_CASES_168.csv',index=False)
 save('SCHEMA.json',{'status':'COMPLETE','keys':['date','sector_id_static'],'fields':table.columns.tolist(),'main_D_center':'(du-n*d_mkt)/(n+10) = D_shrunk-d_mkt = n/(n+10)*(D_original-d_mkt)','main_rank_identity':'exact common-date translation; D_center ranks/percentiles and Tcenter all identical to v6 D_shrunk/T10, no new main ranking information','LOO_Tminus5_subtraction':'own-U old industry numerator old_ownU_up_lag5_recovered and denominator N_U_previous5; never current paired u0/n','LOO_role':'baseline sensitivity only, no replacement of main','no_new_labels':True,'no_new_accounts':True,'P_unchanged':True})
 save('SUMMARY.json',{'complete':True,'rows':len(table),'sessions':len(days),'main_three_fraction_identities_exact_rows':len(table),'main_rank_percentile_tie_and_T10_identity_exact_rows':len(table),'LOO_unknown_rows':loo_unknown,'case_rows':168,'LOO_rows_where_old_ownU_n_differs_current_n':int(table.N_U_previous5.ne(table.n).sum()),'LOO_rows_where_old_ownU_u_differs_current_paired_u0':int(table.old_ownU_up_lag5_recovered.ne(table.u0).sum()),'new_stock_reads':0,'new_labels':0,'new_accounts':0,'seconds':time.monotonic()-start})
 save('SOURCE_SHA256.json',HASH);save('OUTPUT_SHA256.json',{str(p.resolve()):hashlib.sha256(p.read_bytes()).hexdigest()for p in O.iterdir()if p.is_file()and p.name not in ['OUTPUT_SHA256.json','run.log']})
 print(json.dumps({'complete':True,'rows':len(table),'seconds':time.monotonic()-start}),flush=True)
if __name__=='__main__':main()
