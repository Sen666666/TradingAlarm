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
for num,(sid,wanted) in enumerate(sorted(query_by.items()),1):
 rec=manifest[sid];expected={**rec['source_sha256'],**rec['output_sha256']}
 sp=next(p for p in rec['source_sha256'] if p.endswith('/signal.parquet'))
 ff=pd.read_parquet(src(rec['refs']['facts'],expected[rec['refs']['facts']]))
 raw=pd.read_parquet(src(sp,expected[sp]),columns=['source_kind','source_path','segment_id'])
 cp=pd.read_parquet(src(rec['refs']['CP1'],expected[rec['refs']['CP1']]),columns=['ready','receipt','delta_frontier','reset_reason'])
 assert ff.index.is_unique and raw.index.is_unique and cp.index.is_unique
 assert ff.index.is_monotonic_increasing and raw.index.is_monotonic_increasing
 # All original daily state rows through the latest signal are used, including warm history.
 end=max(wanted);cc=cal[cal<=end];exact=ff.reindex(cc);asof=ff[['i_target','segment_id']].reindex(cc,method='ffill');rz=raw.reindex(cc);cz=cp.reindex(cc)
 # Full native epoch identity matches sealed prior reference, including as-of suspensions.
 last=None;counter=0;root_known=False;root_reason='NO_KNOWN_ACTIVE_ROOT';prev_exact=None;prev_i=None
 obs_i=0;obs_cp=0;birth=None;maxclose=None;known_birth=False;seen_unknown=False;rows_this=0
 for day,ar,er,rr,cr in zip(cc,asof.to_dict('records'),exact.to_dict('records'),rz.to_dict('records'),cz.to_dict('records')):
  target=tri(ar['i_target']) if pd.notna(ar['segment_id']) else False
  seg=int(ar['segment_id']) if pd.notna(ar['segment_id']) else -1;key=(target,seg)
  newkey=key!=last
  if newkey:
   counter+=1;last=key;obs_i=0;obs_cp=0;birth=None;maxclose=None;known_birth=False;seen_unknown=False
  lin=tuple(str(rr.get(k)) for k in ['source_kind','source_path','segment_id'])
  known=tri(er['i_target']) is not None and pd.notna(er['segment_id']) and all(pd.notna(rr.get(k)) for k in ['source_kind','source_path','segment_id']) and int(er['segment_id'])==int(rr['segment_id'])
  current=tri(er['i_target']);adjacent=known and prev_exact is not None and lin==prev_exact
  if current is False:root_known=False;root_reason='I_OFF'
  elif current is True and prev_i is False and adjacent:root_known=True;root_reason='KNOWN_I_0_TO_1';birth=day;known_birth=True
  elif current is True and not adjacent:root_known=False;root_reason='MISSING_OR_CHANGED_LINEAGE';seen_unknown=True
  elif current is None:root_known=False;root_reason='CURRENT_I_UNKNOWN';seen_unknown=True
  if current is True and birth is None:birth=day
  ib=tri(er.get('i_buy'));cpr=tri(cr.get('receipt'))
  pri_i=obs_i;pri_cp=obs_cp
  if current is True:
   if ib:obs_i+=1
   if cpr:obs_cp+=1
  close=er.get('close');previous_max=maxclose
  if current is True and pd.notna(close):maxclose=float(close) if maxclose is None else max(maxclose,float(close))
  daystr=str(day.date());epoch=f'{sid}|{seg}|{counter}'
  if daystr in wanted:
   if current is None:ig='MARKET_STATE_UNKNOWN'
   elif current is False:ig='I_OFF'
   elif not root_known or not known_birth:ig='I_EPOCH_UNKNOWN_OR_LEFT_TRUNCATED'
   elif ib is True:ig='I_BUY_FIRST' if obs_i==1 else 'I_BUY_REPEAT'
   elif ib is False:ig='OTHER_NOT_I_BUY'
   else:ig='MARKET_STATE_UNKNOWN'
   ovv=ovmap[(sid,daystr)]
   cptrace=tri(ovv.get('old_cp_trace_known'))
   if current is None or cpr is None:cg='CP_TRACE_OR_EPOCH_UNKNOWN'
   elif not cpr:cg='NO_CP_TODAY'
   elif not root_known or not known_birth or cptrace is not True:cg='CP_TRACE_OR_EPOCH_UNKNOWN'
   else:cg='CP_FIRST_IN_I' if obs_cp==1 else 'CP_REPEAT_IN_I'
   hwm='UNKNOWN' if not root_known or not known_birth or pd.isna(close) else 'FIRST_I_DAY' if birth==day else 'NEW_I_HWM' if previous_max is not None and close>previous_max else 'BELOW_OR_EQUAL'
   row=dict(sid=sid,day=daystr,i_epoch=epoch,i_birth_observed_day=str(birth.date()) if birth is not None else None,i_birth_known=known_birth,i_epoch_lineage_known=root_known,i_epoch_lineage_reason=root_reason,i_epoch_seen_unknown=seen_unknown,i_target=current,e0_target=tri(er.get('e0_target')),i_buy=ib,i_group=ig,prior_i_buy_observed_count=pri_i if current is True else None,i_buy_observed_ordinal=obs_i if ib is True and current is True else None,prior_i_buy_known_count=pri_i if root_known and known_birth else None,i_buy_known_ordinal=obs_i if ib is True and root_known and known_birth else None,cp_receipt=cpr,cp_ready=tri(cr.get('ready')),cp_trace_known=cptrace,cp_group=cg,prior_cp_observed_count=pri_cp if current is True else None,cp_observed_ordinal=obs_cp if cpr is True and current is True else None,cp_known_ordinal=obs_cp if cpr is True and root_known and known_birth and cptrace is True else None,close=close,prior_I_high_close=previous_max,i_hwm_group=hwm,source_segment=seg,source_kind=rr.get('source_kind'),source_path=rr.get('source_path'),source_first_day=str(ff.index.min().date()),source_history_days_before_signal=int(ff.index.searchsorted(day)))
   for ours,old in [('i_epoch','old_i_epoch'),('i_buy','old_i_buy'),('i_target','old_i_target'),('e0_target','old_e0_target'),('i_epoch_lineage_known','old_epoch_lineage_known'),('i_epoch_lineage_reason','old_epoch_lineage_reason'),('cp_receipt','old_cp_fresh')]:
    a=row[ours];b=ovv.get(old)
    equal=(pd.isna(a) and pd.isna(b)) or (pd.notna(a) and pd.notna(b) and a==b)
    if not equal:mismatch.append(dict(sid=sid,day=daystr,field=ours,ours=a,sealed=b))
   features.append(row);rows_this+=1
  if current is True and newkey:
   epochs_out.append(dict(sid=sid,i_epoch=epoch,birth_observed_day=str(day.date()),birth_known=root_known,birth_reason=root_reason,source_first_day=str(ff.index.min().date())))
  prev_exact=lin if known else None;prev_i=current
 assert rows_this==len(wanted),(sid,rows_this,len(wanted))
 coverage.append(dict(sid=sid,source_rows=len(ff),full_history_first_day=str(ff.index.min().date()),full_history_last_day=str(ff.index.max().date()),common_clock_scanned=len(cc),query_signals=len(wanted),all_query_days_in_facts=all(pd.Timestamp(t) in ff.index for t in wanted),all_facts_days_on_common_clock_before_last_signal=ff.loc[:end].index.isin(cc).all()))
 if num%250==0:print('STATE_HISTORY',num,len(query_by),round(time.monotonic()-began,1),flush=True)
