"""Additional entry-time joins and three case extracts from already saved 2022 ledgers."""
from pathlib import Path
import pandas as pd,numpy as np,json,hashlib,math
O=Path(__file__).resolve().parent;R=O.parent;E=R/'independent_channel_joint_economic_v1/economic_2022'
r=pd.read_csv(O/'PRICE_ROUND_ENTRY_FACTS.csv',low_memory=False)
mp=R/'momentum_persistence_breadth_v1/canonical_mu3_comparison_v2/COMMON_K_COMPARISON.parquet'
m=pd.read_parquet(mp);m['signal_day']=m.day.astype(str).str[:10];assert not m.duplicated(['sector','signal_day']).any()
r=r.merge(m[['sector','signal_day','M3_candidate','M3_right_known','M3_delta3','sector_stage']],on=['sector','signal_day'],how='left',validate='many_to_one');assert r.M3_candidate.notna().all()
r['M3_entry']=r.M3_candidate.map({1:'ON',0:'OFF',-1:'UNKNOWN'});r['prewindow_root']=r.root_day.lt('2022-01-01')
abp=E/'AB_DECISION_AUDIT.json';ab=pd.DataFrame(json.loads(abp.read_text()));ab['signal_day']=ab.day.str[:10];assert not ab.duplicated(['sid','signal_day']).any()
r=r.merge(ab[['sid','signal_day','decision_before_joint','close_check','I_qualified']],on=['sid','signal_day'],how='left',validate='many_to_one');r['actual_ab_close_diagnosis']=r.decision_before_joint.fillna('NO_ORIGINAL_AB_EVENT')
r['signal_current20high_in_raw_coordinate']=r.contemporary_prior20_high/r.adjustment_factor
r['probe_signal_S_in_raw_coordinate']=r.S_new/r.adjustment_factor
r['signal_root_break_margin']=r.C/r.U-1
r['signal_current20_break_margin']=r.C/r.contemporary_prior20_high-1
r['subsequent_add']=r.ADD_fees.gt(0)
assert r.loc[r.actual_buy,['old_sector_known','old_sector_observed_today','old_sector_rs_ready_fresh','old_sector_up']].all().all()
rr=r[r.common&r.actual_buy]
def stats(g):
 c=g[g.full_closed];u=g[g.status.str.contains('UNKNOWN')]
 return dict(registered_rounds=len(g),actual_buys=int(g.actual_buy.sum()),unique_stocks=int(g.sid.nunique()),closed_rounds=len(c),unknown_rounds=len(u),unknown_with_buy=int(u.actual_buy.sum()),closed_net=float(c.closed_total_pnl.sum()),PROBE_trade_net=float(c.PROBE_realized.sum()),ADD_trade_net=float(c.ADD_realized.sum()),net80_income=float(c.net80_income.sum()),fees_already_included=float(c.fees.sum()),profit_rounds=int(c.closed_total_pnl.gt(0).sum()),loss_rounds=int(c.closed_total_pnl.lt(0).sum()),unknown_known_cost=float(u.remaining_known_cost.sum()),unknown_realized_trade=float(u.realized_trade.sum()),unknown_confirmed_income=float(u.net80_income.sum()),unknown_fees=float(u.fees.sum()),median_root_age_sessions=float(g.root_age_sessions.median()),median_plan_risk=float(g.entry_risk.median()),median_risk_fraction=float(g.risk_fraction.median()),median_holding_sessions=float(c.holding_sessions.median()))
tables={}
for scope,g in [('ALL',r),('COMMON_ACTUAL',rr)]:
 for fields in [['M3_entry'],['participation','ticket'],['prewindow_root'],['ticket','break20_fact'],['actual_ab_close_diagnosis'],['M3_entry','stock_gate'],['M3_entry','signal_quarter'],['subsequent_add'],['signal_quarter','ticket'],['status']]:
  rows=[]
  for key,s in g.groupby(fields,dropna=False):
   key=key if isinstance(key,tuple) else (key,);rows.append(dict(zip(fields,key),**stats(s)))
  tables[scope+'__'+'__'.join(fields)]=rows
