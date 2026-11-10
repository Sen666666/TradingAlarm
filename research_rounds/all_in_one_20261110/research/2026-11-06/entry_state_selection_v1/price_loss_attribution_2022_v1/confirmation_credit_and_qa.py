"""Read-only historical confirmation-age diagnostics and attribution consistency QA."""
from pathlib import Path
import pandas as pd,numpy as np,json,hashlib,math
O=Path(__file__).resolve().parent;R=O.parent;r=pd.read_csv(O/'PRICE_ROUND_ENTRY_FACTS_WITH_M3.csv',low_memory=False).copy()
cp=Path('/Users/bytedance/Documents/ChatGPT/money/TradingAlarm/runtime/market/update-20261030-153010-c551af/prepared/h1.npz')
with np.load(cp,allow_pickle=False) as z:cal=pd.DatetimeIndex(z['dates'])
r['confirmation_age_sessions']=[int(((cal>pd.Timestamp(c))&(cal<=pd.Timestamp(d))).sum()) if pd.notna(c) else np.nan for c,d in zip(r.confirmed_at,r.signal_day)]
r['signal_amount_over_frozen_B']=r.amount/r.B
p=R/'independent_channel_full1709_preflight_v1/DAILY_STATES.parquet'
d=pd.read_parquet(p,columns=['sid','day','window','Q','root_day']);d=d[d.window.astype(str).eq('2022')].sort_values(['sid','day']);d['previous_Q']=d.groupby('sid').Q.shift();d['previous_root_day']=d.groupby('sid').root_day.shift();d['signal_day']=d.day.astype(str).str[:10]
r=r.merge(d[['sid','signal_day','previous_Q','previous_root_day']],on=['sid','signal_day'],how='left',validate='many_to_one');same=pd.to_datetime(r.root_day).eq(r.previous_root_day);r['current_day_credit_increment_from_saved_daily']=r.Q.sub(r.previous_Q).where(same);r['credit_increment_known']=same&r.Q.notna()&r.previous_Q.notna()
rr=r[r.common&r.actual_buy];x=rr[rr.ticket.eq('CONTINUING_FRONTIER')&rr.phase.eq('CONFIRMED')]
def desc(s):return {str(k):float(v) for k,v in s.describe(percentiles=[.1,.25,.5,.75,.9]).items()}
def agg(g):return {'n':len(g),'net':float(g.closed_total_pnl.sum()),'confirm_age_distribution':desc(g.confirmation_age_sessions),'current_Q_increment_known_n':int(g.credit_increment_known.sum()),'Q_increment_distribution_known_only':desc(g.current_day_credit_increment_from_saved_daily),'amount_over_B_distribution':desc(g.signal_amount_over_frozen_B)}
result={'semantic_scope':'CONFIRMED is retained historical evidence Q>=R, not current-day volume strength or new confirmation. Age is a signal-time fact, not a proposed filter. Current-day increments are differences of saved market Q only when previous row shares same root; warm-prefix absent values stay unknown.','common_continuing_confirmed':agg(x),'common_first_all_continuing_confirmed':agg(x[x.participation.eq('FIRST_ALL_STRATEGY_BUY')]),'confirmed_now_split':{str(k):agg(g) for k,g in x.groupby('confirmed_now')},'main_loss_cell':agg(x[x.participation.eq('FIRST_ALL_STRATEGY_BUY')&x.stock_gate.eq('E0_ON_I_ON')]),'cases':r[r.sid.isin(['000977.SZ','605118.SH','605020.SH'])][['round_id','signal_day','root_day','confirmed_at','confirmed_now','confirmation_age_sessions','Q','R','current_day_credit_increment_from_saved_daily','signal_amount_over_frozen_B']].to_dict('records')}
qa={'price_round_count':len(r),'actual_price_buy_count':int(r.actual_buy.sum()),'actual_price_stock_count':int(r[r.actual_buy].sid.nunique()),'common_actual_price_buy_count':len(rr),'market_receipt_join_missing':int(r._merge.ne('both').sum()),'all_actual_entries_at_same_earliest_common_open':bool(r.loc[r.actual_buy,'entry_day'].eq(r.loc[r.actual_buy,'next_common_open_day']).all()),'all_root_births_break_contemporary_prior20_high':bool(r.loc[r.born,'contemporary_20high_break'].eq(True).all()),'all_common_closed':bool(rr.full_closed.all()),'all_price_closed_exit_old_S':bool(r.loc[r.full_closed,'exit_reason'].eq('PRICE_OLD_S_EXIT').all()),'common_total_exact':abs(rr.closed_total_pnl.sum()+1187457.6691341577)<1e-7,'maximum_entry_plan_risk':float(r.entry_risk.max()),'sources_changed':[],'economic_rerun_count':0,'counterfactual_profit_run_count':0,'production_files_modified':False,'original_ledger_modified':False,'final_exit_protection_reconstructed':False}
h=json.loads((O/'SOURCE_HASHES.json').read_text())
for path,digest in h.items():
 if hashlib.sha256(Path(path).read_bytes()).hexdigest()!=digest:qa['sources_changed'].append(path)
qa['all_primary_sources_unchanged']=not qa['sources_changed'];assert qa['all_primary_sources_unchanged']
for file,prefix,target in [('ATTRIBUTION.json','COMMON__',1187457.6691341577),('SUPPLEMENT_AND_CASES.json','COMMON',1187457.6691341577)]:
 j=json.loads((O/file).read_text())
 for name,rows in j['tables'].items():
  if name.startswith(prefix):assert abs(sum(z['closed_net'] for z in rows)+target)<1e-7,name
qa['every_common_grouping_complete_net_conservation']=True
assert qa['all_actual_entries_at_same_earliest_common_open']
for field in ['common_total_exact','all_common_closed','all_root_births_break_contemporary_prior20_high','all_price_closed_exit_old_S']:assert qa[field]
def clean(x):
 if isinstance(x,dict):return {str(k):clean(v) for k,v in x.items()}
 if isinstance(x,list):return [clean(v) for v in x]
 if isinstance(x,(float,np.floating)):return float(x) if math.isfinite(x) else None
 if isinstance(x,(np.integer,)):return int(x)
 if isinstance(x,(np.bool_,)):return bool(x)
 return x
(O/'CONFIRMATION_CREDIT.json').write_text(json.dumps(clean(result),ensure_ascii=False,indent=2)+'\n');(O/'READ_ONLY_QA.json').write_text(json.dumps(clean(qa),ensure_ascii=False,indent=2)+'\n')
r.to_csv(O/'PRICE_ROUND_ATTRIBUTION_FINAL.csv',index=False)
h[str(p)]=hashlib.sha256(p.read_bytes()).hexdigest();(O/'SOURCE_HASHES.json').write_text(json.dumps(h,indent=2)+'\n')
print(json.dumps(clean(qa),ensure_ascii=False,indent=2));print(json.dumps(clean(result['cases']),ensure_ascii=False,indent=2));print('MAIN_LOSS_CELL',json.dumps(clean(result['main_loss_cell']),ensure_ascii=False))
