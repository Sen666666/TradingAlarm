"""Read frozen 2022 ledgers/market facts; no strategy/economic imports or reruns."""
import json, hashlib, math
from pathlib import Path
from collections import defaultdict, deque
import numpy as np
import pandas as pd
R=Path('/Users/bytedance/Documents/Codex/2026-11-06/entry_state_selection_v1')
O=Path(__file__).resolve().parent
E=R/'independent_channel_joint_economic_v1/economic_2022'
paths=[E/'joint/ROUNDS.csv',E/'joint/ACTIONS.csv',E/'joint/CLAIMS.json',E/'COMPARISON_REPORT_RECOVERED.json',R/'independent_channel_full1709_preflight_v1/overlap/RECEIPT_CONDITIONAL_OVERLAP.parquet']
H={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}
rep=json.loads(paths[3].read_text()); rounds=pd.read_csv(paths[0]); actions=pd.read_csv(paths[1])
ov=pd.read_parquet(paths[4]);ov=ov[ov.window.astype(str)=='2022'].copy();ov['signal_day']=ov.day.dt.strftime('%Y-%m-%d')
assert not ov.duplicated(['sid','signal_day']).any()
r=rounds[rounds.owner_lane=='PRICE'].merge(ov,on=['sid','signal_day'],how='left',suffixes=('','_m'),indicator=True,validate='many_to_one');assert r._merge.eq('both').all()
common=set(rep['summary'][0]['common_covered_sids']);r['common']=r.sid.isin(common)
buy=actions[actions.side.eq('buy_core')].sort_values(['day','sid','round_id']).copy(); buy['all_strategy_buy_number']=buy.groupby('sid').cumcount()+1
buy=buy.merge(rounds[['round_id','owner_lane']],on='round_id',validate='one_to_one');pb=buy[buy.owner_lane.eq('PRICE')].copy();pb['price_buy_number']=pb.groupby('sid').cumcount()+1
r=r.merge(pb[['round_id','all_strategy_buy_number','price_buy_number']],on='round_id',how='left',validate='one_to_one');r['actual_buy']=r.price_buy_number.notna();r['full_closed']=r.status.eq('COMPLETE_CONDITIONAL_STOCK_ROUND')
r['participation']=np.where(~r.actual_buy,'NO_BUY',np.where(r.all_strategy_buy_number.eq(1),'FIRST_ALL_STRATEGY_BUY',np.where(r.price_buy_number.eq(1),'FIRST_PRICE_AFTER_AB','REPEAT_PRICE')))
r['stock_gate']=np.where(~r.old_e0_ready.fillna(False),'E0_NOT_READY',np.where(~r.old_e0_target.fillna(False),'E0_OFF',np.where(~r.old_i_target.fillna(False),'E0_ON_I_OFF','E0_ON_I_ON')))
r['ticket']=np.where(r.born,'ROOT_BIRTH','CONTINUING_FRONTIER')
r['signal_quarter']=pd.to_datetime(r.signal_day).dt.to_period('Q').astype(str)
r['root_age_calendar_days']=(pd.to_datetime(r.signal_day)-r.root_day).dt.days
r['root_age_bucket']=pd.cut(r.root_age_calendar_days,[-1,0,5,20,60,np.inf],labels=['0','1_5','6_20','21_60','61_plus']).astype(str)
r['ab_permit_fact']=np.where(r.old_ab_I_PVR_qualified_permit,'AB_I_PVR_EVENT',np.where(r.old_ab_raw_permit,'AB_EVENT_I_OR_PVR_UNQUALIFIED','NO_AB_EVENT'))
r['risk_fraction']=r.entry_risk/r.entry_gross
# Accounting is exact FIFO over the saved normalized report, not a counterfactual.
acc=defaultdict(lambda: defaultdict(float));lots=defaultdict(deque)
for a in sorted(rep['normalized_actions'],key=lambda a:(str(a['known_day']),int(a['sequence']))):
 if a['arm']!='joint' or a['lane']!='PRICE':continue
 rid=a['round_id'];role=a['role'];q,p,f=float(a['q']),float(a['price']),float(a['fee']);t=acc[rid];t['fees']+=f;t[role+'_fees']+=f
 if a['side']=='BUY':
  lots[(rid,role)].append([q,q*p+f]);t['buy_cost']+=q*p+f
 else:
  rem=q;cost=0
  while rem>1e-8:
   z=lots[(rid,role)][0];take=min(rem,z[0]);c=z[1]*take/z[0];cost+=c;rem-=take;z[0]-=take;z[1]-=c
   if z[0]<1e-8:lots[(rid,role)].popleft()
  t['realized_trade']+=q*p-f-cost;t[role+'_realized']+=q*p-f-cost