cells=rr.groupby('entry_cell').closed_total_pnl.sum().sort_values();top=list(cells.index[:3]);rr=rr.copy();rr['nonoverlap_top_losses']=rr.entry_cell.where(rr.entry_cell.isin(top),'ALL_OTHER_ENTRY_CELLS')
tables['COMMON_TOP3_PLUS_ALL_REMAINDER']=[dict(entry_cell=k,**stats(g)) for k,g in rr.groupby('nonoverlap_top_losses')]
rep=json.loads((E/'COMPARISON_REPORT_RECOVERED.json').read_text());rounds=pd.read_csv(E/'joint/ROUNDS.csv');acts=pd.read_csv(E/'joint/ACTIONS.csv')
full_sids=['000977.SZ','605118.SH','605020.SH'];brief_sids=['002031.SZ','002174.SZ','603516.SH'];cases={}
cols=['round_id','name','signal_day','entry_day','next_common_open_day','entry_price','entry_open','entry_q','entry_gross','entry_fee','entry_floor_raw','entry_risk','price_buy_number','all_strategy_buy_number','root_day','a_day','root_age_sessions','ticket','phase','Q','R','old_e0_ready','old_e0_target','old_i_target','old_i_buy','old_ab_raw_permit','actual_ab_close_diagnosis','M3_entry','raw_close','signal_current20high_in_raw_coordinate','probe_signal_S_in_raw_coordinate','contemporary_20high_break','exit_day','exit_price','status','closed_total_pnl','fees','net80_income','buy_cost','PROBE_realized','ADD_realized','holding_sessions']
for sid in full_sids+brief_sids:
 price=r[r.sid.eq(sid)].sort_values('entry_day')
 cases[sid]={'detail_level':'FULL' if sid in full_sids else 'SUPPORTING_COUNTEREXAMPLE','price_rounds':price[cols].to_dict('records'),'all_joint_rounds':rounds[rounds.sid.eq(sid)][['round_id','owner_lane','signal_day','entry_day','entry_price','exit_day','status','net_pnl']].to_dict('records'),'saved_joint_actions':acts[acts.sid.eq(sid)].to_dict('records'),'baseline_lane':[x for x in rep['lane_rows'] if x['sid']==sid and x['arm']=='baseline' and x['lane']=='AB'][0]}
def clean(x):
 if isinstance(x,dict):return {str(k):clean(v) for k,v in x.items()}
 if isinstance(x,(tuple,list)):return [clean(v) for v in x]
 if isinstance(x,(np.integer,)):return int(x)
 if isinstance(x,(np.floating,float)):return float(x) if math.isfinite(x) else None
 if isinstance(x,(np.bool_,)):return bool(x)
 return x
result={'M3_unknown_semantics':'M3_candidate=-1 is UNKNOWN from fixed-denominator uncertainty bounds, not OFF.','tables':tables,'cases':cases,'actual_price_stock_count':int(r[r.actual_buy].sid.nunique()),'actual_signal_industry_gate_all_four_true':True,'read_only_qa':{'no_economic_consumer_import_or_call':True,'ledger_and_price_source_hashes_recorded':True,'all_2411_receipts_joined':True,'all_M3_joined':True,'same_day_AB_legal_pass_for_PRICE_entries':int(r.decision_before_joint.eq('PASS_TO_JOINT_QUEUE').sum())}}
(O/'SUPPLEMENT_AND_CASES.json').write_text(json.dumps(clean(result),ensure_ascii=False,indent=2)+'\n');r.to_csv(O/'PRICE_ROUND_ENTRY_FACTS_WITH_M3.csv',index=False)
h=json.loads((O/'SOURCE_HASHES.json').read_text())
for p in [mp,abp,E/'CORE_SUMMARY_RECOVERED.json',E/'FROZEN_RESPONSIBILITIES.json',R/'independent_channel_joint_economic_v1/post_audit/INDEPENDENT_ECONOMIC_AUDIT_2022.json']:
 h[str(p)]=hashlib.sha256(p.read_bytes()).hexdigest()
(O/'SOURCE_HASHES.json').write_text(json.dumps(h,indent=2)+'\n')
for k in ['COMMON_TOP3_PLUS_ALL_REMAINDER','COMMON_ACTUAL__participation__ticket','COMMON_ACTUAL__prewindow_root','COMMON_ACTUAL__ticket__break20_fact','COMMON_ACTUAL__subsequent_add','COMMON_ACTUAL__actual_ab_close_diagnosis','ALL__status']:
 print('\n'+k);print(pd.DataFrame(tables[k]).to_string(index=False))
print('\nCASES_M3',r[r.sid.isin(full_sids)][['sid','signal_day','M3_entry','signal_current20high_in_raw_coordinate']].to_string(index=False))
