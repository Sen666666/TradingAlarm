"""Post-hoc source-driven E0 confirmation coordinate; no new signals or ranks."""
from pathlib import Path
import hashlib,importlib.util,json
import pandas as pd
O=Path(__file__).resolve().parent;NAME='SUPPLEMENT_2025NOV28_SEMI_E0_ANCHOR_21'
HELPER_SHA='04cf39b25039020927dcc3fede017028eba58175388cdc6c0c9fae1972c7c0d3'
def main():
 spec=importlib.util.spec_from_file_location('frozen_v5_paths',O/'build_paths.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
 m.bind(O/'build_paths.py',HELPER_SHA);m.bind(__file__);m.bind(m.ROOT/'EXTRACTION_CONTRACT.txt',m.CONTRACT_SHA)
 untouched=[O/n for n in ['build_paths.py','CAUSAL_FEATURE_PATHS.parquet','COUNTEREXAMPLE_EXISTING_FEATURE_PATHS.parquet','OUTPUT_SHA256.json']]
 original_hash={str(p.resolve()):hashlib.sha256(p.read_bytes()).hexdigest()for p in untouched}
 basis=pd.read_parquet(m.bind(m.ROOT/'original_eligibility/ORIGINAL_INDUSTRY_E0_CP_EVENT_PATHS.parquet'))
 basis=basis[basis.case_id.eq('2026JAN5_SEMI')&basis.date.eq('2026-01-05')].iloc[0]
 assert basis.last_confirmed_low_confirmation_date=='2025-11-28'and basis.last_confirmed_low_pivot_date=='2025-11-21'
 f=pd.read_parquet(m.bind(m.V4/'STUDY_STATES_2022_2026.parquet'));count_fields=['N_U_t','N25valid','Nobserved','N_above20_t','N_above20_tminus5']
 counts=pd.read_parquet(m.bind(m.S/'industry_selection/channels_v2/INDUSTRY_OPPORTUNITIES_DAILY.parquet'),columns=['date','sector_id_static','Nstatic',*count_fields])
 f=f.merge(counts,on=['date','sector_id_static'],validate='one_to_one',suffixes=('','_v2'));assert len(f)==97650
 for k in count_fields:assert f[k].eq(f[k+'_v2']).all();f=f.drop(columns=k+'_v2')
 f=f.sort_values(['sector_id_static','date'])
 for col in m.CHANGE_FIELDS:f['d1_'+col]=f.groupby('sector_id_static')[col].diff()
 market=pd.read_csv(m.bind(m.MARKET),parse_dates=['date']);cal=pd.DatetimeIndex(market.date).as_unit('ns');dates=cal.strftime('%Y-%m-%d').tolist();pos={d:i for i,d in enumerate(dates)}
 anchor='2025-11-28';sec='URFI881121';chosen=dates[pos[anchor]-5:pos[anchor]+16];needed=set(chosen)|{dates[pos[d]-1]for d in chosen};cut={}
 for day,g in f[f.date.isin(needed)].groupby('date'):cut[day]={'P':g.loc[g.P_order.eq(5)].iloc[0],'T':g.loc[g.T_order.eq(3)].iloc[0]}
 manifest=json.loads(m.bind(m.B/'INDUSTRY_MANIFEST.json').read_text());manifest=[r for r in manifest if r['series']==sec];price=m.price_diagnostics(manifest,cal)[sec];lookup=f.set_index(['date','sector_id_static']);rows=[]
 for rel,day in zip(range(-5,16),chosen):
  r=lookup.loc[day,sec];z=r.to_dict();z.update(case_id='2025NOV28_SEMI_E0_ANCHOR',case_role='POST_HOC_SOURCE_DRIVEN_SUPPLEMENT',anchor_session=anchor,anchor_is_algorithmic_launch=False,anchor_basis='ORIGINAL_E0_LOW_CONFIRMATION_COORDINATE',anchor_source_pivot_date='2025-11-21',anchor_is_blind_preregistered=False,date=day,sector_id_static=sec,relative_session=rel,asof_clock='SIGNAL_CLOSE',earliest_possible_action_session=dates[pos[day]+1])
  z['original_H1_score']=r.v3_H1_cache_same_date_score;z['original_H1_order']=r.v3_native_H1_order;z['P_state_mechanical_fact']=m.state_fact(r)
  for prefix in ['P','T']:
   prev=dates[pos[day]-1];changes={k:cut[day][prefix][k]-cut[prev][prefix][k]for k in m.CHANGE_FIELDS};z.update(m.compare(r,cut[day][prefix],prefix,changes))
  z.update(price.loc[pd.Timestamp(day)].to_dict());rows.append(z)
 result=pd.DataFrame(rows);assert len(result)==21 and result.relative_session.tolist()==list(range(-5,16))
 result.to_parquet(O/(NAME+'.parquet'),index=False);result.to_csv(O/(NAME+'.csv'),index=False)
 checks=[]
 for day in [chosen[0],anchor,chosen[-1]]:
  a=m.price_diagnostics(manifest,cal[:pos[day]+1])[sec].loc[pd.Timestamp(day)];b=result[result.date.eq(day)].iloc[0]
  for col in a.index:assert (pd.isna(a[col])and pd.isna(b[col]))or a[col]==b[col]
  checks.append({'date':day,'prefix_exact_fields':len(a)})
 assert all(hashlib.sha256(Path(p).read_bytes()).hexdigest()==h for p,h in original_hash.items())
 m.save(NAME+'.SUMMARY.json',{'status':'COMPLETE','rows':21,'first_session':chosen[0],'last_session':chosen[-1],'anchor':anchor,'anchor_nature':'Post-hoc source-driven original E0 low confirmation coordinate; not blind preregistration or an optimal market launch','source_registration_basis_original_Jan5_row':{'low_confirmation_date':basis.last_confirmed_low_confirmation_date,'low_pivot_date':basis.last_confirmed_low_pivot_date},'original_Jan5_anchor_not_replaced':True,'original_files_unchanged':original_hash,'new_stock_reads':0,'new_accounts':0,'new_future_labels':0,'new_rankings':0,'new_signal_gates':0,'score_gap_decompositions_exact':42,'price_prefix_checks':checks,'schema_fields':result.columns.tolist()})
 m.save(NAME+'.SOURCE_SHA256.json',m.HASH)
 m.save(NAME+'.OUTPUT_SHA256.json',{str(p.resolve()):hashlib.sha256(p.read_bytes()).hexdigest()for p in [Path(__file__),*[O/(NAME+x)for x in ['.parquet','.csv','.SUMMARY.json','.SOURCE_SHA256.json']]]})
 print(json.dumps({'complete':True,'rows':len(result),'first':chosen[0],'last':chosen[-1]}),flush=True)
if __name__=='__main__':main()