for (rid,role),ls in lots.items():acc[rid]['remaining_known_cost']+=sum(z[1] for z in ls)
for c in rep['normalized_claims']:
 if c['arm']=='joint' and c['lane']=='PRICE' and c['legal_ex_confirmed'] is True:
  acc[c['round_id']]['net80_income']+=float(c['amount']);acc[c['round_id']]['receivable']+=float(c['receivable'])
cols=['fees','PROBE_fees','ADD_fees','buy_cost','realized_trade','PROBE_realized','ADD_realized','remaining_known_cost','net80_income','receivable']
for c in cols:r[c]=r.round_id.map(lambda rid:acc[rid][c])
r['identifiable_realized_plus_income']=r.realized_trade+r.net80_income
r['closed_total_pnl']=r.identifiable_realized_plus_income.where(r.full_closed)
assert np.allclose(r.loc[r.full_closed,'closed_total_pnl'],r.loc[r.full_closed,'net_pnl'],atol=1e-7)
assert abs(r.loc[r.common,'closed_total_pnl'].sum()+1187457.6691341577)<1e-7
assert abs(r.fees.sum()-r.all_fees.sum())<1e-7
# Read same sealed prepared adjusted bars. Compute contemporary prior20 High only, no model replay.
mp=Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/universe-cp1-inputs-20261031/STOCK_MANIFEST.json');manifest={x['symbol']:x for x in json.loads(mp.read_text())};H[str(mp)]=hashlib.sha256(mp.read_bytes()).hexdigest()
cp=Path('/Users/bytedance/Documents/ChatGPT/money/TradingAlarm/runtime/market/update-20261030-153010-c551af/prepared/h1.npz');H[str(cp)]=hashlib.sha256(cp.read_bytes()).hexdigest()
with np.load(cp,allow_pickle=False) as z:cal=pd.DatetimeIndex(z['dates'])
cal=cal[cal<='2022-12-31'];current=[]
for sid,g in r.groupby('sid',sort=False):
 m=manifest[sid];path=Path(next(k for k in m['source_sha256'] if k.endswith('/signal.parquet')));h=hashlib.sha256(path.read_bytes()).hexdigest();assert h==m['source_sha256'][str(path)];H[str(path)]=h
 raw=pd.read_parquet(path,columns=['high','close','source_kind','source_path','segment_id','price_eligible','source_invalid']).reindex(cal)
 hi=raw.high.rolling(20,min_periods=20).max().shift(1)
 for z in g.itertuples():
  day=pd.Timestamp(z.signal_day);ix=cal.get_loc(day);q=raw.iloc[ix-20:ix+1]
  same=q[['source_kind','source_path','segment_id']].nunique(dropna=False).le(1).all();valid=q.price_eligible.fillna(False).all() and not q.source_invalid.fillna(True).any()
  hh=float(hi.loc[day]) if same and valid else np.nan
  assert math.isclose(float(raw.loc[day,'close']),float(z.C),rel_tol=1e-11)
  rd=pd.Timestamp(z.root_day);age=int(((cal>rd)&(cal<=day)).sum())
  current.append({'round_id':z.round_id,'contemporary_prior20_high':hh,'contemporary_20high_break':None if not np.isfinite(hh) else bool(z.C>hh),'root_age_sessions':age})
 print('market facts',sid,len(current),flush=True) if len(current)%300==0 else None
