"""Causal-prefix and exact cache checks on the frozen v5 extraction."""
from pathlib import Path
import hashlib,importlib.util,json
import pandas as pd
O=Path(__file__).resolve().parent
def main():
 spec=importlib.util.spec_from_file_location('v5_paths',O/'build_paths.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
 m.bind(__file__);m.bind(m.ROOT/'EXTRACTION_CONTRACT.txt',m.CONTRACT_SHA)
 main=pd.read_parquet(m.bind(O/'CAUSAL_FEATURE_PATHS.parquet'));counter=pd.read_parquet(m.bind(O/'COUNTEREXAMPLE_EXISTING_FEATURE_PATHS.parquet'))
 original=pd.read_parquet(m.bind(m.V4/'STUDY_STATES_2022_2026.parquet')).set_index(['date','sector_id_static'])
 checked=0
 for r in pd.concat([main,counter]).to_dict('records'):
  z=original.loc[r['date'],r['sector_id_static']]
  for col in original.columns:
   a,b=r[col],z[col];assert (pd.isna(a)and pd.isna(b))or a==b,(r['case_id'],r['date'],col)
   checked+=1
 market=pd.read_csv(m.bind(m.MARKET),parse_dates=['date']);cal=pd.DatetimeIndex(market.date).as_unit('ns');pos={str(d.date()):i for i,d in enumerate(cal)}
 manifest=json.loads(m.bind(m.B/'INDUSTRY_MANIFEST.json').read_text());prefix=[]
 pricecols=['index_close','index_r1_log','prior20_high_close','prior60_high_close','distance_to_prior20_high_log','distance_to_prior60_high_log','newhigh20','newhigh60','crossup20','crossup60','index_segment_id']
 for case,_,anchor,sec in m.CASES:
  ref=main[main.case_id.eq(case)].set_index('date')
  for rel in [-5,0,15]:
   end=cal[pos[anchor]+rel];day=str(end.date());a=m.price_diagnostics([r for r in manifest if r['series']==sec],cal[:pos[day]+1])[sec].loc[end]
   for col in pricecols:
    b=ref.loc[day,col];assert (pd.isna(a[col])and pd.isna(b))or a[col]==b,(case,day,col)
   prefix.append({'case_id':case,'date':day,'relative_session':rel,'price_fields_checked':len(pricecols),'calendar_prefix_exact':True})
 # Shared price leg for the already-frozen software failure window only.
 sec='URFI881272';anchor='2024-10-08';z=m.price_diagnostics([r for r in manifest if r['series']==sec],cal)[sec]
 selected=cal[pos[anchor]-5:pos[anchor]+16];z=z.loc[selected].copy();z['date']=selected.strftime('%Y-%m-%d');z['case_id']='2024OCT8_SOFTWARE';z['sector_id_static']=sec;z['relative_session']=range(-5,16)
 z.reset_index(drop=True).to_parquet(O/'COUNTEREXAMPLE_SOFTWARE_PRICE_PATHS.parquet',index=False);z.to_csv(O/'COUNTEREXAMPLE_SOFTWARE_PRICE_PATHS.csv',index=False)
 m.save('PRICE_PREFIX_CHECKS.json',prefix)
 fields=['case_id','date','sector_id_static','industry_static','relative_session','Rp','p_Rp','B_now','p_B','Nstatic','N_U_t','N_above20_t','N_above20_tminus5','rs_ind5','p_R5','dB5_paired','p_dB5','P_score','P_order','P_mature','P_state_mechanical_fact','P_cutoff_industry','P_cutoff_Nstatic','P_cutoff_N_U_t','P_gap_vs_cutoff_exact','P_gap_contribution_p_Rp_exact','P_gap_contribution_p_B_exact','T_score','T_order','T_cutoff_industry','T_cutoff_Nstatic','T_cutoff_N_U_t','T_cutoff_N_above20_t','T_cutoff_N_above20_tminus5','T_gap_vs_cutoff_exact','T_gap_contribution_p_R5_exact','T_gap_contribution_p_dB5_exact','original_H1_order',*pricecols]
 m.save('FINAL_KEY_FACTS.json',{'anchor_rows':main[main.relative_session.eq(0)][fields].to_dict('records'),'not_single_feature_causal_attribution':True})
 m.save('VERIFICATION_SUMMARY.json',{'main_and_aux_rows':len(main),'counter_existing_rows':len(counter),'counter_software_price_rows':len(z),'exact_original_cached_fields_checked':checked,'all_cached_fields_exact':True,'price_prefixes':len(prefix),'price_prefix_fields_checked':len(prefix)*len(pricecols),'all_prefix_exact':True,'new_stock_source_reads':0,'new_accounts':0,'new_forward_labels':0,'new_signal_gates':0})
 (O/'PREPARATION_HISTORY_NOTE.txt').write_text('EXISTING_FEATURE_PATHS及EXISTING_KEY_FACTS是首批历史准备交付，不含最终全部Δ/计数/price。正式主84+辅助21见CAUSAL_FEATURE_PATHS；反例原P/T63见COUNTEREXAMPLE_EXISTING_FEATURE_PATHS；反例软件price21另表，地产/多元金融price由burst_raw线负责。以上均不重算策略或账户。\n')
 m.save('VERIFICATION_SOURCE_SHA256.json',m.HASH)
 m.save('OUTPUT_SHA256.json',{str(p.resolve()):hashlib.sha256(p.read_bytes()).hexdigest()for p in O.iterdir()if p.is_file()and p.name!='OUTPUT_SHA256.json'})
 print(json.dumps({'complete':True,'main_rows':len(main),'counter_rows':len(counter),'prefixes':len(prefix),'cache_fields_exact':checked}),flush=True)
if __name__=='__main__':main()
