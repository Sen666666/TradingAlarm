"""Fixed event-window readout of existing causal scores/states; no new gate."""
from pathlib import Path
from fractions import Fraction
import hashlib,json,sys
import pandas as pd
import numpy as np
O=Path(__file__).resolve().parent;ROOT=O.parent;S=ROOT.parent
V4=S/'separated_momentum_v4/ranking';B=Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/universe-cp1-inputs-20261031')
MARKET=Path('/Users/bytedance/repos/TradingAlarm/TradingAlarm/TradingAlarm/research/data/ths-index-history-20261018/canonical/USHI1B0300.csv')
CASES=[('924_SEMI','MAIN','2024-09-24','URFI881121'),('924_SOFTWARE','MAIN','2024-09-24','URFI881272'),('924_COMMUNICATION','MAIN','2024-09-24','URFI881129'),('2026JAN5_SEMI','MAIN','2026-01-05','URFI881121'),('2026JAN15_SEMI','AUX','2026-01-15','URFI881121')]
COUNTER_CASES=[('2022JAN24_REALESTATE','COUNTEREXAMPLE','2022-01-24','URFI881153'),('2024OCT8_SOFTWARE','COUNTEREXAMPLE','2024-10-08','URFI881272'),('2024OCT8_FINANCIAL','COUNTEREXAMPLE','2024-10-08','URFI881283')]
CONTRACT_SHA='a335d4fac74826d11d3294f271f8336318f170b057450333a5a114e22d27fe92'
CHANGE_FIELDS=['Rp','B_now','rs_ind5','dB5_paired','p_Rp','p_B','p_R5','p_dB5','P_score','T_score']
HASH={}
def bind(p,h=None):
 p=Path(p).resolve();z=hashlib.sha256(p.read_bytes()).hexdigest()
 if h is not None:assert z==h,(str(p),'source hash changed')
 HASH[str(p)]=z;return p
def clean(x):
 if x is pd.NA or x is pd.NaT:return None
 if isinstance(x,dict):return {str(k):clean(v)for k,v in x.items()}
 if isinstance(x,list):return [clean(v)for v in x]
 if hasattr(x,'item'):return clean(x.item())
 if isinstance(x,float)and not np.isfinite(x):return None
 return x
def save(name,x):(O/name).write_text(json.dumps(clean(x),ensure_ascii=False,indent=2,allow_nan=False)+'\n')
def pct(row,col):
 n=int(row[col+'_referenceN']);u=round(float(row[col])*2*n);z=Fraction(u,2*n)
 assert float(z)==float(row[col]);return z
def compare(row,cutoff,prefix,line_changes):
 p,q=('p_Rp','p_B')if prefix=='P'else('p_R5','p_dB5');weights=(Fraction(3,5),Fraction(2,5))if prefix=='P'else(Fraction(1,2),Fraction(1,2))
 out={prefix+'_cutoff_sector':cutoff.sector_id_static,prefix+'_cutoff_industry':cutoff.industry_static}
 fields=['Rp','B_now','rs_ind5','dB5_paired','p_Rp','p_B','p_R5','p_dB5','Nstatic','N_U_t','N25valid','Nobserved','N_above20_t','N_above20_tminus5',prefix+'_score',prefix+'_score_exact',prefix+'_order']
 for k in fields:out[prefix+'_cutoff_'+k]=cutoff[k]
 for k,v in line_changes.items():out[prefix+'_cutoff_line_d1_'+k]=v
 for col,w in zip([p,q],weights):
  z=w*(pct(row,col)-pct(cutoff,col));out[prefix+'_gap_contribution_'+col]=float(z);out[prefix+'_gap_contribution_'+col+'_exact']=str(z)
 gap=Fraction(row[prefix+'_score_exact'])-Fraction(cutoff[prefix+'_score_exact'])
 assert sum(weights[j]*(pct(row,k)-pct(cutoff,k))for j,k in enumerate([p,q]))==gap
 out[prefix+'_gap_vs_cutoff']=float(gap);out[prefix+'_gap_vs_cutoff_exact']=str(gap)
 order=int(row[prefix+'_order']);K=5 if prefix=='P'else 3
 out[prefix+'_relative_rank_fact']='IN_TOP_K'if order<=K else'BELOW_CUTOFF_SCORE'if gap<0 else'EXACT_SCORE_TIE_SID_CUT'
 return out
