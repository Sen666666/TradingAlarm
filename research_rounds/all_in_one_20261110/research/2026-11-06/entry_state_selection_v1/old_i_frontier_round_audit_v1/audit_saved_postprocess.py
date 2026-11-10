"""Frozen read-only attribution; no strategy/consumer/economic execution imports."""
from pathlib import Path
from collections import defaultdict
from decimal import Decimal as D
import json, hashlib, time, math
import numpy as np
import pandas as pd
O=Path(__file__).resolve().parent; R=O.parent
J=R/'independent_channel_joint_economic_v1'
M=Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/universe-cp1-inputs-20261031/STOCK_MANIFEST.json')
HFILE=Path('/Users/bytedance/Documents/ChatGPT/money/TradingAlarm/runtime/market/update-20261030-153010-c551af/prepared/h1.npz')
HASHES={}
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def src(p,expected=None):
 p=Path(p);h=sha(p)
 if expected:assert h==expected,('SOURCE_HASH',str(p))
 if str(p) in HASHES:assert h==HASHES[str(p)]
 HASHES[str(p)]=h;return p
def clean(x):
 if isinstance(x,dict):return {str(k):clean(v) for k,v in x.items()}
 if isinstance(x,(list,tuple,np.ndarray)):return [clean(v) for v in x]
 if isinstance(x,(pd.Timestamp,Path)):return str(x)
 if isinstance(x,np.generic):return clean(x.item())
 if isinstance(x,float) and not math.isfinite(x):return None
 return x
def dump(n,x):
 with (O/n).open('x') as f:json.dump(clean(x),f,ensure_ascii=False,indent=2,allow_nan=False);f.write('\n')
def out(n,x):assert not (O/n).exists();x.to_csv(O/n,index=False)
def csv(p,**kw):return pd.read_csv(src(p),low_memory=False,float_precision='round_trip',**kw)
def js(p):return json.loads(src(p).read_text())
def true(x):return pd.notna(x) and x in (True,1,'True')
def tri(x):return None if pd.isna(x) or x not in (True,False,0,1) else bool(x)
src(__file__);proto=js(O/'PROTOCOL.json')
began=time.monotonic()
manifest={x['symbol']:x for x in js(M)}
with np.load(src(HFILE),allow_pickle=False) as hh:cal=pd.DatetimeIndex(hh['dates'])
cal=cal[cal<='2024-12-31']
ds=[];regids=[];expected_files={}
for year in (2022,2024):
 p=J/f'baseline_regression_{year}';qa=js(p/'EXACT_REGRESSION_QA.json')
 assert qa['result']=='PASS_PRICE_OFF_EXACT' and qa['price_enabled'] is False
 for n,v in qa['checks'].items():
  fn=p/(n+'.json' if n in ['CLAIMS','BRIDGES','LEDGER_QA'] else n+'.csv')
  if year==2022 and n in ['CORE_AND_FULL_ROUNDS','FINANCIAL_COVERAGE']:fn=p/'postprocess_completion'/fn.name
  src(fn,v['actual_file_sha256']);expected_files[str(fn)]=v['actual_file_sha256']
 d=csv(p/'DECISIONS.csv',usecols=['event_id','day','sid','name','industry','sector','event_type','I_qualified','PVR_known','arm','selected','stock_state_before','decision','round_id','blocking_round_id'])
 d['year']=year; assert d.arm.eq('A_UNION_B').all()
 ds.append(d)
 q=csv(p/'ROUNDS.csv',usecols=['round_id','event_id','sid','signal_day','event_type','status','entry_day','status_day','exit_day','arm'])
 q['year']=year;regids.append(q)
dec=pd.concat(ds,ignore_index=True);registered=pd.concat(regids,ignore_index=True)
assert not dec.duplicated(['year','event_id']).any()
assert set(zip(dec.loc[dec.selected,'year'],dec.loc[dec.selected,'round_id']))==set(zip(registered.year,registered.round_id))
queries=dec[['sid','day']].drop_duplicates()
query_by={sid:set(g.day) for sid,g in queries.groupby('sid')}
overcols=['sid','day','old_i_epoch','old_i_buy','old_i_target','old_e0_target','old_epoch_lineage_known','old_epoch_lineage_reason','old_cp_fresh','old_cp_trace_known']
ov=pd.read_parquet(src(R/'independent_channel_full1709_preflight_v1/overlap/DAILY_OVERLAP.parquet'),columns=overcols)
ov['day']=ov.day.dt.strftime('%Y-%m-%d')
ov=queries.merge(ov,on=['sid','day'],how='left',validate='one_to_one')
ovmap=ov.set_index(['sid','day']).to_dict('index')
features=[];coverage=[];epochs_out=[];mismatch=[]