f=pd.DataFrame(features);assert len(f)==len(queries) and not f.duplicated(['sid','day']).any()
out('OVERLAP_STATE_MISMATCHES.csv',pd.DataFrame(mismatch,columns=['sid','day','field','ours','sealed']))
assert not mismatch,('SEALED_STATE_MISMATCH',len(mismatch))
out('SIGNAL_STATE_PRELABEL.csv',f);out('SOURCE_HISTORY_COVERAGE.csv',pd.DataFrame(coverage));out('I_EPOCH_BIRTHS_PRELABEL.csv',pd.DataFrame(epochs_out))
pre=dec.merge(f,on=['sid','day'],validate='many_to_one')
out('ALL_AB_DECISIONS_PRELABEL.csv',pre)
dump('FEATURE_SEAL.json',{n:sha(O/n) for n in ['PROTOCOL.json','audit_saved.py','SIGNAL_STATE_PRELABEL.csv','ALL_AB_DECISIONS_PRELABEL.csv','SOURCE_HISTORY_COVERAGE.csv','I_EPOCH_BIRTHS_PRELABEL.csv']})
print('FEATURES_SEALED',len(pre),'elapsed',round(time.monotonic()-began,1),flush=True)
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
  assert int(r['core_qty'])+int(r['add_qty'])==inv
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