def state_fact(r):
 if not r.P_known:return 'P_INPUT_UNKNOWN'
 if pd.isna(r.P_mature):return 'INITIAL_OR_DATA_STATE_UNCERTAIN'
 if r.P_known_exit:return 'REMOVED_THIRD_CONSECUTIVE_ABOVE10'
 if r.P_mature:
  if r.P_order<=5:return 'MATURE_TOP5'
  if r.P_order<=10:return 'MATURE_6_TO10_BUFFER'
  return 'MATURE_EXIT_BUFFER_'+r.P_exit_counts_possible
 if r.P_order<=5:return 'FIRST_TOP5_WAIT_SECOND_CONSECUTIVE'
 if r.P_order<=10:return 'INACTIVE_6_TO10_NO_ACQUIRED_QUALIFICATION'
 return 'INACTIVE_OUTSIDE_TOP10'
def price_diagnostics(manifest,calendar):
 out={}
 for r in manifest:
  if r['series']not in {c[3]for c in CASES}:continue
  p=r['refs']['CP1_input'];f=pd.read_parquet(bind(p,r['output_sha256'][p]),columns=['close','segment_id']).reindex(calendar)
  c=f.close;seg=f.segment_id;valid=c.gt(0)&np.isfinite(c)&seg.notna();a=pd.DataFrame(index=calendar);a['index_close']=c
  same2=valid.rolling(2,min_periods=2).sum().eq(2)&seg.eq(seg.shift())
  a['index_r1_log']=np.log(c/c.shift()).where(same2)
  for n in [20,60]:
   priorvalid=valid.shift().rolling(n,min_periods=n).sum().eq(n)
   priorsegmax=seg.shift().rolling(n,min_periods=n).max();priorsegmin=seg.shift().rolling(n,min_periods=n).min()
   known=priorvalid&valid&priorsegmax.eq(priorsegmin)&seg.eq(priorsegmax)
   high=c.shift().rolling(n,min_periods=n).max().where(known);a[f'prior{n}_high_close']=high
   a[f'distance_to_prior{n}_high_log']=np.log(c/high).where(known)
   nh=pd.Series(pd.NA,index=calendar,dtype='boolean');nh.loc[known]=c.loc[known].gt(high.loc[known]);a[f'newhigh{n}']=nh
   # A local crossing episode, not the first historical or future-defined high.
   cross=nh&~nh.shift();a[f'crossup{n}']=cross
  a['index_segment_id']=seg;out[r['series']]=a
 return out