for sid in sorted(query_by):
 rec=manifest[sid];ex={**rec['source_sha256'],**rec['output_sha256']}
 for p in [rec['refs']['facts'],rec['refs']['CP1'],next(p for p in rec['source_sha256'] if p.endswith('/signal.parquet'))]:src(p,ex[p])
seal=js(O/'FEATURE_SEAL.json')
assert all(sha(O/n)==h for n,h in seal.items())
f=csv(O/'SIGNAL_STATE_PRELABEL.csv')
pre=csv(O/'ALL_AB_DECISIONS_PRELABEL.csv')
mismatch=[];features=f.to_dict('records')
# Only below this seal do we load economic values.
allrounds=[];actionrows=[];recon=[];finrows=[];checks=[]
for year in (2022,2024):
 p=J/f'baseline_regression_{year}'
 reportp=p/'postprocess_completion' if year==2022 else p
 rr=csv(reportp/'CORE_AND_FULL_ROUNDS.csv');aa=csv(p/'ACTIONS.csv');fc=csv(reportp/'FINANCIAL_COVERAGE.csv');cl=js(p/'CLAIMS.json');br=js(p/'BRIDGES.json')
 assert rr.arm.eq('A_UNION_B').all() and aa.arm.eq('A_UNION_B').all()
 rd=rr.merge(f,left_on=['sid','signal_day'],right_on=['sid','day'],validate='one_to_one');rd['year']=year
 assert len(rd)==len(rr);assert rr.round_id.is_unique and fc.round_id.is_unique
 for col in ['financial_coverage_status','evidence_usable_closed','coverage_reasons']:
  a=rr.set_index('round_id')[col].fillna('').sort_index();b=fc.set_index('round_id')[col].fillna('').sort_index();pd.testing.assert_series_equal(a,b)
 acts={rid:g for rid,g in aa.groupby('round_id',sort=False)}
 claimby=defaultdict(list)
 for c in cl:claimby[c['owner_round_id']].append(c)
 buys=aa[aa.side.eq('buy_core')];sells=aa[aa.side.eq('sell_all')]
 assert buys.round_id.is_unique and sells.round_id.is_unique
 bd=buys.set_index('round_id').to_dict('index');ed=sells.set_index('round_id').to_dict('index')
 rd['had_actual_proxy_initial_buy']=rd.round_id.isin(bd)
 rd['had_saved_full_exit']=rd.round_id.isin(ed)
 rd['full_exit_action_day']=rd.round_id.map(lambda rid:ed.get(rid,{}).get('day'))
 for r in rd.to_dict('records'):
  rid=r['round_id'];g=acts.get(rid,aa.iloc[:0]);inv=0;cash=D(0);fees=D(0);buycash=D(0)
  for idx,a in g.iterrows():
   q=int(a.q);isbuy=a.side.startswith('buy');before=inv;inv+=q if isbuy else -q
   assert inv>=0
   if a.side=='buy_core':assert before==0
   if a.side=='sell_all':assert inv==0
   v=D(str(a.price))*q;fee=D(str(a.fee));fees+=fee;cash+=-v-fee if isbuy else v-fee
   if isbuy:buycash+=v+fee
   actionrows.append(dict(year=year,round_id=rid,sid=r['sid'],action_row=int(idx),day=a.day,side=a.side,q=q,inventory_before=before,inventory_after=inv,price=a.price,fee=a.fee,signal_day=a.signal_day,is_full_exit=a.side=='sell_all'))
  assert int(r['core_qty'] if pd.notna(r['core_qty']) else 0)+int(r['add_qty'] if pd.notna(r['add_qty']) else 0)==inv
  assert r['had_actual_proxy_initial_buy']==pd.notna(r['entry_day'])
  if r['had_actual_proxy_initial_buy']:
   assert bd[rid]['day']==r['entry_day'] and int(bd[rid]['q'])==int(r['entry_q'])
  div=sum((D(str(c['amount'])) for c in claimby[rid] if c['recognized']),D(0))
  divpaid=sum((D(str(c['amount'])) for c in claimby[rid] if c['settled']),D(0))
  net=cash+div
  def chk(actual,expected,label):
   if pd.isna(expected):return None
   diff=float(actual)-float(expected);assert abs(diff)<1e-7,(year,rid,label,diff);return diff
  difffees=chk(fees,r['all_fees'],'fees');diffbuy=chk(buycash,r['total_buy_cash'],'buy_cash')
  diffdiv=chk(div,r['dividend_net80_total'],'dividend');diffpaid=chk(divpaid,r['dividend_net80_paid'],'paid')
  diffcash=chk(cash+divpaid,r['cash_after_payouts'],'cash_after_payouts')
  diffrecv=chk(div-divpaid,r['receivable_after_payouts'],'receivable')
  diffnet=chk(net,r['net_pnl'],'net') if r['status']=='COMPLETE_CONDITIONAL_STOCK_ROUND' else None
  recon.append(dict(year=year,round_id=rid,status=r['status'],action_count=len(g),inventory_end=inv,action_cash_net=float(cash),recognized_dividend=float(div),paid_dividend=float(divpaid),recomputed_closed_net=float(net) if r['status']=='COMPLETE_CONDITIONAL_STOCK_ROUND' else None,saved_net_pnl=r['net_pnl'],net_diff=diffnet,fees_diff=difffees,buy_cash_diff=diffbuy,cash_after_payouts_diff=diffcash,receivable_diff=diffrecv))
 # Actual initial entries only; registration or i_buy counts never substitutes.
 rd['actual_initial_buy_ordinal_in_window']=pd.NA;rd['prior_actual_same_I_count']=0;rd['prior_actual_same_I_round_id']=None;rd['prior_actual_same_I_exit_day']=None
 rd['actual_I_participation']='NOT_BOUGHT';rd['previous_actual_round_id']=None
 past=defaultdict(list)
 for idx,r in rd[rd.had_actual_proxy_initial_buy].sort_values(['sid','entry_day','round_id']).iterrows():
  prior=past[r.sid];same=[z for z in prior if z['i_epoch']==r.i_epoch and z['i_epoch_lineage_known'] and r.i_epoch_lineage_known and z['i_target'] and r.i_target]
  rd.loc[idx,'actual_initial_buy_ordinal_in_window']=len(prior)+1
  if prior:
   pp=prior[-1];assert pp['round_id'] in ed,('PREVIOUS_NOT_FLAT',r.round_id,pp['round_id'])
   assert ed[pp['round_id']]['day']<=r.signal_day<r.entry_day,('CLOCK',r.round_id)
   rd.loc[idx,'previous_actual_round_id']=pp['round_id']
  rd.loc[idx,'prior_actual_same_I_count']=len(same)
  if not r.i_epoch_lineage_known:part='I_EPOCH_UNKNOWN'
  elif same:
   pp=same[-1];exitday=ed[pp['round_id']]['day'];assert exitday<=r.signal_day
   part='SAME_I_REENTRY_AFTER_FULL_EXIT';rd.loc[idx,'prior_actual_same_I_round_id']=pp['round_id'];rd.loc[idx,'prior_actual_same_I_exit_day']=exitday
  else:part='FIRST_ACTUAL_INITIAL_IN_THIS_I_WITHIN_WINDOW'
  rd.loc[idx,'actual_I_participation']=part;past[r.sid].append(r.to_dict())
 def financial(r):
  if 'UNKNOWN' in r.status:return 'EXECUTION_PATH_UNKNOWN'
  if not r.had_actual_proxy_initial_buy:return 'NO_BUY_NOFILL' if 'NOFILL' in r.status else 'NO_BUY_OTHER'
  if 'CENSORED' in r.status:return 'CENSORED'
  if r.financial_coverage_status=='COVERAGE_UNKNOWN':return 'CLOSED_FINANCIAL_COVERAGE_UNKNOWN'
  if r.status=='COMPLETE_CONDITIONAL_STOCK_ROUND' and r.evidence_usable_closed:return 'CLOSED_COVERED_NONORDINARY_ACTIONS' if r.financial_coverage_status=='VERIFIED_ACTIONS_SCENARIO' else 'CLOSED_COVERED_ORDINARY_NO_ACTION'
  return 'OTHER_UNRESOLVED'
 rd['financial_path_group']=rd.apply(financial,axis=1)
 rd['full_outcome_usable']=rd.financial_path_group.isin(['CLOSED_COVERED_ORDINARY_NO_ACTION','CLOSED_COVERED_NONORDINARY_ACTIONS'])
 rd['full_net_R_initial_risk']=np.where(rd.full_outcome_usable & rd.entry_risk.gt(0),rd.net_pnl/rd.entry_risk,np.nan)
 rd['closed_financial_unknown_with_numeric_saved_net']=rd.financial_path_group.eq('CLOSED_FINANCIAL_COVERAGE_UNKNOWN') & rd.net_pnl.notna()
 rd['economic_evidence_domain']='SAVED_INDEPENDENT_STOCK_CONDITIONAL_PROXY_NET80_NOT_ACCOUNT_NOT_BROKER'
 allrounds.append(rd);fc['year']=year;finrows.append(fc)
 checks.append(dict(year=year,registrations=len(rr),actual_initial_buys=len(buys),sell_all=len(sells),actions=len(aa),covered_closed=int(rd.full_outcome_usable.sum()),execution_unknown=int(rd.status.str.contains('UNKNOWN').sum()),financial_unknown=int(rd.financial_coverage_status.eq('COVERAGE_UNKNOWN').sum()),unbought=int((~rd.had_actual_proxy_initial_buy).sum()),known_same_I_reentries=int(rd.actual_I_participation.eq('SAME_I_REENTRY_AFTER_FULL_EXIT').sum())))