r=r.merge(pd.DataFrame(current),on='round_id',validate='one_to_one');r['break20_fact']=r.contemporary_20high_break.map({True:'BREAKS_CURRENT_20HIGH',False:'DOES_NOT_BREAK_CURRENT_20HIGH'}).fillna('UNKNOWN')
assert r.loc[r.born,'contemporary_20high_break'].eq(True).all()
r['entry_cell']=r.participation+' | '+r.ticket+' | '+r.stock_gate+' | '+r.phase
risk=pd.DataFrame(rep['round_risk_holding_diagnostics']);risk=risk[(risk.arm=='joint')&(risk.lane=='PRICE')]
r=r.merge(risk[['round_id','holding_sessions','gap_status']],on='round_id',how='left',validate='one_to_one')
def summarise(g):
 closed=g[g.full_closed];unk=g[g.status.str.contains('UNKNOWN')]
 return {'n_registered_rounds':len(g),'n_actual_buy':int(g.actual_buy.sum()),'unique_sids':g.sid.nunique(),'n_closed':int(g.full_closed.sum()),'n_unknown':len(unk),'unknown_with_buy':int(unk.actual_buy.sum()),'no_buy':int((~g.actual_buy).sum()),'closed_net':closed.closed_total_pnl.sum(),'closed_probe_trade':closed.PROBE_realized.sum(),'closed_add_trade':closed.ADD_realized.sum(),'closed_income':closed.net80_income.sum(),'closed_fees_included':closed.fees.sum(),'closed_buy_cost':closed.buy_cost.sum(),'closed_profit_count':int(closed.closed_total_pnl.gt(0).sum()),'closed_loss_count':int(closed.closed_total_pnl.lt(0).sum()),'closed_gross_profitable_net':closed.loc[closed.closed_total_pnl.gt(0),'closed_total_pnl'].sum(),'closed_gross_losing_net':closed.loc[closed.closed_total_pnl.lt(0),'closed_total_pnl'].sum(),'unknown_known_realized':unk.realized_trade.sum(),'unknown_confirmed_income':unk.net80_income.sum(),'unknown_remaining_known_cost':unk.remaining_known_cost.sum(),'unknown_fees_paid':unk.fees.sum(),'closed_net_loss_over_3000_count':int(closed.closed_total_pnl.lt(-3000).sum()),'closed_holding_sessions_median':closed.holding_sessions.median(),'root_age_sessions_median':g.root_age_sessions.median()}
result={'scope':'Read-only attribution of frozen actual conditional PRICE ledger. Not an economic rerun, account return, or proposed entry filter. UNKNOWN total PnL remains unknown. Fees already included in trade PnL.','join':{'price_rounds':len(r),'missing_market_join':int(r._merge.ne('both').sum()),'duplicate_overlap_keys':int(ov.duplicated(['sid','signal_day']).sum()),'common_stock_denominator':len(common)},'all_price':summarise(r),'common_price':summarise(r[r.common]),'tables':{}}
for scope,g in [('ALL',r),('COMMON',r[r.common])]:
 for fields in [['status'],['participation'],['price_buy_number'],['stock_gate'],['phase'],['ticket'],['signal_quarter'],['root_age_bucket'],['ab_permit_fact'],['break20_fact'],['ticket','phase'],['participation','ticket'],['signal_quarter','participation'],['entry_cell'],['ticket','break20_fact'],['stock_gate','ab_permit_fact']]:
  table=[]
  for key,sub in g.groupby(fields,dropna=False,observed=True):
   key=key if isinstance(key,tuple) else (key,);table.append(dict(zip(fields,key),**summarise(sub)))
  result['tables'][scope+'__'+'__'.join(fields)]=table
# Exact totals reconcile and economic inputs unchanged.
for p in paths:assert hashlib.sha256(p.read_bytes()).hexdigest()==H[str(p)]
def clean(x):
 if isinstance(x,dict):return {str(k):clean(v) for k,v in x.items()}
 if isinstance(x,(tuple,list)):return [clean(v) for v in x]
 if isinstance(x,(np.integer,)):return int(x)
 if isinstance(x,(np.floating,)):return None if not np.isfinite(x) else float(x)
 if isinstance(x,(np.bool_,)):return bool(x)
 if isinstance(x,float) and not math.isfinite(x):return None
 return x
(O/'ATTRIBUTION.json').write_text(json.dumps(clean(result),ensure_ascii=False,indent=2)+'\n')
r.to_csv(O/'PRICE_ROUND_ENTRY_FACTS.csv',index=False)
(O/'SOURCE_HASHES.json').write_text(json.dumps(H,indent=2)+'\n')
print(json.dumps(clean({k:v for k,v in result.items() if k!='tables'}),ensure_ascii=False,indent=2))
for name in ['COMMON__participation','COMMON__ticket__phase','COMMON__signal_quarter','COMMON__stock_gate','COMMON__break20_fact','COMMON__ab_permit_fact']:
 print('\n'+name);print(pd.DataFrame(result['tables'][name]).to_string(index=False))
print('\nTOP_CELLS');print(pd.DataFrame(result['tables']['COMMON__entry_cell']).sort_values('closed_net').head(12).to_string(index=False))