def main():
 existing_only='--existing-only'in sys.argv;counter='--counterexisting'in sys.argv;bind(__file__)
 bind(ROOT/'EXTRACTION_CONTRACT.txt',CONTRACT_SHA)
 if counter:existing_only=True
 f=pd.read_parquet(bind(V4/'STUDY_STATES_2022_2026.parquet'));assert len(f)==97650
 count_fields=['N_U_t','N25valid','Nobserved','N_above20_t','N_above20_tminus5']
 counts=pd.read_parquet(bind(S/'industry_selection/channels_v2/INDUSTRY_OPPORTUNITIES_DAILY.parquet'),columns=['date','sector_id_static','Nstatic',*count_fields])
 f=f.merge(counts,on=['date','sector_id_static'],validate='one_to_one',suffixes=('','_v2'));assert len(f)==97650 and f.Nstatic.ge(f.N_U_t).all()
 for k in count_fields:assert f[k].eq(f[k+'_v2']).all();f=f.drop(columns=k+'_v2')
 market=pd.read_csv(bind(MARKET),parse_dates=['date']);calendar=pd.DatetimeIndex(market.date).as_unit('ns');dates=calendar.strftime('%Y-%m-%d').tolist();pos={d:i for i,d in enumerate(dates)}
 manifest=json.loads(bind(B/'INDUSTRY_MANIFEST.json').read_text());prices={}if existing_only else price_diagnostics(manifest,calendar)
 f=f.sort_values(['sector_id_static','date']).copy()
 for col in CHANGE_FIELDS:f['d1_'+col]=f.groupby('sector_id_static')[col].diff()
 lookup=f.set_index(['date','sector_id_static']);cutoffs={};cutoff_changes={}
 for day,g in f.groupby('date'):
  cutoffs[day]={'P':g.loc[g.P_order.eq(5)].iloc[0],'T':g.loc[g.T_order.eq(3)].iloc[0]}
 for day,cut in cutoffs.items():
  prev=dates[pos[day]-1]
  for prefix in ['P','T']:
   cutoff_changes[day,prefix]={k:(cut[prefix][k]-cutoffs[prev][prefix][k])if prev in cutoffs else np.nan for k in CHANGE_FIELDS}
 records=[]
 for case,role,anchor,sec in (COUNTER_CASES if counter else CASES):
  for relative in range(-5,16):
   day=dates[pos[anchor]+relative];r=lookup.loc[day,sec];record=r.to_dict()
   record.update(case_id=case,case_role=role,anchor_session=anchor,anchor_is_algorithmic_launch=False,date=day,sector_id_static=sec,relative_session=relative,asof_clock='SIGNAL_CLOSE',earliest_possible_action_session=dates[pos[day]+1])
   record['original_H1_score']=r.v3_H1_cache_same_date_score;record['original_H1_order']=r.v3_native_H1_order;record['P_state_mechanical_fact']=state_fact(r)
   record.update(compare(r,cutoffs[day]['P'],'P',cutoff_changes[day,'P']));record.update(compare(r,cutoffs[day]['T'],'T',cutoff_changes[day,'T']))
   if not existing_only:record.update(prices[sec].loc[pd.Timestamp(day)].to_dict())
   records.append(record)
 result=pd.DataFrame(records);assert len(result)==(63 if counter else 105)and not result.duplicated(['case_id','date']).any()
 basename='COUNTEREXAMPLE_EXISTING_FEATURE_PATHS'if counter else'EXISTING_FEATURE_PATHS'if existing_only else'CAUSAL_FEATURE_PATHS'
 result.to_parquet(O/(basename+'.parquet'),index=False);result.to_csv(O/(basename+'.csv'),index=False)
 pre='COUNTEREXAMPLE_'if counter else''
 save(pre+'SCHEMA.json',{'status':'EXISTING_FIELDS_READY'if existing_only else'COMPLETE','key':['case_id','date'],'main_rows':0 if counter else 84,'aux_rows':0 if counter else 21,'counterexample_rows':63 if counter else 0,'all_fields':result.columns.tolist(),'score_gap_sign':'candidate minus same-day cutoff score','score_gap_weights':{'P':{'p_Rp':'.6','p_B':'.4'},'T':{'p_R5':'.5','p_dB5':'.5'}},'d1_own':'same sector current minus prior common session; computed before case slicing','cutoff_line_d1':'current cutoff minus prior common-session cutoff; comparator industry may change','counts_scope':'Nstatic is current1709 pool industry members; N_U_t is that days valid liquid static subpool, not all historical industry stocks; counts do not impose any new gate','H1_is_score_order_not_No60_topK_funding_permission':True,'not_a_causal_single_feature_attribution':True,'P_state_is_carried_not_restarted_at_case_anchor':True,'all_values_asof_row_close':True,'formal_PIT':False,'no_new_signal_gates':True,'no_new_accounts':True,'newhigh':'current close strictly above prior20/60 maxclose, excluding current, complete common sessions and same segment','crossup':'Kleene newhigh(T) AND NOT newhigh(T-1); not historical first and no forward information'})
 save(pre+'SUMMARY.json',{'status':'EXISTING_FIELDS_READY'if existing_only else'COMPLETE','rows':len(result),'case_counts':result.groupby('case_id').size().to_dict(),'new_stock_source_reads':0,'new_accounts':0,'new_forward_labels':0,'gap_decompositions_exact':2*len(result)})
 save(pre+'SOURCE_SHA256.json',HASH);save('OUTPUT_SHA256.json',{str(p.resolve()):hashlib.sha256(p.read_bytes()).hexdigest()for p in O.iterdir()if p.is_file()and p.name!='OUTPUT_SHA256.json'})
 print(json.dumps({'complete':True,'existing_only':existing_only,'rows':len(result)}),flush=True)
if __name__=='__main__':main()