z=pd.concat(allrounds,ignore_index=True)
out('ALL_REGISTERED_ROUNDS_ATTRIBUTED.csv',z);out('ALL_ACTUAL_ACTIONS_RECONCILED.csv',pd.DataFrame(actionrows));out('ROUND_ACTION_CASH_RECONCILIATION.csv',pd.DataFrame(recon));out('FULL_FINANCIAL_PATH_COVERAGE.csv',pd.concat(finrows,ignore_index=True))
out('SAME_I_REENTRY_AFTER_FULL_EXIT.csv',z[z.actual_I_participation.eq('SAME_I_REENTRY_AFTER_FULL_EXIT')])
out('UNKNOWN_AND_NO_BUY_ROUNDS.csv',z[~z.full_outcome_usable])
def metrics(g):
 c=g[g.full_outcome_usable];w=c[c.net_pnl>0];l=c[c.net_pnl<0];zero=c[c.net_pnl==0]
 return dict(registered=len(g),actual_buys=int(g.had_actual_proxy_initial_buy.sum()),usable_closed=len(c),W=len(w),L=len(l),zero=len(zero),win_rate=len(w)/len(c) if len(c) else None,mean_win_cny=w.net_pnl.mean(),mean_loss_cny=l.net_pnl.mean(),payoff_mean_win_over_abs_loss=w.net_pnl.mean()/abs(l.net_pnl.mean()) if len(w) and len(l) else None,net_sum_cny=c.net_pnl.sum(),mean_net_cny=c.net_pnl.mean(),mean_full_return=c.net_return_on_buy_cash.mean(),mean_win_return=w.net_return_on_buy_cash.mean(),mean_loss_return=l.net_return_on_buy_cash.mean(),tail_ge30_count=int(c.net_return_on_buy_cash.ge(.3).sum()),tail_ge30_net_cny=c.loc[c.net_return_on_buy_cash.ge(.3),'net_pnl'].sum(),tail_gt3_initial_R_count=int(c.full_net_R_initial_risk.gt(3).sum()),tail_gt3_initial_R_net_cny=c.loc[c.full_net_R_initial_risk.gt(3),'net_pnl'].sum(),risk_denominator_missing=int(c.entry_risk.isna().sum()+c.entry_risk.le(0).sum()),unknown_execution=int(g.status.str.contains('UNKNOWN').sum()),unknown_financial_closed=int(g.financial_path_group.eq('CLOSED_FINANCIAL_COVERAGE_UNKNOWN').sum()),nonordinary_covered=int(g.financial_path_group.eq('CLOSED_COVERED_NONORDINARY_ACTIONS').sum()),not_bought=int((~g.had_actual_proxy_initial_buy).sum()),censored=int(g.status.str.contains('CENSORED').sum()),raw_numeric_saved_net_all_status_sum=g.net_pnl.sum())
summary=[]
for dims in [[],['i_group'],['cp_group'],['actual_I_participation'],['financial_path_group'],['event_type'],['i_hwm_group'],['i_group','event_type'],['i_group','financial_path_group'],['i_group','actual_I_participation'],['i_group','cp_group'],['i_group','i_hwm_group']]:
 for key,g in z.groupby(['year']+dims,dropna=False,sort=True):
  if not isinstance(key,tuple):key=(key,)
  summary.append(dict(dimension='ALL' if not dims else '+'.join(dims),**dict(zip(['year']+dims,key)),**metrics(g)))
su=pd.DataFrame(summary);out('FULL_NET_SUMMARY.csv',su)
dd=pre.merge(z[['year','round_id','had_actual_proxy_initial_buy','financial_path_group','full_outcome_usable']],on=['year','round_id'],how='left',validate='many_to_one')
dd['registration_outcome']=np.where(dd.selected,dd.financial_path_group,'NOT_SELECTED_'+dd.decision)
out('ALL_AB_DECISIONS_WITH_OUTCOME_CLASS.csv',dd)
out('ALL_DECISION_FUNNEL_COUNTS.csv',dd.groupby(['year','i_group','cp_group','event_type','decision','registration_outcome'],dropna=False).size().rename('signals').reset_index())
# Split prior-count independently from on-day permit; no post-hoc thresholds.
out('PRIOR_I_BUY_EXACT_COUNT_SUMMARY.csv',z.groupby(['year','prior_i_buy_known_count','i_group'],dropna=False).apply(lambda g:pd.Series(metrics(g)),include_groups=False).reset_index())
tail=z[z.full_outcome_usable & (z.net_return_on_buy_cash.ge(.3)|z.full_net_R_initial_risk.gt(3))]
out('COMPLETE_FULL_TAILS.csv',tail)
for year in (2022,2024):
 q=z[z.year.eq(year)];a=su[su.year.eq(year)&su.dimension.eq('i_group')]
 assert int(a.registered.sum())==len(q)
 assert int(a.W.sum()+a.L.sum()+a.zero.sum())==int(q.full_outcome_usable.sum())
 assert abs(a.net_sum_cny.sum()-q.loc[q.full_outcome_usable,'net_pnl'].sum())<1e-7
 assert abs(a.raw_numeric_saved_net_all_status_sum.sum()-q.net_pnl.sum())<1e-7
assert all(sha(p)==h for p,h in HASHES.items())
dump('SOURCE_HASHES.json',HASHES)
qa=dict(passed=True,checks=checks,source_hashes=len(HASHES),source_hashes_unchanged=True,prelabel_feature_seal_unchanged=all(sha(O/n)==h for n,h in js(O/'FEATURE_SEAL.json').items()),unique_signal_queries=len(f),all_decisions=len(pre),registered_rounds=len(z),market_overlap_rows_read=748542,all_history_stocks=len(query_by),overlap_exact_state_mismatches=len(mismatch),all_action_cash_reconciliation=True,all_groups_partition=True,new_economic_runs=0,consumers_imported=0,PRICE_economic_data_used=False,elapsed_seconds=time.monotonic()-began)
dump('QA.json',qa)
dump('OUTPUT_HASHES.json',{p.name:sha(p) for p in O.iterdir() if p.is_file() and p.name!='OUTPUT_HASHES.json'})
print(json.dumps(clean(qa),ensure_ascii=False),flush=True)
print(su[su.dimension.isin(['ALL','i_group','actual_I_participation'])][['year','dimension','i_group','actual_I_participation','registered','actual_buys','usable_closed','W','L','zero','win_rate','payoff_mean_win_over_abs_loss','net_sum_cny','tail_ge30_count','tail_gt3_initial_R_count','unknown_execution','unknown_financial_closed']].to_string(index=False),flush=True)
